# LUO Chat

Giao diện chat Muse 3 cột (danh sách chat | khung chat | media) có hàng đợi chạy ngầm. Dùng LUO-API làm nền, **không thay thế** LUO Studio.

## Chạy
1. Lần đầu: nhấp đúp **Cai dat.bat** (tạo `.venv` và cài thư viện, cần Python 3.11+ 64-bit).
2. Nhấp đúp **LUO Chat.bat**. Thư mục này độc lập, tự bật LUO-API riêng (`luo-muse-api/`). Dữ liệu ở `userdata/` (api = tài khoản Muse, chat = hội thoại/media/tệp tải lên).
Đừng chạy cùng lúc với LUO Studio nếu dùng chung tài khoản Muse.

## Dùng
- Chọn **Tạo video / Tạo ảnh / Chat AI**, nhập mô tả, Enter để gửi. Kẹp giấy = ảnh tham chiếu, biểu tượng video = video/âm thanh tham chiếu, đũa phép = tạo hàng loạt (mỗi dòng một yêu cầu).
- Video xong hiện ngay trong khung chat và cột Media. Chọn nhiều video rồi **Ghép** (cần ffmpeg trong `bin/`) hoặc **Tải xuống** (zip).
- Cài đặt: số video chạy song song, số lần tự thử lại (đổi tài khoản mỗi lần), thời gian chờ, duyệt prompt của Claude.

## Để Claude điều khiển
Claude dùng `chatctl.py` (xem đầu file) hoặc `POST /api/batch`. Prompt hiện trong giao diện với nhãn **Claude**. Bật "Duyệt prompt của Claude" để chúng chờ bạn bấm Chạy.

## Kiến trúc
`run.py` (khởi động) · `server.py` (HTTP + hàng đợi + gọi `/v1/videos`, `/v1/images/tasks`, `/v1/chat/completions`) · `ui/` (HTML/JS/CSS thuần) · `run.py` (khởi động) · `chatctl.py` (CLI).
