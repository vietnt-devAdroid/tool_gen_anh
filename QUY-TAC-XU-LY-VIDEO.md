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
- **Chạy thử: chỉ 1 video** (hoặc đúng số người dùng nói, ví dụ "3 video"). Chỉ chạy cả thư mục khi người dùng nói rõ. Dùng `--only tên1,tên2` hoặc `--limit N`.

#### 0d. Biến thể ĐỔI NHÂN VẬT + HÌNH TRÒN "BEFORE" xuyên suốt video (image to video)
Khi người dùng yêu cầu "thay đổi nhân vật, giữ nguyên nội dung video gốc, luôn có hình tròn ảnh before":
- **Hình tròn BEFORE**: ảnh before (ảnh nhân vật, lấy từ bộ nhân vật theo mã, mục 5b) cắt gọn vào đầu + vai, viền trắng, chữ **BEFORE** bên dưới, **hiện suốt toàn bộ video** (từ giây 0 đến hết), cỡ khoảng 30% cạnh ngắn của khung. Đặt ở **vị trí ít vướng nội dung** (ưu tiên phía trên, như mẫu: giữa hoặc góc trên); không che mặt/chủ thể chính, không che chữ quan trọng. Công cụ tự chọn vị trí theo độ chi tiết/chuyển động của khung hình.
- **Đổi nhân vật chính** bằng nhân vật trong ảnh before; mọi thứ còn lại (bối cảnh, hành động, camera, nhịp, độ dài, âm thanh gốc) giữ y như gốc.
- Công cụ: `python v2v.py <thư_mục_video> --char V04 [--offset N] [--only ...]` (cần có mã nhân vật). Mỗi cảnh gửi Muse đoạn gốc + ảnh nhân vật; ghép; dán hình tròn bằng ffmpeg (`add_before_circle`). Kết quả `<tên>_v2v_before.mp4` (bản chưa dán hình tròn: `_nocircle`). Mỗi video một cuộc trò chuyện (tiêu đề "<tên> - before").
- **Chọn mã đúng giới tính/độ tuổi với chủ thể gốc** (chủ thể nam -> V01/V07/V13; nữ -> V04/V10/V16; trung niên V02/V05/V08/V11/V14/V17)
- **Hạn chế đã biết**: Muse không giữ cùng một khuôn mặt qua các cảnh (mỗi cảnh tạo riêng), có thể lệch nhân vật; chữ/logo trong video gốc không tái tạo
- Nhiều video cùng một câu lệnh: trong giao diện LUO Chat, đính kèm nhiều video rồi tích "Mỗi video 1 cuộc trò chuyện" để tạo từng cuộc riêng, chạy song song (tối đa = số tài khoản x 2).

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

### 3b. Video có cặp ảnh BEFORE -> AFTER ở phần đầu (nhịp bám sát video gốc)
Áp dụng khi video mẫu cho thấy ảnh before rồi biến đổi sang ảnh after (nhiều cặp nối nhau). **Đo nhịp thật của video gốc, không đoán**:
1. Trích khung 10 hình/giây vài giây đầu (`ffmpeg -t 8 -i source.mp4 -vf "fps=10,scale=72:-2,tile=14x6" -frames:v 1 fine.png`, mỗi ô = 0,1s) rồi **nhìn** để ghi cho MỘT cặp: (a) giữ ảnh before, (b) thời lượng quét before -> after, (c) giữ ảnh after, (d) hiệu ứng + thời lượng sang cặp kế, (e) chu kỳ cả cặp.
2. **Thời lượng quét before -> after = đúng như gốc** (ví dụ Z0137: ~1,2s; làm nhanh hơn như 0,8s là sai, trông gấp). **Giữ ảnh after không dài hơn gốc** (Z0137: ~1,0s; đặt trong khoảng 0,9-1,2s, KHÔNG để > 1,5s vì ảnh đứng yên lâu rồi cắt đột ngột sẽ giật). Hiệu ứng sang cặp kế dùng đúng loại và độ dài của gốc (Z0137: loé trắng ~0,4s). Ảnh before chỉ giữ <= 0,3s.
3. **Số cặp = độ dài phần đầu / chu kỳ cặp của gốc** (Z0137: chu kỳ ~2,6s, phần đầu 18s -> 7 cặp), KHÔNG chọn chu kỳ tròn tuỳ ý (như 3,0s) rồi để thừa thời gian giữ.
4. Mốc dựng (`timeline`: `t` = lúc hiệu ứng bắt đầu, `d` = độ dài hiệu ứng): ảnh before `b_i` tại `i x chu_kỳ` (hiệu ứng sang `glow`); ảnh after `a_i` tại `b_i.t + glow + 0,05`, `d = thời lượng quét`; thời gian giữ after = chu_kỳ - (glow + 0,05 + quét) phải xấp xỉ gốc. Cặp đầu: `a_0` tại ~0,2s (gốc đã bắt đầu quét ngay từ giây 0).
5. Sau khi dựng: xem lại khung hình vùng chuyển (không chỉ contact sheet thưa) để chắc nhịp quét/giữ khớp bảng đo ở bước 1; chỉnh rồi dựng lại (chỉ tốn ffmpeg nếu ảnh Muse đã có).
- Lưới 2x2 (`type: grid2x2`): 4 ô cùng ảnh gốc, mỗi ô quét lên (`wipeup`) sang ảnh biến đổi tại đúng mốc video gốc, nhãn trắng viền đen dưới mỗi ô; sau lưới thay end card app bằng flow.
- Chiều tỉ lệ & cỡ: giữ tỉ lệ video gốc (`size` trong spec). Ảnh Muse 9:16.

## 4. Âm thanh
- Video gốc **chỉ nhạc**: giữ nhạc gốc, lặp cho hết video (mặc định `audio: "loop"`, chỗ nối chồng mờ 0,5s, mờ cuối 0,6s).
- Video gốc **có lời nói**: viết lời mới **ngắn**, đúng ý video, bằng ngôn ngữ yêu cầu (cột Ngôn ngữ / yêu cầu người dùng; trống = giữ ngôn ngữ gốc), chia câu khớp nhịp cảnh (kể cả đoạn flow: giới thiệu upload, đang loading, ảnh after xong). Đặt `revoice` trong spec (giọng chọn bằng `transcribe.py --voices <mã>` ví dụ `en`, `pt`, `es`, `vi`). **KHÔNG hiển thị phụ đề** cho lời mới (không dùng `captions`).
- Lồng tiếng mới **GIỮ NHẠC NỀN gốc**: `specrun` tự tách nhạc khỏi giọng gốc bằng Demucs (`separate.py`, cache cạnh video), lặp nhạc hết video và tự hạ nhỏ khi có giọng mới. Nếu không tách được thì chỉ có giọng mới (ghi vào log).
- Lời đọc quá dài so với video sẽ báo lỗi: rút ngắn câu hoặc tăng `rate`.
- **Tốc độ đọc mặc định `+18%`** (`pipeline.VOICE_RATE`; `+8%` nghe chậm so với video mẫu). Không đặt `rate` trong spec thì dùng mức này.
- **Số ảnh biến đổi phải THEO LỜI (sub) của từng video**, không cố định: dùng `pipeline.plan_beats(lines, 18.0, voice_name)` -> danh sách mốc bắt đầu từng ảnh. Mỗi CÂU ở phần đầu = một nhịp biến đổi (mốc = lúc câu bắt đầu đọc, theo đúng giọng/tốc độ); câu dài hơn 5,5s tách đôi; nhịp ngắn hơn 3,4s gộp; tối thiểu 3, tối đa 6 ảnh. Thường ra 4-5 ảnh cho phần đầu 18s (trước đây 7-12 ảnh là quá nhiều). Video before->after: thời gian dôi ra dồn vào ảnh BEFORE, giữ ảnh AFTER vẫn ~1s.

## 5. Tạo ảnh bằng Muse (qua LUO Chat)
- Prompt tiếng Anh, "photorealistic", dọc 9:16, mô tả nhân vật + trang phục đầy đủ + bối cảnh + dáng. Mỗi biến thể phải **khác rõ rệt** về nhân vật/dáng/bối cảnh.
- Giữ nhân vật nhất quán giữa các ảnh: stage sau dùng `ref` ảnh stage trước. Ảnh AFTER: `ref: ["before", "after_sample"]` và prompt nói rõ: GIỮ danh tính của ảnh thứ nhất, CHỈ áp dụng kiểu biến đổi của ảnh thứ hai, KHÔNG sao chép gương mặt ảnh thứ hai.
- Ảnh đã tạo được tái sử dụng theo (prompt + ảnh tham chiếu), nên chạy lại không tốn thêm.
- Bàn tay/chuyển động thật (ví dụ tay đang vẽ): chỉ dùng clip ngắn Muse tạo từ ảnh tĩnh khi video gốc có chuyển động đó.

## 5b. BỘ NHÂN VẬT và MÃ NHÂN VẬT (loại image to image)
- Bộ nhân vật nằm ở `D:\180 nhan vat Photo` (đổi bằng `characters_dir` trong `daily_config.json`): **18 thư mục = 18 mã** (V01..V18), mỗi thư mục **10 ảnh nhân vật toàn thân nền trắng do Muse tạo**. Tên thư mục: `V04_Au-My_Nu_20-35` = mã + khu vực (Au-My / Latin / India) + giới tính (Nam / Nu) + nhóm tuổi (20-35 / 40-60 / 5-6).
- **Sau mỗi video người dùng cho MÃ nhân vật** (ví dụ "V04") ứng với tên thư mục. Dùng các ảnh của thư mục đó làm **ảnh BEFORE** (danh tính + trang phục) cho các biến thể: nhân vật 1, 2, ..., 10 luân phiên; nếu số biến thể > 10 thì dùng lại nhân vật nhưng đổi dáng/bối cảnh. Chưa có mã mà task cần nhân vật thì **hỏi người dùng mã**.
- Công cụ: `python characters.py list | show V04 | pick V04 20`. Trong spec dùng ảnh có sẵn bằng `{"key": "before", "use": "<đường dẫn ảnh>"}` (không tạo lại); rồi ảnh AFTER tạo từ ảnh before đó: `ref: ["before", "after_sample"]` (giữ danh tính của before, theo kiểu biến đổi của after mẫu, không sao chép gương mặt người trong ảnh mẫu). Mô tả người cho prompt lấy từ `describe` của mã (ví dụ "Latin American female, aged 20-35").
- **Nhóm tuổi 5-6 (V03, V06, V09, V12, V15, V18) là TRẺ EM: KHÔNG dùng làm chủ thể** (quy tắc nội dung); nếu người dùng đưa các mã này thì báo và đề nghị mã người lớn tương ứng (cùng khu vực/giới tính, nhóm 20-35 hoặc 40-60).
- Các ảnh nhân vật là ảnh AI hư cấu của người dùng, vẫn áp dụng: ăn mặc đầy đủ, không biến thành người nổi tiếng, không sao chép gương mặt từ ảnh mẫu.

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

## 10. Bài học bổ sung (image to image, đã trả giá)
- **Trẻ em**: gốc có trẻ em thì làm bản TOÀN NGƯỜI LỚN và nói rõ với người dùng; không tạo ảnh before/after của trẻ em thật. Ảnh `after_sample` phải LÀM MỜ mặt/chữ/logo, nếu không Muse sao chép mặt (kể cả trẻ em) sang ảnh after; prompt dặn "show ONLY the N adults, no children"; xem ảnh after cuối của từng video trước khi báo xong.
- **Logo**: không dùng logo, trừ logo Grand Theft Auto VI người dùng đã chấp nhận cho video concept GTA (`edge_gta.png`, chạy theo mép quét: clip `{"trans":"wipedown","edge":"<png>"}`).
- **Ảnh after ở đuôi upload** (`fafter`) phải là ảnh SAU BIẾN ĐỔI đúng concept video, tạo từ `fbefore`, không phải ảnh chung chung (lỗi Z0177).
- **Từ bị Muse chặn**: tránh "nude", "child"... kể cả tên màu ("nude-pink" -> "blush-pink"). Áo trễ vai phải có áo/đồ bên trong cùng tông để không trông như hở.
- **Cache và dựng lại**: Muse cache theo tiêu đề (id spec) + prompt + ảnh đầu: muốn ảnh mới thì ĐỔI `id`. `specrun` bỏ qua biến thể đã có mp4: xoá mp4 cũ rồi mới dựng lại.
- **Kho nhân vật** chỉ 10 ảnh/mã: biến thể > 10 sẽ trùng người (Z0172 biến thể 6-10 lặp 1-5); cần mã khác hoặc ảnh tự gen. Không dùng nhóm trẻ em (V03, V06, V09, V12, V15, V18).
- **Chữ chính xác**: dùng `text` trong stage (đóng sau khi ảnh tạo; `heart`, `line`, `arrow`, `image`, `blend: multiply`), không để Muse tự viết chữ khi cần đúng từng ký tự. Chữ chỉ nằm trên ảnh before/after ở phần đầu theo video mẫu; đoạn đuôi upload không đóng chữ nếu mẫu không có.
- **Âm thanh**: `audio: orig_head` (giữ âm gốc phần đầu), `orig_keep` (chỉ thay lời gốc bằng giọng mới trên nền nhạc, giữ âm gốc sau mốc cắt). Nhạc bài hát gốc phải giữ nguyên, không thay nhạc khác.
- **Nhịp**: transition nhanh như gốc, rút tổng thời lượng nếu cần; số ảnh theo sub (`plan_beats`); phụ đề từng chữ chỉ khi video mẫu có.
- **Giao việc luồng phụ**: dùng Agent MỚI + brief ngắn trỏ `AGENT-BRIEF.md`, không fork (fork mang cả ngữ cảnh dài, rất tốn token). Lệnh như "chạy batch Z0175" gõ cho Claude, KHÔNG gõ vào khung chat của LUO Chat (sẽ bị gửi cho Muse làm prompt).
- **Quy trình người dùng muốn**: phân tích -> spec -> dry -> MỘT bản mẫu để kiểm -> khi duyệt mới chạy 10 biến thể.
