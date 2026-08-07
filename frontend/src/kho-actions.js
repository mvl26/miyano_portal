// Khai báo hành động theo TRẠNG THÁI THẬT của phiếu nhập/xuất kho — dùng
// chung cho PhieuNhapDetail.vue và PhieuXuatDetail.vue, theo đúng nguyên tắc
// "ẩn hành động không hợp lệ thay vì hiện nút rồi báo lỗi khi bấm":
//   - Nháp (docstatus 0): Sửa (form đã ở chế độ sửa) + Ghi sổ.
//   - Đã ghi sổ (docstatus 1): In; Huỷ CHỈ khi không phải phiếu đảo — backend
//     (block_cancel_of_reversal) ném lỗi vô điều kiện cho phiếu đảo, nên nút
//     Huỷ không bao giờ được hiện cho nó.
//   - Đã huỷ (docstatus 2): chỉ còn In.
//
// Đây là bảng quyết định NGUỒN DUY NHẤT — cả hai màn hình chi tiết đọc từ
// đây thay vì tự suy lại điều kiện, để không lệch nhau khi sửa sau này.
export function phieuActions(doc) {
  if (!doc) return []
  const loai = doc.loai_nhap || doc.loai_xuat || ''
  if (doc.docstatus === 0) {
    return [{ key: 'submit', label: 'Ghi sổ', variant: 'primary' }]
  }
  if (doc.docstatus === 1) {
    const list = [{ key: 'print', label: 'In phiếu', variant: 'secondary' }]
    if (loai !== 'Phiếu đảo') {
      list.push({ key: 'cancel', label: 'Huỷ phiếu', variant: 'danger' })
    }
    return list
  }
  if (doc.docstatus === 2) {
    return [{ key: 'print', label: 'In phiếu', variant: 'secondary' }]
  }
  return []
}

// docstatus -> nhãn + màu badge, khớp với backend (_TRANG_THAI trong kho.py).
export function trangThaiBadge(docstatus) {
  const map = {
    0: { label: 'Nháp', cls: 'b-gray' },
    1: { label: 'Đã ghi sổ', cls: 'b-blue' },
    2: { label: 'Đã huỷ', cls: 'b-red' },
  }
  return map[docstatus] || { label: '', cls: 'b-gray' }
}
