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

// ISO datetime (yyyy-mm-dd HH:MM:SS) → dd/mm/yyyy HH:MM — dùng cho hạn SLA
// tính bằng GIỜ (E6 `sla_den_han`, 48 giờ làm việc): chỉ có ngày thì một hạn
// "14/08 09:00" và "14/08 17:00" hiện ra giống hệt nhau.
export function fmtDateTime(v) {
  if (!v) return ''
  const s = String(v)
  const datePart = fmtDate(s)
  const timePart = s.slice(11, 16)
  return timePart ? `${datePart} ${timePart}` : datePart
}

// Map trạng thái đơn (đã Việt hoá ở backend) → class badge.
export function statusBadge(statusVi) {
  const map = {
    'Chờ xác nhận': 'b-gray',
    'Đang xử lý': 'b-blue',
    'Đang giao': 'b-orange',
    'Hoàn thành': 'b-green',
    'Hoàn thành (đóng sớm)': 'b-green',
    'Đã huỷ': 'b-red',
    // Review vòng 1 Task 11 — nhãn MỚI của `_so_status_vi_full` cho
    // `workflow_state = "Từ chối"`. Thiếu dòng này thì một đơn Miyano đã
    // từ chối đeo badge XÁM y hệt một đơn đang chờ xử lý bình thường —
    // đúng tín hiệu sai mà bản vá backend vừa dựng ra để dẹp.
    'Miyano đã từ chối': 'b-red',
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

// Map trạng thái `Portal De Xuat Mua` (nguyên văn tiếng Việt của doctype,
// options: Nháp/Chờ duyệt/Đã duyệt/Chờ duyệt sửa/Từ chối/Đã huỷ) → class
// badge. Dùng chung cho màn danh sách (Task 3) và chi tiết (Task 4) — một
// nguồn duy nhất, không lặp lại bảng màu ở từng view.
export function deXuatBadge(trangThai) {
  const map = {
    'Nháp': 'b-gray',
    'Chờ duyệt': 'b-blue',
    'Chờ duyệt sửa': 'b-orange',
    'Đã duyệt': 'b-green',
    'Từ chối': 'b-red',
    'Đã huỷ': 'b-red',
  }
  return map[trangThai] || 'b-gray'
}

// Task 11 (QĐ-G11) — MỘT dòng đời cho màn "Yêu cầu của tôi":
// `nhap → cho_duyet → da_duyet → cho_khach_dong_y → da_giao`, cộng hai ngõ
// cụt. Giá trị do backend suy (`portal_yeu_cau_cua_toi.giai_doan`), không
// phải client tự ghép từ hai từ điển trạng thái cũ.
//
// Ruling P54 (chủ đầu tư, 26/08/2026) — TÁCH KHOÁ KHỎI NHÃN. Tới trước bản
// này, backend trả thẳng chữ tiếng Việt và chính chữ đó vừa là khoá lọc vừa
// là giá trị đi trong URL (`?chip=`), nên đổi một chữ vì lý do BIÊN TẬP làm
// chết mọi link đã gửi cho bệnh viện. Nay backend chỉ nói KHOÁ; ba bảng
// dưới đây là NƠI DUY NHẤT trong cả hệ thống ánh xạ khoá → chữ người đọc.
export const GIAI_DOAN = [
  'nhap', 'cho_duyet', 'da_duyet', 'cho_khach_dong_y',
  'da_giao', 'tu_choi', 'da_huy',
]

// Đổi chữ ở BẢNG NÀY là đủ, và từ P54 trở đi việc đó KHÔNG còn động tới
// khoá, tới URL, tới bộ lọc hay tới bất kỳ liên kết nào đã phát ra ngoài.
//
// `cho_khach_dong_y` — tên cũ "Chờ báo giá" đọc NGƯỢC: nó nghe như đang chờ
// Miyano, trong khi đơn thật sự chờ Miyano ra giá lại nằm ở "Đã duyệt".
// Giai đoạn này là lúc BÁO GIÁ ĐÃ VỀ và bệnh viện đang giữ việc.
export const NHAN_GIAI_DOAN = {
  nhap: 'Nháp',
  cho_duyet: 'Chờ duyệt',
  da_duyet: 'Đã duyệt',
  cho_khach_dong_y: 'Chờ quý vị đồng ý',
  da_giao: 'Đã giao',
  tu_choi: 'Từ chối',
  da_huy: 'Đã huỷ',
}

// Bí danh cho nhãn CŨ — chính bộ chuỗi đã đi ra ngoài trong `?chip=` trước
// 26/08/2026. ĐÓNG BĂNG: không thêm nhãn mới vào đây, thêm là buộc lại nhãn
// vào định danh đúng như trước P54.
//
// Bảng này KHÔNG thừa dù backend cũng có bản của nó: đường đi của một link
// cũ là `?chip=Chờ báo giá` → `onMounted` → rào lọc phía client. Rào đó
// không nhận ra chuỗi cũ thì `giai_doan` gửi lên là `undefined` và bí danh
// phía backend KHÔNG BAO GIỜ được chạm tới — bệnh viện thấy "Tất cả" mà
// không có tín hiệu gì.
const BI_DANH_GIAI_DOAN_CU = {
  'Nháp': 'nhap',
  'Chờ duyệt': 'cho_duyet',
  'Đã duyệt': 'da_duyet',
  'Chờ báo giá': 'cho_khach_dong_y',
  'Đã giao': 'da_giao',
  'Từ chối': 'tu_choi',
  'Đã huỷ': 'da_huy',
}

// Chuẩn hoá một giá trị từ URL về khoá. `''` khi không nhận ra — nơi gọi
// hiểu là "không lọc", KHÔNG phải là ném lỗi vào mặt người vừa mở một link.
export function khoaGiaiDoan(gt) {
  const s = String(gt || '')
  if (GIAI_DOAN.includes(s)) return s
  return BI_DANH_GIAI_DOAN_CU[s] || ''
}

export function nhanGiaiDoan(khoa) {
  return NHAN_GIAI_DOAN[khoa] || khoa || ''
}

export function giaiDoanBadge(khoa) {
  const map = {
    nhap: 'b-gray',
    cho_duyet: 'b-blue',
    da_duyet: 'b-blue',
    cho_khach_dong_y: 'b-orange',
    da_giao: 'b-green',
    tu_choi: 'b-red',
    da_huy: 'b-red',
  }
  return map[khoa] || 'b-gray'
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
