# ✅ Python 3.12 기반 이미지 사용
FROM python:3.12-slim

# 작업 디렉토리 생성
WORKDIR /app

# requirements 복사 및 설치
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스 복사
COPY / .

# 포트 열기 (FastAPI 기본 포트)
EXPOSE 8000

# 실행 명령
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
