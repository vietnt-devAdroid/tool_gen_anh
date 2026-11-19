# Cài đặt LUO Chat trên máy mới

## Yêu cầu
- Windows 10/11, **Python 3.11 trở lên (64-bit)** (nhớ tick "Add python.exe to PATH" khi cài).
- Google Chrome (LUO-API dùng Chrome để điều khiển Muse), kết nối internet.
- Tài khoản Muse (muse.ai) để tạo ảnh/video.

## Các bước
1. Giải nén thư mục này ở nơi có ổ trống (ví dụ `D:\LUO-Chat`). **Không** giải nén vào thư mục có dấu hoặc quá dài.
2. Chạy **`Cai dat.bat`** (tạo môi trường Python và cài thư viện, vài phút).
3. (Tuỳ chọn, nặng 1-2 GB) Chạy **`Cai them nhac nen va giong noi.bat`** nếu làm video có **lời nói** và muốn lồng tiếng mới mà giữ nhạc nền.
4. Chạy **`LUO Chat.bat`** để mở ứng dụng.
5. Vào mục **Tài khoản** → "Đăng nhập tài khoản mới" để thêm tài khoản Muse (Chrome sẽ mở ra để bạn đăng nhập).
6. Dùng chat để tạo ảnh/video; muốn làm hàng loạt từ video mẫu, mở Claude Code trong thư mục này: file `CLAUDE.md` và `QUY-TAC-XU-LY-VIDEO.md` đã dạy Claude cách xử lý.

## Cấu hình tuỳ chọn (làm tự động theo Google Sheet)
Sao chép `daily_config.example.json` thành `daily_config.json` rồi điền `sheet_url`... Xem `HUONG-DAN-TU-DONG.md`.

## Lưu ý
- Thư mục `userdata\` (tạo khi chạy) chứa tài khoản/cookie Muse, khoá API, chat và ảnh: **không gửi cho người khác**.
- `bin\ffmpeg.exe` là bản ffmpeg kèm theo (giấy phép của ffmpeg: https://ffmpeg.org/legal.html).
- Mỗi người dùng tài khoản Muse của riêng mình; tuân thủ điều khoản của Muse.
