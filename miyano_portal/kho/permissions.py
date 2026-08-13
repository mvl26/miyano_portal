"""Cách ly dữ liệu kho giữa các khách hàng — LỚP PHÒNG THỦ THỨ HAI.

ĐỌC ĐOẠN NÀY TRƯỚC. Kể từ vòng 4, không hàm nào trong file này là cơ chế cách
ly chính. Cách ly chính là: role `Customer` KHÔNG còn DocPerm nào trên sáu
doctype kho (xem mảng "permissions" của sáu file JSON, và khối comment dài
trong hooks.py). Không có grant nền thì Frappe chặn Website User ngay ở vòng
kiểm role, trước khi bất kỳ permission_query_conditions / has_permission nào
được gọi — nên với cấu hình hiện tại các hàm dưới đây không bao giờ chạy cho
một tài khoản portal.

Portal đọc dữ liệu kho DUY NHẤT qua miyano_portal/api/kho.py, nơi kho được suy
từ phiên đăng nhập bằng get_portal_kho() rồi lọc tường minh — an toàn nhờ cấu
trúc truy vấn, không nhờ tầng phân quyền.

Vì sao vẫn giữ file này: nếu ai đó cấp lại DocPerm cho `Customer` (sửa JSON,
hoặc Role Permission Manager tạo Custom DocPerm), các hàm này lập tức sống lại
và hạ mức thiệt hại từ "rò rỉ mọi khách hàng" xuống "vẫn chỉ thấy kho của
mình". Đừng xoá chúng, nhưng cũng đừng viện dẫn chúng như bằng chứng an toàn.

Kho Khách Hàng lọc theo `customer`; năm doctype còn lại đều mang field `kho`
nên lọc theo danh sách kho mà user được phép thấy. Chỉ Website User bị ràng
buộc — nhân viên Miyano ngồi desk thấy toàn bộ, giống cơ chế đã dùng cho Sales
Order ở miyano_portal/permissions.py.
"""

import frappe

from miyano_portal.permissions import _is_restricted_user
from miyano_portal.portal_context import get_allowed_customers, get_allowed_khos


def _kho_condition(table: str, user: str | None) -> str:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return ""
	khos = get_allowed_khos(user)
	if not khos:
		return "1=0"
	joined = ", ".join(frappe.db.escape(k) for k in khos)
	return f"`tab{table}`.`kho` in ({joined})"


def kho_query(user=None) -> str:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return ""
	customers = get_allowed_customers(user)
	if not customers:
		return "1=0"
	joined = ", ".join(frappe.db.escape(c) for c in customers)
	return f"`tabCustomer Warehouse`.`customer` in ({joined})"


def vat_tu_query(user=None) -> str:
	return _kho_condition("Customer Warehouse Item", user)


def receipt_query(user=None) -> str:
	return _kho_condition("Customer Stock Receipt", user)


def issue_query(user=None) -> str:
	return _kho_condition("Customer Stock Issue", user)


def sle_query(user=None) -> str:
	return _kho_condition("Customer Stock Ledger Entry", user)


def lot_query(user=None) -> str:
	return _kho_condition("Customer Stock Lot Balance", user)


def ncc_query(user=None) -> str:
	"""E4: Customer Supplier mang field `kho` riêng (không phải kho tự nó),
	nên lọc đúng khuôn _kho_condition() như Customer Warehouse Item."""
	return _kho_condition("Customer Supplier", user)


def khoa_phong_query(user=None) -> str:
	"""E8: Customer Department mang field `kho` riêng, cùng hình dạng
	Customer Supplier — lọc đúng khuôn _kho_condition()."""
	return _kho_condition("Customer Department", user)


def kho_has_permission(doc, ptype=None, user=None) -> bool:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return True
	return doc.get("customer") in get_allowed_customers(user)


def kho_child_has_permission(doc, ptype=None, user=None) -> bool:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return True
	return doc.get("kho") in get_allowed_khos(user)


# `Customer Stock Receipt Item` và `Customer Stock Issue Item` là grandchild:
# istable=1, permissions=[] trong JSON, và không mang field `kho` của riêng
# mình — chỉ có `parent` trỏ về Customer Stock Receipt/Issue.
#
# BỐI CẢNH LỊCH SỬ — mô tả tình trạng TRƯỚC VÒNG 4, không phải hiện trạng.
# Khi role `Customer` còn read=1 trên chứng từ cha: kiểm quyền trên PARENT chỉ
# dừng ở mức doctype (read=1 là đủ để qua), rồi db_query mới lọc CHILD table —
# bảng child không có permission_query_conditions riêng thì không bị lọc gì cả,
# và `frappe.client.get_list`/`get_value` cho phép Website User đọc thẳng bảng
# child theo `parent`/`parenttype`, không đi qua parent doc nào hết. Đó là lý
# do hai hàm dưới đây tồn tại.
#
# HIỆN TRẠNG (vòng 4): role `Customer` không còn DocPerm nào trên chứng từ cha,
# nên bước "read=1 là đủ để qua" không còn xảy ra — đã đo:
# `frappe.client.get_list` trên cả sáu doctype cha ném PermissionError cho cả
# hai user portal. Hai hàm dưới đây vì thế không còn được gọi tới trong thực
# tế; giữ lại làm lớp phòng thủ thứ hai (xem docstring đầu file).
#
# Vẫn giữ nguyên bài học gốc: nếu ai đó thêm loại chứng từ (voucher) thứ ba VÀ
# cấp quyền cho một role portal, bảng item con của nó phải được nối dây hook
# riêng — đó là lỗ dễ tái xuất hiện nhất ở đây.


def _child_condition(table: str, parent_table: str, user: str | None) -> str:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return ""
	khos = get_allowed_khos(user)
	if not khos:
		return "1=0"
	joined = ", ".join(frappe.db.escape(k) for k in khos)
	return (
		f"`tab{table}`.`parent` in "
		f"(select name from `tab{parent_table}` where `kho` in ({joined}))"
	)


def receipt_item_query(user=None) -> str:
	return _child_condition(
		"Customer Stock Receipt Item", "Customer Stock Receipt", user
	)


def issue_item_query(user=None) -> str:
	return _child_condition(
		"Customer Stock Issue Item", "Customer Stock Issue", user
	)


# FINDING 4 (vòng review 2, CRITICAL) — TOÀN BỘ khối comment này mô tả tình
# trạng TRƯỚC VÒNG 4. Mọi câu dạng "role Customer có read=1/print=1 trên chứng
# từ cha" bên dưới là mô tả LỊCH SỬ, không còn đúng với hiện trạng: vòng 4 đã
# gỡ sạch DocPerm của `Customer` khỏi sáu doctype kho. Giữ lại nguyên văn vì
# câu chuyện leo thang quyền vẫn là bài học đúng và sẽ đúng trở lại ngay nếu
# grant quay lại.
#
# Bản trước có `voucher_item_has_permission`
# trả kết quả kho-check cho MỌI ptype (read/write/delete/submit/cancel như
# nhau). Hàm đó được đăng ký trong hooks.py["has_permission"] nhưng — như
# FINDING 1 đã chứng minh — KHÔNG BAO GIỜ được framework gọi tới cho doctype
# istable=1 (has_child_permission() rẽ nhánh sang parent trước khi bất kỳ hook
# has_permission nào của child có cơ hội chạy). Vì hook chết, hai controller
# (customer_stock_receipt_item.py, customer_stock_issue_item.py) phải tự ghi
# đè has_permission() ở mức class — và bản ghi đè ĐẦU TIÊN mắc đúng lỗi này:
# nó cũng trả kết quả kho-check cho mọi ptype, khiến role Customer (vốn chỉ
# có read=1 trên chứng từ cha, write=0/delete=0/submit=0/cancel=0) ĐƯỢC CẤP
# quyền xoá/sửa dòng con — xác nhận thực nghiệm: frappe.delete_doc() xoá được
# một dòng trên phiếu ĐÃ SUBMIT, và doc.save() ghi đè được đơn giá trên dòng
# nháp, cả hai đều làm sổ (Customer Stock Ledger Entry) lệch khỏi phiếu vì
# on_submit/on_cancel của phiếu cha không hề chạy.
#
# Sửa: hàm dùng chung dưới đây CHỈ được gọi cho ptype="read" hoặc "print" —
# cả hai controller đảm bảo điều đó bằng cách tự kiểm
# `permtype not in ("read", "print")` và giao lại cho `super().has_permission()`
# (vốn đã đúng: Customer role không có write/delete/submit/cancel trên chứng
# từ cha nên super() tự trả False, không cần kho-check nào thêm). "print"
# được thêm cùng "read" ở vòng review 3, sau khi đo thực nghiệm thấy
# `doc.has_permission("print")` cũng trả True sai cho khách khác — cùng cơ
# chế: Customer role có print=1 trên chứng từ cha giống hệt read=1, và
# `frappe.utils.weasyprint.get_html()` gọi thẳng `doc.check_permission("print")`.
# Hàm này không tự vệ bằng cách kiểm lại ptype bên trong, vì nó chỉ được gọi
# từ đúng một chỗ đã kiểm rồi — nhân đôi việc kiểm ở đây dễ tạo ảo giác "đã an
# toàn" trong khi điểm quyết định thật sự nằm ở lời gọi, không nằm ở hàm.
#
# GIỚI HẠN QUAN TRỌNG (FINDING 8, vòng review 3): hàm này — và cả hai
# has_permission() override gọi nó — CHỈ chặn được khi kiểm tra đi qua
# INSTANCE của document (doc.check_permission()/doc.has_permission()). Lời
# gọi MODULE-LEVEL `frappe.has_permission(doctype, ptype, doc)` (hàm tự do,
# không phải instance method) KHÔNG BAO GIỜ chạm tới class này — với doctype
# istable=1, nó rẽ thẳng vào `frappe.permissions.has_child_permission()`, một
# hàm hoàn toàn nằm trong Frappe core, tự suy `parent_doc` (luôn resolve về
# None cho cả doc-instance lẫn docname-string) rồi tự đệ quy kiểm ROLE THUẦN
# trên doctype cha — không có bước nào trong đường đó gọi `doc.has_permission()`.
#
# CÁCH LỖ ĐÓ ĐƯỢC ĐÓNG (vòng 4): chính vì đường module-level luôn quy về
# "kiểm role trên doctype CHA", gỡ hết DocPerm của role `Customer` trên hai
# chứng từ cha làm bước kiểm đó trả False cho mọi Website User — và vì thế
# `/printview`, `download_pdf`, `frappe.client.has_permission` đều bị chặn.
# Nói cách khác: lỗ này KHÔNG được đóng bởi hàm dưới đây, mà bởi cấu hình
# quyền. Hàm dưới đây chỉ còn giá trị nếu grant `Customer` quay trở lại.
# Đo trước/sau, xem task-6-report.md, addendum vòng 4.
def voucher_item_readable(doc, ptype=None, user=None) -> bool:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return True
	parent_type, parent = doc.get("parenttype"), doc.get("parent")
	if not parent_type or not parent:
		return False
	kho = frappe.db.get_value(parent_type, parent, "kho")
	return bool(kho) and kho in get_allowed_khos(user)
