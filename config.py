import os
from dotenv import load_dotenv

# .env 파일 불러오기
load_dotenv()

# 환경변수에서 MySQL 설정 불러오기
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "db": os.getenv("MYSQL_DB"),
}
