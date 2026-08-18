"""Điền `Customer Department.customer` từ `kho.customer`, và viết hoa `ma_khoa`.

Chạy MỘT LẦN cho mỗi site. Bản ghi nào không suy ra được khách hàng (kho đã
bị xoá) thì KHÔNG đoán — ghi Error Log để vận hành xử tay, vì đoán sai ở đây
là gán một khoa phòng cho nhầm bệnh viện.
"""

import frappe


def execute():
	rows = frappe.get_all(
		"Customer Department", fields=["name", "kho", "customer", "ma_khoa"]
	)
	mo_coi = []
	for r in rows:
		gia_tri = {}
		if not r.customer:
			cust = frappe.db.get_value("Customer Warehouse", r.kho, "customer") if r.kho else None
			if not cust:
				mo_coi.append(r.name)
				continue
			gia_tri["customer"] = cust
		if r.ma_khoa and r.ma_khoa != r.ma_khoa.strip().upper():
			gia_tri["ma_khoa"] = r.ma_khoa.strip().upper()
		if gia_tri:
			frappe.db.set_value("Customer Department", r.name, gia_tri, update_modified=False)

	if mo_coi:
		frappe.log_error(
			title="Khoa phòng không suy ra được khách hàng",
			message=(
				"Các khoa phòng sau không có `kho` hợp lệ để suy ra `customer`, "
				"cần gán tay: " + ", ".join(mo_coi)
			),
		)
