"""Lớp cơ sở dùng chung cho hai bảng dòng chứng từ kho.

`Customer Stock Receipt Item` và `Customer Stock Issue Item` từng có hai bản
`has_permission()` GIỐNG NHAU TỪNG BYTE trong hai file controller. Trùng lặp ở
đúng chỗ này là loại nguy hiểm nhất: nó là logic phân quyền, và một bản vá chỉ
sửa một trong hai file sẽ để hở một nửa mà không có gì đỏ lên (FINDING N4,
review cuối). Gộp về một chỗ để không còn "một nửa" nào tồn tại.

CẢNH BÁO KHI SỬA: bộ test hiện tại KHÔNG bắt được việc lớp này thôi không chạy
nữa. Kể từ vòng 4, role `Customer` không còn DocPerm nào trên chứng từ cha, nên
mọi test phủ định về dòng con pass nhờ vòng kiểm role chứ không nhờ override
này. Nếu Frappe thôi nhận diện được controller (đổi tên class, MRO hỏng), lớp
phòng thủ thứ hai chết âm thầm trong khi suite vẫn xanh — đó là lý do có
`test_child_item_controllers_use_shared_has_permission`.
"""

from frappe.model.document import Document

from miyano_portal.kho.permissions import voucher_item_readable


class VoucherItemBase(Document):
	"""Ghi đè has_permission() ở mức CLASS cho hai permtype "read" và "print"
	— LỚP PHÒNG THỦ THỨ HAI, KHÔNG phải cơ chế cách ly chính.

	CƠ CHẾ CHÍNH (vòng 4): role `Customer` không còn DocPerm nào trên chứng từ
	CHA (`Customer Stock Receipt` / `Customer Stock Issue`). Vì mọi đường kiểm
	quyền của một doctype istable=1 — kể cả đường module-level mà override này
	không với tới — cuối cùng đều quy về kiểm role trên doctype cha, việc gỡ
	grant đó chặn Website User trên MỌI đường gọi, kể cả `/printview`. Portal
	đọc dữ liệu kho duy nhất qua miyano_portal/api/kho.py. Xem khối comment
	trong hooks.py và task-6-report.md, addendum vòng 4.

	Override này vì thế chỉ còn ý nghĩa nếu ai đó cấp lại DocPerm cho
	`Customer` trên chứng từ cha: khi đó nó lại là thứ chặn các đường gọi đi
	qua INSTANCE. Đừng viện dẫn nó như bằng chứng hai doctype này an toàn —
	đọc "PHẠM VI THẬT SỰ" bên dưới để biết nó KHÔNG chặn được gì.

	`frappe.permissions.has_child_permission()` không kiểm được theo TỪNG DÒNG
	cho bảng con (istable=1): nó suy ra parent_doctype rồi kiểm quyền trên
	PARENT thay vì trên chính dòng này — nhưng chỉ khi dòng con đó có
	`parent_doc` gắn sẵn (tức được lấy ra từ `.items` của parent doc đã load).
	Một dòng load ĐỘC LẬP qua `frappe.get_doc(<child dt>, <name>)` có
	`parent_doc` resolve về `None`, nên has_child_permission() TỤT VỀ kiểm tra
	ROLE THUẦN trên doctype cha, bỏ qua hoàn toàn field `kho` của dòng cụ thể.
	Hook has_permission cho chính hai doctype này KHÔNG BAO GIỜ được gọi (đã
	cố tình không đăng ký trong hooks.py — xem comment ở đó, và assertion
	ngược trong test_hooks_registered_for_every_kho_doctype).

	PHẠM VI THẬT SỰ (vòng review 3, FINDING 8 — sửa comment sai của bản trước,
	vốn từng viết "chặn được MỌI đường gọi", KHÔNG ĐÚNG):

	- CÓ chặn: `doc.check_permission()` / `doc.has_permission()` — mọi nơi gọi
	  qua INSTANCE của document này, ví dụ REST v1/v2 single-doc GET
	  (`read_doc()` gọi `doc.check_permission("read")`), và
	  `frappe.utils.weasyprint.get_html()` (gọi `doc.check_permission("print")`).
	- KHÔNG chặn: lời gọi MODULE-LEVEL `frappe.has_permission(doctype, ptype,
	  doc)` (hàm tự do trong frappe/__init__.py, không phải instance method).
	  Với doctype istable=1, hàm này gọi thẳng
	  `frappe.permissions.has_child_permission()`, và hàm đó KHÔNG BAO GIỜ gọi
	  `doc.has_permission()` — nó tự suy `parent_doc` (cùng lỗi resolve-về-None
	  như trên, xảy ra trên CẢ đường doc-instance LẪN đường docname-string) rồi
	  tự đệ quy kiểm ROLE THUẦN trên doctype cha, hoàn toàn không đụng tới lớp
	  này. `frappe/www/printview.py` (`validate_print_permission`),
	  `frappe/utils/print_format.py` (`download_pdf`) và `frappe/client.py`
	  (`has_permission`) đều gọi đúng dạng module-level này. Đo thực nghiệm ở
	  vòng 3, KHI role `Customer` còn read=1 trên chứng từ cha:
	  `doc.has_permission("read")` -> False (override chạy đúng),
	  `frappe.has_permission(doc.doctype, "read", doc)` -> True (override không
	  được gọi tới) — và `/printview` render ra số lô, số lượng, đơn giá của
	  khách khác.

	  Lỗ đó KHÔNG đóng được ở tầng class/hook của riêng doctype con trong
	  Frappe 15.113.4. Vòng 4 đóng nó ở tầng cấu hình quyền: bỏ DocPerm của
	  `Customer` trên doctype CHA, đúng chỗ mà has_child_permission() quy về.
	  Sau thay đổi đó, cả ba đường trên đều trả PermissionError cho tài khoản
	  portal — không nhờ override này, mà nhờ không còn grant nền nào để tụt
	  về.

	FINDING 4 (vòng review 2, CRITICAL — đã vá). Đoạn này mô tả tình trạng
	TRƯỚC VÒNG 4; các con số quyền nêu ở đây là LỊCH SỬ, vì vòng 4 đã gỡ sạch
	DocPerm của `Customer` khỏi chứng từ cha. Giữ nguyên vì logic thu hẹp theo
	permtype vẫn đúng và sẽ lại cần thiết ngay nếu grant quay lại. Nguyên văn:
	bản trước trả kết quả kho-check cho MỌI permtype như nhau, nên role
	Customer (khi đó có read=1/print=1 trên chứng từ cha, write=0/delete=0/
	submit=0/cancel=0) được CẤP quyền xoá/sửa dòng con. CHỈ được thu hẹp "read"
	và "print"; mọi permtype khác phải giao lại cho Frappe mặc định (vốn đã
	đúng: Customer role không có các quyền đó trên chứng từ cha nên super() tự
	trả False). "print" được thêm vào cùng nhóm với "read" ở vòng 3, sau khi đo
	được `doc.has_permission("print")` cũng trả True sai cho khách khác — cùng
	cơ chế, Customer role có print=1 trên chứng từ cha giống hệt read=1.

	`self.flags.ignore_permissions` được kiểm TRƯỚC TIÊN và tách biệt khỏi
	nhánh permtype — nếu để `super().has_permission(...)` tự xử lý cờ này (nó
	có xử lý) rồi mới gọi tiếp `voucher_item_readable()` phía dưới, cờ
	ignore_permissions sẽ bị ghi đè mất tác dụng, phá vỡ
	`insert(ignore_permissions=True)` mà seed và test hiện có phụ thuộc vào.
	"""

	def has_permission(self, permtype="read", *, debug=False, user=None):
		if self.flags.ignore_permissions:
			return True
		if permtype not in ("read", "print"):
			return super().has_permission(permtype, debug=debug, user=user)
		if not super().has_permission(permtype, debug=debug, user=user):
			return False
		return voucher_item_readable(self, permtype, user=user)
