"""Sổ nhật ký thao tác — luật CHỈ-THÊM và luật KHÔNG-NÉM-LỖI.

Một bản ghi ở đây là một câu khẳng định về QUÁ KHỨ. Sửa nó là nói dối về
quá khứ, nên doctype chặn cả sửa lẫn xoá — kể cả từ Desk của nhân sự
Miyano, kể cả `ignore_permissions`.

Luật thứ hai quan trọng ngang: ghi nhật ký KHÔNG ĐƯỢC ném lỗi ra ngoài.
Nó được gọi ngay sau những chuyển trạng thái đã thành công (`gui_duyet`,
`duyet`, hook giao hàng…); một trục trặc ở khâu ghi mà cuốn theo cả
transaction sẽ làm mất đúng thứ vừa làm được. Cùng ràng buộc tuyệt đối mà
`portal_thong_bao_khach.bao_*` đang chịu.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import nhat_ky
from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestNhatKyChiThem(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item

	def _ghi(self, **kw):
		return nhat_ky.ghi(
			nhat_ky.SK_KHOA_GUI_DUYET,
			customer=self.kh_a, khoa_phong=self.khoa_a,
			de_xuat=self._phieu(), vai=nhat_ky.VAI_KHOA,
			**kw,
		)

	def _phieu(self):
		# `self.item` lấy trong setUp, KHÔNG gọi lại `dung_fixture()` ở đây:
		# hàm đó XOÁ SẠCH mọi phiếu `_TEST DX%` mỗi lần chạy, nên gọi lại
		# giữa chừng là tự xoá dữ liệu bài test vừa dựng — và triệu chứng sẽ
		# nổ ra ở một bài khác, khó lần ngược.
		if not getattr(self, "_ten_phieu", None):
			doc = frappe.get_doc({
				"doctype": "Portal De Xuat Mua",
				"customer": self.kh_a, "khoa_phong": self.khoa_a,
				"items": [{"item_code": self.item, "so_luong_de_xuat": 1}],
			}).insert(ignore_permissions=True)
			self._ten_phieu = doc.name
		return self._ten_phieu

	def test_ghi_duoc_mot_dong(self):
		ten = self._ghi(ghi_chu="Hết găng tay")
		self.assertTrue(ten)
		d = frappe.get_doc(nhat_ky.DOCTYPE, ten)
		self.assertEqual(d.su_kien, nhat_ky.SK_KHOA_GUI_DUYET)
		self.assertEqual(d.vai, nhat_ky.VAI_KHOA)
		self.assertEqual(d.customer, self.kh_a)
		self.assertTrue(d.thoi_diem)

	def test_nguoi_thao_tac_mac_dinh_la_phien_dang_goi(self):
		"""Người thao tác là NGƯỜI ĐANG GỌI tại khoảnh khắc đó — không phải
		thứ người gọi phải nhớ truyền vào. Bắt mỗi chỗ gọi tự truyền là tạo
		ra một chỗ để quên, và quên ở đây nghĩa là một dòng nhật ký không
		có ai."""
		ten = self._ghi()
		self.assertEqual(
			frappe.db.get_value(nhat_ky.DOCTYPE, ten, "nguoi_thao_tac"),
			frappe.session.user,
		)

	def test_vai_he_thong_khong_gan_nguoi(self):
		"""VẾ ÂM của bài trên. `don_tao` là việc của HỆ THỐNG — gán tên
		người đang chạy vào đó là vu cho họ một thao tác họ không làm."""
		ten = nhat_ky.ghi(
			nhat_ky.SK_DON_TAO, customer=self.kh_a,
			de_xuat=self._phieu(), vai=nhat_ky.VAI_HE_THONG,
		)
		self.assertFalse(
			frappe.db.get_value(nhat_ky.DOCTYPE, ten, "nguoi_thao_tac")
		)

	def test_khong_sua_duoc_dong_da_ghi(self):
		ten = self._ghi()
		d = frappe.get_doc(nhat_ky.DOCTYPE, ten)
		d.ghi_chu = "sửa lại"
		with self.assertRaises(frappe.ValidationError) as ctx:
			d.save(ignore_permissions=True)
		self.assertIn("chỉ ghi thêm", str(ctx.exception))

	def test_khong_xoa_duoc_dong_da_ghi(self):
		ten = self._ghi()
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.delete_doc(nhat_ky.DOCTYPE, ten, force=True, ignore_permissions=True)
		self.assertIn("không xoá được", str(ctx.exception))

	def test_phai_gan_vao_mot_chung_tu(self):
		"""Một dòng nhật ký không gắn vào phiếu lẫn đơn là một dòng không ai
		đọc tới được."""
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({
				"doctype": nhat_ky.DOCTYPE, "customer": self.kh_a,
				"su_kien": nhat_ky.SK_DON_TAO, "vai": nhat_ky.VAI_HE_THONG,
				"thoi_diem": frappe.utils.now_datetime(),
			}).insert(ignore_permissions=True)

	def test_ghi_hong_KHONG_nem_loi_ra_ngoai(self):
		"""Ràng buộc tuyệt đối. Hàm này chạy ngay sau những chuyển trạng
		thái ĐÃ THÀNH CÔNG; ném lỗi ở đây là cuốn theo cả transaction và
		làm mất đúng thứ vừa làm được."""
		ten = nhat_ky.ghi(
			nhat_ky.SK_KHOA_GUI_DUYET, customer="_KHACH_KHONG_TON_TAI_",
			de_xuat=self._phieu(), vai=nhat_ky.VAI_KHOA,
		)
		self.assertIsNone(ten)
