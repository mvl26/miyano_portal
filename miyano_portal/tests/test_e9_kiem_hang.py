"""E9 — Kiểm hàng khi nhận & trả lại phần hàng hỏng.

Thiết kế: `docs/superpowers/specs/2026-08-16-kiem-hang-tra-hang-hong-design.md`.

Hai điều cả file này tồn tại để chốt, vì cả hai đều là loại hồi quy im lặng:

1. **Khách CHƯA MỞ KHO vẫn kiểm hàng được.** Đây là lý do doctype này tồn tại
   riêng thay vì bám vào `Customer Stock Receipt` (16/21 khách trên site chưa
   có kho). `TestKiemHangKhachKhongCoKho` dựng một khách hoàn toàn mới, KHÔNG
   `Customer Warehouse` nào, và chạy trọn luồng.
2. **`sl_giao` không bao giờ đến từ client.** Nó là mốc đối chiếu; nhận nó từ
   payload là để bên bị ràng buộc tự khai ràng buộc của mình.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

from miyano_portal.api import portal as api
from miyano_portal import portal_kiem_hang as kh

COMPANY = "Miyano Việt Nam"
KHO_MYN = "Kho Miyano - MYN"
COST_CENTER = "Main - MYN"

ITEM = "MYN-GLOVE-M"
ITEM_2 = "MYN-SYR-10"

KHACH_MOI = "KH Test Kiểm Hàng"
USER_MOI = "kiemhang@test.miyano"
KHACH_KHAC = "KH Test Kiểm Hàng B"
USER_KHAC = "kiemhangb@test.miyano"

STAFF = "sales-kiemhang@test.miyano"


def _khach_va_user(customer: str, email: str) -> None:
	"""Khách hàng + Contact + Website User, KHÔNG mở Customer Warehouse.

	Dựng mới thay vì mượn khách demo có sẵn: điểm cần chứng minh là luồng chạy
	cho khách KHÔNG có kho, mà mọi khách demo trong `seed_kho_demo` đều có kho.
	"""
	if not frappe.db.exists("Customer", customer):
		frappe.get_doc({
			"doctype": "Customer", "customer_name": customer,
			"customer_type": "Company",
		}).insert(ignore_permissions=True)
	if not frappe.db.exists("User", email):
		u = frappe.get_doc({
			"doctype": "User", "email": email, "first_name": customer,
			"send_welcome_email": 0, "user_type": "Website User",
		})
		# Role `Customer` — chính là role mà tài khoản cổng THẬT mang (nó cấp
		# quyền đọc Sales Order/Delivery Note/Sales Invoice, xem hooks.py).
		# Thiếu nó, fixture dựng ra một tài khoản NHẸ HƠN tài khoản thật và
		# test sẽ đỏ ở đúng những chỗ khách thật chạy được.
		u.append("roles", {"role": "Customer"})
		u.insert(ignore_permissions=True)
	# `User.after_insert` của Frappe TỰ TẠO một Contact cho tài khoản mới —
	# Contact đó có `user` nhưng KHÔNG có Dynamic Link nào sang Customer. Bản
	# đầu của fixture này thấy nó rồi bỏ qua, nên `get_allowed_customers()`
	# trả rỗng và 21/23 test đỏ với "Tài khoản chưa gắn với khách hàng nào".
	# Vì vậy: tìm thấy thì phải KIỂM cả link, không chỉ kiểm sự tồn tại.
	ten_contact = frappe.db.get_value("Contact", {"user": email}, "name")
	if ten_contact:
		ct = frappe.get_doc("Contact", ten_contact)
	else:
		ct = frappe.get_doc({"doctype": "Contact", "first_name": customer, "user": email})
	if not any(
		l.link_doctype == "Customer" and l.link_name == customer
		for l in (ct.get("links") or [])
	):
		ct.append("links", {"link_doctype": "Customer", "link_name": customer})
		ct.save(ignore_permissions=True) if ct.name else ct.insert(ignore_permissions=True)
	# Task 5 (18/08/2026): `portal_context.get_allowed_customers()` đổi từ đọc
	# `Contact`/`Dynamic Link` sang đọc `Portal Member`. Đoạn Dynamic Link ở
	# trên vẫn đúng cho mọi thứ CÒN LẠI đi qua Contact (thông báo, v.v.) —
	# nhưng bản thân danh tính cổng thì không còn đi qua nó nữa. Thêm bước
	# này là bản sao chính xác của việc tạo Contact+Dynamic Link phía trên:
	# cùng một ý "dựng một tài khoản cổng thuộc khách hàng này", chỉ đổi
	# đúng nguồn sự thật. Không có ca "hai tài khoản" nào trong file test
	# này nên luôn active=1, không cần nhánh Quản lý-tắt của patch backfill.
	if not frappe.db.exists("Portal Member", {"user": email}):
		frappe.get_doc({
			"doctype": "Portal Member", "user": email, "customer": customer,
			"vai_tro": "Quản lý",
		}).insert(ignore_permissions=True)


def _staff_user() -> str:
	if not frappe.db.exists("User", STAFF):
		u = frappe.get_doc({
			"doctype": "User", "email": STAFF, "first_name": "Sales Kiểm Hàng",
			"send_welcome_email": 0,
		})
		u.insert(ignore_permissions=True)
	u = frappe.get_doc("User", STAFF)
	for role in ("Sales Manager", "Sales User"):
		if role not in [r.role for r in u.roles]:
			u.append("roles", {"role": role})
	u.save(ignore_permissions=True)
	return STAFF


class _KiemHangBase(FrappeTestCase):
	"""FrappeTestCase rollback MỘT LẦN cho cả class — mọi test phải tự đưa
	trạng thái về mốc chuẩn trong setUp, không dựa vào test đứng trước."""

	customer = KHACH_MOI
	user = USER_MOI

	def setUp(self):
		_khach_va_user(KHACH_MOI, USER_MOI)
		_khach_va_user(KHACH_KHAC, USER_KHAC)
		self.staff = _staff_user()
		frappe.set_user("Administrator")
		self._nap_ton(ITEM, 200)
		self._nap_ton(ITEM_2, 200)
		self.addCleanup(frappe.set_user, "Administrator")
		# `tabError Log` là MyISAM (phi giao dịch) — dòng do test ép lỗi sinh
		# ra không bị rollback cuốn đi. Tự dọn, cùng khuôn test_kho_delivery_hook.
		self.addCleanup(
			frappe.db.delete, "Error Log", {"method": ["like", "Kiểm hàng:%"]}
		)

	def _nap_ton(self, item_code, qty):
		make_stock_entry(
			item_code=item_code, qty=qty, to_warehouse=KHO_MYN, rate=1000,
			company=COMPANY, purpose="Material Receipt",
		)

	def _dn(self, rows=None, customer=None, submit=True):
		dn = frappe.new_doc("Delivery Note")
		dn.company = COMPANY
		dn.customer = customer or self.customer
		dn.posting_date = frappe.utils.today()
		for r in rows or [{"item_code": ITEM, "qty": 10, "rate": 95000}]:
			dn.append("items", {
				"item_code": r["item_code"], "qty": r["qty"], "rate": r["rate"],
				"warehouse": KHO_MYN, "cost_center": COST_CENTER,
			})
		dn.insert(ignore_permissions=True)
		if submit:
			dn.submit()
		return dn

	def _nhu_khach(self, user=None):
		frappe.set_user(user or self.user)

	def _gui(self, dn, dong, ghi_chu=None, user=None):
		self._nhu_khach(user)
		try:
			return api.portal_kiem_hang_gui(dn.name, dong, ghi_chu)
		finally:
			frappe.set_user("Administrator")


class TestKiemHangKhachKhongCoKho(_KiemHangBase):
	"""Điểm 1 của docstring đầu file — lý do doctype này tồn tại riêng."""

	def test_khach_khong_co_kho_van_mo_duoc_man_kiem_hang(self):
		self.assertFalse(
			frappe.db.exists("Customer Warehouse", {"customer": self.customer}),
			"Fixture sai: khách này phải KHÔNG có kho, nếu không test chứng "
			"minh nhầm điều đang cần chứng minh.",
		)
		dn = self._dn()
		self._nhu_khach()
		try:
			d = api.portal_kiem_hang_get(dn.name)
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(d["moi"])
		self.assertEqual(len(d["bien_ban"]["items"]), 1)
		self.assertEqual(d["bien_ban"]["items"][0]["item_code"], ITEM)

	def test_khach_khong_co_kho_gui_duoc_bien_ban_bao_hang_hong(self):
		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 7, "sl_tra": 3,
		                     "ly_do": "Vỡ 3 hộp"}])
		self.assertEqual(kq["trang_thai"], kh.TT_CHO_XU_LY)
		self.assertTrue(kq["co_hang_hong"])


class TestKiemHangDungSoLieu(_KiemHangBase):
	def test_dong_gop_theo_ma_hang_va_mac_dinh_nhan_du(self):
		"""Hai dòng cùng mã trên phiếu giao (Miyano xuất từ hai lô) phải hiện
		ra một dòng cho khách — chi tiết lô là việc nội bộ của Miyano."""
		dn = self._dn([
			{"item_code": ITEM, "qty": 6, "rate": 95000},
			{"item_code": ITEM, "qty": 4, "rate": 95000},
			{"item_code": ITEM_2, "qty": 5, "rate": 12000},
		])
		self._nhu_khach()
		try:
			items = api.portal_kiem_hang_get(dn.name)["bien_ban"]["items"]
		finally:
			frappe.set_user("Administrator")
		theo_ma = {i["item_code"]: i for i in items}
		self.assertEqual(len(items), 2)
		self.assertEqual(theo_ma[ITEM]["sl_giao"], 10)
		# Mặc định "nhận đủ": trường hợp phổ biến nhất không phải gõ gì.
		self.assertEqual(theo_ma[ITEM]["sl_nhan"], 10)
		self.assertEqual(theo_ma[ITEM]["sl_tra"], 0)

	def test_sl_giao_tu_client_bi_bo_qua(self):
		"""Điểm 2 của docstring đầu file.

		Khách gửi `sl_giao: 999` và `sl_nhan: 500`. Nếu server tin payload thì
		500 <= 999 và biên bản lưu thành công — khách vừa tự khai mình được
		giao 999. Server phải dựng lại `sl_giao` từ phiếu giao (10) và chặn.
		"""
		dn = self._dn()
		self._nhu_khach()
		try:
			with self.assertRaises(frappe.ValidationError):
				api.portal_kiem_hang_gui(
					dn.name,
					[{"item_code": ITEM, "sl_giao": 999, "sl_nhan": 500,
					  "sl_tra": 0, "ly_do": "x"}],
				)
		finally:
			frappe.set_user("Administrator")

	def test_nhan_cong_tra_vuot_sl_giao_bi_chan(self):
		dn = self._dn()
		self._nhu_khach()
		try:
			with self.assertRaises(frappe.ValidationError):
				api.portal_kiem_hang_gui(
					dn.name,
					[{"item_code": ITEM, "sl_nhan": 9, "sl_tra": 3, "ly_do": "x"}],
				)
		finally:
			frappe.set_user("Administrator")

	def test_lech_ma_khong_co_ly_do_bi_chan(self):
		dn = self._dn()
		self._nhu_khach()
		try:
			with self.assertRaises(frappe.ValidationError):
				api.portal_kiem_hang_gui(
					dn.name, [{"item_code": ITEM, "sl_nhan": 7, "sl_tra": 0}]
				)
		finally:
			frappe.set_user("Administrator")

	def test_nhan_du_thi_dong_ngay_khong_lam_phien_nhan_vien(self):
		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 10, "sl_tra": 0}])
		self.assertEqual(kq["trang_thai"], kh.TT_DA_XAC_NHAN)
		self.assertFalse(kq["co_hang_hong"])

	def test_thieu_hang_khong_hong_van_vao_cho_xu_ly(self):
		"""Thiếu hàng không sinh phiếu trả, nhưng vẫn là khiếu nại — rơi vào
		"Đã xác nhận" là mất tín hiệu (đúng lỗi C1 của BR-K17)."""
		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 8, "sl_tra": 0,
		                     "ly_do": "Thiếu 2 hộp"}])
		self.assertEqual(kq["trang_thai"], kh.TT_CHO_XU_LY)
		self.assertFalse(kq["co_hang_hong"])

	def test_sl_thieu_duoc_suy_ra_khong_luu_thanh_field(self):
		dn = self._dn()
		self._gui(dn, [{"item_code": ITEM, "sl_nhan": 6, "sl_tra": 1,
		                "ly_do": "1 hỏng, 3 thiếu"}])
		self._nhu_khach()
		try:
			bb = api.portal_kiem_hang_get(dn.name)["bien_ban"]
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(bb["items"][0]["sl_thieu"], 3)


class TestKiemHangCachLy(_KiemHangBase):
	def test_khong_kiem_duoc_phieu_giao_cua_khach_khac(self):
		dn = self._dn(customer=KHACH_KHAC)
		self._nhu_khach(USER_MOI)
		try:
			with self.assertRaises(frappe.PermissionError):
				api.portal_kiem_hang_get(dn.name)
			with self.assertRaises(frappe.PermissionError):
				api.portal_kiem_hang_gui(
					dn.name, [{"item_code": ITEM, "sl_nhan": 10}]
				)
		finally:
			frappe.set_user("Administrator")

	def test_phieu_giao_khong_ton_tai_tra_cung_mot_loi(self):
		"""Không để người gọi dò được sự tồn tại của chứng từ khách khác."""
		self._nhu_khach()
		try:
			with self.assertRaises(frappe.PermissionError):
				api.portal_kiem_hang_get("MAT-DN-KHONG-CO-THAT")
		finally:
			frappe.set_user("Administrator")

	def test_phieu_giao_con_nhap_khong_kiem_duoc(self):
		dn = self._dn(submit=False)
		self._nhu_khach()
		try:
			with self.assertRaises(frappe.ValidationError):
				api.portal_kiem_hang_get(dn.name)
		finally:
			frappe.set_user("Administrator")

	def test_gui_lan_hai_tren_cung_phieu_giao_bi_chan(self):
		dn = self._dn()
		self._gui(dn, [{"item_code": ITEM, "sl_nhan": 10}])
		self._nhu_khach()
		try:
			with self.assertRaises(frappe.ValidationError):
				api.portal_kiem_hang_gui(
					dn.name, [{"item_code": ITEM, "sl_nhan": 9, "sl_tra": 0,
					           "ly_do": "đổi ý"}]
				)
		finally:
			frappe.set_user("Administrator")

	def test_luu_nhap_nhieu_lan_chi_sinh_mot_bien_ban(self):
		dn = self._dn()
		self._nhu_khach()
		try:
			a = api.portal_kiem_hang_luu(dn.name, [{"item_code": ITEM, "sl_nhan": 10}])
			b = api.portal_kiem_hang_luu(dn.name, [{"item_code": ITEM, "sl_nhan": 9,
			                                        "sl_tra": 1, "ly_do": "vỡ"}])
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(a["name"], b["name"])
		self.assertEqual(
			frappe.db.count("Portal Delivery Inspection", {"delivery_note": dn.name}), 1
		)


class TestKiemHangVaiNhanVien(_KiemHangBase):
	def _bien_ban_hong(self, sl_tra=3):
		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 10 - sl_tra,
		                     "sl_tra": sl_tra, "ly_do": "Vỡ khi vận chuyển"}])
		return dn, frappe.get_doc("Portal Delivery Inspection", kq["name"])

	def test_duyet_tra_sinh_phieu_tra_hang_nhap_dung_so_luong(self):
		dn, bb = self._bien_ban_hong(3)
		frappe.set_user(self.staff)
		try:
			kq = kh.kiem_hang_duyet_tra(bb.name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(kq["trang_thai"], kh.TT_DA_DUYET_TRA)
		tra = frappe.get_doc("Delivery Note", kq["phieu_tra_hang"])
		# NHÁP, không submit hộ: tồn kho Miyano chỉ được cộng lại khi hàng về
		# thật (spec §4.5).
		self.assertEqual(tra.docstatus, 0)
		self.assertTrue(tra.is_return)
		self.assertEqual(tra.return_against, dn.name)
		self.assertEqual(len(tra.items), 1)
		self.assertEqual(tra.items[0].item_code, ITEM)
		self.assertEqual(float(tra.items[0].qty), -3)

	def test_duyet_tra_chi_giu_dong_hong(self):
		dn = self._dn([
			{"item_code": ITEM, "qty": 10, "rate": 95000},
			{"item_code": ITEM_2, "qty": 5, "rate": 12000},
		])
		kq = self._gui(dn, [
			{"item_code": ITEM, "sl_nhan": 8, "sl_tra": 2, "ly_do": "Vỡ"},
			{"item_code": ITEM_2, "sl_nhan": 5, "sl_tra": 0},
		])
		frappe.set_user(self.staff)
		try:
			r = kh.kiem_hang_duyet_tra(kq["name"])
		finally:
			frappe.set_user("Administrator")
		tra = frappe.get_doc("Delivery Note", r["phieu_tra_hang"])
		self.assertEqual([i.item_code for i in tra.items], [ITEM])

	def test_duyet_tra_khi_khong_co_hang_hong_bi_chan(self):
		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 8, "sl_tra": 0,
		                     "ly_do": "Thiếu"}])
		frappe.set_user(self.staff)
		try:
			with self.assertRaises(frappe.ValidationError):
				kh.kiem_hang_duyet_tra(kq["name"])
		finally:
			frappe.set_user("Administrator")

	def test_khach_khong_tu_duyet_duoc_bien_ban_cua_minh(self):
		"""Cổng khách không có đường tới hàm này, nhưng hàm vẫn phải tự đứng
		vững — nó là `@frappe.whitelist()`, tức gọi được qua HTTP."""
		dn, bb = self._bien_ban_hong()
		self._nhu_khach()
		try:
			with self.assertRaises(frappe.PermissionError):
				kh.kiem_hang_duyet_tra(bb.name)
		finally:
			frappe.set_user("Administrator")

	def test_tu_choi_bat_buoc_co_ly_do(self):
		dn, bb = self._bien_ban_hong()
		frappe.set_user(self.staff)
		try:
			with self.assertRaises(frappe.ValidationError):
				kh.kiem_hang_tu_choi(bb.name, "  ")
			kq = kh.kiem_hang_tu_choi(bb.name, "Hàng đã ký nhận nguyên vẹn")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(kq["trang_thai"], kh.TT_TU_CHOI)
		self.assertEqual(
			frappe.db.get_value("Portal Delivery Inspection", bb.name, "ly_do_tu_choi"),
			"Hàng đã ký nhận nguyên vẹn",
		)

	def test_da_xu_ly_dong_bien_ban_chi_thieu_hang(self):
		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 8, "sl_tra": 0,
		                     "ly_do": "Thiếu 2"}])
		frappe.set_user(self.staff)
		try:
			r = kh.kiem_hang_da_xu_ly(kq["name"], "Đã giao bù ngày mai")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(r["trang_thai"], kh.TT_DA_XU_LY)

	def test_submit_phieu_tra_hang_day_bien_ban_sang_da_thu_hoi(self):
		dn, bb = self._bien_ban_hong(3)
		frappe.set_user(self.staff)
		try:
			kq = kh.kiem_hang_duyet_tra(bb.name)
		finally:
			frappe.set_user("Administrator")
		tra = frappe.get_doc("Delivery Note", kq["phieu_tra_hang"])
		tra.submit()
		self.assertEqual(
			frappe.db.get_value("Portal Delivery Inspection", bb.name, "trang_thai"),
			kh.TT_DA_THU_HOI,
		)

	def test_huy_bien_ban_da_co_phieu_tra_bi_chan(self):
		"""Huỷ ở đây để lại một phiếu trả hàng mồ côi — kho Miyano nhìn vào
		không biết còn phải thu hồi hay không."""
		dn, bb = self._bien_ban_hong()
		frappe.set_user(self.staff)
		try:
			kh.kiem_hang_duyet_tra(bb.name)
		finally:
			frappe.set_user("Administrator")
		bb.reload()
		with self.assertRaises(frappe.ValidationError):
			bb.cancel()


class TestKiemHangHienTrenDonHang(_KiemHangBase):
	def test_order_track_tra_trang_thai_kiem_hang_va_hoa_don_cua_don(self):
		so = frappe.new_doc("Sales Order")
		so.company = COMPANY
		so.customer = self.customer
		so.transaction_date = frappe.utils.today()
		so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 3)
		so.append("items", {
			"item_code": ITEM, "qty": 10, "rate": 95000,
			"warehouse": KHO_MYN, "delivery_date": so.delivery_date,
			"cost_center": COST_CENTER,
		})
		so.insert(ignore_permissions=True)
		so.submit()

		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
		dn = make_delivery_note(so.name)
		dn.company = COMPANY
		for r in dn.items:
			r.warehouse = KHO_MYN
			r.cost_center = COST_CENTER
		dn.insert(ignore_permissions=True)
		dn.submit()

		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
		si = make_sales_invoice(so.name)
		si.insert(ignore_permissions=True)
		si.submit()

		self._gui(dn, [{"item_code": ITEM, "sl_nhan": 7, "sl_tra": 3,
		                "ly_do": "Vỡ 3"}])

		self._nhu_khach()
		try:
			d = api.portal_order_track(so.name)
		finally:
			frappe.set_user("Administrator")

		dot = [x for x in d["deliveries"] if x["name"] == dn.name][0]
		self.assertIsNotNone(dot["kiem_hang"])
		self.assertEqual(dot["kiem_hang"]["trang_thai"], kh.TT_CHO_XU_LY)
		self.assertTrue(dot["kiem_hang"]["co_hang_hong"])

		# Khoảng trống 2026-08-16: đơn phải chỉ thẳng tới hoá đơn CỦA NÓ.
		self.assertEqual([h["name"] for h in d["hoa_don"]], [si.name])
		self.assertEqual(d["hoa_don"][0]["tong_tien"], float(si.grand_total))


class TestKiemHangThongBaoNoiBo(_KiemHangBase):
	"""Phát hiện trong UAT 2026-08-16 — khiếu nại rơi vào im lặng.

	Khách hàng không có `account_manager` (Bệnh viện Bạch Mai trên site thật là
	một ví dụ) thì `_sales_phu_trach` trả None và bản đầu của
	`bao_kiem_hang_co_van_de` lặng lẽ `return False`: khách gửi biên bản báo
	hàng hỏng, không nhân viên Miyano nào biết, và không có gì đỏ lên.
	"""

	def test_khach_khong_co_account_manager_van_bao_duoc_sales_manager(self):
		frappe.db.set_value("Customer", self.customer, "account_manager", None)
		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 7, "sl_tra": 3,
		                     "ly_do": "Vỡ 3"}])
		nhan = frappe.get_all("Notification Log", filters={
			"document_type": "Portal Delivery Inspection",
			"document_name": kq["name"],
			"subject": ["like", "Portal - Kiểm hàng có vấn đề%"],
		}, pluck="for_user")
		self.assertTrue(
			nhan,
			"Biên bản có hàng hỏng mà KHÔNG ai trong Miyano nhận được thông báo.",
		)
		# Người nhận phải là người LÀM ĐƯỢC gì đó với biên bản này.
		for u in nhan:
			self.assertIn(
				"Sales Manager",
				[r.role for r in frappe.get_doc("User", u).roles],
				f"{u} nhận cảnh báo nhưng không có quyền duyệt/từ chối biên bản.",
			)

	def test_co_account_manager_thi_chi_bao_dung_nguoi_do(self):
		"""Đường lui CHỈ dùng khi không có ai phụ trách — không gửi song song,
		một khiếu nại không cần cả phòng cùng đọc."""
		frappe.db.set_value("Customer", self.customer, "account_manager", self.staff)
		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 7, "sl_tra": 3,
		                     "ly_do": "Vỡ 3"}])
		nhan = frappe.get_all("Notification Log", filters={
			"document_type": "Portal Delivery Inspection",
			"document_name": kq["name"],
			"subject": ["like", "Portal - Kiểm hàng có vấn đề%"],
		}, pluck="for_user")
		self.assertEqual(nhan, [self.staff])

	def test_nhan_du_thi_khong_lam_phien_ai(self):
		frappe.db.set_value("Customer", self.customer, "account_manager", self.staff)
		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 10, "sl_tra": 0}])
		self.assertFalse(frappe.get_all("Notification Log", filters={
			"document_type": "Portal Delivery Inspection",
			"document_name": kq["name"],
		}))


class TestKiemHangDuLieuThat(_KiemHangBase):
	"""Ba lỗ hổng chỉ nổ trên hình dạng dữ liệu THẬT, không nổ trên fixture
	một-dòng-một-mã của các class trên (review 2026-08-16)."""

	def test_tra_hang_phan_bo_qua_nhieu_dong_cung_ma(self):
		"""Miyano xuất theo lô nên một mã thường nằm trên nhiều dòng phiếu
		giao. Dồn toàn bộ SL trả vào dòng ĐẦU TIÊN sẽ vượt SL của chính dòng
		đó và bị `validate_returned_qty` của ERPNext chặn — lỗi chỉ xuất hiện
		khi số trả lớn hơn dòng đầu."""
		dn = self._dn([
			{"item_code": ITEM, "qty": 4, "rate": 95000},
			{"item_code": ITEM, "qty": 6, "rate": 95000},
		])
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 3, "sl_tra": 7,
		                     "ly_do": "Vỡ 7 hộp"}])
		frappe.set_user(self.staff)
		try:
			r = kh.kiem_hang_duyet_tra(kq["name"])
		finally:
			frappe.set_user("Administrator")

		tra = frappe.get_doc("Delivery Note", r["phieu_tra_hang"])
		self.assertEqual(
			sum(float(i.qty) for i in tra.items), -7,
			"Tổng SL trên phiếu trả phải đúng bằng số khách báo hỏng.",
		)
		for i in tra.items:
			self.assertLessEqual(
				abs(float(i.qty)), 6,
				"Không dòng nào được mang SL trả vượt SL nó đã giao.",
			)

	def test_bi_tu_choi_thi_khach_gui_lai_duoc(self):
		"""spec §4.3 hứa khách có đường lùi sau khi bị từ chối. Bản bị từ chối
		vẫn là docstatus=1, nên nếu `_chan_da_gui` không loại nó ra thì khách
		đọc "Liên hệ Miyano" trên một màn khoá cứng và hết đường."""
		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 7, "sl_tra": 3,
		                     "ly_do": "Vỡ 3"}])
		frappe.set_user(self.staff)
		try:
			kh.kiem_hang_tu_choi(kq["name"], "Biên bản ký nhận ghi nguyên vẹn")
		finally:
			frappe.set_user("Administrator")

		self._nhu_khach()
		try:
			d = api.portal_kiem_hang_get(dn.name)
			self.assertTrue(
				d["bien_ban"]["co_the_gui_lai"],
				"Cổng phải báo cho client biết còn đường gửi lại.",
			)
			self.assertEqual(len(d["dong_goc"]), 1, "Phải trả kèm dòng gốc để gõ lại.")
			moi = api.portal_kiem_hang_gui(
				dn.name,
				[{"item_code": ITEM, "sl_nhan": 8, "sl_tra": 2, "ly_do": "Đếm lại: 2 hỏng"}],
			)
			# Khách phải thấy BẢN MỚI, không phải bản đã bị từ chối.
			sau = api.portal_kiem_hang_get(dn.name)
		finally:
			frappe.set_user("Administrator")

		self.assertNotEqual(moi["name"], kq["name"])
		self.assertEqual(sau["bien_ban"]["name"], moi["name"])
		self.assertEqual(sau["bien_ban"]["trang_thai"], kh.TT_CHO_XU_LY)
		# Bản bị từ chối GIỮ NGUYÊN làm lịch sử của cuộc trao đổi.
		self.assertEqual(
			frappe.db.get_value("Portal Delivery Inspection", kq["name"], "trang_thai"),
			kh.TT_TU_CHOI,
		)

	def test_dong_giu_cho_khong_bao_gio_hien_tren_man_kiem_hang(self):
		"""C-1 (2015-08-15) lặp lại đúng hình dạng cũ: ba lối ra đã gác,
		lối VÀO thì chưa. `kiem_khong_con_dong_giu_cho` chặn Sales Order mang
		dòng giữ chỗ, nhưng một Delivery Note lập TAY trên Desk không đi qua
		chốt đó."""
		from miyano_portal.portal_mua_le import ITEM_GIU_CHO

		if not frappe.db.exists("Item", ITEM_GIU_CHO):
			self.skipTest(f"Site chưa có {ITEM_GIU_CHO}")
		dn = self._dn([
			{"item_code": ITEM, "qty": 10, "rate": 95000},
			{"item_code": ITEM_GIU_CHO, "qty": 1, "rate": 0},
		])
		self._nhu_khach()
		try:
			items = api.portal_kiem_hang_get(dn.name)["bien_ban"]["items"]
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(
			[i["item_code"] for i in items], [ITEM],
			f"{ITEM_GIU_CHO} là chi tiết kỹ thuật nội bộ, khách không được thấy.",
		)

	def test_kiem_hang_chay_tren_don_MUA_LE_that(self):
		"""Chủ đầu tư yêu cầu kiểm hàng cho CẢ hai chế độ đặt hàng. Mọi test
		trên đây dựng phiếu giao bằng tay hoặc từ đơn thường — chưa cái nào đi
		qua `_xay_don_ban_le`, tức đường mà đơn mua lẻ THẬT đi."""
		from miyano_portal.portal_mua_le import ITEM_GIU_CHO

		# BR-R1 — cờ cho phép mua lẻ. Bật tường minh trong test thay vì dựa
		# vào giá trị mặc định của patch: một fixture dựa vào mặc định là một
		# fixture sẽ đỏ vào ngày sales tắt cờ cho một khách nào đó.
		frappe.db.set_value("Customer", self.customer, "custom_cho_phep_mua_le", 1)
		self._nhu_khach()
		try:
			dat = api.portal_order_place(
				items=[{"item_code": ITEM, "qty": 4}],
				mode="ban_le",
				request_id=frappe.generate_hash(length=12),
				delivery_date=frappe.utils.add_days(frappe.utils.today(), 5),
				dat_ngoai=[{"ten_hang": "Kẹp mạch máu cỡ S", "dvt": "Cái", "so_luong": 2}],
			)
		finally:
			frappe.set_user("Administrator")
		so = frappe.get_doc("Sales Order", dat["sales_order"])
		self.assertEqual(so.get("custom_loai_don"), "Mua lẻ")

		# Nhân viên chốt giá rồi xác nhận đơn — đường đi thật của một đơn lẻ.
		for r in so.items:
			if r.item_code != ITEM_GIU_CHO:
				r.rate = 95000
		# Task 13 (QĐ-G13) — KHÔNG còn dựng TAY dòng hàng cho dòng đặt ngoài,
		# và KHÔNG còn tự tay tick `da_xu_ly`: khớp mã là hệ thống tự CHUYỂN
		# dòng gõ tay thành dòng hàng thật, tự gỡ dòng giữ chỗ (bẫy 3) và tự
		# bật `da_xu_ly` (QĐ-G16). Giữ nguyên đoạn dựng tay của bản cũ sẽ
		# ĐẾM ĐÔI số lượng (2 dòng tay + 2 dòng chuyển = 4), và biên bản kiểm
		# hàng bên dưới báo "giao 4, nhận tốt 2" — đúng cái đỏ đã bắt được.
		for d in (so.get("custom_dat_ngoai") or []):
			d.item_khop = ITEM_2
		so.flags.ignore_permissions = True
		so.save()
		so.reload()
		self.assertNotIn(
			ITEM_GIU_CHO, [r.item_code for r in so.items],
			"khớp mã xong thì dòng giữ chỗ phải tự biến mất (Task 13, bẫy 3)",
		)
		for r in so.items:
			if r.item_code == ITEM_2:
				# Miyano chốt giá cho dòng vừa chuyển (mã này ngoài hợp đồng
				# của khách thử nghiệm nên tới đây `rate = 0`, đúng tầng 2).
				r.rate = 12000
				r.cost_center = COST_CENTER
		so.save(ignore_permissions=True)
		so.submit()

		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
		dn = make_delivery_note(so.name)
		dn.company = COMPANY
		for r in dn.items:
			r.warehouse = KHO_MYN
			r.cost_center = COST_CENTER
		dn.insert(ignore_permissions=True)
		dn.submit()

		self._nhu_khach()
		try:
			d = api.portal_kiem_hang_get(dn.name)
		finally:
			frappe.set_user("Administrator")
		ma = sorted(i["item_code"] for i in d["bien_ban"]["items"])
		self.assertEqual(ma, sorted([ITEM, ITEM_2]))
		self.assertNotIn(ITEM_GIU_CHO, ma)

		kq = self._gui(dn, [
			{"item_code": ITEM, "sl_nhan": 3, "sl_tra": 1, "ly_do": "Rách bao"},
			{"item_code": ITEM_2, "sl_nhan": 2, "sl_tra": 0},
		])
		self.assertEqual(kq["trang_thai"], kh.TT_CHO_XU_LY)
		self.assertTrue(kq["co_hang_hong"])


class TestKiemHangHangThieuVaHenGiao(_KiemHangBase):
	"""Vai NHÂN VIÊN, 2026-08-16 — trả lời khách về hàng thiếu.

	Điểm phải chốt: một biên bản VỪA có hàng hỏng VỪA thiếu hàng. Bản trước
	gộp cả hai vào `trang_thai`, nên `kiem_hang_duyet_tra` đẩy sang "Đã duyệt
	trả" là nửa THIẾU thành vô hình — cổng xử lý nó chỉ mở ở "Chờ xử lý", và
	không ai trả lời khách được nữa. Không test nào của bản trước chạm tới
	trường hợp hỗn hợp này.
	"""

	def _don_giao_thieu(self, sl_nhan=6, sl_tra=0):
		"""Đơn THẬT → phiếu giao → biên bản báo thiếu (và hỏng nếu sl_tra>0)."""
		so = frappe.new_doc("Sales Order")
		so.company = COMPANY
		so.customer = self.customer
		so.transaction_date = frappe.utils.today()
		so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 3)
		so.append("items", {
			"item_code": ITEM, "qty": 10, "rate": 95000,
			"warehouse": KHO_MYN, "cost_center": COST_CENTER,
			"delivery_date": frappe.utils.getdate(so.delivery_date),
		})
		so.insert(ignore_permissions=True)
		so.submit()

		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
		dn = make_delivery_note(so.name)
		dn.company = COMPANY
		for r in dn.items:
			r.warehouse = KHO_MYN
			r.cost_center = COST_CENTER
		dn.insert(ignore_permissions=True)
		dn.submit()

		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": sl_nhan, "sl_tra": sl_tra,
		                     "ly_do": "Thiếu/hỏng khi nhận"}])
		return so, dn, frappe.get_doc("Portal Delivery Inspection", kq["name"])

	def test_bien_ban_vua_hong_vua_thieu_van_tra_loi_duoc_phan_thieu(self):
		so, dn, bb = self._don_giao_thieu(sl_nhan=6, sl_tra=2)  # 10 giao, 2 hỏng, 2 thiếu
		self.assertTrue(bb.co_hang_hong)
		self.assertTrue(bb.co_thieu_hang())

		frappe.set_user(self.staff)
		try:
			kh.kiem_hang_duyet_tra(bb.name)
			bb.reload()
			self.assertEqual(bb.trang_thai, kh.TT_DA_DUYET_TRA)
			# ĐÂY là chỗ bản trước chết: cổng xử lý hàng thiếu khoá theo
			# `trang_thai`, mà `trang_thai` giờ thuộc về luồng trả hàng.
			kq = kh.kiem_hang_hen_giao(
				bb.name, frappe.utils.add_days(frappe.utils.today(), 5),
				"Sẽ giao bù", "Hàng về kho ngày 5 tới",
			)
		finally:
			frappe.set_user("Administrator")

		bb.reload()
		self.assertEqual(bb.xu_ly_thieu, "Sẽ giao bù")
		self.assertEqual(kq["loai"], "Sẽ giao bù")
		# Luồng trả hàng KHÔNG bị lời hẹn giao đụng vào.
		self.assertEqual(bb.trang_thai, kh.TT_DA_DUYET_TRA)

	def test_giao_bu_khong_doi_ngay_cam_ket_goc(self):
		so, dn, bb = self._don_giao_thieu(sl_nhan=7)
		ngay_goc = frappe.get_doc("Sales Order", so.name).delivery_date
		hen = frappe.utils.add_days(frappe.utils.today(), 9)
		frappe.set_user(self.staff)
		try:
			kh.kiem_hang_hen_giao(bb.name, hen, "Sẽ giao bù", "Chờ hàng nhập khẩu")
		finally:
			frappe.set_user("Administrator")
		so.reload()
		self.assertEqual(so.delivery_date, ngay_goc,
		                 "«Sẽ giao bù» phải GIỮ ngày cam kết gốc — đó là lịch sử.")
		self.assertEqual(str(so.custom_ngay_hen_giao), str(frappe.utils.getdate(hen)))

	def test_doi_ngay_giao_cap_nhat_ca_don_va_tung_dong(self):
		"""Đổi mỗi header là để lại một đơn 'trễ hạn' vĩnh viễn trên mọi báo
		cáo giao hàng của ERPNext — chúng đọc `Sales Order Item.delivery_date`."""
		so, dn, bb = self._don_giao_thieu(sl_nhan=7)
		hen = frappe.utils.add_days(frappe.utils.today(), 12)
		frappe.set_user(self.staff)
		try:
			kh.kiem_hang_hen_giao(bb.name, hen, "Đã đổi ngày giao", "Khách đồng ý dời")
		finally:
			frappe.set_user("Administrator")
		so.reload()
		self.assertEqual(so.delivery_date, frappe.utils.getdate(hen))
		for r in so.items:
			self.assertEqual(r.delivery_date, frappe.utils.getdate(hen))

	def test_khach_thay_loi_hen_tren_chi_tiet_don(self):
		so, dn, bb = self._don_giao_thieu(sl_nhan=7)
		hen = frappe.utils.add_days(frappe.utils.today(), 6)
		frappe.set_user(self.staff)
		try:
			kh.kiem_hang_hen_giao(bb.name, hen, "Sẽ giao bù", "Nhà cung cấp giao chậm")
		finally:
			frappe.set_user("Administrator")

		self._nhu_khach()
		try:
			d = api.portal_order_track(so.name)
			bb_khach = api.portal_kiem_hang_get(dn.name)["bien_ban"]
		finally:
			frappe.set_user("Administrator")
		self.assertIsNotNone(d["hen_giao"])
		self.assertEqual(d["hen_giao"]["loai"], "Sẽ giao bù")
		self.assertEqual(d["hen_giao"]["ngay"], str(frappe.utils.getdate(hen)))
		self.assertEqual(bb_khach["xu_ly_thieu"], "Sẽ giao bù")

	def test_khach_nhan_thong_bao_moi_lan_hen_lai(self):
		"""Hẹn lại lần hai là một tin khách CẦN biết — chống trùng theo tên
		đơn sẽ nuốt mất nó, đúng con số khách đang chờ."""
		from miyano_portal.portal_hen_giao import hen_giao_lai

		so, dn, bb = self._don_giao_thieu(sl_nhan=7)
		frappe.set_user(self.staff)
		try:
			hen_giao_lai(so.name, frappe.utils.add_days(frappe.utils.today(), 5),
			             "Sẽ giao bù", "Lần một: chờ hàng")
			hen_giao_lai(so.name, frappe.utils.add_days(frappe.utils.today(), 15),
			             "Sẽ giao bù", "Lần hai: hàng vẫn chưa về")
		finally:
			frappe.set_user("Administrator")
		bao = frappe.get_all("Notification Log", filters={
			"document_type": "Sales Order", "document_name": so.name,
			"subject": ["like", "Portal - Hẹn lịch giao%"],
		}, pluck="subject")
		self.assertEqual(len(bao), 2, f"Phải có 2 thông báo, đang có: {bao}")

	def test_khong_hen_giao_lai_vao_qua_khu(self):
		so, dn, bb = self._don_giao_thieu(sl_nhan=7)
		frappe.set_user(self.staff)
		try:
			with self.assertRaises(frappe.ValidationError):
				kh.kiem_hang_hen_giao(
					bb.name, frappe.utils.add_days(frappe.utils.today(), -1),
					"Sẽ giao bù", "ngày quá khứ",
				)
		finally:
			frappe.set_user("Administrator")

	def test_khong_xu_ly_phan_thieu_hai_lan(self):
		so, dn, bb = self._don_giao_thieu(sl_nhan=7)
		frappe.set_user(self.staff)
		try:
			kh.kiem_hang_hen_giao(bb.name, frappe.utils.add_days(frappe.utils.today(), 5),
			                      "Sẽ giao bù", "Lần một")
			with self.assertRaises(frappe.ValidationError):
				kh.kiem_hang_da_xu_ly(bb.name, "đổi ý")
		finally:
			frappe.set_user("Administrator")

	def test_bien_ban_khong_thieu_hang_thi_khong_hen_giao_duoc(self):
		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 7, "sl_tra": 3,
		                     "ly_do": "Hỏng cả 3"}])  # 7+3=10, không thiếu
		frappe.set_user(self.staff)
		try:
			with self.assertRaises(frappe.ValidationError):
				kh.kiem_hang_hen_giao(kq["name"], frappe.utils.add_days(frappe.utils.today(), 5),
				                      "Sẽ giao bù", "không có gì thiếu")
		finally:
			frappe.set_user("Administrator")

	def test_chi_thieu_hang_dong_lai_thi_trang_thai_ve_da_xu_ly(self):
		so, dn, bb = self._don_giao_thieu(sl_nhan=7)
		frappe.set_user(self.staff)
		try:
			kh.kiem_hang_da_xu_ly(bb.name, "Đã giảm trừ công nợ")
		finally:
			frappe.set_user("Administrator")
		bb.reload()
		self.assertEqual(bb.xu_ly_thieu, "Không giao bù")
		self.assertEqual(bb.trang_thai, kh.TT_DA_XU_LY)


class TestHangTraVeVaoKhoRieng(_KiemHangBase):
	"""QĐ chủ đầu tư 2026-08-16 — hàng hỏng trả về KHÔNG lẫn vào tồn bán được.

	Với vật tư y tế đây là khác biệt có thật: `make_return_doc` chép nguyên kho
	của dòng gốc, tức bơm tiêm gãy kim quay lại đúng kho đang bán.
	"""

	def test_phieu_tra_hang_ghi_vao_kho_hang_tra_ve_cung_cong_ty(self):
		from miyano_portal.kho_hang_tra_ve import dam_bao_kho

		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 7, "sl_tra": 3,
		                     "ly_do": "Vỡ 3"}])
		frappe.set_user(self.staff)
		try:
			r = kh.kiem_hang_duyet_tra(kq["name"])
		finally:
			frappe.set_user("Administrator")

		tra = frappe.get_doc("Delivery Note", r["phieu_tra_hang"])
		kho_mong_doi = dam_bao_kho(tra.company)
		self.assertTrue(kho_mong_doi)
		for row in tra.items:
			self.assertEqual(
				row.warehouse, kho_mong_doi,
				"Hàng hỏng trả về phải vào kho «Hàng trả về», không phải kho bán được.",
			)
		self.assertEqual(
			frappe.db.get_value("Warehouse", kho_mong_doi, "company"), tra.company,
			"Kho trả về phải CÙNG công ty với phiếu giao — site có hai pháp nhân.",
		)

	def test_ghi_so_phieu_tra_hang_cong_ton_vao_kho_tra_ve(self):
		"""«Làm nhập kho và ghi nhận vào kho» của nhân viên CHÍNH LÀ việc ghi
		sổ phiếu trả hàng — test này chốt rằng tồn thật sự đổi, và đổi ở đúng
		kho."""
		from erpnext.stock.utils import get_stock_balance
		from miyano_portal.kho_hang_tra_ve import dam_bao_kho

		dn = self._dn()
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 7, "sl_tra": 3,
		                     "ly_do": "Vỡ 3"}])
		frappe.set_user(self.staff)
		try:
			r = kh.kiem_hang_duyet_tra(kq["name"])
		finally:
			frappe.set_user("Administrator")

		tra = frappe.get_doc("Delivery Note", r["phieu_tra_hang"])
		kho_tra = dam_bao_kho(tra.company)
		truoc = get_stock_balance(ITEM, kho_tra)
		ban_duoc_truoc = get_stock_balance(ITEM, KHO_MYN)
		tra.submit()
		self.assertEqual(get_stock_balance(ITEM, kho_tra), truoc + 3)
		self.assertEqual(
			get_stock_balance(ITEM, KHO_MYN), ban_duoc_truoc,
			"Tồn kho BÁN ĐƯỢC không được đổi khi thu hồi hàng hỏng.",
		)


ITEM_LO = "MYNTEST-KH-LO"
LOT_KH = "LOTTEST-KIEMHANG-A"


class TestTraHangTheoLo(_KiemHangBase):
	"""Hàng theo LÔ là mặc định của một nhà phân phối vật tư y tế, không phải
	trường hợp biên — `delivery_hook._lo_cua_dong()` tồn tại vì thế.

	`make_return_doc` chép cả `serial_and_batch_bundle` của dòng gốc, mà bundle
	đó mang kho RIÊNG trỏ về kho xuất. Đổi `row.warehouse` sang kho «Hàng trả
	về» mà không đụng bundle thì ERPNext chặn lúc ghi sổ — và hàng hỏng không
	bao giờ về được kho nào.
	"""

	def setUp(self):
		super().setUp()
		self._vat_tu_co_lo()

	def _vat_tu_co_lo(self):
		if not frappe.db.exists("Item", ITEM_LO):
			frappe.get_doc({
				"doctype": "Item", "item_code": ITEM_LO,
				"item_name": "Vật tư test kiểm hàng theo lô",
				"item_group": frappe.get_all(
					"Item Group", filters={"is_group": 0}, pluck="name"
				)[0],
				"stock_uom": "Hộp", "is_stock_item": 1,
				"has_batch_no": 1, "create_new_batch": 0,
			}).insert(ignore_permissions=True)
		if not frappe.db.exists("Batch", LOT_KH):
			frappe.get_doc({
				"doctype": "Batch", "batch_id": LOT_KH,
				"item": ITEM_LO, "expiry_date": "2028-12-31",
			}).insert(ignore_permissions=True)
		make_stock_entry(
			item_code=ITEM_LO, qty=50, to_warehouse=KHO_MYN, rate=1000,
			batch_no=LOT_KH, company=COMPANY, purpose="Material Receipt",
		)

	def _dn_co_lo(self, qty=10):
		dn = frappe.new_doc("Delivery Note")
		dn.company = COMPANY
		dn.customer = self.customer
		dn.posting_date = frappe.utils.today()
		dn.append("items", {
			"item_code": ITEM_LO, "qty": qty, "rate": 95000,
			"warehouse": KHO_MYN, "cost_center": COST_CENTER,
			"batch_no": LOT_KH, "use_serial_batch_fields": 1,
		})
		dn.insert(ignore_permissions=True)
		dn.submit()
		return dn

	def test_tra_hang_theo_lo_ghi_so_duoc_vao_kho_hang_tra_ve(self):
		from erpnext.stock.utils import get_stock_balance
		from miyano_portal.kho_hang_tra_ve import dam_bao_kho

		dn = self._dn_co_lo(10)
		kq = self._gui(dn, [{"item_code": ITEM_LO, "sl_nhan": 7, "sl_tra": 3,
		                     "ly_do": "Vỡ 3 hộp"}])
		frappe.set_user(self.staff)
		try:
			r = kh.kiem_hang_duyet_tra(kq["name"])
		finally:
			frappe.set_user("Administrator")

		tra = frappe.get_doc("Delivery Note", r["phieu_tra_hang"])
		kho_tra = dam_bao_kho(tra.company)
		truoc = get_stock_balance(ITEM_LO, kho_tra)
		# ĐÂY là bước bản trước chưa bao giờ chạy trên hàng có lô.
		tra.submit()
		self.assertEqual(get_stock_balance(ITEM_LO, kho_tra), truoc + 3)
		for row in tra.items:
			self.assertEqual(row.warehouse, kho_tra)


class TestBannerHenGiaoTuTat(_KiemHangBase):
	"""Một lời hứa ĐÃ GIỮ vẫn treo trên trang đơn của khách như thể còn đang
	chờ — bốn test banner của bản trước đều chỉ chốt nó HIỆN RA, không cái nào
	chốt nó TẮT ĐI."""

	def _don_da_giao(self):
		so = frappe.new_doc("Sales Order")
		so.company = COMPANY
		so.customer = self.customer
		so.transaction_date = frappe.utils.today()
		so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 3)
		so.append("items", {
			"item_code": ITEM, "qty": 10, "rate": 95000,
			"warehouse": KHO_MYN, "cost_center": COST_CENTER,
			"delivery_date": frappe.utils.getdate(so.delivery_date),
		})
		so.insert(ignore_permissions=True)
		so.submit()
		return so

	def _giao(self, so, qty=None):
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
		dn = make_delivery_note(so.name)
		dn.company = COMPANY
		for r in dn.items:
			r.warehouse = KHO_MYN
			r.cost_center = COST_CENTER
			if qty is not None:
				r.qty = qty
		dn.insert(ignore_permissions=True)
		dn.submit()
		return dn

	def _hen(self, so, loai="Sẽ giao bù"):
		from miyano_portal.portal_hen_giao import hen_giao_lai
		frappe.set_user(self.staff)
		try:
			return hen_giao_lai(
				so.name, frappe.utils.add_days(frappe.utils.today(), 5),
				loai, "Chờ hàng về kho",
			)
		finally:
			frappe.set_user("Administrator")

	def _banner(self, so):
		from miyano_portal.portal_hen_giao import hen_giao_cua_don
		return hen_giao_cua_don(frappe.get_doc("Sales Order", so.name))

	def test_giao_xong_thi_loi_hen_thoi_hien(self):
		so = self._don_da_giao()
		self._giao(so, qty=6)
		self._hen(so)
		self.assertIsNotNone(self._banner(so), "Chưa giao bù thì lời hẹn phải còn.")
		self._giao(so, qty=4)
		self.assertIsNone(
			self._banner(so),
			"Đã giao sau lời hẹn mà banner vẫn treo — khách đọc một lời hứa đã giữ "
			"như thể còn đang chờ.",
		)

	def test_phieu_TRA_HANG_khong_lam_tat_loi_hen(self):
		"""`make_return_doc` chép nguyên `against_sales_order`. Không loại
		`is_return` ra thì việc thu hồi hàng hỏng sẽ tự tắt đúng cái lời hẹn
		giao bù được lập RA vì phần hàng hỏng đó."""
		so = self._don_da_giao()
		dn = self._giao(so)
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 7, "sl_tra": 3,
		                     "ly_do": "Vỡ 3"}])
		self._hen(so)
		frappe.set_user(self.staff)
		try:
			r = kh.kiem_hang_duyet_tra(kq["name"])
		finally:
			frappe.set_user("Administrator")
		frappe.get_doc("Delivery Note", r["phieu_tra_hang"]).submit()
		self.assertIsNotNone(
			self._banner(so),
			"Thu hồi hàng hỏng KHÔNG phải là đã giao bù.",
		)

	def test_khong_tu_choi_bien_ban_da_lo_hua_lich_giao(self):
		so = self._don_da_giao()
		dn = self._giao(so, qty=6)
		# giao 6: nhận tốt 3 + hỏng 2 → THIẾU 1, mới có phần thiếu để hẹn giao.
		kq = self._gui(dn, [{"item_code": ITEM, "sl_nhan": 3, "sl_tra": 2,
		                     "ly_do": "2 vỡ, 1 không tới"}])
		frappe.set_user(self.staff)
		try:
			kh.kiem_hang_hen_giao(
				kq["name"], frappe.utils.add_days(frappe.utils.today(), 5),
				"Sẽ giao bù", "Giao bù phần thiếu",
			)
			with self.assertRaises(frappe.ValidationError):
				kh.kiem_hang_tu_choi(kq["name"], "Đổi ý, không chấp nhận")
		finally:
			frappe.set_user("Administrator")
