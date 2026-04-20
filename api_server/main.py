import json
import logging
import os
import asyncio
from typing import Any, Dict, List, Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

# Hugging Face Transformers for local sentiment analysis
from transformers import pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
import re

# Monitoring
from prometheus_client import Counter, Histogram, generate_latest
import redis

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"

app = FastAPI(
    title="Async Review Sentiment API",
    default_response_class=UTF8JSONResponse,
)

# Middleware for metrics
@app.middleware("http")
async def add_metrics(request: Request, call_next):
    start_time = REQUEST_LATENCY.time()
    response = await call_next(request)
    REQUEST_LATENCY.labels(method=request.method, endpoint=request.url.path).observe(start_time)
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, status=response.status_code).inc()
    return response

logger = logging.getLogger(__name__)

# --- Models ---
class ReviewIn(BaseModel):
    review_id: int
    user_id: str = Field(min_length=1)
    review_text: str = Field(min_length=1)

class ReviewOut(BaseModel):
    review_id: int
    sentiment: Literal["positive", "negative", "neutral", "error_parsing", "unknown"] = "unknown"
    keywords: List[str] = Field(default_factory=list)

# --- Global Initialization ---
# Load Hugging Face sentiment analysis model
sentiment_model = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")

# TF-IDF for keyword extraction
vectorizer = TfidfVectorizer(max_features=100, stop_words=None)  # Adjust as needed

# 동시성 제어: 한 번에 처리되는 최대 동시 요청 수
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "10"))
semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

# Monitoring metrics
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('api_request_duration_seconds', 'Request duration in seconds', ['method', 'endpoint'])

# Redis for caching
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

def _extract_keywords(text: str, num_keywords: int = 3) -> List[str]:
    """Extract top keywords using TF-IDF."""
    try:
        # Simple tokenization (for Korean, better to use konlpy, but keeping simple)
        words = re.findall(r'\b\w+\b', text)
        if len(words) < num_keywords:
            return words[:num_keywords]
        tfidf_matrix = vectorizer.fit_transform([text])
        feature_names = vectorizer.get_feature_names_out()
        scores = tfidf_matrix.toarray()[0]
        top_indices = scores.argsort()[-num_keywords:][::-1]
        return [feature_names[i] for i in top_indices]
    except Exception:
        return []

async def _analyze_single_review_async(review: ReviewIn) -> ReviewOut:
    """Analyze single review using local Hugging Face model with Redis caching."""
    cache_key = f"review:{review.review_id}"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        return ReviewOut.parse_raw(cached_result)
    
    try:
        async with semaphore:
            # Sentiment analysis
            result = sentiment_model(review.review_text)[0]
            label = result['label']  # e.g., '1 star', '2 stars', etc.
            # Map to positive, negative, neutral
            if '1' in label or '2' in label:
                sentiment = 'negative'
            elif '4' in label or '5' in label:
                sentiment = 'positive'
            else:
                sentiment = 'neutral'
            
            # Keyword extraction
            keywords = _extract_keywords(review.review_text)
            
            review_out = ReviewOut(
                review_id=review.review_id,
                sentiment=sentiment,
                keywords=keywords
            )
            
            # Cache result
            redis_client.setex(cache_key, 3600, review_out.json())  # Cache for 1 hour
            
            return review_out
    except Exception as exc:
        logger.error("Failed to process review_id %s: %s", review.review_id, exc)
        return ReviewOut(review_id=review.review_id, sentiment="error_parsing", keywords=[])


@app.get("/")
def home() -> dict[str, str]:
    return {"status": "Async AI Sentiment API Running"}

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/metrics")
def metrics():
    return generate_latest()

@app.post("/analyze_reviews", response_model=List[ReviewOut])
async def analyze_reviews(reviews: List[ReviewIn]) -> List[ReviewOut]:
    """
    수신된 리뷰 리스트를 비동기 태스크로 분할하여 병렬 처리합니다.
    """
    if not reviews:
        return []

    # 모든 리뷰에 대해 비동기 태스크 생성
    tasks = [_analyze_single_review_async(review) for review in reviews]
    
    # asyncio.gather를 통해 모든 태스크를 동시에 실행 (세마포어에 의해 실제 동시 실행 수는 통제됨)
    results = await asyncio.gather(*tasks)
    
    return list(results)