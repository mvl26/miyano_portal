// Định dạng tiền tệ / ngày tháng dùng chung cho portal.

// VND đầy đủ: 45.870.000 ₫
export function fmtVND(v) {
  const n = Number(v || 0)
  return n.toLocaleString('vi-VN') + ' ₫'
}

// VND rút gọn theo triệu cho KPI: 128,4 tr ₫
export function fmtVNDShort(v) {
  const n = Number(v || 0)
  if (Math.abs(n) >= 1e6) {
    return (n / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 1 }) + ' tr ₫'
  }
  return fmtVND(n)
}

// ISO (yyyy-mm-dd) → dd/mm/yyyy
export function fmtDate(v) {
  if (!v) return ''
  const s = String(v).slice(0, 10)
  const parts = s.split('-')
  if (parts.length !== 3) return s
  return `${parts[2]}/${parts[1]}/${parts[0]}`
}

// Map trạng thái đơn (đã Việt hoá ở backend) → class badge.
export function statusBadge(statusVi) {
  const map = {
    'Chờ xác nhận': 'b-gray',
    'Đang xử lý': 'b-blue',
    'Đang giao': 'b-orange',
    'Hoàn thành': 'b-green',
    'Đã huỷ': 'b-red',
  }
  return map[statusVi] || 'b-gray'
}

// Map trạng thái hoá đơn (đã Việt hoá ở backend) → class badge.
export function invoiceBadge(statusVi) {
  const map = {
    'Nháp': 'b-gray',
    'Chưa thanh toán': 'b-blue',
    'TT một phần': 'b-orange',
    'Đã thanh toán': 'b-green',
    'Quá hạn': 'b-red',
    'Trả hàng': 'b-gray',
    'Đã ghi sổ': 'b-blue',
    'Đã huỷ': 'b-red',
  }
  return map[statusVi] || 'b-gray'
}

// YYYY-MM-DD hôm nay (local) để so sánh hạn thanh toán.
export function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Cộng thêm n ngày vào hôm nay → YYYY-MM-DD.
export function addDaysISO(n) {
  const d = new Date()
  d.setDate(d.getDate() + n)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// BR-O13 — cộng NGÀY LÀM VIỆC, bỏ qua Thứ Bảy và Chủ Nhật.
// Phải khớp `portal_dat_hang.ngay_giao_mac_dinh()` phía server: lệch nhau thì
// ô nhập điền sẵn một ngày mà chính server vừa từ chối.
// Cố ý không trừ ngày lễ — server cũng không, và một bảng ngày lễ chỉ có ở
// một phía là cách chắc chắn để hai bên lệch nhau.
export function addWorkDaysISO(n) {
  const d = new Date()
  let conLai = n
  while (conLai > 0) {
    d.setDate(d.getDate() + 1)
    const thu = d.getDay() // 0 = CN, 6 = T7
    if (thu !== 0 && thu !== 6) conLai -= 1
  }
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Số ngày từ hôm nay tới ngày ISO (dương = còn hạn, âm = quá hạn).
export function daysUntil(iso) {
  if (!iso) return null
  const target = new Date(String(iso).slice(0, 10) + 'T00:00:00')
  const now = new Date(todayISO() + 'T00:00:00')
  return Math.round((target - now) / 86400000)
}
