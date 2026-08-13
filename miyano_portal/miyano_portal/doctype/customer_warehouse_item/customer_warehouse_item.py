import frappe
from frappe.model.document import Document

from miyano_portal.kho.ledger import EPS


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
		"""`ton_toi_thieu`/`diem_dat_lai`/`ton_toi_da`/`lead_time_ngay`/
		`boi_so_dat` là Float/Int trên một doctype THƯỜNG — cột DB tương ứng
		luôn `NOT NULL DEFAULT 0` (xác nhận bằng `SHOW COLUMNS`, hành vi
		chuẩn của Frappe cho MỌI field số, không có cách khai báo nào tắt
		được), khác hẳn field Single như `Miyano Portal Settings.nguong_
		cham_luan_chuyen_ngay` (nơi `tabSingles` đơn giản KHÔNG CÓ dòng khi
		chưa cấu hình — xem `reports.py::_nguong_cham_luan_chuyen()`). Không
		có "dòng vắng mặt" nào để phân biệt "chưa khai" với "khai 0" ở đây,
		nên 0 được coi LÀ "chưa khai" — cùng quy ước với
		`kho/dutru.py::chua_khai()` (đọc docstring ở đó cho đánh đổi nghiệp
		vụ đã biết và chấp nhận).

		Ngưỡng `EPS` dùng CHUNG với `chua_khai()` (import từ `kho/ledger.py`,
		review E5 round 2, M-2): hai hàm coi "chưa khai" là NGƯỠNG số rác dấu
		phẩy động giống nhau — trước bản này `_da_khai` tự dùng `1e-9` trong
		khi `chua_khai()` dùng `EPS=0.0005`, một giá trị cỡ `0.0001` sẽ được
		một bên coi là "đã khai" còn bên kia coi là "chưa khai", dù docstring
		tuyên bố "cùng quy ước"."""
		if gia_tri in (None, ""):
			return False
		return abs(float(gia_tri)) > EPS

	def _kiem_thu_tu(self, ten_a: str, gia_tri_a, ten_b: str, gia_tri_b) -> None:
		"""So `a ≤ b` khi CẢ HAI đã khai — ĐỘC LẬP với ô còn lại trong bộ ba
		min/ROP/max (I-1, review E5 round 2).

		Trước bản này, `min ≤ ROP ≤ max` chỉ được kiểm khi ĐỦ CẢ BA ô — một
		khách gõ nhầm đảo `ton_toi_thieu=100`/`ton_toi_da=5` mà để trống ROP
		lưu SẠCH không một cảnh báo, vì phép kiểm ba-ngôi cũ không chạy. Từ
		đó màn dự trù báo "Thiếu" đỏ VĨNH VIỄN (tồn luôn < 100), `sl_goi_y`
		luôn = 0 (max=5 luôn nhỏ hơn tồn), và job daily gửi email cảnh báo
		mỗi tuần về một vật tư không hề thiếu — không có đường nào báo cho
		khách biết họ gõ nhầm. So TỪNG CẶP ngay khi cặp đó có đủ hai ô bắt
		được ca này mà không cần đợi ô thứ ba."""
		if self._da_khai(gia_tri_a) and self._da_khai(gia_tri_b):
			a, b = float(gia_tri_a), float(gia_tri_b)
			if a > b:
				frappe.throw(
					f"{ten_a} ({a:g}) không được lớn hơn {ten_b} ({b:g}).",
					frappe.ValidationError,
				)

	def _validate_nguong_ton(self):
		"""E5/DataDict §2.1: `ton_toi_thieu`/`diem_dat_lai`/`ton_toi_da` ≥ 0
		(cả ba, không riêng min — I-1); `min ≤ ROP ≤ max` kiểm THEO TỪNG CẶP
		ngay khi cặp đó đã khai (`_kiem_thu_tu()`), không đợi đủ cả ba. Một
		khách mới bắt đầu cấu hình (ví dụ chỉ nhập min, chưa nhập ROP/max)
		chưa có gì để so — chặn cứng khi CHỈ MỘT ô có giá trị sẽ ép khách
		phải điền đủ ba ô cùng lúc, trái với AC US-E5.1 (lưu từng phần).

		`lead_time_ngay`/`boi_so_dat` kiểm riêng, không phụ thuộc bộ ba
		min/ROP/max — hai trường này đứng độc lập trong công thức (BR-P2/P4).
		`lead_time_ngay` dùng `_da_khai()` (coi 0 là "chưa khai"), KHÔNG phải
		`not in (None, "")` (I-2, review E5 round 2): `kho/vat_tu.py::
		_so_hoac_khong()` ánh xạ MỌI ô trống thành 0 cho cả năm trường ngưỡng
		— nếu ở đây vẫn coi 0 là "đã khai" cho riêng `lead_time_ngay`, xoá
		trắng ô Lead time trên form sẽ ném "Lead time phải trong khoảng
		1–60" ngay tại chính ô đang trống, một hành vi không nhất quán với
		bốn ô kia (xoá trắng lưu được bình thường)."""
		for nhan, gia_tri in (
			("Tồn tối thiểu (min)", self.ton_toi_thieu),
			("Điểm đặt lại (ROP)", self.diem_dat_lai),
			("Tồn tối đa (max)", self.ton_toi_da),
		):
			if self._da_khai(gia_tri) and float(gia_tri) < 0:
				frappe.throw(f"{nhan} không được âm.", frappe.ValidationError)

		self._kiem_thu_tu("Tồn tối thiểu (min)", self.ton_toi_thieu, "Điểm đặt lại (ROP)", self.diem_dat_lai)
		self._kiem_thu_tu("Điểm đặt lại (ROP)", self.diem_dat_lai, "Tồn tối đa (max)", self.ton_toi_da)
		self._kiem_thu_tu("Tồn tối thiểu (min)", self.ton_toi_thieu, "Tồn tối đa (max)", self.ton_toi_da)

		if self._da_khai(self.lead_time_ngay) and not (1 <= frappe.utils.cint(self.lead_time_ngay) <= 60):
			frappe.throw("Lead time (ngày) phải trong khoảng 1–60.", frappe.ValidationError)

		if self._da_khai(self.boi_so_dat) and float(self.boi_so_dat) <= 0:
			frappe.throw("Bội số đặt phải lớn hơn 0.", frappe.ValidationError)
