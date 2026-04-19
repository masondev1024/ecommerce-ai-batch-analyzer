# 개요
- fastapi를 이용한 API 서비스 간단하게 구성
- 해당 서비스는 airflow의 서비스단에 추가(docker-compose.yaml)

# 구동
    ~\Projects\Airflow\api_server> uvicorn main:app --host 0.0.0.0 --port 8000

# 접속
    - 홈페이지
        - http://127.0.0.1:8000/
    - 문서 접속(swagger docs)
        - swagger를 fastapi 기본 제공(flask, django 기본 x)
        - http://127.0.0.1:8000/docs
            ```
                API 문서 제공, API 테스트 가능
            ```
    - API 문서 간결화
        - http://127.0.0.1:8000/redoc
    - API 테스트 전용
        - postman( 구글 extension -> 독립)
        - thunderclient ( vscode extension)