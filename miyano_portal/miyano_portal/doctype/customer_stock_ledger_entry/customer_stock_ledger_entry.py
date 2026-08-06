import frappe
from frappe.model.document import Document


class CustomerStockLedgerEntry(Document):
	"""Sổ ghi tăng dần. Chỉ insert, không sửa, không xoá.

	Ngoại lệ duy nhất được phép sửa sau khi insert là cờ `da_dao` — xem
	ledger.mark_reversed(). Mọi thay đổi khác đều bị chặn ở đây để một lỗi
	lập trình về sau không âm thầm làm hỏng sổ.

	Guard đặt ở `before_save` (không phải `on_update`) vì `Document.save()`
	gọi `db_update()` TRƯỚC `run_post_save_methods()` và không có savepoint
	quanh save: nếu chặn ở `on_update`, dòng sai đã được ghi vào DB trong
	transaction hiện tại trước khi ValidationError được ném ra, nên bất kỳ
	nơi gọi nào bắt exception (import hàng loạt, background job,
	try/except quanh post_lines) sẽ để lại giá trị hỏng mà không có lỗi lộ
	ra. `before_save` chạy trước `db_update()` nên chặn được trước khi ghi.
	`self.get_doc_before_save()` đã có dữ liệu ở bước này vì Frappe nạp nó
	trong `load_doc_before_save()`, chạy trước `run_before_save_methods()`.
	"""

	def before_save(self):
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
