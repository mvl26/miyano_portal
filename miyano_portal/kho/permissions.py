"""Cách ly dữ liệu kho giữa các khách hàng.

Kho Khách Hàng lọc theo `customer`; năm doctype còn lại đều mang field `kho`
nên lọc theo danh sách kho mà user được phép thấy.

Chỉ Website User bị ràng buộc — nhân viên Miyano ngồi desk thấy toàn bộ, giống
cơ chế đã dùng cho Sales Order ở miyano_portal/permissions.py.
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
# mình — chỉ có `parent` trỏ về Customer Stock Receipt/Issue. Kiểm tra quyền
# trên PARENT chỉ dừng ở mức doctype (role Customer có read=1 là đủ để qua),
# rồi db_query mới lọc CHILD table — nếu bảng child không có
# permission_query_conditions/has_permission riêng, nó không bị lọc gì cả.
# `frappe.client.get_list`/`get_value` cho phép Website User đọc thẳng bảng
# child theo `parent`/`parenttype`, không đi qua parent doc nào hết, nên phải
# đăng ký hook CHO CHÍNH hai doctype này, tách biệt với parent. Đây đúng là
# loại lỗ hổng dễ tái xuất hiện nhất khi có ai đó thêm loại chứng từ (voucher)
# thứ ba mà quên nối dây hook cho bảng item con của nó.


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


# FINDING 4 (vòng review 2, CRITICAL): bản trước có `voucher_item_has_permission`
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
# Sửa: hàm dùng chung dưới đây CHỈ được gọi cho ptype="read" — cả hai
# controller đảm bảo điều đó bằng cách tự kiểm `permtype != "read"` và giao
# lại cho `super().has_permission()` (vốn đã đúng: Customer role không có
# write/delete/submit/cancel trên chứng từ cha nên super() tự trả False,
# không cần kho-check nào thêm). Hàm này không tự vệ bằng cách kiểm lại
# ptype bên trong, vì nó chỉ được gọi từ đúng một chỗ đã kiểm rồi — nhân đôi
# việc kiểm ở đây dễ tạo ảo giác "đã an toàn" trong khi điểm quyết định thật
# sự nằm ở lời gọi, không nằm ở hàm.
def voucher_item_readable(doc, ptype=None, user=None) -> bool:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return True
	parent_type, parent = doc.get("parenttype"), doc.get("parent")
	if not parent_type or not parent:
		return False
	kho = frappe.db.get_value(parent_type, parent, "kho")
	return bool(kho) and kho in get_allowed_khos(user)
