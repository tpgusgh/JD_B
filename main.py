# serial_app.py

import os
import aiomysql
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from model import Order
from config import MYSQL_CONFIG
import json
import ssl
import threading
import paho.mqtt.client as mqtt
import requests


# ======================
# 기본 설정
# ======================
SECRET_KEY = os.environ.get("SECRET_KEY", "fallback_secret_for_dev")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60000000

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

MQTT_BROKER = "mqtt-web.mieung.kr"
MQTT_PORT = 443
MQTT_TOPIC_ROOMS = "echo/save"

app = FastAPI()

db_pool = None
mqtt_client = None
rooms_storage: list[str] = []
pi_statuses = {}
order_state = {"status": "OPEN", "queue_count": 0}


# ======================
# CORS 설정
# ======================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================
# MySQL 연결 풀
# ======================
@app.on_event("startup")
async def startup_event():
    global db_pool
    db_pool = await aiomysql.create_pool(**MYSQL_CONFIG)
    print("[Startup] MySQL pool created.")

    # MQTT 백그라운드 실행
    mqtt_thread = threading.Thread(target=start_mqtt_client, daemon=True)
    mqtt_thread.start()
    print("[Startup] MQTT client thread started.")


@app.on_event("shutdown")
async def shutdown_event():
    global db_pool, mqtt_client
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        print("[Shutdown] MySQL pool closed.")

    if mqtt_client:
        mqtt_client.disconnect()
        print("[Shutdown] MQTT client disconnected.")


# ======================
# 모델
# ======================
class UserRegister(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


# ======================
# JWT / 비밀번호 관련
# ======================
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def truncate_password(password: str, max_bytes: int = 72) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) <= max_bytes:
        return password

    truncated = encoded[:max_bytes]
    while True:
        try:
            decoded = truncated.decode("utf-8")
            break
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return decoded


def hash_password(password: str) -> str:
    safe_pass = truncate_password(password)
    return pwd_context.hash(safe_pass)


def verify_password(plain: str, hashed: str) -> bool:
    safe_plain = truncate_password(plain)
    return pwd_context.verify(safe_plain, hashed)


# ======================
# DB 유저 조회
# ======================
async def get_user_by_username(username: str):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM users WHERE username=%s;", (username,))
            return await cur.fetchone()


async def get_user(user_id: int):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM users WHERE id=%s;", (user_id,))
            return await cur.fetchone()


# ======================
# 인증 유저
# ======================
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        raise credentials_exception

    user = await get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return user


# ======================
# 회원가입
# ======================
@app.post("/register")
async def register(user: UserRegister):
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:

            existing = await get_user_by_username(user.username)
            if existing:
                raise HTTPException(status_code=400, detail="Username already exists")

            hashed_pw = hash_password(user.password)

            await cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s);",
                (user.username, hashed_pw),
            )
            await conn.commit()

    return {"status": "success"}


# ======================
# 로그인
# ======================
@app.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid username or password")

    token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token({"sub": user["username"]}, token_expires)

    return {"access_token": token, "token_type": "bearer"}


# ======================
# 주문 생성
# ======================
@app.post("/order")
async def create_order(order: Order, current_user: dict = Depends(get_current_user)):
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:

            await cur.execute("SELECT COUNT(*) FROM orders;")
            count = (await cur.fetchone())[0]
            order_id = f"{count + 1:04}"

            await cur.execute(
                """
                INSERT INTO orders (
                    order_id, sugar, coffee, water, iced_tea, green_tea,
                    name, room, status, user_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    order_id,
                    order.sugar,
                    order.coffee,
                    order.water,
                    order.iced_tea,
                    order.green_tea,
                    order.name,
                    order.room,
                    "배달준비중",
                    current_user["id"],
                ),
            )
            await conn.commit()

    return {"status": "success", "order_id": order_id}


# ======================
# 주문 상태 조회
# ======================
@app.get("/order/{order_id}/status")
async def get_order_status(order_id: str):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM orders WHERE order_id=%s;", (order_id,))
            order = await cur.fetchone()

            if not order:
                return {"status": "error", "message": "Order not found"}

            return {"status": "success", "data": order}


# ======================
# 내부 API (MQTT용)
# ======================
@app.post("/internal/order-finish")
async def internal_order_finish(data: dict):
    order_id = data.get("order_id")
    if not order_id:
        return {"status": "fail", "error": "order_id missing"}

    print(f"[API] 내부 주문 완료 처리 시작: {order_id}")

    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE orders SET status=%s WHERE order_id=%s;",
                    ("배달완료", order_id),
                )
                await conn.commit()

        print(f"[API] 주문 완료 처리 성공: {order_id}")
        return {"status": "success"}

    except Exception as e:
        print("[API ERROR] 주문 완료 처리 실패:", e)
        return {"status": "fail", "error": str(e)}


# ======================
# 주문 가능 상태
# ======================
@app.get("/order/state")
async def api_get_order_state():
    return {"status": "success", "data": order_state}


# ======================
# MQTT 처리
# ======================
def on_mqtt_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected. rc={rc}")
    if rc == 0:
        client.subscribe(MQTT_TOPIC_ROOMS)
        client.subscribe("order/state")
        client.subscribe("order/finish")
        print("[MQTT] Subscribed to topics.")
    else:
        print("[MQTT] MQTT 연결 실패")


def on_mqtt_message(client, userdata, msg):
    global rooms_storage, order_state

    try:
        payload = msg.payload.decode("utf-8")
        print(f"[MQTT] Message received on {msg.topic}: {payload}")

        data = json.loads(payload)

        # rooms 처리
        if msg.topic == MQTT_TOPIC_ROOMS:
            if isinstance(data.get("rooms"), list):
                rooms_storage = data["rooms"]
                print(f"[MQTT] rooms_storage updated: {rooms_storage}")

        # order/state 처리
        elif msg.topic == "order/state":
            order_state = data
            print(f"[MQTT] order_state updated: {order_state}")

        # 주문 완료 처리
        elif msg.topic == "order/finish":
            order_id = data.get("order_id")
            if order_id:
                print(f"[MQTT] 주문 완료 요청 수신: {order_id}")

                try:
                    requests.post(
                        "http://localhost:5000/internal/order-finish",
                        json={"order_id": order_id},
                        timeout=2
                    )
                except Exception as e:
                    print("[MQTT] 내부 API 호출 실패:", e)

    except Exception as e:
        print("[MQTT ERROR] 메시지 처리 오류:", e)


def start_mqtt_client():
    global mqtt_client
    print("[MQTT] Starting MQTT client...")

    client = mqtt.Client(transport="websockets")

    client.tls_set(cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLSv1_2)
    client.tls_insecure_set(True)

    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message

    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    mqtt_client = client
    client.loop_forever()
