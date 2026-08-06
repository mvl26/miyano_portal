import frappe
from frappe.model.document import Document


class CustomerWarehouse(Document):
	def validate(self):
		self._one_per_customer()
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
