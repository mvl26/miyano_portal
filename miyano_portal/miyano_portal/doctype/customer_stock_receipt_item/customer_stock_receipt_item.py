from frappe.model.document import Document

from miyano_portal.kho.permissions import voucher_item_readable


class CustomerStockReceiptItem(Document):
	def has_permission(self, permtype="read", *, debug=False, user=None):
		"""Ghi đè has_permission() ở mức CLASS cho hai permtype "read" và
		"print" — KHÔNG chặn được mọi đường gọi, xem "Phạm vi thật sự" bên
		dưới trước khi tin rằng doctype này đã an toàn tuyệt đối.

		`frappe.permissions.has_child_permission()` không kiểm được theo TỪNG
		DÒNG cho bảng con (istable=1): nó suy ra parent_doctype rồi kiểm quyền
		trên PARENT thay vì trên chính dòng này — nhưng chỉ khi dòng con đó có
		`parent_doc` gắn sẵn (tức được lấy ra từ `.items` của parent doc đã
		load). Một dòng load ĐỘC LẬP qua `frappe.get_doc("Customer Stock
		Receipt Item", <name>)` có `parent_doc` resolve về `None`, nên
		has_child_permission() TỤT VỀ kiểm tra ROLE THUẦN trên doctype cha, bỏ
		qua hoàn toàn field `kho` của dòng cụ thể. Hook has_permission cho
		chính doctype này KHÔNG BAO GIỜ được gọi (đã cố tình không đăng ký
		trong hooks.py — xem comment ở đó).

		PHẠM VI THẬT SỰ (vòng review 3, FINDING 8 — sửa comment sai ở đây,
		bản trước từng viết "chặn được MỌI đường gọi", KHÔNG ĐÚNG):

		- CÓ chặn: `doc.check_permission()` / `doc.has_permission()` — mọi
		  nơi gọi qua INSTANCE của document này, ví dụ REST v1/v2 single-doc
		  GET (`read_doc()` gọi `doc.check_permission("read")`), và
		  `frappe.utils.weasyprint.get_html()` (gọi
		  `doc.check_permission("print")`).
		- KHÔNG chặn: lời gọi MODULE-LEVEL `frappe.has_permission(doctype,
		  ptype, doc)` (hàm tự do trong frappe/__init__.py, không phải
		  instance method). Với doctype istable=1, hàm này gọi thẳng
		  `frappe.permissions.has_child_permission()`, và hàm đó KHÔNG BAO
		  GIỜ gọi `doc.has_permission()` — nó tự suy `parent_doc` (cùng lỗi
		  resolve-về-None như trên, xảy ra trên CẢ đường doc-instance LẪN
		  đường docname-string) rồi tự đệ quy kiểm ROLE THUẦN trên doctype
		  cha, hoàn toàn không đụng tới class này. `frappe/www/printview.py`
		  (`validate_print_permission`) gọi đúng dạng module-level này — nên
		  `/printview?doctype=Customer Stock Receipt Item&name=<dòng của
		  khách khác>` vẫn render được cho một Website User khác khách hàng,
		  DÙ override này đã có mặt. Xác nhận thực nghiệm:
		  `doc.has_permission("read")` → False (override chạy đúng),
		  `frappe.has_permission(doc.doctype, "read", doc)` → True (override
		  không được gọi tới). Không có cách đóng lỗ này ở tầng class/hook
		  của riêng doctype con trong Frappe 15.113.4 — cần chặn ở tầng
		  route/request, việc đó nằm ngoài phạm vi override này (xem
		  task-6-report.md, addendum vòng 3).

		FINDING 4 (vòng review 2, CRITICAL — đã vá): bản trước trả kết quả
		kho-check cho MỌI permtype như nhau, nên role Customer (chỉ có
		read=1/print=1 trên chứng từ cha, write=0/delete=0/submit=0/cancel=0)
		được CẤP quyền xoá/sửa dòng con. CHỈ được thu hẹp "read" và "print";
		mọi permtype khác phải giao lại cho Frappe mặc định (vốn đã đúng:
		Customer role không có các quyền đó trên chứng từ cha nên super() tự
		trả False). "print" được thêm vào cùng nhóm với "read" ở vòng 3, sau
		khi đo được `doc.has_permission("print")` cũng trả True sai cho
		khách khác — cùng cơ chế, Customer role có print=1 trên chứng từ cha
		giống hệt read=1.

		`self.flags.ignore_permissions` được kiểm TRƯỚC TIÊN và tách biệt
		khỏi nhánh permtype — nếu để `super().has_permission(...)` tự xử lý
		cờ này (nó có xử lý) rồi mới gọi tiếp `voucher_item_readable()` phía
		dưới, cờ ignore_permissions sẽ bị ghi đè mất tác dụng, phá vỡ
		`insert(ignore_permissions=True)` mà seed và test hiện có phụ thuộc
		vào.
		"""
		if self.flags.ignore_permissions:
			return True
		if permtype not in ("read", "print"):
			return super().has_permission(permtype, debug=debug, user=user)
		if not super().has_permission(permtype, debug=debug, user=user):
			return False
		return voucher_item_readable(self, permtype, user=user)
