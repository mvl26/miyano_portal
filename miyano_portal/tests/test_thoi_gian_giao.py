"""Quản lý thời gian giao hàng (09/10/2026).

Ba lời hứa với khách, mỗi lời một nguồn:

  * **Dự kiến giao theo từng mặt hàng** — `Sales Order Item.delivery_date`,
    CHỈ khi Miyano đã xác nhận đơn. Trước mốc đó con số trên dòng là "ngày
    cần" do chính khách gõ lúc đặt; in nó ra dưới chữ "Dự kiến giao" là để
    Miyano cam kết một ngày mình chưa hề xem.
  * **Thời gian giao chính xác** — `Delivery Note.custom_thoi_gian_giao`
    (ngày + giờ) do Miyano nhập trên phiếu giao. `posting_date` là ngày GHI
    SỔ, không phải lúc hàng tới nơi.
  * **Email** — hai thư "Đơn xác nhận" và "Xuất giao" nói đúng hai con số
    trên, không một bản tính riêng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import de_xuat, portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.setup.install_notifications import DEFS
from miyano_portal.tests import test_chi_tiet_gop as goc
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"


def _mau_thu(ten: str) -> str:
	return next(d["message"] for d in DEFS if d["name"] == ten)


def _dung_thu(ten: str, doc) -> str:
	"""Dựng thư bằng ĐÚNG context mà doctype `Notification` dùng lúc gửi —
	không tự chế một context rộng hơn rồi đo lại chính nó."""
	from frappe.email.doctype.notification.notification import get_context

	return frappe.render_template(_mau_thu(ten), get_context(doc))


def _don_phieu_giao_cu():
	"""Huỷ phiếu giao TRƯỚC khi `_don_phieu_cu` huỷ đơn — đơn còn phiếu giao
	đã ghi sổ thì `cancel()` vấp `LinkExistsError`. Rollback của
	`FrappeTestCase` chỉ chạy MỘT lần cho cả class, nên phiếu của test trước
	vẫn còn đó khi test sau dọn."""
	for r in frappe.get_all(
		"Delivery Note", filters={"customer": ["like", "_TEST DX%"]},
		fields=["name", "docstatus"],
	):
		if r.docstatus == 1:
			frappe.get_doc("Delivery Note", r.name).cancel()
		frappe.delete_doc("Delivery Note", r.name, force=True, ignore_permissions=True)


class _Base(FrappeTestCase):
	_thanh_vien = goc.TestChiTietGopBackend._thanh_vien
	_phieu_da_duyet = goc.TestChiTietGopBackend._phieu_da_duyet

	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_giao_cu()
		goc._don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item
		self.quan_ly = self._thanh_vien("tgg.ql@demo.miyano", "Quản lý", None)
		self.nhan_vien = self._thanh_vien(
			"tgg.nv@demo.miyano", "Nhân viên khoa", self.khoa_a
		)
		self.ngay_du_kien = frappe.utils.getdate(
			frappe.utils.add_days(frappe.utils.today(), 5)
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _don(self, xac_nhan=True):
		so = frappe.get_doc({
			"doctype": "Sales Order", "customer": self.kh_a, "company": COMPANY,
			"transaction_date": frappe.utils.today(),
			"delivery_date": self.ngay_du_kien,
			"items": [{
				"item_code": self.item, "qty": 4, "rate": 1000,
				"delivery_date": self.ngay_du_kien,
			}],
		}).insert(ignore_permissions=True)
		if xac_nhan:
			so.submit()
		return so

	def _phieu_giao(self, so, ghi_so=True):
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

		dn = make_delivery_note(so.name)
		dn.company = COMPANY
		dn.insert(ignore_permissions=True)
		if ghi_so:
			dn.submit()
		return dn

	def _track(self, so_name):
		frappe.set_user(self.quan_ly)
		try:
			return portal.portal_order_track(order=so_name)
		finally:
			frappe.set_user("Administrator")


class TestNgayGiaoDuKienTheoDong(_Base):
	def test_don_da_xac_nhan_tra_ngay_du_kien_tung_dong(self):
		so = self._don(xac_nhan=True)
		dong = self._track(so.name)["items"][0]
		self.assertEqual(
			frappe.utils.getdate(dong["ngay_giao_du_kien"]), self.ngay_du_kien
		)

	def test_don_chua_xac_nhan_KHONG_tra_ngay_du_kien(self):
		"""Ngày trên đơn nháp là "ngày cần" của KHÁCH — chưa phải lời hứa
		của Miyano."""
		so = self._don(xac_nhan=False)
		dong = self._track(so.name)["items"][0]
		self.assertIn("ngay_giao_du_kien", dong)
		self.assertIsNone(dong["ngay_giao_du_kien"])

	def test_chi_tiet_phieu_tra_ngay_du_kien_theo_dong(self):
		"""Bảng mặt hàng lấy dòng từ PHIẾU khi có phiếu — thiếu phép nối ở
		`de_xuat_chi_tiet` thì cột mới trống trên đúng những đơn đi qua
		luồng duyệt, tức gần như mọi đơn mới."""
		phieu = self._phieu_da_duyet(so_luong=10)
		so = frappe.get_doc("Sales Order", phieu.sales_order)

		frappe.set_user(self.quan_ly)
		dong = next(
			d for d in de_xuat.de_xuat_chi_tiet(ten=phieu.name)["items"]
			if d["item_code"] == self.item
		)
		frappe.set_user("Administrator")
		self.assertEqual(so.docstatus, 0)
		self.assertIsNone(dong["ngay_giao_du_kien"])

		so.delivery_date = self.ngay_du_kien
		for r in so.items:
			r.delivery_date = self.ngay_du_kien
		so.flags.ignore_permissions = True
		so.submit()

		frappe.set_user(self.quan_ly)
		dong = next(
			d for d in de_xuat.de_xuat_chi_tiet(ten=phieu.name)["items"]
			if d["item_code"] == self.item
		)
		self.assertEqual(
			frappe.utils.getdate(dong["ngay_giao_du_kien"]), self.ngay_du_kien
		)


class TestThoiGianGiaoTrenPhieuGiao(_Base):
	def test_phieu_giao_tu_dien_thoi_gian_giao_khi_de_trong(self):
		"""Phiếu dựng ở server (mapper `make_delivery_note`) không đi qua
		form nên không có giá trị mặc định nào của form."""
		dn = self._phieu_giao(self._don(), ghi_so=False)
		self.assertTrue(dn.custom_thoi_gian_giao)
		self.assertEqual(
			frappe.utils.getdate(dn.custom_thoi_gian_giao),
			frappe.utils.getdate(dn.posting_date),
		)

	def test_phieu_giao_giu_thoi_gian_miyano_da_nhap(self):
		so = self._don()
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

		dn = make_delivery_note(so.name)
		dn.company = COMPANY
		dn.custom_thoi_gian_giao = "2026-10-12 09:30:00"
		dn.insert(ignore_permissions=True)
		self.assertEqual(str(dn.custom_thoi_gian_giao), "2026-10-12 09:30:00")

	def test_order_track_tra_thoi_gian_giao_cua_tung_dot(self):
		so = self._don()
		dn = self._phieu_giao(so)
		frappe.db.set_value(
			"Delivery Note", dn.name, "custom_thoi_gian_giao", "2026-10-12 09:30:00"
		)
		kq = self._track(so.name)
		self.assertEqual(str(kq["deliveries"][0]["thoi_gian_giao"]), "2026-10-12 09:30:00")
		self.assertEqual(str(kq["dot_giao"][0]["thoi_gian_giao"]), "2026-10-12 09:30:00")

	def test_phieu_cu_chua_co_thoi_gian_giao_lui_ve_ngay_ghi_so(self):
		"""Phiếu giao lập TRƯỚC bản này không có giá trị — cổng không được
		để trống đợt giao đó."""
		so = self._don()
		dn = self._phieu_giao(so)
		frappe.db.set_value("Delivery Note", dn.name, "custom_thoi_gian_giao", None)
		frappe.db.set_value("Delivery Note", dn.name, "posting_time", "14:05:00")
		kq = self._track(so.name)
		self.assertEqual(
			str(kq["deliveries"][0]["thoi_gian_giao"]),
			f"{dn.posting_date} 14:05:00",
		)

	def test_man_kiem_hang_doc_cung_ngay_giao_voi_man_don(self):
		"""Hai màn nói về CÙNG một đợt giao không được ra hai ngày."""
		so = self._don()
		dn = self._phieu_giao(so)
		frappe.db.set_value(
			"Delivery Note", dn.name, "custom_thoi_gian_giao", "2026-10-12 09:30:00"
		)
		frappe.set_user(self.quan_ly)
		kq = portal.portal_kiem_hang_get(dn.name)
		self.assertEqual(str(kq["ngay_giao"]), "2026-10-12")


class TestEmailCoThoiGianGiao(_Base):
	def test_thu_xac_nhan_don_neu_ngay_du_kien_tung_mat_hang(self):
		so = self._don()
		thu = _dung_thu("Portal - Đơn xác nhận", so)
		self.assertIn(self.item, thu)
		self.assertIn(self.ngay_du_kien.strftime("%d/%m/%Y"), thu)

	def test_thu_xac_nhan_don_KHONG_liet_ke_dong_giu_cho(self):
		"""Cổng đã lọc dòng giữ chỗ khỏi phía khách — thư không được phơi
		nó ra bằng đường khác."""
		so = self._don()
		so.items[0].item_code = ITEM_GIU_CHO
		so.items[0].item_name = "DONG GIU CHO NOI BO"
		thu = _dung_thu("Portal - Đơn xác nhận", so)
		self.assertNotIn("DONG GIU CHO NOI BO", thu)
		self.assertNotIn(ITEM_GIU_CHO, thu)

	def test_thu_xuat_giao_neu_thoi_gian_giao(self):
		dn = self._phieu_giao(self._don(), ghi_so=False)
		dn.custom_thoi_gian_giao = "2026-10-12 09:30:00"
		thu = _dung_thu("Portal - Xuất giao", dn)
		self.assertIn("12/10/2026 09:30", thu)

	def test_patch_cap_nhat_hai_thu_da_cai_tren_site(self):
		"""`install_portal_notifications()` BỎ QUA bản ghi đã tồn tại — site
		đang chạy chỉ nhận nội dung mới qua patch."""
		from miyano_portal.patches.v1_40 import them_thoi_gian_giao_hang

		for ten in ("Portal - Đơn xác nhận", "Portal - Xuất giao"):
			frappe.db.set_value("Notification", ten, "message", "ban cu")
		them_thoi_gian_giao_hang.execute()
		for ten in ("Portal - Đơn xác nhận", "Portal - Xuất giao"):
			self.assertEqual(
				frappe.db.get_value("Notification", ten, "message"), _mau_thu(ten)
			)
