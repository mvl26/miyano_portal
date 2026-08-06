import frappe
from frappe.model.document import Document


class CustomerWarehouse(Document):
	def validate(self):
		self._one_per_customer()
		self._ma_kho_duy_nhat()
		if not self.ten_don_vi_in:
			self.ten_don_vi_in = frappe.db.get_value(
				"Customer", self.customer, "customer_name"
			)

	def _one_per_customer(self):
		"""Mỗi khách hàng chỉ được có đúng một kho trên cổng (spec §2, quyết định 5).

		Field `customer` đã đánh unique ở tầng database, nhưng lỗi
		DuplicateEntryError của MariaDB không đọc được với người dùng cuối, nên
		chặn sớm ở đây để trả về thông báo tiếng Việt.
		"""
		existing = frappe.db.get_value(
			"Customer Warehouse",
			{"customer": self.customer, "name": ["!=", self.name or ""]},
			"name",
		)
		if existing:
			frappe.throw(
				f"Khách hàng {self.customer} đã có kho {existing} trên cổng. "
				f"Mỗi khách hàng chỉ được có một kho.",
				frappe.ValidationError,
			)

	def _ma_kho_duy_nhat(self):
		"""Mã kho đi vào số phiếu (PN-BM-2026-00001) nên phải duy nhất toàn hệ thống.

		Field đã đánh unique ở database, nhưng khi chạm phải index đó Frappe in
		ra "Mã kho must be unique" — tiếng Anh, lẫn vào giao diện tiếng Việt.
		Chặn trước ở đây để thông báo đọc được.
		"""
		self.ma_kho = (self.ma_kho or "").strip()
		existing = frappe.db.get_value(
			"Customer Warehouse",
			{"ma_kho": self.ma_kho, "name": ["!=", self.name or ""]},
			["name", "customer"],
			as_dict=True,
		)
		if existing:
			frappe.throw(
				f"Mã kho {self.ma_kho} đã được dùng cho kho {existing.name} "
				f"({existing.customer}). Hãy chọn mã khác.",
				frappe.ValidationError,
			)
