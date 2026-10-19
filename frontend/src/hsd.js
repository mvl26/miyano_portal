// HSD tối thiểu theo yêu cầu khách (spec 2026-10-19 §4.6). Server là chốt
// thật (0–60, ly_do `hsd_toi_thieu_khong_hop_le`); đây chỉ để chặn sớm ở ô nhập.

export const LOI_HSD = 'HSD tối thiểu phải là số tháng từ 0 đến 60.'

// `''`/null/undefined = "để trống" (kế thừa đầu phiếu / không yêu cầu), khác 0.
export function chuanHoaThang(v) {
  if (v === null || v === undefined) return { ok: true, gia_tri: null }
  const s = String(v).trim()
  if (s === '') return { ok: true, gia_tri: null }
  if (!/^\d+$/.test(s)) return { ok: false, gia_tri: null, loi: LOI_HSD }
  const n = Number(s)
  if (n > 60) return { ok: false, gia_tri: null, loi: LOI_HSD }
  return { ok: true, gia_tri: n }
}

// Dòng có giá trị (kể cả 0) thì dùng dòng, không thì đầu phiếu.
export function thangHieuLuc(dong, dauPhieu) {
  const d = dong?.hsd_toi_thieu_thang
  if (d !== null && d !== undefined && d !== '') return Number(d)
  return dauPhieu ?? null
}

// Nhãn hiển thị ở chi tiết đơn; 0/rỗng = không yêu cầu → không hiện gì.
export function nhanHsd(v) {
  const n = Number(v)
  return v !== null && v !== undefined && v !== '' && n > 0 ? `HSD tối thiểu: ${n} tháng` : ''
}
