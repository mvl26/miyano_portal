import frappe
from frappe.model.document import Document

from miyano_portal.kho import similarity


class CustomerSupplier(Document):
	def validate(self):
		self.ten_ncc = (self.ten_ncc or "").strip()
		if not self.ten_ncc:
			frappe.throw("Thiếu Tên NCC.", frappe.ValidationError)
		self._kiem_mst()
		self._chan_trung_tuyet_doi()

	def _kiem_mst(self):
		self.mst = (self.mst or "").strip() or None
		if self.mst and not (self.mst.isdigit() and len(self.mst) in (10, 13)):
			frappe.throw(
				"Mã số thuế phải gồm 10 hoặc 13 chữ số.", frappe.ValidationError
			)

	def _chan_trung_tuyet_doi(self):
		"""BR-N3 / NL-7.3: unique theo (kho, ten_ncc), KHÔNG unique toàn cục —
		hai khách khác nhau được phép có NCC trùng tên. So sánh không dấu để
		"Cty ABC" và "Công ty ABC" gõ lệch dấu vẫn coi là cùng một tên.

		Đây là chốt chặn CHÍNH (chạy trên mọi đường ghi — cả kho_ncc_save lẫn
		Desk); kho/ncc.py chỉ tính thêm gợi ý "gần giống" (không chặn) cho
		response của endpoint, không lặp lại logic chặn ở đây.
		"""
		rows = frappe.get_all(
			"Customer Supplier",
			filters={"kho": self.kho, "name": ["!=", self.name or ""]},
			fields=["name", "ten_ncc"],
		)
		for row in rows:
			if similarity.la_trung_tuyet_doi(self.ten_ncc, row.ten_ncc):
				frappe.throw(
					f'Kho đã có NCC tên "{row.ten_ncc}". Tên NCC không được '
					"trùng trong cùng một kho.",
					frappe.ValidationError,
				)

	def on_trash(self):
		"""BR-N3: NCC đã dùng trên >=1 phiếu thì không xoá được, chỉ tắt
		active. Đường portal không có endpoint xoá (giống Customer Warehouse
		Item), nên chốt này chủ yếu bảo vệ đường xoá qua Desk."""
		if frappe.db.exists("Customer Stock Receipt", {"ncc": self.name}):
			frappe.throw(
				f"Không thể xoá NCC {self.ten_ncc}: đã được dùng trên phiếu "
				"nhập. Hãy tắt (Hoạt động = 0) thay vì xoá.",
				frappe.ValidationError,
			)
