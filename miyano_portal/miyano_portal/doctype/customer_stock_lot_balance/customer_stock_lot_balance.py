import hashlib

from frappe.model.document import Document
from frappe.utils import getdate


class CustomerStockLotBalance(Document):
	def autoname(self):
		"""Tên xác định theo (kho, vật tư, lô, hạn dùng) để không bao giờ có hai
		bản ghi tồn cho cùng một lô.

		Số lô do khách nhập tay nên có thể dài hoặc chứa ký tự lạ; băm lại để
		tên luôn nằm trong giới hạn 140 ký tự của Frappe.

		Từ 19/10/2026 (spec tách số lô) khoá thêm HẠN DÙNG: số lô NCC trùng được
		giữa hai lô thật khác hạn. Hạn chuẩn hoá về `YYYY-MM-DD` hoặc chuỗi rỗng
		để `None`/`""`/date/str của cùng một hạn băm ra cùng một tên. Bản ghi cũ
		(băm không có hạn) giữ nguyên tên — chuỗi thô mới luôn có thêm "::" nên
		không bao giờ trùng tên cũ.
		"""
		han = str(getdate(self.han_su_dung)) if self.han_su_dung else ""
		raw = f"{self.kho}::{self.vat_tu}::{self.so_lo}::{han}"
		self.name = "TON-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
