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


VAT_TU_DEMO = [
	{
		"key": "vt_bm", "kho_key": "kho_bm", "ma_vat_tu": "MYN-GLOVE-M",
		"ten_vat_tu": "Găng tay y tế size M", "dvt": "Hộp",
		"item_code": "MYN-GLOVE-M",
	},
	{
		"key": "vt_rieng_bm", "kho_key": "kho_bm", "ma_vat_tu": "BM-GAC-01",
		"ten_vat_tu": "Gạc y tế mua ngoài", "dvt": "Cái", "item_code": None,
	},
	{
		"key": "vt_pxn", "kho_key": "kho_pxn", "ma_vat_tu": "MYN-SYR-10",
		"ten_vat_tu": "Bơm tiêm 10ml", "dvt": "Cái", "item_code": "MYN-SYR-10",
	},
]


def _ensure_vat_tu(kho: str, row: dict) -> str:
	existing = frappe.db.get_value(
		"Customer Warehouse Item", {"kho": kho, "ma_vat_tu": row["ma_vat_tu"]}, "name"
	)
	if existing:
		return existing
	# item_code chỉ set khi Item đó thật sự tồn tại trên site, để seed không vỡ
	# khi chạy trên database chưa có catalog Miyano.
	item_code = row["item_code"]
	if item_code and not frappe.db.exists("Item", item_code):
		item_code = None
	doc = frappe.get_doc({
		"doctype": "Customer Warehouse Item",
		"kho": kho,
		"ma_vat_tu": row["ma_vat_tu"],
		"ten_vat_tu": row["ten_vat_tu"],
		"dvt": row["dvt"],
		"item_code": item_code,
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
	out = {
		"kho_bm": names["Bệnh viện Bạch Mai"],
		"kho_pxn": names["PXN ABC"],
	}
	for row in VAT_TU_DEMO:
		out[row["key"]] = _ensure_vat_tu(out[row["kho_key"]], row)
	return out
