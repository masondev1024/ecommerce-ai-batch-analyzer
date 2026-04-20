# ecommerce-ai-batch-analyzer

An end-to-end Microservices Architecture (MSA) data pipeline that performs asynchronous sentiment analysis and keyword extraction on E-commerce reviews using local Hugging Face models. Enhanced with modern data engineering technologies for portfolio demonstration.

## 📌 Architecture Overview

This project is built with a strict separation of concerns, dividing the orchestration, data ingestion, AI computation, storage, and monitoring into isolated, scalable services:

* **Orchestration (Apache Airflow):** Manages the scheduling, task dependencies, and data processing workflows.
* **Data Ingestion (Apache Kafka):** Handles real-time data streaming and decoupling of data producers/consumers.
* **AI Inference (FastAPI):** An independent, purely API-driven server for local ML model inference with caching.
* **Data Warehouse (MySQL):** Stores the raw and analyzed E-commerce review data.
* **Metadata DB (PostgreSQL):** Stores Airflow's internal metadata.
* **Caching (Redis):** Provides high-performance caching for analysis results.
* **Object Storage (MinIO):** S3-compatible storage for data artifacts and backups.
* **Monitoring (Prometheus + Grafana):** Observability stack for metrics collection and visualization.

### Why MSA with Modern Tech Stack?
By adopting industry-standard technologies, this project demonstrates:
1. **Scalability:** Independent scaling of each service based on load.
2. **Reliability:** Fault isolation and event-driven architecture with Kafka.
3. **Performance:** Redis caching and local ML inference eliminate external API costs.
4. **Observability:** Comprehensive monitoring with Prometheus metrics and Grafana dashboards.
5. **Data Engineering Best Practices:** ETL pipelines, data quality checks, and modern storage solutions.

## 🛠 Tech Stack

* **Language:** Python 3.11+
* **Orchestration:** Apache Airflow 2.9 (LocalExecutor)
* **Streaming:** Apache Kafka 7.4 + Zookeeper
* **API Server:** FastAPI, Uvicorn, Pydantic
* **AI / ML:** Hugging Face Transformers (Local Inference)
* **Databases:** MySQL 8.0, PostgreSQL 15
* **Caching:** Redis 7
* **Storage:** MinIO (S3-compatible)
* **Monitoring:** Prometheus, Grafana
* **Infrastructure:** Docker & Docker Compose

## 🚀 Getting Started

### Prerequisites
* Docker and Docker Compose installed.


### Data Flow
1. Reviews are produced to Kafka topic 'reviews'
2. Airflow DAG consumes from Kafka and processes in batches
3. FastAPI server performs sentiment analysis with local models
4. Results are cached in Redis and stored in MySQL
5. Metrics are collected by Prometheus and visualized in Grafana
