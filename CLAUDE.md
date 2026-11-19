# LUO Chat — hướng dẫn cho Claude

Dự án này tạo video quảng cáo bằng Muse + ffmpeg. Khi người dùng đưa video mẫu hoặc nhờ xử lý video, **đọc và làm theo** bộ quy tắc sau (nội dung, hai loại video, cấu trúc, âm thanh, kiểm tra):

@QUY-TAC-XU-LY-VIDEO.md

**Việc đầu tiên khi bắt đầu task xử lý video: HỎI loại video** nếu người dùng chưa nói rõ — "image to image" (ảnh before -> after, dựng bằng ảnh tĩnh + khung upload, nhiều biến thể) hay "image to video" (cả thư mục video, gen lại từng video y như gốc bằng Muse, đa luồng, mỗi video một cuộc trò chuyện; công cụ `v2v.py`). Lịch tự động không hỏi được: tạm thời mặc định image to image, trừ khi yêu cầu ghi rõ image to video.

Ghi chú nhanh:
- Python: `.venv\Scripts\python.exe` (đặt `PYTHONIOENCODING=utf-8`). Chưa có `.venv` thì chạy `Cai dat.bat`.
- Mở LUO Chat bằng `LUO Chat.bat` (cần có ít nhất một tài khoản Muse đã đăng nhập ở trang Tài khoản).
- Tuân thủ tuyệt đối "Quy tắc nội dung" (người hư cấu/không sao chép gương mặt người thật, ăn mặc đầy đủ, không người nổi tiếng).
