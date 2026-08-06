import frappe
from frappe.model.document import Document

from miyano_portal.permissions import _is_restricted_user
from miyano_portal.portal_context import get_allowed_khos


class CustomerStockReceiptItem(Document):
	def has_permission(self, permtype="read", *, debug=False, user=None):
		"""Ghi đè has_permission() ở mức CLASS, không dựa vào hook.

		`frappe.permissions.has_child_permission()` không kiểm được theo TỪNG
		DÒNG cho bảng con (istable=1): nó suy ra parent_doctype rồi kiểm quyền
		trên PARENT thay vì trên chính dòng này — nhưng chỉ khi dòng con đó có
		`parent_doc` gắn sẵn (tức được lấy ra từ `.items` của parent doc đã
		load). Một dòng load ĐỘC LẬP qua `frappe.get_doc("Customer Stock
		Receipt Item", <name>)` — đúng như /api/resource/<dt>/<name>/ và
		/api/v2/document/<dt>/<name>/ của Frappe đều làm — có `parent_doc`
		resolve về `None`, nên has_child_permission() TỤT VỀ kiểm tra ROLE
		THUẦN trên doctype cha, bỏ qua hoàn toàn field `kho` của dòng cụ thể.
		Hook has_permission đăng ký trong hooks.py cho chính doctype này
		(`voucher_item_has_permission`) KHÔNG BAO GIỜ được gọi qua đường này,
		vì `frappe.permissions.has_permission()` rẽ nhánh sang
		has_child_permission() ngay khi thấy istable=1, trước khi có cơ hội
		chạy các hook has_permission đăng ký cho doctype con. Ghi đè thẳng
		has_permission() trên class là cách duy nhất chặn được MỌI đường gọi
		(get_doc().check_permission(), REST v1, REST v2), vì Document.check_permission()
		gọi self.has_permission() — một instance method, luôn resolve đúng
		override này bất kể doc được load kiểu gì.
		"""
		if self.flags.ignore_permissions:
			return True
		user = user or frappe.session.user
		if not _is_restricted_user(user):
			return super().has_permission(permtype, debug=debug, user=user)
		parent = self.get("parent")
		if not parent:
			return False
		kho = frappe.db.get_value("Customer Stock Receipt", parent, "kho")
		return bool(kho) and kho in get_allowed_khos(user)
