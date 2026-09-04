"""Task 5 (nhật ký thao tác + dòng thời gian) — phía ĐỌC.

Hai thứ được thi công ở đây, cả hai đều DÙNG LẠI chốt đã có, không tự chế:

- `portal_context.lien_he_nguoi_dung()` — mở rộng `ten_nguoi_dung()` thành
  `{ten, dien_thoai, tai_khoan}`. Ranh giới quyền riêng tư §8 nằm ở đây:
  `vai=miyano` không bao giờ lộ email.
- `api/portal.py::portal_nhat_ky_yeu_cau()` — endpoint đọc sổ, hỏi ĐÚNG hai
  chốt phạm vi (`_phieu_cua_toi(..., cho_quan_ly=True)` cho phiếu,
  `dam_bao_xem_duoc()` + `check_permission("read")` cho đơn), cộng phép suy
  hai dòng cho chứng từ tạo trước khi bật nhật ký (§9.6).

Đọc `nhat_ky.ghi()` không bao giờ ném lỗi — mọi thao tác chuyển trạng thái
dưới đây (`gui_duyet`/`tu_choi`/`duyet`) tự ghi log thật vào sổ, không có
test nào ở đây gán tay một dòng nhật ký rồi đo lại chính nó (trừ bài `vai=
miyano`, nơi CHÍNH việc gán tay một dòng `SK_MIYANO_XAC_NHAN` là thứ đang
được kiểm tra — không có đường mã sản phẩm nào tạo sự kiện đó trong app này
ở giai đoạn hiện tại, workflow Sales Order của Miyano chạy trên Desk)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import nhat_ky
from miyano_portal.api import de_xuat
from miyano_portal.api import portal as portal_api
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.portal_context import lien_he_nguoi_dung
from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestLienHeNguoiDung(FrappeTestCase):
	"""`lien_he_nguoi_dung()` một mình — không cần fixture phiếu/nhật ký, chỉ
	cần một `User`.

	SỐ ĐIỆN THOẠI FIXTURE NẰM Ở DẢI RIÊNG `0938271xxx` — cố ý, không phải
	ngẫu nhiên. `tabUser.mobile_no` có **UNIQUE index** (`SHOW INDEX FROM
	tabUser` → `Non_unique = 0`), nên một fixture cầm số "đẹp" kiểu
	`0912345678` sẽ đâm vào bất kỳ bản ghi thật/demo nào tình cờ giữ số đó và
	làm bài ĐỎ bằng `IntegrityError` — một lỗi đọc ra như "tính năng hỏng"
	trong khi thật ra chỉ là hai fixture giẫm chân nhau.
	Chuyện đó đã xảy ra thật ngày 04/09/2026: lượt chạy thử toàn tuyến để lại
	tài khoản demo giữ `0912345678`/`0987654321`, và sáu bài ở lớp này đỏ.
	Dải `0938271xxx` dùng chung với `test_nhan_su_import.py` cho đúng mục đích
	đó. Thêm fixture số điện thoại mới thì lấy tiếp trong dải này."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.email_day_du = "_test_nky_lienhe_du@miyano-test.local"
		if not frappe.db.exists("User", self.email_day_du):
			frappe.get_doc({
				"doctype": "User", "email": self.email_day_du,
				"first_name": "Nguyễn Văn Đủ", "user_type": "Website User",
				"send_welcome_email": 0, "mobile_no": "0938271201",
			}).insert(ignore_permissions=True)
		else:
			frappe.db.set_value(
				"User", self.email_day_du,
				{"full_name": "Nguyễn Văn Đủ", "mobile_no": "0938271201", "phone": ""},
			)

		self.email_khong_ten = "_test_nky_lienhe_khongten@miyano-test.local"
		if not frappe.db.exists("User", self.email_khong_ten):
			frappe.get_doc({
				"doctype": "User", "email": self.email_khong_ten,
				"first_name": self.email_khong_ten, "user_type": "Website User",
				"send_welcome_email": 0,
			}).insert(ignore_permissions=True)
		else:
			frappe.db.set_value(
				"User", self.email_khong_ten,
				{"full_name": self.email_khong_ten, "mobile_no": "", "phone": ""},
			)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_du_ten_dien_thoai_tai_khoan(self):
		kq = lien_he_nguoi_dung(self.email_day_du)
		self.assertEqual(kq["ten"], "Nguyễn Văn Đủ")
		self.assertEqual(kq["dien_thoai"], "0938271201")
		self.assertEqual(kq["tai_khoan"], self.email_day_du)

	def test_thieu_ca_hai_so_tra_rong_khong_phai_none(self):
		"""(b) đề bài — tầng hiển thị Vue in thẳng giá trị này; `None` in ra
		chữ "null" trên màn khách xem."""
		kq = lien_he_nguoi_dung(self.email_khong_ten)
		self.assertEqual(kq["dien_thoai"], "")
		self.assertIsNotNone(kq["dien_thoai"])

	def test_ten_trung_email_thi_tai_khoan_rong(self):
		"""`ten_nguoi_dung()` lui về CHÍNH email khi không tra được `full_name`
		— in thêm tài khoản lúc đó chỉ là lặp lại đúng một chuỗi hai lần."""
		kq = lien_he_nguoi_dung(self.email_khong_ten)
		self.assertEqual(kq["ten"], self.email_khong_ten)
		self.assertEqual(kq["tai_khoan"], "")

	def test_cho_hien_tai_khoan_false_luon_rong_du_ten_khac_email(self):
		"""Ranh giới §8 — tham số này là CÁCH DUY NHẤT gọi hàm nói "đừng trả
		email", không phụ thuộc việc `ten` có khác email hay không."""
		kq = lien_he_nguoi_dung(self.email_day_du, cho_hien_tai_khoan=False)
		self.assertEqual(kq["ten"], "Nguyễn Văn Đủ")
		self.assertEqual(kq["tai_khoan"], "")

	def test_email_rong_tra_ca_ba_truong_rong(self):
		kq = lien_he_nguoi_dung(None)
		self.assertEqual(kq, {"ten": "", "dien_thoai": "", "tai_khoan": ""})


class TestPortalNhatKyYeuCau(FrappeTestCase):
	"""Endpoint đọc sổ — chốt phạm vi (Step 1) + suy hai dòng cho đơn cũ
	(Step 5)."""

	def setUp(self):
		frappe.set_user("Administrator")
		# Dọn Sales Order test TRƯỚC — cùng khuôn `test_chi_tiet_gop.py::
		# _don_phieu_cu()`/`test_yeu_cau_list.py::_don_phieu_cu`. Cần cho
		# nhánh `order=` (Step 4, đi qua `de_xuat_duyet.duyet_va_tao_don`):
		# không dọn thì `_insert_so_idempotent` thấy một Sales Order CŨ còn
		# tham chiếu `custom_de_xuat`/`ma_de_xuat` bị TÁI SỬ DỤNG (xem chú
		# thích "RÁC MỒ CÔI" dưới đây) và từ chối tạo đơn thứ hai.
		for r in frappe.get_all(
			"Sales Order", filters={"customer": ["like", "_TEST DX%"]},
			fields=["name", "docstatus"],
		):
			if r.docstatus == 1:
				frappe.get_doc("Sales Order", r.name).cancel()
			frappe.delete_doc("Sales Order", r.name, force=True, ignore_permissions=True)
		# Hạ trạng thái phiếu cũ về Nháp trước khi dọn fixture — né `on_trash`
		# chặn xoá phiếu đã gửi duyệt (cùng khuôn `test_de_xuat_thu_hoi.py`).
		frappe.db.sql(
			"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
			   WHERE customer LIKE '\\_TEST DX%%'""",
			TRANG_THAI_NHAP,
		)
		f = dung_fixture(self)
		self.kh_a, self.kh_b = f.kh_a, f.kh_b
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc  # dưới kh_a
		self.khoa_duoc_b = f.khoa_duoc  # dưới kh_b

		# Dọn RÁC MỒ CÔI trước khi test này chạy — KHÔNG phải một vi phạm
		# "chỉ ghi thêm" của tính năng: `dung_fixture()` ngay trên vừa
		# `force=True` xoá SẠCH mọi phiếu `_TEST DX%` của những test TRƯỚC,
		# nhưng `Portal Nhat Ky Yeu Cau` không biết gì về việc đó (doctype
		# này ra đời sau `fixtures_de_xuat.py`) — mọi dòng nhật ký cũ tham
		# chiếu tới các phiếu vừa bị xoá trở thành RÁC MỒ CÔI, không có chủ.
		# `FrappeTestCase` chỉ rollback ở RANH GIỚI CLASS (`addClassCleanup`,
		# xem `frappe/tests/utils.py`), không rollback giữa các bài trong
		# cùng class — và autoname kiểu series của `Portal De Xuat Mua`
		# (`DXM-.YYYY.-.#####`) TÁI SỬ DỤNG đúng số vừa xoá nếu đó là số
		# CUỐI đã cấp (`revert_series_if_last` của framework). Không dọn ở
		# đây, một phiếu MỚI của bài sau có thể trùng TÊN với phiếu đã xoá
		# của bài trước — và nhật ký của bài trước "sống lại" dưới tên phiếu
		# của bài sau, làm SAI SỐ DÒNG một cách không đoán trước được (bắt
		# gặp thực nghiệm: `test_yeu_cau_MOI_khong_bi_hien_doi` đếm ra 4 dòng
		# `khoa_gui_duyet` thay vì 1 vì đúng lý do này). Chỉ xoá theo
		# `customer LIKE '_TEST DX%'` — không đụng dữ liệu thật của site.
		frappe.db.sql(
			"delete from `tabPortal Nhat Ky Yeu Cau` where customer like '\\_TEST DX%%'"
		)

		# Khoa thứ hai CÙNG kh_a — cô lập đúng trục khoa, không lẫn trục
		# khách hàng (cùng khuôn `test_de_xuat_cach_ly.py`).
		self.khoa_duoc_a = self._dam_bao_khoa(
			self.kh_a, "Dược (nội bộ, test nhật ký)", "NKYDUOCNB"
		)

		self.quan_ly = self._thanh_vien(
			"nky.ql@demo.miyano", self.kh_a, "Quản lý", None
		)
		self.nv_huyethoc = self._thanh_vien(
			"nky.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		self.nv_duoc_a = self._thanh_vien(
			"nky.duoc_a@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_duoc_a
		)
		self.quan_ly_b = self._thanh_vien(
			"nky.ql_b@demo.miyano", self.kh_b, "Quản lý", None
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixture riêng của file này -----------------------------------------

	def _dam_bao_khoa(self, customer, ten, ma):
		ten_bp = frappe.db.get_value(
			"Customer Department", {"customer": customer, "ma_khoa": ma}, "name"
		)
		if ten_bp:
			return ten_bp
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": customer,
			"ten_khoa_phong": ten, "ma_khoa": ma, "active": 1,
		}).insert(ignore_permissions=True).name

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
		# Cùng khuôn `test_chi_tiet_gop.py::_thanh_vien` — nối `Contact` của
		# user vào ĐÚNG `customer`, không chỉ tạo `Portal Member`. Cần cho
		# nhánh `order=` (Step 4): `dat_hang.tao_sales_order` (qua
		# `duyet_va_tao_don`) đi qua `validate_party_contact` của ERPNext,
		# và hàm đó ném "Contact Person does not belong to..." nếu thiếu
		# liên kết này — không liên quan gì tới phạm vi khoa/khách hàng mà
		# task này đang kiểm, chỉ là điều kiện TIÊN QUYẾT để dựng được một
		# đơn hàng thật trong fixture.
		contact = frappe.db.get_value("Contact", {"user": email})
		if contact and not frappe.db.exists("Dynamic Link", {
			"parent": contact, "parenttype": "Contact",
			"link_doctype": "Customer", "link_name": customer,
		}):
			c = frappe.get_doc("Contact", contact)
			c.append("links", {"link_doctype": "Customer", "link_name": customer})
			c.save(ignore_permissions=True)
		return email

	def _phieu(self, customer, khoa, owner):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": customer, "khoa_phong": khoa,
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", owner)
		doc.reload()
		return doc

	def _phieu_da_duyet_thanh_don(self):
		"""Đi qua ĐƯỜNG DUYỆT THẬT (`de_xuat_duyet.duyet_va_tao_don`), KHÔNG
		gán tay `sales_order` — cùng khuôn `test_chi_tiet_gop.py::
		_phieu_da_duyet` (gán tay là ghim một trạng thái rồi đo lại chính
		nó). Dùng để kiểm nhánh `order=` của endpoint: một yêu cầu đi hết
		luồng có CẢ phiếu lẫn đơn."""
		doc = self._phieu(self.kh_a, self.khoa_huyethoc, self.nv_huyethoc)
		frappe.set_user(self.nv_huyethoc)
		doc.reload()
		doc.ly_do_yeu_cau = "Hết bông băng"
		doc.gui_duyet()

		frappe.set_user(self.quan_ly)
		doc.reload()
		from miyano_portal import de_xuat_duyet
		de_xuat_duyet.duyet_va_tao_don(doc.name, self.quan_ly)
		doc.reload()
		return doc

	def _xac_nhan_don_that(self, ten_don):
		"""Đưa Sales Order qua ĐÚNG hai chuyển tiếp workflow thật ("Gửi duyệt"
		rồi "Xác nhận", cùng chuỗi `test_nhat_ky_su_kien.py::TestNhatKySuKien
		Miyano` đã dùng) để `nhat_ky_hook.tu_sales_order_on_update` ghi một
		dòng `SK_MIYANO_XAC_NHAN` THẬT.

		Dòng này CHỈ mang `sales_order` (xem `nhat_ky_hook.py` —
		`nhat_ky.ghi(su_kien, ..., sales_order=doc.name, ...)`, KHÔNG có tham
		số `de_xuat`), khác hẳn `SK_KHOA_GUI_DUYET`/`SK_QUAN_LY_DUYET` (chỉ
		mang `de_xuat`, không mang `sales_order` — xem `portal_de_xuat_mua.py
		::gui_duyet/duyet`) và khác `SK_DON_TAO` (mang CẢ HAI). Đây là khoá
		DUY NHẤT trong fixture của lớp này chỉ tìm được qua vế `sales_order`
		của truy vấn — dùng để canh ĐÚNG phép GỘP OR hai vế, không phải phép
		suy §9.6 (chỉ suy `khoa_gui_duyet`/`quan_ly_duyet`, không suy được
		khoá này) và không lẫn với `SK_DON_TAO` (khớp cả hai vế nên không
		phân biệt được AND với OR).

		Chạy với `Administrator`: `self.quan_ly` (Website User, role
		Customer) không có quyền chạy chuyển tiếp workflow Sales Order trên
		Desk — nơi gọi phải tự đặt lại user cần đọc SAU lời gọi này."""
		from frappe.model.workflow import apply_workflow
		frappe.set_user("Administrator")
		so = frappe.get_doc("Sales Order", ten_don)
		so = apply_workflow(so, "Gửi duyệt")
		so = apply_workflow(so, "Xác nhận")
		return so

	def _phieu_da_duyet_hai_vong(self):
		"""Đi hết một vòng đời có thật: gửi → từ chối → gửi lại → duyệt —
		bốn dòng nhật ký THẬT, đúng thứ tự thời gian, đúng người ở mỗi
		bước (chuyển session TRƯỚC mỗi lời gọi vì `nhat_ky.ghi()` mặc định
		lấy `nguoi_thao_tac` từ `frappe.session.user` tại KHOẢNH KHẮC gọi)."""
		doc = self._phieu(self.kh_a, self.khoa_huyethoc, self.nv_huyethoc)

		frappe.set_user(self.nv_huyethoc)
		doc.ly_do_yeu_cau = "Hết găng tay cỡ M — lần 1"
		doc.gui_duyet()

		frappe.set_user(self.quan_ly)
		doc.reload()
		doc.tu_choi("Sai mã hàng")

		frappe.set_user(self.nv_huyethoc)
		doc.reload()
		doc.ly_do_yeu_cau = "Hết găng tay cỡ M — lần 2"
		doc.gui_duyet()

		frappe.set_user(self.quan_ly)
		doc.reload()
		doc.duyet(self.quan_ly, tu_cach="Quản lý chính")
		doc.reload()
		return doc

	# -- Step 1.1: vế dương --------------------------------------------------

	def test_quan_ly_doc_duoc_nhat_ky_du_dong_dung_thu_tu(self):
		doc = self._phieu_da_duyet_hai_vong()

		frappe.set_user(self.quan_ly)
		rows = portal_api.portal_nhat_ky_yeu_cau(de_xuat=doc.name)

		self.assertEqual(
			[r["su_kien"] for r in rows],
			[
				nhat_ky.SK_KHOA_GUI_DUYET,
				nhat_ky.SK_QUAN_LY_TU_CHOI,
				nhat_ky.SK_KHOA_GUI_DUYET,
				nhat_ky.SK_QUAN_LY_DUYET,
			],
		)
		for truoc, sau in zip(rows, rows[1:]):
			self.assertLessEqual(truoc["thoi_diem"], sau["thoi_diem"])
		self.assertTrue(all(r["suy_ra"] is False for r in rows))

	# -- Step 1.2: vế âm trục khoa --------------------------------------------

	def test_nhan_vien_khoa_khac_khong_doc_duoc_nhat_ky_khoa_ban(self):
		"""`nv_duoc_a` và `nv_huyethoc` CÙNG khách hàng (`kh_a`), KHÁC khoa —
		cô lập đúng trục khoa, không lẫn trục khách hàng của bài kế tiếp."""
		doc = self._phieu(self.kh_a, self.khoa_huyethoc, self.nv_huyethoc)
		frappe.set_user(self.nv_huyethoc)
		doc.ly_do_yeu_cau = "Hết bơm tiêm"
		doc.gui_duyet()

		frappe.set_user(self.nv_duoc_a)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_nhat_ky_yeu_cau(de_xuat=doc.name)

	# -- Step 1.3: vế âm trục khách hàng --------------------------------------

	def test_benh_vien_khac_khong_doc_duoc_nhat_ky(self):
		doc = self._phieu(self.kh_a, self.khoa_huyethoc, self.nv_huyethoc)
		frappe.set_user(self.nv_huyethoc)
		doc.ly_do_yeu_cau = "Hết bơm tiêm"
		doc.gui_duyet()

		frappe.set_user(self.quan_ly_b)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_nhat_ky_yeu_cau(de_xuat=doc.name)

	# -- Step 1.4: vai=miyano không bao giờ trả email -------------------------

	def test_vai_miyano_khong_bao_gio_tra_email(self):
		"""Khoá đúng ranh giới §8 — bệnh viện thấy TÊN và SỐ nhân sự Miyano
		để gọi hỏi trách nhiệm, KHÔNG BAO GIỜ thấy email/tài khoản.

		Dựng dòng thẳng qua `nhat_ky.ghi()` thay vì đi hết đường ghi thật
		(`nhat_ky_hook.tu_sales_order_on_update`, móc vào `Sales Order.
		on_update`, bắn khi `workflow_state` CHUYỂN sang "Đã xác nhận"/"Chờ
		khách đồng ý"/"Từ chối" — đường thật CÓ tồn tại và ĐÃ được Task 1-4
		nối dây, xem `nhat_ky_hook.py`): đường đó đòi dựng cả một workflow
		Sales Order thật trên Desk, quá nặng cho riêng bài này. Đã ĐỌC (không
		đoán) TOÀN BỘ năm chỗ ghi mang vai Miyano thật trong app — cả hai hàm
		của `nhat_ky_hook.py` (`SK_MIYANO_XAC_NHAN`/`SK_MIYANO_BAO_GIA`/
		`SK_MIYANO_TU_CHOI`/`SK_HOA_DON`) và `kho/delivery_hook.py`
		(`SK_GIAO_HANG`) — cả năm đều truyền `vai=nhat_ky.VAI_MIYANO` tường
		minh, không chỗ nào lách qua `vai=he_thong`/`vai=quan_ly` kèm
		`nguoi_thao_tac` thật (nếu có thì email sẽ lọt qua endpoint mà không
		bài nào ở đây bắt được — đã soát để loại khả năng đó). Dòng dựng tay
		ở đây đi qua ĐÚNG một nhánh mã (`_dong()` trong `portal_nhat_ky_yeu_
		cau`, so `vai != VAI_MIYANO`) mà cả năm chỗ ghi thật kia cũng đi qua
		— không phải một đường vòng riêng."""
		doc = self._phieu(self.kh_a, self.khoa_huyethoc, self.nv_huyethoc)

		nhan_su_email = "_test_nky_miyano_staff@miyano-test.local"
		if not frappe.db.exists("User", nhan_su_email):
			frappe.get_doc({
				"doctype": "User", "email": nhan_su_email,
				"first_name": "Trần Thị Miyano", "user_type": "System User",
				"send_welcome_email": 0, "mobile_no": "0938271202",
			}).insert(ignore_permissions=True)
		else:
			frappe.db.set_value(
				"User", nhan_su_email,
				{"full_name": "Trần Thị Miyano", "mobile_no": "0938271202"},
			)

		nhat_ky.ghi(
			nhat_ky.SK_MIYANO_XAC_NHAN, customer=self.kh_a,
			khoa_phong=self.khoa_huyethoc, de_xuat=doc.name,
			vai=nhat_ky.VAI_MIYANO, nguoi_thao_tac=nhan_su_email,
		)

		frappe.set_user(self.quan_ly)
		rows = portal_api.portal_nhat_ky_yeu_cau(de_xuat=doc.name)
		mien = [r for r in rows if r["vai"] == nhat_ky.VAI_MIYANO]
		self.assertEqual(len(mien), 1)
		self.assertEqual(mien[0]["ten"], "Trần Thị Miyano")
		self.assertEqual(mien[0]["tai_khoan"], "")

	# -- Step 4: nhánh `order=` -----------------------------------------------

	def test_doc_qua_order_gop_ca_nhat_ky_cua_phieu(self):
		"""Một yêu cầu đi hết luồng có CẢ phiếu lẫn đơn — đọc qua `order=`
		(nhánh `dam_bao_xem_duoc` + `check_permission`, KHÔNG qua
		`_phieu_cua_toi`) vẫn phải thấy đủ nhật ký của PHIẾU
		(`khoa_gui_duyet`/`quan_ly_duyet`), không chỉ những sự kiện gắn
		thẳng vào đơn — đúng câu "một yêu cầu có cả phiếu lẫn đơn thì nhật
		ký nằm ở cả hai" của Step 4.

		VÒNG SỬA (Việc #2, fix-wave brief) — `khoa_gui_duyet`/`quan_ly_duyet`
		KHÔNG đủ để canh phép GỘP: cả hai đều được phép suy §9.6 tự chèn lại
		khi truy vấn thật không thấy gì (chèn ĐÚNG hai khoá này, không hơn),
		nên một truy vấn CHẾT (`or_filters` bị đổi thành `filters`, tức AND —
		đã ĐO: 18/18 bài của module này vẫn XANH với phép phá đó, kể cả hai
		bài ở đây trước bản sửa) vẫn để lại đúng hai khoá này nhờ fallback,
		không phải nhờ truy vấn. Thêm `SK_MIYANO_XAC_NHAN` THẬT (qua
		`_xac_nhan_don_that`, chỉ mang `sales_order` không mang `de_xuat`) —
		phép suy §9.6 KHÔNG suy được khoá này (nó không nằm trong bốn
		trường phiếu §9.6 đọc), nên nó CHỈ có thể xuất hiện qua đúng vế
		`sales_order` của `or_filters`. Dưới AND, vế `sales_order=ten_don`
		đứng CÙNG điều kiện `de_xuat=ten_de_xuat` trên MỘT dòng — dòng
		`SK_MIYANO_XAC_NHAN` có `de_xuat` rỗng nên KHÔNG khớp AND, bài này
		đỏ đúng ở khẳng định mới."""
		doc = self._phieu_da_duyet_thanh_don()
		self.assertTrue(doc.sales_order)
		self._xac_nhan_don_that(doc.sales_order)

		frappe.set_user(self.quan_ly)
		rows = portal_api.portal_nhat_ky_yeu_cau(order=doc.sales_order)
		su_kien = [r["su_kien"] for r in rows]
		self.assertIn(nhat_ky.SK_KHOA_GUI_DUYET, su_kien)
		self.assertIn(nhat_ky.SK_QUAN_LY_DUYET, su_kien)
		self.assertIn(
			nhat_ky.SK_MIYANO_XAC_NHAN, su_kien,
			"Thiếu SK_MIYANO_XAC_NHAN (chỉ mang sales_order, không mang de_xuat, "
			"KHÔNG thể do phép suy §9.6 sinh ra) — truy vấn GỘP hai vế de_xuat/"
			"sales_order đang chết (vd or_filters bị đổi thành filters/AND) và "
			"chỉ còn sống sót nhờ fallback che đúng hai khoá khoa_gui_duyet/"
			"quan_ly_duyet ở trên",
		)

	def test_order_vs_de_xuat_tra_cung_mot_bo_dong(self):
		"""Đọc qua `de_xuat=` và qua `order=` của CÙNG một yêu cầu phải ra
		cùng một bộ `su_kien` — hai đường vào cùng một sổ, không phải hai
		bộ lọc lệch nhau.

		VÒNG SỬA (Việc #2) — phép so sánh HAI TẬP bằng nhau một mình KHÔNG
		canh được phép gộp OR/AND: cả hai nhánh `de_xuat=`/`order=` của
		`portal_nhat_ky_yeu_cau` cùng tính ra ĐÚNG một cặp `(ten_de_xuat,
		ten_don)` một khi cả phiếu lẫn đơn đã tồn tại (xem `api/portal.py`),
		nên chúng luôn gọi `frappe.get_all` với CÙNG một `dieu_kien` — hỏng
		AND thì CẢ HAI nhánh hỏng GIỐNG NHAU, hai tập rỗng-như-nhau vẫn
		`assertEqual` được. Thêm khẳng định RIÊNG rằng `SK_MIYANO_XAC_NHAN`
		THẬT (qua `_xac_nhan_don_that`, chỉ mang `sales_order`) có mặt
		trong CHÍNH tập trả về — khoá này không do phép suy §9.6 sinh ra,
		nên nó chỉ sống sót khi vế OR hoạt động đúng."""
		doc = self._phieu_da_duyet_thanh_don()
		self._xac_nhan_don_that(doc.sales_order)

		frappe.set_user(self.quan_ly)
		qua_de_xuat = {r["su_kien"] for r in portal_api.portal_nhat_ky_yeu_cau(de_xuat=doc.name)}
		qua_don = {r["su_kien"] for r in portal_api.portal_nhat_ky_yeu_cau(order=doc.sales_order)}
		self.assertEqual(qua_de_xuat, qua_don)
		self.assertIn(
			nhat_ky.SK_MIYANO_XAC_NHAN, qua_de_xuat,
			"Thiếu SK_MIYANO_XAC_NHAN — hai tập bằng nhau không chứng minh được "
			"phép GỘP OR còn sống, vì cả hai nhánh cùng tính ra CÙNG dieu_kien "
			"và hỏng GIỐNG NHAU khi or_filters bị đổi thành filters/AND",
		)

	def test_nhan_vien_khoa_khac_khong_doc_duoc_nhat_ky_qua_order(self):
		"""VẾ ÂM của nhánh `order=` — cùng chốt trục khoa, khác cửa vào."""
		doc = self._phieu_da_duyet_thanh_don()
		frappe.set_user(self.nv_duoc_a)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_nhat_ky_yeu_cau(order=doc.sales_order)

	def test_benh_vien_khac_khong_doc_duoc_nhat_ky_qua_order(self):
		"""VẾ ÂM trục KHÁCH HÀNG của nhánh `order=` — `dam_bao_xem_duoc()` một
		mình KHÔNG kiểm được trục này (nó no-op cho Quản lý — xem docstring
		hàm đó): `quan_ly_b` là Quản lý của `kh_b`, nên `pham_vi_don()` của
		CHÍNH họ trả `{}` bất kể đơn đang xem thuộc khách hàng nào. Chỉ
		`so.check_permission("read")` (qua hook `sales_has_permission` ->
		`_has_customer_permission`) mới chặn được ca này — thiếu dòng đó,
		một quản lý bệnh viện B đọc được nguyên nhật ký của bệnh viện A qua
		cửa `order=`."""
		doc = self._phieu_da_duyet_thanh_don()
		frappe.set_user(self.quan_ly_b)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_nhat_ky_yeu_cau(order=doc.sales_order)

	# -- Step 5: suy hai dòng cho chứng từ tạo trước khi bật nhật ký --------

	def test_don_cu_khong_co_nhat_ky_van_suy_duoc_hai_dong(self):
		"""Phiếu tạo trước khi bật nhật ký vẫn mang người yêu cầu và người
		duyệt — trên chính bốn trường của nó (`nguoi_yeu_cau`/`thoi_diem_gui`/
		`nguoi_duyet`/`thoi_diem_duyet`). Để màn hình trống trơn ở ca này là
		làm người dùng tưởng hệ thống hỏng.

		Xoá sổ bằng SQL THÔ (không qua ORM) — CỐ Ý, vì `on_trash`/`validate`
		của `Portal Nhat Ky Yeu Cau` chặn cả xoá lẫn sửa từ mọi đường ORM,
		kể cả `ignore_permissions`/`force=True` (xem `test_nhat_ky.py`). Đây
		là MÔ PHỎNG một phiếu tạo TRƯỚC khi tính năng nhật ký tồn tại (không
		hề có dòng nào được ghi lúc đó) — không phải xoá bằng chứng của một
		phiếu đã có nhật ký thật."""
		doc = self._phieu_da_duyet_hai_vong()
		frappe.db.sql(
			"delete from `tabPortal Nhat Ky Yeu Cau` where de_xuat = %s", doc.name
		)
		self.assertEqual(
			frappe.db.count("Portal Nhat Ky Yeu Cau", {"de_xuat": doc.name}), 0
		)

		frappe.set_user(self.quan_ly)
		rows = portal_api.portal_nhat_ky_yeu_cau(de_xuat=doc.name)

		su_kien = [r["su_kien"] for r in rows]
		self.assertIn(nhat_ky.SK_KHOA_GUI_DUYET, su_kien)
		self.assertIn(nhat_ky.SK_QUAN_LY_DUYET, su_kien)
		self.assertTrue(
			all(r["suy_ra"] is True for r in rows),
			"phiếu không còn dòng nhật ký thật nào — MỌI dòng trả về phải "
			"là dòng suy (suy_ra=True), không dòng nào suy_ra=False",
		)

	def test_yeu_cau_MOI_khong_bi_hien_doi(self):
		"""VẾ ÂM của bài trên. Thiếu bài này thì phép suy ở Step 5 chèn thêm
		một bản sao cho MỌI yêu cầu MỚI — mỗi lần gửi duyệt sẽ hiện hai dòng
		`khoa_gui_duyet` giống hệt nhau (một thật, một suy), và không ai đỏ
		được vì bài dương ở trên chỉ đếm "có mặt" (assertIn), không đếm SỐ
		LẦN xuất hiện."""
		doc = self._phieu(self.kh_a, self.khoa_huyethoc, self.nv_huyethoc)
		frappe.set_user(self.nv_huyethoc)
		doc.ly_do_yeu_cau = "Hết bông băng"
		doc.gui_duyet()
		doc.reload()

		frappe.set_user(self.quan_ly)
		rows = portal_api.portal_nhat_ky_yeu_cau(de_xuat=doc.name)

		su_kien = [r["su_kien"] for r in rows]
		self.assertEqual(su_kien.count(nhat_ky.SK_KHOA_GUI_DUYET), 1)
		self.assertFalse(any(r["suy_ra"] for r in rows))


class TestDeXuatChiTietTruyVetDienThoai(FrappeTestCase):
	"""Task 6 — `de_xuat_chi_tiet()` mở khối truy vết ra thêm ba khoá
	(`nguoi_yeu_cau_dien_thoai`, `nguoi_duyet_ten`, `nguoi_duyet_dien_thoai`),
	giải Ở BIÊN GIỚI API cạnh `nguoi_yeu_cau_ten` đã có (chốt 21/08) — vá
	luôn Minor #6 của review 03/09: `KhoiTruyVet.vue` đang hiện thẳng
	`phieu.nguoi_duyet` (EMAIL THÔ) ở vế "Truy vết duyệt".

	Setup RIÊNG với `TestPortalNhatKyYeuCau` ở trên: hai lớp kiểm hai hàm
	khác nhau (`de_xuat_chi_tiet` ở đây, `portal_nhat_ky_yeu_cau` ở trên) —
	gộp chung một `setUp` nặng chỉ để mượn vài dòng fixture là trộn hai mối
	quan tâm không liên quan tới nhau.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc
		self.quan_ly = self._thanh_vien("nky6.ql@demo.miyano", self.kh_a, "Quản lý", None)
		# HAI nhân viên riêng — KHÔNG dùng chung một user cho bài "có số" và
		# bài "không có số": `FrappeTestCase` không rollback giữa các bài
		# trong CÙNG class (chỉ ở ranh giới class), và `unittest` không đảm
		# bảo chạy theo đúng thứ tự định nghĩa (mặc định theo thứ tự tên
		# phương thức) — nếu dùng chung một user, bài nào chạy SAU sẽ thấy
		# `mobile_no` bài TRƯỚC vừa ghi, và một trong hai bài đỏ vì lý do
		# SAI (thứ tự chạy), không phải vì code thiếu.
		self.nv_a = self._thanh_vien("nky6.nv_a@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc)
		self.nv_b = self._thanh_vien("nky6.nv_b@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc)

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
		gia_tri = {"customer": customer, "vai_tro": vai_tro, "khoa_phong": khoa_phong, "active": 1}
		if ten_tv:
			frappe.db.set_value("Portal Member", ten_tv, gia_tri)
		else:
			frappe.get_doc({"doctype": "Portal Member", "user": email, **gia_tri}).insert(ignore_permissions=True)
		return email

	def _dat_ten(self, email, first_name, last_name):
		"""`full_name` là field TÍNH (`User.validate()` ghép `first_name` +
		`last_name`) — phải đi qua `save()`, không `db.set_value` thẳng,
		cùng khuôn `test_de_xuat_endpoint.py::_dat_ten`."""
		u = frappe.get_doc("User", email)
		u.first_name, u.last_name = first_name, last_name
		u.save(ignore_permissions=True)

	def _phieu(self, owner):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", owner)
		doc.reload()
		return doc

	def test_nguoi_duyet_ten_la_ten_hien_thi_khong_phai_email(self):
		"""Step 1.1 — vá Minor #6 review 03/09."""
		self._dat_ten(self.quan_ly, "Phạm", "Quản Lý")
		doc = self._phieu(self.nv_a)
		frappe.set_user(self.nv_a)
		doc.reload()
		doc.ly_do_yeu_cau = "Hết bông băng"
		doc.gui_duyet()

		frappe.set_user(self.quan_ly)
		doc.reload()
		doc.duyet(self.quan_ly, tu_cach="Quản lý chính")

		kq = de_xuat.de_xuat_chi_tiet(doc.name)
		self.assertEqual(kq["nguoi_duyet_ten"], "Phạm Quản Lý")
		self.assertNotIn("@", kq["nguoi_duyet_ten"])
		# Trường GỐC không đổi — cùng lý do `nguoi_yeu_cau`/`nguoi_yeu_cau_ten`
		# đã tách: `nguoi_duyet` vẫn phải là email nguyên vẹn cho hạ tầng
		# khác (Notification…) đọc.
		self.assertEqual(kq["nguoi_duyet"], self.quan_ly)

	def test_dien_thoai_dung_khi_tai_khoan_co_so(self):
		"""Step 1.2 — tài khoản CÓ số."""
		frappe.db.set_value("User", self.nv_a, "mobile_no", "0938271203")
		doc = self._phieu(self.nv_a)
		frappe.set_user(self.nv_a)
		kq = de_xuat.de_xuat_chi_tiet(doc.name)
		self.assertEqual(kq["nguoi_yeu_cau_dien_thoai"], "0938271203")

	def test_dien_thoai_rong_khong_phai_None_khi_khong_co_so(self):
		"""Step 1.3 — tài khoản KHÔNG có số: khoá phải là `""`, không `None`,
		không `"—"` — ba giá trị khác nhau ở tầng hiển thị (brief Task 6)."""
		doc = self._phieu(self.nv_b)
		frappe.set_user(self.nv_b)
		kq = de_xuat.de_xuat_chi_tiet(doc.name)
		self.assertEqual(kq["nguoi_yeu_cau_dien_thoai"], "")
		self.assertIsNotNone(kq["nguoi_yeu_cau_dien_thoai"])
		self.assertNotEqual(kq["nguoi_yeu_cau_dien_thoai"], "—")
