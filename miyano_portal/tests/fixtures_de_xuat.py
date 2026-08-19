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
