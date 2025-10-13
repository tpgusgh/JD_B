# serial_app.py
import aiomysql
from fastapi import FastAPI
from model import Order
from config import MYSQL_CONFIG

app = FastAPI()
db_pool = None  # MySQL connection pool

# ======================
# 1. 앱 시작 / 종료 시 MySQL 초기화
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
# 2. API: 주문 생성 (DB 저장)
# ======================
@app.post("/order")
async def create_order(order: Order):
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            # 주문 번호 자동 증가
            await cur.execute("SELECT COUNT(*) FROM orders;")
            count = (await cur.fetchone())[0]
            order_id = f"{count + 1:04}"  # 예: 0001, 0002

            await cur.execute(
                """
                INSERT INTO orders (
                    order_id, sugar, coffee, water, iced_tea, green_tea, name, room
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
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
                ),
            )
            await conn.commit()

            print(f"[Order Received] ID: {order_id}, Data: {order}")
            return {
                "status": "success",
                "order_id": order_id,
                "order": order
            }

# ======================
# 3. API: 주문 상태 조회
# ======================
@app.get("/order/{order_id}/status")
async def get_order_status(order_id: str):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM orders WHERE order_id = %s;", (order_id,))
            order = await cur.fetchone()

            if order:
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
                    "created_at": order["created_at"]
                }
            else:
                return {
                    "status": "error",
                    "message": "주문 정보를 찾을 수 없습니다."
                }

# ======================
# 4. API: 전체 주문 목록 조회
# ======================
@app.get("/orders")
async def get_all_orders():
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM orders ORDER BY created_at DESC;")
            rows = await cur.fetchall()
            return {"orders": rows}
