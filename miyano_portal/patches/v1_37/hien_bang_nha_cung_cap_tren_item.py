"""Bảng NHÀ CUNG CẤP của Item — dùng lại `Item.supplier_items` sẵn có.

Chủ đầu tư 28/09/2026: *"trong item em cũng thêm cho anh 1 table trong đó
chứa nhiều nhà cung cấp mà có thể cung cấp item đó"*, và màn `/portal/
dat-hang` lọc hàng theo nhà cung cấp.

VÌ SAO KHÔNG tạo bảng con mới: ERPNext đã có ĐÚNG bảng này — `supplier_items`
(bảng con `Item Supplier`: nhà cung cấp + mã hàng bên NCC, nhiều dòng mỗi
item), nằm ở tab Purchasing. Một bảng thứ hai cùng nghĩa sớm muộn sẽ lệch với
bảng gốc mà ERPNext tự đọc (vd. giao thẳng từ NCC). Patch này CHỈ đổi nhãn
sang tiếng Việt và mở sẵn phần (mặc định bị gập) để người nhập nhìn thấy.
"""

from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	for field, prop, value, kieu in (
		("supplier_details", "label", "Nhà cung cấp", "Data"),
		("supplier_details", "collapsible", "0", "Check"),
		("supplier_items", "label", "Nhà cung cấp có thể cung cấp mặt hàng này", "Data"),
	):
		make_property_setter("Item", field, prop, value, kieu, validate_fields_for_doctype=False)
