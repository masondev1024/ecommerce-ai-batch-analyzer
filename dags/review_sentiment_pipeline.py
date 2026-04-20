import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.mysql.hooks.mysql import MySqlHook
from kafka import KafkaConsumer

MYSQL_CONN_ID = "mysql_reviews"
# Larger chunks for better throughput with local model
CHUNK_SIZE = int(os.getenv("REVIEW_CHUNK_SIZE", "500"))
REQUEST_DELAY_SECONDS = 1


def _chunked(items: List[Dict[str, Any]], chunk_size: int) -> List[List[Dict[str, Any]]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def _mysql_text_cell(val: Any) -> str:
    """Normalize DB cell to str; TEXT as bytes must be decoded as utf-8, not str(bytes)."""
    if val is None:
        return ""
    if isinstance(val, (bytes, bytearray)):
        return bytes(val).decode("utf-8", errors="replace")
    return str(val)


_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")


def _repair_utf8_bytes_misdecoded_as_latin1(s: str) -> str:
    """
    MySQL/client sometimes mis-decodes UTF-8 as latin1 (mojibake). Fix by reversing bytes.
    Do not skip the whole string if a few codepoints are >255 — that left text unrepaired.
    """
    if not s:
        return s
    if _HANGUL_RE.search(s):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except UnicodeError:
        pass
    try:
        raw = bytes(ord(c) for c in s if ord(c) < 256)
        return raw.decode("utf-8")
    except UnicodeError:
        return s


def extract_reviews_from_kafka(**_: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Consume reviews from Kafka topic."""
    consumer = KafkaConsumer(
        'reviews',
        bootstrap_servers=['kafka:29092'],
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='airflow-consumer',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    
    reviews = []
    timeout = 10  # seconds
    start_time = time.time()
    
    for message in consumer:
        reviews.append(message.value)
        if time.time() - start_time > timeout:
            break
    
    consumer.close()
    logging.info("Consumed %s reviews from Kafka", len(reviews))
    return reviews


def call_review_api(**context: Dict[str, Any]) -> List[Dict[str, Any]]:
    ti = context["ti"]
    reviews = ti.xcom_pull(task_ids="extract_pending_reviews") or []
    if not reviews:
        logging.info("No pending reviews to process.")
        return []

    # Docker: use service hostname (same compose network). Host browser uses localhost:8000; Airflow container does NOT.
    base_url = os.getenv("REVIEW_API_BASE_URL", "http://ai-api-server:8000").rstrip("/")
    url = f"{base_url}/analyze_reviews"
    # Gemini CLI can exceed 30s; use (connect, read) so slow reads don't look like a "hang".
    connect_s = int(os.getenv("REVIEW_API_CONNECT_TIMEOUT", "15"))
    read_s = int(os.getenv("REVIEW_API_READ_TIMEOUT", "300"))
    timeout: Tuple[int, int] = (connect_s, read_s)
    all_results: List[Dict[str, Any]] = []

    for chunk_index, chunk in enumerate(_chunked(reviews, CHUNK_SIZE), start=1):
        logging.info("POST %s chunk %s/%s (%s reviews)", url, chunk_index, (len(reviews) + CHUNK_SIZE - 1) // CHUNK_SIZE, len(chunk))
        try:
            response = requests.post(url, json=chunk, timeout=timeout)
            response.encoding = "utf-8"
            if not response.ok:
                logging.error(
                    "API HTTP %s — response body (truncated): %s",
                    response.status_code,
                    (response.text or "")[:4000],
                )
            response.raise_for_status()
            chunk_results = response.json()
            if not isinstance(chunk_results, list):
                raise ValueError("API response is not a list")
            all_results.extend(chunk_results)
            logging.info("Chunk %s done: got %s rows (total %s)", chunk_index, len(chunk_results), len(all_results))
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Failed on API chunk {chunk_index}: {exc}") from exc

        if chunk_index * CHUNK_SIZE < len(reviews):
            time.sleep(REQUEST_DELAY_SECONDS)

    logging.info("Received %s analyzed results", len(all_results))
    return all_results

def load_analyzed_reviews(**context: Dict[str, Any]) -> int:
    ti = context["ti"]
    analyzed = ti.xcom_pull(task_ids="call_review_api") or []
    if not analyzed:
        return 0

    # 데이터 직렬화 (이 단계에서 한글이 살아있는지 확인은 이미 되셨음)
    update_data = [
        (
            str(item["sentiment"]).lower(),
            json.dumps(item.get("keywords", []), ensure_ascii=False), 
            int(item["review_id"])
        )
        for item in analyzed
    ]

    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)
    
    with hook.get_conn() as conn:
        with conn.cursor() as cursor:
            # [수정] 쿼리 실행 직전에 세션 인코딩을 강력하게 고정
            cursor.execute("SET NAMES utf8mb4")
            cursor.execute("SET CHARACTER SET utf8mb4")
            cursor.execute("SET character_set_connection=utf8mb4")
            
            query = """
                UPDATE reviews
                SET sentiment = %s,
                    keywords = %s,
                    status = 'completed'
                WHERE review_id = %s
                  AND status = 'pending'
            """
            cursor.executemany(query, update_data)
            conn.commit()
            updated_count = cursor.rowcount

    logging.info("Updated %s reviews", updated_count)
    return updated_count

with DAG(
    dag_id="review_sentiment_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule_interval="@daily",
    catchup=False,
    default_args={
        "owner": "data-team",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["ecommerce", "review", "gemini", "batch"],
) as dag:
    t1 = PythonOperator(
        task_id="extract_reviews_from_kafka",
        python_callable=extract_reviews_from_kafka,
    )

    t2 = PythonOperator(
        task_id="call_review_api",
        python_callable=call_review_api,
    )

    t3 = PythonOperator(
        task_id="load_analyzed_reviews",
        python_callable=load_analyzed_reviews,
    )

    t1 >> t2 >> t3
