"""Sổ nhật ký thao tác — CHỈ THÊM.

Một bản ghi ở đây là một câu khẳng định về QUÁ KHỨ: "lúc 14:22 ngày 03/09,
anh A đã duyệt phiếu này". Sửa nó là nói dối về quá khứ, xoá nó là xoá bằng
chứng — nên cả hai đều bị chặn ở tầng doctype, không phải ở tầng endpoint:
`api/` chỉ là một trong các đường vào, còn bất biến này thuộc về chính
chứng từ.
"""

import frappe
from frappe.model.document import Document


class PortalNhatKyYeuCau(Document):
	def validate(self):
		if not (self.de_xuat or self.sales_order):
			frappe.throw(
				"Dòng nhật ký phải gắn vào một phiếu đề xuất hoặc một đơn "
				"hàng — không gắn vào đâu thì không ai đọc tới được.",
				frappe.ValidationError,
			)

	def on_update(self):
		# `on_update` chạy CẢ khi insert. `get_doc_before_save()` trả None ở
		# lần insert đầu tiên — đó là cách phân biệt "vừa ghi" với "đang sửa
		# một dòng đã ghi", và là cách duy nhất không phải tin vào `is_new()`
		# (cờ đó đã bị đặt lại ở thời điểm hook này chạy).
		if self.get_doc_before_save() is not None:
			frappe.throw(
				"Nhật ký thao tác chỉ ghi thêm, không sửa được.",
				frappe.ValidationError,
			)

	def on_trash(self):
		frappe.throw(
			"Nhật ký thao tác không xoá được — đó là bằng chứng ai đã làm gì.",
			frappe.ValidationError,
		)
