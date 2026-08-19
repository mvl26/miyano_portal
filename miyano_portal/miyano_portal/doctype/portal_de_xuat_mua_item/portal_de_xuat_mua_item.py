"""Dòng hàng của `Portal De Xuat Mua`.

CỐ Ý **không** kế thừa `kho.voucher_item.VoucherItemBase`: lớp đó thu hẹp
quyền theo field `kho`, còn bảng này không có `kho` — cha (`Portal De Xuat
Mua`) mang `customer` trực tiếp. Override dưới đây CÙNG HÌNH DẠNG với
`portal_delivery_inspection_item.py::PortalDeliveryInspectionItem`, chỉ đổi
tên doctype cha.

Đọc docstring `VoucherItemBase` trước khi tin lớp này đang bảo vệ cái gì:
cơ chế cách ly CHÍNH là `Portal De Xuat Mua` không có DocPerm nào (§5.1, xem
JSON — mảng `permissions` rỗng). Override này là LỚP PHÒNG THỦ THỨ HAI, chỉ
sống lại nếu ai đó cấp DocPerm cho doctype cha.
"""

import frappe
from frappe.model.document import Document

from miyano_portal.permissions import _is_restricted_user
from miyano_portal.portal_context import get_allowed_customers, pham_vi_don


class PortalDeXuatMuaItem(Document):
	def has_permission(self, permtype="read", *, debug=False, user=None):
		# Kiểm cờ TRƯỚC và tách khỏi nhánh permtype — để `super()` xử lý cờ
		# rồi mới lọc tiếp sẽ làm `insert(ignore_permissions=True)` của
		# seed/test mất tác dụng (cùng lý do đã ghi ở VoucherItemBase).
		if self.flags.ignore_permissions:
			return True
		# CHỈ thu hẹp "read"/"print". Mọi permtype khác giao lại cho Frappe.
		if permtype not in ("read", "print"):
			return super().has_permission(permtype, debug=debug, user=user)
		if not super().has_permission(permtype, debug=debug, user=user):
			return False

		user = user or frappe.session.user
		if not _is_restricted_user(user):
			return True
		cha = frappe.db.get_value(
			"Portal De Xuat Mua", self.parent, ["customer", "khoa_phong"],
			as_dict=True,
		) if self.parent else None
		if not cha or cha.customer not in get_allowed_customers(user):
			return False
		# I4 (review tổng 19/08) — VẾ KHOA, khớp `permissions.de_xuat_item_
		# query` (tầng hook trên CÙNG doctype này) và `permissions.de_xuat_
		# co_quyen` (tầng instance của doctype CHA). Bản trước chỉ lọc
		# `customer`: hai tầng cùng một doctype trả lời khác nhau cho cùng
		# một câu hỏi, và tầng nào được hỏi lại tuỳ kênh truy cập — đúng
		# loại nửa vá tự nó thành lỗ hổng khi ai đó cấp DocPerm cho doctype
		# cha (kịch bản duy nhất làm lớp này sống dậy, xem docstring đầu
		# file). Dùng lại `pham_vi_don()`, KHÔNG viết lại logic khoa; hỏng
		# thì FAIL-CLOSED, cùng nguyên tắc `de_xuat_item_query`.
		try:
			pv = pham_vi_don(user)
		except frappe.PermissionError:
			return False
		khoa = pv.get("custom_khoa_phong")
		return not khoa or cha.khoa_phong == khoa
