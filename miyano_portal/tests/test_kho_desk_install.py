"""Cài đặt ba Report + Workspace của Phase 6 — idempotent, đúng role, đúng
ref_doctype. Số liệu/hành vi báo cáo đã có test riêng ở test_kho_desk_reports.py;
file này chỉ khoá cấu hình cài đặt (dễ vỡ âm thầm nếu ai đó sửa
install_kho_desk_reports.py/install_kho_workspace.py mà không chạy lại test)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.setup.install_kho_desk_reports import REPORTS, STAFF_ROLES, install_kho_desk_reports
from miyano_portal.setup.install_kho_workspace import TITLE as WORKSPACE_TITLE, install_kho_workspace


class TestKhoDeskReportInstall(FrappeTestCase):
	def test_installs_idempotently_with_correct_ref_doctype_and_roles(self):
		install_kho_desk_reports()
		install_kho_desk_reports()  # phải không lỗi, không tạo trùng

		for spec in REPORTS:
			doc = frappe.get_doc("Report", spec["report_name"])
			self.assertEqual(doc.ref_doctype, spec["ref_doctype"])
			self.assertEqual(doc.report_type, "Script Report")
			self.assertEqual(doc.is_standard, "Yes")
			self.assertEqual(doc.disable_prepared_report_automation, 1)
			roles = {r.role for r in doc.roles}
			self.assertEqual(roles, set(STAFF_ROLES))
			self.assertNotIn("Customer", roles, "role Customer không bao giờ được có mặt ở đây")
			self.assertEqual(
				frappe.db.count("Report", {"report_name": spec["report_name"]}), 1,
				"gọi install hai lần không được tạo bản ghi Report thứ hai",
			)

	def test_no_doctype_has_customer_report_permission(self):
		"""Chốt chặn thật của ba report này: `ref_doctype` không có DocPerm
		nào cho role Customer — nếu ai đó lỡ cấp lại (xem lịch sử bốn vòng vá
		trong kho/permissions.py), test này đỏ trước khi kịp ship.

		Đọc THẲNG `tabDocPerm` sau khi CLEAR CACHE, không dùng `frappe.get_meta()`
		(cache theo tiến trình): một DocPerm bị cấp lại trong DB nhưng meta
		cache của tiến trình test còn giữ bản cũ sẽ khiến bài test này XANH
		SAI — đã tận mắt gặp trong lúc dựng file này (xem p6-desk-report.md,
		"Sự cố mất dữ liệu": has_permission() trả True thật trong khi
		frappe.get_meta() ở một tiến trình khác vẫn báo sạch)."""
		install_kho_desk_reports()
		ref_doctypes = {spec["ref_doctype"] for spec in REPORTS}
		for dt in ref_doctypes:
			frappe.clear_cache(doctype=dt)
			roles_with_perm = set(frappe.get_all("DocPerm", filters={"parent": dt}, pluck="role"))
			self.assertNotIn("Customer", roles_with_perm, msg=f"doctype: {dt}")


class TestKhoWorkspaceInstall(FrappeTestCase):
	def test_installs_idempotently_with_report_and_doctype_shortcuts(self):
		# Workspace Shortcut kiểu "Report" là Dynamic Link tới doctype Report
		# thật — ba report phải tồn tại trước, đúng thứ tự trong patches.txt.
		install_kho_desk_reports()
		install_kho_workspace()
		install_kho_workspace()  # phải không lỗi, không tạo trùng

		self.assertEqual(frappe.db.count("Workspace", {"title": WORKSPACE_TITLE}), 1)
		ws = frappe.get_doc("Workspace", WORKSPACE_TITLE)
		self.assertEqual(ws.public, 1)
		self.assertEqual(ws.module, "Miyano Portal")

		shortcut_types = {(s.type, s.link_to) for s in ws.shortcuts}
		for report_name in (
			"Tồn kho khách hàng", "Nhập-Xuất-Tồn khách hàng", "Cảnh báo hạn dùng khách hàng",
		):
			self.assertIn(("Report", report_name), shortcut_types)
		for doctype in (
			"Customer Warehouse", "Customer Warehouse Item", "Customer Stock Receipt",
			"Customer Stock Issue", "Customer Stock Ledger Entry", "Customer Stock Lot Balance",
		):
			self.assertIn(("DocType", doctype), shortcut_types)
		# Task 15 — màn Desk nhập nhân sự phải CÓ LỐI VÀO. Đường duy nhất
		# trước đó là gõ tay tên trang vào thanh tìm kiếm, tức là không ai
		# ngoài người viết code biết nó tồn tại.
		self.assertIn(("Page", "nhap-nhan-su"), shortcut_types)

		roles = {r.role for r in ws.roles}
		self.assertEqual(roles, {"System Manager", "Sales Manager", "Sales User"})
