"""Bốn lỗi lộ ra khi chạy yêu cầu báo giá trên trình duyệt thật (13/10/2026).

P-1 chi tiết đơn "Theo báo giá" thiếu mặt hàng vốn là dòng khách gõ tay;
P-2 Desk còn cho tạo đơn thứ hai / huỷ báo giá của cổng đã có đơn;
P-3 khối "thông tin khách khai" rơi vào tab "Liên kết";
P-6 lời đòi lý do từ chối không nói nhập ở đâu.
"""

from pathlib import Path

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, nowdate

from miyano_portal import bao_gia
from miyano_portal.api import portal
from miyano_portal.tests.nen_bao_gia import NenBaoGia

JS = Path(frappe.get_app_path("miyano_portal")) / "public" / "js"

DONG_GO_TAY = {
	"ten_hang": "Găng tay thử không bột", "dvt": "Hộp", "so_luong": 2,
	"hang_san_xuat": "Hãng thử", "ghi_chu": "Loại đang dùng",
}

# Đúng những khoá `portal_order_track` vốn trả cho một dòng `dat_ngoai`.
KHOA_DAT_NGOAI = {
	"name", "ten_hang", "dvt", "so_luong", "ghi_chu", "da_xu_ly", "item_khop",
	"model_ma", "hang_san_xuat", "nuoc_san_xuat", "quy_cach", "ncc_hien_tai",
	"gia_hien_tai", "anh", "khong_co_anh", "mo_ta_nhan_dang",
}


def _bo_chu_thich(nguon: str) -> str:
	return "\n".join(d for d in nguon.splitlines() if not d.strip().startswith("//"))


class NenSoatTrinhDuyet(NenBaoGia):
	@classmethod
	def setUpClass(cls):
		cls.addClassCleanup(
			frappe.clear_document_cache, "Workflow", "Sales Order - Client Portal"
		)
		super().setUpClass()
		from miyano_portal.patches.v1_41 import gia_theo_price_list

		gia_theo_price_list.mo_rong_workflow()

	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("stdbg.ql@demo.miyano", self.kh_a)

	def _voi_khach(self, ham, *a, **kw):
		frappe.set_user(self.ql)
		try:
			return ham(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def _don_tu_bao_gia_co_dong_go_tay(self):
		"""Kịch bản của lỗi P-1: phiếu có 1 mã + 1 dòng gõ tay; Miyano khớp mã
		dòng gõ tay trên báo giá, điền giá, gửi; khách đồng ý. Trả
		`(Sales Order, Quotation, phiếu)`."""
		phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"trang_thai": "Đã duyệt", "ngay_can": add_days(nowdate(), 10),
			"items": [{"item_code": self.item_boi_so, "so_luong_de_xuat": 20, "so_luong_duyet": 20}],
			"dat_ngoai": [dict(DONG_GO_TAY)],
		}).insert(ignore_permissions=True)
		kq = bao_gia.tao_bao_gia(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 20}],
			dat_ngoai=[dict(DONG_GO_TAY)], request_id=frappe.generate_hash(length=12),
			khoa_phong=self.khoa_huyethoc,
		)
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		bg.custom_de_xuat = phieu.name
		bg.custom_dat_ngoai[0].item_khop = self.item_ngoai
		bg.save()
		bg.reload()
		for d in bg.items:
			if not d.rate:
				d.rate = d.price_list_rate = 7000
		bg.save()
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "bao_gia", bg.name)
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		ten = self._voi_khach(bao_gia.dong_y, bg.name)["sales_order"]
		return frappe.get_doc("Sales Order", ten), frappe.get_doc("Quotation", bg.name), phieu


class TestChiTietDonDuMatHang(NenSoatTrinhDuyet):
	"""P-1 — mọi item_code của Sales Order phải có đường vào bảng chi tiết."""

	def test_track_tra_dong_go_tay_da_khop_cua_bao_gia_nguon(self):
		so, _bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		self.assertEqual(
			{d.item_code for d in so.items}, {self.item_boi_so, self.item_ngoai}
		)
		# Thiết kế: đơn sinh ra KHÔNG mang dòng gõ tay (`no_copy`).
		self.assertFalse(so.get("custom_dat_ngoai"))

		kq = self._voi_khach(portal.portal_order_track, so.name)
		self.assertEqual(len(kq["dat_ngoai"]), 1)
		dong = kq["dat_ngoai"][0]
		self.assertEqual(dong["item_khop"], self.item_ngoai)
		self.assertTrue(dong["da_xu_ly"])
		self.assertEqual(dong["ten_hang"], DONG_GO_TAY["ten_hang"])
		self.assertEqual(dong["so_luong"], 2)
		self.assertEqual(dong["hang_san_xuat"], "Hãng thử")

	def test_moi_ma_tren_don_deu_co_duong_vao_bang_chi_tiet(self):
		"""Bảng dựng từ dòng của phiếu + dòng gõ tay đã khớp (`dat_ngoai`) +
		mọi dòng còn lại của `items` (`dong-bang-mat-hang.js`). Ở phía server
		bất biến là: `items` trả ĐỦ mọi mã của đơn, và mã không có trên phiếu
		vốn là dòng gõ tay thì đi kèm thứ khách đã khai."""
		so, _bg, phieu = self._don_tu_bao_gia_co_dong_go_tay()
		kq = self._voi_khach(portal.portal_order_track, so.name)
		tren_don = {d.item_code for d in so.items}
		self.assertEqual({d["item_code"] for d in kq["items"]}, tren_don)
		by_ma = {d["item_code"]: d for d in kq["items"]}
		self.assertEqual(by_ma[self.item_ngoai]["qty"], 2)
		self.assertEqual(by_ma[self.item_ngoai]["rate"], 54000)
		self.assertEqual(by_ma[self.item_ngoai]["amount"], 108000)
		tren_phieu = {d.item_code for d in phieu.items}
		da_khop = {d["item_khop"] for d in kq["dat_ngoai"] if d["da_xu_ly"]}
		self.assertEqual(tren_don - tren_phieu, da_khop)

	def test_khong_lo_gi_cua_bao_gia_ngoai_cac_khoa_von_co(self):
		so, bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		kq = self._voi_khach(portal.portal_order_track, so.name)
		for dong in kq["dat_ngoai"]:
			self.assertEqual(set(dong), KHOA_DAT_NGOAI)
		self.assertNotIn(bg.name, frappe.as_json(kq["dat_ngoai"]))

	def test_dong_khop_ma_khong_con_tren_don_thi_khong_tra(self):
		"""Nhân viên bỏ mặt hàng khỏi đơn nháp: dòng gõ tay ứng với nó không
		được dựng lại thành một dòng hàng ma trên bảng của khách."""
		so, _bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		so.items = [d for d in so.items if d.item_code != self.item_ngoai]
		so.save()
		kq = self._voi_khach(portal.portal_order_track, so.name)
		self.assertEqual(kq["dat_ngoai"], [])

	def test_bao_gia_cua_khach_khac_khong_bao_gio_duoc_doc(self):
		so, bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		self.assertEqual(bao_gia.bao_gia_cua_don(so), bg.name)
		gia_mao = frappe._dict(
			customer=self.kh_b, custom_loai_don=bao_gia.LOAI_DON_THEO_BAO_GIA,
			custom_request_id=so.custom_request_id,
		)
		self.assertIsNone(bao_gia.bao_gia_cua_don(gia_mao))
		mua_le = frappe._dict(
			customer=self.kh_a, custom_loai_don="Mua lẻ",
			custom_request_id=so.custom_request_id,
		)
		self.assertIsNone(bao_gia.bao_gia_cua_don(mua_le))

	def test_mau_in_xac_nhan_don_hang_du_hai_dong(self):
		so, _bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		html = frappe.get_print("Sales Order", so.name, print_format="Miyano - Xác nhận đơn hàng")
		for ma in (self.item_boi_so, self.item_ngoai):
			self.assertIn(ma, html)


CHIN_TRUONG = {
	"model_ma": "NBG-100-M", "hang_san_xuat": "Ansell", "nuoc_san_xuat": "Malaysia",
	"quy_cach": "hộp 100 chiếc", "ncc_hien_tai": "Công ty ABC", "gia_hien_tai": 185000.0,
	"anh": "", "khong_co_anh": True,
	"mo_ta_nhan_dang": "Hộp màu xanh dương, in chữ Nitrile Exam Gloves",
}


class TestChinTruongQuaTrack(NenSoatTrinhDuyet):
	"""Chín trường CR-03 của dòng gõ tay đi qua `portal_order_track` với GIÁ
	TRỊ THẬT, ở cả hai nguồn dòng của `_dat_ngoai_cho_khach`. Vế hành vi của
	`test_cr03_dat_ngoai.TestOrderTrackTraDuChinTruong` (vế đó soi mã nguồn)."""

	def _dong(self):
		return {
			"ten_hang": "Găng tay chín trường", "dvt": "Hộp", "so_luong": 3,
			**{**CHIN_TRUONG, "khong_co_anh": 1},
		}

	def _khang_dinh(self, dong):
		self.assertEqual(dong["ten_hang"], "Găng tay chín trường")
		for khoa, gt in CHIN_TRUONG.items():
			with self.subTest(truong=khoa):
				self.assertEqual(dong[khoa], gt)

	def test_don_mua_le_cu_dong_tu_chinh_don(self):
		from miyano_portal import dat_hang

		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[], dat_ngoai=[self._dong()],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.custom_loai_don, "Mua lẻ")
		self.assertEqual(len(so.custom_dat_ngoai), 1)
		tra = self._voi_khach(portal.portal_order_track, so.name)
		self.assertEqual(len(tra["dat_ngoai"]), 1)
		self._khang_dinh(tra["dat_ngoai"][0])
		self.assertFalse(tra["dat_ngoai"][0]["da_xu_ly"])

	def test_don_theo_bao_gia_dong_tu_bao_gia_nguon(self):
		kq = bao_gia.tao_bao_gia(
			self.kh_a, items=[], dat_ngoai=[self._dong()],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		bg.custom_dat_ngoai[0].item_khop = self.item_ngoai
		bg.save()
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		so = frappe.get_doc(
			"Sales Order", self._voi_khach(bao_gia.dong_y, bg.name)["sales_order"]
		)
		self.assertEqual(so.custom_loai_don, bao_gia.LOAI_DON_THEO_BAO_GIA)
		self.assertFalse(so.get("custom_dat_ngoai"))
		tra = self._voi_khach(portal.portal_order_track, so.name)
		self.assertEqual(len(tra["dat_ngoai"]), 1)
		self._khang_dinh(tra["dat_ngoai"][0])
		self.assertEqual(tra["dat_ngoai"][0]["item_khop"], self.item_ngoai)


class TestChotBaoGiaDaCoDon(NenSoatTrinhDuyet):
	"""P-2 — báo giá của cổng đã có đơn: không đơn thứ hai, không huỷ báo giá."""

	def _don_thu_hai(self, bg):
		from erpnext.selling.doctype.quotation.quotation import make_sales_order

		so2 = make_sales_order(bg.name)
		so2.delivery_date = add_days(nowdate(), 10)
		for d in so2.items:
			d.delivery_date = so2.delivery_date
		return so2

	def test_khong_tao_duoc_don_thu_hai_tu_bao_gia_cua_cong(self):
		so, bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		so2 = self._don_thu_hai(bg)
		# ERPNext chỉ trừ số "đã đặt" theo đơn ĐÃ Submit: đơn đầu còn nháp nên
		# bản thứ hai mang đủ mọi dòng.
		self.assertEqual(len(so2.items), 2)
		with self.assertRaisesRegex(frappe.ValidationError, so.name):
			so2.insert()
		self.assertEqual(
			frappe.db.count("Sales Order Item", {"prevdoc_docname": bg.name, "docstatus": ["<", 2]}),
			2,
		)

	def test_don_da_bi_tu_choi_van_khong_tao_tay_don_khac(self):
		"""Đơn của báo giá cổng chỉ sinh ra khi khách đồng ý: đơn đó bị Miyano
		từ chối cũng không mở đường tạo tay một đơn khác từ cùng báo giá."""
		so, bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		self._tu_choi_don(so)
		so2 = self._don_thu_hai(bg)
		with self.assertRaisesRegex(frappe.ValidationError, so.name):
			so2.insert()

	def test_keo_dong_bao_gia_cong_vao_don_nhap_da_luu_bi_tu_choi(self):
		"""«Lấy mặt hàng từ → Báo giá» trên một đơn nháp ĐÃ LƯU không đi qua
		`insert`: chốt phải đứng ở `validate`."""
		from erpnext.selling.doctype.quotation.quotation import make_sales_order

		from miyano_portal import dat_hang

		so, bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_ngoai, "qty": 10}],
			request_id=frappe.generate_hash(length=12),
		)
		nhap = frappe.get_doc("Sales Order", kq["sales_order"])
		nhap = make_sales_order(bg.name, target_doc=nhap)
		self.assertTrue([d for d in nhap.items if d.get("prevdoc_docname") == bg.name])
		with self.assertRaisesRegex(frappe.ValidationError, so.name):
			nhap.save()
		self.assertFalse(frappe.db.exists(
			"Sales Order Item", {"parent": kq["sales_order"], "prevdoc_docname": bg.name}
		))

	def test_don_hop_le_van_luu_va_xac_nhan_duoc(self):
		so, _bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		so.save()
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual(so.docstatus, 1)

	def test_keo_dong_bao_gia_noi_bo_vao_don_nhap_van_duoc(self):
		from erpnext.selling.doctype.quotation.quotation import make_sales_order

		from miyano_portal import dat_hang

		bg = self._bao_gia_tho(nguon="Nội bộ")
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		bg = apply_workflow(bg, bao_gia.HD_GHI_NHAN)
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_ngoai, "qty": 10}],
			request_id=frappe.generate_hash(length=12),
		)
		nhap = make_sales_order(bg.name, target_doc=frappe.get_doc("Sales Order", kq["sales_order"]))
		nhap.save()
		self.assertTrue([d for d in nhap.items if d.get("prevdoc_docname") == bg.name])

	def test_bao_gia_noi_bo_van_tao_don_binh_thuong(self):
		bg = self._bao_gia_tho(nguon="Nội bộ")
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		bg = apply_workflow(bg, bao_gia.HD_GHI_NHAN)
		self.assertEqual(bg.docstatus, 1)
		so = self._don_thu_hai(bg)
		so.insert()
		self.assertEqual(so.items[0].prevdoc_docname, bg.name)
		self.assertTrue(frappe.db.exists("Sales Order", so.name))

	def test_ban_sua_doi_va_ban_sao_khong_bi_chan(self):
		so, bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		# Bản «Amend» của CHÍNH đơn hợp lệ, kể cả khi mã yêu cầu không đi theo.
		sua_doi = frappe.copy_doc(so)
		sua_doi.amended_from = so.name
		sua_doi.custom_request_id = None
		self.assertTrue([d for d in sua_doi.items if d.get("prevdoc_docname") == bg.name])
		bao_gia.chan_don_thu_hai_tu_bao_gia_cong(sua_doi)
		# `amended_from` trỏ tới một đơn KHÁC không phải giấy thông hành.
		from miyano_portal import dat_hang

		khac = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_ngoai, "qty": 10}],
			request_id=frappe.generate_hash(length=12),
		)["sales_order"]
		chau = frappe.copy_doc(so)
		chau.custom_request_id = None
		chau.amended_from = khac
		with self.assertRaisesRegex(frappe.ValidationError, so.name):
			bao_gia.chan_don_thu_hai_tu_bao_gia_cong(chau)
		# Bản sửa đổi của bản sửa đổi: lần ngược chuỗi `amended_from` tới đơn gốc.
		frappe.db.set_value(
			"Sales Order", khac, {"amended_from": so.name, "custom_request_id": None}
		)
		bao_gia.chan_don_thu_hai_tu_bao_gia_cong(chau)
		# Bản «Duplicate»: `prevdoc_docname` là `no_copy` nên không còn trỏ về báo giá.
		ban_sao = frappe.copy_doc(so, ignore_no_copy=False)
		self.assertFalse([d for d in ban_sao.items if d.get("prevdoc_docname")])
		bao_gia.chan_don_thu_hai_tu_bao_gia_cong(ban_sao)

	def _tu_choi_don(self, so):
		so.custom_ly_do_tu_choi = "Không còn nguồn hàng cho đợt này"
		so.save()
		so = apply_workflow(so, portal.WF_TU_CHOI)
		self.assertEqual((so.workflow_state, so.docstatus), (portal.WF_TU_CHOI, 0))
		return so

	def test_khong_huy_duoc_bao_gia_khi_don_con_song(self):
		so, bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		with self.assertRaises(frappe.ValidationError) as ctx:
			bg.cancel()
		loi = str(ctx.exception)
		self.assertIn(so.name, loi)
		self.assertIn("«Từ chối»", loi)
		# Đơn nháp còn phiếu gốc trỏ vào: Frappe không cho xoá.
		self.assertNotIn("xoá", loi)
		self.assertNotIn("xóa", loi)
		self.assertEqual(frappe.db.get_value("Quotation", bg.name, "docstatus"), 1)

	def test_don_bi_miyano_tu_choi_thi_huy_duoc_bao_gia(self):
		"""«Từ chối» là trạng thái KẾT THÚC ở docstatus 0: đơn không bao giờ
		tới docstatus 2, đòi "huỷ đơn trước" là khoá báo giá vĩnh viễn."""
		so, bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		self._tu_choi_don(so)
		bg.cancel()
		self.assertEqual(frappe.db.get_value("Quotation", bg.name, "docstatus"), 2)

	def test_don_khach_huy_thi_huy_duoc_bao_gia(self):
		so, bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		frappe.db.set_value("Sales Order", so.name, "workflow_state", portal.WF_KHACH_HUY)
		bg.cancel()
		self.assertEqual(frappe.db.get_value("Quotation", bg.name, "docstatus"), 2)

	def test_chot_huy_bo_qua_don_da_huy_va_bao_gia_noi_bo(self):
		so, bg, _phieu = self._don_tu_bao_gia_co_dong_go_tay()
		frappe.db.set_value("Sales Order", so.name, "docstatus", 2, update_modified=False)
		bao_gia.chan_huy_khi_con_don(bg)
		bao_gia.chan_huy_khi_con_don(self._bao_gia_tho(nguon="Nội bộ"))

	def test_hai_chot_duoc_dang_ky_trong_hooks(self):
		su_kien = frappe.get_hooks("doc_events")
		self.assertIn(
			"miyano_portal.bao_gia.chan_huy_khi_con_don",
			su_kien["Quotation"]["before_cancel"],
		)
		self.assertIn(
			"miyano_portal.bao_gia.chan_don_thu_hai_tu_bao_gia_cong",
			su_kien["Sales Order"]["validate"],
		)
		self.assertNotIn("before_insert", su_kien["Sales Order"])

	def test_desk_go_nut_tao_don_va_dat_la_da_mat(self):
		ma = _bo_chu_thich((JS / "quotation.js").read_text(encoding="utf-8"))
		self.assertIn('"Client Portal"', ma)
		self.assertRegex(
			ma, r'remove_custom_button\(__\("Sales Order"\),\s*__\("Create"\)\)'
		)
		self.assertRegex(ma, r'remove_custom_button\(__\("Set as Lost"\)\)')
		# Handler `refresh` của `frappe.ui.form.on` chạy TRƯỚC `refresh` của
		# ERPNext (nơi thêm hai nút), và `setTimeout(…, 0)` / `frappe.after_ajax`
		# cũng quá sớm — đo trên trình duyệt thật: nút vẫn còn. Chỗ gỡ phải là
		# `cscript.custom_refresh`, handler script_manager xếp SAU `cscript.refresh`.
		self.assertRegex(ma, r"frm\.cscript\.custom_refresh\s*=\s*function")
		than = ma[ma.index("frm.cscript.custom_refresh ="):ma.index("refresh(frm)")]
		self.assertIn("go_nut_bao_gia_cong_da_dong_y(frm)", than)
		self.assertNotRegex(ma, r"(?m)^(const|let|class)\s")


class TestKhoiKhachKhaiDuoiBang(NenBaoGia):
	"""P-3 — khối nằm dưới bảng `custom_dat_ngoai`, không trong dashboard."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.ma = _bo_chu_thich((JS / "hang_moi_khach_khai.js").read_text(encoding="utf-8"))

	def test_khong_con_ve_vao_dashboard(self):
		self.assertNotIn("dashboard.add_section(", self.ma)

	def test_chen_sau_bang_dat_ngoai(self):
		self.assertIn("frm.fields_dict.custom_dat_ngoai", self.ma)
		self.assertRegex(self.ma, r"\.insertAfter\(|\.after\(")
		self.assertIn("mvl-hang-moi-khach-khai", self.ma)

	def test_khoi_cu_duoc_go_TRUOC_moi_loi_thoat_som(self):
		"""Khối không còn do dashboard quản nên Frappe không tự dọn: một form
		dùng lại cho mọi chứng từ, không gỡ trước thì chứng từ KHÔNG có dòng
		nào vẫn hiện khối của chứng từ vừa xem."""
		than = self.ma[self.ma.index("miyano_portal.hien_thong_tin_hang_moi = function"):]
		i_go = than.index(".remove()")
		self.assertLess(i_go, than.index("return;"))

	def test_file_dung_chung_khong_khai_bien_toan_cuc(self):
		"""Frappe chạy JS của form như một thẻ <script> toàn cục, và file này
		nạp cho cả Sales Order lẫn Quotation: một `const`/`let` ở cấp ngoài
		cùng làm lần nạp thứ hai ném "already been declared" — chết cả form."""
		self.assertNotRegex(self.ma, r"(?m)^(const|let|class)\s")

	def test_bang_dat_ngoai_khong_nam_trong_muc_thu_gon(self):
		for dt in ("Sales Order", "Quotation"):
			muc, thay = None, False
			for f in frappe.get_meta(dt).fields:
				if f.fieldtype == "Section Break":
					muc = f
				if f.fieldname == "custom_dat_ngoai":
					thay = True
					self.assertFalse(muc and muc.collapsible, dt)
			self.assertTrue(thay, f"{dt} không có bảng custom_dat_ngoai")


class TestLyDoTuChoiDeThay(NenBaoGia):
	"""P-6."""

	def test_thong_diep_noi_nhap_o_dau(self):
		bg = self._bao_gia_tho()
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(bg, bao_gia.HD_TU_CHOI)
		loi = str(ctx.exception)
		self.assertIn("«Cổng khách hàng»", loi)
		self.assertIn("«Lý do từ chối»", loi)
		self.assertIn("bấm lại «Từ chối»", loi)

	def test_muc_cong_khach_hang_cua_bao_gia_khong_thu_gon(self):
		from miyano_portal.patches.v1_42 import bao_gia_quotation

		bao_gia_quotation.them_truong()
		meta = frappe.get_meta("Quotation")
		self.assertEqual(meta.get_field("custom_sec_cong_khach_hang").collapsible, 0)
		self.assertEqual(
			frappe.db.get_value(
				"Custom Field", {"dt": "Quotation", "fieldname": "custom_sec_cong_khach_hang"},
				"collapsible",
			), 0,
		)
