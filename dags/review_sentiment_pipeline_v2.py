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

MYSQL_CONN_ID = "mysql_reviews"
CHUNK_SIZE = int(os.getenv("REVIEW_CHUNK_SIZE", "50"))
REQUEST_DELAY_SECONDS = 3


def _chunked(items: List[Dict[str, Any]], chunk_size: int) -> List[List[Dict[str, Any]]]:
    return [items[i: i + chunk_size] for i in range(0, len(items), chunk_size)]


def _mysql_text_cell(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, (bytes, bytearray)):
        return bytes(val).decode("utf-8", errors="replace")
    return str(val)


_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")


def _repair_utf8_bytes_misdecoded_as_latin1(s: str) -> str:
    if not s:
        return s

    if _HANGUL_RE.search(s):
        return s

    try:
        repaired = s.encode("latin1").decode("utf-8")
        return repaired
    except UnicodeError:
        pass

    try:
        raw = bytes(ord(c) for c in s if ord(c) < 256)
        repaired = raw.decode("utf-8")
        return repaired
    except UnicodeError:
        return s


def _set_utf8mb4_session(cursor) -> None:
    cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.execute("SET CHARACTER SET utf8mb4")
    cursor.execute("SET character_set_connection = utf8mb4")
    cursor.execute("SET collation_connection = 'utf8mb4_unicode_ci'")


def extract_pending_reviews(**_: Dict[str, Any]) -> List[Dict[str, Any]]:
    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)

    sql = """
        SELECT review_id, user_id, review_text
        FROM reviews
        WHERE status = 'pending'
        ORDER BY review_id ASC
    """

    conn = hook.get_conn()
    try:
        with conn.cursor() as cursor:
            _set_utf8mb4_session(cursor)
            cursor.execute(sql)
            records = cursor.fetchall()
    finally:
        conn.close()

    reviews: List[Dict[str, Any]] = []
    repaired_count = 0

    for row in records:
        user_id = _mysql_text_cell(row[1])
        raw_review_text = _mysql_text_cell(row[2])
        repaired_review_text = _repair_utf8_bytes_misdecoded_as_latin1(raw_review_text)

        if raw_review_text != repaired_review_text:
            repaired_count += 1

        reviews.append(
            {
                "review_id": int(row[0]),
                "user_id": user_id,
                "review_text": repaired_review_text,
                "original_review_text": raw_review_text,
            }
        )

    logging.info(
        "Extracted %s pending reviews (repaired %s mojibake rows)",
        len(reviews),
        repaired_count,
    )
    return reviews


def call_review_api(**context: Dict[str, Any]) -> List[Dict[str, Any]]:
    ti = context["ti"]
    reviews = ti.xcom_pull(task_ids="extract_pending_reviews") or []
    if not reviews:
        logging.info("No pending reviews to process.")
        return []

    base_url = os.getenv("REVIEW_API_BASE_URL", "http://ai-api-server:8000").rstrip("/")
    url = f"{base_url}/analyze_reviews"

    connect_s = int(os.getenv("REVIEW_API_CONNECT_TIMEOUT", "15"))
    read_s = int(os.getenv("REVIEW_API_READ_TIMEOUT", "300"))
    timeout: Tuple[int, int] = (connect_s, read_s)

    all_results: List[Dict[str, Any]] = []

    for chunk_index, chunk in enumerate(_chunked(reviews, CHUNK_SIZE), start=1):
        logging.info(
            "POST %s chunk %s/%s (%s reviews)",
            url,
            chunk_index,
            (len(reviews) + CHUNK_SIZE - 1) // CHUNK_SIZE,
            len(chunk),
        )
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
            logging.info(
                "Chunk %s done: got %s rows (total %s)",
                chunk_index,
                len(chunk_results),
                len(all_results),
            )
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Failed on API chunk {chunk_index}: {exc}") from exc

        if chunk_index * CHUNK_SIZE < len(reviews):
            time.sleep(REQUEST_DELAY_SECONDS)

    repaired_map = {
        int(item["review_id"]): item["review_text"]
        for item in reviews
    }

    merged_results = []
    for item in all_results:
        review_id = int(item["review_id"])
        merged_results.append(
            {
                "review_id": review_id,
                "review_text": repaired_map[review_id],   # 복구된 텍스트 유지
                "sentiment": str(item["sentiment"]).lower(),
                "keywords": item.get("keywords", []),
            }
        )

    logging.info("Received %s analyzed results", len(merged_results))
    return merged_results

def load_analyzed_reviews(**context: Dict[str, Any]) -> int:
    ti = context["ti"]
    analyzed = ti.xcom_pull(task_ids="call_review_api") or []
    if not analyzed:
        return 0

    update_data = [
        (
            item["review_text"],  # review_text도 같이 저장
            str(item["sentiment"]).lower(),
            json.dumps(item.get("keywords", []), ensure_ascii=False).encode("utf-8").decode("utf-8"),
            int(item["review_id"]),
        )
        for item in analyzed
    ]

    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)

    with hook.get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET NAMES utf8mb4")
            cursor.execute("SET CHARACTER SET utf8mb4")
            cursor.execute("SET character_set_connection=utf8mb4")

            query = """
                UPDATE reviews
                SET review_text = %s,
                    sentiment = %s,
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
    dag_id="review_sentiment_pipeline_v2",
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
        task_id="extract_pending_reviews",
        python_callable=extract_pending_reviews,
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