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

// Gọi một whitelist method của backend portal. Trả về d.message (payload thật).
export async function call(method, args) {
  const res = await fetch(API_PREFIX + method, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': csrfToken(),
    },
    body: JSON.stringify(args || {}),
  })
  const data = await res.json()
  if (!res.ok) {
    const msg = data && (data.exception || data._server_messages || data.message)
    throw new Error(msg || ('HTTP ' + res.status))
  }
  return data.message
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

export default { call, login, logout }
