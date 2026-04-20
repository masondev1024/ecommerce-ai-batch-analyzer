# E-commerce AI Batch Analyzer: 비용 최적화 및 성능 향상 분석 및 수정 보고서

## 📋 프로젝트 개요

이 프로젝트는 E-commerce 리뷰 데이터를 배치 처리하여 감정 분석 및 키워드 추출을 수행하는 마이크로서비스 아키텍처(MSA) 기반 데이터 파이프라인입니다. 원래 Google Gemini AI API를 사용하여 감정 분석을 수행했으나, 5만 개 데이터 처리 시 예상되는 높은 API 비용 문제를 해결하기 위해 로컬 모델 기반으로 전환하였습니다.

## 🔍 기존 구조 분석

### 아키텍처 구성 요소
- **Orchestration (Apache Airflow):** 스케줄링, 태스크 의존성 관리, 데이터베이스 I/O 처리
- **AI Inference (FastAPI):** Gemini AI API와 통신하는 독립적인 API 서버
- **Data Warehouse (MySQL):** 원본 및 분석된 리뷰 데이터 저장
- **Metadata DB (PostgreSQL):** Airflow 내부 메타데이터 저장

### 기존 처리 흐름
1. Airflow DAG가 MySQL에서 `status = 'pending'`인 리뷰를 추출
2. 50개씩 청크로 나누어 FastAPI 서버로 전송
3. FastAPI 서버가 각 리뷰를 Gemini API로 분석 (비동기 처리, 세마포어로 동시성 제어)
4. 분석 결과를 MySQL에 업데이트

### 비용 문제점
- Gemini API는 유료 서비스로, 각 요청마다 비용 발생
- 5만 개 데이터 × 요청 비용 = 예상 수십~수백 달러 비용 발생
- API Rate Limit으로 인한 처리 지연 가능성

## 🛠 수정 사항 및 기술 스택 변경

### 1. AI 모델 교체: Gemini API → Hugging Face 로컬 모델
**수정 파일:** `api_server/main.py`, `api_server/requirements.txt`

**변경 내용:**
- Google Generative AI SDK 제거
- Hugging Face Transformers 라이브러리 추가
- 감정 분석 모델: `nlptown/bert-base-multilingual-uncased-sentiment` (다국어 지원)
- 키워드 추출: TF-IDF 기반 간단한 키워드 추출 구현

**기술 스택 변경:**
```python
# 기존
import google.generativeai as genai

# 변경 후
from transformers import pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
```

### 2. 배치 처리 최적화
**수정 파일:** `dags/review_sentiment_pipeline.py`

**변경 내용:**
- 청크 사이즈: 50 → 500개로 증가 (더 큰 배치 처리)
- 요청 간 딜레이: 3초 → 1초로 감소 (로컬 처리로 Rate Limit 없음)

### 3. 의존성 업데이트
**수정 파일:** `api_server/requirements.txt`

**추가 라이브러리:**
- `transformers`: Hugging Face 모델 로딩 및 추론
- `torch`: PyTorch (Transformers 백엔드)
- `scikit-learn`: TF-IDF 키워드 추출

## ⚡ 성능 및 비용 최적화 원리

### 1. 비용 절감 원리
- **API 비용 제거:** 로컬 모델 실행으로 외부 API 호출 비용 0원
- **확장성:** GPU 활용 시 더 빠른 처리 가능
- **무제한 처리:** Rate Limit 없이 로컬 리소스 한계 내에서 무제한 처리

### 2. 처리 속도 향상 원리
- **병렬 처리 유지:** asyncio + 세마포어로 동시성 제어 유지
- **큰 배치 처리:** 청크 사이즈 증가로 네트워크 오버헤드 감소
- **로컬 추론:** 네트워크 지연 제거, CPU/GPU 직접 활용

### 3. 안정성 유지 원리
- **동일 인터페이스:** DAG과 API 엔드포인트 변경 없음 (블랙박스 교체)
- **에러 처리:** 예외 발생 시 "error_parsing" 반환으로 파이프라인 안정성 유지
- **메모리 관리:** TF-IDF 벡터라이저 재사용으로 메모리 효율성

## 📊 예상 성능 비교

| 항목 | 기존 (Gemini API) | 수정 후 (로컬 모델) |
|------|-------------------|---------------------|
| 비용 | 5만개 × API 비용 | 0원 (로컬 실행) |
| 처리 속도 | API 지연 + Rate Limit | 로컬 추론 속도 |
| 확장성 | API 한계 | 하드웨어 리소스 한계 |
| 안정성 | 네트워크 의존 | 로컬 안정성 |

## 🔧 추가 최적화 가능 사항

1. **더 나은 한국어 모델:** `monologg/koelectra-base-v3-discriminator` 등 한국어 특화 모델 사용
2. **키워드 추출 향상:** KoNLPy + TF-IDF 또는 KeyBERT 사용
3. **GPU 활용:** CUDA 지원으로 GPU 가속
4. **캐싱 레이어:** Redis 등으로 중복 분석 방지
5. **배치 사이즈 동적 조정:** 시스템 리소스에 따른 자동 조정

## 🚀 배포 및 실행

수정된 코드는 기존 Docker Compose 설정과 호환되며, 별도 환경 변수 설정 없이 실행 가능합니다. 로컬 모델 다운로드는 최초 실행 시 자동으로 이루어집니다.

이러한 변경으로 5만 개 데이터 처리 시 비용을 0원으로 유지하면서도 빠르고 안정적인 배치 처리가 가능해졌습니다.