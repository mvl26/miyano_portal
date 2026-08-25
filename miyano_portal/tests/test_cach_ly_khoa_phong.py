"""Cách ly giữa các khoa: khoa A không đọc được chứng từ của khoa B (bước 8).

Không được lộ CẢ SỰ TỒN TẠI của chứng từ — thông báo lỗi phải giống hệt
trường hợp chứng từ không có thật.

Dùng khách hàng ZZTEST8 RIÊNG của bộ test này (không phải "Bệnh viện Bạch
Mai" thật trên site — "VÒNG SỬA 3" của `test_portal_member.py` đã tài liệu
hoá đúng bẫy đó: một khách thật đã có Quản lý active thì tạo thêm một Quản
lý nữa sẽ ăn `_chan_hai_quan_ly`, và mọi test ngầm giả định "chưa ai active"
sẽ vỡ đúng ngày dữ liệu thật đổi).
"""

import base64

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.selling.doctype.sales_order.sales_order import (
	make_delivery_note,
	make_sales_invoice,
)

from miyano_portal import dat_hang, permissions, portal_context
from miyano_portal.api import kho as kho_api
from miyano_portal.api import portal as portal_api
from miyano_portal.kho import khoa_phong as khoa_phong_mod

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
	"""C1 (review vòng sửa 1, CRITICAL), VIẾT LẠI cho Task 7 (§5.5, phê chuẩn
	điều phối viên 19/08/2026 — "Blocker 1" trong `task-7-report.md`).

	Bản GỐC của lớp này (bước 1-4, TRƯỚC khi có luồng duyệt đề xuất) mã hoá
	đúng MỘT bất biến: "`portal_order_place` tự suy `khoa_phong` từ `Portal
	Member` của phiên, KHÔNG nhận từ client" — và cho NHÂN VIÊN KHOA đặt
	hàng TRỰC TIẾP qua endpoint này. §5.5 đổi có chủ đích: từ Task 7, nhân
	viên khoa KHÔNG còn đặt hàng trực tiếp qua `portal_order_place` nữa (họ
	đi qua `de_xuat_gui_duyet` → quản lý duyệt) — gọi thẳng bị TỪ CHỐI kèm
	thông báo rõ, không phải lỗi khó hiểu. Nếu không chặn, nhân viên gọi
	thẳng API sẽ vượt mặt toàn bộ cổng duyệt vừa dựng, biến tính năng đó
	thành trang trí.

	Ý ĐỊNH GỐC ("khoa suy từ server, không nhận từ client") KHÔNG mất đi —
	nó chuyển sang kiểm THẲNG `portal_context.khoa_phong_cho_don()` (xem
	`test_de_xuat_duyet.py::TestQuanLyDatTrucTiepTuDuyet.
	test_nhan_vien_khoa_gui_khoa_khac_van_bi_ep_ve_khoa_minh`), vì hàm ĐÓ —
	không còn `portal_order_place` cho nhân viên khoa nữa — mới là chỗ bất
	biến đó còn đo được.

	Quản lý (`self.ql`) KHÔNG bị chặn — họ vẫn đặt trực tiếp mỗi ngày (sáu
	tài khoản thật đang chạy đều là quản lý); `test_quan_ly_dat_don_thi_
	khoa_phong_de_trong` giữ NGUYÊN không đổi."""

	def _dat_qua_cong(self, request_id=None, khoa_phong=None):
		return portal_api.portal_order_place(
			mode="ban_le",
			items=[{"item_code": ITEM, "qty": 1}],
			request_id=request_id or frappe.generate_hash(length=20),
			khoa_phong=khoa_phong,
		)

	def test_nhan_vien_khoa_goi_thang_bi_tu_choi_ro_rang(self):
		"""Task 7, §5.5 câu cuối — thay cho
		`test_nhan_vien_khoa_dat_don_thi_don_mang_dung_khoa_cua_ho` (bản gốc
		kỳ vọng THÀNH CÔNG, nay ĐỐI LẬP với hành vi mới)."""
		frappe.set_user(self.nv_a.user)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._dat_qua_cong()
		self.assertIn("gửi duyệt", str(ctx.exception))

	def test_nhan_vien_khoa_bi_chan_khong_tao_don_rac(self):
		"""Task 7 — thay cho `test_nhan_vien_khoa_dat_don_thi_chinh_ho_mo_
		lai_duoc` (bản gốc không còn nghĩa: không có đơn nào được tạo để mà
		"mở lại"). Phép chặn phải xảy ra TRƯỚC khi chạm `dat_hang.
		tao_sales_order`, không phải chặn sau khi đơn đã lỡ tạo."""
		frappe.set_user(self.nv_a.user)
		truoc = frappe.db.count("Sales Order", {"customer": KHACH})
		with self.assertRaises(frappe.ValidationError):
			self._dat_qua_cong()
		sau = frappe.db.count("Sales Order", {"customer": KHACH})
		self.assertEqual(sau, truoc)

	def test_khoa_khac_van_khong_thay_don_vua_dat(self):
		"""Task 7 — ý định cách ly GIỮ NGUYÊN, nhưng đơn của khoa A giờ do
		QUẢN LÝ đặt hộ qua `khoa_phong` mới ở giỏ hàng (§5.5), vì nhân viên
		khoa A không còn tự đặt trực tiếp được (xem test phía trên)."""
		frappe.set_user(self.ql.user)
		kq = self._dat_qua_cong(khoa_phong=self.kp_a.name)
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_order_track(kq["sales_order"])

	def test_quan_ly_dat_don_thi_khoa_phong_de_trong(self):
		"""Không đổi — quản lý không truyền `khoa_phong` vẫn ra đơn Toàn
		viện, y hệt trước Task 7."""
		frappe.set_user(self.ql.user)
		kq = self._dat_qua_cong()
		self.assertFalse(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_khoa_phong")
		)

	def test_khoa_da_tat_khong_dong_dau_duoc(self):
		"""Task 7 — thay cho bản gốc (nhân viên khoa gọi `portal_order_place`
		với khoa đã tắt): giờ nhân viên khoa bị chặn TRƯỚC khi bất kỳ kiểm
		tra active nào chạy tới, kể cả khi khoa của họ đã tắt — thông báo
		VẪN phải là lời mời gửi duyệt, không lộ chi tiết "khoa đã tắt" mà
		chính nhân viên khoa không có quyền tự sửa.

		SỬA (review I1) — bản trước của docstring này TỰ NHẬN phép kiểm
		active gốc của `dat_hang.tao_sales_order` "vẫn đứng… qua
		`khoa_phong_cho_don()`" và trỏ sang
		`test_quan_ly_khong_chon_duoc_khoa_benh_vien_khac_qua_khoa_phong_
		cho_don` — SAI: test đó chỉ đổi BỆNH VIỆN, không đổi `active`, và
		`khoa_phong_cho_don()` tự kiểm `active` bằng CHÍNH SQL của nó
		(`portal_context.py`), không đi qua `dat_hang` chút nào. Test này
		giờ CHỈ còn khẳng định "nhân viên khoa bị chặn hẳn, kể cả khi khoa
		đã tắt" — vế "`dat_hang.tao_sales_order` tự nó có canh `active`
		không" chuyển sang `test_dat_hang_tu_choi_khoa_da_tat` ngay dưới,
		gọi THẲNG `dat_hang`, không qua `portal_order_place`."""
		frappe.db.set_value("Customer Department", self.kp_a.name, "active", 0)
		frappe.set_user(self.nv_a.user)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._dat_qua_cong()
		self.assertIn("gửi duyệt", str(ctx.exception))

	def test_dat_hang_tu_choi_khoa_da_tat(self):
		"""Review I1 — `dat_hang.tao_sales_order` PHẢI tự canh `Customer
		Department.active` ở TẦNG CỦA NÓ, độc lập với `khoa_phong_cho_don()`
		(tầng khoa ↔ NGƯỜI GỌI ở `portal_context.py`): hai tầng kiểm hai
		việc khác nhau (khoa ↔ khách hàng ở đây, khoa ↔ người gọi ở kia),
		và Task 7 đã bỏ mất đường TEST duy nhất từng chạm nhánh này khi viết
		lại `test_khoa_da_tat_khong_dong_dau_duoc` để không còn gọi tới
		`dat_hang` (nhân viên khoa bị chặn TRƯỚC đó rồi). Gọi THẲNG
		`dat_hang.tao_sales_order` qua `_don()` — không qua
		`portal_order_place`, vì nhân viên khoa không còn đặt trực tiếp
		được nữa (xem các test trên); `_don()` không cần phiên đăng nhập."""
		frappe.db.set_value("Customer Department", self.kp_a.name, "active", 0)
		with self.assertRaises(frappe.PermissionError) as ctx:
			self._don(self.kp_a.name)
		self.assertIn("không thuộc đơn vị", str(ctx.exception))


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


class TestV1NotificationLogQuaHookKhongDuocRoRi(_NenCachLy):
	"""V1 (review tổng toàn nhánh — CRITICAL). `TestThongBaoApDungPhamVi`
	ngay TRÊN chỉ khoá đúng MỘT đường đọc: `portal_thong_bao_list`/
	`portal_thong_bao_doc` (`_thong_bao_trong_pham_vi`, `api/portal.py`).
	`Notification Log` (core) cấp `read/report/export` cho role `All`
	(JSON gốc), mà `ALL_USER_ROLE` được framework gán cho MỌI user kể cả
	Website User (`frappe/permissions.py`); `get_permission_query_
	conditions` của core chỉ lọc `for_user = session.user` — KHÔNG có vế
	khoa; và doctype này KHÔNG phải bảng con (`frappe.is_table`) nên
	`rest_guard`/`search_guard` không chặn. Nghĩa là `frappe.get_list`/
	`frappe.client.get_value` đi THẲNG, bỏ qua toàn bộ tầng endpoint ở
	`api/portal.py`.

	`bao_hen_giao_lai`/`bao_kiem_hang_ket_qua` (`portal_thong_bao_khach.py`)
	fan-out MỘT bản ghi `Notification Log` cho MỖI thành viên active của
	KHÁCH HÀNG (chưa lọc theo khoa lúc TẠO — docstring `_portal_users_cua_
	khach` tự nhận). `for_user` vì thế đúng ngay từ đầu cho nhân viên khoa
	B dù chứng từ thuộc khoa A — điều kiện `for_user` của core không chặn
	được ca này.

	Test dưới đây gọi THẲNG hai đường đọc thô đó — KHÔNG qua `portal_api.*`
	— để chứng minh lưới an toàn phải nằm ở tầng hook
	(`permission_query_conditions`), đúng như V1 yêu cầu."""

	def setUp(self):
		super().setUp()
		self.don_a = self._don(self.kp_a.name)
		self.don_b = self._don(self.kp_b.name)
		self.log_a = frappe.get_doc({
			"doctype": "Notification Log",
			"subject": f"Portal - Hẹn lịch giao: {self.don_a} — Giao lại 20/08/2026",
			"for_user": self.nv_b.user,
			"type": "Alert",
			"document_type": "Sales Order",
			"document_name": self.don_a,
			"email_content": "Lý do: hàng chưa về kho Miyano.",
		}).insert(ignore_permissions=True)
		self.log_b = frappe.get_doc({
			"doctype": "Notification Log",
			"subject": f"Portal - Hẹn lịch giao: {self.don_b} — Giao lại 20/08/2026",
			"for_user": self.nv_b.user,
			"type": "Alert",
			"document_type": "Sales Order",
			"document_name": self.don_b,
			"email_content": "Lý do: hàng chưa về kho Miyano.",
		}).insert(ignore_permissions=True)
		# Coordinator (2026-08-18, sau vòng vá đầu) — điều kiện SQL cho
		# Delivery Note/Sales Invoice trong notification_khoa_query() chưa
		# có luồng THẬT nào sinh ra hôm nay (bao_kiem_hang_ket_qua dùng
		# document_type="Portal Delivery Inspection", bao_da_nhap_hang dùng
		# "Customer Stock Receipt") — nhánh đó vì thế ĐANG ẨN, chưa có test
		# xác nhận LỌC đúng (trước đó chỉ có bằng chứng nó PARSE đúng, gián
		# tiếp qua việc không test nào khác trong suite ăn OperationalError).
		# KHÔNG dựng cả một luồng nghiệp vụ giả chỉ để test — tạo THẲNG một
		# Notification Log document_type="Delivery Note" trỏ tới phiếu giao
		# của khoa A, đúng như coordinator chỉ định, để kiểm đúng vế SQL đó.
		self.so_dn_a = self._don_submitted(self.kp_a.name)
		self.dn_a = make_delivery_note(self.so_dn_a.name)
		self.dn_a.insert(ignore_permissions=True)
		self.log_dn_a = frappe.get_doc({
			"doctype": "Notification Log",
			"subject": f"Portal - Đã giao hàng: {self.dn_a.name}",
			"for_user": self.nv_b.user,
			"type": "Alert",
			"document_type": "Delivery Note",
			"document_name": self.dn_a.name,
			"email_content": "Phiếu giao đã được lập.",
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.delete(
			"Notification Log",
			{"name": ["in", [self.log_a.name, self.log_b.name, self.log_dn_a.name]]},
		)
		super().tearDown()

	def test_frappe_get_list_khong_tra_thong_bao_khoa_khac(self):
		frappe.set_user(self.nv_b.user)
		ten = frappe.get_list(
			"Notification Log",
			filters={"for_user": self.nv_b.user},
			fields=["name", "subject", "document_name"],
			pluck="name",
		)
		self.assertNotIn(
			self.log_a.name, ten,
			"frappe.get_list phải bị vế khoa chặn — hook permission_query_"
			"conditions cho Notification Log chưa thu hẹp theo khoa.",
		)
		self.assertIn(
			self.log_b.name, ten,
			"Thông báo của ĐÚNG khoa mình phải vẫn thấy — không được chặn quá tay.",
		)

	def test_frappe_client_get_value_khong_tra_thong_bao_khoa_khac(self):
		from frappe.client import get_value as client_get_value

		frappe.set_user(self.nv_b.user)
		kq_khac = client_get_value(
			"Notification Log", "subject", filters={"name": self.log_a.name}
		)
		self.assertEqual(
			kq_khac, {},
			"frappe.client.get_value phải trả rỗng (không lộ subject/tên đơn "
			"của khoa khác) — đúng ngữ nghĩa 'không tìm thấy' dam_bao_xem_"
			"duoc dùng khắp đề án.",
		)
		kq_minh = client_get_value(
			"Notification Log", "subject", filters={"name": self.log_b.name}
		)
		self.assertEqual(kq_minh.get("subject"), self.log_b.subject)

	def test_frappe_get_list_khong_tra_thong_bao_delivery_note_khoa_khac(self):
		"""Coordinator (2026-08-18) — kiểm ĐÚNG vế `Delivery Note` của
		`notification_khoa_query` (quy về đơn cha qua `_dieu_kien_khoa_qua_
		don_cha`), không chỉ vế `Sales Order` (hai test ngay trên). `dn_a`
		(setUp) là phiếu giao của khoa A; `log_dn_a` gán `for_user=nv_b.user`
		— đúng hình fan-out hiện tại (gửi cho mọi thành viên active của
		khách hàng, chưa lọc khoa lúc tạo)."""
		frappe.set_user(self.nv_b.user)
		ten = frappe.get_list(
			"Notification Log",
			filters={"for_user": self.nv_b.user},
			fields=["name", "subject", "document_name"],
			pluck="name",
		)
		self.assertNotIn(
			self.log_dn_a.name, ten,
			"frappe.get_list phải bị vế khoa chặn cho document_type="
			"'Delivery Note' — nhánh Delivery Note của notification_khoa_"
			"query chưa lọc đúng.",
		)


class TestC3ThieuCotKhoaFailClosed(_NenCachLy):
	"""C3 (review vòng sửa 2, CRITICAL) — vế khoa thêm vào `permissions.py`
	(Vòng sửa 1, C2) sinh SQL tham chiếu `` `tabSales Order`.
	`custom_khoa_phong` `` trên MỌI truy vấn Sales Order/Delivery Note/Sales
	Invoice của MỌI Website User — không còn giới hạn ở 21 hàm
	`api/portal.py` nữa. Nếu patch `v1_23/them_khoa_phong_vao_don_hang`
	CHƯA THỰC SỰ chạy trên site đích (bẫy đã ghi nhận: `install_app` có thể
	"hoàn thành giả" patch — ghi Patch Log mà không chạy DDL thật), mọi
	truy vấn đó chết bằng MariaDB lỗi 1054 (unknown column) — cổng khách
	SẬP HOÀN TOÀN, không phải suy giảm êm.

	`portal_context._cot_khoa_phong_ton_tai()` (chuyển từ `permissions.py`
	sang `portal_context.py` ở Vòng sửa 3, V2 — để cả tầng hook LẪN
	`dam_bao_xem_duoc`/`_ten_don_trong_pham_vi` ở `api/portal.py` dùng
	CHUNG một nguồn kiểm tra) là lưới an toàn: thiếu cột thì fail-closed
	(`"1=0"` ở tầng hook, `PermissionError(LOI_KHONG_THAY)` ở tầng
	endpoint), KHÔNG ném lỗi CSDL thô ra khách."""

	def setUp(self):
		super().setUp()
		self.don_a = self._don(self.kp_a.name)
		# Chốt cache cấp tiến trình — reset TRƯỚC mỗi test để không ăn theo
		# kết quả (True, cột THẬT tồn tại trên site test) của lần gọi trước.
		portal_context._cot_khoa_ton_tai = None
		self.addCleanup(self._reset_cache)
		# V1 (review vòng sửa 3) — `frappe.log_error()` (gọi khi giả lập
		# thiếu cột) ghi vào `tabError Log`, MyISAM (phi giao dịch) nên SỐNG
		# SÓT qua rollback cuối class — đúng bẫy repo này đã tự học và tự vá
		# ở năm chỗ khác (`test_e3_doi_soat.py`, `test_kho_delivery_hook.py`,
		# `test_thong_bao_khach.py`, `test_khoa_phong_theo_khach.py`,
		# `test_e9_kiem_hang.py`). Không dọn thì mỗi lần chạy suite bồi thêm
		# rác vĩnh viễn vào site dùng chung.
		self.addCleanup(
			frappe.db.delete,
			"Error Log",
			# `frappe.log_error(title=...)` lưu vào field `method` (Data),
			# KHÔNG có field `title` thật trên doctype Error Log của bản
			# Frappe này (đã kiểm JSON: chỉ có `method`/`error`/`reference_*`)
			# — xác nhận bằng thực nghiệm, `frappe.db.delete(..., {"title":
			# ...})` ném OperationalError "Unknown column 'title'".
			{"method": "Thiếu cột Sales Order.custom_khoa_phong"},
		)

	def _reset_cache(self):
		portal_context._cot_khoa_ton_tai = None

	def test_dieu_kien_sql_tra_1_bang_0_khi_thieu_cot(self):
		from unittest.mock import patch as mock_patch

		frappe.set_user(self.nv_a.user)
		with mock_patch("frappe.db.has_column", return_value=False):
			dk = permissions.sales_query()
		self.assertIn("1=0", dk)

	def test_frappe_get_list_khong_nem_loi_csdl_khi_thieu_cot(self):
		"""Phép kiểm THẬT nhất: gọi `frappe.get_list` (đường mà lỗi 1054 sẽ
		lộ ra nếu chốt không hoạt động) — chỉ được trả rỗng, KHÔNG được ném
		`OperationalError`."""
		from unittest.mock import patch as mock_patch

		frappe.set_user(self.nv_a.user)
		with mock_patch("frappe.db.has_column", return_value=False):
			rows = frappe.get_list("Sales Order", filters={"customer": KHACH})
		self.assertEqual(rows, [])

	def test_ket_qua_kiem_duoc_nho_khong_hoi_lai_moi_lan(self):
		"""`_cot_khoa_phong_ton_tai()` chỉ được gọi `frappe.db.has_column`
		ĐÚNG MỘT LẦN cho nhiều lượt dựng điều kiện liên tiếp — nhớ trong
		tiến trình, không hỏi lại CSDL/Redis mỗi lần (hàm này chạy trên MỌI
		truy vấn)."""
		from unittest.mock import patch as mock_patch

		frappe.set_user(self.nv_a.user)
		with mock_patch("frappe.db.has_column", return_value=True) as gia_lap:
			permissions.sales_query()
			permissions.delivery_query()
			permissions.invoice_query()
			self.assertEqual(gia_lap.call_count, 1)

	def test_da_kiem_du_toan_ven_van_thay_dung_don_khi_co_cot(self):
		"""Đối chứng: chốt KHÔNG được tự ý fail-closed khi cột THẬT SỰ có
		(giá trị mặc định trên site test) — chỉ fail-closed khi thiếu."""
		frappe.set_user(self.nv_a.user)
		ten = frappe.get_list(
			"Sales Order", filters={"customer": KHACH}, pluck="name"
		)
		self.assertIn(self.don_a, ten)

	def test_portal_order_track_fail_closed_khong_phai_loi_csdl_khi_thieu_cot(self):
		"""V2 (review vòng sửa 3, Important) — bằng chứng cho ĐÚNG con
		đường khách hàng thật đi qua: `portal_order_track` gọi
		`dam_bao_xem_duoc` TRƯỚC `so.check_permission("read")`
		(`api/portal.py`), không qua tầng hook (`permissions.py`) chút nào.
		Trước bản vá V2, lưới an toàn C3 chỉ nằm ở `permissions.py` — đường
		NÀY (đường endpoint, nơi phần lớn traffic cổng thật đi qua) vẫn ăn
		`frappe.db.get_value(..., "custom_khoa_phong")` thô, tức vẫn sập
		bằng lỗi CSDL nếu thiếu cột. Sau bản vá, `dam_bao_xem_duoc` tự gọi
		CHUNG `_cot_khoa_phong_ton_tai()` (chuyển sang `portal_context.py`)
		— khẳng định ở đây: nhân viên khoa nhận `PermissionError` (thông
		điệp `LOI_KHONG_THAY`, không tiết lộ "thiếu cột"), TUYỆT ĐỐI không
		phải một `OperationalError`/`ProgrammingError` từ MariaDB."""
		from unittest.mock import patch as mock_patch

		frappe.set_user(self.nv_a.user)
		with mock_patch("frappe.db.has_column", return_value=False):
			with self.assertRaises(frappe.PermissionError) as cm:
				portal_api.portal_order_track(self.don_a)
		self.assertEqual(str(cm.exception), portal_context.LOI_KHONG_THAY)

	def test_portal_order_history_fail_closed_khong_phai_loi_csdl_khi_thieu_cot(self):
		"""V2 (review tổng toàn nhánh, Important) — `_pham_vi_filters()`
		(`api/portal.py`, nuôi `portal_order_history`/`_dem_don_theo_trang_
		thai`) TRƯỚC bản vá KHÔNG gọi `_cot_khoa_phong_ton_tai()` — an toàn
		trên site test hôm nay CHỈ nhờ MAY MẮN cột thật sự tồn tại. Giả lập
		"coi như thiếu cột" (mock `has_column=False`, cùng kỹ thuật các test
		C3 khác trong lớp này): SAU bản vá, hai endpoint traffic cao nhất
		này phải fail-closed (rỗng), KHÔNG được lặng lẽ trả dữ liệu thật chỉ
		vì cột THẬT vẫn còn đó trên site test."""
		from unittest.mock import patch as mock_patch

		frappe.set_user(self.nv_a.user)
		with mock_patch("frappe.db.has_column", return_value=False):
			kq = portal_api.portal_order_history()
		self.assertEqual(kq["rows"], [])
		self.assertEqual(kq["tong"], 0)

	def test_portal_dashboard_kpi_fail_closed_khong_phai_loi_csdl_khi_thieu_cot(self):
		"""Cùng lý do ngay trên — `portal_dashboard_kpi` đếm qua
		`_dem_don_theo_trang_thai` -> `_pham_vi_filters()`, endpoint traffic
		cao thứ hai (màn đầu tiên khách nhìn thấy mỗi lần đăng nhập)."""
		from unittest.mock import patch as mock_patch

		frappe.set_user(self.nv_a.user)
		with mock_patch("frappe.db.has_column", return_value=False):
			kq = portal_api.portal_dashboard_kpi()
		self.assertEqual(kq["don_cho_xac_nhan"], 0)
		self.assertEqual(kq["don_dang_giao"], 0)

	def test_pham_vi_filters_fail_closed_khong_tham_chieu_cot_khi_thieu(self):
		"""V2 — bằng chứng RED THẬT (hai test round-trip ngay trên KHÔNG đỏ
		trước bản vá: `permissions.sales_query()`, tầng hook, ĐÃ tự chặn
		bằng `"1=0"` từ Vòng sửa 2/3, nên kết quả cuối cùng của
		`frappe.get_list` vẫn rỗng dù `_pham_vi_filters()` chưa có lưới —
		hai lớp AND lại, lớp hook che mất khoảng hở của lớp endpoint). Rủi
		ro THẬT không nằm ở KẾT QUẢ (hook vẫn cứu được) mà ở CÂU SQL: filter
		`["custom_khoa_phong", "=", ...]` bị AND vào WHERE cùng điều kiện
		hook — MariaDB PHẢI phân giải tên cột đó lúc parse, không có
		short-circuit theo giá trị runtime của vế còn lại. Trên một site
		thật CHƯA chạy patch (cột thật sự không tồn tại), câu đó vẫn ném
		1054 bất kể hook có trả `"1=0"` hay không. Kiểm TRỰC TIẾP giá trị
		`_pham_vi_filters()` trả về — không round-trip qua `frappe.get_list`
		— đúng kỹ thuật `test_dieu_kien_sql_tra_1_bang_0_khi_thieu_cot` đã
		dùng để cô lập tầng hook."""
		from unittest.mock import patch as mock_patch

		frappe.set_user(self.nv_a.user)
		with mock_patch("frappe.db.has_column", return_value=False):
			filters = portal_api._pham_vi_filters()
		self.assertFalse(
			any("custom_khoa_phong" in str(f) for f in filters),
			f"_pham_vi_filters() vẫn tham chiếu custom_khoa_phong dù cột "
			f"được coi là thiếu — sẽ ném 1054 thô trên site chưa chạy "
			f"patch, bất kể tầng hook có chặn hay không: {filters!r}",
		)


class TestC5NguoiDungNoiBoKhongPhaiAdministrator(_NenCachLy):
	"""C5 (review vòng sửa 2) — Frappe cho `Administrator` đi thẳng TRƯỚC
	khi tới bất kỳ hook `has_permission`/`permission_query_conditions` nào
	(`frappe/permissions.py::has_permission`, nhánh `user == "Administrator"`
	return `True` ngay). Cả bộ suite (kể cả `setUp`/tearDown, và MỌI test
	khác trong file này giữa hai lần `frappe.set_user`) chạy dưới
	`Administrator` phần lớn thời gian — suite xanh KHÔNG PHẢI bằng chứng
	rằng `_is_restricted_user` đúng cho một System User THẬT (nhân viên
	Miyano ngồi Desk). Dựng một System User mang role `Sales User` (không
	phải Administrator) và khẳng định họ KHÔNG bị vế khoa mới thêm chặn
	nhầm."""

	def setUp(self):
		super().setUp()
		self.don_a = self._don(self.kp_a.name)
		self.staff_email = "zztest8.staff@miyano.vn"
		if not frappe.db.exists("User", self.staff_email):
			u = frappe.get_doc({
				"doctype": "User", "email": self.staff_email, "first_name": "ZZ Staff",
				"user_type": "System User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Sales User"})
			u.insert(ignore_permissions=True)

	def test_nhan_vien_mien_khong_bi_gioi_han_theo_khoa(self):
		frappe.set_user(self.staff_email)
		ten = frappe.get_list(
			"Sales Order", filters={"customer": KHACH}, pluck="name"
		)
		self.assertIn(
			self.don_a, ten,
			"System User (nhân viên Miyano) bị hook khoa phòng chặn nhầm — "
			"_is_restricted_user phải trả False cho user_type=System User.",
		)

	def test_nhan_vien_mien_doc_duoc_ca_hai_khoa(self):
		don_b = self._don(self.kp_b.name)
		frappe.set_user(self.staff_email)
		ten = frappe.get_list(
			"Sales Order", filters={"customer": KHACH}, pluck="name"
		)
		self.assertIn(self.don_a, ten)
		self.assertIn(don_b, ten)


class TestC6HaiTangDongYVoiNhau(_NenCachLy):
	"""C6 (review vòng sửa 2) — từ Vòng sửa 1 có HAI tầng quyết định phạm vi
	cho cùng một chứng từ: endpoint cổng (`dam_bao_xem_duoc`/`pham_vi_don`,
	`api/portal.py`) và hook framework (`permissions.py`, Vòng sửa 1 C2).
	Hiện chúng đồng ý vì tầng hook luôn ANDed vào MỌI `frappe.get_list`
	không `ignore_permissions` — nhưng KHÔNG assertion nào trong bộ test
	trước đó khẳng định trực tiếp điều đó. Nếu ai đó đổi một endpoint liệt
	kê (vd. `portal_deliveries`) sang `frappe.get_all(..., ignore_
	permissions=True)`, hai tầng lệch NGAY (endpoint hết tự lọc chặt, hook
	bị bỏ qua) mà không test nào ở Vòng sửa 1 bắt được — test dưới đây so
	sánh TRỰC TIẾP kết quả hai đường cho CÙNG một chứng từ."""

	def setUp(self):
		super().setUp()
		self.don_a = self._don(self.kp_a.name)

	def test_sales_order_hai_duong_dong_y_cho_khoa_khac(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_order_track(self.don_a)
		ten = frappe.get_list(
			"Sales Order", filters={"customer": KHACH}, pluck="name"
		)
		self.assertNotIn(self.don_a, ten)

	def test_sales_order_hai_duong_dong_y_cho_chinh_khoa(self):
		frappe.set_user(self.nv_a.user)
		self.assertEqual(
			portal_api.portal_order_track(self.don_a)["order"], self.don_a
		)
		ten = frappe.get_list(
			"Sales Order", filters={"customer": KHACH}, pluck="name"
		)
		self.assertIn(self.don_a, ten)

	def test_portal_deliveries_khop_chinh_xac_voi_frappe_get_list_qua_hook(self):
		"""Ghim đúng kịch bản C6 nêu: nếu `portal_deliveries` bị đổi sang
		một đường bỏ qua hook, test này phải đỏ vì hai tập hợp lệch nhau."""
		so_a = self._don_submitted(self.kp_a.name)
		dn_a = make_delivery_note(so_a.name)
		dn_a.insert(ignore_permissions=True)

		frappe.set_user(self.nv_b.user)
		qua_endpoint = {r["name"] for r in portal_api.portal_deliveries(limit=200)}
		qua_hook_truc_tiep = set(
			frappe.get_list("Delivery Note", filters={"customer": KHACH}, pluck="name")
		)
		self.assertEqual(qua_endpoint, qua_hook_truc_tiep)
		self.assertNotIn(dn_a.name, qua_endpoint)

		frappe.set_user(self.nv_a.user)
		qua_endpoint = {r["name"] for r in portal_api.portal_deliveries(limit=200)}
		qua_hook_truc_tiep = set(
			frappe.get_list("Delivery Note", filters={"customer": KHACH}, pluck="name")
		)
		self.assertEqual(qua_endpoint, qua_hook_truc_tiep)
		self.assertIn(dn_a.name, qua_endpoint)

	def test_portal_invoices_khop_chinh_xac_voi_frappe_get_list_qua_hook(self):
		so_a = self._don_submitted(self.kp_a.name)
		si_a = make_sales_invoice(so_a.name)
		si_a.insert(ignore_permissions=True)

		frappe.set_user(self.nv_b.user)
		qua_endpoint = {r["name"] for r in portal_api.portal_invoices(limit=200)["rows"]}
		qua_hook_truc_tiep = set(
			frappe.get_list("Sales Invoice", filters={"customer": KHACH}, pluck="name")
		)
		self.assertEqual(qua_endpoint, qua_hook_truc_tiep)
		self.assertNotIn(si_a.name, qua_endpoint)


class TestKhongLamPhienKhachDangDung(FrappeTestCase):
	"""Task 9 — nghiệm thu ràng buộc tự đặt cho cả đề án: không làm phiền
	khách hàng đang dùng. Sau bốn bước nền (1–4), mọi tài khoản cổng CŨ là
	`Quản lý` không gắn khoa → `pham_vi_don()` trả `{}` → phải thấy ĐÚNG
	những gì họ thấy trước khi đề án này tồn tại.

	`TestTuongThichNguoc` (`test_portal_member.py`) đã khẳng định vai trò/
	khoa phòng của Portal Member sau patch VÀ `pham_vi_don(user) == {}` cho
	đúng hai tài khoản này — KHÔNG lặp lại khẳng định đó ở đây.
	`TestDonCuKhongGanKhoa` (lớp trên trong file này) đã khẳng định MỘT đơn
	cụ thể còn hiện ra. Còn thiếu đúng một việc: SỐ LƯỢNG chứng từ qua các
	endpoint thật phải khớp CHÍNH XÁC — không thiếu, không thừa — với CSDL,
	cho đúng khách hàng đó. Hai test dưới đây đo qua HAI endpoint khác nhau
	(`portal_order_history`/Sales Order, `portal_invoices`/Sales Invoice —
	khác hook quyền: `sales_query` so với `invoice_query` + `_loc_qua_don_
	cha`), không phải một phép đo lặp lại dưới hai cái tên.

	Dùng tài khoản cổng THẬT (`bvbm@demo.miyano`, `bvminhduc@demo.miyano`)
	— đây là bài kiểm "khách đang dùng không bị phiền", một khách ZZTEST
	mới dựng lên không kiểm đúng điều đang nói. CHỈ ĐỌC — không sửa gì.

	Đo bằng SO SÁNH HAI VẾ cùng lúc, cùng điều kiện lọc — không ghim hằng
	số (bài học Task 4). `frappe.db.count(..., {"customer": ...})` KHÔNG
	thêm `docstatus < 2`: đọc `portal_order_history`/`portal_invoices`
	(api/portal.py) cho thấy nhánh không lọc theo trạng thái không tự thêm
	điều kiện `docstatus` nào — cơ chế loại bỏ chứng từ Đã huỷ (nếu có) nằm
	ở UI (chip lọc `trang_thai`), không ở tầng đếm mặc định này. Brief gốc
	của Task 9 giả định `docstatus < 2` — SAI với hành vi thật: đo tại
	18/08/2026, "Bệnh viện Bạch Mai" có `SAL-ORD-2026-00027` docstatus=2
	(Đã huỷ), và `tong` production ĐANG đếm luôn đơn đó (71, brief SẼ kỳ
	vọng sai thành 70). Đã tự đo lại và sửa (xem `task-9-report.md`)."""

	CAC_TAI_KHOAN_CU = ("bvbm@demo.miyano", "bvminhduc@demo.miyano")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_tai_khoan_cu_van_thay_dung_so_luong_don_cua_benh_vien(self):
		for user in self.CAC_TAI_KHOAN_CU:
			khach = frappe.db.get_value("Portal Member", {"user": user}, "customer")
			frappe.set_user(user)
			ds = portal_api.portal_order_history()
			frappe.set_user("Administrator")
			# CÙNG lúc, CÙNG điều kiện lọc (chỉ `customer`, không thêm
			# `docstatus` — xem docstring lớp) — so hai vế với nhau, không
			# ghim một con số tuyệt đối.
			that = frappe.db.count("Sales Order", {"customer": khach})
			self.assertGreater(
				that, 0,
				f"{user} ({khach}): CSDL không còn đơn nào — phép so sánh "
				f"0 == 0 không chứng minh được gì (bẫy Task 4)",
			)
			self.assertEqual(
				ds["tong"], that,
				f"{user} ({khach}): endpoint trả tong={ds['tong']}, "
				f"CSDL đếm được {that} đơn",
			)

	def test_tai_khoan_cu_van_thay_dung_so_luong_hoa_don_cua_benh_vien(self):
		"""Endpoint THỨ HAI. Đo thật 18/08/2026: Bệnh viện Bạch Mai hiện
		KHÔNG có Sales Invoice nào (0 == 0 tự nó không chứng minh gì), Minh
		Đức có 9 — chốt TỔNG hai tài khoản > 0 sau vòng lặp để cả test không
		rỗng, thay vì đòi từng tài khoản một phải dương (đó là dữ liệu thật,
		không phải điều test này được phép ép buộc)."""
		tong_tat_ca = 0
		for user in self.CAC_TAI_KHOAN_CU:
			khach = frappe.db.get_value("Portal Member", {"user": user}, "customer")
			frappe.set_user(user)
			ds = portal_api.portal_invoices()
			frappe.set_user("Administrator")
			that = frappe.db.count("Sales Invoice", {"customer": khach})
			tong_tat_ca += that
			self.assertEqual(
				ds["tong"], that,
				f"{user} ({khach}): endpoint trả tong={ds['tong']}, "
				f"CSDL đếm được {that} hoá đơn",
			)
		self.assertGreater(
			tong_tat_ca, 0,
			"cả hai tài khoản đều 0 hoá đơn — phép so sánh rỗng, không "
			"chứng minh được gì (bẫy Task 4)",
		)


class TestV3KhoaKhongGanKhoVanQuaDuocCong(_NenCachLy):
	"""V3 (review tổng toàn nhánh — Ruling SAI, §7.0 của progress ledger).
	Ruling gốc hoãn việc này với lý lẽ "hôm nay chưa có khoa phòng nào
	không gắn kho" — lý lẽ đó TỰ HUỶ: `docs/HDSD-phan-quyen-khoa-phong.md`
	(tài liệu vừa viết CHO chính đề án này) dạy nhân viên Miyano khai
	`Customer Department` để TRỐNG ô Kho — đó là điều kiện để tạo Portal
	Member vai "Nhân viên khoa" cho một khoa chưa có nhu cầu quản lý kho.

	`kp_a`/`kp_b` (fixture `_NenCachLy`) vốn dĩ đã KHÔNG gắn kho (`_kp()`
	không truyền `kho`) — đúng hình đó, không cần dựng thêm khoa nào khác.

	`api/kho.py::_khoa_cua_kho` xác nhận sở hữu bằng so `Customer
	Department.kho == kho` — khoa `kho=None` không bao giờ khớp một `kho`
	thật, `PermissionError` chắc chắn dù cùng khách hàng. `kho/khoa_
	phong.py::list_rows` lọc `{"kho": kho}` — khoa đó không bao giờ hiện
	trong danh mục cổng, dù nhân viên đứng đúng kho của bệnh viện mình."""

	def setUp(self):
		super().setUp()
		self.kho = frappe.db.get_value("Customer Warehouse", {"customer": KHACH})
		if not self.kho:
			self.kho = frappe.get_doc({
				"doctype": "Customer Warehouse", "customer": KHACH,
				"ten_kho": "ZZTEST8 Kho V3", "ma_kho": "ZZT8V3", "active": 1,
				"ngay_bat_dau": frappe.utils.today(),
			}).insert(ignore_permissions=True).name
			self.addCleanup(
				frappe.delete_doc, "Customer Warehouse", self.kho,
				force=True, ignore_permissions=True,
			)
		self.assertIsNone(
			frappe.db.get_value("Customer Department", self.kp_a.name, "kho"),
			"Fixture lỗi: kp_a phải KHÔNG gắn kho để phép kiểm này có nghĩa "
			"(đúng hình HDSD dạy Miyano khai).",
		)

	def _xoa_khach_khac(self, khach_khac):
		frappe.db.delete("Customer Department", {"customer": khach_khac})
		frappe.delete_doc("Customer", khach_khac, force=True, ignore_permissions=True)

	def test_khoa_khong_gan_kho_hien_trong_danh_muc_cong(self):
		rows = khoa_phong_mod.list_rows(self.kho)
		self.assertIn(
			self.kp_a.name, [r["name"] for r in rows],
			"khoa không gắn kho phải VẪN hiện trong danh mục cổng — cùng "
			"khách hàng với kho đang xem, không cần chính khoa đó gắn kho.",
		)

	def test_khoa_khong_gan_kho_van_xac_nhan_so_huu_duoc(self):
		# Không được ném PermissionError — endpoint sửa (kho_khoa_phong_save)
		# gọi thẳng hàm này trước khi cho sửa.
		self.assertEqual(kho_api._khoa_cua_kho(self.kp_a.name, self.kho), self.kp_a.name)

	def test_khoa_cua_kho_van_chan_khoa_cua_khach_khac(self):
		khach_khac = "ZZTEST8V3 Benh Vien Khac"
		if not frappe.db.exists("Customer", khach_khac):
			frappe.get_doc({
				"doctype": "Customer", "customer_name": khach_khac,
				"customer_type": "Company", "customer_group": "All Customer Groups",
				"territory": "All Territories",
			}).insert(ignore_permissions=True)
		self.addCleanup(self._xoa_khach_khac, khach_khac)
		kp_khac = frappe.get_doc({
			"doctype": "Customer Department", "customer": khach_khac,
			"ten_khoa_phong": "ZZTEST8V3 Khoa Khac",
		}).insert(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			kho_api._khoa_cua_kho(kp_khac.name, self.kho)


class TestBienBanBanGiaoDaKy(_NenCachLy):
	"""Chủ đầu tư chốt 25/08/2026 — nhân viên Miyano in mẫu 02-VT, ký nhận
	với khách tại kho, **scan rồi đính vào chính phiếu giao**; khách bấm
	"⬇ Phiếu giao đợt" trên cổng phải nhận ĐÚNG BẢN ĐÃ KÝ đó, không phải một
	bản in lại chưa có chữ ký nào.

	Ba bài dưới đây tách theo ba thứ có thể hỏng RIÊNG, không gộp: có scan
	thì trả scan; chưa có scan thì vẫn in như cũ (không được vỡ đường đang
	chạy hằng ngày); và ô `Attach` trỏ tới file KHÔNG thuộc phiếu này thì
	không được phát ra.
	"""

	def setUp(self):
		super().setUp()
		self.so_a = self._don_submitted(self.kp_a.name)
		self.dn_a = make_delivery_note(self.so_a.name)
		self.dn_a.insert(ignore_permissions=True)

	# Ảnh PNG 1x1 THẬT. Frappe chạy bản scan qua PIL khi đuôi file là ảnh
	# (nén lại/đọc kích thước), nên vài byte giả sẽ nổ `UnidentifiedImageError`
	# ở tầng fixture — một thất bại không liên quan gì tới thứ đang kiểm.
	_PNG = base64.b64decode(
		"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
	)

	def _dinh_scan(self, doctype, name, ten_file="bien-ban-da-ky.png", noi_dung=None):
		noi_dung = self._PNG if noi_dung is None else noi_dung
		f = frappe.get_doc({
			"doctype": "File", "file_name": ten_file,
			"attached_to_doctype": doctype, "attached_to_name": name,
			"is_private": 1, "content": noi_dung,
		}).insert(ignore_permissions=True)
		return f

	def test_co_ban_scan_thi_cong_tra_DUNG_ban_da_ky(self):
		f = self._dinh_scan("Delivery Note", self.dn_a.name)
		frappe.db.set_value(
			"Delivery Note", self.dn_a.name, "custom_bien_ban_da_ky", f.file_url
		)
		frappe.set_user(self.nv_a.user)
		portal_api.portal_document_download("Delivery Note", self.dn_a.name)
		self.assertEqual(frappe.local.response.filecontent, self._PNG)
		# KHÔNG được cứng đuôi `.pdf`: bản scan phần lớn là ảnh chụp, và một
		# JPG mang tên `.pdf` mở ra rác trên máy bệnh viện.
		self.assertTrue(
			frappe.local.response.filename.endswith(".png"),
			f"đuôi file sai: {frappe.local.response.filename}",
		)

	def test_chua_co_ban_scan_thi_van_in_nhu_cu(self):
		"""Vế răng của bài trên: nếu nhánh mới nuốt luôn cả đường cũ thì bài
		trên vẫn xanh, còn 6 tài khoản đang chạy thật mất nút tải phiếu."""
		frappe.set_user(self.nv_a.user)
		from unittest.mock import patch

		with patch("frappe.utils.pdf.get_pdf", return_value=b"%PDF-fake"):
			portal_api.portal_document_download("Delivery Note", self.dn_a.name)
		self.assertEqual(frappe.local.response.filecontent, b"%PDF-fake")

	def test_cong_phat_DUNG_to_phieu_hai_ben_ky(self):
		"""Chủ đầu tư chốt 25/08 — nút "⬇ Phiếu giao đợt" phải phát ĐÚNG mẫu
		02-VT "Phiếu xuất kho kiêm biên bản bàn giao", tờ giấy hai bên ký tại
		kho. Trước bản này nó phát "Miyano - Phiếu giao hàng" — một tờ KHÁC:
		bố cục khác, không có cột Số lô/Hạn dùng, không có đoạn cam kết bàn
		giao. Khách ký tờ A, tải về tờ B, và không có tín hiệu nào báo vì mỗi
		tờ tự nó đều "đúng".

		Khẳng định trên HTML đã render (chặn ở `get_pdf`) chứ không khẳng
		định tên mẫu trong hằng số — hằng số đổi mà đường render đi lối khác
		thì bài kiểm tên vẫn xanh.
		"""
		frappe.set_user(self.nv_a.user)
		from unittest.mock import patch

		giu = {}
		with patch("frappe.utils.pdf.get_pdf", side_effect=lambda h, *a, **k: giu.setdefault("html", h) and b"" or b"%PDF"):
			portal_api.portal_document_download("Delivery Note", self.dn_a.name)
		html = giu["html"]
		for phai_co in (
			"PHIẾU XUẤT KHO KIÊM BIÊN BẢN BÀN GIAO",
			"99/2025/TT-BTC", "Số lô", "Hạn dùng",
			"Hai bên đã kiểm tra và xác nhận",
			"Người giao hàng", "Người nhận hàng",
		):
			self.assertIn(phai_co, html, f"cổng phát nhầm mẫu — thiếu «{phai_co}»")

	def test_o_attach_tro_sang_file_CUA_PHIEU_KHAC_thi_khong_phat_ra(self):
		"""`custom_bien_ban_da_ky` chỉ là một CHUỖI đường dẫn, sửa được từ
		Desk và trỏ được tới file của bất kỳ chứng từ nào. Không đối chiếu
		`attached_to_doctype`/`attached_to_name` thì cổng thành một đường đọc
		file tuỳ ý — đúng lớp rò rỉ mà `dam_bao_xem_duoc` dựng ra để chặn.
		"""
		la = self._dinh_scan("Sales Order", self.so_a.name, "cua-chung-tu-khac.png")
		frappe.db.set_value(
			"Delivery Note", self.dn_a.name, "custom_bien_ban_da_ky", la.file_url
		)
		frappe.set_user(self.nv_a.user)
		from unittest.mock import patch

		with patch("frappe.utils.pdf.get_pdf", return_value=b"%PDF-fake"):
			portal_api.portal_document_download("Delivery Note", self.dn_a.name)
		self.assertEqual(
			frappe.local.response.filecontent, b"%PDF-fake",
			"file không thuộc phiếu này vẫn bị phát ra cho khách",
		)
		self.assertNotEqual(frappe.local.response.filecontent, self._PNG)
