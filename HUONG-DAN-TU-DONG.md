# Chạy tự động mỗi đêm từ Google Sheet

Mỗi ngày lúc ~1:00 sáng, Claude (tác vụ đã lên lịch `luo-daily-video-variants`) mở sheet, kiểm tra tab của ngày (vd `17-11`). Nếu đã điền đủ 3 cột (tên video | link | yêu cầu) thì tải video mẫu, phân tích cấu trúc, tạo biến thể bằng LUO Chat, rồi tải kết quả lên Drive.

## Cấu trúc sheet đang dùng (tab "Plan test_AI Photo")
Ngày order (ngày làm) | Mã order | Tên video | **Sample** (tên file video mẫu) | Yêu cầu biến thể | Nhân vật | Ảnh before | Hook | Ngôn ngữ | **Số lượng dự kiến** (= số video cần tạo). Tên file kết quả: `<Mã order>[_<Tên video>]_bienthe_<số>.mp4`.
- Chỉ làm hàng có Ngày order = hôm nay VÀ đã có Mã order + Sample; hàng chưa có Sample để lần sau.
- Cột Ngôn ngữ: nếu video có lời thoại thì nhận dạng (transcribe.py), viết lại lời ngắn bằng ngôn ngữ đó và lồng tiếng mới (mất nhạc nền gốc).
- Ảnh before: luôn tự tạo bằng Muse (nhân vật hư cấu theo cột Nhân vật); KHÔNG dùng ảnh người thật từ Pinterest.

## Cần cài một lần
1. Sheet chia sẻ "Bất kỳ ai có đường liên kết đều xem được" (đã xong). `daily_config.json`: `sheet_url`, `tab_name`.
2. **Chỉ chỗ lấy video mẫu**: `sample_dir` (thư mục trên máy chứa các file Z00xxx.mp4) — hoặc link thư mục Drive (chưa hỗ trợ tải tự động).
3. **Tải kết quả lên Drive**: làm theo hướng dẫn đầu file `drive_upload.gs`, rồi điền `upload_url`, `upload_token`, `upload_folder_id`. Chưa điền thì kết quả vẫn ở `D:\ketqua\<ngày>\<mã>\out\`.
4. Máy phải **bật** và **ứng dụng Claude đang mở** lúc 1:00.

## Lệnh thủ công
- `python daily.py check [--date 2026-11-17]` xem tab/hàng/đã điền chưa
- `python daily.py download` tìm video mẫu của các hàng sẵn sàng
- `python transcribe.py video.mp4` nhận dạng lời thoại; `--voices vi` liệt kê giọng
- `python analyze.py video.mp4` ảnh contact sheet + mốc đổi cảnh để xem cấu trúc
- `python specrun.py dry|run spec.json` dựng biến thể từ spec (ví dụ ở `examples\`)
- `python upload.py file.mp4 --path 17-11/Z0200` tải lên Drive
- Log: `userdata\daily_log.txt`; trạng thái đã xử lý: `userdata\daily_state.json`

## Loại video "ảnh before -> ảnh after"
- Phần đầu bám sát video gốc (ảnh tĩnh, mốc cảnh, chuyển cảnh). Đoạn app của người khác (CapCut/end card) bị bỏ, thay bằng **khung upload của bạn**: mẫu upload -> ảnh BEFORE vào khung -> LOADING -> ảnh AFTER toàn màn hình (`tail.mode = "flow"`). Video không có đoạn app khác thì nối thêm khung upload ở cuối.
- **Ảnh after mẫu** (1 ảnh) đặt ở `assets\after_samples\<Mã order>.png` hoặc `default.png` (hoặc `after_sample.png` cạnh video mẫu). Ảnh after của từng biến thể được tạo từ ảnh before theo kiểu ảnh mẫu đó.
- Âm thanh: có nhạc -> lặp nhạc gốc hết video. Có lời nói -> viết lời mới bằng ngôn ngữ trong cột Ngôn ngữ, lồng tiếng, **không phụ đề**.
- Chuyển cảnh nhanh, không để khoảng chết quá 1 giây; video có thể dài hơn gốc.

## Video mẫu và ảnh after lấy từ chính Sheet
- Ô **Sample** (vd `Z00126.mp4`) là chữ có **link Drive ẩn** phía sau; `daily.py` đọc link đó (qua file XLSX xuất của sheet) rồi tải về `D:\ketqua\<dd-mm>\<mã_tên>\source.mp4`. **Điều kiện: file trên Drive phải để "Bất kỳ ai có đường liên kết đều xem được"**; nếu không Drive đòi đăng nhập và tải sẽ báo lỗi rõ ràng. Sample là link TikTok/Facebook thì chưa tự tải được.
- Cột **O "Ảnh after"**: dán link ảnh (link file Drive công khai hoặc link ảnh trực tiếp), hoặc `=IMAGE("link")`, hoặc ảnh thả nổi trên ô. `daily.py` tải thành `after_sample.<đuôi>` trong thư mục video. Ảnh chèn thẳng "trong ô" chưa đọc được.
- Cột **Link hoàn thành** (T) của sheet là link thư mục Drive kết quả của từng hàng (hiện chưa dùng để tải lên).
