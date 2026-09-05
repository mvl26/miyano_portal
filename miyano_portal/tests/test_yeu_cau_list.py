"""Task 11 (QĐ-G11) — MỘT danh sách, MỘT dòng đời: `portal_yeu_cau_cua_toi`.

Lỗi đang sửa: một yêu cầu của khoa nằm ở "Đề xuất mua" khi còn là phiếu rồi
NHẢY sang "Đơn hàng của tôi" sau khi quản lý duyệt. Nhân viên phải biết
trước yêu cầu của mình đang ở giai đoạn NỘI BỘ nào mới tìm lại được nó —
tức phải học sơ đồ kiến trúc của hệ thống.

Endpoint gộp trả về đúng MỘT dòng cho mỗi yêu cầu, ở bất kỳ giai đoạn nào:
`nhap → cho_duyet → da_duyet → cho_khach_dong_y → da_giao` (cộng hai ngõ
cụt `tu_choi`/`da_huy` — trạng thái THẬT mà người dùng tự đưa yêu cầu của
mình vào, xem bài học "Việc (d)" của `DeXuatList.vue`).

Ruling P54 (26/08/2026) — những giá trị trên là KHOÁ NỘI BỘ, không phải
nhãn. Endpoint này không nói tiếng Việt về giai đoạn nữa; nhãn hiển thị
("Nháp", "Chờ quý vị đồng ý", …) sống ở `frontend/src/format.js` và được
ghim ở `test_giai_doan_khoa_va_nhan.py`. Lý do tách: trước P54 chính chuỗi
hiển thị là khoá lọc VÀ đi trong URL (`?chip=`), nên đổi một chữ tiếng Việt
làm chết mọi link đã gửi cho bệnh viện.

BỐI CẢNH KIẾN TRÚC — role `Customer` có ZERO DocPerm trên `Portal De Xuat
Mua`, nên `frappe.get_list` ném `PermissionError` cho MỌI Website User
TRƯỚC KHI hook phạm vi kịp chạy (xem docstring `api/de_xuat.py`). Đường
sống là hàm whitelist, và nó phải TỰ hỏi đúng chốt phạm vi
(`get_portal_member()` cho khách, `pham_vi_don()` cho khoa) — test ở đây vì
thế gọi THẲNG endpoint dưới `frappe.set_user(...)`, đúng khuôn
`test_de_xuat_endpoint.py`.

Phiếu-đã-duyệt-thành-đơn được dựng bằng ĐƯỜNG DUYỆT THẬT
(`de_xuat_duyet.duyet_va_tao_don`), KHÔNG phải bằng cách gán tay
`phieu.sales_order = <một SO dựng riêng>`: gán tay là ghim một trạng thái
rồi đo lại chính nó, không chứng minh gì về mối nối mà mã thật dùng — đúng
kiểu fixture-che-cổng dự án này đã dính bảy lần.
"""

import re
from pathlib import Path
from unittest.mock import patch as mock_patch

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import de_xuat_duyet
from miyano_portal.api import de_xuat, portal
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"
WAREHOUSE = "Stores - MYN"

FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"


def _don_phieu_cu():
	"""Bẫy #1 + #2 — dọn Sales Order test TRƯỚC khi dọn phiếu, và hạ trạng
	thái phiếu cũ về Nháp TRƯỚC KHI `dung_fixture()` force-delete
	(`on_trash` chặn xoá phiếu đã gửi duyệt). Cùng khuôn
	`test_de_xuat_sua_sau_duyet.py::_don_phieu_cu`.

	Cổng KHÔNG submit Sales Order (mọi đơn cổng là nháp, xem
	`test_de_xuat_duyet.py`), nên `docstatus: 0` phủ hết đơn lớp này tạo
	ra; đơn submit (nếu về sau có) phải huỷ trước khi xoá."""
	for r in frappe.get_all(
		"Sales Order", filters={"customer": ["like", "_TEST DX%"]},
		fields=["name", "docstatus"],
	):
		if r.docstatus == 1:
			frappe.get_doc("Sales Order", r.name).cancel()
		frappe.delete_doc("Sales Order", r.name, force=True, ignore_permissions=True)
	frappe.db.sql(
		"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
		   WHERE customer LIKE '\\_TEST DX%%'""",
		TRANG_THAI_NHAP,
	)


def _dam_bao_thanh_vien(email, customer, vai_tro, khoa_phong):
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
	_gan_contact_vao_khach(email, customer)
	return email


def _gan_contact_vao_khach(email, customer):
	"""`tao_sales_order` cần Contact gắn đúng Customer để không ném
	"Contact Person does not belong to..." — cùng lý do
	`test_de_xuat_sua_sau_duyet.py`."""
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


class TestYeuCauList(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a, self.kh_b = f.kh_a, f.kh_b
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc  # dưới kh_a
		self.khoa_b = f.khoa_duoc             # dưới kh_b

		# Khoa THỨ HAI cùng kh_a — cô lập đúng trục khoa, không lẫn trục
		# khách hàng (cùng lý do `test_de_xuat_endpoint.py` đã ghi).
		self.khoa_duoc = self._dam_bao_khoa(
			self.kh_a, "Dược (nội bộ, test yêu cầu)", "DXYCDUOC"
		)

		self.user_quan_ly = _dam_bao_thanh_vien(
			"dxyc.ql@demo.miyano", self.kh_a, "Quản lý", None
		)
		self.user_huyethoc = _dam_bao_thanh_vien(
			"dxyc.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa",
			self.khoa_huyethoc,
		)
		self.user_duoc = _dam_bao_thanh_vien(
			"dxyc.duoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_duoc
		)
		self.user_benh_vien_b = _dam_bao_thanh_vien(
			"dxyc.benhvienb@demo.miyano", self.kh_b, "Nhân viên khoa", self.khoa_b
		)

		# (1) Phiếu NHÁP của khoa Huyết học — đầu dòng đời.
		self.phieu_nhap = self._tao_phieu(
			self.kh_a, self.khoa_huyethoc, self.user_huyethoc
		)
		# (2) Đơn ĐÃ GIAO của CÙNG khoa, KHÔNG đi qua đường đề xuất (đơn cũ
		#     của sáu tài khoản đang chạy thật) — cuối dòng đời.
		self.don_da_giao = self._tao_don(self.kh_a, self.khoa_huyethoc)
		# `status`/`per_delivered` là hai cột ERPNext tự ghi khi Delivery
		# Note cập nhật đơn; ghi thẳng ở đây là mô phỏng ĐÚNG hai cột mà
		# phép suy giai đoạn đọc, không phải né một cổng nào.
		frappe.db.set_value(
			"Sales Order", self.don_da_giao,
			{"status": "Completed", "per_delivered": 100},
			update_modified=False,
		)
		# (3) Phiếu ĐÃ DUYỆT + đơn sinh ra từ nó — qua ĐƯỜNG DUYỆT THẬT.
		self.phieu_da_duyet, self.don_cua_phieu = self._duyet_that(
			self.kh_a, self.khoa_huyethoc, self.user_huyethoc
		)
		# (4) Phiếu Nháp của khoa KHÁC, cùng bệnh viện — trục khoa.
		self.phieu_khoa_duoc = self._tao_phieu(
			self.kh_a, self.khoa_duoc, self.user_duoc
		)
		# (5) Phiếu Nháp của bệnh viện KHÁC — trục khách hàng.
		self.phieu_benh_vien_b = self._tao_phieu(
			self.kh_b, self.khoa_b, self.user_benh_vien_b
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixture riêng của file này -------------------------------------------

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

	def _tao_phieu(self, customer, khoa_phong, owner, so_luong=1):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": customer, "khoa_phong": khoa_phong,
			"items": [{"item_code": self.item, "so_luong_de_xuat": so_luong}],
		})
		doc.insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", owner)
		return doc.name

	def _tao_don(self, customer, khoa_phong):
		"""Đơn KHÔNG đi qua đường đề xuất — đúng hình dạng đơn cũ."""
		so = frappe.get_doc({
			"doctype": "Sales Order", "customer": customer, "company": COMPANY,
			"transaction_date": frappe.utils.today(),
			"delivery_date": frappe.utils.add_days(frappe.utils.today(), 5),
			"selling_price_list": "Standard Selling",
			"custom_loai_don": "Mua lẻ",
			"custom_khoa_phong": khoa_phong,
			"items": [{
				"item_code": self.item, "qty": 1, "rate": 1000,
				"warehouse": WAREHOUSE,
			}],
		}).insert(ignore_permissions=True)
		return so.name

	def _duyet_that(self, customer, khoa_phong, owner):
		"""Phiếu đi TRỌN đường thật: lập → gửi duyệt → quản lý duyệt → đơn.

		Trả `(ten_phieu, ten_don)`."""
		ten = self._tao_phieu(customer, khoa_phong, owner)
		doc = frappe.get_doc("Portal De Xuat Mua", ten)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, self.user_quan_ly)
		return kq["de_xuat"], kq["sales_order"]

	def _miyano_tu_choi(self, ten_don):
		"""Đưa đơn tới `workflow_state = "Từ chối"` bằng CHÍNH máy trạng
		thái (`Chờ xác nhận --Gửi duyệt--> Chờ Miyano xác nhận --Từ chối-->
		Từ chối`, xem `setup/install_workflow.py`), KHÔNG `db.set_value`.

		Đây là đường Sales User bấm thật trên Desk. Ghim thẳng chuỗi
		"Từ chối" vào cột sẽ chứng minh được đúng một điều — rằng chuỗi đó
		nằm trong cột — chứ không chứng minh trạng thái ấy TỚI ĐƯỢC. Cả bộ
		test này tồn tại vì lần trước một đơn tới được đúng trạng thái đó
		mà màn hình đọc ra "Đã duyệt".

		`apply_workflow` chỉ tra vai trò qua `frappe.get_roles()` ->
		`frappe.session.user` (giải thích dài ở `portal_order_accept`); test
		chạy dưới Administrator nên đi qua được chốt `Sales User`."""
		from frappe.model.workflow import apply_workflow

		so = frappe.get_doc("Sales Order", ten_don)
		so = apply_workflow(so, "Gửi duyệt")
		# BR-O14/NL-2.1 (`portal_duyet_don.kiem_ly_do_tu_choi`) — không có
		# lý do thì KHÔNG chuyển sang "Từ chối" được. Phải GHI XUỐNG CSDL,
		# không gán trên object: `apply_workflow` mở đầu bằng
		# `doc.load_from_db()` (frappe/model/workflow.py:102) nên mọi thứ
		# gán trên bản trong bộ nhớ bị xoá sạch — đúng như Desk, nơi form
		# được LƯU rồi mới bấm hành động workflow. Đây là một field dữ liệu
		# thường, KHÔNG phải cái cổng đang đo: cổng là chuyển tiếp trạng
		# thái, và nó vẫn đi qua `apply_workflow` thật.
		frappe.db.set_value(
			"Sales Order", ten_don, "custom_ly_do_tu_choi",
			"Hàng ngừng nhập, không cấp được lô này.", update_modified=False,
		)
		so = apply_workflow(so, "Từ chối")
		self.assertEqual(
			so.workflow_state, "Từ chối",
			"fixture chưa tới được trạng thái cần đo — bài test bên dưới "
			"sẽ nói dối nếu bỏ qua khẳng định này",
		)
		return so.name

	def _goi(self, user, **kw):
		frappe.set_user(user)
		try:
			return portal.portal_yeu_cau_cua_toi(**kw)
		finally:
			frappe.set_user("Administrator")

	def _dong(self, kq):
		return kq["rows"]

	def _ma_phieu(self, kq):
		return [r["de_xuat"] for r in self._dong(kq) if r["de_xuat"]]

	def _ma_don(self, kq):
		return [r["sales_order"] for r in self._dong(kq) if r["sales_order"]]

	# -- ca chính: MỘT lần gọi thấy CẢ dòng đời -------------------------------

	def test_phieu_nhap_va_don_da_giao_cua_cung_khoa_hien_trong_MOT_lan_goi(self):
		"""VẾ DƯƠNG, CA CHÍNH (QĐ-G11).

		Trước task này hai thứ đó nằm ở HAI màn: phiếu Nháp ở `/de-xuat`,
		đơn đã giao ở `/orders`. Nhân viên phải đoán trước yêu cầu của mình
		đang ở giai đoạn nội bộ nào mới tìm lại được nó."""
		kq = self._goi(self.user_huyethoc, limit=100)
		self.assertIn(self.phieu_nhap, self._ma_phieu(kq))
		self.assertIn(self.don_da_giao, self._ma_don(kq))

	def test_phieu_da_duyet_va_don_sinh_ra_tu_no_la_MOT_dong(self):
		"""Task 9 đã cho phiếu và đơn CÙNG một mã; danh sách gộp phải nhận
		ra chúng là MỘT yêu cầu, không phải hai."""
		kq = self._goi(self.user_huyethoc, limit=100)
		khop = [
			r for r in self._dong(kq)
			if r["de_xuat"] == self.phieu_da_duyet
			or r["sales_order"] == self.don_cua_phieu
		]
		self.assertEqual(
			len(khop), 1,
			f"Phiếu {self.phieu_da_duyet} và đơn {self.don_cua_phieu} phải "
			f"là MỘT dòng, đang ra {len(khop)}: {khop}",
		)
		# Và dòng đó phải mang CẢ HAI đầu mối, để màn danh sách mở được sang
		# đúng chứng từ mà không phải đoán.
		self.assertEqual(khop[0]["de_xuat"], self.phieu_da_duyet)
		self.assertEqual(khop[0]["sales_order"], self.don_cua_phieu)

	def test_tong_dem_sau_khi_gop_khong_dem_hai_lan(self):
		"""`tong` nuôi phân trang — đếm TRƯỚC khi gộp thì trang cuối rỗng
		và khách thấy một con số không khớp số dòng đếm được."""
		kq = self._goi(self.user_huyethoc, limit=100)
		self.assertEqual(kq["tong"], len(self._dong(kq)))

	# -- cách ly: trục KHÁCH HÀNG --------------------------------------------

	def test_khach_A_thay_yeu_cau_cua_chinh_minh(self):
		"""VẾ DƯƠNG của phép cách ly — thiếu nó thì một endpoint luôn trả
		rỗng cũng qua bài âm bên dưới."""
		kq = self._goi(self.user_quan_ly, limit=100)
		self.assertIn(self.phieu_nhap, self._ma_phieu(kq))
		self.assertIn(self.don_da_giao, self._ma_don(kq))

	def test_khach_A_khong_thay_yeu_cau_cua_khach_B(self):
		kq = self._goi(self.user_quan_ly, limit=100)
		self.assertNotIn(self.phieu_benh_vien_b, self._ma_phieu(kq))

	def test_khach_B_thay_yeu_cau_cua_chinh_minh(self):
		"""VẾ DƯƠNG ở phía bên kia — B phải thấy CỦA B, không chỉ "không
		thấy của A"."""
		kq = self._goi(self.user_benh_vien_b, limit=100)
		self.assertIn(self.phieu_benh_vien_b, self._ma_phieu(kq))
		self.assertNotIn(self.phieu_nhap, self._ma_phieu(kq))
		self.assertNotIn(self.don_da_giao, self._ma_don(kq))

	# -- cách ly: trục KHOA PHÒNG --------------------------------------------

	def test_nhan_vien_khoa_thay_yeu_cau_cua_khoa_minh(self):
		"""VẾ DƯƠNG."""
		kq = self._goi(self.user_huyethoc, limit=100)
		self.assertIn(self.phieu_nhap, self._ma_phieu(kq))

	def test_nhan_vien_khoa_khong_thay_yeu_cau_cua_khoa_khac(self):
		kq = self._goi(self.user_huyethoc, limit=100)
		self.assertNotIn(self.phieu_khoa_duoc, self._ma_phieu(kq))

	def test_nhan_vien_khoa_khac_khong_thay_DON_cua_khoa_khac(self):
		"""Trục khoa phải áp cho CẢ nhánh đơn hàng, không chỉ nhánh phiếu —
		đơn mang tổng tiền, đúng thứ `_khoa_query_condition` sinh ra để
		giấu."""
		kq = self._goi(self.user_duoc, limit=100)
		self.assertNotIn(self.don_da_giao, self._ma_don(kq))
		# vế dương đi kèm: khoa Dược VẪN thấy phiếu của chính mình
		self.assertIn(self.phieu_khoa_duoc, self._ma_phieu(kq))

	def test_quan_ly_thay_ca_hai_khoa(self):
		"""VẾ DƯƠNG của quản lý — nhìn xuyên mọi khoa TRONG bệnh viện mình."""
		kq = self._goi(self.user_quan_ly, limit=100)
		self.assertIn(self.phieu_nhap, self._ma_phieu(kq))
		self.assertIn(self.phieu_khoa_duoc, self._ma_phieu(kq))

	def test_thieu_cot_khoa_phong_thi_KHONG_ro_don_cua_khoa_khac(self):
		"""Fail-closed lúc triển khai — cùng lưới `_pham_vi_filters()` đã
		lập cho `portal_order_history`: site CHƯA chạy patch v1_23 thì nhánh
		đơn hàng phải BIẾN MẤT với nhân viên khoa, không được lặng lẽ trả
		đơn của MỌI khoa (và cũng không được ném lỗi CSDL 1054 thô).

		Đo trên NHÁNH ĐƠN (`nguon == 'don'`) — nhánh DUY NHẤT phải đọc cột
		`custom_khoa_phong` để biết khoa. Đơn đứng SAU một phiếu vẫn hiện
		bình thường: nó tới qua nhánh PHIẾU, mà phiếu có cột `khoa_phong`
		riêng của doctype, không dính patch v1_23."""
		with mock_patch(
			"miyano_portal.api.portal._cot_khoa_phong_ton_tai", return_value=False
		):
			kq = self._goi(self.user_huyethoc, limit=100)
		self.assertEqual([r for r in self._dong(kq) if r["nguon"] == "don"], [])
		self.assertNotIn(self.don_da_giao, self._ma_don(kq))
		# Phiếu (có trục khoa RIÊNG, không phụ thuộc cột custom) vẫn tới
		# được đúng người — "câm" đúng chỗ, không câm cả màn.
		self.assertIn(self.phieu_nhap, self._ma_phieu(kq))

	# -- giai đoạn: MỘT dòng đời ---------------------------------------------

	def test_giai_doan_cua_phieu_nhap(self):
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_phieu(kq, self.phieu_nhap)
		self.assertEqual(dong["giai_doan"], "nhap")

	def test_giai_doan_cua_don_da_giao(self):
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_don(kq, self.don_da_giao)
		self.assertEqual(dong["giai_doan"], "da_giao")

	def test_giai_doan_cua_phieu_cho_duyet(self):
		ten = self._tao_phieu(self.kh_a, self.khoa_huyethoc, self.user_huyethoc)
		doc = frappe.get_doc("Portal De Xuat Mua", ten)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		kq = self._goi(self.user_huyethoc, limit=100)
		self.assertEqual(self._tim_theo_phieu(kq, ten)["giai_doan"], "cho_duyet")

	def test_giai_doan_cua_phieu_vua_duyet_xong(self):
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_phieu(kq, self.phieu_da_duyet)
		self.assertEqual(dong["giai_doan"], "da_duyet")

	# -- Important (review vòng 1) — Miyano TỪ CHỐI đơn ------------------------

	def test_don_bi_MIYANO_TU_CHOI_khong_duoc_doc_ra_Da_duyet(self):
		"""`Từ chối` là một `workflow_state` CÓ THẬT của Sales Order
		(`setup/install_workflow.py`) — Sales User bấm được từ "Chờ Miyano
		xác nhận". Khối CASE xử lý `Từ chối` ở cấp PHIẾU nhưng bỏ sót cấp
		ĐƠN, nên đơn đã chết rơi vào `else` và đọc ra "Đã duyệt".

		Đo được trên đúng tài khoản nghiệm thu: `MD-HUYETHOC-260821-01`
		(khoa `KP-00002` của `buiviet9802@gmail.com`) đang hiện "Đã duyệt".
		Y tá đọc xong thì CHỜ VÔ HẠN một lô hàng Miyano đã huỷ từ 21/08.

		Thiếu sót này MÂU THUẪN với chính khối CASE: nó đã đặc biệt hoá
		`Khách huỷ` và `Báo giá hết hạn` từ ĐÚNG bộ từ vựng workflow đó."""
		self._miyano_tu_choi(self.don_cua_phieu)
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_phieu(kq, self.phieu_da_duyet)
		self.assertEqual(dong["giai_doan"], "tu_choi")

	def test_nhan_chi_tiet_cua_don_bi_tu_choi_khong_doc_ra_Cho_xac_nhan(self):
		"""Nhãn phụ cũng không cứu được trước bản vá: `_so_status_vi_full`
		chỉ ghi đè `Báo giá hết hạn` và `Khách huỷ`, nên một đơn bị từ chối
		đọc ra "Chờ xác nhận" — y hệt một đơn đang sống."""
		self._miyano_tu_choi(self.don_cua_phieu)
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_phieu(kq, self.phieu_da_duyet)
		self.assertEqual(dong["trang_thai_don"], "Miyano đã từ chối")

	def test_chip_Tu_choi_LOI_DUOC_don_bi_miyano_tu_choi(self):
		"""VẾ DƯƠNG của chính ngõ cụt — QĐ-G11 thêm hai giai đoạn ngõ cụt
		để một yêu cầu ĐÃ CHẾT vẫn TÌM LẠI ĐƯỢC. Trước bản vá, lọc chip
		"Từ chối" không lôi nó ra."""
		self._miyano_tu_choi(self.don_cua_phieu)
		kq = self._goi(self.user_huyethoc, limit=100, giai_doan="tu_choi")
		self.assertIn(self.phieu_da_duyet, self._ma_phieu(kq))

	def test_nhan_don_bi_tu_choi_dung_CA_o_danh_sach_don_cu(self):
		"""`_so_status_vi_full` là hàm DÙNG CHUNG — `portal_order_history`
		và `portal_order_track` cũng đọc nó. Sửa ở một chỗ mà đo ở một chỗ
		khác là cách duy nhất chứng minh nó không phải một nhánh riêng của
		màn gộp. Đi qua ĐƯỜNG CÔNG KHAI, không gọi hàm `_` trực tiếp."""
		self._miyano_tu_choi(self.don_cua_phieu)
		frappe.set_user(self.user_huyethoc)
		try:
			rows = portal.portal_order_history(limit=200)["rows"]
		finally:
			frappe.set_user("Administrator")
		don = next(r for r in rows if r["name"] == self.don_cua_phieu)
		self.assertEqual(don["status_vi"], "Miyano đã từ chối")

	def test_hai_nhan_ghi_de_da_co_KHONG_bi_dung_den(self):
		"""VẾ ĐỐI CHỨNG — bản vá không được kéo theo `Khách huỷ`/`Báo giá
		hết hạn` sang nhãn mới, và một đơn đang sống vẫn phải đọc ra "Chờ
		xác nhận"."""
		frappe.db.set_value(
			"Sales Order", self.don_cua_phieu, "workflow_state",
			"Khách huỷ", update_modified=False,
		)
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_phieu(kq, self.phieu_da_duyet)
		self.assertEqual(dong["giai_doan"], "da_huy")
		self.assertEqual(dong["trang_thai_don"], "Đã huỷ")

	# -- Ruling P42 — giao MỘT PHẦN chưa phải "Đã giao" ------------------------

	def test_giao_mot_phan_KHONG_duoc_ghi_la_Da_giao(self):
		"""Ruling P42 — ngưỡng cũ (`per_delivered > 0`) làm một đơn mới
		giao 25% hiện "Đã giao", trong khi nhãn phụ TRÊN CÙNG MỘT DÒNG ghi
		"Đang giao" và thanh tiến độ vẽ 25%. Hai câu trái ngược nhau đặt
		cạnh nhau; và khoa đang chờ nốt 75% còn lại thì đọc câu sai."""
		frappe.db.set_value(
			"Sales Order", self.don_cua_phieu,
			{"status": "To Deliver and Bill", "per_delivered": 25},
			update_modified=False,
		)
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_phieu(kq, self.phieu_da_duyet)
		self.assertNotEqual(dong["giai_doan"], "da_giao")
		self.assertEqual(dong["giai_doan"], "da_duyet")
		# Nhãn phụ VẪN nói đúng phần còn lại — đó là lý do KHÔNG cần một
		# giai đoạn thứ sáu (QĐ-G11 chốt năm).
		self.assertEqual(dong["trang_thai_don"], "Đang giao")

	def test_giao_du_100_moi_la_Da_giao(self):
		"""VẾ DƯƠNG của chính ngưỡng — thiếu nó thì một ngưỡng không bao
		giờ đạt (`> 100`) cũng qua bài trên."""
		frappe.db.set_value(
			"Sales Order", self.don_cua_phieu,
			{"status": "To Bill", "per_delivered": 100},
			update_modified=False,
		)
		kq = self._goi(self.user_huyethoc, limit=100)
		self.assertEqual(
			self._tim_theo_phieu(kq, self.phieu_da_duyet)["giai_doan"], "da_giao"
		)

	def test_giai_doan_cho_khach_dong_y_khi_don_dang_o_vong_bao_gia(self):
		"""Chốt canh cho chính giai đoạn `cho_khach_dong_y` của QĐ-G11 — nó
		phải TỚI ĐƯỢC, không phải một chip luôn rỗng (bài học "Việc (d)" của
		`DeXuatList.vue`). Trạng thái này do `hooks`/`portal_bao_gia` ghi
		bằng `db.set_value` y như dòng dưới.

		Ruling P54 (26/08/2026) — bài này TRƯỚC ĐÂY ghim chuỗi hiển thị
		`"Chờ báo giá"`. Giữ nguyên bài, đổi thứ nó ghim: endpoint nay trả
		KHOÁ NỘI BỘ, còn nhãn tiếng Việt ("Chờ quý vị đồng ý") là việc của
		tầng hiển thị và được ghim riêng ở `test_giai_doan_khoa_va_nhan.py`.
		Ghim khoá bằng CHUỖI VIẾT THẲNG, không qua hằng số `GIAI_DOAN_*`:
		so với hằng số thì bài test đi theo mọi lần đổi giá trị và không
		còn ghim gì cả."""
		frappe.db.set_value(
			"Sales Order", self.don_cua_phieu, "workflow_state",
			"Chờ khách đồng ý", update_modified=False,
		)
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_phieu(kq, self.phieu_da_duyet)
		self.assertEqual(dong["giai_doan"], "cho_khach_dong_y")
		# Nhãn CHI TIẾT của đơn vẫn đi kèm — giai đoạn gộp không được nuốt
		# mất tín hiệu "đang chờ CHÍNH BẠN đồng ý".
		self.assertEqual(dong["trang_thai_don"], "Chờ xác nhận")

	def test_bi_danh_chuoi_CU_van_ra_dung_tap_ket_qua(self):
		"""Ruling P54, mục 3 — link `?chip=Chờ báo giá` ĐÃ GỬI CHO BỆNH VIỆN
		phải vẫn dẫn đúng chỗ: không rơi lặng lẽ về "Tất cả", cũng không ném
		lỗi cho một liên kết hợp lệ ngày hôm qua.

		So HAI TẬP KẾT QUẢ chứ không chỉ "gọi được mà không ném": một bí
		danh trỏ nhầm khoá vẫn "gọi được" nhưng trả về tập của giai đoạn
		khác. `assertIn` đi kèm để hai tập cùng RỖNG không thể xanh — đó là
		cách hỏng dễ xảy ra nhất nếu fixture trôi.

		`_tap(...)` nuốt `ValidationError` thành một CHUỖI có chữ thay vì để
		nó nổ: mục đích là bài này đỏ ở CẤP KHẲNG ĐỊNH (so hai tập, đọc ra
		ngay vế nào ném) chứ không đỏ ở cấp exception, nơi thông báo lỗi
		không nói được vế kia trả về gì."""
		frappe.db.set_value(
			"Sales Order", self.don_cua_phieu, "workflow_state",
			"Chờ khách đồng ý", update_modified=False,
		)

		def _tap(gd):
			try:
				kq = self._goi(self.user_huyethoc, limit=100, giai_doan=gd)
			except frappe.ValidationError as e:
				return f"NÉM: {e}"
			return {r["de_xuat"] for r in self._dong(kq)}

		theo_khoa = _tap("cho_khach_dong_y")
		self.assertIn(self.phieu_da_duyet, theo_khoa)
		self.assertEqual(_tap("Chờ báo giá"), theo_khoa)

	def test_giai_doan_cua_phieu_bi_tu_choi(self):
		"""Ngõ cụt VẪN phải tìm lại được — người vừa bị từ chối là người đi
		tìm phiếu đó ngay sau đó."""
		ten = self._tao_phieu(self.kh_a, self.khoa_huyethoc, self.user_huyethoc)
		doc = frappe.get_doc("Portal De Xuat Mua", ten)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		frappe.set_user(self.user_quan_ly)
		try:
			de_xuat.de_xuat_tu_choi(ten, "không đủ ngân sách")
		finally:
			frappe.set_user("Administrator")
		kq = self._goi(self.user_huyethoc, limit=100)
		self.assertEqual(self._tim_theo_phieu(kq, ten)["giai_doan"], "tu_choi")

	# -- mã hiện ra cho người dùng --------------------------------------------

	def test_phieu_nhap_KHONG_lo_ten_noi_bo_lam_ma(self):
		"""`DXM-2026-000xx` là tên nội bộ (naming_series), KHÔNG phải mã
		khoa đọc. Phiếu Nháp chưa có mã (mã cấp lúc Gửi duyệt) → `ma` rỗng,
		và tầng hiển thị nói thẳng "(chưa gửi duyệt)" — đúng cách
		`DeXuatList.vue` đã làm trước khi gộp. Rơi về `p.name` là để lộ mã
		hệ thống ra mặt người dùng ở ĐÚNG dòng đầu tiên một nhân viên có
		phiếu nháp nhìn thấy."""
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_phieu(kq, self.phieu_nhap)
		self.assertEqual(dong["ma"], "")
		self.assertNotIn("DXM-", str(dong["ma"]))

	def test_phieu_da_gui_duyet_mang_dung_ma_cua_khach(self):
		"""VẾ DƯƠNG — thiếu nó thì một endpoint luôn trả `ma = ""` cũng qua
		bài trên."""
		ma_that = frappe.db.get_value(
			"Portal De Xuat Mua", self.phieu_da_duyet, "ma_de_xuat"
		)
		self.assertTrue(ma_that, "fixture chưa cấp mã — bài này không đo được gì")
		kq = self._goi(self.user_huyethoc, limit=100)
		self.assertEqual(self._tim_theo_phieu(kq, self.phieu_da_duyet)["ma"], ma_that)

	def test_don_khong_qua_de_xuat_mang_chinh_ten_don_lam_ma(self):
		"""Đơn cũ (`SAL-ORD-...`) chưa từng đi qua phiếu nào — tên đơn CHÍNH
		LÀ mã khách vẫn đối chiếu với Miyano, không có gì để giấu."""
		kq = self._goi(self.user_huyethoc, limit=100)
		self.assertEqual(self._tim_theo_don(kq, self.don_da_giao)["ma"], self.don_da_giao)

	# -- lọc + phân trang -----------------------------------------------------

	def test_loc_giai_doan_loc_TRONG_SQL_chu_khong_phai_tren_mot_trang(self):
		"""Hồi quy đã bắt một lần ở `Orders.vue` (brief 2026-08-16): lọc
		phía client trên ĐÚNG MỘT trang đã tải làm khách chọn "xem 1 dòng"
		rồi bấm một chip thì thấy TRỐNG, dù dòng khớp nằm ở trang sau —
		khách kết luận SAI là mình không có yêu cầu nào ở giai đoạn đó."""
		khong_loc = self._goi(self.user_huyethoc, limit=1, start=0)
		self.assertEqual(len(self._dong(khong_loc)), 1)
		# Phiếu Nháp KHÔNG nằm ở trang 1 khi không lọc (nó được tạo sớm
		# nhất, mà thứ tự là mới-nhất-trước) — thiếu khẳng định này thì bài
		# dưới có thể xanh vì TRÙNG HỢP, không vì lọc chạy ở SQL.
		self.assertNotEqual(self._dong(khong_loc)[0]["de_xuat"], self.phieu_nhap)
		co_loc = self._goi(self.user_huyethoc, limit=1, start=0, giai_doan="nhap")
		self.assertEqual(
			[r["de_xuat"] for r in self._dong(co_loc)], [self.phieu_nhap]
		)
		self.assertEqual(co_loc["tong"], 1)

	def test_tong_khong_doi_theo_co_trang(self):
		to = self._goi(self.user_huyethoc, limit=100)["tong"]
		nho = self._goi(self.user_huyethoc, limit=1)["tong"]
		self.assertEqual(to, nho)
		self.assertGreater(to, 1, "fixture quá nghèo để bài này nói được gì")

	def test_phan_trang_khong_lap_va_khong_bo_sot_dong(self):
		tat_ca = self._goi(self.user_huyethoc, limit=100)
		khoa = [r["khoa_sap_xep"] for r in self._dong(tat_ca)]
		lat = []
		for i in range(len(khoa)):
			lat += [
				r["khoa_sap_xep"]
				for r in self._dong(self._goi(self.user_huyethoc, limit=1, start=i))
			]
		self.assertEqual(lat, khoa)

	# -- lọc theo khoa phòng (03/09/2026) -------------------------------------
	#
	# Bộ lọc này SANG từ màn `/duyet` đã nghỉ. Yêu cầu gốc của chủ đầu tư
	# nằm trong chính `DuyetList.vue`: "quản lý sẽ filter theo khoa … cốt
	# lõi là để quản lý biết được khoa nào đang mua cái gì mà để duyệt".
	# Bỏ màn đó mà không mang bộ lọc theo là đánh rơi một yêu cầu đã chốt.
	#
	# Lọc ở SQL, KHÔNG ở client — cùng bài học `giai_doan` ngay trên: danh
	# sách này phân trang ở server, nên lọc trên một trang đã tải sẽ hiện 3
	# dòng và ngầm bảo khoa đó chỉ có 3 (đúng lỗi `DuyetList.vue` tự cảnh
	# báo về trần `limit` của nó).

	def test_quan_ly_loc_duoc_theo_khoa_phong(self):
		khong_loc = self._goi(self.user_quan_ly, limit=100)
		self.assertIn(self.phieu_khoa_duoc, self._ma_phieu(khong_loc))
		self.assertIn(self.phieu_nhap, self._ma_phieu(khong_loc))
		co_loc = self._goi(self.user_quan_ly, limit=100, khoa_phong=self.khoa_duoc)
		self.assertIn(self.phieu_khoa_duoc, self._ma_phieu(co_loc))
		self.assertNotIn(self.phieu_nhap, self._ma_phieu(co_loc))

	def test_loc_khoa_loc_TRONG_SQL_chu_khong_phai_tren_mot_trang(self):
		"""`tong` phải là tổng ĐÃ LỌC. Lọc phía client để nguyên `tong` cũ
		làm thanh phân trang vẽ ra những trang rỗng — và quản lý đọc con số
		đó như số phiếu của khoa."""
		co_loc = self._goi(
			self.user_quan_ly, limit=1, start=0, khoa_phong=self.khoa_duoc
		)
		self.assertEqual([r["de_xuat"] for r in self._dong(co_loc)],
		                 [self.phieu_khoa_duoc])
		self.assertEqual(co_loc["tong"], 1)

	def test_loc_khoa_cong_don_voi_loc_giai_doan(self):
		"""Hai bộ lọc phải GIAO nhau, không cái nào nuốt cái nào — quản lý
		mở chip "Chờ duyệt" rồi chọn khoa là ca dùng chính của màn này."""
		kq = self._goi(
			self.user_quan_ly, limit=100,
			khoa_phong=self.khoa_huyethoc, giai_doan="nhap",
		)
		ma = self._ma_phieu(kq)
		self.assertIn(self.phieu_nhap, ma)
		self.assertNotIn(self.phieu_khoa_duoc, ma)   # đúng giai đoạn, sai khoa
		self.assertNotIn(self.phieu_da_duyet, ma)    # đúng khoa, sai giai đoạn

	def test_nhan_vien_khoa_truyen_khoa_KHAC_khong_thay_gi_them(self):
		"""Tham số này chỉ được phép THU HẸP. Nhân viên khoa Huyết học gõ
		tay `khoa_phong=<khoa Dược>` phải ra RỖNG — không phải ra phiếu của
		khoa Dược. Chốt thật nằm ở `pham_vi_don()` (đã kẹp `dk_phieu`/
		`dk_don` trước khi bộ lọc này chạy); bài này canh rằng bộ lọc mới
		không mở một đường vòng qua nó."""
		kq = self._goi(
			self.user_huyethoc, limit=100, khoa_phong=self.khoa_duoc
		)
		self.assertEqual(self._dong(kq), [])
		self.assertEqual(kq["tong"], 0)

	def test_nhan_vien_khoa_truyen_dung_khoa_minh_van_thay(self):
		"""VẾ DƯƠNG — thiếu nó thì `1=0` cũng qua bài trên."""
		kq = self._goi(
			self.user_huyethoc, limit=100, khoa_phong=self.khoa_huyethoc
		)
		self.assertIn(self.phieu_nhap, self._ma_phieu(kq))

	def test_khong_truyen_khoa_thi_khong_loc_gi(self):
		"""VẾ DƯƠNG cho chính tham số — mặc định phải giữ nguyên hành vi
		cũ, không im lặng lọc theo khoa của người gọi."""
		kq = self._goi(self.user_quan_ly, limit=100)
		ma = self._ma_phieu(kq)
		self.assertIn(self.phieu_nhap, ma)
		self.assertIn(self.phieu_khoa_duoc, ma)

	def test_giai_doan_la_thi_bao_loi_chu_khong_am_tham_bo_loc(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._goi(self.user_huyethoc, giai_doan="Xanh lá")
		self.assertIn("Xanh lá", str(ctx.exception))

	# -- tiện ích -------------------------------------------------------------

	def _tim_theo_phieu(self, kq, ten):
		for r in self._dong(kq):
			if r["de_xuat"] == ten:
				return r
		self.fail(f"Không thấy phiếu {ten} trong danh sách: {self._dong(kq)}")

	def _tim_theo_don(self, kq, ten):
		for r in self._dong(kq):
			if r["sales_order"] == ten:
				return r
		self.fail(f"Không thấy đơn {ten} trong danh sách: {self._dong(kq)}")


class TestDuongCuVaSoCua(FrappeTestCase):
	"""QĐ-G11 — đường cũ CHUYỂN HƯỚNG (không 404) và nav còn 8/7 mục.

	Đọc file JS bằng regex CỐ Ý — cùng lý do và cùng tiền lệ
	`test_de_xuat_action_registry.py`: frontend không có hạ tầng test, và
	hai điều được canh ở đây (một route bị xoá, một mục nav mọc lại) không
	có bước build nào bắt được. Không dựng hạ tầng JS mới cho việc này.
	"""

	ROUTER = FRONTEND_SRC / "router.js"
	APP = FRONTEND_SRC / "App.vue"

	# Năm đường nằm trong bookmark của khách VÀ trong link của thông báo tự
	# động đã gửi đi. Trả 404 cho một đường đang chạy là hồi quy.
	#
	# `/duyet` vào danh sách này 03/09/2026, khi màn duyệt riêng nghỉ — đó
	# là đường quản lý mở HÀNG NGÀY, đúng loại đường nằm trong tab ghim.
	DUONG_CU = ("/orders", "/orders/:name", "/de-xuat", "/de-xuat/:ten", "/duyet")

	def _khoi_route(self, path: str) -> str:
		"""Khối `{ ... }` khai báo route có `path: '<path>'`."""
		noi_dung = self.ROUTER.read_text(encoding="utf-8")
		moc = re.search(
			r"\{[^{}]*path:\s*'" + re.escape(path) + r"'.*?\n\s*\},?\n",
			noi_dung, re.S,
		)
		if moc:
			return moc.group(0)
		moc = re.search(r"\{[^{}]*path:\s*'" + re.escape(path) + r"'[^{}]*\}", noi_dung)
		self.assertIsNotNone(
			moc, f"router.js KHÔNG còn khai báo đường cũ {path} — nó sẽ 404."
		)
		return moc.group(0)

	def test_duong_cu_van_con_khai_bao(self):
		for path in self.DUONG_CU:
			self._khoi_route(path)

	def test_duong_cu_la_CHUYEN_HUONG_chu_khong_phai_man_hinh(self):
		for path in self.DUONG_CU:
			khoi = self._khoi_route(path)
			self.assertIn("redirect", khoi, f"{path} phải chuyển hướng")
			self.assertNotIn(
				"component:", khoi,
				f"{path} vẫn trỏ vào một component — hai cửa cho cùng một thứ",
			)

	def test_duong_cu_duyet_van_mang_chip_cho_duyet(self):
		"""Review TOÀN NHÁNH (03/09/2026) — TRƯỚC bài này, KHÔNG assert nào
		trong cả suite nhắc `chip` hay `cho_duyet` cho đường `/duyet`. Xoá
		`query: { chip: 'cho_duyet' }` khỏi `router.js` thì bookmark HÀNG
		NGÀY của quản lý rơi vào một danh sách toàn viện chưa lọc, mà cả
		suite vẫn xanh — `test_duong_cu_la_CHUYEN_HUONG...` chỉ hỏi có
		`redirect` hay không.

		`/duyet` khác bốn đường cũ còn lại ở chỗ: chúng chỉ cần TỚI ĐÚNG
		MÀN, còn đường này mang theo cả BỘ LỌC — màn duyệt riêng đã nghỉ,
		nên "hàng chờ của tôi" giờ chỉ tồn tại dưới dạng danh sách gộp + chip
		`cho_duyet` (chip đó gom đúng hai trạng thái màn cũ gộp)."""
		khoi = self._khoi_route("/duyet")
		self.assertIn(
			"chip", khoi,
			"/duyet chuyển hướng mà KHÔNG mang `chip` — bookmark hàng ngày của "
			"quản lý rơi vào danh sách toàn viện chưa lọc.",
		)
		self.assertIn(
			"cho_duyet", khoi,
			"/duyet mang một chip KHÁC `cho_duyet` — hàng chờ của quản lý là "
			"đúng chip đó, không phải chip nào khác.",
		)

	def test_badge_cho_duyet_dan_toi_DANH_SACH_DA_LOC(self):
		"""Review TOÀN NHÁNH (03/09/2026) — mục nav là `to: '/yeu-cau'` TRẦN.
		Quản lý thấy badge "7", bấm vào rơi vào danh sách toàn viện chưa lọc
		và phải tự biết bấm tiếp chip "Chờ duyệt". Cả `App.vue` lẫn
		`cho-duyet.js` đều khẳng định "badge và đích nó dẫn tới không nói hai
		con số khác nhau" — câu đó SAI chừng nào đích còn trần.

		Đích có điều kiện, KHÔNG phải một chuỗi cứng trong mảng NAV: mục này
		là mục CHUNG của mọi vai trò (nhân viên khoa dùng chính nó để xem yêu
		cầu của mình). Nên phép lọc chỉ được gắn khi CHÍNH badge đang hiện —
		cùng cờ `hienBadgeDuyet` mà template hỏi, không phải một phép suy vai
		trò thứ hai đặt cạnh nó rồi sớm muộn lệch."""
		noi_dung = self.APP.read_text(encoding="utf-8")
		moc = re.search(r"function dichNav\([^)]*\)\s*\{.*?\n\}", noi_dung, re.S)
		self.assertIsNotNone(
			moc,
			"App.vue không có `function dichNav(...)` — mục nav mang badge vẫn "
			"trỏ vào một danh sách chưa lọc.",
		)
		than = moc.group(0)
		self.assertIn(
			"cho_duyet", than,
			"`dichNav()` không gắn chip `cho_duyet` — badge dẫn tới danh sách "
			"toàn viện, không phải bảy phiếu nó vừa đếm.",
		)
		self.assertIn(
			"hienBadgeDuyet", than,
			"`dichNav()` không hỏi `hienBadgeDuyet` — hoặc nó lọc cho CẢ nhân "
			"viên khoa (mục nav chung, họ không có hàng chờ nào), hoặc nó suy "
			"vai trò lần thứ hai bên cạnh cờ template đang dùng.",
		)
		self.assertRegex(
			noi_dung, r':to="dichNav\(n\)"',
			"Thanh nav không dùng `dichNav(n)` — hàm tính đích được khai nhưng "
			"không ai hỏi nó.",
		)

	def test_man_danh_sach_NGHE_chip_doi_giua_chung(self):
		"""Nửa còn lại của cùng một bản vá: đích mang `?chip=cho_duyet` chỉ
		có tác dụng nếu màn CHỊU NGHE.

		`YeuCauList.vue` khôi phục chip trong `onMounted` — mà Vue Router
		KHÔNG dựng lại component khi chỉ QUERY đổi trên cùng một route. Quản
		lý ĐANG ĐỨNG ở `/yeu-cau` (ca thường gặp nhất — vừa duyệt xong một
		phiếu rồi bấm badge lần nữa) sẽ thấy URL đổi mà bộ lọc đứng yên. Xoá
		watcher này thì bản vá Việc 4 im lặng trở lại thành vô tác dụng cho
		đúng người nó phục vụ, và không bước build nào nói gì."""
		man = (FRONTEND_SRC / "views" / "YeuCauList.vue").read_text(encoding="utf-8")
		self.assertRegex(
			man, r"watch\(\(\)\s*=>\s*route\.query\.chip",
			"YeuCauList.vue không theo dõi `route.query.chip` — đích mang chip "
			"không đổi được bộ lọc khi người dùng đã đứng sẵn trên màn này.",
		)

	def test_duong_cu_co_tham_so_GIU_NGUYEN_tham_so(self):
		"""Link trong email thông báo trỏ tới MỘT chứng từ cụ thể. Chuyển
		hướng về danh sách suông là đánh mất đúng thứ người nhận đang tìm."""
		self.assertIn("params", self._khoi_route("/orders/:name"))
		self.assertIn("params", self._khoi_route("/de-xuat/:ten"))

	def test_man_yeu_cau_ton_tai(self):
		noi_dung = self.ROUTER.read_text(encoding="utf-8")
		self.assertIn("'/yeu-cau'", noi_dung)
		self.assertIn("YeuCauList", noi_dung)

	def test_khong_con_man_danh_sach_cu(self):
		"""Ba màn danh sách cũ NGHỈ — còn file là còn đường mọc lại một
		mục nav thứ hai cho cùng một thứ."""
		self.assertFalse(
			(FRONTEND_SRC / "views" / "Orders.vue").exists(),
			"Orders.vue phải nghỉ (gộp vào YeuCauList.vue)",
		)
		self.assertFalse(
			(FRONTEND_SRC / "views" / "DeXuatList.vue").exists(),
			"DeXuatList.vue phải nghỉ (gộp vào YeuCauList.vue)",
		)
		# 03/09/2026 — hàng chờ duyệt nay là CHÍNH màn này lọc chip
		# `cho_duyet`. Giữ file lại là giữ nguyên vẹn một màn chỉ còn thiếu
		# một dòng trong `router.js` để sống lại.
		self.assertFalse(
			(FRONTEND_SRC / "views" / "DuyetList.vue").exists(),
			"DuyetList.vue phải nghỉ (hàng chờ = YeuCauList.vue + chip cho_duyet)",
		)
		# Hai màn CHI TIẾT cũ (`OrderDetail.vue`/`DeXuatDetail.vue`) cũng đã
		# nghỉ 03/09/2026, nhưng chúng được canh ở
		# `test_chi_tiet_gop.py::test_hai_man_cu_da_nghi` — bài này chỉ nói
		# về màn DANH SÁCH.

	def _dong_nav(self) -> list[str]:
		"""Mỗi mục nav là MỘT dòng trong mảng `const NAV = [...]` của
		App.vue (dòng chú thích xen giữa không mang `key:` nên tự rụng)."""
		noi_dung = self.APP.read_text(encoding="utf-8")
		moc = re.search(r"const NAV = \[(.*?)\n\]", noi_dung, re.S)
		self.assertIsNotNone(moc, "Không đọc được mảng NAV trong App.vue")
		return [d for d in moc.group(1).split("\n") if re.search(r"key:\s*'", d)]

	def _muc_nav(self) -> list[str]:
		return [re.search(r"key:\s*'([\w-]+)'", d).group(1) for d in self._dong_nav()]

	def _dong_badge_duyet(self) -> str:
		"""Dòng `const hienBadgeDuyet = computed(...)` — chốt vai trò DUY
		NHẤT còn lại trên thanh nav sau 03/09/2026."""
		noi_dung = self.APP.read_text(encoding="utf-8")
		moc = re.search(r"const hienBadgeDuyet\s*=\s*computed\(.*?\)\n", noi_dung, re.S)
		self.assertIsNotNone(
			moc,
			"App.vue không còn `const hienBadgeDuyet = computed(...)` — badge "
			"số phiếu chờ duyệt không còn chỗ nào hỏi vai trò.",
		)
		return moc.group(0)

	def test_badge_cho_duyet_van_HOI_vai_tro_chu_khong_chi_hien_theo_so(self):
		"""Thay cho `test_nav_thuc_su_LOC_theo_vai_tro...` (bỏ 03/09/2026
		cùng mục nav "Duyệt" — mảng NAV không còn mục nào theo vai trò, nên
		`navItems` thôi lọc).

		Thứ CÒN theo vai trò là badge số phiếu chờ duyệt trên mục "Danh sách
		đơn hàng". Nó PHẢI tự hỏi `la_quan_ly`, không được dựa vào việc
		`capNhatChoDuyetCount()` tình cờ để `choDuyetCount` bằng 0 cho nhân
		viên khoa: một tín hiệu phân quyền suy ra từ "giá trị mặc định tình
		cờ đúng" hỏng lặng lẽ vào ngày ai đó nạp con số ấy từ chỗ khác — và
		khi đó nhân viên khoa thấy số phiếu chờ của TOÀN VIỆN.

		Đây là lần thứ tám dự án dính kiểu "test trông như phủ mà chẳng kiểm
		gì", và lần này nó gác một thứ thuộc về PHÂN QUYỀN."""
		dong = self._dong_badge_duyet()
		# ĐÚNG khoá `me.la_quan_ly`, KHÔNG tự suy từ `vai_tro === 'Quản lý'`
		# — kế hoạch uỷ quyền tạm thời sẽ làm phép so chuỗi đó bỏ sót.
		self.assertIn(
			"la_quan_ly", dong,
			"`hienBadgeDuyet` không đọc `store.me.la_quan_ly` — badge hàng chờ "
			"của quản lý sẽ hiện cho mọi vai trò.",
		)
		# Và badge phải THẬT SỰ đi qua cờ đó trong template, không chỉ khai
		# một computed rồi vẽ bằng biến khác.
		noi_dung = self.APP.read_text(encoding="utf-8")
		self.assertRegex(
			noi_dung, r"v-if=\"n\.duyet && hienBadgeDuyet\"",
			"Badge trên thanh nav không dùng `hienBadgeDuyet` — cờ vai trò được "
			"khai nhưng không ai hỏi nó.",
		)

	def test_so_muc_nav_dung_7_cho_moi_vai_tro(self):
		"""Nghiệm thu của chủ đầu tư đếm bằng MẮT trên thanh nav. 11 cửa ban
		đầu → 9 sau Task 10 → 8/7 sau Task 11 → 7 cho MỌI vai trò từ
		03/09/2026 (mục "Duyệt" nghỉ, hàng chờ về chung "Danh sách đơn
		hàng").

		`requireQuanLy` phải biến mất KHỎI mảng NAV cùng lúc: một cờ không
		còn ai đọc, nằm lại trong dòng khai báo, đọc như một chốt phân
		quyền còn sống."""
		self.test_badge_cho_duyet_van_HOI_vai_tro_chu_khong_chi_hien_theo_so()
		muc = self._muc_nav()
		self.assertEqual(len(muc), 7, f"Nav phải còn 7 mục, đang là {muc}")
		# Soát TRÊN CÁC DÒNG KHAI BÁO của mảng NAV, không trên cả file: chữ
		# `requireQuanLy` còn được nhắc trong chú thích giải thích vì sao nó
		# đã đi, và một chú thích lịch sử không phải một cờ còn sống.
		con_co = [d for d in self._dong_nav() if "requireQuanLy" in d]
		self.assertEqual(
			con_co, [],
			"Cờ `requireQuanLy` không còn ai đọc (navItems thôi lọc) mà vẫn "
			f"nằm trong dòng khai báo NAV: {con_co}. Bỏ hẳn, đừng để lại — "
			"nó đọc như một chốt phân quyền còn hiệu lực.",
		)

	def test_nav_khong_con_hai_cua_cho_cung_mot_thu(self):
		muc = self._muc_nav()
		self.assertIn("yeu-cau", muc)
		self.assertNotIn("orders", muc)
		self.assertNotIn("de-xuat", muc)
		# 03/09/2026 — "Duyệt" NAY ĐÃ gộp vào đây, đảo ngược khẳng định cũ
		# ("hàng chờ việc khác danh sách của tôi"). Điều đổi ý kiến: việc
		# DUYỆT nằm ở màn CHI TIẾT, nên `/duyet` chưa bao giờ là một chỗ làm
		# việc — chỉ là bản sao thứ hai của cùng bộ dữ liệu, tức đúng thứ
		# Task 11 dỡ ở hai mục kia.
		self.assertNotIn("duyet", muc)
