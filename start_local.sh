#!/bin/bash

echo "🔧 Setting up Python virtual environment..."

# 1. .venv 폴더가 없으면 생성
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# 2. 가상환경 활성화
source .venv/bin/activate

# 3. requirements.txt 설치
echo "📦 Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Run FastAPI App"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload