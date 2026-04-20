# E-commerce AI Batch Analyzer: 비용 최적화 및 성능 향상 분석 및 수정 보고서

## 📋 프로젝트 개요

이 프로젝트는 E-commerce 리뷰 데이터를 배치 처리하여 감정 분석 및 키워드 추출을 수행하는 마이크로서비스 아키텍처(MSA) 기반 데이터 파이프라인입니다. 데이터 엔지니어 포트폴리오로서 최근 실무에서 많이 사용되는 기술 스택을 최대한 활용하여 확장하였습니다.

## 🔍 기존 구조 분석

### 아키텍처 구성 요소 (기존)
- **Orchestration (Apache Airflow):** 스케줄링, 태스크 의존성 관리, 데이터베이스 I/O 처리
- **AI Inference (FastAPI):** Gemini AI API와 통신하는 독립적인 API 서버
- **Data Warehouse (MySQL):** 원본 및 분석된 리뷰 데이터 저장
- **Metadata DB (PostgreSQL):** Airflow 내부 메타데이터 저장

### 비용 문제점 (기존)
- Gemini API는 유료 서비스로, 각 요청마다 비용 발생
- 5만 개 데이터 × API 비용 = 예상 수십~수백 달러 비용 발생

## 🛠 수정 사항 및 기술 스택 변경

### 1. AI 모델 교체: Gemini API → Hugging Face 로컬 모델
**수정 파일:** `api_server/main.py`, `api_server/requirements.txt`

**변경 내용:**
- Google Generative AI SDK 제거
- Hugging Face Transformers 라이브러리 추가
- 감정 분석 모델: `nlptown/bert-base-multilingual-uncased-sentiment` (다국어 지원)
- 키워드 추출: TF-IDF 기반 간단한 키워드 추출 구현

### 2. 데이터 스트리밍 추가: Apache Kafka
**추가 파일:** `docker-compose.yml`, `dags/review_sentiment_pipeline.py`

**변경 내용:**
- Kafka + Zookeeper 서비스 추가
- DAG에서 MySQL 직접 조회 → Kafka Consumer로 변경
- 이벤트 기반 데이터 처리 구현

### 3. 캐싱 레이어 추가: Redis
**수정 파일:** `api_server/main.py`, `docker-compose.yml`

**변경 내용:**
- Redis 서비스 추가
- 분석 결과 캐싱 (TTL 1시간)
- 중복 분석 방지 및 성능 향상

### 4. 오브젝트 스토리지 추가: MinIO
**추가 파일:** `docker-compose.yml`

**변경 내용:**
- S3 호환 오브젝트 스토리지 추가
- 데이터 아티팩트 및 백업 저장소 제공

### 5. 모니터링 스택 추가: Prometheus + Grafana
**추가 파일:** `docker-compose.yml`, `config/prometheus.yml`, `api_server/main.py`

**변경 내용:**
- Prometheus 메트릭 수집
- FastAPI 미들웨어로 요청 메트릭 추가
- Grafana 대시보드 구성

### 6. 배치 처리 최적화
**수정 파일:** `dags/review_sentiment_pipeline.py`

**변경 내용:**
- 청크 사이즈: 50 → 500개로 증가 (더 큰 배치 처리)
- 요청 간 딜레이: 3초 → 1초로 감소 (로컬 처리로 Rate Limit 없음)

## ⚡ 성능 및 비용 최적화 원리

### 1. 비용 절감 원리
- **API 비용 제거:** 로컬 모델 실행으로 외부 API 호출 비용 0원
- **확장성:** GPU 활용 시 더 빠른 처리 가능
- **무제한 처리:** Rate Limit 없이 로컬 리소스 한계 내에서 무제한 처리

### 2. 처리 속도 향상 원리
- **병렬 처리 유지:** asyncio + 세마포어로 동시성 제어 유지
- **큰 배치 처리:** 청크 사이즈 증가로 네트워크 오버헤드 감소
- **로컬 추론:** 네트워크 지연 제거, CPU/GPU 직접 활용
- **캐싱:** Redis를 통한 중복 계산 방지

### 3. 안정성 유지 원리
- **동일 인터페이스:** DAG과 API 엔드포인트 변경 없음 (블랙박스 교체)
- **에러 처리:** 예외 발생 시 "error_parsing" 반환으로 파이프라인 안정성 유지
- **메모리 관리:** TF-IDF 벡터라이저 재사용으로 메모리 효율성

### 4. 데이터 엔지니어링 모범 사례 적용
- **이벤트 드리븐 아키텍처:** Kafka를 통한 느슨한 결합
- **캐싱 전략:** Redis를 활용한 성능 최적화
- **모니터링:** Prometheus 메트릭으로 관측 가능성 확보
- **스토리지 계층화:** MySQL + MinIO로 데이터 관리

## 📊 예상 성능 비교

| 항목 | 기존 (Gemini API) | 수정 후 (로컬 + 최신 기술) |
|------|-------------------|-----------------------------|
| 비용 | 5만개 × API 비용 | 0원 (로컬 실행) |
| 처리 속도 | API 지연 + Rate Limit | 로컬 추론 + 캐싱 |
| 확장성 | API 한계 | MSA + 컨테이너 확장 |
| 안정성 | 네트워크 의존 | 로컬 + 모니터링 |
| 기술 스택 | 기본 MSA | 최신 데이터 엔지니어링 |

## 🔧 활용된 최신 기술 스택

### 데이터 엔지니어링 핵심 기술
- **Apache Kafka:** 실시간 데이터 스트리밍 및 이벤트 기반 처리
- **Redis:** 고성능 인메모리 캐싱
- **MinIO:** 클라우드 네이티브 오브젝트 스토리지
- **Prometheus + Grafana:** 모니터링 및 관측 가능성
- **Docker Compose:** 컨테이너 오케스트레이션

### MLOps 요소
- **Hugging Face Transformers:** 로컬 ML 모델 서빙
- **FastAPI + Pydantic:** API 설계 및 데이터 검증
- **Asyncio:** 비동기 처리로 동시성 관리

## 🚀 배포 및 실행

수정된 코드는 Docker Compose로 완전 컨테이너화되어 배포됩니다. 각 서비스는 독립적으로 확장 가능하며, 모니터링 대시보드를 통해 실시간 상태를 확인할 수 있습니다.

이러한 변경으로 5만 개 데이터 처리 시 비용을 0원으로 유지하면서도 최신 데이터 엔지니어링 기술을 활용한 견고한 파이프라인을 구축하였습니다.