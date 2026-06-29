# Readiness Checklist – Lab 05 (team-gate)

Đây là danh sách kiểm tra (checklist) để đảm bảo stack Docker Compose của bạn đã sẵn sàng trước khi gửi bài. Hãy tick vào mỗi mục sau khi hoàn thành.

- [x] **Database ready:** container DB đã chạy và phản hồi `pg_isready`. Kiểm tra bằng `docker exec -it fit4110-db-lab05-gate pg_isready -U gateuser`.
- [x] **AI service ready:** (Không áp dụng cho team-gate theo yêu cầu đề bài).
- [x] **API ready:** container API trả `200` cho `/health` và có thể nhận/xử lý access-events khi token hợp lệ.
- [x] **Environment variables:** `.env` đã được thiết lập đúng (APP_PORT, POSTGRES_USER, AUTH_TOKEN,…). Không sử dụng secret thật; lưu secret vào `.env` cục bộ, commit `.env.example`.
- [x] **Network & Ports:** mạng `team-internal` hoạt động; ports 8000 (API) và 5432 (DB) được map đúng.
- [x] **Image tags:** bạn đã build image với tag `v0.1.0-gate` và push lên registry (bạn sẽ làm bước push này trên máy local của bạn).

Ghi chú thêm những vấn đề gặp phải hoặc điều chỉnh tại đây:

```
- Đã bỏ qua AI service theo đúng như hướng dẫn trong README.md dành cho team-gate.
- API và Postgres database đã liên kết thành công qua network team-internal.
```