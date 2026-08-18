"""Cách ly giữa các khoa: khoa A không đọc được chứng từ của khoa B (bước 8).

Không được lộ CẢ SỰ TỒN TẠI của chứng từ — thông báo lỗi phải giống hệt
trường hợp chứng từ không có thật.

Dùng khách hàng ZZTEST8 RIÊNG của bộ test này (không phải "Bệnh viện Bạch
Mai" thật trên site — "VÒNG SỬA 3" của `test_portal_member.py` đã tài liệu
hoá đúng bẫy đó: một khách thật đã có Quản lý active thì tạo thêm một Quản
lý nữa sẽ ăn `_chan_hai_quan_ly`, và mọi test ngầm giả định "chưa ai active"
sẽ vỡ đúng ngày dữ liệu thật đổi).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.selling.doctype.sales_order.sales_order import (
	make_delivery_note,
	make_sales_invoice,
)

from miyano_portal import dat_hang, portal_context
from miyano_portal.api import portal as portal_api

KHACH = "ZZTEST8 Benh Vien"
MA_NGAN = "ZZT8BV"
ITEM = "MYN-GLOVE-M"
COMPANY = "Miyano Việt Nam"
KHO_MYN = "Kho Miyano - MYN"
COST_CENTER = "Main - MYN"


class _NenCachLy(FrappeTestCase):
	def setUp(self):
		self._don_sach()
		self.addCleanup(self._don_sach)
		frappe.set_user("Administrator")
		frappe.get_doc({
			"doctype": "Customer", "customer_name": KHACH,
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
			"custom_ma_ngan": MA_NGAN, "custom_cho_phep_mua_le": 1,
		}).insert(ignore_permissions=True)
		self.kp_a = self._kp("ZZTEST8 Khoa A", "ZZT8A")
		self.kp_b = self._kp("ZZTEST8 Khoa B", "ZZT8B")
		self.ql = self._tv("zztest8.ql@demo.miyano", "Quản lý", None)
		self.nv_a = self._tv("zztest8.a@demo.miyano", "Nhân viên khoa", self.kp_a.name)
		self.nv_b = self._tv("zztest8.b@demo.miyano", "Nhân viên khoa", self.kp_b.name)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _don_sach(self):
		"""Chạy cả đầu setUp (dọn rác từ lần chạy trước bị ngắt giữa chừng)
		lẫn cuối qua addCleanup. `frappe.delete_doc(..., force=True)` — KHÔNG
		`frappe.db.delete` — Sales Order/Delivery Note/Sales Invoice có bảng
		con, và một số đã submit; SQL thô để lại rác ở bảng con lẫn không huỷ
		được chứng từ đã submit (lỗi đã bắt hai lần trong đề án)."""
		frappe.set_user("Administrator")
		# Thứ tự XOÁ: con trước cha (Sales Invoice/Delivery Note tham chiếu
		# ngược `Sales Order` qua dòng hàng). `force=True` ở `delete_doc`
		# KHÔNG tự huỷ chứng từ đã submit (đã kiểm thực nghiệm) — phải tự
		# `.cancel()` trước, rồi mới xoá được.
		for dt in ("Sales Invoice", "Delivery Note", "Sales Order"):
			for row in frappe.get_all(dt, filters={"customer": KHACH}, fields=["name", "docstatus"]):
				if row.docstatus == 1:
					frappe.get_doc(dt, row.name).cancel()
				frappe.delete_doc(dt, row.name, force=True, ignore_permissions=True)
		frappe.db.delete("Notification Log", {"for_user": ["like", "zztest8.%"]})
		for ct in frappe.get_all("Contact", filters={"name": ["like", f"{KHACH}-zztest8.%"]}, pluck="name"):
			frappe.delete_doc("Contact", ct, force=True, ignore_permissions=True)
		frappe.db.delete("Portal Member", {"user": ["like", "zztest8.%"]})
		frappe.db.delete("Customer Department", {"customer": KHACH})
		frappe.db.delete("Customer", {"name": KHACH})

	def _kp(self, ten, ma):
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH,
			"ten_khoa_phong": ten, "ma_khoa": ma,
		}).insert(ignore_permissions=True)

	def _tv(self, email, vai_tro, khoa_phong):
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "ZZ",
				"user_type": "Website User", "send_welcome_email": 0,
			})
			# Role `Customer` — CHÍNH cổng gán role này qua `portal_provision`
			# (api/portal.py) khi cấp tài khoản thật; không có nó thì DocPerm
			# gốc trên Sales Order/... chặn ngay ở tầng vai trò, TRƯỚC KHI
			# `generic_has_permission`/`pham_vi_don` kịp chạy — một User dựng
			# tay không qua đường cấp tài khoản thật phải tự thêm role này.
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
			# Vòng sửa 1 (C1) — `User.on_update()` tự sinh một Contact "mồ
			# côi" (user=email, KHÔNG Dynamic Link tới Customer nào — xem
			# TestChieuNguocDanhTinh trong test_portal_member.py). Đường ĐẶT
			# HÀNG THẬT (`dat_hang.py`, cả hai nhánh `_xay_don_*`) tra Contact
			# THEO `frappe.session.user` rồi gán thẳng vào `so.contact_person`
			# — Contact mồ côi đó khiến ERPNext tự chặn lúc `insert()`
			# ("Contact Person does not belong to..."). `portal_provision`
			# (đường cấp tài khoản THẬT) luôn tạo kèm một Contact CÓ Dynamic
			# Link tới đúng khách hàng — mô phỏng lại đúng bước đó ở đây,
			# cùng khuôn `contact_name = f"{customer}-{email}"`.
			ten_contact = f"{KHACH}-{email}"
			if not frappe.db.exists("Contact", ten_contact):
				ct = frappe.get_doc({"doctype": "Contact", "first_name": KHACH, "user": email})
				ct.name = ten_contact
				ct.append("email_ids", {"email_id": email, "is_primary": 1})
				ct.append("links", {"link_doctype": "Customer", "link_name": KHACH})
				ct.insert(ignore_permissions=True)
		return frappe.get_doc({
			"doctype": "Portal Member", "user": email, "customer": KHACH,
			"vai_tro": vai_tro, "khoa_phong": khoa_phong,
		}).insert(ignore_permissions=True)

	def _don(self, khoa_phong=None) -> str:
		"""Đơn NHÁP qua đúng lõi `dat_hang.tao_sales_order` (mode mua lẻ —
		không cần Item Price, rate=0 đủ để lưu). `khoa_phong=None` mô phỏng
		đúng đơn CŨ trước khi đề án này tồn tại."""
		kq = dat_hang.tao_sales_order(
			KHACH, mode="ban_le",
			items=[{"item_code": ITEM, "qty": 2}],
			request_id=frappe.generate_hash(length=20), khoa_phong=khoa_phong,
		)
		return kq["sales_order"]

	def _don_submitted(self, khoa_phong) -> "frappe.Document":
		"""Đơn ĐÃ SUBMIT, dựng tay (không qua `dat_hang`) — cần cho
		`make_delivery_note`/`make_sales_invoice` (ERPNext chỉ map từ nguồn
		`docstatus == 1`). `custom_khoa_phong` ghi thẳng qua `db.set_value`
		(field `read_only=1`, `dat_hang.tao_sales_order` là đường ghi hợp lệ
		duy nhất cho đơn NHÁP — ở đây ta cố ý đi tắt để dựng nhanh một đơn đã
		submit cho hai test cách ly DN/SI bên dưới)."""
		so = frappe.new_doc("Sales Order")
		so.customer = KHACH
		so.company = COMPANY
		so.transaction_date = frappe.utils.today()
		so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 3)
		so.append("items", {
			"item_code": ITEM, "qty": 5, "rate": 10000,
			"warehouse": KHO_MYN, "delivery_date": so.delivery_date,
			"cost_center": COST_CENTER,
		})
		so.insert(ignore_permissions=True)
		frappe.db.set_value("Sales Order", so.name, "custom_khoa_phong", khoa_phong)
		so.reload()
		so.submit()
		return so


class TestTangHookPermissionsChanKhoa(_NenCachLy):
	"""C2 (review vòng sửa 1, CRITICAL) — cách ly theo khoa TRƯỚC bản vá này
	chỉ sống ở tầng `api/portal.py` (21 hàm whitelist). Đường đọc KHÔNG qua
	21 hàm đó — `frappe.get_list`/`frappe.client.get_list`/`get_value`/
	`frappe.desk.reportview`/REST/`/printview` — đều bottom-out ở
	`permission_query_conditions`/`has_permission` (`hooks.py`), nơi Task 8
	(bản đầu) không hề động tới: `sales_query`/`delivery_query`/
	`invoice_query`/`*_has_permission` (`permissions.py`) TRƯỚC bản vá này
	chỉ lọc theo `customer`. Vì role `Customer` có DocPerm read TRỰC TIẾP
	trên Sales Order/Delivery Note/Sales Invoice (patch
	`v1_0/grant_customer_role_read_perms`), một nhân viên khoa gọi thẳng
	`frappe.client.get_list`/`search_guard.client_get_list` sẽ thấy TOÀN BỘ
	đơn của MỌI khoa trong bệnh viện — kênh mà bộ test Task 8 (bản đầu)
	hoàn toàn không chạm tới."""

	def setUp(self):
		super().setUp()
		self.don_a = self._don(self.kp_a.name)

	def test_frappe_get_list_khong_lo_don_khoa_khac(self):
		frappe.set_user(self.nv_b.user)
		ten = frappe.get_list(
			"Sales Order", filters={"customer": KHACH}, pluck="name"
		)
		self.assertNotIn(self.don_a, ten)

	def test_frappe_get_list_chinh_khoa_van_thay(self):
		frappe.set_user(self.nv_a.user)
		ten = frappe.get_list(
			"Sales Order", filters={"customer": KHACH}, pluck="name"
		)
		self.assertIn(self.don_a, ten)

	def test_has_permission_tren_doc_chan_khoa_khac(self):
		frappe.set_user(self.nv_b.user)
		so = frappe.get_doc("Sales Order", self.don_a)
		self.assertFalse(so.has_permission("read"))

	def test_has_permission_tren_doc_cho_chinh_khoa(self):
		frappe.set_user(self.nv_a.user)
		so = frappe.get_doc("Sales Order", self.don_a)
		self.assertTrue(so.has_permission("read"))

	def test_client_get_list_qua_search_guard_khong_lo_don_khoa_khac(self):
		"""Đúng kênh reviewer nêu tên: `frappe.client.get_list` qua
		`search_guard.client_get_list` — Sales Order KHÔNG phải bảng con
		(`frappe.is_table` sai) nên guard NG-37b không chặn nó, rơi thẳng
		xuống `frappe.client.get_list` thật -> `permission_query_conditions`."""
		from miyano_portal import search_guard

		frappe.set_user(self.nv_b.user)
		rows = search_guard.client_get_list(
			"Sales Order", fields=["name"], filters={"customer": KHACH},
			limit_page_length=200,
		)
		self.assertNotIn(self.don_a, [r["name"] for r in rows])

	def test_client_get_value_qua_search_guard_khong_doc_duoc_don_khoa_khac(self):
		"""`frappe.client.get_value` kiểm quyền Ở TẦNG DOCTYPE
		(`frappe.has_permission(doctype)`, không kèm `doc` cụ thể — luôn
		True vì role Customer có DocPerm read) RỒI MỚI lọc qua
		`get_list`/`permission_query_conditions` — nên một đơn ngoài phạm vi
		không ném lỗi, nó biến mất khỏi kết quả (`{}`), đúng bản chất của
		một điều kiện SQL bổ sung (`sales_query`), không phải một cổng
		chặn cứng. An toàn (không rò dữ liệu) chỉ khác hình dạng lỗi so với
		`dam_bao_xem_duoc` (nơi CÓ ném `PermissionError` vì đó là kiểm một
		chứng từ, không phải lọc một danh sách)."""
		from miyano_portal import search_guard

		frappe.set_user(self.nv_b.user)
		self.assertFalse(
			search_guard.client_get_value(
				"Sales Order", "grand_total", filters={"name": self.don_a}
			)
		)

	def test_delivery_note_qua_frappe_get_list_chan_khoa_khac(self):
		so_a = self._don_submitted(self.kp_a.name)
		dn_a = make_delivery_note(so_a.name)
		dn_a.insert(ignore_permissions=True)
		frappe.set_user(self.nv_b.user)
		ten = frappe.get_list(
			"Delivery Note", filters={"customer": KHACH}, pluck="name"
		)
		self.assertNotIn(dn_a.name, ten)
		frappe.set_user(self.nv_a.user)
		ten = frappe.get_list(
			"Delivery Note", filters={"customer": KHACH}, pluck="name"
		)
		self.assertIn(dn_a.name, ten)

	def test_sales_invoice_qua_frappe_get_list_chan_khoa_khac(self):
		so_a = self._don_submitted(self.kp_a.name)
		si_a = make_sales_invoice(so_a.name)
		si_a.insert(ignore_permissions=True)
		frappe.set_user(self.nv_b.user)
		ten = frappe.get_list(
			"Sales Invoice", filters={"customer": KHACH}, pluck="name"
		)
		self.assertNotIn(si_a.name, ten)
		frappe.set_user(self.nv_a.user)
		ten = frappe.get_list(
			"Sales Invoice", filters={"customer": KHACH}, pluck="name"
		)
		self.assertIn(si_a.name, ten)

	def test_quan_ly_khong_bi_hook_gioi_han(self):
		frappe.set_user(self.ql.user)
		ten = frappe.get_list(
			"Sales Order", filters={"customer": KHACH}, pluck="name"
		)
		self.assertIn(self.don_a, ten)


class TestCachLyGiuaCacKhoa(_NenCachLy):
	def setUp(self):
		super().setUp()
		self.don_a = self._don(self.kp_a.name)

	def test_don_ghi_dung_khoa_phong(self):
		self.assertEqual(
			frappe.db.get_value("Sales Order", self.don_a, "custom_khoa_phong"),
			self.kp_a.name,
		)

	def test_khoa_khac_khong_doc_duoc_chi_tiet_don(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_order_track(self.don_a)

	def test_khoa_khac_khong_thay_don_trong_danh_sach(self):
		frappe.set_user(self.nv_b.user)
		ds = portal_api.portal_order_history()
		self.assertNotIn(self.don_a, [r["name"] for r in ds["rows"]])

	def test_chinh_khoa_do_van_doc_duoc(self):
		frappe.set_user(self.nv_a.user)
		self.assertEqual(portal_api.portal_order_track(self.don_a)["order"], self.don_a)

	def test_quan_ly_doc_duoc_don_cua_moi_khoa(self):
		frappe.set_user(self.ql.user)
		self.assertEqual(portal_api.portal_order_track(self.don_a)["order"], self.don_a)

	def test_don_khong_co_that_va_don_khoa_khac_bao_loi_GIONG_NHAU(self):
		"""Không được lộ cả sự tồn tại của chứng từ."""
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError) as khoa_khac:
			portal_api.portal_order_track(self.don_a)
		with self.assertRaises(frappe.PermissionError) as khong_co:
			portal_api.portal_order_track("SAL-ORD-KHONG-CO-THAT")
		self.assertEqual(str(khoa_khac.exception), str(khong_co.exception))


class TestDonCuKhongGanKhoa(_NenCachLy):
	"""Đơn CŨ (`custom_khoa_phong` trống) thuộc thời kỳ một-bệnh-viện-một-
	tài-khoản. Quản lý (`pham_vi_don()` trả `{}`) vẫn thấy hết — không đơn
	nào biến mất khỏi màn hình của họ. Nhân viên khoa thì KHÔNG thấy đơn cũ —
	đây là hành vi CÓ CHỦ ĐÍCH (không quy được đơn cũ về khoa nào), không
	phải một lỗi."""

	def setUp(self):
		super().setUp()
		self.don_cu = self._don(None)

	def test_quan_ly_van_thay_don_cu(self):
		frappe.set_user(self.ql.user)
		self.assertEqual(
			portal_api.portal_order_track(self.don_cu)["order"], self.don_cu
		)
		ds = portal_api.portal_order_history()
		self.assertIn(self.don_cu, [r["name"] for r in ds["rows"]])

	def test_nhan_vien_khoa_khong_thay_don_cu(self):
		frappe.set_user(self.nv_a.user)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_order_track(self.don_cu)
		ds = portal_api.portal_order_history()
		self.assertNotIn(self.don_cu, [r["name"] for r in ds["rows"]])


class TestNhanhDeliveryNoteCachLy(_NenCachLy):
	"""Nhánh `Delivery Note` của `dam_bao_xem_duoc` — cách ly RIÊNG, không
	gộp với nhánh Sales Order (constraint #4 của đề bài)."""

	def setUp(self):
		super().setUp()
		self.so_a = self._don_submitted(self.kp_a.name)
		self.dn_a = make_delivery_note(self.so_a.name)
		self.dn_a.insert(ignore_permissions=True)

	def test_khoa_khac_khong_doc_duoc_phieu_giao(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError):
			portal_context.dam_bao_xem_duoc("Delivery Note", self.dn_a.name)

	def test_chinh_khoa_do_doc_duoc_phieu_giao(self):
		frappe.set_user(self.nv_a.user)
		# Không ném gì cả — đây chính là phép kiểm.
		portal_context.dam_bao_xem_duoc("Delivery Note", self.dn_a.name)

	def test_phieu_giao_khong_co_that_va_khoa_khac_bao_loi_GIONG_NHAU(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError) as khoa_khac:
			portal_context.dam_bao_xem_duoc("Delivery Note", self.dn_a.name)
		with self.assertRaises(frappe.PermissionError) as khong_co:
			portal_context.dam_bao_xem_duoc("Delivery Note", "MAT-DN-KHONG-CO-THAT")
		self.assertEqual(str(khoa_khac.exception), str(khong_co.exception))


class TestNhanhSalesInvoiceCachLy(_NenCachLy):
	"""Nhánh `Sales Invoice` của `dam_bao_xem_duoc` — cách ly RIÊNG."""

	def setUp(self):
		super().setUp()
		self.so_a = self._don_submitted(self.kp_a.name)
		self.si_a = make_sales_invoice(self.so_a.name)
		self.si_a.insert(ignore_permissions=True)

	def test_khoa_khac_khong_doc_duoc_hoa_don(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError):
			portal_context.dam_bao_xem_duoc("Sales Invoice", self.si_a.name)

	def test_chinh_khoa_do_doc_duoc_hoa_don(self):
		frappe.set_user(self.nv_a.user)
		portal_context.dam_bao_xem_duoc("Sales Invoice", self.si_a.name)

	def test_hoa_don_khong_co_that_va_khoa_khac_bao_loi_GIONG_NHAU(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError) as khoa_khac:
			portal_context.dam_bao_xem_duoc("Sales Invoice", self.si_a.name)
		with self.assertRaises(frappe.PermissionError) as khong_co:
			portal_context.dam_bao_xem_duoc("Sales Invoice", "MAT-SI-KHONG-CO-THAT")
		self.assertEqual(str(khoa_khac.exception), str(khong_co.exception))


class TestDatHangQuaCongTuSuySeverKhoa(_NenCachLy):
	"""C1 (review vòng sửa 1, CRITICAL) — `portal_order_place` (đường ĐẶT HÀNG
	THẬT của khách trên cổng) phải tự suy `khoa_phong` từ `Portal Member` của
	PHIÊN đăng nhập, KHÔNG nhận từ client. Trước bản vá này, mọi đơn đặt qua
	cổng có `custom_khoa_phong = NULL` — nhân viên khoa đặt xong đơn thì
	CHÍNH HỌ không mở lại được đơn vừa đặt (class `TestDonCuKhongGanKhoa` ở
	trên hoá ra đang mô tả đúng trạng thái production thật, không phải một
	ca biên)."""

	def _dat_qua_cong(self, request_id=None):
		return portal_api.portal_order_place(
			mode="ban_le",
			items=[{"item_code": ITEM, "qty": 1}],
			request_id=request_id or frappe.generate_hash(length=20),
		)

	def test_nhan_vien_khoa_dat_don_thi_don_mang_dung_khoa_cua_ho(self):
		frappe.set_user(self.nv_a.user)
		kq = self._dat_qua_cong()
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_khoa_phong"),
			self.kp_a.name,
		)

	def test_nhan_vien_khoa_dat_don_thi_chinh_ho_mo_lai_duoc(self):
		"""Ca mà cả bộ test trước vòng sửa này đang THIẾU."""
		frappe.set_user(self.nv_a.user)
		kq = self._dat_qua_cong()
		self.assertEqual(
			portal_api.portal_order_track(kq["sales_order"])["order"], kq["sales_order"]
		)

	def test_khoa_khac_van_khong_thay_don_vua_dat(self):
		frappe.set_user(self.nv_a.user)
		kq = self._dat_qua_cong()
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_order_track(kq["sales_order"])

	def test_quan_ly_dat_don_thi_khoa_phong_de_trong(self):
		frappe.set_user(self.ql.user)
		kq = self._dat_qua_cong()
		self.assertFalse(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_khoa_phong")
		)

	def test_khoa_da_tat_khong_dong_dau_duoc(self):
		"""Minor kèm C1 (review vòng sửa 1) — `dat_hang.tao_sales_order`
		phải kiểm CẢ `Customer Department.active`, không chỉ `customer`."""
		frappe.db.set_value("Customer Department", self.kp_a.name, "active", 0)
		frappe.set_user(self.nv_a.user)
		with self.assertRaises(frappe.PermissionError):
			self._dat_qua_cong()


class TestCacEndpointDonKhacApDungPhamVi(_NenCachLy):
	"""Sáu endpoint còn lại đọc/sửa MỘT `Sales Order` cụ thể — tất cả gọi
	`dam_bao_xem_duoc("Sales Order", order)` NGAY DÒNG ĐẦU (cùng cơ chế đã
	unit-test kỹ ở `TestCachLyGiuaCacKhoa`), nên một test GỘP xác nhận từng
	endpoint THẬT SỰ có gọi nó là đủ — không cần lặp lại bộ 6 test cách ly
	đầy đủ cho mỗi cái, vì phần lõi cách ly (nhánh Sales Order của
	`dam_bao_xem_duoc`) đã bị cô lập và test riêng ở trên."""

	def setUp(self):
		super().setUp()
		self.don_a = self._don(self.kp_a.name)

	def test_moi_endpoint_deu_chan_khoa_khac(self):
		frappe.set_user(self.nv_b.user)
		goi = {
			"portal_reorder": lambda: portal_api.portal_reorder(self.don_a),
			"portal_order_accept": lambda: portal_api.portal_order_accept(self.don_a, "dong_y"),
			"portal_order_sua_so_luong": lambda: portal_api.portal_order_sua_so_luong(
				self.don_a, {"items": []}
			),
			"portal_order_huy": lambda: portal_api.portal_order_huy(
				self.don_a, "Đặt nhầm, không cần nữa"
			),
			"portal_request_cancel": lambda: portal_api.portal_request_cancel(self.don_a, "x"),
			"portal_bao_gia_pdf": lambda: portal_api.portal_bao_gia_pdf(self.don_a),
		}
		for ten, fn in goi.items():
			with self.assertRaises(frappe.PermissionError, msg=ten):
				fn()

	def test_document_download_chan_khoa_khac(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_document_download("Sales Order", self.don_a)

	def test_document_download_chinh_khoa_qua_duoc_vong_kiem_khoa(self):
		"""Vòng sửa 1 (review độc lập, Minor) — bản trước dùng `except
		Exception: pass` sau `except PermissionError`, nuốt MỌI lỗi khác nên
		test gần như không kiểm gì (kể cả một `PermissionError` bị một tầng
		khác bọc lại vẫn lọt qua). Mock đúng bước RENDER PDF (phụ thuộc
		wkhtmltopdf trên máy chạy test, không phải điều đang kiểm) để hàm
		chạy TRỌN VẸN không cần bọc except nào — nếu vòng kiểm khoa còn chặn
		nhầm, `portal_document_download` sẽ tự ném thật, `assertIsNotNone`
		phía dưới thất bại rõ ràng thay vì bị nuốt."""
		frappe.set_user(self.nv_a.user)
		from unittest.mock import patch

		with patch("frappe.utils.pdf.get_pdf", return_value=b"%PDF-fake"):
			portal_api.portal_document_download("Sales Order", self.don_a)
		self.assertEqual(frappe.local.response.filecontent, b"%PDF-fake")


class TestKiemHangApDungPhamVi(_NenCachLy):
	"""`portal_kiem_hang_get/luu/gui` đi qua `_dn_kiem_hang_cua_khach` —
	`dam_bao_xem_duoc("Delivery Note", ...)` đứng NGAY DÒNG ĐẦU, TRƯỚC cả
	phép kiểm `docstatus`. Phiếu giao NHÁP (chưa submit) đủ để tách hai vòng
	kiểm: khoa khác ăn PermissionError NGAY; đúng khoa đi tiếp và ăn lỗi
	`docstatus` (ValidationError) — chứng minh nó đã QUA được vòng khoa."""

	def setUp(self):
		super().setUp()
		self.so_a = self._don_submitted(self.kp_a.name)
		self.dn_a = make_delivery_note(self.so_a.name)
		self.dn_a.insert(ignore_permissions=True)  # cố ý KHÔNG submit

	def test_khoa_khac_bi_chan_truoc_ca_kiem_docstatus(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_kiem_hang_get(self.dn_a.name)

	def test_chinh_khoa_qua_duoc_vong_khoa_roi_moi_an_loi_docstatus(self):
		frappe.set_user(self.nv_a.user)
		with self.assertRaises(frappe.ValidationError) as cm:
			portal_api.portal_kiem_hang_get(self.dn_a.name)
		self.assertIn("chưa được ghi sổ", str(cm.exception))


class TestEinvoiceApDungPhamVi(_NenCachLy):
	"""`portal_einvoice_nhap` (qua `_dn_cua_khach`) và `portal_einvoice_ho_tro`
	(qua `_ho_so_cua_hoa_don`) — cùng cơ chế `dam_bao_xem_duoc`, khác helper
	sở hữu bọc ngoài."""

	def setUp(self):
		super().setUp()
		self.so_a = self._don_submitted(self.kp_a.name)
		self.dn_a = make_delivery_note(self.so_a.name)
		self.dn_a.insert(ignore_permissions=True)
		self.si_a = make_sales_invoice(self.so_a.name)
		self.si_a.insert(ignore_permissions=True)

	def test_einvoice_nhap_chan_khoa_khac(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_einvoice_nhap(self.dn_a.name)

	def test_einvoice_nhap_chinh_khoa_qua_duoc(self):
		frappe.set_user(self.nv_a.user)
		# Không có bản ghi HĐĐT nào — trả `None`, không ném gì cả.
		self.assertIsNone(portal_api.portal_einvoice_nhap(self.dn_a.name))

	def test_einvoice_ho_tro_chan_khoa_khac(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_einvoice_ho_tro(self.si_a.name)


class TestPortalDeliveriesApDungPhamVi(_NenCachLy):
	def setUp(self):
		super().setUp()
		self.so_a = self._don_submitted(self.kp_a.name)
		self.dn_a = make_delivery_note(self.so_a.name)
		self.dn_a.insert(ignore_permissions=True)

	def test_khoa_khac_khong_thay_phieu_giao_trong_danh_sach(self):
		frappe.set_user(self.nv_b.user)
		ds = portal_api.portal_deliveries(limit=200)
		self.assertNotIn(self.dn_a.name, [r["name"] for r in ds])

	def test_chinh_khoa_thay_phieu_giao_trong_danh_sach(self):
		frappe.set_user(self.nv_a.user)
		ds = portal_api.portal_deliveries(limit=200)
		self.assertIn(self.dn_a.name, [r["name"] for r in ds])

	def test_quan_ly_thay_ca_hai_khoa(self):
		frappe.set_user(self.ql.user)
		ds = portal_api.portal_deliveries(limit=200)
		self.assertIn(self.dn_a.name, [r["name"] for r in ds])

	def test_khong_nhan_ban_qua_phep_noi_bang_dong(self):
		"""Đơn nhiều dòng cùng trỏ về MỘT phiếu giao không được nhân bản
		chính phiếu giao đó trên danh sách (thiếu `distinct` là bẫy đã cảnh
		báo trong code)."""
		frappe.set_user(self.nv_a.user)
		ds = portal_api.portal_deliveries(limit=200)
		ten = [r["name"] for r in ds]
		self.assertEqual(ten.count(self.dn_a.name), 1)


class TestPortalInvoicesApDungPhamVi(_NenCachLy):
	def setUp(self):
		super().setUp()
		self.so_a = self._don_submitted(self.kp_a.name)
		self.si_a = make_sales_invoice(self.so_a.name)
		self.si_a.insert(ignore_permissions=True)

	def test_khoa_khac_khong_thay_hoa_don_va_khong_tinh_vao_tong(self):
		frappe.set_user(self.nv_b.user)
		kq = portal_api.portal_invoices(limit=200)
		self.assertNotIn(self.si_a.name, [r["name"] for r in kq["rows"]])

	def test_chinh_khoa_thay_hoa_don(self):
		frappe.set_user(self.nv_a.user)
		kq = portal_api.portal_invoices(limit=200)
		self.assertIn(self.si_a.name, [r["name"] for r in kq["rows"]])

	def test_khong_nhan_ban_hoa_don_qua_phep_noi_bang_dong(self):
		frappe.set_user(self.nv_a.user)
		kq = portal_api.portal_invoices(limit=200)
		ten = [r["name"] for r in kq["rows"]]
		self.assertEqual(ten.count(self.si_a.name), 1)


class TestPortalDashboardKpiApDungPhamVi(_NenCachLy):
	"""`hoa_don_chua_thanh_toan` — con số TỔNG HỢP, không phải một danh sách;
	đúng loại "hồi quy im lặng" hàm này CỐ Ý ngừa (lọc `rows` mà quên lọc
	tổng số thì con số KPI vẫn rò công nợ toàn bệnh viện ra màn hình đầu tiên
	nhân viên khoa nhìn thấy mỗi lần đăng nhập)."""

	def setUp(self):
		super().setUp()
		self.so_a = self._don_submitted(self.kp_a.name)
		self.si_a = make_sales_invoice(self.so_a.name)
		self.si_a.insert(ignore_permissions=True)
		self.si_a.submit()

	def test_hoa_don_chua_thanh_toan_khong_tinh_khoa_khac(self):
		self.assertGreater(
			frappe.db.get_value("Sales Invoice", self.si_a.name, "outstanding_amount") or 0, 0,
			"Fixture lỗi: hoá đơn test phải còn nợ để phép kiểm này có nghĩa.",
		)
		frappe.set_user(self.nv_b.user)
		kq = portal_api.portal_dashboard_kpi()
		self.assertEqual(kq["hoa_don_chua_thanh_toan"], 0)

	def test_hoa_don_chua_thanh_toan_tinh_dung_khoa(self):
		frappe.set_user(self.nv_a.user)
		kq = portal_api.portal_dashboard_kpi()
		self.assertGreaterEqual(kq["hoa_don_chua_thanh_toan"], 1)


class TestI2FailClosedThongBaoChoNhanVienChuaGanKhoa(_NenCachLy):
	"""I2 (review vòng sửa 1) — `pham_vi_don()` CỐ Ý fail-closed
	(`portal_context.py:80-81`) cho một Nhân viên khoa `active=1` mà
	`khoa_phong` rỗng (đi vòng qua `validate()` bằng `db.set_value` — giới
	hạn đã biết, xem docstring `pham_vi_don`). Bản `_pham_vi_phien_hien_
	tai()` trước vòng sửa này bắt `PermissionError` đó rồi trả `{}` =
	KHÔNG GIỚI HẠN — LẬT NGƯỢC fail-closed thành fail-open đúng ở ca
	`pham_vi_don()` tồn tại để chặn. Tài khoản lỗi cấu hình này phải KHÔNG
	thấy thông báo nào trỏ tới Sales Order/Delivery Note/Sales Invoice."""

	def setUp(self):
		super().setUp()
		self.don_a = self._don(self.kp_a.name)
		email = "zztest8.chuagankhoa@demo.miyano"
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "ZZ",
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		# `active=0` để qua được `_chan_vai_tro_va_khoa_phong` lúc insert, rồi
		# bật lại bằng `db.set_value` — đúng con đường "giới hạn đã biết" mà
		# `pham_vi_don()` tự nhận là phải tự vệ, không tin việc ghi luôn đúng.
		tv = frappe.get_doc({
			"doctype": "Portal Member", "user": email, "customer": KHACH,
			"vai_tro": "Nhân viên khoa", "khoa_phong": None, "active": 0,
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal Member", tv.name, "active", 1)
		self.user_chua_gan_khoa = email
		self.log = frappe.get_doc({
			"doctype": "Notification Log",
			"subject": f"Portal - Đơn mới: {self.don_a}",
			"for_user": email,
			"type": "Alert",
			"document_type": "Sales Order",
			"document_name": self.don_a,
			"email_content": "Đơn hàng mới cần xác nhận.",
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.delete("Notification Log", {"for_user": self.user_chua_gan_khoa})
		super().tearDown()

	def test_khong_thay_thong_bao_don_hang_khi_chua_gan_khoa(self):
		frappe.set_user(self.user_chua_gan_khoa)
		kq = portal_api.portal_thong_bao_list(limit=100)
		self.assertNotIn(self.log.name, [i["name"] for i in kq["items"]])

	def test_bam_thong_bao_don_hang_khi_chua_gan_khoa_bi_tu_choi(self):
		frappe.set_user(self.user_chua_gan_khoa)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_thong_bao_doc(self.log.name)


class TestThongBaoApDungPhamVi(_NenCachLy):
	"""`portal_thong_bao_list`/`portal_thong_bao_doc` — Notification Log
	không mang khoa phòng riêng, phải quy về đơn cha qua `document_type`/
	`document_name` (cùng nguyên tắc dẫn xuất). `for_user` đã lọc đúng người
	NHẬN, nhưng KHÔNG phải bằng chứng người đó có quyền đọc chứng từ đích —
	dựng thẳng một `Notification Log` trỏ tới đơn khoa A rồi gán `for_user`
	cho nhân viên khoa B để mô phỏng đúng lỗ mà `_thong_bao_trong_pham_vi`
	phải chặn (chính lỗ mà `_portal_users_cua_khach` — chưa lọc khoa lúc
	TẠO — có thể sinh ra thật ngoài đời, xem docstring hàm đó)."""

	def setUp(self):
		super().setUp()
		self.don_a = self._don(self.kp_a.name)
		self.log = frappe.get_doc({
			"doctype": "Notification Log",
			"subject": f"Portal - Đơn mới: {self.don_a}",
			"for_user": self.nv_b.user,
			"type": "Alert",
			"document_type": "Sales Order",
			"document_name": self.don_a,
			"email_content": "Đơn hàng mới cần xác nhận.",
		}).insert(ignore_permissions=True)

	def test_danh_sach_an_dong_thong_bao_ngoai_pham_vi(self):
		frappe.set_user(self.nv_b.user)
		kq = portal_api.portal_thong_bao_list(limit=100)
		self.assertNotIn(self.log.name, [i["name"] for i in kq["items"]])

	def test_bam_thong_bao_ngoai_pham_vi_bao_loi_GIONG_khong_co_that(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError) as ngoai_pham_vi:
			portal_api.portal_thong_bao_doc(self.log.name)
		with self.assertRaises(frappe.PermissionError) as khong_co:
			portal_api.portal_thong_bao_doc("KHONG-CO-THAT-TB")
		self.assertEqual(str(ngoai_pham_vi.exception), str(khong_co.exception))
