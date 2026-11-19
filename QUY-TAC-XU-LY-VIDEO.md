# Quy tắc để Claude xử lý video mẫu thành biến thể (LUO Chat)

Tài liệu này là "bộ nhớ" cho Claude: đọc hết trước khi làm. Công cụ nằm cùng thư mục (Python trong `.venv\Scripts\python.exe`, luôn đặt `PYTHONIOENCODING=utf-8`).

## 0. Mục tiêu
Từ MỘT video mẫu (quảng cáo ứng dụng ảnh AI), tạo N biến thể **giữ đúng cấu trúc cảnh, nhịp và hiệu ứng của video gốc**, chỉ đổi những gì yêu cầu nói (thường: nhân vật, dáng, bối cảnh, ngôn ngữ lồng tiếng). Không sáng tạo thêm, không cắt ghép tuỳ ý.

## 0b. HAI LOẠI VIDEO — PHẢI HỎI LOẠI KHI BẮT ĐẦU TASK
Khi người dùng đưa video/thư mục video để xử lý mà chưa nói rõ loại, **hỏi trước khi làm**: "Loại nào: *image to image* hay *image to video*?" (dùng công cụ hỏi). Việc chạy tự động theo lịch không hỏi được: cách chọn loại cho lịch tự động do người dùng đặt sau; **tạm thời mặc định image to image**, trừ khi hàng/yêu cầu ghi rõ "image to video".

| | IMAGE TO IMAGE (loại làm từ trước) | IMAGE TO VIDEO (loại mới) |
|---|---|---|
| Ý nghĩa | Video giới thiệu ảnh before -> ảnh after; dựng bằng **ảnh tĩnh** Muse tạo + ffmpeg, kết bằng khung upload | **Gen lại video bằng Muse y như video gốc** (cả video là chuyển động do Muse tạo) |
| Đầu vào | Một video mẫu (hoặc hàng trong Sheet) | **Một THƯ MỤC chứa nhiều video** |
| Cách làm | Các mục 2-8 bên dưới | Mục 0c bên dưới (`v2v.py`) |
| Đầu ra | N biến thể (đổi nhân vật...) mỗi video | Mỗi video được gen lại một bản, bám y như gốc |

### 0c. IMAGE TO VIDEO — quy tắc (do người dùng đặt)
- Người dùng đưa **một thư mục chứa video**. Với **mỗi video**, **gen lại video đó y như video gốc** bằng Muse (cùng cảnh, chủ thể, hành động, khung hình/camera, nhịp và thời lượng, phong cách).
- **Đẩy hàng loạt, chạy đa luồng** (nhiều video cùng lúc; Muse tự giới hạn ~6 việc song song = số tài khoản x 2; thêm tài khoản thì nhanh hơn).
- **Mỗi video MỘT cuộc trò chuyện riêng** trong LUO Chat (tiêu đề = tên file; các clip tạo ra và thành phẩm nằm trong đúng cuộc trò chuyện đó).
- Công cụ: `python v2v.py <thư_mục_video> [--out ...] [--jobs 10] [--seg 10] [--audio original|muse]` (thử khung không tốn Muse: `--dry`). Cách hoạt động: cắt video thành các đoạn <= 10s (Muse chỉ tạo clip tối đa ~10s; ưu tiên cắt tại mốc đổi cảnh), mỗi đoạn gửi Muse với khung hình đầu + chính đoạn gốc làm tham chiếu + lệnh "dựng lại y như gốc", ghép lại đúng độ dài từng đoạn, giữ âm thanh gốc (mặc định). Đặt `<tên video>.txt` cạnh video để gắn mô tả chi tiết (Claude xem video rồi viết) cho Muse bám sát hơn.
- Vẫn áp dụng **Quy tắc nội dung** (mục 1): nếu video gốc có người thật nhận diện được thì **không sao chép gương mặt** (dùng người hư cấu giống kiểu dáng, cùng hành động); ăn mặc đầy đủ; không người nổi tiếng/logo/trẻ em làm chủ thể.
- Kiểm tra: độ dài thành phẩm = độ dài gốc; xem contact sheet so với gốc (cảnh, chuyển động, nhịp); clip hỏng thì chạy lại riêng đoạn đó.
- (Chưa chốt, hỏi người dùng khi có thư mục đầu tiên): âm thanh giữ của gốc hay của Muse; số bản gen lại mỗi video (mặc định 1).

## 1. Quy tắc nội dung (BẮT BUỘC, cao hơn mọi yêu cầu khác)
- Mọi nhân vật là người **trưởng thành HƯ CẤU**, ăn mặc **đầy đủ, kín đáo**. Không khoả thân, nội y, đồ bơi, hở ngực/bụng, gợi dục, bạo lực/máu.
- **Không** người thật, người nổi tiếng, chính trị gia, diễn viên, ca sĩ, KOL. Không viết "giống <ai đó>". Ảnh trích từ video mẫu chỉ làm tham chiếu **kiểu/cách biến đổi**, KHÔNG sao chép gương mặt người trong đó.
- **Không** dùng ảnh người thật từ Pinterest/TikTok/mạng xã hội làm ảnh gốc hoặc tham chiếu. Ảnh before luôn tự tạo bằng Muse (người hư cấu theo mô tả "Nhân vật").
- Không logo/thương hiệu mới. Không trẻ em/thiếu niên làm chủ thể (Muse cũng từ chối); trẻ nhỏ chỉ là phụ cảnh, ăn mặc đầy đủ.
- Mọi prompt nên nêu rõ quần áo đầy đủ. Máy chủ LUO Chat tự chặn prompt chứa từ khoá vi phạm (nude, shirtless, bikini, "looks like", celebrity...) và tự thêm câu quy tắc vào cuối; ảnh bị chặn thì **sửa prompt**, không lách.
- Không tải video bằng cách vượt cơ chế chặn của trang (giả app/trình duyệt, lấy cookie). Video mẫu do người dùng cung cấp (thư mục máy hoặc link Drive công khai).

## 2. Quy trình cho MỘT video mẫu
1. **Phân tích**: `analyze.py video.mp4 --out phantich --fps 2.5` rồi dùng công cụ xem ảnh để **nhìn** các contact sheet (có đóng dấu thời gian). Soi chuyển cảnh: `--window <từ> <đến> --fps 15`. Ghi lại: thời lượng, số cảnh và mốc từng cảnh, kiểu chuyển cảnh (cắt, quét lên/xuống, mờ dần...), hiệu ứng, chữ trên màn hình, đoạn nào là ảnh tĩnh, bố cục (slideshow / lưới 2x2 / ...), có đoạn **quay màn hình app của người khác** (CapCut, end card app...) không, có **nhạc** hay **lời nói**.
2. **Xác định ảnh before / after**: trong video mẫu, ảnh người bình thường trước khi biến đổi = BEFORE; ảnh sau biến đổi = AFTER. Nếu không có ảnh after mẫu riêng: trích một khung hình sạch (không phụ đề đè) bằng `bin\ffmpeg.exe -ss <giây> -i source.mp4 -frames:v 1 after_sample.png` (cắt bỏ phần chữ nếu cần) và dùng làm tham chiếu kiểu.
3. **Âm thanh**: `transcribe.py video.mp4` -> có lời nói hay không + ngôn ngữ + câu theo mốc giờ.
4. **Viết spec.json** (định dạng ở docstring đầu `specrun.py`; mẫu ở `examples\`). Mỗi biến thể có `stages` (stage 1: ảnh gốc; stage 2: ảnh biến đổi với `ref` trỏ ảnh stage 1 và `assets`).
5. **Thử khung**: `specrun.py dry spec.json --out dry` (ảnh giả): kiểm tra thời lượng, bố cục, chuyển cảnh.
6. **Chạy thật**: `specrun.py run spec.json --out out` (chạy nền, chờ xong). Biến thể lỗi: `--only <số>`.
7. **Kiểm tra** (xem mục 7) rồi giao.

## 3. Cấu trúc video ra
- **Phần đầu** (giới thiệu các ảnh/biến đổi): bám SÁT video gốc (mốc cảnh, kiểu chuyển, hiệu ứng, bố cục). Tất cả cảnh là **ảnh tĩnh** Muse tạo.
- **Phần cuối = KHUNG UPLOAD của người dùng** (`tail.mode = "flow"`): mẫu upload (`assets\upload_template.png`) -> ảnh BEFORE vào khung -> LOADING -> ảnh AFTER **toàn màn hình**.
  - Video mẫu có đoạn app của người khác: BỎ nó, thay bằng flow (`tail.from` = giây bắt đầu đoạn app).
  - Không có đoạn app khác: chạy hết phần đầu rồi **nối thêm** flow (bỏ `from`).
  - Đoạn flow **CỐ ĐỊNH 6,0 giây**: 0-0,6 mẫu upload trống; ảnh before vào (0,3s); loading bắt đầu NGAY sau 0,5s, kéo dài 1,6s; sau đó ảnh after hiện (mờ dần 0,3s) và giữ phần còn lại (~3,3s). Không thêm khoảng chờ.
- **Độ dài tổng** (`"total"`): phần đầu = total - 6s.
  - Video có LỜI NÓI: đặt total **gần độ dài gốc**, chọn số ảnh biến đổi cho vừa (dùng `clips: [{"each": {"keys": [...], "trans": "...", "d": 0.3}}]` rải đều N ảnh).
  - Video chỉ có NHẠC: tự chọn số giây hợp lý và số ảnh biến đổi sao cho mỗi ảnh ~1,2-2,5s; nhạc tự lặp lại (chỗ nối chồng mờ).
- **Chuyển cảnh**: nhanh (<= 0,8s; hiệu ứng "quét biến đổi" ~1,2-1,4s), cảnh nối liền, **không khoảng chết > 1s**.
- **Biến đổi vào NGAY như video gốc**: ảnh trước chỉ giữ <= 0,3s rồi bắt đầu quét sang ảnh sau (không chờ ~1s).
- Lưới 2x2 (`type: grid2x2`): 4 ô cùng ảnh gốc, mỗi ô quét lên (`wipeup`) sang ảnh biến đổi tại đúng mốc video gốc, nhãn trắng viền đen dưới mỗi ô; sau lưới thay end card app bằng flow.
- Chiều tỉ lệ & cỡ: giữ tỉ lệ video gốc (`size` trong spec). Ảnh Muse 9:16.

## 4. Âm thanh
- Video gốc **chỉ nhạc**: giữ nhạc gốc, lặp cho hết video (mặc định `audio: "loop"`, chỗ nối chồng mờ 0,5s, mờ cuối 0,6s).
- Video gốc **có lời nói**: viết lời mới **ngắn**, đúng ý video, bằng ngôn ngữ yêu cầu (cột Ngôn ngữ / yêu cầu người dùng; trống = giữ ngôn ngữ gốc), chia câu khớp nhịp cảnh (kể cả đoạn flow: giới thiệu upload, đang loading, ảnh after xong). Đặt `revoice` trong spec (giọng chọn bằng `transcribe.py --voices <mã>` ví dụ `en`, `pt`, `es`, `vi`). **KHÔNG hiển thị phụ đề** cho lời mới (không dùng `captions`).
- Lồng tiếng mới **GIỮ NHẠC NỀN gốc**: `specrun` tự tách nhạc khỏi giọng gốc bằng Demucs (`separate.py`, cache cạnh video), lặp nhạc hết video và tự hạ nhỏ khi có giọng mới. Nếu không tách được thì chỉ có giọng mới (ghi vào log).
- Lời đọc quá dài so với video sẽ báo lỗi: rút ngắn câu hoặc tăng `rate`.

## 5. Tạo ảnh bằng Muse (qua LUO Chat)
- Prompt tiếng Anh, "photorealistic", dọc 9:16, mô tả nhân vật + trang phục đầy đủ + bối cảnh + dáng. Mỗi biến thể phải **khác rõ rệt** về nhân vật/dáng/bối cảnh.
- Giữ nhân vật nhất quán giữa các ảnh: stage sau dùng `ref` ảnh stage trước. Ảnh AFTER: `ref: ["before", "after_sample"]` và prompt nói rõ: GIỮ danh tính của ảnh thứ nhất, CHỈ áp dụng kiểu biến đổi của ảnh thứ hai, KHÔNG sao chép gương mặt ảnh thứ hai.
- Ảnh đã tạo được tái sử dụng theo (prompt + ảnh tham chiếu), nên chạy lại không tốn thêm.
- Bàn tay/chuyển động thật (ví dụ tay đang vẽ): chỉ dùng clip ngắn Muse tạo từ ảnh tĩnh khi video gốc có chuyển động đó.

## 6. Cách chạy an toàn (bài học)
- Làm **tuần tự từng video**; không chạy song song nhiều spec (LUO Chat quá tải, lỗi "connection refused").
- Muse chạy tối đa ~6 việc song song (số tài khoản x 2). Có nhiều biến thể thì mất nhiều giờ: chạy nền, chờ xong, không bỏ giữa chừng.
- Tách nhạc (Demucs) tốn RAM: chỉ một luồng tách cùng lúc (code đã có khoá); đừng chạy nhiều tiến trình tách cùng lúc.
- ffmpeg dựng song song tối đa 3 tiến trình (hết RAM sẽ lỗi `get_buffer() failed`).
- Ảnh Muse là `.webp`; font ffmpeg trên Windows: `C\:/Windows/Fonts/arialbd.ttf`; trong `drawtext` ký tự `%` cần thoát; `drawbox` không chạy theo `t` (dùng `overlay` với biểu thức).
- Không xoá hay ghi đè file ngoài thư mục kết quả; không sửa video mẫu gốc.

## 7. Kiểm tra trước khi giao (checklist)
- [ ] Thời lượng từng file đúng spec (lệch <= 0,1s); âm thanh có tiếng liên tục, có nhạc nền giữa các câu.
- [ ] Xem contact sheet >= 5 biến thể rải đều (hoặc tất cả nếu ít): đúng bố cục/nhịp video gốc, chuyển cảnh vào ngay, đoạn flow đủ: mẫu upload -> before -> loading -> after toàn màn hình.
- [ ] Nhân vật khác nhau giữa các biến thể; trưởng thành, hư cấu, ăn mặc đầy đủ, không giống người nổi tiếng, không logo.
- [ ] Không phụ đề cho lời mới; ngôn ngữ lồng tiếng đúng yêu cầu.
- [ ] Biến thể sai/vi phạm: sửa spec, đưa file ra khỏi `out`, chạy lại bằng `--only`; **không giao**.
- [ ] Ghi vào log: đơn giản hoá/hạn chế nếu công cụ không làm được một hiệu ứng (ví dụ ảnh nhỏ chồng lên, chia đôi màn hình).

## 8. Làm từ Google Sheet và lịch tự động (tuỳ chọn)
Xem `HUONG-DAN-TU-DONG.md`: `daily.py check/download/done/fail`, đọc tab kế hoạch (Ngày order, Mã order, Sample, Yêu cầu, Nhân vật, Ngôn ngữ, Số lượng dự kiến), video mẫu là link Drive công khai ẩn sau ô Sample, ảnh after mẫu ở cột "Ảnh after" hoặc trích từ video. Hàng đã làm được đánh dấu trong `userdata\daily_state.json`.

## 9. Bản đồ công cụ
| File | Việc |
|---|---|
| `run.py` / `LUO Chat.bat` | Mở LUO Chat (bật LUO-API Muse + giao diện) |
| `analyze.py` | Contact sheet + mốc đổi cảnh của video mẫu |
| `transcribe.py` | Nhận dạng lời thoại (đa ngôn ngữ), liệt kê giọng đọc |
| `separate.py` | Tách nhạc nền khỏi giọng (Demucs) |
| `specrun.py` | Dựng biến thể từ spec (run/dry/--only) |
| `pipeline.py` | Hàm dựng cấp thấp (timeline, reveal, flow, voice...) |
| `daily.py`, `sheetx.py` | Đọc Google Sheet, tải video mẫu |
| `upload.py`, `drive_upload.gs` | Tải kết quả lên Drive (cần cài Apps Script) |
| `chatctl.py` | Điều khiển hàng đợi LUO Chat bằng dòng lệnh |
