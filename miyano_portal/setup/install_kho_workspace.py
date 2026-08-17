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
	# Yêu cầu chủ đầu tư 2026-08-17 — báo cáo cấp phát gộp theo tháng × khoa
	# phòng. Có shortcut ngay từ đầu vì đây là con số nhân viên phải mở HÀNG
	# THÁNG khi đối chiếu với bệnh viện; bốn report kho còn lại (đối soát, chất
	# lượng dữ liệu, tiêu thụ, tỷ trọng, cấp phát mức dòng) vẫn vào qua menu
	# Report — chúng phục vụ việc tra cứu theo tình huống, không theo kỳ.
	("Cấp phát theo tháng và khoa phòng", "green"),
]

# Cổng khách hàng — việc do KHÁCH đẩy sang, nhân viên phải thấy được hàng chờ.
#
# Trước 16/08/2026 hai doctype này KHÔNG nằm trong workspace nào, không
# shortcut, không thẻ đếm: đường vào duy nhất là thông báo (mất rồi thì thôi)
# hoặc gõ tay tên doctype vào thanh tìm kiếm. Một hàng đợi mà không có chỗ nào
# nhìn thấy nó thì không phải hàng đợi.
#
# `stats_filter` cho ra CON SỐ ngay trên shortcut — nhân viên mở Desk là biết
# còn mấy việc, không phải bấm vào mới biết. Đó là lý do dùng shortcut có
# filter chứ không phải một link trơn.
_CONG_KHACH_SHORTCUTS = [
	{
		"label": "Biên bản kiểm hàng",
		"link_to": "Portal Delivery Inspection",
		"color": "orange",
		"stats_filter": {"trang_thai": "Chờ xử lý", "docstatus": 1},
	},
	{
		"label": "Yêu cầu hàng hoá",
		"link_to": "Portal Item Request",
		"color": "blue",
		"stats_filter": {"trang_thai": "Mới"},
	},
]

_CONG_KHACH_REPORTS = [
	("Đối soát giao nhận", "red"),
	("Đơn chậm xử lý", "orange"),
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

	content.append(_block("hdr-cong-khach", "header", {
		"text": '<span class="h5">Việc từ cổng khách hàng</span>', "col": 12,
	}))
	for idx, sc in enumerate(_CONG_KHACH_SHORTCUTS):
		content.append(_block(f"sc-cong-{idx}", "shortcut", {"shortcut_name": sc["label"], "col": 4}))
		shortcuts.append({
			"type": "DocType", "label": sc["label"], "link_to": sc["link_to"],
			"color": sc["color"], "stats_filter": frappe.as_json(sc["stats_filter"]),
		})
	for idx, (label, color) in enumerate(_CONG_KHACH_REPORTS):
		content.append(_block(f"sc-cong-rp-{idx}", "shortcut", {"shortcut_name": label, "col": 4}))
		shortcuts.append({"type": "Report", "label": label, "link_to": label, "color": color})

	content.append(_block("hdr-bao-cao", "header", {
		"text": '<span class="h5">Báo cáo kho khách</span>', "col": 12,
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
	"""Idempotent, và CẬP NHẬT được workspace đã tồn tại.

	Bản đầu `return` ngay khi workspace có sẵn, nên mọi shortcut thêm về sau
	không bao giờ tới được site đã cài — đúng cái bẫy đã làm hai doctype cổng
	khách hàng nằm ngoài mọi workspace suốt từ đầu. Giờ ghi đè content +
	shortcuts, giữ nguyên phần còn lại (roles, icon, sắp xếp cá nhân của
	người dùng nằm ở doctype khác nên không bị đụng).
	"""
	content, shortcuts = _build_content_and_shortcuts()
	if frappe.db.exists("Workspace", TITLE):
		doc = frappe.get_doc("Workspace", TITLE)
		doc.content = frappe.as_json(content)
		doc.shortcuts = []
		for sc in shortcuts:
			doc.append("shortcuts", sc)
		doc.flags.ignore_permissions = True
		doc.save()
		return
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
