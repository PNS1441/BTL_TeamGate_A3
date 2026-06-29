# 🚪 Smart Campus - Access Gate (Team A3)

Dự án Xây dựng hệ thống Cổng kiểm soát ra vào (Access Gate) thông minh cho Smart Campus, tích hợp xác thực đa luồng qua IoT (MQTT) và kết nối chéo với Hệ thống Lõi (Core Business) thông qua mạng LAN ảo Radmin VPN.

## 👥 Thành viên nhóm A3
| Họ và tên | Nhiệm vụ |
|:---|:---|
| **Phạm Thị Yến Anh** | Quản lý nhóm, phân tích thiết kế, viết báo cáo |
| **Nguyễn Văn Phước** | Thiết kế cơ sở dữ liệu, chạy kiểm thử API |
| **Phạm Ngọc Sơn** | Lập trình client IoT (MQTT), kiểm thử tự động, lập trình Backend API |
| **Bùi Thiên Phú** | Triển khai Docker, cấu hình tích hợp Radmin VPN |

## 🚀 Tính năng nổi bật
- **RESTful API:** Quản lý thẻ quẹt, ghi nhận lịch sử ra vào an toàn với Fast API.
- **Fail-Closed Security:** Nếu mất kết nối tới máy chủ trung tâm, cổng tự động đóng để đảm bảo an ninh (`core_service_timeout`).
- **Anti-Spam IoT:** Tự động phát hiện và ngăn chặn hành vi quẹt 1 thẻ liên tục để phá hoại hệ thống (`spam_detected`).
- **Dockerized:** Đóng gói toàn bộ ứng dụng và Database SQLite, sẵn sàng deploy chỉ với 1 lệnh.
- **Automated Testing:** Tự động hóa kiểm thử bằng Newman/Postman đạt độ phủ 100% Test case.

## 🛠️ Hướng dẫn cài đặt và chạy hệ thống

### 1. Khởi động Server (Docker)
```bash
# Clone source code
git clone https://github.com/PNS1441/BTL_TeamGate_A3.git
cd BTL_TeamGate_A3

# Chạy Docker Compose
docker compose up -d --build

# Kiểm tra trạng thái
docker compose ps
curl http://localhost:8000/health
```

### 2. Chạy kịch bản giả lập thiết bị IoT (Quẹt thẻ)
```bash
# Cài đặt thư viện paho-mqtt nếu chưa có: pip install paho-mqtt
python test_spam.py
```
*(Cùng lúc mở thêm 1 terminal chạy `docker compose logs -f api` để xem log chặn Spam)*

### 3. Chạy báo cáo kiểm thử tự động (Newman)
```bash
npm install
npm run test:compose
```
*(Sau khi chạy xong, mở file `reports/newman-btl-teamgate.html` bằng trình duyệt để xem kết quả Pass 100%)*

## 📁 Cấu trúc thư mục chính
- `/src/gate_app/`: Chứa mã nguồn Python (FastAPI, SQLite, logic Anti-Spam).
- `/src/gate_app/mqtt_client.py`: Nơi xử lý giao thức IoT và thuật toán chặn Spam.
- `/postman/`: Chứa bộ Collection và Environment chạy test tự động.
- `/reports/`: Nơi xuất file báo cáo giao diện HTML xanh lá mượt mà.
- `docker-compose.yml`: File cấu hình khởi chạy toàn bộ kiến trúc.

---
🎓 **Học phần:** Dịch vụ kết nối, Công nghệ nền tảng (FIT4110)
🏫 Báo cáo Bài Tập Lớn - Học kỳ 2026
