"""Report desk "Chất lượng dữ liệu kho khách" — US-E3.6 (Phần B của E3) +
US-E5.5 (E5, mở rộng NL-9.3).

(M5, E3 phần B review: đổi tên từ "Chất lượng dữ liệu" — tên Report
DOCNAME DUY NHẤT TOÀN SITE across mọi app, một tên chung chung như vậy dễ
đụng report của app khác trong tương lai.)

E5 (US-E5.5) MỞ RỘNG report này thêm HAI khía cạnh chất lượng dữ liệu qua
bộ lọc `loai_van_de`, thay vì tạo report thứ hai trùng mục đích:

  * (mặc định, không chọn) — Item thiếu lô/hạn (US-E3.6, giữ NGUYÊN hành vi
    cũ, cột cũ) — liệt kê các Item của Miyano đang sinh ra dòng
    `thieu_lo_han=1` trên phiếu nhập kho khách hàng (NL-3.7: lô rơi về
    `KHONG-LO` vì Item chưa bật `Has Batch No`/`Has Expiry Date`).
  * `loai_van_de="kho_khong_hoat_dong"` — kho không có phiếu xuất N ngày
    (NL-9.3): dữ liệu xấu (khách không cập nhật phiếu xuất) làm dự trù (E5)
    sai theo.
  * `loai_van_de="thieu_chung_tu"` — phiếu nhập "Mua ngoài" thiếu số chứng
    từ NCC (E4, BR-N2).

Ba khía cạnh có ĐƠN VỊ PHÂN TÍCH khác nhau (Item / Kho / Phiếu) nên giữ BA
bộ cột riêng thay vì gộp cưỡng ép vào một bộ cột chung đầy ô rỗng chéo
nhau — `execute()` trả cột KHÁC NHAU tuỳ `loai_van_de`, một khả năng chuẩn
của Frappe Script Report.

Toàn bộ số học sống ở `miyano_portal.kho.desk_reports.chat_luong_du_lieu_rows()`
(dispatcher) và ba hàm `_thieu_lo_han_rows()`/`_kho_khong_hoat_dong_rows()`/
`_thieu_chung_tu_rows()`.

Quyền hạn: cùng khuôn với `đối_soát_giao_nhận.py` — `ref_doctype=Customer
Stock Receipt`, `roles=System Manager/Sales Manager/Sales User`, KHÔNG có
role `Customer`.
"""

import frappe

from miyano_portal.kho import desk_reports

COLUMNS_THIEU_LO_HAN = [
	{"label": "Mã Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
	{"label": "Tên Item", "fieldname": "item_name", "fieldtype": "Data", "width": 240},
	{"label": "Đã bật Has Batch No", "fieldname": "has_batch_no", "fieldtype": "Check", "width": 130},
	{"label": "Đã bật Has Expiry Date", "fieldname": "has_expiry_date", "fieldtype": "Check", "width": 140},
	{"label": "Số dòng thiếu lô/hạn", "fieldname": "so_dong_thieu", "fieldtype": "Int", "width": 130},
	{"label": "Số khách bị ảnh hưởng", "fieldname": "so_khach_anh_huong", "fieldtype": "Int", "width": 130},
	{"label": "Lần gần nhất", "fieldname": "lan_gan_nhat", "fieldtype": "Date", "width": 110},
]

COLUMNS_KHO_KHONG_HOAT_DONG = [
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
	{"label": "Kho", "fieldname": "ten_kho", "fieldtype": "Data", "width": 180},
	{"label": "Xuất gần nhất", "fieldname": "ngay_xuat_gan_nhat", "fieldtype": "Date", "width": 120},
	{"label": "Số ngày không xuất", "fieldname": "so_ngay_khong_xuat", "fieldtype": "Int", "width": 140},
]

COLUMNS_THIEU_CHUNG_TU = [
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
	{"label": "Kho", "fieldname": "ten_kho", "fieldtype": "Data", "width": 160},
	{"label": "Phiếu nhập", "fieldname": "phieu_nhap", "fieldtype": "Link", "options": "Customer Stock Receipt", "width": 130},
	{"label": "Ngày", "fieldname": "ngay", "fieldtype": "Date", "width": 100},
	{"label": "NCC", "fieldname": "ncc", "fieldtype": "Data", "width": 160},
	{"label": "Trạng thái phiếu", "fieldname": "trang_thai_phieu", "fieldtype": "Data", "width": 130},
]

# Nhãn tiếng Việt hiển thị trên ô chọn (.js) -> mã ổn định dùng nội bộ
# (desk_reports.chat_luong_du_lieu_rows()) — dịch tại RANH GIỚI UI, không
# để nhãn có dấu lọt vào logic so sánh nội bộ.
_MA_THEO_NHAN = {
	"Kho không hoạt động": "kho_khong_hoat_dong",
	"Phiếu thiếu chứng từ NCC": "thieu_chung_tu",
}
_COLUMNS_THEO_MA = {
	"kho_khong_hoat_dong": COLUMNS_KHO_KHONG_HOAT_DONG,
	"thieu_chung_tu": COLUMNS_THIEU_CHUNG_TU,
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	loai_van_de = _MA_THEO_NHAN.get(filters.get("loai_van_de") or "")

	raw = filters.get("chi_chua_bat_co")
	# Mặc định BẬT khi field vắng mặt (None/"" — ô Check chưa từng đổi giá
	# trị trong URL deep-link); có mặt thì cint() trước khi dùng, KHÔNG so
	# truthy thô — một filter gửi "0" (chuỗi) là truthy trong Python, sẽ
	# BẬT nhầm bộ lọc dù người dùng đang để ô Check TẮT.
	chi_chua_bat_co = True if raw in (None, "") else bool(frappe.utils.cint(raw))

	data = desk_reports.chat_luong_du_lieu_rows(
		customer=filters.get("customer") or None,
		chi_chua_bat_co=chi_chua_bat_co,
		loai_van_de=loai_van_de,
		# Chỉ có ý nghĩa cho "Kho không hoạt động" — desk_reports bỏ qua ở
		# hai khía cạnh còn lại, không cần kiểm loai_van_de ở đây.
		so_ngay=filters.get("so_ngay") or None,
	)
	columns = _COLUMNS_THEO_MA.get(loai_van_de, COLUMNS_THIEU_LO_HAN)
	return columns, data
