"""Workspace desk "Kho khách hàng" — Phase 6: một chỗ duy nhất để nhân viên
Miyano vào ba báo cáo kho khách hàng và sáu doctype kho, thay vì phải nhớ tên
từng cái. Cài idempotent qua setup module + patch, đúng khuôn các file
install_kho_*.py khác trong thư mục này.

Nhãn hiển thị của sáu shortcut doctype dùng lại ĐÚNG tên tiếng Việt trong
thiết kế gốc (§3.1-3.6 của kho-khach-hang-design.md) — bản thân doctype vẫn
giữ tên tiếng Anh (Customer Warehouse, ...) để tránh định danh module Python
có dấu tiếng Việt (xem lý do đã bàn khi đặt tên thư mục report/), nhưng nhân
viên nhìn thấy đúng cái tên hộ khách hàng gọi.
"""

import frappe

TITLE = "Kho khách hàng"

_REPORT_SHORTCUTS = [
	("Tồn kho khách hàng", "yellow"),
	("Nhập-Xuất-Tồn khách hàng", "blue"),
	("Cảnh báo hạn dùng khách hàng", "red"),
]

# (doctype thật, nhãn tiếng Việt hiển thị — đúng tên trong thiết kế gốc §3)
_DOCTYPE_SHORTCUTS = [
	("Customer Warehouse", "Kho Khách Hàng"),
	("Customer Warehouse Item", "Vật Tư Kho Khách"),
	("Customer Stock Receipt", "Phiếu Nhập Kho"),
	("Customer Stock Issue", "Phiếu Xuất Kho"),
	("Customer Stock Ledger Entry", "Sổ Kho Khách"),
	("Customer Stock Lot Balance", "Tồn Theo Lô"),
]


def _block(block_id: str, block_type: str, data: dict) -> dict:
	return {"id": block_id, "type": block_type, "data": data}


def _build_content_and_shortcuts():
	content = [_block("hdr-kho-khach-hang", "header", {
		"text": f'<span class="h4">{TITLE}</span>', "col": 12,
	})]
	shortcuts = []

	content.append(_block("hdr-bao-cao", "header", {
		"text": '<span class="h5">Báo cáo</span>', "col": 12,
	}))
	for idx, (label, color) in enumerate(_REPORT_SHORTCUTS):
		content.append(_block(f"sc-report-{idx}", "shortcut", {"shortcut_name": label, "col": 4}))
		shortcuts.append({"type": "Report", "label": label, "link_to": label, "color": color})

	content.append(_block("hdr-danh-muc", "header", {
		"text": '<span class="h5">Danh mục</span>', "col": 12,
	}))
	for idx, (doctype, label) in enumerate(_DOCTYPE_SHORTCUTS):
		content.append(_block(f"sc-doctype-{idx}", "shortcut", {"shortcut_name": label, "col": 4}))
		shortcuts.append({"type": "DocType", "label": label, "link_to": doctype})

	return content, shortcuts


def install_kho_workspace():
	if frappe.db.exists("Workspace", TITLE):
		return
	content, shortcuts = _build_content_and_shortcuts()
	frappe.get_doc({
		"doctype": "Workspace",
		"label": TITLE,
		"title": TITLE,
		"module": "Miyano Portal",
		"public": 1,
		"icon": "stock",
		"content": frappe.as_json(content),
		"shortcuts": shortcuts,
		"roles": [
			{"role": "System Manager"},
			{"role": "Sales Manager"},
			{"role": "Sales User"},
		],
	}).insert(ignore_permissions=True)
