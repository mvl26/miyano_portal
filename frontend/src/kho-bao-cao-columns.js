// Định nghĩa cột của ba báo cáo kho — NGUỒN DUY NHẤT cho tiêu đề VÀ thứ tự cột
// của bảng trong BaoCaoNXT.vue (component đọc `field` để lấy giá trị, `label`
// để in tiêu đề — không có nơi nào khác hardcode lại danh sách này).
//
// PHẢI khớp TỪNG CHỮ, ĐÚNG THỨ TỰ với các mảng COLUMNS tương ứng trong
// `miyano_portal/kho/reports.py` (NXT_COLUMNS, NXT_LOT_COLUMNS,
// THE_KHO_COLUMNS, CANH_BAO_COLUMNS) — CẢ nhãn lẫn field. Backend
// test_kho_reports.py đọc lại chính file này (bằng regex trên các đối tượng
// {label, field} bên dưới) để khẳng định "cột xuất Excel khớp cột màn hình"
// không lệch sau một lần sửa cột ở một trong hai phía. Đổi cột ở một bên mà
// quên đổi bên kia sẽ làm test đó đỏ ngay.

export const NXT_COLUMNS = [
  { label: 'Mã vật tư', field: 'ma_vat_tu' },
  { label: 'Tên vật tư', field: 'ten_vat_tu' },
  { label: 'ĐVT', field: 'dvt' },
  { label: 'Tồn đầu - SL', field: 'ton_dau_sl' },
  { label: 'Tồn đầu - Thành tiền', field: 'ton_dau_tt' },
  { label: 'Nhập - SL', field: 'nhap_sl' },
  { label: 'Nhập - Thành tiền', field: 'nhap_tt' },
  { label: 'Xuất - SL', field: 'xuat_sl' },
  { label: 'Xuất - Thành tiền', field: 'xuat_tt' },
  { label: 'Tồn cuối - SL', field: 'ton_cuoi_sl' },
  { label: 'Tồn cuối - Thành tiền', field: 'ton_cuoi_tt' },
]

export const NXT_LOT_COLUMNS = [
  { label: 'Số lô', field: 'so_lo' },
  { label: 'Hạn sử dụng', field: 'han_su_dung' },
  { label: 'Tồn đầu - SL', field: 'ton_dau_sl' },
  { label: 'Tồn đầu - Thành tiền', field: 'ton_dau_tt' },
  { label: 'Nhập - SL', field: 'nhap_sl' },
  { label: 'Nhập - Thành tiền', field: 'nhap_tt' },
  { label: 'Xuất - SL', field: 'xuat_sl' },
  { label: 'Xuất - Thành tiền', field: 'xuat_tt' },
  { label: 'Tồn cuối - SL', field: 'ton_cuoi_sl' },
  { label: 'Tồn cuối - Thành tiền', field: 'ton_cuoi_tt' },
]

export const THE_KHO_COLUMNS = [
  { label: 'Ngày', field: 'ngay' },
  { label: 'Số chứng từ', field: 'chung_tu' },
  { label: 'Loại chứng từ', field: 'loai_chung_tu' },
  { label: 'Đối tác / Nơi nhận', field: 'doi_tac' },
  { label: 'Số lô', field: 'so_lo' },
  { label: 'SL nhập', field: 'sl_nhap' },
  { label: 'SL xuất', field: 'sl_xuat' },
  { label: 'Tồn luỹ kế', field: 'ton_luy_ke' },
]

export const CANH_BAO_COLUMNS = [
  { label: 'Mã vật tư', field: 'ma_vat_tu' },
  { label: 'Tên vật tư', field: 'ten_vat_tu' },
  { label: 'ĐVT', field: 'dvt' },
  { label: 'Số lô', field: 'so_lo' },
  { label: 'Hạn sử dụng', field: 'han_su_dung' },
  { label: 'Số ngày còn lại', field: 'so_ngay_con_lai' },
  { label: 'Số lượng tồn', field: 'so_luong' },
  { label: 'Trạng thái', field: 'trang_thai' },
]

// Gap 2 (review E4 phần B): hai bộ cột còn thiếu cho xuất Excel của Nhật ký
// vật tư và NXT theo đợt hàng — PHẢI khớp reports.NHAT_KY_COLUMNS/DOT_COLUMNS.
export const NHAT_KY_COLUMNS = [
  { label: 'Ngày', field: 'ngay' },
  { label: 'Số phiếu', field: 'phieu' },
  { label: 'Loại', field: 'loai' },
  { label: 'Nguồn / NCC', field: 'nguon' },
  { label: 'Đợt', field: 'dot' },
  { label: 'Lô', field: 'lo' },
  { label: 'Hạn dùng', field: 'han' },
  { label: 'SL nhập', field: 'sl_nhap' },
  { label: 'SL xuất', field: 'sl_xuat' },
  { label: 'Đơn giá', field: 'don_gia' },
  { label: 'Tồn sau giao dịch', field: 'ton_sau' },
  { label: 'Người ghi sổ', field: 'nguoi_ghi_so' },
]

// Yêu cầu chủ đầu tư 2026-08-17 — cấp phát gộp theo tháng × khoa phòng. PHẢI
// khớp reports.CAP_PHAT_THANG_COLUMNS. Bảng trên màn hình hiện dữ liệu này ở
// dạng NHÓM (dòng tiêu đề khoa+tháng, rồi các dòng vật tư), còn file Excel bẻ
// phẳng thành từng dòng vật tư — cùng con số, cùng bộ cột, khác cách xếp.
export const CAP_PHAT_THANG_COLUMNS = [
  { label: 'Khoa phòng', field: 'ten_khoa_phong' },
  { label: 'Tháng', field: 'nhan_thang' },
  { label: 'Vật tư', field: 'vat_tu' },
  { label: 'ĐVT', field: 'dvt' },
  { label: 'SL cấp phát', field: 'sl' },
  { label: 'Giá trị', field: 'gia_tri' },
  { label: 'Số phiếu', field: 'so_phieu' },
]

// Task 14 — bộ cột PHẲNG (Excel) của báo cáo "Vật tư · Máy · Khoa phòng",
// PHẢI khớp reports.THIET_BI_COLUMNS (task 9/10 dựng hàm tính + nối Excel,
// task 14 mới dựng UI để có nhãn màn hình đối chiếu — xem docstring
// reports.bao_cao_thiet_bi_flat_rows()). KHÔNG PHẢI bộ cột của bảng NGOÀI
// (9 cột, gộp theo vật tư) hay bảng CON mở rộng (5 cột, theo máy) của màn
// BaoCaoThietBi.vue — hai bộ đó có tên riêng ngay dưới, không dùng chung
// tên này dù cùng chủ đề, để không phá quy ước "một export = một mảng
// COLUMNS Python cụ thể" mà test_kho_reports.py dựa vào.
export const THIET_BI_COLUMNS = [
  { label: 'Vật tư', field: 'vat_tu' },
  { label: 'Mã vật tư', field: 'ma_vat_tu' },
  { label: 'ĐVT', field: 'dvt' },
  { label: 'Máy', field: 'ten_may' },
  { label: 'Khoa phòng', field: 'ten_khoa' },
  { label: 'SL cấp phát', field: 'sl' },
  { label: 'Giá trị', field: 'gia_tri' },
]

// Bảng NGOÀI của màn BaoCaoThietBi.vue (task 14) — mỗi dòng một vật tư
// (backend: kho_bao_cao_thiet_bi → reports.bao_cao_thiet_bi_rows().dong).
// Không đối chiếu với cột Python nào (đây là bảng MÀN HÌNH, không phải
// Excel) — field 'ma_vat_tu'/'vat_tu'/'dvt' vẫn khớp tên khoá backend để
// component đọc thẳng, nhưng 'may_su_dung' là cột TỰ TÍNH ở client (đếm
// theo_may), không phải khoá trả về từ server.
export const BAO_CAO_THIET_BI_COLUMNS = [
  { label: 'Mã VT', field: 'ma_vat_tu' },
  { label: 'Tên vật tư', field: 'vat_tu' },
  { label: 'ĐVT', field: 'dvt' },
  { label: 'Tồn đầu', field: 'ton_dau' },
  { label: 'Đã nhập', field: 'nhap' },
  { label: 'Đã cấp phát', field: 'cap_phat' },
  { label: 'Xuất khác', field: 'xuat_khac' },
  { label: 'Tồn cuối', field: 'ton_cuoi' },
  { label: 'Máy sử dụng', field: 'may_su_dung' },
]

// Bảng CON (mở rộng một dòng vật tư của bảng trên) — theo máy, khoá đúng
// `theo_may[*]` mà backend trả.
export const BAO_CAO_THIET_BI_MAY_COLUMNS = [
  { label: 'Máy', field: 'ten_may' },
  { label: 'Khoa phòng', field: 'ten_khoa' },
  { label: 'SL xuất', field: 'sl' },
  { label: 'Giá trị', field: 'gia_tri' },
  { label: '%', field: 'pct' },
]

export const DOT_COLUMNS = [
  { label: 'Đợt (phiếu nhập)', field: 'dot' },
  { label: 'Ngày nhận', field: 'ngay_nhan' },
  { label: 'Nguồn / NCC', field: 'nguon' },
  { label: 'Chứng từ', field: 'chung_tu' },
  { label: 'Vật tư', field: 'vat_tu' },
  { label: 'Lô', field: 'lo' },
  { label: 'Hạn dùng', field: 'han_su_dung' },
  { label: 'SL nhập', field: 'sl_nhap' },
  { label: 'Giá trị nhập', field: 'gia_tri_nhap' },
  { label: 'Đã xuất', field: 'da_xuat' },
  { label: 'Còn lại', field: 'con_lai' },
  { label: 'Tuổi tồn (ngày)', field: 'tuoi_ton_ngay' },
  { label: '% tiêu thụ', field: 'pct_tieu_thu' },
  { label: 'Chậm luân chuyển', field: 'cham_luan_chuyen' },
]
