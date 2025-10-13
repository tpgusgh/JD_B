# serial_app.py
import asyncio
from typing import Optional
import serial_asyncio
from fastapi import FastAPI
import json

from model import Order
from config import SERIAL_PORT, BAUDRATE

app = FastAPI()
now_serial_data = None 
serial_task = None 
order_storage = {} # 주문 로컬 스토리지
order_counter = 0  # 주문 번호 카운터

async def read_serial():
    global now_serial_data
    reader, _ = await serial_asyncio.open_serial_connection(
        url=SERIAL_PORT, baudrate=BAUDRATE
    )
    while True:
        try:
            line = await reader.readline()
            decoded = json.loads(line)
            print(f"[Serial] {decoded}")
            now_serial_data = decoded
        except Exception as e:
            print(f"[Error] {e}")
            await asyncio.sleep(1)

@app.on_event("startup")
async def start_serial_reader():
    global serial_task
    serial_task = asyncio.create_task(read_serial())

@app.on_event("shutdown")
async def stop_serial_reader():
    global serial_task
    if serial_task:
        serial_task.cancel()
        try:
            await serial_task
        except asyncio.CancelledError:
            print("[Shutdown] Serial reader cancelled cleanly.")

@app.get("/stock")
async def get_serial_data(type: Optional[str] = None):
    try:
        if type:
            return {type: now_serial_data[type]}
        return now_serial_data
    except Exception as e:
        return {"error": str(e)}

@app.post("/order")
async def create_order(order: Order):
    global order_counter
    if order:
        order_counter += 1
        order_id = f"{order_counter:04}"  # 4자리 숫자, 예: 0001, 0002
        order_storage[order_id] = order
        print(f"[Order Received] ID: {order_id}, Data: {order}")
        return {
            "status": "success",
            "order_id": order_id,
            "order": order
        }
    return {"status": "error"}

@app.get("/order/{order_id}/status")
async def get_order_status(order_id: str):
    order = order_storage.get(order_id)
    if order:
        return {
            "status": "success",
            "order_id": order_id,
            "name": order.name,
            "room": order.room
        }
    return {
        "status": "error",
        "message": "주문 정보를 찾을 수 없습니다."
    }