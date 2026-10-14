"""Task 2 — ghi tám sự kiện chuyển trạng thái của phiếu đề xuất mua vào sổ
nhật ký chỉ-thêm (`Portal Nhat Ky Yeu Cau`, Task 1).

Bài quan trọng nhất là `test_vong_lap_sinh_DU_moi_dong_khong_ghi_de` — nó
chứng minh LÝ DO cả tính năng tồn tại: thanh năm chấm hiện nay không thể
hiện được một vòng bị từ chối rồi gửi lại, còn khối truy vết ở đầu phiếu
(`nguoi_duyet`/`thoi_diem_duyet`) chỉ mang dấu của LẦN DUYỆT ĐẦU TIÊN (HDSD
§7 mục 3b) — vòng "duyệt sửa" bị ghi đè mất. Sổ nhật ký sửa cả hai: mỗi
vòng là MỘT DÒNG MỚI, không đè lên dòng trước.

Fixture theo khuôn `test_de_xuat_thu_hoi.py::TestThuHoiEndpoint` — dọn phiếu
cũ bằng SQL thô TRƯỚC `dung_fixture()` (nó tự dọn `_TEST DX%` nữa, nhưng
`on_trash` chặn xoá phiếu đã gửi duyệt nên phải hạ về Nháp trước), rồi dựng
một thành viên khoa (chủ phiếu) và một quản lý.

CẠM BẪY: `dung_fixture()` xoá SẠCH mọi phiếu `_TEST DX%` mỗi lần gọi — chỉ
gọi nó MỘT LẦN trong `setUp`, không gọi lại giữa một bài test.

CẠM BẪY THỨ HAI (phát hiện khi viết bộ test này, KHÔNG có trong brief) —
`FrappeTestCase` chỉ rollback MỘT LẦN cho cả LỚP (xem chú thích của chính
`dung_fixture()`), nên nhiều bài trong cùng lớp CHIA SẺ một transaction
chưa commit. `dung_fixture()` xoá phiếu `_TEST DX%` cũ bằng `frappe.
delete_doc()` mỗi lần `setUp()` chạy (tức MỖI bài) — và xoá đúng phiếu
VỪA-ĐƯỢC-CẤP-SỐ-CUỐI-CÙNG của chuỗi `DXM-.YYYY.-.#####` khiến Frappe tự
`revert_series_if_last()`, TRẢ LẠI đúng số đó cho phiếu tiếp theo. Kết
quả: MỌI phiếu dựng qua `_phieu_nhap()` ở các bài KHÁC NHAU trong lớp này
mang ĐÚNG MỘT cái tên (`DXM-2026-#####` không đổi). `dung_fixture()` không
biết gì về `Portal Nhat Ky Yeu Cau` (doctype của Task 1) nên không dọn
dòng nhật ký cũ — và dòng nhật ký (append-only, `on_trash` của chính nó từ
chối cả `force=True`, xem `test_nhat_ky.py::test_khong_xoa_duoc_dong_da_
ghi`) sống sót nguyên vẹn sang bài sau, mang đúng `de_xuat` mà phiếu MỚI
của bài sau cũng vừa nhận lại. `_khoa_su_kien()` lọc theo tên đó nên đọc
được CẢ dòng của bài trước lẫn bài này — sổ trông như phình ra so với một
vòng lặp duy nhất.

Vá bằng đúng kiểu bypass `on_trash` mà `dung_fixture()` đã dùng cho chính
`Portal De Xuat Mua` — SQL thô, không qua `delete_doc()`."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bao_gia, de_xuat_duyet, nhat_ky, nhat_ky_hook
from miyano_portal.api import portal
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture, khai_gia

COMPANY = "Miyano Việt Nam"
WAREHOUSE = "Stores - MYN"


class TestNhatKySuKienPhieu(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# `on_trash` chặn xoá phiếu đã gửi duyệt (hỏi `ma_de_xuat`, không hỏi
		# trạng thái — xem `on_trash` của doctype) — hạ phiếu cũ của CHÍNH
		# lớp này về Nháp bằng SQL thô trước khi `dung_fixture()` force-
		# delete. Cùng khuôn `test_de_xuat_thu_hoi.py`.
		frappe.db.sql(
			"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
			   WHERE customer LIKE '\\_TEST DX%%'""",
			TRANG_THAI_NHAP,
		)
		# Dọn dòng nhật ký cũ của CHÍNH lớp này bằng SQL thô — xem "CẠM BẪY
		# THỨ HAI" ở docstring module: `dung_fixture()` xoá phiếu cũ mỗi
		# `setUp()` (mỗi bài) khiến `revert_series_if_last()` trả lại đúng
		# cái tên phiếu vừa xoá cho phiếu tiếp theo, và sổ nhật ký (append-
		# only, `on_trash` từ chối cả `force=True`) không có đường xoá nào
		# khác ngoài SQL thô để dọn dấu vết của bài TRƯỚC trước khi bài SAU
		# tái dùng đúng cái tên đó.
		frappe.db.sql(
			"""DELETE FROM `tab{}` WHERE customer LIKE '\\_TEST DX%%'""".format(
				nhat_ky.DOCTYPE
			)
		)
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item

		self.chu_phieu = self._thanh_vien(
			"nhatky.nv@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_a
		)
		self.quan_ly = self._thanh_vien(
			"nhatky.ql@demo.miyano", self.kh_a, "Quản lý", None
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _thanh_vien(self, email, customer, vai_tro, khoa_phong):
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email,
				"first_name": email.split("@")[0],
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		ten_tv = frappe.db.get_value("Portal Member", {"user": email}, "name")
		gia_tri = {
			"customer": customer, "vai_tro": vai_tro,
			"khoa_phong": khoa_phong, "active": 1,
		}
		if ten_tv:
			frappe.db.set_value("Portal Member", ten_tv, gia_tri)
		else:
			frappe.get_doc({
				"doctype": "Portal Member", "user": email, **gia_tri,
			}).insert(ignore_permissions=True)
		return email

	def _phieu_nhap(self):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"ly_do_yeu_cau": "Hết găng tay cỡ M",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.chu_phieu)
		doc.reload()
		return doc

	def _khoa_su_kien(self, ten_phieu):
		return [
			r.su_kien for r in frappe.get_all(
				nhat_ky.DOCTYPE, filters={"de_xuat": ten_phieu},
				fields=["su_kien"], order_by="thoi_diem asc, creation asc",
			)
		]

	def test_vong_lap_sinh_DU_moi_dong_khong_ghi_de(self):
		"""ĐÂY là bài chứng minh cả tính năng đáng tồn tại.

		Một yêu cầu đi: gửi → bị từ chối → gửi lại → duyệt. Bốn việc, bốn
		dòng. Thanh năm chấm hiện nay hiện được ĐÚNG MỘT trong bốn; khối
		truy vết ở đầu phiếu hoàn toàn không thấy được lần từ chối.
		"""
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()
		frappe.set_user(self.quan_ly)
		phieu.reload(); phieu.tu_choi("Vượt hạn mức quý này")
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()
		frappe.set_user(self.quan_ly)
		phieu.reload(); phieu.duyet(self.quan_ly)

		self.assertEqual(
			self._khoa_su_kien(phieu.name),
			[
				nhat_ky.SK_KHOA_GUI_DUYET,
				nhat_ky.SK_QUAN_LY_TU_CHOI,
				nhat_ky.SK_KHOA_GUI_DUYET,
				nhat_ky.SK_QUAN_LY_DUYET,
			],
		)

	def test_moi_dong_mang_dung_nguoi_va_vai(self):
		"""Không đủ khi chỉ đếm số dòng: một sổ ghi đủ sáu dòng mà gán sai
		người là một sổ nói dối có trật tự."""
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()
		frappe.set_user(self.quan_ly)
		phieu.reload(); phieu.duyet(self.quan_ly)
		dong = frappe.get_all(
			nhat_ky.DOCTYPE, filters={"de_xuat": phieu.name},
			fields=["su_kien", "nguoi_thao_tac", "vai"],
			order_by="thoi_diem asc, creation asc",
		)
		self.assertEqual(dong[0].nguoi_thao_tac, self.chu_phieu)
		self.assertEqual(dong[0].vai, nhat_ky.VAI_KHOA)
		self.assertEqual(dong[1].nguoi_thao_tac, self.quan_ly)
		self.assertEqual(dong[1].vai, nhat_ky.VAI_QUAN_LY)

	def _ghi_chu_quan_ly_duyet(self, ten_phieu):
		dong = frappe.get_all(
			nhat_ky.DOCTYPE,
			filters={"de_xuat": ten_phieu, "su_kien": nhat_ky.SK_QUAN_LY_DUYET},
			fields=["ghi_chu"], order_by="thoi_diem desc", limit=1,
		)
		self.assertEqual(len(dong), 1, "phải có đúng một dòng SK_QUAN_LY_DUYET")
		return dong[0].ghi_chu

	def test_duyet_co_dieu_chinh_ghi_chu_mang_so_dong_da_ha(self):
		"""Việc #5 (vòng sửa sau review toàn nhánh, fix-wave brief) — §6/§9.4
		đòi `ghi_chu` của `quan_ly_duyet` mang CẢ số dòng đã điều chỉnh LẪN
		tư cách duyệt, đúng khuôn ví dụ §9.4: "Hạ 2 dòng so với số khoa xin
		· Tư cách: Quản lý chính". TRƯỚC bản vá này `ghi_chu` chỉ có nửa
		sau ("Tư cách: X") — nửa đầu (mang thông tin: phiếu có bị cắt hay
		không) chưa ship.

		`_phieu_nhap()` tạo MỘT dòng `so_luong_de_xuat=5`; hạ `so_luong_
		duyet` xuống 2 TRƯỚC khi gọi `duyet()` (cùng khuôn `test_de_xuat_
		duyet.py::test_duyet_sinh_sales_order_chi_tu_dong_co_so_luong_
		duyet` — sửa tay rồi `save()`, không đi qua endpoint điều chỉnh)."""
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()

		frappe.set_user(self.quan_ly)
		phieu.reload()
		phieu.items[0].so_luong_duyet = 2
		phieu.save(ignore_permissions=True)
		phieu.reload()
		phieu.duyet(self.quan_ly, tu_cach="Quản lý chính")

		self.assertEqual(
			self._ghi_chu_quan_ly_duyet(phieu.name),
			"Hạ 1 dòng so với số khoa xin · Tư cách: Quản lý chính",
		)

	def test_duyet_nguyen_si_khong_in_menh_de_so_dong(self):
		"""VẾ ÂM của bài trên — duyệt NGUYÊN SI (không đụng `so_luong_duyet`,
		giữ nguyên giá trị `gui_duyet()` đã tự đóng dấu) thì `ghi_chu` KHÔNG
		được mang mệnh đề "Hạ 0 dòng..." — §5 brief: im lặng phần đó thay
		vì in một câu vô nghĩa."""
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()

		frappe.set_user(self.quan_ly)
		phieu.reload()
		phieu.duyet(self.quan_ly, tu_cach="Quản lý chính")

		self.assertEqual(
			self._ghi_chu_quan_ly_duyet(phieu.name), "Tư cách: Quản lý chính"
		)

	def test_thu_hoi_ghi_mot_dong(self):
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()
		phieu.reload(); phieu.thu_hoi()
		self.assertIn(nhat_ky.SK_KHOA_THU_HOI, self._khoa_su_kien(phieu.name))

	def test_tu_choi_sua_ghi_mot_dong(self):
		"""Phiếu cũ còn ở "Chờ duyệt sửa" (xin sửa đã bỏ, patch v1_44): lối
		ra duy nhất là `tu_choi_sua()`. Nó chỉ hỏi `self.trang_thai` và cột
		`so_luong_xin_sua`, nên dựng thẳng trạng thái bằng `db_set` thay vì
		cần Sales Order thật."""
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()
		phieu.db_set("trang_thai", "Chờ duyệt sửa")
		phieu.reload()
		phieu.items[0].so_luong_xin_sua = 3
		frappe.set_user(self.quan_ly)
		phieu.tu_choi_sua("Đơn đã chốt giá, không sửa được nữa")
		dong = frappe.get_all(
			nhat_ky.DOCTYPE, filters={"de_xuat": phieu.name},
			fields=["su_kien", "ghi_chu"],
			order_by="thoi_diem asc, creation asc",
		)
		su_kien = [d.su_kien for d in dong]
		self.assertIn(nhat_ky.SK_QUAN_LY_TU_CHOI_SUA, su_kien)
		dong_tu_choi_sua = next(
			d for d in dong if d.su_kien == nhat_ky.SK_QUAN_LY_TU_CHOI_SUA
		)
		self.assertEqual(
			dong_tu_choi_sua.ghi_chu, "Đơn đã chốt giá, không sửa được nữa"
		)

	def test_huy_tu_nhap_ghi_mot_dong(self):
		"""Cạnh `Nháp → Đã huỷ` (review toàn nhánh 03/09/2026, xem
		`CHUYEN_HOP_LE`) — quản lý huỷ được cả phiếu CHƯA TỪNG gửi."""
		phieu = self._phieu_nhap()
		frappe.set_user(self.quan_ly)
		phieu.huy()
		self.assertIn(nhat_ky.SK_QUAN_LY_HUY_PHIEU, self._khoa_su_kien(phieu.name))

	def test_ghi_nhat_ky_hong_KHONG_lam_hong_chuyen_trang_thai(self):
		"""Ràng buộc tuyệt đối, kiểm bằng cách làm hỏng THẬT khâu ghi.

		Làm hỏng ở TẦNG DƯỚI (`frappe.get_doc` bên trong module `nhat_ky`),
		KHÔNG mock lên chính `nhat_ky.ghi`: mock lên hàm đó sẽ thay luôn cả
		lớp `try/except` nằm bên trong nó, tức đo một thứ khác hẳn với thứ
		đang cần chứng minh.

		LỆCH SO VỚI BRIEF, có chủ ý: brief mock `nhat_ky.frappe.get_doc`
		với `side_effect=RuntimeError(...)` VÔ ĐIỀU KIỆN. `nhat_ky.frappe`
		CHÍNH LÀ module `frappe` (một `import frappe` chia sẻ đúng một
		object), nên mock đó chặn MỌI lời gọi `frappe.get_doc` của TOÀN
		TIẾN TRÌNH, không riêng gì lời gọi bên trong `nhat_ky.ghi()`. Chính
		`self.save()` của `gui_duyet()` cũng gọi `frappe.get_doc` (qua
		`_set_defaults()` dựng template dòng con — `document.py`, hàm
		`_set_defaults`), và `frappe.set_user()` gọi ngay phía trên xoá
		sạch cache `frappe.local.new_doc_templates` (`frappe/__init__.py`,
		`set_user()`) nên cache chắc chắn NGUỘI ngay trước `gui_duyet()`.
		Kết quả đo được: mock vô điều kiện làm CHÍNH `self.save()` văng
		`RuntimeError` — TRƯỚC KHI luồng chạy tới `nhat_ky.ghi()` — nên bài
		test không còn đo được điều nó định đo (`gui_duyet()` ném lỗi thẳng
		ra ngoài, không phải một chuyển trạng thái thành công với nhật ký
		ghi hỏng lặng lẽ).

		Sửa bằng cách CHỈ hỏng đúng lời gọi `frappe.get_doc({"doctype":
		nhat_ky.DOCTYPE, ...})` mà `nhat_ky.ghi()` tự phát ra — mọi lời gọi
		khác (kể cả những lời gọi cũng truyền một `dict` có khoá
		`"doctype"`, như `make_new_doc()`) đi thẳng qua bản gốc. Vẫn patch
		ĐÚNG TẦNG DƯỚI mà brief đòi, chỉ thu hẹp phạm vi lại đúng bằng lời
		gọi mà `nhat_ky.ghi()` tự thực hiện."""
		from unittest.mock import patch as mock_patch
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload()

		goc_get_doc = nhat_ky.frappe.get_doc

		def hong_neu_la_nhat_ky(*args, **kwargs):
			if args and isinstance(args[0], dict) and args[0].get("doctype") == nhat_ky.DOCTYPE:
				raise RuntimeError("ổ đĩa hỏng")
			return goc_get_doc(*args, **kwargs)

		with mock_patch.object(nhat_ky.frappe, "get_doc", side_effect=hong_neu_la_nhat_ky):
			phieu.gui_duyet()
		phieu.reload()
		self.assertEqual(phieu.trang_thai, "Chờ duyệt")


class TestNhatKySuKienKhach(FrappeTestCase):
	"""Task 3 — sự kiện do KHÁCH thao tác. Từ patch v1_44 khách chỉ còn đồng
	ý / từ chối / sửa số lượng trên báo giá (Quotation, `bao_gia.py`); dòng
	nhật ký mang `de_xuat` của phiếu đứng sau báo giá.

	Dòng nhật ký cũ của `_TEST DX%` bị dọn bằng SQL thô mỗi `setUp` — cùng
	"CẠM BẪY THỨ HAI" ở docstring module: `dung_fixture()` xoá phiếu nên tên
	phiếu bị tái dùng giữa các bài."""

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.sql(
			"""DELETE FROM `tab{}` WHERE customer LIKE '\\_TEST DX%%'""".format(
				nhat_ky.DOCTYPE
			)
		)
		f = dung_fixture(self)
		self.kh_a, self.kh_b = f.kh_a, f.kh_b
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item
		self.item2 = self._item2()

		self.quan_ly_a = self._thanh_vien("nkkhach.ql.a@demo.miyano", self.kh_a)
		self.quan_ly_b = self._thanh_vien("nkkhach.ql.b@demo.miyano", self.kh_b)

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixture riêng của lớp này -------------------------------------------

	def _item2(self):
		"""Vật tư THỨ HAI — cần cho bài đếm số dòng đổi: một báo giá CHỈ một
		dòng không phân biệt được `ghi_chu` đếm ĐÚNG `len(thay_doi)` với một
		hằng số "1 dòng…" viết cứng."""
		ten = "_TEST DX NK ITEM 2"
		if not frappe.db.exists("Item", ten):
			frappe.get_doc({
				"doctype": "Item", "item_code": ten, "item_name": ten,
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"stock_uom": "Nos", "is_stock_item": 0,
			}).insert(ignore_permissions=True)
		return ten

	def _thanh_vien(self, email, customer):
		"""Luôn dựng "Quản lý": sửa số lượng báo giá chỉ mở cho quản lý, và
		sổ ghi `VAI_QUAN_LY` cho cả ba thao tác."""
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email,
				"first_name": email.split("@")[0],
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		ten_tv = frappe.db.get_value("Portal Member", {"user": email}, "name")
		gia_tri = {"customer": customer, "vai_tro": "Quản lý", "khoa_phong": None, "active": 1}
		if ten_tv:
			frappe.db.set_value("Portal Member", ten_tv, gia_tri)
		else:
			frappe.get_doc({
				"doctype": "Portal Member", "user": email, **gia_tri,
			}).insert(ignore_permissions=True)
		return email

	def _bao_gia_cho_khach(self, items=None):
		"""Báo giá của cổng có phiếu đứng sau, Miyano đã điền giá và gửi khách."""
		items = items or [(self.item, 1, 1000)]
		phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_a, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"trang_thai": "Đã duyệt",
			"items": [{"item_code": ma, "so_luong_de_xuat": sl, "so_luong_duyet": sl}
			          for ma, sl, _ in items],
		}).insert(ignore_permissions=True)
		kq = bao_gia.tao_bao_gia(
			self.kh_a, items=[{"item_code": ma, "qty": sl} for ma, sl, _ in items],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_a,
		)
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		bg.custom_de_xuat = phieu.name
		gia = {ma: g for ma, _, g in items}
		for d in bg.items:
			d.rate = d.price_list_rate = gia[d.item_code]
		bg.save()
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "bao_gia", bg.name)
		return apply_workflow(bg, bao_gia.HD_GUI_KHACH), phieu.name

	def _dong_cua_phieu(self, ten_phieu, su_kien):
		return frappe.get_all(
			nhat_ky.DOCTYPE, filters={"de_xuat": ten_phieu, "su_kien": su_kien},
			fields=["su_kien", "nguoi_thao_tac", "vai", "customer", "khoa_phong",
			        "ghi_chu", "sales_order"],
			order_by="thoi_diem asc, creation asc",
		)

	def _voi(self, user, ham, *a, **kw):
		frappe.set_user(user)
		try:
			return ham(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def _kiem_nguoi_bam(self, dong):
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].nguoi_thao_tac, self.quan_ly_a)
		self.assertEqual(dong[0].vai, nhat_ky.VAI_QUAN_LY)
		self.assertEqual(dong[0].customer, self.kh_a)
		self.assertEqual(dong[0].khoa_phong, self.khoa_a)

	# -- các bài --------------------------------------------------------------

	def test_dong_y_ghi_dong_nhat_ky(self):
		bg, phieu = self._bao_gia_cho_khach()
		kq = self._voi(self.quan_ly_a, portal.portal_bao_gia_dong_y, bg.name)
		dong = self._dong_cua_phieu(phieu, nhat_ky.SK_KHACH_DONG_Y)
		self._kiem_nguoi_bam(dong)
		self.assertEqual(dong[0].sales_order, kq["sales_order"])

	def test_khong_dong_y_ghi_dong_nhat_ky_voi_ly_do(self):
		bg, phieu = self._bao_gia_cho_khach()
		ly_do = "Giá cao hơn dự toán của đơn vị."
		self._voi(self.quan_ly_a, portal.portal_bao_gia_tu_choi, bg.name, ly_do)
		dong = self._dong_cua_phieu(phieu, nhat_ky.SK_KHACH_KHONG_DONG_Y)
		self._kiem_nguoi_bam(dong)
		self.assertEqual(dong[0].ghi_chu, ly_do)

	def test_sua_so_luong_ghi_dong_nhat_ky_dem_dung_so_dong_doi(self):
		"""`ghi_chu` phải đếm ĐÚNG `len(thay_doi)` — hai dòng đổi số lượng
		trên một báo giá hai dòng."""
		bg, phieu = self._bao_gia_cho_khach([(self.item, 1, 1000), (self.item2, 2, 500)])
		moi = {self.item: 5, self.item2: 7}
		self._voi(self.quan_ly_a, portal.portal_bao_gia_sua_so_luong, bg.name,
		          [{"name": d.name, "qty": moi[d.item_code]} for d in bg.items])
		dong = self._dong_cua_phieu(phieu, nhat_ky.SK_KHACH_GUI_LAI_BAO_GIA)
		self._kiem_nguoi_bam(dong)
		self.assertEqual(dong[0].ghi_chu, "2 dòng thay đổi")

	def test_bao_gia_cua_benh_vien_khac_bi_chan_va_KHONG_ghi_nhat_ky(self):
		"""Vế âm bắt buộc (brief) — thiếu bài này thì lưới không phân biệt
		được "chặn đúng" với "chặn nhưng vẫn kịp ghi"."""
		bg, phieu = self._bao_gia_cho_khach()
		with self.assertRaises(frappe.PermissionError):
			self._voi(self.quan_ly_b, portal.portal_bao_gia_dong_y, bg.name)
		self.assertEqual(
			frappe.get_all(nhat_ky.DOCTYPE, filters={
				"de_xuat": phieu, "vai": ["!=", nhat_ky.VAI_MIYANO]}),
			[],
		)


class TestNhatKySuKienMiyano(FrappeTestCase):
	"""Task 4 — sự kiện MIYANO/HỆ THỐNG: hai chuyển `workflow_state` của
	`Sales Order` (`SK_MIYANO_XAC_NHAN`/`SK_MIYANO_TU_CHOI`; "Chờ khách đồng
	ý" và `SK_MIYANO_BAO_GIA` của đơn đã bỏ ở patch v1_44,
	qua `nhat_ky_hook.tu_sales_order_on_update`), `SK_GIAO_HANG` (Delivery
	Note submit), `SK_HOA_DON` (Sales Invoice submit, qua `nhat_ky_hook.
	tu_sales_invoice_on_submit`), và `SK_DON_TAO` ở HAI nơi sinh Sales Order
	trực tiếp — `de_xuat_duyet.duyet_va_tao_don` và `api/portal._dam_bao_
	phieu_tu_duyet` (đứng sau `portal_order_place`, giỏ hàng quản lý).

	Không cần vá "CẠM BẪY THỨ HAI" (dòng nhật ký rò giữa các bài trong cùng
	lớp — xem docstring module đầu file): mọi fixture của lớp này tự dựng
	MỘT `Sales Order` mang TÊN MỚI ở mỗi bài (không xoá-rồi-tái-dùng tên như
	`dung_fixture()` làm với `Portal De Xuat Mua`), và mọi khẳng định lọc
	theo `sales_order=<tên đơn của chính bài đó>` — không đụng dòng của bài
	khác dù `FrappeTestCase` không rollback giữa các method."""

	def setUp(self):
		frappe.set_user("Administrator")
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item
		# Spec 2026-10-12 §5 — phiếu / giỏ còn mã chưa có giá nay sinh Quotation.
		# Lớp này đo NHÁNH ĐƠN của đường thật, nên vật tư có giá trong Price
		# List của khách và đơn sinh ra là đơn "Theo bảng giá".
		khai_gia(self.kh_a, self.item)
		self.chu_phieu = self._thanh_vien(
			"nkmiyano.nv@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_a,
		)
		self.quan_ly = self._thanh_vien(
			"nkmiyano.ql@demo.miyano", self.kh_a, "Quản lý", None, gan_contact=True,
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixture chung của lớp ------------------------------------------

	def _thanh_vien(self, email, customer, vai_tro, khoa_phong, gan_contact=False):
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email,
				"first_name": email.split("@")[0],
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		ten_tv = frappe.db.get_value("Portal Member", {"user": email}, "name")
		gia_tri = {
			"customer": customer, "vai_tro": vai_tro,
			"khoa_phong": khoa_phong, "active": 1,
		}
		if ten_tv:
			frappe.db.set_value("Portal Member", ten_tv, gia_tri)
		else:
			frappe.get_doc({
				"doctype": "Portal Member", "user": email, **gia_tri,
			}).insert(ignore_permissions=True)
		if gan_contact:
			# `dat_hang.tao_sales_order` đọc Contact của `frappe.session.
			# user` để điền `contact_person` — thiếu Dynamic Link tới
			# khách hàng thì ERPNext ném "Contact Person does not belong
			# to {customer}" ngay lúc insert (cùng bẫy đã ghi ở
			# `test_de_xuat_duyet.py::_gan_contact_vao_khach`). CHỈ cần
			# cho `quan_ly` — người duy nhất trong lớp này gọi vào đường
			# sinh Sales Order (`duyet_va_tao_don`/`portal_order_place`).
			self._gan_contact_vao_khach(email, customer)
		return email

	def _gan_contact_vao_khach(self, email, customer):
		contact_name = frappe.db.get_value("Contact", {"user": email})
		if not contact_name:
			return
		if frappe.db.exists("Dynamic Link", {
			"parent": contact_name, "parenttype": "Contact",
			"link_doctype": "Customer", "link_name": customer,
		}):
			return
		c = frappe.get_doc("Contact", contact_name)
		c.append("links", {"link_doctype": "Customer", "link_name": customer})
		c.save(ignore_permissions=True)

	def _don_moi(self, items=None):
		"""Sales Order THẬT ở trạng thái ĐẦU của workflow ("Chờ xác nhận",
		Frappe tự gán lúc insert — KHÔNG ép tay bằng `db.set_value`), để
		các bài dưới tự đi tiếp bằng `apply_workflow` — đường THẬT một
		Sales User/Sales Manager đi trên Desk (xem `test_yeu_cau_list.py::
		_miyano_tu_choi`), không phải ghi thẳng cột."""
		so = frappe.get_doc({
			"doctype": "Sales Order", "customer": self.kh_a, "company": COMPANY,
			"transaction_date": frappe.utils.today(),
			"delivery_date": frappe.utils.add_days(frappe.utils.today(), 5),
			"selling_price_list": "Standard Selling",
			"custom_loai_don": "Mua lẻ",
			"custom_khoa_phong": self.khoa_a,
			"items": items or [
				{"item_code": self.item, "qty": 1, "rate": 1000, "warehouse": WAREHOUSE},
			],
		}).insert(ignore_permissions=True)
		so.reload()
		return so

	def _dong_cua_don(self, ten_don):
		return frappe.get_all(
			nhat_ky.DOCTYPE, filters={"sales_order": ten_don},
			fields=["su_kien", "nguoi_thao_tac", "vai", "customer", "khoa_phong", "ghi_chu"],
			order_by="thoi_diem asc, creation asc",
		)

	# -- Sales Order: hai trạng thái Miyano đứng tên ----------------------

	def test_tu_choi_ghi_dung_mot_dong_voi_nguoi_thao_tac(self):
		"""Bài trọng tâm của Task 4 (brief) — đường THẬT qua `apply_workflow`,
		không gán tay cột `workflow_state`."""
		from frappe.model.workflow import apply_workflow
		so = self._don_moi()
		# "Chờ Miyano xác nhận" KHÔNG nằm trong ánh xạ — bước này không ghi
		# gì; nếu bài dưới đếm ra 2 dòng, lỗi nằm ở CHÍNH bước này bị ghi
		# nhầm, không phải ở bước "Từ chối".
		so = apply_workflow(so, "Gửi duyệt")
		frappe.db.set_value(
			"Sales Order", so.name, "custom_ly_do_tu_choi",
			"Hàng ngừng nhập, không cấp được lô này.", update_modified=False,
		)
		so = apply_workflow(so, "Từ chối")
		self.assertEqual(
			so.workflow_state, "Từ chối",
			"fixture chưa tới được trạng thái cần đo",
		)

		dong = self._dong_cua_don(so.name)
		self.assertEqual(len(dong), 1, "chỉ 'Từ chối' được map — 'Gửi duyệt' không được ghi")
		self.assertEqual(dong[0].su_kien, nhat_ky.SK_MIYANO_TU_CHOI)
		self.assertEqual(dong[0].nguoi_thao_tac, "Administrator")
		self.assertEqual(dong[0].vai, nhat_ky.VAI_MIYANO)
		self.assertEqual(dong[0].customer, self.kh_a)
		self.assertEqual(dong[0].khoa_phong, self.khoa_a)
		self.assertEqual(dong[0].ghi_chu, "Hàng ngừng nhập, không cấp được lô này.")

	def test_luu_lai_khong_doi_workflow_state_khong_sinh_dong(self):
		"""Vế bắt buộc thứ hai (brief) — lưới của cả phép so cũ/mới: thiếu
		bài này thì mỗi lần Miyano sửa ghi chú vặt trên một đơn ĐÃ Ở một
		trạng thái CÓ MAP cũng đẻ thêm một dòng.

		VÒNG SỬA 1 (review) — bản đầu resave một SO còn ở "Chờ xác nhận",
		trạng thái đó VỐN KHÔNG nằm trong `_ANH_XA_TRANG_THAI` nên nhánh
		`if not su_kien: return` đã chặn giùm — reviewer chứng minh bằng
		tay: xoá hẳn `if cu == moi: return`, bài đó VẪN XANH.

		VÒNG SỬA 1, LẦN HAI (tự phát hiện khi làm lại phép chứng minh đỏ)
		— bản sửa đầu tiên dùng "Đã xác nhận" (state CÓ MAP nhưng SUBMIT,
		docstatus=1) rồi resave. Đã ĐO: một resave draft→submitted-y-nguyên
		(docstatus 1→1) được Frappe xếp `_action = "update_after_submit"`
		(`Document.check_docstatus_transition`, nhánh `to_docstatus ==
		SUBMITTED` + `docstatus.is_submitted()`), và `run_post_save_methods`
		CHỈ gọi `on_update_after_submit` cho action đó — KHÔNG BAO GIỜ gọi
		`on_update`. Nghĩa là `tu_sales_order_on_update` không hề chạy cho
		lượt resave đó, có hay không có chốt `cu == moi` — bài kiểu đó vẫn
		xanh dù xoá chốt, NHƯNG vì lý do hoàn toàn khác (hook không được
		gọi), không phải vì chốt hoạt động đúng.

		Sửa ĐÚNG: dùng "Từ chối" — trạng thái CÓ MAP (`SK_MIYANO_TU_CHOI`)
		và DRAFT (`doc_status="0"`). Một resave draft→draft (docstatus 0→0)
		được xếp `_action = "save"`, và `run_post_save_methods` GỌI
		`on_update` cho action đó — đường DUY NHẤT còn lại giữa bài test này
		và một dòng log thừa chính là chốt `cu == moi`. (Bản trước dùng "Chờ
		khách đồng ý"; trạng thái đó đã bỏ ở patch v1_44.)"""
		so = self._don_moi()
		so = apply_workflow(so, "Gửi duyệt")
		frappe.db.set_value(
			"Sales Order", so.name, "custom_ly_do_tu_choi",
			"Hàng ngừng nhập, không cấp được lô này.", update_modified=False,
		)
		so = apply_workflow(so, "Từ chối")
		self.assertEqual(
			so.workflow_state, "Từ chối",
			"fixture chưa tới được trạng thái ĐÃ MAP (draft) cần đo",
		)
		self.assertEqual(so.docstatus, 0, "phải là trạng thái DRAFT để resave còn gọi on_update")
		so_dong_truoc = len(self._dong_cua_don(so.name))
		self.assertEqual(so_dong_truoc, 1, "lượt 'Từ chối' phải tự sinh đúng 1 dòng")

		so.po_no = "PO-NHATKY-TEST"
		so.save(ignore_permissions=True)
		so.reload()

		self.assertEqual(
			so.workflow_state, "Từ chối", "fixture phải giữ nguyên workflow_state",
		)
		self.assertEqual(
			len(self._dong_cua_don(so.name)), so_dong_truoc,
			"lưu lại không đổi workflow_state không được sinh thêm dòng nhật ký",
		)

	def test_xac_nhan_ghi_dung_mot_dong(self):
		from frappe.model.workflow import apply_workflow
		so = self._don_moi()
		so = apply_workflow(so, "Gửi duyệt")
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual(so.workflow_state, "Đã xác nhận")
		self.assertEqual(
			so.docstatus, 1,
			"'Xác nhận' submit đơn — on_update vẫn chạy TRƯỚC on_submit (Frappe "
			"run_post_save_methods), nên hook vẫn bắt được chuyển tiếp này",
		)

		dong = self._dong_cua_don(so.name)
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].su_kien, nhat_ky.SK_MIYANO_XAC_NHAN)
		self.assertEqual(dong[0].vai, nhat_ky.VAI_MIYANO)
		self.assertEqual(dong[0].customer, self.kh_a)
		self.assertEqual(dong[0].khoa_phong, self.khoa_a)

	def test_trang_thai_trung_gian_khong_ghi(self):
		"""'Chờ Miyano xác nhận' không nằm trong ánh xạ trạng thái — vế
		âm cho `_ANH_XA_TRANG_THAI`, không chỉ kiểm trạng thái CÓ map."""
		from frappe.model.workflow import apply_workflow
		so = self._don_moi()
		so = apply_workflow(so, "Gửi duyệt")
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		self.assertEqual(self._dong_cua_don(so.name), [])

	# -- Delivery Note / Sales Invoice ------------------------------------

	def _kho_hoat_dong(self):
		ten = frappe.db.get_value("Customer Warehouse", {"customer": self.kh_a}, "name")
		if ten:
			frappe.db.set_value(
				"Customer Warehouse", ten, {"active": 1, "ngay_bat_dau": "2020-01-01"},
			)
			return ten
		return frappe.get_doc({
			"doctype": "Customer Warehouse", "customer": self.kh_a,
			"ten_kho": "_TEST Kho nhat ky", "ma_kho": "_TESTNKKHO",
			"active": 1, "ngay_bat_dau": "2020-01-01",
		}).insert(ignore_permissions=True).name

	def _don_da_xac_nhan(self):
		"""SO `docstatus=1` — Frappe TỰ khớp `workflow_state` sang trạng
		thái có `doc_status` bằng docstatus mới, NGAY CẢ khi submit thẳng
		không qua `apply_workflow` (đã đo trên `erptest.local`); dòng
		`SK_MIYANO_XAC_NHAN` sinh ra từ đó là hiệu ứng CÓ THẬT của hành
		động submit, không phải nhiễu cần né — các bài dưới lọc `dong` theo
		ĐÚNG `su_kien` đang đo, không đếm tổng số dòng của cả đơn."""
		so = self._don_moi()
		so.submit()
		return so

	def test_giao_hang_ghi_dung_mot_dong_voi_dot(self):
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
		self._kho_hoat_dong()
		so = self._don_da_xac_nhan()
		dn = make_delivery_note(so.name)
		dn.set_posting_time = 1
		dn.posting_date = frappe.utils.today()
		dn.insert(ignore_permissions=True)
		dn.submit()
		self.assertEqual(dn.docstatus, 1)

		dong = [r for r in self._dong_cua_don(so.name) if r.su_kien == nhat_ky.SK_GIAO_HANG]
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].vai, nhat_ky.VAI_MIYANO)
		self.assertEqual(dong[0].nguoi_thao_tac, "Administrator")
		self.assertEqual(dong[0].customer, self.kh_a)
		self.assertEqual(dong[0].khoa_phong, self.khoa_a)
		self.assertEqual(dong[0].ghi_chu, "Đợt 1")

	def _kho_tat(self):
		"""Đảm bảo khách KHÔNG có `Customer Warehouse` đang hoạt động —
		KHÔNG chỉ "không gọi `_kho_hoat_dong()`". `FrappeTestCase` không
		rollback GIỮA các bài trong cùng lớp (xem docstring lớp), và
		`test_giao_hang_ghi_dung_mot_dong_voi_dot` (chạy TRƯỚC bài dưới đây
		theo thứ tự alphabet 'd' < 'v') gọi `_kho_hoat_dong()` để lại một
		`Customer Warehouse.active = 1` cho CHÍNH `self.kh_a` — nếu bài dưới
		chỉ đơn giản "bỏ qua" bước mở kho, nó vẫn thừa hưởng kho ACTIVE của
		bài kia và phép phá cần lộ ra (Việc #3 — lời gọi nhật ký từng nằm
		sâu trong `_tao_phieu()`, chỉ chạy khi có kho) sẽ KHÔNG lộ — đúng
		bẫy "bài test tự đảm bảo điều kiện mà lỗi cần để lộ ra" brief đã
		cảnh. Đặt tường minh `active = 0` (hoặc không tạo gì, nếu chưa có
		hàng nào) để bài này ĐÚNG với cả hai vế brief nêu: "Customer
		Warehouse.active = 0 (hoặc không có kho)"."""
		ten = frappe.db.get_value("Customer Warehouse", {"customer": self.kh_a}, "name")
		if ten:
			frappe.db.set_value("Customer Warehouse", ten, "active", 0)

	def test_giao_hang_van_ghi_khi_khach_chua_mo_kho(self):
		"""Việc #3 (fix-wave brief) — chứng minh ĐỎ: TRƯỚC bản vá, `nhat_ky.
		ghi(SK_GIAO_HANG)` nằm SÂU trong `_tao_phieu()`, một hàm của module
		KHO chỉ chạy sau khi `_kho_cua_khach()` (gọi từ `_tu_delivery_note`)
		tìm thấy kho ACTIVE. Với `Customer Warehouse.active = 0`,
		`_tu_delivery_note()` `return None` NGAY ở dòng kiểm `kho`, nên
		không dòng `giao_hang` nào từng được ghi — đã ĐO trước bản vá: bài
		này đỏ với `AssertionError: 0 != 1`.

		Hỏng thật (brief, đo trên site): 1/6 khách có Portal Member active
		KHÔNG có Customer Warehouse active (`Bệnh viện Đa khoa Miyano`) —
		bệnh viện đó đặt hàng, Miyano giao hàng, dòng thời gian không có
		một dòng `giao_hang` nào dù thanh tiến trình phía trên vẫn sáng
		"Giao hàng"."""
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
		self._kho_tat()
		so = self._don_da_xac_nhan()
		dn = make_delivery_note(so.name)
		dn.set_posting_time = 1
		dn.posting_date = frappe.utils.today()
		dn.insert(ignore_permissions=True)
		dn.submit()
		self.assertEqual(dn.docstatus, 1)

		dong = [r for r in self._dong_cua_don(so.name) if r.su_kien == nhat_ky.SK_GIAO_HANG]
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].vai, nhat_ky.VAI_MIYANO)
		self.assertEqual(dong[0].nguoi_thao_tac, "Administrator")
		self.assertEqual(dong[0].customer, self.kh_a)
		self.assertEqual(dong[0].khoa_phong, self.khoa_a)
		self.assertEqual(dong[0].ghi_chu, "Đợt 1")
		# Không có Customer Warehouse active → KHÔNG được tạo phiếu nhập kho
		# khách nào, đúng nhánh `_tu_delivery_note()` thoát sớm. Khẳng định
		# này giữ ranh giới: nhật ký ghi ĐỘC LẬP với kho, không phải nhật ký
		# "kéo" kho hoạt động theo.
		self.assertFalse(
			frappe.db.exists("Customer Stock Receipt", {"delivery_note": dn.name}),
			"Không có kho active mà vẫn sinh Phiếu Nhập Kho Khách — sai giả "
			"định của chính bài test này (khách chưa mở kho)",
		)

	def test_so_dot_hong_van_ghi_dong_giao_hang_chi_mat_ghi_chu(self):
		"""`_so_dot_cua()` hỏng thì MẤT CHỮ "Đợt N", KHÔNG mất cả dòng.

		`so_dot` chỉ trang trí `ghi_chu`. Trước bản vá, nó được gọi trần
		trong `_ghi_nhat_ky_giao_hang()`, nên một lỗi ở hàm đếm đợt — một
		hàm của module KHO — cuốn theo cả dòng `giao_hang`. Đó đúng thứ
		coupling vừa bị gỡ một tầng bên trên (lời gọi ghi sổ đã tách khỏi
		đường tạo phiếu kho, nhưng vẫn còn dính hàm này).

		Hỏng thật: thanh tiến trình 5 mốc phía trên vẫn sáng "Giao hàng"
		trong khi sổ không có gì — hai khối trên CÙNG một màn nói ngược
		nhau, và khối im lặng lại là khối được dùng để đối chiếu.

		Bài này đo đúng ranh giới đó: dòng VẪN sinh, `ghi_chu` là `None`."""
		import unittest.mock

		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

		from miyano_portal.kho import delivery_hook

		so = self._don_da_xac_nhan()
		with unittest.mock.patch.object(
			delivery_hook, "_so_dot_cua", side_effect=RuntimeError("hỏng có chủ ý")
		):
			dn = make_delivery_note(so.name)
			dn.set_posting_time = 1
			dn.posting_date = frappe.utils.today()
			dn.insert(ignore_permissions=True)
			dn.submit()
		self.assertEqual(dn.docstatus, 1, "Delivery Note phải submit được")

		dong = [r for r in self._dong_cua_don(so.name) if r.su_kien == nhat_ky.SK_GIAO_HANG]
		self.assertEqual(
			len(dong), 1,
			"Mất cả dòng giao hàng vì hàm đếm đợt hỏng — dòng thời gian im "
			"lặng trong khi thanh tiến trình vẫn sáng 'Giao hàng'",
		)
		self.assertIsNone(dong[0].ghi_chu, "Không tính được đợt thì để trống, đừng bịa")
		self.assertEqual(dong[0].vai, nhat_ky.VAI_MIYANO)
		self.assertEqual(dong[0].customer, self.kh_a)
		self.assertEqual(dong[0].khoa_phong, self.khoa_a)

	def test_hoa_don_ghi_dung_mot_dong(self):
		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
		so = self._don_da_xac_nhan()
		si = make_sales_invoice(so.name)
		si.set_posting_time = 1
		si.insert(ignore_permissions=True)
		si.submit()
		self.assertEqual(si.docstatus, 1)

		dong = [r for r in self._dong_cua_don(so.name) if r.su_kien == nhat_ky.SK_HOA_DON]
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].vai, nhat_ky.VAI_MIYANO)
		self.assertEqual(dong[0].customer, self.kh_a)
		self.assertEqual(dong[0].khoa_phong, self.khoa_a)

	def test_hoa_don_tra_hang_khong_ghi(self):
		"""Vế âm — giấy báo có (`is_return`) không phải một lần PHÁT HÀNH
		hoá đơn mới cho khách; ghi nó vào sổ sẽ làm một khoản hoàn tiền
		trông giống một lần xuất hoá đơn (xem docstring `nhat_ky_hook.
		tu_sales_invoice_on_submit`).

		Dùng một double nhẹ (`_GiaDoc`) thay vì dựng cả một hoá đơn trả hàng
		thật: hàm chỉ chạm ba thuộc tính (`customer`/`is_return`/`items`)
		qua `.get()`/lặp — double khớp đúng giao diện đó (KHÔNG dùng
		`frappe._dict`: nó là `dict` con, nên `.items` đọc ra hẳn phương
		thức `dict.items` có sẵn thay vì khoá `"items"` gán tay — che mất
		đúng nhánh `for row in doc.items` cần đo). Patch thẳng `nhat_ky.ghi`
		để khẳng định KHÔNG BỊ GỌI, chính xác hơn đếm dòng CSDL lọc theo
		`sales_order=None` (bộ lọc đó có thể trùng dòng của một hoá đơn
		khác trong cùng lớp nếu sau này ai đó thêm bài mới)."""
		from unittest.mock import patch as mock_patch

		class _GiaDoc:
			def __init__(self, **kw):
				self._d = kw

			def get(self, key):
				return self._d.get(key)

			def __getattr__(self, key):
				return self._d[key]

		fake_doc = _GiaDoc(customer=self.kh_a, is_return=1, items=[])
		with mock_patch.object(nhat_ky, "ghi") as gia:
			nhat_ky_hook.tu_sales_invoice_on_submit(fake_doc)
		gia.assert_not_called()

	# -- SK_DON_TAO: hai nơi sinh Sales Order trực tiếp -------------------

	def _phieu_cho_duyet(self):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"ly_do_yeu_cau": "cần gấp",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 3}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.chu_phieu)
		doc.reload()
		frappe.set_user(self.chu_phieu)
		doc.gui_duyet()
		doc.reload()
		frappe.set_user(self.quan_ly)
		return doc

	def test_don_tao_qua_duyet_va_tao_don_ghi_dung_mot_dong_he_thong(self):
		doc = self._phieu_cho_duyet()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, self.quan_ly)
		frappe.set_user("Administrator")

		dong = self._dong_cua_don(kq["sales_order"])
		self.assertEqual(len(dong), 1, "duyet_va_tao_don chỉ nên sinh MỘT dòng SK_DON_TAO")
		self.assertEqual(dong[0].su_kien, nhat_ky.SK_DON_TAO)
		self.assertEqual(dong[0].vai, nhat_ky.VAI_HE_THONG)
		self.assertIsNone(
			dong[0].nguoi_thao_tac,
			"vai=VAI_HE_THONG không được gán nguoi_thao_tac (xem nhat_ky.ghi())",
		)
		self.assertEqual(dong[0].customer, self.kh_a)
		self.assertEqual(dong[0].khoa_phong, self.khoa_a)
		# `de_xuat` không nằm trong field list của `_dong_cua_don()` — đọc
		# riêng để khẳng định mắt xích dò vết KHÔNG rỗng (cạm bẫy thứ tự
		# (b) trong brief: `doc.name` chỉ có SAU `doc.duyet()`/insert).
		ten_de_xuat = frappe.db.get_value(
			nhat_ky.DOCTYPE,
			{"sales_order": kq["sales_order"], "su_kien": nhat_ky.SK_DON_TAO},
			"de_xuat",
		)
		self.assertEqual(ten_de_xuat, doc.name)

	def test_don_tao_qua_gio_hang_quan_ly_ghi_dung_mot_dong_he_thong(self):
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_place(
			mode="ban_le", items=[{"item_code": self.item, "qty": 2}],
			khoa_phong=self.khoa_a, request_id="_TEST NK GIO HANG DON",
		)
		frappe.set_user("Administrator")

		dong = self._dong_cua_don(kq["sales_order"])
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].su_kien, nhat_ky.SK_DON_TAO)
		self.assertEqual(dong[0].vai, nhat_ky.VAI_HE_THONG)
		self.assertIsNone(dong[0].nguoi_thao_tac)
		self.assertEqual(dong[0].customer, self.kh_a)
		self.assertEqual(dong[0].khoa_phong, self.khoa_a)
		ten_de_xuat = frappe.db.get_value(
			nhat_ky.DOCTYPE,
			{"sales_order": kq["sales_order"], "su_kien": nhat_ky.SK_DON_TAO},
			"de_xuat",
		)
		self.assertEqual(ten_de_xuat, kq["de_xuat"])

	def test_don_tao_bam_lai_khong_sinh_dong_thu_hai(self):
		"""BR-O12 (bấm lại/`da_ton_tai=True`) — KHÔNG được sinh dòng SK_DON_TAO
		thứ hai cho một Sales Order KHÔNG hề được tạo mới lần này."""
		frappe.set_user(self.quan_ly)
		kq1 = portal.portal_order_place(
			mode="ban_le", items=[{"item_code": self.item, "qty": 2}],
			khoa_phong=self.khoa_a, request_id="_TEST NK GIO HANG BAM LAI",
		)
		kq2 = portal.portal_order_place(
			mode="ban_le", items=[{"item_code": self.item, "qty": 2}],
			khoa_phong=self.khoa_a, request_id="_TEST NK GIO HANG BAM LAI",
		)
		frappe.set_user("Administrator")

		self.assertTrue(kq2["da_ton_tai"], "fixture chưa tới được kịch bản bấm lại")
		self.assertEqual(kq1["sales_order"], kq2["sales_order"])
		dong = [
			r for r in self._dong_cua_don(kq1["sales_order"]) if r.su_kien == nhat_ky.SK_DON_TAO
		]
		self.assertEqual(len(dong), 1)
