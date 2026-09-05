// Vòng sửa 2 (04/09/2026) — bài test cho `_dichLoiMayChu()`/`_lotTheHtml()`
// trong `api.js`. Lượt chạy thử tay bắt một toast hiện NGUYÊN VĂN HTML thô
// (`<details><summary>Bạn không được phép truy cập chức năng này...`) — hai
// hàm này là TOÀN BỘ tầng "dịch lỗi server thành câu người đọc được" của
// SPA, dùng chung cho callUrl/uploadFile/downloadFile/fetchBlobUrl.
//
// Không có test framework nào (vitest/jest) được cài cho `frontend/` — thư
// mục này chỉ có Vite làm bundler, không có bộ chạy test. Thay vì viết một
// bài "trông như test" mà không ai chạy, dùng `node:test` + `node:assert`
// (built-in từ Node 18, không cần cài thêm gì) — chạy thật bằng:
//
//   node --test src/api.dich-loi.test.mjs
//
// Mỗi bài dưới đây khẳng định bằng REGEX rằng chuỗi cuối cùng sẽ đưa vào
// toast (a) không còn thẻ HTML nào, và (b) với lỗi quyền/phiên thì đúng là
// câu tiếng Việt cố định, không phải nguyên văn lỗi máy chủ.

import test from 'node:test'
import assert from 'node:assert/strict'
import { _dichLoiMayChu, _lotTheHtml, _trichLoiTuResponse } from './api.js'

const CO_THE_HTML = /<[a-zA-Z][^>]*>/

test('lột thẻ HTML thô (đúng ca bắt được ở lượt chạy thử tay)', () => {
  const raw =
    '<details><summary>Bạn không được phép truy cập chức năng này (whitelist)' +
    '</summary><pre>Traceback...</pre></details>'
  const sach = _lotTheHtml(raw)
  assert.doesNotMatch(sach, CO_THE_HTML, 'không được còn thẻ HTML nào sau khi lột')
  assert.match(sach, /Bạn không được phép truy cập chức năng này/)
})

test('_dichLoiMayChu lột thẻ HTML cho lỗi KHÔNG PHẢI lỗi quyền/phiên', () => {
  const raw = '<b>Số lượng</b> vượt hạn mức cho phép.'
  const ket_qua = _dichLoiMayChu(raw, 'ValidationError', 417)
  assert.doesNotMatch(ket_qua, CO_THE_HTML, 'không được dựng HTML thô ra toast')
  assert.match(ket_qua, /Số lượng.*vượt hạn mức cho phép/)
})

test('_dichLoiMayChu đổi thông điệp mang RÁC KỸ THUẬT (thẻ HTML + "whitelist"/"CSRF") thành câu tiếng Việt cố định', () => {
  // errName ở đây CỐ Ý là 'PermissionError' — nhưng thứ khiến bài này đổi
  // câu KHÔNG PHẢI vì tên lớp (xem bài "KHÔNG đụng vào PermissionError
  // NGHIỆP VỤ" bên dưới — cùng errName, câu sạch thì đi qua nguyên vẹn), mà
  // vì bản thân thông điệp mang rác kỹ thuật (thẻ HTML, "whitelist", "CSRF").
  const raw =
    '<details><summary>Bạn không được phép truy cập chức năng này (whitelist)' +
    '</summary><pre>...CSRF...</pre></details>'
  const ket_qua = _dichLoiMayChu(raw, 'PermissionError', 403)
  assert.doesNotMatch(ket_qua, CO_THE_HTML, 'không được còn thẻ HTML nào')
  assert.doesNotMatch(ket_qua, /whitelist/i, 'không được lộ thuật ngữ kỹ thuật')
  assert.match(ket_qua, /đăng nhập lại/i, 'phải là câu người dùng đọc hiểu được')
})

test('_dichLoiMayChu đổi lỗi CSRFTokenError (400 Invalid Request) thành câu tiếng Việt', () => {
  // Đúng ca thứ hai bắt được ở lượt chạy thử: thử lại ngay sau lỗi 403 thì
  // ra 400 CSRFTokenError — thông điệp thô chứa chữ "CSRF" nên rơi vào nhánh
  // "rác kỹ thuật" của `_dichLoiMayChu`, không cần soi riêng mã 400.
  const ket_qua = _dichLoiMayChu('Invalid Request. CSRF Token Mismatch.', '', 400)
  assert.doesNotMatch(ket_qua, /CSRF/i, 'không được lộ thuật ngữ kỹ thuật')
  assert.match(ket_qua, /đăng nhập lại/i)
})

test('_dichLoiMayChu KHÔNG đụng vào lỗi nghiệp vụ bình thường (không phải quyền/phiên)', () => {
  // Vế âm: một lỗi nghiệp vụ tiếng Việt, sạch, mã HTTP không phải 401 —
  // câu gốc phải đi qua nguyên vẹn (chỉ lột thẻ HTML, không có gì để lột ở
  // đây), KHÔNG bị đổi thành câu "hết phiên" chung chung.
  const raw = 'Kho chưa được mở cho khách hàng này.'
  const ket_qua = _dichLoiMayChu(raw, 'ValidationError', 417)
  assert.equal(ket_qua, raw)
})

test('_dichLoiMayChu KHÔNG đụng vào PermissionError NGHIỆP VỤ (bản đầu vòng sửa 2 SAI ở đúng ca này)', () => {
  // `miyano_portal/api/*.py` dùng `frappe.PermissionError` cho HÀNG CHỤC lỗi
  // NGHIỆP VỤ mang câu tiếng Việt sạch sẵn (`raise frappe.PermissionError(
  // "Phiếu này không thuộc đơn vị của bạn.")`, "Chỉ quản lý mới duyệt được
  // đề xuất.", v.v — xem `grep -rn "PermissionError" miyano_portal/api/`).
  // Bản đầu của vòng sửa này đổi TOÀN BỘ PermissionError/403 thành câu "hết
  // phiên, đăng nhập lại" — SAI cho đúng ca này: một khách hàng bị từ chối
  // vì kho chưa mở sẽ thấy lời khuyên "đăng nhập lại" hoàn toàn lạc đề, dù
  // phiên của họ vẫn còn nguyên. Bài này CHÍNH LÀ bài mà review độc lập chỉ
  // ra là thiếu — nó phải XANH với `_dichLoiMayChu` đúng, và phải ĐỎ nếu ai
  // đó quay lại kiểu "thay theo tên lớp" của bản đầu.
  const raw = 'Bệnh viện này chưa mở kho.'
  const ket_qua = _dichLoiMayChu(raw, 'PermissionError', 403)
  assert.equal(ket_qua, raw, 'câu nghiệp vụ sạch phải đi qua NGUYÊN VẸN, không bị thay bằng câu hết phiên')
})

test('GHI NHẬN RANH GIỚI (advisor, vòng sửa 2): rác kỹ thuật ở BẤT KỲ ĐÂU trong raw thắng câu nghiệp vụ sạch', () => {
  // `_RAC_KY_THUAT` soi trên TOÀN BỘ `raw`, không chỉ trên phần còn lại sau
  // khi lột thẻ — nghĩa là nếu Frappe (ở chế độ debug, hoặc một lỗi khác)
  // nối một traceback/thuật ngữ kỹ thuật vào SAU một câu nghiệp vụ sạch,
  // toàn bộ câu bị thay bằng "hết phiên", kể cả phần nghiệp vụ đọc được.
  // Đây là LỰA CHỌN CÓ CHỦ Ý (an toàn theo hướng thà hiện một câu chung
  // chung còn hơn để lọt một traceback), KHÔNG PHẢI sơ suất — bài này ghim
  // lại ranh giới đó để người sau đọc thấy một quyết định đã được cân nhắc,
  // không phải một lỗ hổng chưa ai để ý.
  const raw = 'Phiếu này không thuộc đơn vị của bạn. Traceback: ...'
  const ket_qua = _dichLoiMayChu(raw, 'PermissionError', 403)
  assert.match(ket_qua, /đăng nhập lại/i, 'phải rơi vào câu "hết phiên" cố định')
  assert.doesNotMatch(ket_qua, /Traceback/i, 'không được lộ chữ "Traceback"')
})

test('_trichLoiTuResponse đọc được message từ `_server_messages` JSON lồng hai lớp, không trả JSON thô', () => {
  // Đúng hình Frappe trả khi không có `exception` — JSON của một MẢNG các
  // chuỗi, mỗi chuỗi lại là JSON của một dict `{message, indicator}`. Không
  // parse đúng hai lớp thì một nurse sẽ thấy dấu ngoặc nhọn/gạch chéo ngược
  // trần trước mặt — cùng họ lỗi với thẻ HTML thô (review độc lập, vòng sửa
  // 2), chỉ khác nguồn field.
  const data = {
    _server_messages: JSON.stringify([
      JSON.stringify({ message: 'Số lượng vượt hạn mức cho phép.', indicator: 'red' }),
    ]),
  }
  const { msg, errName } = _trichLoiTuResponse(data)
  assert.equal(msg, 'Số lượng vượt hạn mức cho phép.')
  assert.equal(errName, '')
})

test('_trichLoiTuResponse KHÔNG trả JSON thô ra ngoài khi `_server_messages` méo', () => {
  const data = { _server_messages: '{not valid json' }
  const { msg } = _trichLoiTuResponse(data)
  assert.equal(msg, null, 'parse lỗi thì coi như không trích được gì, KHÔNG trả chuỗi JSON méo')
})
