import frappe
from frappe.model.document import Document


class CustomerWarehouse(Document):
	def validate(self):
		self._one_per_customer()
		self._ma_kho_duy_nhat()
		self._ghi_moc_bat_buoc_khoa_phong()
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

	def _ghi_moc_bat_buoc_khoa_phong(self):
		"""US-E8.2/BR-CP2 — điểm tinh tế nhất của E8: một Check đơn thuần
		("bắt buộc khoa phòng: có/không") không đủ để trả lời "phiếu này có bị
		chặn hay không", vì chốt chặn phải so MỐC BẬT CỜ với THỜI ĐIỂM TẠO
		PHIẾU (không phải thời điểm ghi sổ) — "bật lúc 10:00 thì chỉ phiếu tạo
		SAU 10:00 mới bị chặn; phiếu nháp tạo TRƯỚC đó vẫn ghi sổ được (tránh
		khoá tồn đọng)". Không có mốc thời gian nào được lưu lại thì không có
		gì để so — vì vậy kho mang thêm `bat_buoc_khoa_phong_tu` (Datetime,
		read-only, chỉ hệ ghi), và hàm này là NƠI DUY NHẤT ghi vào đó.

		Tự đặt mốc = now() đúng một lần, tại đúng thời điểm cờ chuyển từ 0
		sang 1 — bắt được cả hai tình huống:
		  * kho CŨ đang bật cờ lần đầu (self.is_new() == False, giá trị cũ
		    trong DB là 0) — đây là ca chính của US-E8.2.
		  * kho MỚI tạo với cờ đã bật sẵn (self.is_new() == True) — "trước"
		    coi như 0 vì kho chưa từng tồn tại, nên bước tạo kho CHÍNH LÀ lúc
		    cờ "bật" — không có phiếu nào tạo trước một kho chưa tồn tại nên
		    không có gì để ân hạn.
		Tắt cờ (1 -> 0) không đụng tới mốc: BẬT LẠI sau đó (0 -> 1 lần hai)
		phải ghi đè bằng mốc MỚI — "mốc bật cờ" luôn là lần bật GẦN NHẤT, mọi
		phiếu nháp tạo trong khoảng kho tạm tắt cờ đều được coi là "tạo khi
		cờ đang tắt", đúng tinh thần "không khoá tồn đọng".

		QUYẾT ĐỊNH CHO CA BIÊN (ghi rõ vì đây là chỗ dễ đoán sai, và đã ĐỔI
		HƯỚNG một lần — xem F-1, review E8): nếu `bat_buoc_khoa_phong=1` mà
		`bat_buoc_khoa_phong_tu` lại rỗng — chỉ có thể xảy ra khi ai đó bật
		cờ bằng đường KHÔNG qua validate() (ví dụ `frappe.db.set_value`
		thẳng, hoặc — kịch bản THẬT khi Miyano triển khai cho nhiều bệnh
		viện — một patch rollout/Data Import bật cờ hàng loạt) — phía kiểm
		tra (`customer_stock_issue.py:_chan_thieu_khoa_phong`) TỰ LÀNH: ghi
		`now()` làm mốc ngay tại lần phát hiện, rồi so bình thường từ đó.
		Bản ĐẦU coi "mốc rỗng" là "áp bắt buộc cho TẤT CẢ" — nghe an toàn hơn
		nhưng SAI HƯỚNG: nó biến một cờ bật hàng loạt (đúng kịch bản triển
		khai 20 bệnh viện) thành một lần ĐÓNG BĂNG tức thời mọi phiếu nháp
		đang mở ở MỌI kho — chính là "khoá tồn đọng" mà NL-4.11 sinh ra để
		tránh. Tự lành vào `now()` giữ đúng tinh thần "phiếu nháp tạo TRƯỚC
		khi bật cờ vẫn ghi sổ được", chỉ khác ở chỗ "khi bật cờ" được xác
		định lại là "khi có phiếu đầu tiên chạm phải cờ thiếu mốc", không
		phải "khi ai đó gõ UPDATE".
		"""
		bat = frappe.utils.cint(self.bat_buoc_khoa_phong)
		truoc = 0
		if not self.is_new():
			truoc = frappe.utils.cint(
				frappe.db.get_value(
					"Customer Warehouse", self.name, "bat_buoc_khoa_phong"
				)
			)
		if bat and not truoc:
			self.bat_buoc_khoa_phong_tu = frappe.utils.now_datetime()
