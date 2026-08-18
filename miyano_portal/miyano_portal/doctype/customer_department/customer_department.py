import frappe
from frappe.model.document import Document

from miyano_portal.kho import similarity


class CustomerDepartment(Document):
	# Mã dành riêng của hệ thống — không đặt cho khoa phòng cụ thể được.
	# "CHUNG" dùng cho phiếu "Đề nghị mua" quản lý đặt hàng "Toàn viện" (spec §5.5).
	MA_DANH_RIENG = {"CHUNG"}

	def validate(self):
		self.ten_khoa_phong = (self.ten_khoa_phong or "").strip()
		if not self.ten_khoa_phong:
			frappe.throw("Thiếu Tên khoa phòng.", frappe.ValidationError)
		if self.kho:
			kho_cua = frappe.db.get_value("Customer Warehouse", self.kho, "customer")
			if not self.customer:
				# Đường tạo CŨ (trước bước này) chỉ truyền `kho`, không truyền
				# `customer` — suy `customer` từ `kho.customer` để không đổi
				# hành vi của những chỗ gọi có từ trước (vd _make_khoa() trong
				# test E8, kho_khoa_phong_save trong api/kho.py).
				self.customer = kho_cua
			elif kho_cua != self.customer:
				# Kho nào cũng phải thuộc đúng bệnh viện của khoa phòng này —
				# không chặn thì một khoa của bệnh viện A trỏ được vào kho của B.
				frappe.throw(
					"Kho được chọn không thuộc khách hàng này.", frappe.ValidationError
				)
		self._chuan_hoa_ma_khoa()
		self._chan_trung_tuyet_doi()

	def _chuan_hoa_ma_khoa(self):
		"""Mã khoa đi vào TÊN của phiếu Đề nghị mua (spec §6.1) nên phải là
		một định danh, không phải chữ tự do: viết hoa, chỉ A-Z0-9, không trùng
		trong cùng bệnh viện, và không được lấy mã dành riêng."""
		self.ma_khoa = (self.ma_khoa or "").strip().upper() or None
		if not self.ma_khoa:
			return
		if len(self.ma_khoa) > 20:
			frappe.throw("Mã khoa không được quá 20 ký tự.", frappe.ValidationError)
		if not self.ma_khoa.isalnum() or not self.ma_khoa.isascii():
			frappe.throw(
				"Mã khoa chỉ được dùng chữ cái không dấu và chữ số (ví dụ HUYETHOC).",
				frappe.ValidationError,
			)
		if self.ma_khoa in self.MA_DANH_RIENG:
			frappe.throw(
				f'"{self.ma_khoa}" là mã dành riêng của hệ thống, không đặt cho '
				"khoa phòng được.",
				frappe.ValidationError,
			)
		trung = frappe.db.exists(
			"Customer Department",
			{"customer": self.customer, "ma_khoa": self.ma_khoa, "name": ["!=", self.name or ""]},
		)
		if trung:
			frappe.throw(
				f'Bệnh viện này đã có khoa phòng mang mã "{self.ma_khoa}".',
				frappe.ValidationError,
			)

	def _chan_trung_tuyet_doi(self):
		"""BR-CP1 / NL-4.13: unique theo (customer, ten_khoa_phong), KHÔNG
		unique toàn cục — hai khách khác nhau được phép có khoa trùng tên (ví
		dụ hai bệnh viện đều có "Khoa Hồi sức"). So sánh không dấu, cùng khuôn
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
			filters={"customer": self.customer, "name": ["!=", self.name or ""]},
			fields=["name", "ten_khoa_phong"],
		)
		for row in rows:
			if similarity.la_trung_tuyet_doi(self.ten_khoa_phong, row.ten_khoa_phong):
				frappe.throw(
					f'Bệnh viện đã có khoa phòng tên "{row.ten_khoa_phong}". Tên khoa '
					"phòng không được trùng trong cùng một bệnh viện.",
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
