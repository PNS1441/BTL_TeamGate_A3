# RUN_COMPOSE.md – Hướng dẫn chạy Lab 05 cho Access Gate (team-gate)

Tài liệu này hướng dẫn người khác clone repo sạch và chạy lại stack Compose của Lab 05 dành cho nhóm `team-gate`.

---

## 1. Clone repo

```bash
git clone <repo-url>
cd lab-5-PNS1441
```

---

## 2. Cài dependencies cho Newman/Prism/Spectral (tuỳ chọn)

```bash
npm install
```

---

## 3. Build & chạy stack Docker Compose

```bash
# Copy .env.example sang .env và chỉnh sửa nếu cần
cp .env.example .env

# Chạy bằng lệnh make (đã bao gồm tự động tạo class-net nếu chưa có)
make compose-up
```

Lệnh trên sẽ tạo các container:

- `fit4110-db-lab05-gate` (PostgreSQL)
- `fit4110-api-lab05-gate` (API FastAPI Access Gate trên port 8000)

Theo dõi log:

```bash
make logs
```

Sau vài giây, kiểm tra health của mỗi service:

```bash
# API
curl http://localhost:8000/health

# DB readiness
docker exec -it fit4110-db-lab05-gate pg_isready -U gateuser
```

---

## 4. Chạy Newman test trên stack Compose (tuỳ chọn)

Bạn có thể chạy bài test Postman collection để kiểm thử các API của Gate:

```bash
npm run test:compose
```

Report được sinh ra tại:

```text
reports/newman-lab05-compose.html
```

---

## 5. Dừng stack

Khi không cần nữa, dừng và xoá các container bằng:

```bash
make compose-down
```

Nếu muốn xoá volume dữ liệu của DB, hãy chạy thủ công:

```bash
docker compose down -v
```

---

## 6. Lệnh nhanh bằng Makefile

- `make compose-up`: Khởi tạo và chạy các containers
- `make compose-down`: Dừng và xoá containers
- `make logs`: Xem log các containers
- `make test-compose`: Chạy bài kiểm thử Postman/Newman

---

## 7. Mẹo gỡ lỗi

- Sử dụng `docker compose ps` để xem trạng thái container.
- Nếu API trả lỗi kết nối DB (khi bạn thêm logic kết nối thực), hãy kiểm tra biến môi trường `POSTGRES_*` trong `.env` và đảm bảo DB đã sẵn sàng (`pg_isready`).