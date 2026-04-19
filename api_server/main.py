import json
import logging
import os
import asyncio
from typing import Any, Dict, List, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

# Google Generative AI 공식 SDK 임포트
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core.exceptions import ResourceExhausted, InternalServerError

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
# API Key 초기화
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.warning("GEMINI_API_KEY is not set in environment variables.")
else:
    genai.configure(api_key=api_key)

# 동시성 제어: 한 번에 LLM API로 날아가는 최대 동시 요청 수
# 이 값이 너무 크면 429 Rate Limit 에러가 빈발하며, 너무 작으면 처리 속도가 느려집니다.
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "10"))
semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

def _gemini_model_id() -> str:
    raw = (os.getenv("GEMINI_MODEL") or "gemini-2.0-flash").strip()
    return raw.replace("models/", "")

def _build_single_prompt(review: ReviewIn) -> str:
    return (
        "You are an expert AI data analyst highly trained in Korean Natural Language Processing (NLP). "
        "Analyze the sentiment of the provided Korean review and extract 2-3 key phrases.\n\n"
        "INSTRUCTIONS:\n"
        "1. Determine the sentiment strictly as one of: 'positive', 'negative', or 'neutral'.\n"
        "2. Extract 2-3 important keywords (in Korean).\n"
        "3. Output MUST be a valid JSON object with keys: 'sentiment' (string) and 'keywords' (array of strings).\n\n"
        f"REVIEW TEXT:\n{review.review_text}"
    )

async def _analyze_single_review_async(review: ReviewIn, model: genai.GenerativeModel) -> ReviewOut:
    """단일 리뷰를 분석하며, Rate Limit 발생 시 지수 백오프(Exponential Backoff)로 재시도합니다."""
    prompt = _build_single_prompt(review)
    max_retries = 3
    base_delay = 2.0

    for attempt in range(max_retries):
        try:
            # 세마포어를 통해 동시 실행되는 코루틴의 수를 제한
            async with semaphore:
                response = await model.generate_content_async(
                    prompt,
                    # JSON 모드 강제: 응답이 반드시 JSON 구조를 띄도록 강제 (Gemini 1.5 Pro/Flash 이상 지원)
                    generation_config=GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.0
                    )
                )
            
            # 파싱 로직: JSON 모드를 사용하므로 정규식 없이 바로 loads 가능
            result_dict = json.loads(response.text)
            return ReviewOut(
                review_id=review.review_id,
                sentiment=str(result_dict.get("sentiment", "unknown")).lower(),
                keywords=[str(k) for k in result_dict.get("keywords", [])]
            )

        except ResourceExhausted:
            wait_time = base_delay * (2 ** attempt)
            logger.warning("Rate limit hit for review_id %s. Retrying in %s seconds...", review.review_id, wait_time)
            await asyncio.sleep(wait_time)
        except (InternalServerError, Exception) as exc:
            logger.error("Failed to process review_id %s: %s", review.review_id, exc)
            return ReviewOut(review_id=review.review_id, sentiment="error_parsing", keywords=[])

    # 최대 재시도 횟수 초과
    logger.error("Max retries exceeded for review_id %s", review.review_id)
    return ReviewOut(review_id=review.review_id, sentiment="error_parsing", keywords=[])


@app.get("/")
def home() -> dict[str, str]:
    return {"status": "Async AI Sentiment API Running"}

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/analyze_reviews", response_model=List[ReviewOut])
async def analyze_reviews(reviews: List[ReviewIn]) -> List[ReviewOut]:
    """
    수신된 리뷰 리스트를 비동기 태스크로 분할하여 병렬 처리합니다.
    """
    if not reviews:
        return []

    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    model_name = _gemini_model_id()
    model = genai.GenerativeModel(model_name)

    # 모든 리뷰에 대해 비동기 태스크 생성
    tasks = [_analyze_single_review_async(review, model) for review in reviews]
    
    # asyncio.gather를 통해 모든 태스크를 동시에 실행 (세마포어에 의해 실제 동시 실행 수는 통제됨)
    results = await asyncio.gather(*tasks)
    
    return list(results)