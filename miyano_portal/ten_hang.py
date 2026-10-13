"""Tên hiển thị của mặt hàng trên cổng khách hàng — MỘT nguồn cho mọi bảng.

Quy tắc hiển thị (chủ đầu tư 13/10/2026), áp cho cổng, Desk, mẫu in và email:

* Thứ tự cố định: Mã → Tên mặt hàng → Tên thường gọi.
* Tên mặt hàng là `item_name` — tên XUẤT HOÁ ĐƠN. Không nơi nào cắt tên; ô
  hiển thị tự xuống dòng.
* Tên thường gọi (`Item.custom_ten_thuong_goi`, patch v1_39) là của TỪNG khách:
  chỉ các dòng có `customer` = khách đang xem. Chỉ hiện trên cổng — chứng từ
  in và Desk dùng tên xuất hoá đơn.

Mọi bảng mặt hàng của cổng hỏi `thong_tin_ten_hang()` (qua endpoint
`api/hang_hoa.portal_ten_hang`, hoặc thẳng như `portal_catalog_gop`) thay vì
mỗi payload tự mang một bản tên thường gọi — năm màn năm bản sao là năm chỗ
để quên lọc theo khách.
"""

import frappe

# Một màn của cổng không bao giờ có tới ngần này dòng hàng; chặn để một lời gọi
# tự chế không biến endpoint thành đường dò toàn bộ danh mục trong một phát.
SO_MA_TOI_DA = 500


def ten_thuong_goi_theo_ma(customer: str, item_codes) -> dict[str, list[str]]:
	"""`{item_code: [tên thường gọi của CHÍNH khách này, theo thứ tự nhập]}`.

	Mã không có tên thường gọi vắng mặt trong dict. Một truy vấn cho cả danh
	sách mã.
	"""
	ma = [m for m in dict.fromkeys(item_codes or []) if m]
	# Site chưa chạy patch v1_39 thì chưa có bảng — coi như chưa ai đặt tên.
	if not (customer and ma) or not frappe.db.table_exists("Item Ten Thuong Goi"):
		return {}
	out: dict[str, list[str]] = {}
	for t in frappe.get_all(
		"Item Ten Thuong Goi",
		filters={"parenttype": "Item", "customer": customer, "parent": ["in", ma]},
		fields=["parent", "ten_thuong_goi"], order_by="parent asc, idx asc",
	):
		out.setdefault(t.parent, []).append(t.ten_thuong_goi)
	return out


def thong_tin_ten_hang(customer: str, item_codes) -> dict[str, dict]:
	"""`{item_code: {"item_name": tên xuất hoá đơn, "ten_thuong_goi": [...]}}`.

	Chỉ các mã CÓ THẬT trong `Item`; mã lạ và mã rỗng bị bỏ qua lặng lẽ (một
	dòng hàng cũ trỏ vào mã đã xoá không được làm hỏng cả bảng).
	"""
	ma = [m for m in dict.fromkeys(item_codes or []) if m]
	if not ma:
		return {}
	ten = dict(frappe.get_all(
		"Item", filters={"name": ["in", ma]}, fields=["name", "item_name"], as_list=True,
	))
	goi = ten_thuong_goi_theo_ma(customer, list(ten))
	return {
		m: {"item_name": ten[m], "ten_thuong_goi": goi.get(m, [])}
		for m in ma if m in ten
	}
