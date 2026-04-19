# ecommerce-ai-batch-analyzer


An end-to-end Microservices Architecture (MSA) data pipeline that performs asynchronous sentiment analysis and keyword extraction on E-commerce reviews using the Gemini AI API.

## 📌 Architecture Overview

This project is built with a strict separation of concerns, dividing the orchestration and the heavy AI computation into isolated, scalable services:

* **Orchestration (Apache Airflow):** Manages the scheduling, task dependencies, and database I/O.
* **AI Inference (FastAPI):** An independent, purely API-driven server dedicated to communicating with the Gemini LLM.
* **Data Warehouse (MySQL):** Stores the raw and analyzed E-commerce review data.
* **Metadata DB (PostgreSQL):** Stores Airflow's internal metadata.

### Why MSA?
By decoupling the Airflow workers from the AI API server, we achieve:
1.  **Independent Scalability:** The FastAPI server can be scaled out independently if the API load increases.
2.  **Fault Isolation:** If the AI API times out or hits rate limits, it does not crash the Airflow scheduler.
3.  **High Concurrency:** The FastAPI server utilizes `asyncio` and `google-generativeai` SDK to process multiple LLM requests concurrently without blocking OS threads, drastically improving batch processing speed compared to synchronous CLI calls.

## 🛠 Tech Stack

* **Language:** Python 3.11+
* **Orchestration:** Apache Airflow 2.9 (LocalExecutor)
* **API Server:** FastAPI, Uvicorn, Pydantic
* **AI / LLM:** Google Gemini 2.0 Flash (`google-generativeai` Async SDK)
* **Database:** MySQL 8.0, PostgreSQL 15
* **Infrastructure:** Docker & Docker Compose

## 🚀 Getting Started

### Prerequisites
* Docker and Docker Compose installed.
* A valid Google Gemini API Key.
