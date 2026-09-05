"""CR-04 — căn cứ tồn kho ngay cạnh dòng hàng khi quản lý duyệt.

Chủ đầu tư chốt 05/09/2026. Quản lý duyệt đơn phải trả lời đúng một câu:
"số lượng nhân viên đề nghị có hợp lý không?" — hôm nay họ không có căn cứ
nào ngoài kinh nghiệm.

BA ĐIỀU ĐỊNH HÌNH BỘ TEST NÀY:

1. **Không có dữ liệu thì trả `None`, KHÔNG trả 0.** "Tồn 0" nghĩa là HẾT
   HÀNG; "không biết" là chuyện khác hẳn. Cho quản lý đọc nhầm hai thứ đó là
   làm hỏng đúng cái CR-04 sinh ra để sửa — họ duyệt một đơn vì tưởng kho
   trống, trong khi thật ra hệ thống không tra được. Phần lớn bài dưới đây
   canh đúng ranh giới này.

2. **Module kho hỏng không được làm chết màn duyệt.** Cùng nguyên tắc
   `delivery_hook._chay_an_toan` và `dn_co_hoa_don_nhap`: hỏng thì mất các
   con số, không mất cả trang.

3. **`get_portal_kho()` NÉM LỖI khi khách chưa mở kho** — 1/6 khách hiện tại
   rơi vào đó. Gọi thẳng nó ở đây là làm chết màn chi tiết đơn của đúng
   những bệnh viện đó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.kho import can_cu_duyet as cc


class TestMucTonTru(FrappeTestCase):
	"""Màu chấm suy từ "Còn dùng được", KHÔNG từ Min (0/22 vật tư có Min)."""

	def test_sap_het_thi_do(self):
		self.assertEqual(cc.muc_ton_tru(0), "do")
		self.assertEqual(cc.muc_ton_tru(cc.NGUONG_DO), "do")

	def test_dang_can_thi_vang(self):
		self.assertEqual(cc.muc_ton_tru(cc.NGUONG_DO + 0.1), "vang")
		self.assertEqual(cc.muc_ton_tru(cc.NGUONG_VANG), "vang")

	def test_du_ton_thi_xanh(self):
		self.assertEqual(cc.muc_ton_tru(cc.NGUONG_VANG + 0.1), "xanh")
		self.assertEqual(cc.muc_ton_tru(365), "xanh")

	def test_khong_biet_thi_KHONG_CHAM_MAU(self):
		"""ADU trống -> `con_dung_duoc` là None -> KHÔNG đoán màu.

		Trả "do" cho ca này là nói với quản lý "sắp hết" trong khi thật ra
		không ai biết gì cả — sai nguy hiểm hơn im lặng.
		"""
		self.assertIsNone(cc.muc_ton_tru(None))


class TestCoCanhBao(FrappeTestCase):
	"""⚠ = "đặt khi chưa cần" — còn dùng được lâu mà nhân viên vẫn đặt."""

	def test_con_dung_lau_ma_van_dat_thi_canh_bao(self):
		self.assertTrue(cc.co_canh_bao(con_dung_duoc=100, nv_dat=10))
		self.assertTrue(cc.co_canh_bao(con_dung_duoc=cc.NGUONG_DAT_KHI_CHUA_CAN, nv_dat=1))

	def test_sap_het_ma_dat_thi_KHONG_canh_bao(self):
		"""Đặt khi sắp hết là việc ĐÚNG — gắn cờ vào đó là dạy quản lý bỏ qua cờ."""
		self.assertFalse(cc.co_canh_bao(con_dung_duoc=5, nv_dat=20))

	def test_khong_dat_thi_khong_canh_bao(self):
		self.assertFalse(cc.co_canh_bao(con_dung_duoc=100, nv_dat=0))

	def test_khong_biet_thi_khong_canh_bao(self):
		self.assertFalse(cc.co_canh_bao(con_dung_duoc=None, nv_dat=10))


class TestConDungDuoc(FrappeTestCase):
	def test_chia_dung(self):
		self.assertAlmostEqual(cc.con_dung_duoc(ton=4, dang_ve=0, adu=0.8), 5.0)
		self.assertAlmostEqual(cc.con_dung_duoc(ton=2, dang_ve=10, adu=0.3), 40.0)

	def test_adu_bang_0_thi_None_KHONG_chia(self):
		"""Chia cho 0 là ValueError; trả một số vô cực cũng vô nghĩa với người
		đọc. Không có mức dùng thì không nói được còn dùng bao lâu."""
		self.assertIsNone(cc.con_dung_duoc(ton=100, dang_ve=0, adu=0))

	def test_adu_None_thi_None(self):
		self.assertIsNone(cc.con_dung_duoc(ton=100, dang_ve=0, adu=None))

	def test_ton_None_thi_None(self):
		"""Không tra được tồn thì không suy ra được số ngày còn dùng."""
		self.assertIsNone(cc.con_dung_duoc(ton=None, dang_ve=0, adu=1))


class TestKhachChuaMoKho(FrappeTestCase):
	"""1/6 khách hiện tại không có kho nào. Màn duyệt của họ vẫn phải sống."""

	def test_khong_co_kho_thi_tra_rong_KHONG_nem_loi(self):
		kq = cc.can_cu_cho_don(
			frappe._dict(customer="_TEST CR04 KHONG CO KHO", name="SO-X", items=[])
		)
		self.assertEqual(kq, {})

	def test_khong_goi_get_portal_kho(self):
		"""`get_portal_kho()` ném PermissionError khi khách chưa mở kho.

		Bài này canh Ở TẦNG MÃ NGUỒN vì đó là chỗ lỗi sẽ quay lại: một bản vá
		sau đọc thấy "đã có hàm lấy kho" rồi gọi nó cho gọn, và màn chi tiết
		đơn của mọi bệnh viện chưa mở kho chết ngay — một lỗi chỉ lộ ra với
		đúng nhóm khách đó.
		"""
		import ast
		import inspect

		# SOI BẰNG CÂY CÚ PHÁP, không tìm chuỗi: chính docstring của module
		# giải thích VÌ SAO không được gọi hàm này, nên nó có chứa tên đó.
		# Tìm chuỗi là bài tự đỏ vì chính lời giải thích của mình — đúng lớp
		# lỗi "khớp chỗ nói thay cho chỗ dùng" mà nhánh này đã trả giá.
		cay = ast.parse(inspect.getsource(cc))
		goi = {
			n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
			for n in ast.walk(cay)
			if isinstance(n, ast.Call)
		}
		self.assertNotIn(
			"get_portal_kho", goi,
			"`can_cu_duyet` GỌI `get_portal_kho()` — hàm đó NÉM LỖI khi khách "
			"chưa mở kho, và sẽ làm chết màn chi tiết đơn của họ",
		)


class TestKhoHongKhongLamChetManDuyet(FrappeTestCase):
	def test_loi_module_kho_tra_rong_va_ghi_log(self):
		from unittest.mock import patch

		with patch.object(cc, "_kho_cua_khach", side_effect=RuntimeError("kho hỏng")):
			kq = cc.can_cu_cho_don(
				frappe._dict(customer="X", name="SO-Y", items=[])
			)
		self.assertEqual(kq, {})


class TestEndpointTraCanCu(FrappeTestCase):
	def test_portal_order_track_tra_khoa_can_cu_kho(self):
		"""Thiếu khoá này thì màn duyệt có chỗ hiện mà không có gì để hiện.

		Lớp lỗi "API trả về mà không màn nào đọc" / "màn hình đọc mà API
		không trả" đã lọt SÁU lần trong dự án này (xem
		`docs/BAN-DO-CHUC-NANG.md` mục 4) — bài này là lưới cho lần thứ bảy.
		"""
		import inspect

		from miyano_portal.api import portal

		self.assertIn(
			'"can_cu_kho"', inspect.getsource(portal.portal_order_track),
			"`portal_order_track` không trả `can_cu_kho`",
		)

	def test_endpoint_so_kho_dung_lai_kho_the_kho_khong_dung_duong_thu_hai(self):
		"""Sổ kho xổ tại dòng dùng lại `kho_the_kho` đã có.

		Endpoint đó tự kiểm vật tư thuộc kho người gọi (`_vat_tu_cua_kho`).
		Dựng đường đọc thứ hai là dựng chỗ thứ hai để quên chốt đó.
		"""
		from miyano_portal.api import kho as api_kho

		self.assertTrue(hasattr(api_kho, "kho_the_kho"))
		self.assertIn(
			"_vat_tu_cua_kho",
			__import__("inspect").getsource(api_kho.kho_the_kho),
			"`kho_the_kho` không còn kiểm vật tư thuộc kho người gọi",
		)

	def test_can_cu_tra_vat_tu_de_man_hinh_goi_duoc_so_kho(self):
		"""Không trả `vat_tu` thì màn hình không có gì để truyền cho
		`kho_the_kho` — nút sổ kho thành nút chết."""
		import inspect

		self.assertIn('"vat_tu": vt', inspect.getsource(cc.can_cu_cho_don))
