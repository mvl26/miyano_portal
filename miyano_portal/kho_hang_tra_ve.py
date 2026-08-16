"""Kho "Hàng trả về" — nơi hàng khách trả về được ghi sổ, TÁCH khỏi tồn bán được.

Quyết định chủ đầu tư 2026-08-16. Trước bản này `make_return_doc` chép nguyên
kho của dòng gốc, nên một bơm tiêm gãy kim khách trả về đi thẳng vào
"Kho Miyano - MYN" và lại bán được cho bệnh viện tiếp theo. Với vật tư y tế đó
không phải một chi tiết kế toán.

Nằm ở module thường (không phải trong `patches/`) vì `dam_bao_kho()` được gọi
LÚC CHẠY: một công ty lập SAU khi patch đã chạy vẫn phải có kho, và một phiếu
trả hàng không được hỏng chỉ vì thứ tự cài đặt.
"""

import frappe

TEN_KHO = "Hàng trả về"


def dam_bao_kho(company: str) -> str | None:
	"""Tên kho "Hàng trả về" của một công ty, tạo nếu chưa có. None nếu công
	ty đó chưa có cây kho nào (chưa dùng tới) — không dựng một cây kho mà
	không ai yêu cầu."""
	if not company:
		return None
	abbr = frappe.db.get_value("Company", company, "abbr")
	if not abbr:
		return None
	ten = f"{TEN_KHO} - {abbr}"
	if frappe.db.exists("Warehouse", ten):
		return ten

	# Kho cha = nhóm gốc của công ty. KHÔNG hardcode "All Warehouses - <abbr>":
	# tên nhóm gốc do ERPNext sinh theo ngôn ngữ/cấu hình lúc lập công ty.
	parent = frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 1, "parent_warehouse": ["is", "not set"]},
		"name",
	) or frappe.db.get_value("Warehouse", {"company": company, "is_group": 1}, "name")
	if not parent:
		return None

	frappe.get_doc({
		"doctype": "Warehouse",
		"warehouse_name": TEN_KHO,
		"company": company,
		"parent_warehouse": parent,
		"is_group": 0,
	}).insert(ignore_permissions=True)
	return ten


def dam_bao_moi_cong_ty() -> list[str]:
	return [
		ten for ten in (dam_bao_kho(c) for c in frappe.get_all("Company", pluck="name"))
		if ten
	]
