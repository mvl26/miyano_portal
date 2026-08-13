import frappe
from frappe.model.document import Document

from miyano_portal.kho import similarity


class CustomerDepartment(Document):
	def validate(self):
		self.ten_khoa_phong = (self.ten_khoa_phong or "").strip()
		if not self.ten_khoa_phong:
			frappe.throw("Thiếu Tên khoa phòng.", frappe.ValidationError)
		self.ma_khoa = (self.ma_khoa or "").strip() or None
		if self.ma_khoa and len(self.ma_khoa) > 20:
			frappe.throw("Mã khoa không được quá 20 ký tự.", frappe.ValidationError)
		self._chan_trung_tuyet_doi()

	def _chan_trung_tuyet_doi(self):
		"""BR-CP1 / NL-4.13: unique theo (kho, ten_khoa_phong), KHÔNG unique
		toàn cục — hai khách khác nhau được phép có khoa trùng tên (ví dụ hai
		bệnh viện đều có "Khoa Hồi sức"). So sánh không dấu, cùng khuôn
		CustomerSupplier._chan_trung_tuyet_doi() (đọc kỹ docstring ở đó).

		CỐ Ý KHÔNG đánh "unique" trên field ten_khoa_phong trong JSON: bảng
		dùng collation utf8mb4_unicode_ci (không phân biệt hoa/thường, PAD
		SPACE) — một unique index của MariaDB sẽ so khác với
		similarity.la_trung_tuyet_doi() (bỏ dấu tiếng Việt, KHÔNG chỉ
		hoa/thường), hai phép so lệch nhau tạo ra khe hở lách được. Đây phải
		là NGUỒN DUY NHẤT cho chốt "trùng tuyệt đối" — đúng khuôn NCC.
		"""
		rows = frappe.get_all(
			"Customer Department",
			filters={"kho": self.kho, "name": ["!=", self.name or ""]},
			fields=["name", "ten_khoa_phong"],
		)
		for row in rows:
			if similarity.la_trung_tuyet_doi(self.ten_khoa_phong, row.ten_khoa_phong):
				frappe.throw(
					f'Kho đã có khoa phòng tên "{row.ten_khoa_phong}". Tên khoa '
					"phòng không được trùng trong cùng một kho.",
					frappe.ValidationError,
				)

	def on_trash(self):
		"""BR-CP1: khoa phòng đã dùng trên >=1 phiếu thì không xoá được, chỉ
		tắt active. Không lọc theo docstatus — kể cả một phiếu NHÁP còn tham
		chiếu khoa này cũng đủ để coi là "đã dùng" (cùng khuôn on_trash() của
		CustomerSupplier, vốn cũng không lọc docstatus)."""
		if frappe.db.exists("Customer Stock Issue", {"khoa_phong": self.name}):
			frappe.throw(
				f"Không thể xoá khoa phòng {self.ten_khoa_phong}: đã được dùng "
				"trên phiếu xuất. Hãy tắt (Hoạt động = 0) thay vì xoá.",
				frappe.ValidationError,
			)
