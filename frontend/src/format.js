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
