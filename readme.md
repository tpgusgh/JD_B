CREATE DATABASE IF NOT EXISTS orders_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE orders_db;


📦 Database Schema — Hyunho App
🧑‍💻 users 테이블 (회원 정보)
필드명	타입	NULL	KEY	기본값	설명
id	int	NO	PRI	—	자동 증가 (기본키)
username	varchar(100)	NO	UNI	—	사용자 이름 (고유값)
password_hash	varchar(255)	NO		—	비밀번호 해시
created_at	timestamp	YES		CURRENT_TIMESTAMP	계정 생성 시각

✅ 비고

username은 중복 불가 (UNIQUE)

비밀번호는 bcrypt 해시로 저장

created_at은 자동으로 현재 시각이 입력됨

☕ orders 테이블 (주문 정보)
필드명	타입	NULL	KEY	기본값	설명
id	int	NO	PRI	—	자동 증가 (기본키)
order_id	varchar(10)	NO	UNI	—	주문번호 (예: 0001, 0002)
sugar	varchar(50)	YES		NULL	설탕 선택
coffee	varchar(50)	YES		NULL	커피 선택
water	varchar(50)	YES		NULL	물 선택
iced_tea	varchar(50)	YES		NULL	아이스티 선택
green_tea	varchar(50)	YES		NULL	녹차 선택
name	varchar(100)	YES		NULL	주문자 이름
room	varchar(100)	YES		NULL	배달 위치 (예: 301호)
created_at	timestamp	YES		CURRENT_TIMESTAMP	주문 생성 시각
status	enum('배달준비중','배달중','배달완료')	NO		'배달준비중'	주문 상태
user_id	int	YES	MUL	NULL	주문한 사용자 ID (외래키)

✅ 비고

user_id는 users.id를 참조 (외래키)

order_id는 주문 순서대로 자동 생성 (0001, 0002 형식)

status는 세 가지 상태 중 하나만 가능:

🟡 배달준비중

🟠 배달중

🟢 배달완료

🔗 관계 (Relationships)
관계	설명
users.id → orders.user_id	1:N (한 유저는 여러 주문을 가질 수 있음)



⚙️ 기타 정보

백엔드: FastAPI + aiomysql

인증 방식: JWT (Access Token)

비밀번호 암호화: bcrypt

DB 연결: MySQL connection pool (aiomysql)

주요 엔드포인트:

POST /register – 회원가입

POST /login – 로그인 (JWT 발급)

POST /order – 주문 생성

GET /orders/me – 내 주문 조회

PATCH /order/{order_id}/status – 주문 상태 변경