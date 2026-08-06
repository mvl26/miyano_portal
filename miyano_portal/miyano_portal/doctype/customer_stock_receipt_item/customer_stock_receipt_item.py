from frappe.model.document import Document

from miyano_portal.kho.permissions import voucher_item_readable


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
		Hook has_permission cho chính doctype này KHÔNG BAO GIỜ được gọi qua
		đường này (đã cố tình không đăng ký trong hooks.py — xem comment ở
		đó), vì `frappe.permissions.has_permission()` rẽ nhánh sang
		has_child_permission() ngay khi thấy istable=1, trước khi có cơ hội
		chạy bất kỳ hook has_permission nào đăng ký cho doctype con. Ghi đè
		thẳng has_permission() trên class là cách duy nhất chặn được MỌI
		đường gọi (get_doc().check_permission(), REST v1, REST v2), vì
		Document.check_permission() gọi self.has_permission() — một instance
		method, luôn resolve đúng override này bất kể doc được load kiểu gì.

		FINDING 4 (vòng review 2, CRITICAL — đã vá): bản trước trả kết quả
		kho-check cho MỌI permtype như nhau, nên role Customer (chỉ có
		read=1 trên chứng từ cha, write=0/delete=0/submit=0/cancel=0) được
		CẤP quyền xoá/sửa dòng con — xác nhận thực nghiệm bằng
		frappe.delete_doc() trên dòng đã submit và doc.save() ghi đè đơn giá
		trên dòng nháp, cả hai đều làm sổ (Customer Stock Ledger Entry) lệch
		khỏi phiếu vì on_submit/on_cancel của phiếu cha không hề chạy. CHỈ
		được thu hẹp quyền đọc; mọi permtype khác phải giao lại cho Frappe
		mặc định (vốn đã đúng: Customer role không có các quyền đó trên
		chứng từ cha nên super() tự trả False).

		`self.flags.ignore_permissions` được kiểm TRƯỚC TIÊN và tách biệt
		khỏi nhánh permtype — nếu để `super().has_permission("read", ...)`
		tự xử lý cờ này (nó có xử lý) rồi mới gọi tiếp `voucher_item_readable()`
		phía dưới, cờ ignore_permissions sẽ bị ghi đè mất tác dụng cho đúng
		permtype="read", phá vỡ `insert(ignore_permissions=True)` mà seed và
		test hiện có phụ thuộc vào.
		"""
		if self.flags.ignore_permissions:
			return True
		if permtype != "read":
			return super().has_permission(permtype, debug=debug, user=user)
		if not super().has_permission(permtype, debug=debug, user=user):
			return False
		return voucher_item_readable(self, permtype, user=user)
