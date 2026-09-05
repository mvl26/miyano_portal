"""Huy hiệu "Có hàng chờ báo giá" trên màn chi tiết đơn.

Huy hiệu này CÓ trên `OrderDetail.vue` của `main`, và rơi mất khi nhánh
`feat/de-xuat-mua` gộp hai màn chi tiết làm một (xoá `OrderDetail.vue`).
Chủ đầu tư yêu cầu thêm lại 05/09/2026.

KHÔNG dựng lại y nguyên bản cũ, và đây là điểm của cả file test này. Bản cũ
bật theo `loai_don === "Mua lẻ"` — tức theo DẤU GHI LẠI ĐƯỜNG đơn đã đi
(`portal_mua_le.di_vong_bao_gia`), không phải theo tình trạng giá lúc này.
Nên nó vẫn hiện "Có hàng chờ báo giá" SAU KHI Miyano đã điền đủ giá: một
cái nhãn nói sai về chính đơn nó đang gắn vào.

Trớ trêu là commit đưa huy hiệu đó lên `main` tên là *"nhãn thôi nói dối
'Mua lẻ'"* (20677ff) — nó sửa nhãn `Mua lẻ` thành `Có hàng chờ báo giá`
nhưng vẫn giữ nguyên vị ngữ cũ, nên chỉ đổi lời nói dối chứ chưa hết dối.

Bản này hỏi ĐÚNG câu mà nhãn nói: *đơn còn dòng nào chưa có giá không?*

VÀ SERVER TRẢ LỜI, KHÔNG PHẢI CLIENT SUY LẠI — Ruling #19 của nhánh này:
một bản sao logic ở client đã từng lệch khỏi server và làm đơn bị từ chối
hiện badge xanh "Đã duyệt". Client chỉ đọc một khoá boolean.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal


class TestCoDongChoBaoGia(FrappeTestCase):
	"""`_co_dong_cho_bao_gia(so)` — vị ngữ thuần, không chạm CSDL."""

	def _so(self, items=None, dat_ngoai=None):
		return frappe._dict(
			items=[frappe._dict(d) for d in (items or [])],
			custom_dat_ngoai=[frappe._dict(d) for d in (dat_ngoai or [])],
		)

	def test_con_dong_gia_0_thi_TRUE(self):
		so = self._so(items=[{"item_code": "A", "rate": 0}, {"item_code": "B", "rate": 1200}])
		self.assertTrue(portal._co_dong_cho_bao_gia(so))

	def test_moi_dong_deu_co_gia_thi_FALSE(self):
		"""Đây là ca mà bản cũ TRẢ SAI.

		Đơn đi qua vòng báo giá, Miyano đã điền đủ giá — không còn gì "chờ
		báo giá" nữa, nhưng bản cũ vẫn bật huy hiệu vì nó đọc dấu đường đi.
		"""
		so = self._so(items=[{"item_code": "A", "rate": 1000}, {"item_code": "B", "rate": 1200}])
		self.assertFalse(portal._co_dong_cho_bao_gia(so))

	def test_dong_giu_cho_khong_tinh(self):
		"""`HANG-DAT-NGOAI` là dòng GIỮ CHỖ kỹ thuật, luôn giá 0 và không bao
		giờ là hàng thật — tính nó vào là huy hiệu sáng vĩnh viễn trên mọi
		đơn có dòng đặt ngoài, kể cả khi Miyano đã báo giá xong tất cả."""
		from miyano_portal.portal_mua_le import ITEM_GIU_CHO

		so = self._so(items=[{"item_code": ITEM_GIU_CHO, "rate": 0},
		                     {"item_code": "B", "rate": 1200}])
		self.assertFalse(portal._co_dong_cho_bao_gia(so))

	def test_dat_ngoai_chua_khop_ma_thi_TRUE(self):
		"""Dòng khách gõ tay mà Miyano chưa tìm ra mã CHÍNH LÀ hàng đang chờ
		báo giá — bỏ vế này thì đơn toàn hàng gõ tay không bao giờ sáng huy
		hiệu, đúng lúc nó cần sáng nhất."""
		so = self._so(items=[{"item_code": "B", "rate": 1200}],
		              dat_ngoai=[{"ten_hang": "Găng tay", "da_xu_ly": 0}])
		self.assertTrue(portal._co_dong_cho_bao_gia(so))

	def test_dat_ngoai_da_khop_het_thi_FALSE(self):
		so = self._so(items=[{"item_code": "B", "rate": 1200}],
		              dat_ngoai=[{"ten_hang": "Găng tay", "da_xu_ly": 1}])
		self.assertFalse(portal._co_dong_cho_bao_gia(so))

	def test_don_rong_thi_FALSE(self):
		self.assertFalse(portal._co_dong_cho_bao_gia(self._so()))


class TestGiaoDienHuyHieu(FrappeTestCase):
	"""Lưới regex — không có hạ tầng test JS."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from pathlib import Path

		import re

		goc = Path(frappe.get_app_path("miyano_portal")).parent
		tho = (goc / "frontend" / "src" / "views" / "ChiTietYeuCau.vue").read_text(
			encoding="utf-8"
		)
		# LỘT CHÚ THÍCH HTML TRƯỚC KHI SOI. Chính chú thích giải thích huy
		# hiệu này có chứa chuỗi "Có hàng chờ báo giá" lẫn chữ "Mua lẻ", nên
		# soi văn bản thô sẽ khớp vào LỜI GIẢI THÍCH thay vì chỗ RENDER —
		# bài tự đỏ (hoặc tệ hơn, tự xanh) vì chính chú thích của mình.
		cls.man = re.sub(r"<!--.*?-->", "", tho, flags=re.S)

	def test_man_chi_tiet_render_huy_hieu(self):
		self.assertIn("Có hàng chờ báo giá", self.man)

	def test_doc_khoa_SERVER_tra_khong_tu_suy_tu_loai_don(self):
		"""Huy hiệu phải bật theo khoá server trả, KHÔNG theo `loai_don`.

		Suy lại ở client là tái diễn đúng Ruling #19 (bản sao `giai_doan` ở
		client đã lệch và làm đơn bị từ chối hiện badge xanh "Đã duyệt"), VÀ
		đưa lại đúng lời nói dối mà bản này sinh ra để bỏ.
		"""
		i = self.man.find("Có hàng chờ báo giá")
		self.assertNotEqual(i, -1)
		quanh = self.man[max(0, i - 400):i]
		self.assertIn(
			"co_dong_cho_bao_gia", quanh,
			"Huy hiệu không đọc khoá `co_dong_cho_bao_gia` do server trả",
		)
		self.assertNotIn(
			"Mua lẻ", quanh,
			"Huy hiệu đang suy lại từ `loai_don === 'Mua lẻ'` — đó là DẤU "
			"đường đơn đã đi, không phải tình trạng giá lúc này",
		)

	def test_endpoint_tra_khoa_do(self):
		import inspect

		self.assertIn(
			'"co_dong_cho_bao_gia"', inspect.getsource(portal.portal_order_track),
			"`portal_order_track` không trả khoá này — màn hình có người tiêu "
			"thụ mà không có người sinh",
		)
