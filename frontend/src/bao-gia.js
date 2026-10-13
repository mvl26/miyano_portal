// Tab "Yêu cầu báo giá" (spec 2026-10-12 §6). JS thuần để test được bằng
// `node --test`; view chỉ vẽ theo những gì module này trả.
//
// Khoá nhóm KHÁC khoá giai đoạn của tab Đơn hàng (`GIAI_DOAN` ở format.js) và
// không được nhập vào đó: hai tab là hai vòng đời.

export const NHOM_BAO_GIA = ['nhap', 'dang_bao_gia', 'cho_dong_y', 'da_dong_y', 'da_dong']

// Hai nhãn giữa nói rõ việc đang ở phía ai. Nhãn "Chờ báo giá" từng bị đọc
// ngược (khách tưởng mình đang chờ trong khi việc ở phía họ) nên không dùng.
const NHAN = {
  nhap: 'Nháp / chờ duyệt nội bộ',
  dang_bao_gia: 'Miyano đang báo giá',
  cho_dong_y: 'Chờ anh/chị đồng ý',
  da_dong_y: 'Đã đồng ý',
  da_dong: 'Đã đóng',
}

const BADGE = {
  nhap: 'b-gray', dang_bao_gia: 'b-blue', cho_dong_y: 'b-orange',
  da_dong_y: 'b-green', da_dong: 'b-red',
}

export function nhanNhomBaoGia(khoa) { return NHAN[khoa] || khoa || '' }
export function nhomBaoGiaBadge(khoa) { return BADGE[khoa] || 'b-gray' }

export function khoaNhomBaoGia(gt) {
  const s = String(gt || '')
  return NHOM_BAO_GIA.includes(s) ? s : ''
}

// Phiếu chưa có Quotation (nháp, chờ duyệt nội bộ) mở màn chi tiết phiếu đang
// có: việc gửi duyệt / duyệt vẫn nằm ở đó. `tu: 'bao-gia'` để nút "Quay lại"
// của màn đó về đúng tab này chứ không về tab Đơn hàng.
export function dichDongBaoGia(dong) {
  if (dong.bao_gia) return { name: 'bao-gia-detail', params: { ten: dong.bao_gia } }
  return { name: 'de-xuat-detail', params: { ten: dong.de_xuat }, query: { tu: 'bao-gia' } }
}

export function hanhDongBaoGia(bg) {
  if (!bg || !bg.duoc_dong_y) return []
  const kq = ['dong_y', 'tu_choi']
  if (bg.duoc_sua_so_luong) kq.push('sua_so_luong')
  return kq
}

export function dongDaSua(items, soLuongMoi) {
  const kq = []
  for (const it of items || []) {
    const moi = Number(soLuongMoi?.[it.name])
    if (!Number.isFinite(moi) || moi <= 0 || moi === Number(it.qty)) continue
    kq.push({ name: it.name, qty: moi })
  }
  return kq
}

// Đi đâu sau `portal_order_place` (màn Đặt hàng, nhánh quản lý). Giỏ có hàng
// chờ báo giá nay ra một YÊU CẦU BÁO GIÁ chứ không ra đơn, nên kết quả có thể
// không mang mã đơn nào:
//   * `tron`    — một đơn và một yêu cầu báo giá: về danh sách đơn hàng.
//   * `bao_gia` — chỉ có yêu cầu báo giá: sang chi tiết yêu cầu vừa tạo.
//   * `don`     — đúng một đơn: màn Đặt hàng tự hiện thẻ xác nhận (`to: null`).
// Loại `don` chỉ trả khi CÓ mã đơn — thẻ xác nhận in mã đó ra màn.
export function dichSauDatHang(res) {
  const don = res?.don || []
  if (don.length === 2) return { loai: 'tron', to: { name: 'yeu-cau' } }
  const baoGia = res?.bao_gia || don.find((d) => d.bao_gia)?.bao_gia
  if (baoGia) return { loai: 'bao_gia', to: { name: 'bao-gia-detail', params: { ten: baoGia } } }
  if (res?.sales_order) return { loai: 'don', to: null }
  return { loai: 'khac', to: { name: 'yeu-cau' } }
}

// Số lượng khách gõ ở màn sửa số lượng phải là số lớn hơn 0 ở MỌI dòng. Trả
// câu lỗi của dòng sai đầu tiên, hoặc '' khi không có dòng nào sai. Cùng nghĩa
// với câu server trả (`bao_gia.py`): dòng 0 không được lặng lẽ bỏ qua — bỏ một
// mặt hàng không phải việc của màn này. Dòng không có ô nhập (`undefined`) là
// dòng không sửa.
export function loiSoLuong(items, soLuongMoi) {
  for (const it of items || []) {
    const gt = soLuongMoi?.[it.name]
    if (gt === undefined) continue
    const so = gt === null || String(gt).trim() === '' ? NaN : Number(gt)
    if (!Number.isFinite(so) || so <= 0) {
      return `${it.item_code || it.name}: số lượng phải lớn hơn 0. `
        + 'Không cần mặt hàng nào nữa thì từ chối báo giá.'
    }
  }
  return ''
}

// Câu báo sau khi quản lý duyệt phiếu (`de_xuat_duyet_phieu`). Phiếu có hàng
// chờ báo giá sinh một YÊU CẦU BÁO GIÁ (`sales_order: null`, `bao_gia: <tên>`),
// không sinh đơn; "Duyệt cả hai" trả thêm kết quả của phiếu kia trong
// `phieu_cung_lan_dat`. Câu báo đếm đúng thứ vừa sinh ra — không biết sinh ra
// gì thì không khẳng định gì.
export function thongBaoSauDuyet(kq) {
  const kia = kq?.phieu_cung_lan_dat || null
  const ds = [kq, kia].filter(Boolean)
  const soDon = ds.filter((k) => k.sales_order).length
  const soBaoGia = ds.filter((k) => !k.sales_order && k.bao_gia).length
  if (!kia) {
    if (soDon) return 'Đã duyệt phiếu — đơn hàng đã được tạo.'
    if (soBaoGia) return 'Đã duyệt phiếu — yêu cầu báo giá đã gửi cho Miyano.'
    return 'Đã duyệt phiếu.'
  }
  const phan = []
  if (soDon) phan.push(`${soDon} đơn hàng đã được tạo`)
  if (soBaoGia) phan.push(`${soBaoGia} yêu cầu báo giá đã gửi cho Miyano`)
  return phan.length ? `Đã duyệt cả hai phiếu — ${phan.join(' và ')}.` : 'Đã duyệt cả hai phiếu.'
}
