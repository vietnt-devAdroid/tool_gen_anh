/**
 * LUO Chat - nhận video từ máy bạn rồi lưu vào thư mục Google Drive của bạn.
 *
 * CÀI MỘT LẦN (khoảng 3 phút):
 *  1. Mở https://script.google.com  ->  Dự án mới  ->  xoá code mẫu, dán TOÀN BỘ file này vào.
 *  2. Đổi TOKEN bên dưới thành một chuỗi bí mật dài do bạn tự đặt (ví dụ 30 ký tự ngẫu nhiên). Giữ kín, chỉ đưa cho LUO Chat.
 *  3. Bấm Triển khai (Deploy) -> Triển khai mới -> loại "Ứng dụng web":
 *        Thực thi với tư cách: Tôi (tài khoản của bạn)
 *        Người có quyền truy cập: Bất kỳ ai
 *     Bấm Triển khai, cấp quyền khi Google hỏi (script cần quyền ghi vào Drive của bạn).
 *  4. Copy "URL ứng dụng web" (dạng https://script.google.com/macros/s/.../exec).
 *  5. Đưa cho LUO Chat: URL này + TOKEN + ID thư mục Drive để lưu kết quả
 *     (ID là đoạn cuối của link thư mục: drive.google.com/drive/folders/<ID>).
 *
 * Mỗi video lưu vào  <thư mục>/<ngày>/<tên video>/<tên file>.  File trùng tên sẽ được thay mới.
 * Giới hạn: mỗi file tối đa khoảng 30 MB (video biến thể thường 2-4 MB).
 */
const TOKEN = 'ĐỔI-THÀNH-CHUỖI-BÍ-MẬT-CỦA-BẠN';

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    if (d.token !== TOKEN || TOKEN.indexOf('ĐỔI-THÀNH') === 0) return out({ ok: false, error: 'sai token' });
    let folder = DriveApp.getFolderById(d.folderId);
    String(d.path || '').split('/').filter(String).forEach(function (n) {
      const it = folder.getFoldersByName(n);
      folder = it.hasNext() ? it.next() : folder.createFolder(n);
    });
    const blob = Utilities.newBlob(Utilities.base64Decode(d.data), d.mime || 'video/mp4', d.name);
    const ex = folder.getFilesByName(d.name);
    while (ex.hasNext()) ex.next().setTrashed(true);
    const f = folder.createFile(blob);
    return out({ ok: true, id: f.getId(), url: f.getUrl() });
  } catch (err) {
    return out({ ok: false, error: String(err) });
  }
}

function doGet() {
  return out({ ok: true, hello: 'LUO Chat uploader' });
}

function out(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
