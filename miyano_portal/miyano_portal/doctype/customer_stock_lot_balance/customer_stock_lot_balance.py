import hashlib

from frappe.model.document import Document


class CustomerStockLotBalance(Document):
	def autoname(self):
		"""Tên xác định theo (kho, vật tư, lô) để không bao giờ có hai bản ghi
		tồn cho cùng một lô.

		Số lô do khách nhập tay nên có thể dài hoặc chứa ký tự lạ; băm lại để
		tên luôn nằm trong giới hạn 140 ký tự của Frappe.
		"""
		raw = f"{self.kho}::{self.vat_tu}::{self.so_lo}"
		self.name = "TON-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
