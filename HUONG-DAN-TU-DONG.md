# Chạy tự động mỗi đêm từ Google Sheet

Mỗi ngày lúc ~1:00 sáng, Claude (tác vụ đã lên lịch `luo-daily-video-variants`) mở sheet, kiểm tra tab của ngày (vd `17-11`). Nếu đã điền đủ 3 cột (tên video | link | yêu cầu) thì tải video mẫu, phân tích cấu trúc, tạo biến thể bằng LUO Chat, rồi tải kết quả lên Drive.

## Cần cài một lần
1. **Sheet** chia sẻ "Bất kỳ ai có đường liên kết đều xem được"; **mỗi file video** trên Drive cũng vậy (link dạng `drive.google.com/file/d/<ID>/view`, không phải link thư mục).
2. Điền `daily_config.json`: `sheet_url` (link sheet).
3. **Tải kết quả lên Drive**: làm theo hướng dẫn đầu file `drive_upload.gs` (tạo Apps Script 3 phút), rồi điền `upload_url`, `upload_token`, `upload_folder_id` vào `daily_config.json`. Chưa điền thì kết quả vẫn nằm ở `D:\ketqua\<ngày>\<tên video>\out\`.
4. Máy phải **bật** và **ứng dụng Claude đang mở** lúc 1:00 (nếu tắt, tác vụ chạy khi mở lại ứng dụng).

## Lệnh thủ công
- `python daily.py check [--date 2026-11-17]` xem tab/hàng/đã điền chưa
- `python daily.py download` tải video của các hàng đủ + chưa xử lý
- `python analyze.py video.mp4` ảnh contact sheet + mốc đổi cảnh để xem cấu trúc
- `python specrun.py dry|run spec.json` dựng biến thể từ spec (ví dụ ở `examples\`)
- `python upload.py file.mp4 --path 17-11/Z0200` tải lên Drive
- Log: `userdata\daily_log.txt`; trạng thái đã xử lý: `userdata\daily_state.json`
