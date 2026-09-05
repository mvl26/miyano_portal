// API client cho cổng khách hàng Miyano.
//
// SPA chạy trên trang website (không có desk `frappe.call`), nên mọi lời gọi
// whitelist đều qua fetch() tới /api/method/... kèm CSRF token. Token được bơm
// vào <meta name="csrf-token"> bởi www/portal/index.html.

function csrfToken() {
  const el = document.querySelector('meta[name=csrf-token]')
  return el ? el.content : ''
}

const API_PREFIX = '/api/method/miyano_portal.api.portal.'
const KHO_PREFIX = '/api/method/miyano_portal.api.kho.'
const DE_XUAT_PREFIX = '/api/method/miyano_portal.api.de_xuat.'

// ---------------------------------------------------------------------------
// Dịch lỗi từ server thành một câu người dùng ĐỌC ĐƯỢC (Vòng sửa 2, 04/09/2026)
// ---------------------------------------------------------------------------
//
// Lượt chạy thử tay 04/09/2026 bắt một toast hiện NGUYÊN VĂN HTML thô
// (`<details><summary>Bạn không được phép truy cập chức năng này...`) kèm
// thuật ngữ kỹ thuật ("whitelist", "CSRF", "Invalid Request"). `{{ }}` của
// Vue tự ESCAPE nên không có rủi ro chạy mã (XSS) — nhưng người đọc (điều
// dưỡng/quản lý bệnh viện, KHÔNG phải lập trình viên) vẫn thấy nguyên một mớ
// thẻ HTML dạng chữ, không đọc được, không biết phải làm gì tiếp.
//
// HAI hàm DÙNG CHUNG cho MỌI nơi lấy lỗi từ response (`callUrl`, `uploadFile`,
// `downloadFile`, `fetchBlobUrl`) — bốn nơi trước đây tự lột tiền tố
// "ClassName: " bằng bốn bản sao gần giống nhau của cùng một regex; một bản
// sao là một chỗ nữa để quên vá khi cần sửa lại (đúng bài học đắt của nhánh
// này: lỗi lọt qua khe vì bị vá một chỗ mà quên chỗ khác).
const LOI_PHIEN_HET_HAN =
  'Phiên làm việc đã hết hạn hoặc bạn không có quyền thực hiện thao tác này. ' +
  'Vui lòng tải lại trang và đăng nhập lại.'

// QUAN TRỌNG (review độc lập, vòng sửa 2 — sau bản đầu SAI): `PermissionError`
// trong `miyano_portal/api/*.py` KHÔNG chỉ dùng cho hết phiên/thiếu quyền —
// nó là kiểu lỗi NGHIỆP VỤ dùng khắp nơi, MANG SẴN câu tiếng Việt sạch, đọc
// được ("Phiếu này không thuộc đơn vị của bạn.", "Chỉ quản lý mới duyệt được
// đề xuất.", "Bệnh viện chưa mở kho." — hàng chục chỗ `raise
// frappe.PermissionError("...")`). Bản đầu của vòng sửa này đổi TOÀN BỘ
// `PermissionError`/HTTP 403 thành câu "hết phiên, đăng nhập lại" theo TÊN
// LỚP — sẽ nuốt mất các câu nghiệp vụ đó, hiện một lời khuyên SAI (đăng nhập
// lại) cho một lỗi không liên quan gì tới phiên đăng nhập. Bắt bằng
// `grep -rn "PermissionError" miyano_portal/api/` trước khi commit.
//
// Vì vậy KHÔNG thay theo tên lớp `PermissionError`/mã 403 một mình — chỉ
// thay khi thông điệp THẬT SỰ không đọc được: (a) tên lớp chỉ dùng cho lỗi
// PHIÊN/CSRF thật (chưa từng thấy dự án tự `raise` hai lớp này cho lỗi
// nghiệp vụ — đã kiểm bằng grep), (b) mã 401, (c) thông điệp mang THUẬT NGỮ
// kỹ thuật ("csrf", "whitelist", "traceback", "invalid request"), hoặc
// (d) không còn gì sau khi lột thẻ. CỐ Ý KHÔNG coi "có thẻ HTML" một mình là
// dấu hiệu đủ để THAY HẲN câu — một thông điệp nghiệp vụ sạch lỡ có thẻ định
// dạng đơn giản (`<b>...</b>`) chỉ cần LỘT THẺ là đọc được, không cần vứt bỏ
// toàn bộ nội dung; thẻ HTML chỉ đáng thay hẳn câu khi nó ĐI KÈM thuật ngữ kỹ
// thuật (đúng ca thật: `<details><summary>...whitelist...</summary>...`).
const _TEN_LOI_PHIEN = new Set(['CSRFTokenError', 'AuthenticationError'])
const _RAC_KY_THUAT = /csrf|whitelist|traceback|invalid request/i

// Lột thẻ HTML khỏi một chuỗi lỗi — KHÔNG phải để dựng lại HTML (không nơi
// nào trong app dùng `v-html` cho thông điệp lỗi), chỉ để không thẻ thô nào
// lọt ra ngoài ở DẠNG CHỮ trong toast (đúng thứ lượt chạy thử bắt được).
export function _lotTheHtml(text) {
  return text
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

// `raw`: thông điệp thô đã lột tiền tố "ClassName: " (nếu tách được), có thể
// là `null`/`undefined` nếu không trích được gì. `errName`: tên lớp lỗi đã
// tách (rỗng nếu không tách được). `httpStatus`: mã HTTP của response.
export function _dichLoiMayChu(raw, errName, httpStatus) {
  const sach = typeof raw === 'string' ? _lotTheHtml(raw) : ''
  const macDinhLoiPhien =
    _TEN_LOI_PHIEN.has(errName) ||
    httpStatus === 401 ||
    (typeof raw === 'string' && (_RAC_KY_THUAT.test(raw) || !sach))
  if (macDinhLoiPhien) return LOI_PHIEN_HET_HAN
  if (typeof raw !== 'string') return raw
  return sach
}

// Trích một thông điệp lỗi + tên lớp lỗi từ response JSON lỗi của Frappe.
// MỘT hàm DUY NHẤT cho cả bốn nơi gọi (tránh bốn bản sao của cùng một logic
// trích chuỗi). Ba nguồn Frappe có thể trả, theo thứ tự ưu tiên:
//
//  1. `exception` — chuỗi dạng "package.module.ClassName: thông điệp".
//  2. `message` — chuỗi thông điệp trần (một số whitelist ném lỗi kiểu này).
//  3. `_server_messages` — chuỗi JSON LỒNG HAI LỚP (JSON của một MẢNG các
//     chuỗi, mỗi chuỗi lại là JSON của MỘT dict `{message, indicator, ...}`)
//     — không parse đúng hai lớp thì đây là nguồn hiện ra dạng JSON TRẦN
//     trước mặt người dùng (bắt được ở review độc lập, vòng sửa 2 — cùng họ
//     lỗi với `<details><summary>`: máy đọc được, người không đọc được).
//     Parse lỗi (JSON méo, cấu trúc khác) thì KHÔNG trả JSON thô ra ngoài —
//     rơi xuống `{ msg: null }`, nơi gọi tự có thông điệp mặc định.
export function _trichLoiTuResponse(data) {
  let msg = data && data.exception
  if (typeof msg === 'string' && msg) {
    const m = msg.match(/^([\w.]*Error):\s*(.+)$/s)
    if (m) return { msg: m[2], errName: m[1].split('.').pop() }
    return { msg, errName: '' }
  }
  if (data && typeof data.message === 'string' && data.message) {
    return { msg: data.message, errName: '' }
  }
  if (data && typeof data._server_messages === 'string') {
    try {
      const arr = JSON.parse(data._server_messages)
      if (Array.isArray(arr) && arr.length) {
        const dau = JSON.parse(arr[0])
        if (dau && typeof dau.message === 'string' && dau.message) {
          return { msg: dau.message, errName: '' }
        }
      }
    } catch {
      // `_server_messages` méo hoặc khác cấu trúc mong đợi — không trả JSON
      // thô ra ngoài, coi như không trích được gì.
    }
  }
  return { msg: null, errName: '' }
}

// Gọi thẳng một method whitelist theo đường dẫn đầy đủ (đã có prefix).
async function callUrl(url, args) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': csrfToken(),
    },
    body: JSON.stringify(args || {}),
  })
  const data = await res.json()
  if (!res.ok) {
    // exception thường dạng "frappe.exceptions.PermissionError: <thông điệp>"
    // — bỏ phần tên lớp lỗi để chỉ hiển thị thông điệp tiếng Việt, nhưng giữ
    // lại tên lớp ở err.name để nơi gọi phân biệt được PermissionError (vd.
    // "chưa có kho") với lỗi hệ thống thật sự.
    const { msg: trich, errName } = _trichLoiTuResponse(data)
    const msg = _dichLoiMayChu(trich, errName, res.status)
    const err = new Error(msg || ('HTTP ' + res.status))
    if (errName) err.name = errName
    // Phong bì lỗi máy đọc được (`30_API_Spec` §1.1): mảng `{item_code, ly_do,
    // con_lai|boi_so|goi_y, thong_diep}`. Server gửi kèm 417 qua
    // `frappe.local.response`. Nơi gọi nào biết dùng thì liệt kê từng dòng sai
    // thay vì đổ một chuỗi nối bằng <br> vào thẻ text.
    if (data && Array.isArray(data.loi)) err.loi = data.loi
    throw err
  }
  return data.message
}

// Gọi một whitelist method của backend portal. Trả về d.message (payload thật).
export async function call(method, args) {
  return callUrl(API_PREFIX + method, args)
}

// Gọi một whitelist method của module kho (miyano_portal.api.kho).
export async function callKho(method, args) {
  return callUrl(KHO_PREFIX + method, args)
}

// Gọi một whitelist method của module đề xuất mua (miyano_portal.api.de_xuat).
export async function callDeXuat(method, args) {
  return callUrl(DE_XUAT_PREFIX + method, args)
}

// URL tải file (GET, mở tab mới hoặc gán vào href) của một method kho trả về
// nội dung nhị phân (vd. kho_import_template).
export function khoDownloadUrl(method) {
  return KHO_PREFIX + method
}

// Upload một file lên Frappe (endpoint chuẩn /api/method/upload_file), dùng
// cho bước "chọn tệp" của import. KHÔNG dùng callUrl(): trình duyệt phải tự
// đặt Content-Type multipart kèm boundary, nên header đó KHÔNG được set tay.
export async function uploadFile(file) {
  const body = new FormData()
  body.append('file', file)
  body.append('is_private', '1')
  const res = await fetch('/api/method/upload_file', {
    method: 'POST',
    headers: { 'X-Frappe-CSRF-Token': csrfToken() },
    body,
  })
  const data = await res.json()
  if (!res.ok) {
    const { msg: trich, errName } = _trichLoiTuResponse(data)
    throw new Error(_dichLoiMayChu(trich, errName, res.status) || 'Tải tệp lên thất bại.')
  }
  return data.message // { file_url, file_name, ... }
}

// CR-03 — tải một ảnh cho MỘT dòng "hàng chưa có trong hệ thống"
// (`portal_dat_ngoai_tai_anh`). KHÔNG dùng `uploadFile()` ở trên: hàm đó
// gọi endpoint UPLOAD CHUNG của Frappe (`/api/method/upload_file`), không
// biết gì về `de_xuat`/`dong_idx` — hai tham số server dùng để kiểm SỞ HỮU
// (phiếu của ai) và VỊ TRÍ (đính đúng dòng nào) trước khi nhận tệp. Vẫn
// multipart tự tay (không qua `callUrl`) vì cùng lý do `uploadFile()` đã
// ghi: trình duyệt phải tự đặt `Content-Type` kèm boundary.
export async function taiAnhDatNgoai(file, de_xuat, dong_idx) {
  const body = new FormData()
  body.append('file', file)
  body.append('de_xuat', de_xuat)
  body.append('dong_idx', String(dong_idx))
  const res = await fetch(API_PREFIX + 'portal_dat_ngoai_tai_anh', {
    method: 'POST',
    headers: { 'X-Frappe-CSRF-Token': csrfToken() },
    body,
  })
  const data = await res.json()
  if (!res.ok) {
    const { msg: trich, errName } = _trichLoiTuResponse(data)
    throw new Error(_dichLoiMayChu(trich, errName, res.status) || 'Tải ảnh lên thất bại.')
  }
  return data.message // { file_url, anh }
}

// URL GET của `portal_dat_ngoai_xem_anh` — dùng với `fetchBlobUrl()`, không
// gán thẳng vào `<img src>`: một `<img>` trỏ thẳng URL này khi bị từ chối
// (ảnh vừa bị xoá ở tab khác, phiên hết hạn…) chỉ hiện icon ảnh vỡ CỦA
// TRÌNH DUYỆT, không cách nào bắt được lỗi để xử lý — cùng lý do `fetchBlobUrl`
// đã được dựng cho khối xem hoá đơn nháp (HĐĐT).
export function datNgoaiXemAnhUrl(de_xuat, file_url) {
  return (
    API_PREFIX + 'portal_dat_ngoai_xem_anh?de_xuat=' + encodeURIComponent(de_xuat) +
    '&file_url=' + encodeURIComponent(file_url)
  )
}

// Tải một file qua GET rồi lưu về máy — dùng cho chứng từ có thể bị TỪ CHỐI
// tuỳ trạng thái/quyền sở hữu (HĐĐT: BR-E4 kiểm từng lần tải). `<a href>` trỏ
// thẳng vào endpoint GET (cách các nút [⬇ PDF] khác của cổng vẫn dùng) mở một
// TAB MỚI khi lỗi — khách thấy JSON lỗi trần cho một CHỨNG TỪ THUẾ thay vì một
// thông báo tiếng Việt. Hàm này tự đọc lỗi JSON và ném Error để nơi gọi toast,
// chỉ khi thành công mới kích hoạt tải file (fetch -> Blob -> <a download>).
export async function downloadFile(url, fallbackName) {
  const res = await fetch(url, { headers: { 'X-Frappe-CSRF-Token': csrfToken() } })
  if (!res.ok) {
    let trich = null
    let errName = ''
    try {
      const data = await res.json()
      ;({ msg: trich, errName } = _trichLoiTuResponse(data))
    } catch {
      // Thân response không phải JSON — không trích được gì, dùng mặc định.
    }
    throw new Error(_dichLoiMayChu(trich, errName, res.status) || 'Không tải được file.')
  }
  const blob = await res.blob()
  const cd = res.headers.get('Content-Disposition') || ''
  const m = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i)
  const filename = m ? decodeURIComponent(m[1]) : fallbackName || 'file'
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(blobUrl)
}

// Đăng nhập qua endpoint chuẩn của Frappe (form-encoded).
export async function login(usr, pwd) {
  const body = new URLSearchParams({ usr, pwd })
  const res = await fetch('/api/method/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Frappe-CSRF-Token': csrfToken(),
    },
    body: body.toString(),
  })
  if (!res.ok) {
    throw new Error('Đăng nhập thất bại. Kiểm tra email/mật khẩu.')
  }
  return res.json().catch(() => ({}))
}

export async function logout() {
  await fetch('/api/method/logout', {
    method: 'GET',
    headers: { 'X-Frappe-CSRF-Token': csrfToken() },
  })
}

// Nạp một file qua GET rồi trả blob URL để NHÚNG vào trang (không tải về máy).
// Dùng cho khối xem hoá đơn nháp: thứ khách cần thấy là chính file PDF do Fast
// dựng, nên nó phải hiện ngay trong trang chứ không nằm trong thư mục
// Downloads. Tách khỏi downloadFile() vì hai việc khác nhau — cái kia kết thúc
// bằng <a download>, cái này trả URL cho nơi gọi tự đặt vào <iframe>.
// Nơi gọi có trách nhiệm URL.revokeObjectURL() khi rời màn hình.
export async function fetchBlobUrl(url) {
  const res = await fetch(url, { headers: { 'X-Frappe-CSRF-Token': csrfToken() } })
  if (!res.ok) {
    let trich = null
    let errName = ''
    try {
      const data = await res.json()
      ;({ msg: trich, errName } = _trichLoiTuResponse(data))
    } catch {
      // Thân response không phải JSON — không trích được gì, dùng mặc định.
    }
    throw new Error(_dichLoiMayChu(trich, errName, res.status) || 'Không mở được file.')
  }
  return URL.createObjectURL(await res.blob())
}

export default {
  call, callKho, callDeXuat, khoDownloadUrl, uploadFile, downloadFile, fetchBlobUrl, login, logout,
  taiAnhDatNgoai, datNgoaiXemAnhUrl,
}
