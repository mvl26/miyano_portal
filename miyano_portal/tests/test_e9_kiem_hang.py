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
		so.items = [r for r in so.items if r.item_code != ITEM_GIU_CHO]
		for d in (so.get("custom_dat_ngoai") or []):
			d.da_xu_ly = 1
			d.item_khop = ITEM_2
		so.append("items", {
			"item_code": ITEM_2, "qty": 2, "rate": 12000,
			"warehouse": KHO_MYN, "cost_center": COST_CENTER,
			# `getdate` chứ không phải chuỗi: các dòng do `_xay_don_ban_le`
			# tạo mang `datetime.date`, và `validate_delivery_date` của ERPNext
			# gọi max() trên hỗn hợp str/date sẽ nổ.
			"delivery_date": frappe.utils.getdate(so.delivery_date),
		})
		so.flags.ignore_permissions = True
		so.save()
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
