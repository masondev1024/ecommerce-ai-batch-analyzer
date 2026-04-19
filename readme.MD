# E-Commerce Review Batch Inference Pipeline

## Overview
본 프로젝트는 일일 수집된 이커머스 상품 리뷰 데이터를 기반으로 AI 감성 분석 및 핵심 키워드 추출을 수행하는 배치 파이프라인(Batch Pipeline)입니다. Airflow를 통한 데이터 파이프라인 오케스트레이션과 FastAPI를 활용한 마이크로서비스(MSA) 형태의 AI 추론 API 연동 구조를 로컬 환경에서 시뮬레이션합니다.

## Architecture
- **Orchestration:** Apache Airflow (DAG 기반 스케줄링 및 배치 제어)
- **Database:** MySQL 8.0 (데이터 웨어하우스 역할, Raw 리뷰 및 분석 결과 적재)
- **API Service:** FastAPI, Uvicorn (배치 추론 요청 수신 및 응답)
- **AI Inference:** Gemini CLI (FastAPI 내부에서 `subprocess` 모듈을 통해 실행)

## Directory Structure
```text
/airflow-local
├── docker-compose.yaml
├── init.sql                      # MySQL 초기 테이블 생성 및 더미 데이터 적재
├── dags/
│   └── review_sentiment_pipeline.py  # Airflow 파이프라인 DAG
└── api_server/
    ├── Dockerfile                # FastAPI 및 Gemini CLI 환경 구성
    ├── requirements.txt
    └── main.py                   # API 엔드포인트 및 서브프로세스 실행 로직