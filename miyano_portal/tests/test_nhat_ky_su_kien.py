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
from frappe.tests.utils import FrappeTestCase

from miyano_portal import nhat_ky
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture


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
		truy vết ở đầu phiếu hoàn toàn không thấy được lần từ chối. Vòng
		"duyệt sửa" (nợ kỹ thuật §7 mục 3b của HDSD — khối truy vết chỉ
		mang dấu của lần duyệt đầu) được canh riêng ở
		`test_duyet_sua_ghi_mot_dong` bên dưới, không lặp lại ở đây.
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

	def test_thu_hoi_ghi_mot_dong(self):
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()
		phieu.reload(); phieu.thu_hoi()
		self.assertIn(nhat_ky.SK_KHOA_THU_HOI, self._khoa_su_kien(phieu.name))

	def test_duyet_sua_ghi_mot_dong(self):
		"""Vá đúng khoản nợ §7 mục 3b của HDSD: khối truy vết ở đầu phiếu
		(`nguoi_duyet`/`thoi_diem_duyet`) chỉ mang dấu của lần DUYỆT ĐẦU
		TIÊN — `duyet_sua()` (vòng SỬA sau khi duyệt) không đụng khối đó
		(xem docstring `duyet()`). Không cần dựng cả Sales Order thật:
		`duyet_sua()` chỉ hỏi `self.trang_thai` và cột `so_luong_xin_sua`
		của dòng, cùng cách `test_de_xuat_thu_hoi.py` dùng `db_set` để đẩy
		thẳng trạng thái thay vì đi lại toàn bộ luồng duyệt + xin sửa."""
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()
		phieu.db_set("trang_thai", "Chờ duyệt sửa")
		phieu.reload()
		phieu.items[0].so_luong_xin_sua = 3
		frappe.set_user(self.quan_ly)
		phieu.duyet_sua()
		self.assertIn(nhat_ky.SK_QUAN_LY_DUYET_SUA, self._khoa_su_kien(phieu.name))

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
