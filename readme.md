CREATE DATABASE IF NOT EXISTS orders_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE orders_db;

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,        -- 내부용 자동 증가 ID
    order_id VARCHAR(10) NOT NULL UNIQUE,     -- 0001, 0002 식의 주문번호
    sugar VARCHAR(50),
    coffee VARCHAR(50),
    water VARCHAR(50),
    iced_tea VARCHAR(50),
    green_tea VARCHAR(50),
    name VARCHAR(100),                        -- 주문자 이름
    room VARCHAR(100),                        -- 방 번호
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- 생성 시각
);
