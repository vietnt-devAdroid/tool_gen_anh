# Bản giao việc cho luồng phụ (image to image) - đọc file này rồi làm, KHÔNG cần ngữ cảnh khác

Dùng khi giao việc xử lý 1 video mẫu cho luồng MỚI (không dùng fork: fork mang theo cả ngữ cảnh dài rất tốn token).
Prompt giao việc chỉ cần: mã video + yêu cầu riêng (nhân vật, ngôn ngữ, chữ, độ dài) + "đọc AGENT-BRIEF.md".

## Môi trường
- Thư mục làm việc: `D:\luo-studio-main\LUO-Chat`. Python: `.venv\Scripts\python.exe` (đặt `PYTHONIOENCODING=utf-8`). Video mẫu: `D:\ketqua\Z####\source.mp4` (chép từ `D:\video_20_11\ITI_Z####.mp4`).
- LUO Chat phải đang chạy (`run.py`, giao diện 18620). Không dừng/khởi động lại nó, không dừng tiến trình Muse.
- Quy tắc nội dung (bắt buộc): `QUY-TAC-XU-LY-VIDEO.md`. Tóm tắt: nhân vật HƯ CẤU người lớn, mặc đủ/kín đáo, KHÔNG trẻ em (chủ thể), KHÔNG người nổi tiếng, KHÔNG logo (trừ logo GTA VI đã được người dùng chấp nhận cho video GTA: `D:\ketqua\Z0174\edge_gta.png`). Gốc có trẻ em -> làm bản toàn người lớn và nói rõ.
- Không sửa `pipeline.py`, `specrun.py`, `server.py` (dùng chung); không commit.

## Quy trình một video
1. `analyze.py <video> --out <thư mục>\an --fps 2.5` + `transcribe.py <video>` -> xem contact sheet (`an\all_01.jpg`), ghi mốc cảnh/góc máy/chữ/chuyển cảnh (đo ở 10 khung/giây nếu cần: `analyze.py --window a b --fps 10`).
2. Viết `gen.py` sinh `spec.json` (10 biến thể) theo mẫu gần nhất:
   - nhiều cảnh ảnh + lời: `D:\ketqua\Z0188\gen.py`, `Z0172\gen_c.py` (phụ đề từng chữ: `patch_caps.py`), `Z0171\gen.py` (collage)
   - before -> after quét + logo: `Z0174\gen.py`, `Z0174\gen_lib.py` (nhân vật kho), `Z0176\gen_orig.py` (giữ âm thanh gốc `audio: orig_head`)
   - chữ trên ảnh: `Z0186\gen.py` (chữ viết tay trên tường), `Z0190\gen.py` (chữ xăm do Muse viết), `Z0175\gen.py` (chữ + trái tim đóng lên ảnh)
   - giữ nguyên nhạc bài hát gốc: `Z0181\gen.py` (`audio: orig_keep`)
   Định dạng spec: docstring đầu `specrun.py`.
3. `specrun.py dry spec.json --only 1 --out <dir>\dry` (kiểm tra nhịp/độ dài, không gọi Muse), rồi chạy THẬT 1 biến thể: `specrun.py run spec.json --only 1 --out <dir>\out`. Xem khung hình kết quả (bảng ảnh `ffmpeg -vf fps=..,scale=..,tile=..`).
4. Báo lại: đường dẫn mp4, cấu trúc, điểm yếu. Ngắn gọn.

## Bài học đã trả giá (làm đúng ngay từ đầu)
- Ảnh mẫu `after_sample.png`: LÀM MỜ mặt/chữ/logo, nếu không Muse sao chép mặt (kể cả TRẺ EM) từ mẫu sang ảnh after. Prompt dặn "show ONLY the N adults from the first image, nobody else, no children". Sau khi chạy xem ảnh after CUỐI của từng video.
- Ảnh after ở đuôi (`fafter`) phải là ảnh SAU BIẾN ĐỔI đúng concept video (tạo từ `fbefore`), không phải ảnh chung chung.
- Muse chặn prompt chứa "nude", "child"... (kể cả tên màu như "nude-pink"): tránh các từ này, dùng "blush-pink"...
- Cache Muse theo tiêu đề + prompt: muốn tạo ảnh mới thì đổi `id` trong spec. `specrun` BỎ QUA biến thể nếu file kết quả đã tồn tại: xóa mp4 cũ trong thư mục `--out` khi muốn dựng lại.
- Kho nhân vật chỉ có 10 ảnh/mã: biến thể > 10 sẽ trùng người; đừng dùng nhóm trẻ em (V03, V06, V09, V12, V15, V18).
- Lời mới cùng ngôn ngữ gốc, tốc độ `+18%` (`pipeline.VOICE_RATE`), không phụ đề trừ khi người dùng muốn; số ảnh biến đổi theo lời: `pipeline.plan_beats`. Tail flow cố định 6s; total mặc định 24s (video gốc ngắn thì bám nhịp gốc + 6s đuôi).
- Chữ cần chính xác: item stage `"text": {...}` (hoặc danh sách) đóng chữ SAU khi ảnh tạo (`specrun.overlay_text`: chữ, hình `heart`/`line`/`arrow`/`image`, `blend: multiply` để in lên bề mặt). Muse tự viết chữ trong ảnh thì không phải ảnh nào cũng đúng.
- Quét chuyển có logo chạy theo mép: clip `{"trans": "wipedown", "edge": "<png>"}`.
- Chạy lô nhiều video cùng lúc: `specrun.py run a.json b.json --overlap 2 --out <base>` (mỗi spec một thư mục con theo tên thư mục chứa spec).

## Đầu ra
- Bản mẫu: `D:\ketqua\Z####\out`. Lô 10 biến thể: `D:\ketqua\Z####\final` hoặc `D:\ketqua\batchN\Z####`.
- Người dùng không đọc kết quả của luồng, nên báo cáo cuối phải có đường dẫn file đầy đủ + điểm yếu.
