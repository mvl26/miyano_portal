"""Dữ liệu kho tối thiểu cho test và demo.

Idempotent: gọi bao nhiêu lần cũng ra cùng kết quả, giống seed_demo.py sẵn có.
Dựa vào các Customer do miyano_portal.setup.seed_demo tạo ra.
"""

import frappe
from miyano_portal.setup.seed_demo import seed_demo

KHO_DEMO = [
	{"customer": "Bệnh viện Bạch Mai", "ten_kho": "Kho Khoa Dược", "ma_kho": "BM"},
	{"customer": "PXN ABC", "ten_kho": "Kho vật tư PXN", "ma_kho": "PXN"},
]


def _ensure_kho(customer: str, ten_kho: str, ma_kho: str) -> str:
	existing = frappe.db.get_value("Customer Warehouse", {"customer": customer}, "name")
	if existing:
		return existing
	doc = frappe.get_doc({
		"doctype": "Customer Warehouse",
		"customer": customer,
		"ten_kho": ten_kho,
		"ma_kho": ma_kho,
		"thu_kho": "Nguyễn Thị Thủ Kho",
		"ngay_bat_dau": "2026-01-01",
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def seed_kho_demo() -> dict:
	seed_demo()
	names = {}
	for row in KHO_DEMO:
		names[row["customer"]] = _ensure_kho(
			row["customer"], row["ten_kho"], row["ma_kho"]
		)
	# KHÔNG gọi frappe.db.commit() ở đây. seed_demo.py sẵn có cũng không gọi,
	# và tám test file hiện tại đều seed trong setUp: commit sẽ phá rollback
	# của FrappeTestCase và ghi rác vĩnh viễn vào site.
	return {
		"kho_bm": names["Bệnh viện Bạch Mai"],
		"kho_pxn": names["PXN ABC"],
	}
