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

export default { call, callKho, khoDownloadUrl, uploadFile, login, logout }
