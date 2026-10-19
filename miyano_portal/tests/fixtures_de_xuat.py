"""Fixture dùng chung cho các test đề xuất mua (spec §5, §6).

Tách ra từ `test_de_xuat_doctype.py` (Task 1) để `test_ma_de_xuat.py` (Task 2)
dùng lại đúng một bộ khách/khoa/vật tư thử nghiệm, thay vì mỗi file tự định
nghĩa một bản riêng rồi trôi lệch theo thời gian.

Khách hàng cố định: `_TEST DX A` (Mã ngắn DXA) có khoa Huyết học (HUYETHOC);
`_TEST DX B` (Mã ngắn DXB) có khoa Dược (DUOC).
"""

import frappe


def dung_fixture(case):
	"""Tạo (hoặc tái dùng) khách/khoa/vật tư thử nghiệm, dọn phiếu cũ trước.

	`case` là `TestCase` đang chạy — chỉ để tham số hoá lời gọi giống các
	fixture khác trong app, bản thân hàm không đụng vào nó. Trả về
	`frappe._dict` gồm `kh_a, kh_b, khoa_huyethoc, khoa_duoc, item`.
	"""
	# FrappeTestCase rollback MỘT LẦN cho cả class → dọn phiếu cũ ở đây để
	# các test trong cùng class không thấy phiếu của nhau.
	#
	# GỠ CHỐT `on_trash` bằng SQL thô TRƯỚC khi xoá. `force=True` chỉ bỏ
	# kiểm liên kết, KHÔNG bỏ `on_trash`, và từ 03/09/2026 chốt đó hỏi
	# `ma_de_xuat` chứ không hỏi trạng thái (phiếu thu hồi về Nháp vẫn là
	# phiếu ĐÃ TỪNG gửi — xem `PortalDeXuatMua.on_trash()`). Gộp vào ĐÂY,
	# cùng bộ lọc với vòng xoá ngay dưới, thay vì sửa mười tám hàm dọn rải
	# rác trong `tests/`: chúng đều chạy trước đúng lời gọi này, và mười
	# tám bản sao của cùng một mẹo gỡ chốt là mười tám chỗ để trôi lệch khi
	# chốt đổi lần sau.
	# Yêu cầu báo giá nháp của test trước đi TRƯỚC phiếu (spec 2026-10-12 §5):
	# xoá phiếu mới nhất làm Frappe lùi bộ đếm tên, phiếu của test sau nhận lại
	# đúng tên cũ, và một Quotation còn sống mang `custom_request_id` = tên đó
	# sẽ bị `tao_bao_gia` coi là báo giá của phiếu mới. Cùng bẫy mà các hàm
	# `_don_phieu_cu` đã chặn cho Sales Order; đặt ở đây một lần cho mọi bộ test.
	for ten in frappe.get_all(
		"Quotation", filters={"party_name": ["like", "_TEST DX%"], "docstatus": 0},
		pluck="name",
	):
		# Đợt nháp (báo giá theo đợt) bị hook `chan_xoa_dot` chặn xoá: bỏ hook.
		frappe.delete_doc(
			"Quotation", ten, force=True, ignore_permissions=True,
			ignore_on_trash=bool(frappe.db.get_value("Quotation", ten, "custom_phieu_goc")),
		)
	frappe.db.sql(
		"""UPDATE `tabPortal De Xuat Mua`
		   SET trang_thai = 'Nháp', ma_de_xuat = NULL
		   WHERE customer LIKE '\\_TEST DX%'"""
	)
	for r in frappe.get_all(
		"Portal De Xuat Mua", filters={"customer": ["like", "_TEST DX%"]}
	):
		frappe.delete_doc("Portal De Xuat Mua", r.name, force=True)

	kh_a = _customer("_TEST DX A", "DXA")
	kh_b = _customer("_TEST DX B", "DXB")
	khoa_huyethoc = _khoa(kh_a, "Huyết học", "HUYETHOC")
	khoa_duoc = _khoa(kh_b, "Dược", "DUOC")
	item = _item()

	return frappe._dict(
		kh_a=kh_a,
		kh_b=kh_b,
		khoa_huyethoc=khoa_huyethoc,
		khoa_duoc=khoa_duoc,
		item=item,
	)


BANG_GIA_TEST = "_TEST DX BANG GIA"


def khai_gia(customer, *ma_hang, gia=1000):
	"""Cho các mã `ma_hang` một giá trong Price List của `customer`.

	Spec 2026-10-12 §5 — phiếu / giỏ còn mã chưa có giá nay sinh Quotation chứ
	không sinh Sales Order. Bộ test nào đo NHÁNH ĐƠN của đường duyệt hay đường
	đặt trực tiếp (liên kết ngược, mã đơn, nhật ký, danh sách...) gọi hàm này
	trong `setUp` để hai đường thật vẫn ra đơn "Theo bảng giá". Khách chưa có
	Price List thì nhận `BANG_GIA_TEST`; đã có thì giữ nguyên bảng đó.
	"""
	bang = frappe.db.get_value("Customer", customer, "default_price_list")
	if not bang:
		bang = BANG_GIA_TEST
		if not frappe.db.exists("Price List", bang):
			frappe.get_doc({
				"doctype": "Price List", "price_list_name": bang,
				"currency": "VND", "selling": 1, "enabled": 1,
			}).insert(ignore_permissions=True)
		frappe.db.set_value("Customer", customer, "default_price_list", bang)
	for ma in ma_hang:
		loc = {"item_code": ma, "price_list": bang, "selling": 1}
		if frappe.db.exists("Item Price", loc):
			frappe.db.set_value("Item Price", loc, "price_list_rate", gia)
		else:
			frappe.get_doc({
				"doctype": "Item Price", "price_list_rate": gia, **loc,
			}).insert(ignore_permissions=True)
	return bang


def _customer(ten, ma_ngan):
	if not frappe.db.exists("Customer", ten):
		frappe.get_doc({
			"doctype": "Customer", "customer_name": ten,
			"customer_group": frappe.db.get_value("Customer Group", {}, "name"),
			"territory": frappe.db.get_value("Territory", {}, "name"),
		}).insert(ignore_permissions=True)
	frappe.db.set_value("Customer", ten, "custom_ma_ngan", ma_ngan)
	return ten


def _khoa(customer, ten, ma):
	ten_bp = frappe.db.get_value(
		"Customer Department", {"customer": customer, "ma_khoa": ma}, "name"
	)
	if ten_bp:
		return ten_bp
	return frappe.get_doc({
		"doctype": "Customer Department", "customer": customer,
		"ten_khoa_phong": ten, "ma_khoa": ma, "active": 1,
	}).insert(ignore_permissions=True).name


def _item():
	ten = "_TEST DX ITEM"
	if not frappe.db.exists("Item", ten):
		frappe.get_doc({
			"doctype": "Item", "item_code": ten, "item_name": ten,
			"item_group": frappe.db.get_value("Item Group", {}, "name"),
			"stock_uom": "Nos", "is_stock_item": 0,
		}).insert(ignore_permissions=True)
	return ten
