import frappe
from frappe.model.document import Document


class CustomerWarehouseItem(Document):
	def validate(self):
		self.ma_vat_tu = (self.ma_vat_tu or "").strip()
		self._unique_within_warehouse()

	def _unique_within_warehouse(self):
		"""Mã vật tư chỉ cần duy nhất TRONG một kho.

		Hai khách khác nhau hoàn toàn được phép dùng trùng mã, nên không thể
		đánh unique ở tầng field; phải kiểm tra theo cặp (kho, ma_vat_tu).
		"""
		existing = frappe.db.get_value(
			"Customer Warehouse Item",
			{
				"kho": self.kho,
				"ma_vat_tu": self.ma_vat_tu,
				"name": ["!=", self.name or ""],
			},
			"name",
		)
		if existing:
			frappe.throw(
				f"Mã vật tư {self.ma_vat_tu} đã tồn tại trong kho này ({existing}).",
				frappe.ValidationError,
			)
