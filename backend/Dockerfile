# Multi-stage build for optimized image
FROM python:3.12-slim as builder

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 시스템 패키지 설치 (빌드 의존성)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# pyproject.toml과 uv.lock을 사용해 uv로 의존성 설치
COPY pyproject.toml uv.lock ./
RUN uv venv && uv sync --frozen

# 프로덕션 스테이지
FROM python:3.12-slim

WORKDIR /app

# 비root 사용자 생성
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 빌더 스테이지에서 설치된 가상환경 복사
COPY --from=builder /app/.venv /app/.venv

# 애플리케이션 코드 복사 (AWS 클라이언트 모듈 포함)
COPY main.py .
COPY dynamodb_client.py .
COPY bedrock_client.py .

# 사용자 권한 설정
RUN chown -R appuser:appuser /app
USER appuser

# PATH 설정 (.venv의 Python 사용)
ENV PATH="/app/.venv/bin:$PATH"

# Cloud Run에서 사용할 포트 설정
ENV PORT=8080
EXPOSE 8080

# uvicorn으로 FastAPI 서버 실행 (더 안정적인 설정)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--log-level", "info", "--access-log"]

