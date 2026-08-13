import frappe
from frappe.model.document import Document


class CustomerWarehouseItem(Document):
	def validate(self):
		self.ma_vat_tu = (self.ma_vat_tu or "").strip()
		self._unique_within_warehouse()
		self._validate_nguong_ton()

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

	def _da_khai(self, gia_tri) -> bool:
		"""`ton_toi_thieu`/`diem_dat_lai`/`ton_toi_da`/`boi_so_dat` là Float/Int
		trên một doctype THƯỜNG — cột DB tương ứng luôn `NOT NULL DEFAULT 0`
		(xác nhận bằng `SHOW COLUMNS`, hành vi chuẩn của Frappe cho MỌI field
		số, không có cách khai báo nào tắt được), khác hẳn field Single như
		`Miyano Portal Settings.nguong_cham_luan_chuyen_ngay` (nơi `tabSingles`
		đơn giản KHÔNG CÓ dòng khi chưa cấu hình — xem
		`reports.py::_nguong_cham_luan_chuyen()`). Không có "dòng vắng mặt" nào
		để phân biệt "chưa khai" với "khai 0" ở đây, nên 0 được coi LÀ "chưa
		khai" — cùng quy ước với `kho/dutru.py::_chua_khai()` (đọc docstring ở
		đó cho đánh đổi nghiệp vụ đã biết và chấp nhận)."""
		if gia_tri in (None, ""):
			return False
		return abs(float(gia_tri)) > 1e-9

	def _validate_nguong_ton(self):
		"""E5/DataDict §2.1: `ton_toi_thieu` ≥ 0; `min ≤ diem_dat_lai ≤
		ton_toi_da` — CHỈ kiểm thứ tự khi CẢ BA đã có giá trị. Một khách mới
		bắt đầu cấu hình (ví dụ chỉ nhập min, chưa nhập ROP/max) chưa có gì để
		so sánh — chặn cứng ở đây sẽ ép khách phải điền đủ ba ô cùng lúc, trái
		với AC US-E5.1 ("bấm Gợi ý từ tiêu thụ rồi khách TỰ lưu", ngụ ý được
		lưu từng phần).

		`lead_time_ngay`/`boi_so_dat` kiểm riêng, không phụ thuộc bộ ba
		min/ROP/max đã đủ hay chưa — hai trường này đứng độc lập trong công
		thức (BR-P2/P4).
		"""
		if self.ton_toi_thieu not in (None, "") and float(self.ton_toi_thieu) < 0:
			frappe.throw("Tồn tối thiểu (min) không được âm.", frappe.ValidationError)

		if self._da_khai(self.ton_toi_thieu) and self._da_khai(self.diem_dat_lai) and self._da_khai(self.ton_toi_da):
			min_ = float(self.ton_toi_thieu)
			rop = float(self.diem_dat_lai)
			max_ = float(self.ton_toi_da)
			if not (min_ <= rop <= max_):
				frappe.throw(
					f"Tồn tối thiểu ({min_:g}) ≤ Điểm đặt lại ({rop:g}) ≤ Tồn tối đa "
					f"({max_:g}) không đúng thứ tự.",
					frappe.ValidationError,
				)

		if self.lead_time_ngay not in (None, "") and not (1 <= frappe.utils.cint(self.lead_time_ngay) <= 60):
			frappe.throw("Lead time (ngày) phải trong khoảng 1–60.", frappe.ValidationError)

		if self._da_khai(self.boi_so_dat) and float(self.boi_so_dat) <= 0:
			frappe.throw("Bội số đặt phải lớn hơn 0.", frappe.ValidationError)
