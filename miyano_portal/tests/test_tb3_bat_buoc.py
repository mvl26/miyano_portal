"""BR-TB-3 — cờ bắt buộc chọn máy, sao y cơ chế mốc thời gian của khoa phòng.

Chốt chặn so THỜI ĐIỂM TẠO PHIẾU với MỐC BẬT CỜ, không so thời điểm ghi sổ:
phiếu nháp tạo trước khi bật cờ vẫn ghi sổ được (tránh khoá tồn đọng).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

KHACH = "ZZTB3 Benh Vien"
KHACH_MOI = "ZZTB3 Benh Vien Moi"


class TestBatBuocThietBi(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._don()
		self.addCleanup(self._don)
		frappe.get_doc({
			"doctype": "Customer", "customer_name": KHACH,
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
		}).insert(ignore_permissions=True)
		self.kho = frappe.get_doc({
			"doctype": "Customer Warehouse", "customer": KHACH,
			"ten_kho": "ZZTB3 Kho", "ma_kho": "ZZTB3",
			"ngay_bat_dau": frappe.utils.add_days(frappe.utils.today(), -30),
		}).insert(ignore_permissions=True)
		self.kp = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH, "kho": self.kho.name,
			"ten_khoa_phong": "ZZTB3 Khoa A", "ma_khoa": "ZZTB3A",
		}).insert(ignore_permissions=True)
		self.may = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH,
			"ma_thiet_bi": "ZZTB3-01", "ten_thiet_bi": "Máy ZZTB3",
		}).insert(ignore_permissions=True)
		self.vat_tu = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho.name,
			"ma_vat_tu": "ZZTB3-HC1", "ten_vat_tu": "Hoá chất ZZTB3", "dvt": "Hộp",
		}).insert(ignore_permissions=True)
		self.lo = "LO-ZZTB3"
		nhap = frappe.get_doc({
			"doctype": "Customer Stock Receipt", "kho": self.kho.name,
			"ngay": frappe.utils.add_days(frappe.utils.today(), -7),
			"loai_nhap": "Nhập khác",
			"items": [{
				"vat_tu": self.vat_tu.name, "so_lo": self.lo, "so_luong": 100,
				"don_gia": 50000,
			}],
		}).insert(ignore_permissions=True)
		nhap.submit()

	def _phieu_nhap_lieu(self, thiet_bi=None, loai_xuat="Xuất sử dụng"):
		"""Lập phiếu và DỪNG Ở NHÁP. Mọi ca ở đây so thời điểm TẠO phiếu với
		mốc bật cờ, nên phiếu phải tồn tại trước khi cờ bật."""
		return frappe.get_doc({
			"doctype": "Customer Stock Issue", "kho": self.kho.name,
			"ngay": frappe.utils.today(), "loai_xuat": loai_xuat,
			"khoa_phong": self.kp.name,
			"items": [{
				"vat_tu": self.vat_tu.name, "so_lo": self.lo,
				"so_luong": 2, "thiet_bi": thiet_bi,
			}],
		}).insert(ignore_permissions=True)

	def _bat_co(self):
		"""Đi qua save() chứ không db.set_value, để _ghi_moc_bat_buoc_thiet_bi()
		chạy và ghi mốc."""
		self.kho.bat_buoc_thiet_bi = 1
		self.kho.save(ignore_permissions=True)

	def _don(self):
		"""Dọn CHỈ dữ liệu của hai khách hàng ZZTB3 của bộ test này (KHACH và
		KHACH_MOI — KHACH_MOI phục vụ ca "kho mới tạo với cờ bật sẵn", cần
		khách hàng riêng vì mỗi khách hàng chỉ được một kho).

		TUYỆT ĐỐI không xoá không lọc — erptest.local là site làm việc thật
		mang dữ liệu demo của nhiều bệnh viện và nhiều bộ test khác.
		"""
		khach = [KHACH, KHACH_MOI]
		khos = frappe.get_all(
			"Customer Warehouse", filters={"customer": ["in", khach]}, pluck="name"
		) or [""]
		phieu_xuat = frappe.get_all("Customer Stock Issue", filters={"kho": ["in", khos]}, pluck="name")
		phieu_nhap = frappe.get_all("Customer Stock Receipt", filters={"kho": ["in", khos]}, pluck="name")
		vat_tu = frappe.get_all("Customer Warehouse Item", filters={"kho": ["in", khos]}, pluck="name")
		frappe.db.delete("Customer Stock Issue Item", {"parent": ["in", phieu_xuat or [""]]})
		frappe.db.delete("Customer Stock Receipt Item", {"parent": ["in", phieu_nhap or [""]]})
		frappe.db.delete("Customer Warehouse Item Equipment", {"parent": ["in", vat_tu or [""]]})
		frappe.db.delete("Customer Stock Issue", {"kho": ["in", khos]})
		frappe.db.delete("Customer Stock Receipt", {"kho": ["in", khos]})
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": ["in", khos]})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": ["in", khos]})
		frappe.db.delete("Customer Warehouse Item", {"kho": ["in", khos]})
		for dt in ("Customer Equipment", "Customer Department", "Customer Warehouse"):
			frappe.db.delete(dt, {"customer": ["in", khach]})
		frappe.db.delete("Customer", {"name": ["in", khach]})

	def test_co_tat_thi_khong_bat_buoc(self):
		doc = self._phieu_nhap_lieu(thiet_bi=None)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_bat_co_thi_phieu_tao_sau_bi_chan(self):
		self._bat_co()
		doc = self._phieu_nhap_lieu(thiet_bi=None)
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_phieu_nhap_tao_truoc_khi_bat_co_van_ghi_so_duoc(self):
		doc = self._phieu_nhap_lieu(thiet_bi=None)   # tạo TRƯỚC
		self._bat_co()                                # bật SAU
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_co_bat_ma_moc_rong_thi_tu_lanh(self):
		"""Cờ bật qua db.set_value (patch rollout hàng loạt) không đi qua
		validate() nên không có mốc. Fail-closed ở đây sẽ ĐÓNG BĂNG mọi
		phiếu nháp đang mở ở MỌI kho — đúng cái E8 sinh ra để tránh."""
		doc = self._phieu_nhap_lieu(thiet_bi=None)
		frappe.db.set_value("Customer Warehouse", self.kho.name, "bat_buoc_thiet_bi", 1)
		frappe.db.set_value("Customer Warehouse", self.kho.name, "bat_buoc_thiet_bi_tu", None)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
		self.assertIsNotNone(
			frappe.db.get_value("Customer Warehouse", self.kho.name, "bat_buoc_thiet_bi_tu")
		)

	def test_chi_ap_cho_xuat_su_dung(self):
		self._bat_co()
		doc = self._phieu_nhap_lieu(thiet_bi=None, loai_xuat="Xuất huỷ - hết hạn")
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_bat_co_va_da_chon_may_thi_ghi_so_duoc(self):
		"""Đối chứng cho test_bat_co_thi_phieu_tao_sau_bi_chan: chốt chặn
		phải THẢ khi dòng đã có máy, không phải chặn vô điều kiện mọi phiếu
		một khi cờ bật. Không có ca này thì một cài đặt luôn throw khi cờ
		bật (bỏ qua self.items) vẫn qua được năm ca còn lại."""
		self._bat_co()
		doc = self._phieu_nhap_lieu(thiet_bi=self.may.name)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_moc_khong_bi_ghi_de_khi_luu_lai_kho(self):
		"""Giết đột biến `if bat:` (bỏ điều kiện `not truoc`) trong
		`_ghi_moc_bat_buoc_thiet_bi()`: nếu mốc bị ghi đè mỗi lần lưu kho
		trong khi cờ đang bật, thời hạn ân hạn bị đặt lại liên tục — một
		phiếu nháp lập từ hôm qua sẽ bị chặn chỉ vì hôm nay ai đó sửa một
		field không liên quan của kho (ví dụ tên thủ kho) rồi bấm Lưu."""
		self._bat_co()
		moc_qua_khu = frappe.utils.add_to_date(frappe.utils.now_datetime(), days=-5)
		frappe.db.set_value(
			"Customer Warehouse", self.kho.name, "bat_buoc_thiet_bi_tu", moc_qua_khu
		)
		self.kho.reload()
		self.kho.thu_kho = "Ai đó khác"
		self.kho.save(ignore_permissions=True)
		moc_sau = frappe.db.get_value(
			"Customer Warehouse", self.kho.name, "bat_buoc_thiet_bi_tu"
		)
		self.assertEqual(
			frappe.utils.get_datetime(moc_sau), frappe.utils.get_datetime(moc_qua_khu)
		)

	def test_kho_moi_tao_voi_co_bat_san_co_moc_ngay(self):
		"""Nhánh `is_new()` của `_ghi_moc_bat_buoc_thiet_bi()`: kho MỚI tạo
		với cờ bật sẵn phải có mốc ngay từ insert() đầu tiên, không đợi một
		lần bật thứ hai. Cần khách hàng RIÊNG (KHACH_MOI) vì mỗi khách hàng
		chỉ được có một kho (_one_per_customer)."""
		frappe.get_doc({
			"doctype": "Customer", "customer_name": KHACH_MOI,
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
		}).insert(ignore_permissions=True)
		kho_moi = frappe.get_doc({
			"doctype": "Customer Warehouse", "customer": KHACH_MOI,
			"ten_kho": "ZZTB3 Kho Moi", "ma_kho": "ZZTB3M",
			"ngay_bat_dau": frappe.utils.add_days(frappe.utils.today(), -30),
			"bat_buoc_thiet_bi": 1,
		}).insert(ignore_permissions=True)
		self.assertIsNotNone(kho_moi.bat_buoc_thiet_bi_tu)

	def test_phieu_dao_khong_bi_chan(self):
		"""on_cancel KHÔNG được phép ném lỗi — bật cờ giữa lúc xuất và lúc
		huỷ không được làm sập thao tác huỷ."""
		doc = self._phieu_nhap_lieu(thiet_bi=None)
		doc.submit()
		self._bat_co()
		doc.cancel()
		self.assertEqual(doc.docstatus, 2)
