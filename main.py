# serial_app.py

import os
import aiomysql
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from model import Order
from config import MYSQL_CONFIG


# ======================
# 기본 설정
# ======================
SECRET_KEY = os.environ.get("SECRET_KEY", "fallback_secret_for_dev")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI()
db_pool = None


# ======================
# CORS 설정
# ======================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 시 모든 출처 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================
# MySQL 연결 풀 관리
# ======================
@app.on_event("startup")
async def startup_event():
    global db_pool
    db_pool = await aiomysql.create_pool(**MYSQL_CONFIG)
    print("[Startup] MySQL pool created.")


@app.on_event("shutdown")
async def shutdown_event():
    global db_pool
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        print("[Shutdown] MySQL pool closed.")


# ======================
# 유저 관련 모델
# ======================
class UserRegister(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


# ======================
# 유틸 함수 (비밀번호 & JWT)
# ======================

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def truncate_password(password: str, max_bytes: int = 72) -> str:
    """
    bcrypt는 비밀번호를 72바이트까지만 처리하므로
    UTF-8 인코딩 기준으로 안전하게 자른다.
    """
    encoded = password.encode("utf-8")
    if len(encoded) <= max_bytes:
        return password

    truncated = encoded[:max_bytes]
    # UTF-8 문자가 잘리지 않도록 안전하게 디코딩
    while True:
        try:
            decoded = truncated.decode("utf-8")
            break
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    print(f"[truncate_password] password truncated to {len(truncated)} bytes")
    return decoded


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    safe_pass = truncate_password(password)
    return pwd_context.hash(safe_pass)


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    safe_plain = truncate_password(plain)
    try:
        return pwd_context.verify(safe_plain, hashed)
    except Exception as e:
        print(f"[verify_password error] {e}")
        return False


# ======================
# 유저 DB 관련 함수
# ======================
async def get_user_by_username(username: str):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM users WHERE username = %s;", (username,))
            return await cur.fetchone()


async def get_user(user_id: int):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM users WHERE id = %s;", (user_id,))
            return await cur.fetchone()


# ======================
# 인증 유저 가져오기
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
        if username is None:
            raise credentials_exception
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

            password_hash = hash_password(user.password)
            await cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s);",
                (user.username, password_hash),
            )
            await conn.commit()

            return {"status": "success", "message": "User registered successfully"}


# ======================
# 로그인
# ======================
@app.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid username or password")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ======================
# 주문 생성 (JWT 인증 필요)
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
                    order_id, sugar, coffee, water, iced_tea, green_tea, name, room, status, user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
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
                    getattr(order, "status", "배달준비중"),
                    current_user["id"],
                ),
            )
            await conn.commit()

            print(f"[Order Received] ID: {order_id}, User: {current_user['username']}")
            return {
                "status": "success",
                "order_id": order_id,
                "user_id": current_user["id"],
                "order": order,
            }


# ======================
# 본인 주문 조회
# ======================
@app.get("/orders/me")
async def get_my_orders(current_user: dict = Depends(get_current_user)):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC;",
                (current_user["id"],),
            )
            return {"orders": await cur.fetchall()}


# ======================
# 전체 주문 조회 (관리자용)
# ======================
@app.get("/orders")
async def get_all_orders():
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM orders ORDER BY created_at DESC;")
            return {"orders": await cur.fetchall()}


# ======================
# 주문 상태 조회
# ======================
@app.get("/order/{order_id}/status")
async def get_order_status(order_id: str):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM orders WHERE order_id = %s;", (order_id,))
            order = await cur.fetchone()

            if not order:
                return {"status": "error", "message": "주문 정보를 찾을 수 없습니다."}

            return {
                "status": "success",
                "order_id": order["order_id"],
                "sugar": order["sugar"],
                "coffee": order["coffee"],
                "water": order["water"],
                "iced_tea": order["iced_tea"],
                "green_tea": order["green_tea"],
                "name": order["name"],
                "room": order["room"],
                "status_s": order["status"],
                "created_at": order["created_at"],
            }


# ======================
# 주문 상태 변경
# ======================
@app.patch("/order/{order_id}/status")
async def update_order_status(order_id: str, new_status: str):
    if new_status not in ["배달준비중", "배달중", "배달완료"]:
        return {"status": "error", "message": "잘못된 상태 값입니다."}

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE orders SET status=%s WHERE order_id=%s;",
                (new_status, order_id),
            )
            await conn.commit()
            return {
                "status": "success",
                "order_id": order_id,
                "new_status": new_status,
            }
