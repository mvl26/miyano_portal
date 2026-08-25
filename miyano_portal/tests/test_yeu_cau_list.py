"""Task 11 (QĐ-G11) — MỘT danh sách, MỘT dòng đời: `portal_yeu_cau_cua_toi`.

Lỗi đang sửa: một yêu cầu của khoa nằm ở "Đề xuất mua" khi còn là phiếu rồi
NHẢY sang "Đơn hàng của tôi" sau khi quản lý duyệt. Nhân viên phải biết
trước yêu cầu của mình đang ở giai đoạn NỘI BỘ nào mới tìm lại được nó —
tức phải học sơ đồ kiến trúc của hệ thống.

Endpoint gộp trả về đúng MỘT dòng cho mỗi yêu cầu, ở bất kỳ giai đoạn nào:
`Nháp → Chờ duyệt → Đã duyệt → Chờ báo giá → Đã giao` (cộng hai ngõ cụt
`Từ chối`/`Đã huỷ` — trạng thái THẬT mà người dùng tự đưa yêu cầu của mình
vào, xem bài học "Việc (d)" của `DeXuatList.vue`).

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
		self.assertEqual(dong["giai_doan"], "Nháp")

	def test_giai_doan_cua_don_da_giao(self):
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_don(kq, self.don_da_giao)
		self.assertEqual(dong["giai_doan"], "Đã giao")

	def test_giai_doan_cua_phieu_cho_duyet(self):
		ten = self._tao_phieu(self.kh_a, self.khoa_huyethoc, self.user_huyethoc)
		doc = frappe.get_doc("Portal De Xuat Mua", ten)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		kq = self._goi(self.user_huyethoc, limit=100)
		self.assertEqual(self._tim_theo_phieu(kq, ten)["giai_doan"], "Chờ duyệt")

	def test_giai_doan_cua_phieu_vua_duyet_xong(self):
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_phieu(kq, self.phieu_da_duyet)
		self.assertEqual(dong["giai_doan"], "Đã duyệt")

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
		self.assertEqual(dong["giai_doan"], "Từ chối")

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
		kq = self._goi(self.user_huyethoc, limit=100, giai_doan="Từ chối")
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
		self.assertEqual(dong["giai_doan"], "Đã huỷ")
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
		self.assertNotEqual(dong["giai_doan"], "Đã giao")
		self.assertEqual(dong["giai_doan"], "Đã duyệt")
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
			self._tim_theo_phieu(kq, self.phieu_da_duyet)["giai_doan"], "Đã giao"
		)

	def test_giai_doan_cho_bao_gia_khi_don_dang_o_vong_bao_gia(self):
		"""Chốt canh cho chính giai đoạn "Chờ báo giá" của QĐ-G11 — nó phải
		TỚI ĐƯỢC, không phải một chip luôn rỗng (bài học "Việc (d)" của
		`DeXuatList.vue`). Trạng thái này do `hooks`/`portal_bao_gia` ghi
		bằng `db.set_value` y như dòng dưới."""
		frappe.db.set_value(
			"Sales Order", self.don_cua_phieu, "workflow_state",
			"Chờ khách đồng ý", update_modified=False,
		)
		kq = self._goi(self.user_huyethoc, limit=100)
		dong = self._tim_theo_phieu(kq, self.phieu_da_duyet)
		self.assertEqual(dong["giai_doan"], "Chờ báo giá")
		# Nhãn CHI TIẾT của đơn vẫn đi kèm — giai đoạn gộp không được nuốt
		# mất tín hiệu "đang chờ CHÍNH BẠN đồng ý".
		self.assertEqual(dong["trang_thai_don"], "Chờ xác nhận")

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
		self.assertEqual(self._tim_theo_phieu(kq, ten)["giai_doan"], "Từ chối")

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
		co_loc = self._goi(self.user_huyethoc, limit=1, start=0, giai_doan="Nháp")
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

	# Bốn đường nằm trong bookmark của khách VÀ trong link của thông báo tự
	# động đã gửi đi. Trả 404 cho một đường đang chạy là hồi quy.
	DUONG_CU = ("/orders", "/orders/:name", "/de-xuat", "/de-xuat/:ten")

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
		"""Hai màn danh sách cũ NGHỈ — còn file là còn đường mọc lại một
		mục nav thứ hai cho cùng một thứ."""
		self.assertFalse(
			(FRONTEND_SRC / "views" / "Orders.vue").exists(),
			"Orders.vue phải nghỉ (gộp vào YeuCauList.vue)",
		)
		self.assertFalse(
			(FRONTEND_SRC / "views" / "DeXuatList.vue").exists(),
			"DeXuatList.vue phải nghỉ (gộp vào YeuCauList.vue)",
		)

	def _dong_nav(self) -> list[str]:
		"""Mỗi mục nav là MỘT dòng trong mảng `const NAV = [...]` của
		App.vue (dòng chú thích xen giữa không mang `key:` nên tự rụng)."""
		noi_dung = self.APP.read_text(encoding="utf-8")
		moc = re.search(r"const NAV = \[(.*?)\n\]", noi_dung, re.S)
		self.assertIsNotNone(moc, "Không đọc được mảng NAV trong App.vue")
		return [d for d in moc.group(1).split("\n") if re.search(r"key:\s*'", d)]

	def _muc_nav(self) -> list[str]:
		return [re.search(r"key:\s*'([\w-]+)'", d).group(1) for d in self._dong_nav()]

	def _muc_nav_chi_quan_ly(self) -> list[str]:
		return [
			re.search(r"key:\s*'([\w-]+)'", d).group(1)
			for d in self._dong_nav()
			if "requireQuanLy" in d
		]

	def _dong_loc_vai_tro(self) -> str:
		"""Dòng `const navItems = computed(...)` — BỘ LỌC vai trò THẬT SỰ
		chạy lúc dựng thanh nav, khác hẳn cờ `requireQuanLy` nằm trong dòng
		KHAI BÁO của mảng `NAV`."""
		noi_dung = self.APP.read_text(encoding="utf-8")
		moc = re.search(r"const navItems\s*=\s*computed\(.*?\)\n", noi_dung, re.S)
		self.assertIsNotNone(
			moc,
			"App.vue không còn `const navItems = computed(...)` — thanh nav "
			"không còn chỗ nào lọc theo vai trò.",
		)
		return moc.group(0)

	def test_nav_thuc_su_LOC_theo_vai_tro_chu_khong_chi_khai_bao_co(self):
		"""Minor-3 (review vòng 1) — phép ĐẾM bên dưới đọc cờ `requireQuanLy`
		trong dòng KHAI BÁO của mảng `NAV`, rồi suy ra 7 bằng `8 − 1`. Xoá
		`.filter(...)` ở `navItems` thì MỌI nhân viên khoa nhìn thấy hàng
		chờ "Duyệt" của quản lý — mà phép đếm đó VẪN xanh, vì dòng khai báo
		không đổi.

		Đây là lần thứ tám dự án dính kiểu "test trông như phủ mà chẳng
		kiểm gì", và lần này nó gác một thứ thuộc về PHÂN QUYỀN. Bài này
		phải đỏ ngay khi bộ lọc bị gỡ."""
		dong = self._dong_loc_vai_tro()
		self.assertIn(
			".filter(", dong,
			"`navItems` không còn lọc gì — mọi mục nav hiện cho mọi vai trò.",
		)
		self.assertIn(
			"requireQuanLy", dong,
			"`navItems` lọc bằng một tiêu chí KHÁC `requireQuanLy` — cờ trên "
			"mảng NAV không còn tác dụng gì.",
		)
		# ĐÚNG khoá `me.la_quan_ly`, KHÔNG tự suy từ `vai_tro === 'Quản lý'`
		# — kế hoạch uỷ quyền tạm thời sẽ làm phép so chuỗi đó bỏ sót.
		self.assertIn(
			"la_quan_ly", dong,
			"`navItems` không đọc `store.me.la_quan_ly` — xem ghi chú Task 5 "
			"ngay trên mục 'Duyệt' trong App.vue.",
		)

	def test_so_muc_nav_dung_8_quan_ly_va_7_nhan_vien(self):
		"""Nghiệm thu của chủ đầu tư đếm bằng MẮT trên thanh nav. 11 cửa
		ban đầu → 9 sau Task 10 → 8 (quản lý) / 7 (nhân viên khoa) ở đây.

		Phép trừ `8 − 1` chỉ có nghĩa KHI bộ lọc vai trò còn sống — nên bài
		này gọi thẳng khẳng định đó trước, thay vì để nó nằm riêng một chỗ
		và hai bài cùng xanh vì hai lý do rời nhau."""
		self.test_nav_thuc_su_LOC_theo_vai_tro_chu_khong_chi_khai_bao_co()
		muc = self._muc_nav()
		chi_quan_ly = self._muc_nav_chi_quan_ly()
		self.assertEqual(len(muc), 8, f"Nav quản lý phải còn 8 mục, đang là {muc}")
		self.assertEqual(
			len(muc) - len(chi_quan_ly), 7,
			f"Nav nhân viên khoa phải còn 7 mục (bỏ {chi_quan_ly}), đang là {muc}",
		)

	def test_nav_khong_con_hai_cua_cho_cung_mot_thu(self):
		muc = self._muc_nav()
		self.assertIn("yeu-cau", muc)
		self.assertNotIn("orders", muc)
		self.assertNotIn("de-xuat", muc)
		# "Duyệt" KHÔNG gộp vào đây — nó là HÀNG CHỜ VIỆC của quản lý, khác
		# mục đích với "yêu cầu của tôi". Gộp hai thứ khác mục đích chỉ vì
		# chúng cùng kiểu dữ liệu là lặp lại đúng lỗi task này đang sửa.
		self.assertIn("duyet", muc)
