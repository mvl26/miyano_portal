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
    let msg = data && (data.exception || data._server_messages || data.message)
    let errName = ''
    if (msg && typeof msg === 'string') {
      const m = msg.match(/^([\w.]*Error):\s*(.+)$/s)
      if (m) {
        errName = m[1].split('.').pop()
        msg = m[2]
      }
    }
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
    const msg = (data && (data.exception || data._server_messages || data.message)) || 'Tải tệp lên thất bại.'
    throw new Error(typeof msg === 'string' ? msg.replace(/^[\w.]*Error:\s*/, '') : 'Tải tệp lên thất bại.')
  }
  return data.message // { file_url, file_name, ... }
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
    let msg = 'Không tải được file.'
    try {
      const data = await res.json()
      const raw = data && (data.exception || data._server_messages || data.message)
      if (typeof raw === 'string') {
        const m = raw.match(/^([\w.]*Error):\s*(.+)$/s)
        msg = m ? m[2] : raw
      }
    } catch {
      // Thân response không phải JSON — giữ thông điệp mặc định.
    }
    throw new Error(msg)
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
    let msg = 'Không mở được file.'
    try {
      const data = await res.json()
      const raw = data && (data.exception || data._server_messages || data.message)
      if (typeof raw === 'string') {
        const m = raw.match(/^([\w.]*Error):\s*(.+)$/s)
        msg = m ? m[2] : raw
      }
    } catch {
      // Thân response không phải JSON — giữ thông điệp mặc định.
    }
    throw new Error(msg)
  }
  return URL.createObjectURL(await res.blob())
}

export default {
  call, callKho, khoDownloadUrl, uploadFile, downloadFile, fetchBlobUrl, login, logout,
}
