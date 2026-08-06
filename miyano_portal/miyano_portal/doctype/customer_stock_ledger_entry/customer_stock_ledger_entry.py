import frappe
from frappe.model.document import Document


class CustomerStockLedgerEntry(Document):
	"""Sổ ghi tăng dần. Chỉ insert, không sửa, không xoá.

	Ngoại lệ duy nhất được phép sửa sau khi insert là cờ `da_dao` — xem
	ledger.mark_reversed(). Mọi thay đổi khác đều bị chặn ở đây để một lỗi
	lập trình về sau không âm thầm làm hỏng sổ.
	"""

	def on_update(self):
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		changed = {
			f.fieldname
			for f in self.meta.fields
			if self.get(f.fieldname) != before.get(f.fieldname)
		}
		if changed - {"da_dao"}:
			frappe.throw(
				"Không được sửa dòng sổ kho đã ghi. Muốn điều chỉnh thì huỷ "
				"phiếu để hệ thống ghi phiếu đảo.",
				frappe.ValidationError,
			)

	def on_trash(self):
		frappe.throw(
			"Không được xoá dòng sổ kho. Muốn điều chỉnh thì huỷ phiếu để hệ "
			"thống ghi phiếu đảo.",
			frappe.ValidationError,
		)
