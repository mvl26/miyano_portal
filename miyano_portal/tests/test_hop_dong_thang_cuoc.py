"""Luật phân định hợp đồng khung THẮNG CUỘC — `nguon_gia_theo_ma_cho_khach()`.

Từ spec 2026-10-09 phiếu đề xuất không còn hỏi hợp đồng, nên các bài từng
canh luật này qua `PortalDeXuatMua._suy_nguon_gia()` đã đi theo. Nhưng hàm
vẫn SỐNG: `gia_hdnt.dong_bo_khach` dùng nó để quyết hợp đồng nào được ghi
giá sang Price List của khách, `portal_mua_le` và các endpoint cũ của
`api/portal.py` cũng gọi nó. File này canh THẲNG hàm đó (Ruling R7), hai
luật không còn bài nào khác chạm tới:

  * trùng `to_date` thì `name` nhỏ hơn thắng (`gia_hdnt.THU_TU_PHAN_DINH`);
  * hợp đồng hết hạn ĐÚNG HÔM NAY vẫn còn hiệu lực (`to_date >= hôm nay`).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	nguon_gia_theo_ma_cho_khach,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"


def _don_bo_cu():
	"""Dọn Blanket Order `_TEST DX%` trước mỗi method (cùng khuôn
	`test_catalog_gop._don_bo_cu`): `FrappeTestCase` chỉ rollback một lần
	mỗi CLASS, nên hợp đồng của method trước vẫn "còn hiệu lực" ở method
	sau và sẽ chen vào phép phân định. Bản ghi đã nộp phải HUỶ trước khi
	xoá."""
	for r in frappe.get_all(
		"Blanket Order", filters={"customer": ["like", "_TEST DX%"]}, fields=["name", "docstatus"]
	):
		if r.docstatus == 1:
			frappe.get_doc("Blanket Order", r.name).cancel()
		frappe.delete_doc("Blanket Order", r.name, force=True, ignore_permissions=True)


class TestHopDongThangCuoc(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_bo_cu()
		self.kh_a = dung_fixture(self).kh_a

	def tearDown(self):
		frappe.set_user("Administrator")

	def _tao_item(self, ten):
		if not frappe.db.exists("Item", ten):
			frappe.get_doc({
				"doctype": "Item", "item_code": ten, "item_name": ten,
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"stock_uom": "Nos", "is_stock_item": 0,
			}).insert(ignore_permissions=True)
		return ten

	def _bo(self, item_code, to_date_offset, from_date_offset=0):
		"""Blanket Order SUBMIT thật ("còn hiệu lực" đòi `docstatus == 1`).
		`rate: 0` — hợp đồng chưa khai giá, để hook `on_submit` (`gia_hdnt.
		tu_hdnt`) không ghi `Item Price` nào: bài ở đây chỉ hỏi AI THẮNG."""
		doc = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": self.kh_a, "company": COMPANY,
			"from_date": frappe.utils.add_days(frappe.utils.today(), from_date_offset),
			"to_date": frappe.utils.add_days(frappe.utils.today(), to_date_offset),
			"items": [{"item_code": item_code, "qty": 5, "rate": 0}],
		}).insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def test_trung_to_date_thi_name_nho_hon_thang(self):
		"""Hai hợp đồng CÙNG `to_date` cho cùng một mã: không có `name asc`
		phá hoà thì MariaDB được trả thứ tự nào cũng đúng, và cùng một câu
		hỏi có thể ra hai hợp đồng khác nhau. Thêm một hợp đồng hết hạn
		MUỘN hơn với tên lớn nhất để chắc phép so là trên `name`, không phải
		"bản ghi tạo sau cùng".

		Dựng bản mang tên LỚN hơn TRƯỚC là không làm được (tên tự sinh tăng
		dần), nên bài này canh chiều sắp xếp: đảo `name asc` thành `name
		desc` trong `THU_TU_PHAN_DINH` thì nó đỏ."""
		ma = self._tao_item("_TEST DX THANG CUOC TRUNG NGAY")
		bo_1 = self._bo(ma, to_date_offset=50)
		bo_2 = self._bo(ma, to_date_offset=50)
		self._bo(ma, to_date_offset=90)
		self.assertLess(bo_1, bo_2, "tiền đề: tên tự sinh tăng dần")

		thang = nguon_gia_theo_ma_cho_khach(self.kh_a)
		self.assertEqual(thang.get(ma), bo_1)
		# Tất định: hỏi lại ra đúng câu trả lời đó.
		self.assertEqual(nguon_gia_theo_ma_cho_khach(self.kh_a).get(ma), bo_1)

	def test_het_han_dung_hom_nay_van_con_hieu_luc(self):
		"""Biên `to_date >= hôm nay`. Hợp đồng hết hạn ĐÚNG HÔM NAY vẫn được
		tính — đó là ngày bệnh viện gấp rút đặt nốt theo hợp đồng sắp hết.

		VẾ ÂM cùng bài: hợp đồng hết hạn HÔM QUA cho một mã khác thì không
		có mặt. Thiếu vế này, một bộ lọc bỏ hẳn điều kiện ngày vẫn qua."""
		ma_bien = self._tao_item("_TEST DX THANG CUOC HET HAN HOM NAY")
		ma_het = self._tao_item("_TEST DX THANG CUOC HET HAN HOM QUA")
		bo_bien = self._bo(ma_bien, to_date_offset=0, from_date_offset=-30)
		self._bo(ma_het, to_date_offset=-1, from_date_offset=-30)

		thang = nguon_gia_theo_ma_cho_khach(self.kh_a)
		self.assertEqual(thang.get(ma_bien), bo_bien)
		self.assertNotIn(ma_het, thang)
