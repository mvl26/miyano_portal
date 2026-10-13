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
from miyano_portal.tests.fixtures_de_xuat import dung_fixture, khai_gia

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
		# Spec 2026-10-12 §5 — phiếu còn mã chưa có giá nay sinh Quotation. Lớp
		# này đo ĐƠN sinh ra từ đường duyệt thật (`_phieu_da_duyet`), nên vật
		# tư có giá trong Price List của khách và đơn là đơn "Theo bảng giá".
		khai_gia(self.kh_a, self.item)
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
	# Final-fix I-2 — giá trị mặc định điền lúc GHI SỔ (`before_submit`), không
	# lúc lưu nháp: ERPNext đặt lại `posting_date`/`posting_time` về "bây giờ" ở
	# MỖI lần validate (trừ khi tick "Edit Posting Date and Time"), nên con số
	# điền ở lần lưu nháp đầu là giờ SOẠN phiếu — phiếu soạn chiều thứ Hai, ghi
	# sổ sáng thứ Ba sẽ báo khách "giao chiều thứ Hai".

	def _ngay_gio_ghi_so(self, dn):
		return frappe.utils.get_datetime(f"{dn.posting_date} {dn.posting_time}")

	def _lui_ngay_gio_ghi_so_cua_phieu_nhap(self, dn):
		"""Phiếu nháp "soạn từ hôm qua 15:00": lần validate kế tiếp (ghi sổ) sẽ
		đặt lại ngày giờ ghi sổ về bây giờ."""
		frappe.db.set_value("Delivery Note", dn.name, {
			"posting_date": frappe.utils.add_days(frappe.utils.today(), -1),
			"posting_time": "15:00:00",
		}, update_modified=False)
		dn.reload()

	def test_phieu_nhap_de_trong_ghi_so_moi_dien_theo_gio_ghi_so(self):
		"""Phiếu dựng ở server (mapper `make_delivery_note`) không đi qua form
		nên không có giá trị mặc định nào của form — hook điền, nhưng CHỈ lúc
		ghi sổ và theo ngày giờ ghi sổ của lúc đó."""
		dn = self._phieu_giao(self._don(), ghi_so=False)
		self.assertFalse(dn.custom_thoi_gian_giao, "nháp: chưa điền")
		self.assertFalse(
			frappe.db.get_value("Delivery Note", dn.name, "custom_thoi_gian_giao")
		)
		self._lui_ngay_gio_ghi_so_cua_phieu_nhap(dn)
		hom_qua = self._ngay_gio_ghi_so(dn)
		dn.save()   # lưu nháp thêm lần nữa vẫn không điền
		self.assertFalse(dn.custom_thoi_gian_giao)

		dn.submit()
		dn.reload()
		self.assertTrue(dn.custom_thoi_gian_giao)
		self.assertEqual(
			frappe.utils.get_datetime(dn.custom_thoi_gian_giao), self._ngay_gio_ghi_so(dn)
		)
		self.assertGreater(frappe.utils.get_datetime(dn.custom_thoi_gian_giao), hom_qua)
		self.assertEqual(
			frappe.utils.getdate(dn.custom_thoi_gian_giao),
			frappe.utils.getdate(frappe.utils.today()),
		)

	def test_phieu_giao_giu_thoi_gian_miyano_da_nhap(self):
		so = self._don()
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

		dn = make_delivery_note(so.name)
		dn.company = COMPANY
		dn.custom_thoi_gian_giao = "2026-10-12 09:30:00"
		dn.insert(ignore_permissions=True)
		self.assertEqual(str(dn.custom_thoi_gian_giao), "2026-10-12 09:30:00")
		dn.submit()
		dn.reload()
		self.assertEqual(str(dn.custom_thoi_gian_giao), "2026-10-12 09:30:00",
		                 "giá trị nhân viên gõ sống qua lúc ghi sổ")

	def test_phieu_tra_hang_cung_luat(self):
		"""Phiếu trả hàng (`is_return`) là một Delivery Note: nháp để trống, ghi
		sổ mới điền; không thừa hưởng giờ giao của phiếu gốc (`no_copy`)."""
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return

		goc_dn = self._phieu_giao(self._don())
		frappe.db.set_value(
			"Delivery Note", goc_dn.name, "custom_thoi_gian_giao", "2026-10-12 09:30:00"
		)
		tra = make_sales_return(goc_dn.name)
		tra.insert(ignore_permissions=True)

		def _don_phieu_tra():
			# `_don_phieu_giao_cu` của bài sau huỷ phiếu theo thứ tự bất kỳ; phiếu
			# gốc còn phiếu trả đã ghi sổ thì vấp `LinkExistsError`.
			frappe.set_user("Administrator")
			if frappe.db.get_value("Delivery Note", tra.name, "docstatus") == 1:
				frappe.get_doc("Delivery Note", tra.name).cancel()
			frappe.delete_doc("Delivery Note", tra.name, force=True, ignore_permissions=True)

		self.addCleanup(_don_phieu_tra)
		self.assertEqual(tra.is_return, 1)
		self.assertFalse(tra.custom_thoi_gian_giao)
		tra.submit()
		tra.reload()
		self.assertEqual(
			frappe.utils.get_datetime(tra.custom_thoi_gian_giao), self._ngay_gio_ghi_so(tra)
		)

	def test_hook_dang_ky_o_before_submit_khong_o_validate(self):
		"""Canh DÒNG ĐĂNG KÝ: mọi test khác chạy qua `submit()` thật, nhưng một
		lần dời hook về `validate` sẽ làm sống lại đúng lỗi "giờ soạn phiếu"."""
		ten = "miyano_portal.portal_thoi_gian_giao.dien_thoi_gian_giao"
		su_kien = frappe.get_hooks("doc_events")["Delivery Note"]
		self.assertIn(ten, su_kien.get("before_submit") or [])
		self.assertNotIn(ten, su_kien.get("validate") or [])

	def test_hook_khong_bao_gio_chan_viec_ghi_so(self):
		from unittest.mock import patch

		from miyano_portal import portal_thoi_gian_giao

		dn = self._phieu_giao(self._don(), ghi_so=False)
		with patch.object(
			portal_thoi_gian_giao, "thoi_gian_giao_cua_dn",
			side_effect=RuntimeError("giả lập"),
		):
			dn.submit()
		self.assertEqual(frappe.db.get_value("Delivery Note", dn.name, "docstatus"), 1)

	def test_thu_xuat_giao_luc_ghi_so_thay_thoi_gian_vua_dien(self):
		"""Notification "Portal - Xuất giao" (event Submit) chạy ở `on_submit`,
		SAU `before_submit`: thư gửi đi lúc ghi sổ phải mang giờ vừa điền. Dựng
		thư ĐÚNG lúc Frappe đánh giá thông báo, trên chính document nó nhận."""
		from unittest.mock import patch

		from frappe.email.doctype.notification import notification

		that = notification.evaluate_alert
		thu = []

		def bat(doc, alert, event):
			if doc.doctype == "Delivery Note" and (
				alert if isinstance(alert, str) else alert.name
			) == "Portal - Xuất giao":
				thu.append((event, _dung_thu("Portal - Xuất giao", doc)))
			return that(doc, alert, event)

		dn = self._phieu_giao(self._don(), ghi_so=False)
		self._lui_ngay_gio_ghi_so_cua_phieu_nhap(dn)
		with patch.object(notification, "evaluate_alert", side_effect=bat):
			dn.submit()
		self.assertEqual([e for e, _ in thu], ["Submit"])
		gio = frappe.utils.format_datetime(self._ngay_gio_ghi_so(dn), "dd/MM/yyyy HH:mm")
		self.assertIn(f"Thời gian giao hàng: {gio}", thu[0][1])
		self.assertIn(frappe.utils.getdate(frappe.utils.today()).strftime("%d/%m/%Y"), thu[0][1])

	# ---- Dọn giá trị tự điền cũ trên phiếu NHÁP (patch v1_41) --------------

	def _dat_bang_ngay_gio_ghi_so(self, dn):
		frappe.db.sql(
			"""update `tabDelivery Note`
			   set custom_thoi_gian_giao = timestamp(posting_date, posting_time)
			   where name = %s""", dn.name)

	def test_patch_xoa_gia_tri_tu_dien_tren_phieu_nhap(self):
		from miyano_portal.patches.v1_41 import gia_theo_price_list as patch

		tu_dien = self._phieu_giao(self._don(), ghi_so=False)
		self._dat_bang_ngay_gio_ghi_so(tu_dien)
		go_tay = self._phieu_giao(self._don(), ghi_so=False)
		frappe.db.set_value("Delivery Note", go_tay.name, "custom_thoi_gian_giao",
		                    "2026-10-12 09:30:00", update_modified=False)
		da_ghi_so = self._phieu_giao(self._don())
		self._dat_bang_ngay_gio_ghi_so(da_ghi_so)
		truoc = frappe.db.get_value(
			"Delivery Note", da_ghi_so.name, ["custom_thoi_gian_giao", "modified"])
		sua_luc = frappe.db.get_value("Delivery Note", tu_dien.name, "modified")

		def gia_tri(dn):
			return frappe.db.get_value("Delivery Note", dn.name, "custom_thoi_gian_giao")

		self.assertTrue(gia_tri(tu_dien))
		so_phieu = patch.don_thoi_gian_giao_tu_dien_tren_phieu_nhap()
		self.assertGreaterEqual(so_phieu, 1)
		self.assertIsNone(gia_tri(tu_dien), "nháp tự điền: xoá để lúc ghi sổ điền lại")
		self.assertEqual(
			frappe.db.get_value("Delivery Note", tu_dien.name, "modified"), sua_luc,
			"không phải một lần ai đó sửa phiếu")
		self.assertEqual(str(gia_tri(go_tay)), "2026-10-12 09:30:00", "nháp gõ tay: giữ")
		self.assertEqual(
			frappe.db.get_value(
				"Delivery Note", da_ghi_so.name, ["custom_thoi_gian_giao", "modified"]),
			truoc, "phiếu đã ghi sổ: không viết lại")

		self.assertEqual(patch.don_thoi_gian_giao_tu_dien_tren_phieu_nhap(), 0, "chạy lại")

		# Phiếu nháp vừa được dọn: ghi sổ thì điền theo giờ ghi sổ.
		tu_dien.reload()
		tu_dien.submit()
		tu_dien.reload()
		self.assertEqual(
			frappe.utils.get_datetime(tu_dien.custom_thoi_gian_giao),
			self._ngay_gio_ghi_so(tu_dien),
		)

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
