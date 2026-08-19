"""Task 9 (§12 Q4) — bịt lỗ "sửa số lượng sau khi đã duyệt".

Lỗ hổng đo được trên code TRƯỚC task này: `portal_order_sua_so_luong` chỉ
chặn theo `workflow_state == "Chờ khách đồng ý"`, KHÔNG chặn theo VAI TRÒ.
Sau khi quản lý duyệt 10 hộp và Miyano báo giá, nhân viên khoa gọi được
THẲNG hàm đó và đổi thành 100 hộp — đơn quay về "Chờ xác nhận" mà không ai
duyệt lại. Chủ đầu tư chốt 19/08 (§12 Q4): nhân viên VẪN sửa được, nhưng sửa
xong phải quay lại quản lý duyệt lần nữa — CHỈ khi đổi SỐ LƯỢNG, không phải
khi đồng ý thẳng với báo giá (`portal_order_accept` không được vướng).

Xem `.superpowers/sdd/2026-08-19-de-xuat-mua-nen/task-9-brief.md`.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import de_xuat_duyet, portal_context
from miyano_portal.api import de_xuat, portal
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	SO_LUONG_XIN_SUA_TRONG,
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"
WAREHOUSE = "Stores - MYN"


def _don_phieu_cu():
	"""Bẫy #1 + #2 (brief) — dọn Sales Order test TRƯỚC khi dọn phiếu, và hạ
	trạng thái phiếu cũ về Nháp TRƯỚC KHI `dung_fixture()` force-delete
	(`on_trash` chặn xoá phiếu đã gửi duyệt). Cùng khuôn `test_de_xuat_
	duyet.py::_don_phieu_cu`."""
	for r in frappe.get_all(
		"Sales Order", filters={"customer": ["like", "_TEST DX%"], "docstatus": 0}
	):
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


def _item2():
	"""Vật tư THỨ HAI, riêng của file này (cùng khuôn `test_de_xuat_duyet.py::
	_item2`) — cần cho I2 (review Task 9): xin bỏ MỘT dòng về 0 mà đơn còn
	dòng khác thì mới không vướng chốt "không còn dòng nào" của
	`portal_order_sua_so_luong`."""
	ten = "_TEST DX SUA ITEM 2"
	if not frappe.db.exists("Item", ten):
		frappe.get_doc({
			"doctype": "Item", "item_code": ten, "item_name": ten,
			"item_group": frappe.db.get_value("Item Group", {}, "name"),
			"stock_uom": "Nos", "is_stock_item": 0,
		}).insert(ignore_permissions=True)
	return ten


def _gan_contact_vao_khach(email, customer):
	"""Cùng lý do `test_de_xuat_duyet.py` — `tao_sales_order` cần Contact
	gắn đúng Customer để không ném "Contact Person does not belong to..."."""
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


class TestDeXuatSuaSauDuyet(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.item2 = _item2()
		self.khoa_huyethoc = f.khoa_huyethoc

		self.user_quan_ly = _dam_bao_thanh_vien(
			"dxsua.ql@demo.miyano", self.kh_a, "Quản lý", None
		)
		self.user_huyethoc = _dam_bao_thanh_vien(
			"dxsua.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa",
			self.khoa_huyethoc,
		)

		# Phiếu "Mua lẻ" quản lý đã duyệt 10 hộp — Sales Order sinh ra rồi
		# ép thẳng "Chờ khách đồng ý" để mô phỏng "Miyano đã báo giá xong"
		# (cùng khuôn `frappe.db.set_value(..., update_modified=False)` mà
		# `test_e6_mua_le.py` dùng khắp nơi để dựng fixture ở trạng thái
		# này, không đi qua đường workflow thật của sales).
		# Dòng thứ hai (item2) — cần cho I2 (review Task 9): xin bỏ dòng
		# `self.item` về 0 mà đơn còn `item2` thì mới không vướng chốt "đơn
		# sẽ không còn dòng nào" của `portal_order_sua_so_luong`.
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"loai_don": "Mua lẻ",
			"items": [
				{"item_code": self.item, "so_luong_de_xuat": 10},
				{"item_code": self.item2, "so_luong_de_xuat": 5},
			],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		doc.items[0].so_luong_duyet = 10
		doc.items[1].so_luong_duyet = 5
		doc.save(ignore_permissions=True)
		doc.reload()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, self.user_quan_ly)
		self.don_da_duyet = kq["sales_order"]
		self.phieu_da_duyet = kq["de_xuat"]
		frappe.db.set_value(
			"Sales Order", self.don_da_duyet, "workflow_state",
			"Chờ khách đồng ý", update_modified=False,
		)

		# Đơn CŨ không qua đường đề xuất — chốt tương thích ngược cho sáu
		# tài khoản đang chạy thật (đều là quản lý). `custom_loai_don =
		# "Mua lẻ"` bắt buộc để `portal_order_sua_so_luong` không chặn ở
		# vòng kiểm loại đơn TRƯỚC KHI chạm tới guard Task 9.
		self.don_cu_khong_co_de_xuat = frappe.get_doc({
			"doctype": "Sales Order", "customer": self.kh_a, "company": COMPANY,
			"transaction_date": frappe.utils.today(),
			"delivery_date": frappe.utils.add_days(frappe.utils.today(), 5),
			"selling_price_list": "Standard Selling",
			"custom_loai_don": "Mua lẻ",
			"items": [{"item_code": self.item, "qty": 1, "rate": 0, "warehouse": WAREHOUSE}],
		}).insert(ignore_permissions=True).name
		frappe.db.set_value(
			"Sales Order", self.don_cu_khong_co_de_xuat, "workflow_state",
			"Chờ khách đồng ý", update_modified=False,
		)

		self.dong_moi = {"items": [{"item_code": self.item, "qty": 100}]}

	def tearDown(self):
		frappe.set_user("Administrator")

	# ---- Lỗ hổng chính — chặn theo VAI TRÒ ------------------------------

	def test_nhan_vien_khoa_khong_goi_thang_portal_order_sua_so_luong(self):
		"""Lỗ hổng chính. Chặn theo VAI TRÒ, không chỉ theo workflow_state."""
		frappe.set_user(self.user_huyethoc)
		with self.assertRaises(frappe.PermissionError) as ctx:
			portal.portal_order_sua_so_luong(self.don_da_duyet, self.dong_moi)
		self.assertIn("xin sửa", str(ctx.exception))

	def test_quan_ly_sua_thang_thi_phieu_de_xuat_CUNG_cap_nhat(self):
		"""VẾ DƯƠNG — và phải PHÂN BIỆT ĐƯỢC, không phải một test xanh sẵn.

		Khẳng định đầu (đơn về "Chờ xác nhận") xanh từ trước khi có task này
		nên tự nó không canh gì. Khẳng định thứ hai mới là thứ mới: quản lý
		sửa thẳng thì phiếu đề xuất đứng sau PHẢI đi theo (Step 4b) — nếu
		không, hai chứng từ nói hai số khác nhau và khối truy vết §5.2
		thành vô nghĩa."""
		frappe.set_user(self.user_quan_ly)
		portal.portal_order_sua_so_luong(self.don_da_duyet, self.dong_moi)
		self.assertEqual(
			frappe.db.get_value("Sales Order", self.don_da_duyet, "workflow_state"),
			"Chờ xác nhận",
		)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_da_duyet)
		self.assertEqual(doc.items[0].so_luong_duyet, 100)
		self.assertEqual(doc.trang_thai, "Đã duyệt")

	def test_don_KHONG_qua_duong_de_xuat_thi_giu_nguyen_hanh_vi_cu(self):
		"""Sáu tài khoản đang chạy: đơn cũ không có `custom_de_xuat` →
		không được đổi hành vi. Đây là chốt tương thích ngược — test DUY
		NHẤT trong task này được phép xanh từ đầu."""
		frappe.set_user(self.user_quan_ly)
		portal.portal_order_sua_so_luong(self.don_cu_khong_co_de_xuat, self.dong_moi)
		self.assertEqual(
			frappe.db.get_value(
				"Sales Order", self.don_cu_khong_co_de_xuat, "workflow_state"
			),
			"Chờ xác nhận",
		)

	# ---- Đường xin sửa / duyệt sửa / từ chối sửa ------------------------

	def test_nhan_vien_xin_sua_thi_phieu_ve_cho_duyet_sua(self):
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xin_sua(self.phieu_da_duyet, self.dong_moi)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_da_duyet)
		self.assertEqual(doc.trang_thai, "Chờ duyệt sửa")
		self.assertEqual(doc.items[0].so_luong_xin_sua, 100)
		self.assertEqual(doc.items[0].so_luong_duyet, 10)   # cột cũ CÒN NGUYÊN

	def test_don_chua_doi_gi_truoc_khi_quan_ly_duyet_sua(self):
		"""Chốt của cả task: xin sửa KHÔNG tự nó chạm vào đơn."""
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xin_sua(self.phieu_da_duyet, self.dong_moi)
		so = frappe.get_doc("Sales Order", self.don_da_duyet)
		self.assertEqual(so.items[0].qty, 10)

	def test_quan_ly_duyet_sua_thi_don_moi_doi(self):
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xin_sua(self.phieu_da_duyet, self.dong_moi)
		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_duyet_sua(self.phieu_da_duyet)
		so = frappe.get_doc("Sales Order", self.don_da_duyet)
		self.assertEqual(so.items[0].qty, 100)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_da_duyet)
		self.assertEqual(doc.trang_thai, "Đã duyệt")
		self.assertEqual(doc.items[0].so_luong_duyet, 100)

	def test_nhan_vien_khong_duyet_sua_duoc(self):
		"""VẾ ÂM cần cho `de_xuat_duyet_sua` — chốt quyền `la_quan_ly()`."""
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xin_sua(self.phieu_da_duyet, self.dong_moi)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_duyet_sua(self.phieu_da_duyet)

	def test_quan_ly_tu_choi_sua_thi_don_giu_nguyen(self):
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xin_sua(self.phieu_da_duyet, self.dong_moi)
		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_tu_choi_sua(self.phieu_da_duyet, "Vượt dự toán quý")
		so = frappe.get_doc("Sales Order", self.don_da_duyet)
		self.assertEqual(so.items[0].qty, 10)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_da_duyet)
		self.assertEqual(doc.trang_thai, "Đã duyệt")
		# I2 (review Task 9) — dọn sạch yêu cầu cũ nghĩa là VỀ SENTINEL
		# "chưa có yêu cầu" (SO_LUONG_XIN_SUA_TRONG = -1), KHÔNG phải về 0:
		# 0 tự nó là một giá trị xin sửa hợp lệ (nghĩa "xin bỏ dòng này").
		# assertFalse(-1) sẽ FAIL vì -1 là truthy — đúng ý, ép test này phải
		# khẳng định đúng sentinel thay vì tình cờ đúng với giá trị cũ.
		self.assertEqual(doc.items[0].so_luong_xin_sua, SO_LUONG_XIN_SUA_TRONG)

	def test_nhan_vien_khong_tu_choi_sua_duoc(self):
		"""VẾ ÂM cần cho `de_xuat_tu_choi_sua`."""
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xin_sua(self.phieu_da_duyet, self.dong_moi)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_tu_choi_sua(self.phieu_da_duyet, "không đủ ngân sách")

	# ---- Con đường thông thường KHÔNG được vướng ------------------------

	def test_nhan_vien_VAN_chap_nhan_bao_gia_duoc(self):
		"""Chủ đầu tư chốt 19/08: "quản lý duyệt 10 hộp, Miyano báo giá,
		nhân viên là xong là đơn đi thành sales order".

		CHỈ đổi số lượng mới phải quay lại quản lý. ĐỒNG Ý với báo giá —
		không đổi gì — thì nhân viên tự làm xong. Bắt duyệt lại ở đây sẽ
		làm tắc đúng con đường thông thường mà không kiểm soát thêm được
		gì: số lượng vẫn đúng số quản lý đã duyệt.
		KHÔNG khẳng định tên trạng thái đích: nó do Workflow document quyết
		định, không do code này. Khẳng định đúng thứ test này canh — nhân
		viên KHÔNG bị chặn, và đơn đã rời trạng thái chờ."""
		frappe.set_user(self.user_huyethoc)
		portal.portal_order_accept(self.don_da_duyet, action="dong_y")
		self.assertNotEqual(
			frappe.db.get_value("Sales Order", self.don_da_duyet, "workflow_state"),
			"Chờ khách đồng ý",
		)

	# ---- Fail-closed khi thiếu cột ---------------------------------------

	def test_thieu_cot_custom_de_xuat_thi_CHAN_chu_khong_tha(self):
		"""Patch v1_24 chưa chạy → cổng phải ĐÓNG, không mở im lặng."""
		frappe.set_user(self.user_huyethoc)
		with patch.object(portal_context, "_cot_de_xuat_ton_tai", return_value=False):
			with self.assertRaises(frappe.PermissionError) as ctx:
				portal.portal_order_sua_so_luong(self.don_da_duyet, self.dong_moi)
		self.assertIn("chưa hoàn tất", str(ctx.exception))

	def test_thieu_cot_KHONG_chan_quan_ly(self):
		"""VẾ DƯƠNG của test trên — quản lý luôn qua được `la_quan_ly()`
		TRƯỚC khi guard kịp hỏi tới cột, nên thiếu cột không ảnh hưởng gì
		tới quản lý."""
		frappe.set_user(self.user_quan_ly)
		with patch.object(portal_context, "_cot_de_xuat_ton_tai", return_value=False):
			portal.portal_order_sua_so_luong(self.don_da_duyet, self.dong_moi)
		self.assertEqual(
			frappe.db.get_value("Sales Order", self.don_da_duyet, "workflow_state"),
			"Chờ xác nhận",
		)

	# ---- I3 (review Task 9) — trạng thái không phục hồi được -------------
	#
	# `_kiem_chuyen(TRANG_THAI_DA_DUYET)` một mình KHÔNG đủ: cạnh đó hợp lệ
	# từ CẢ "Chờ duyệt" (đường duyệt lần đầu thật) LẪN "Chờ duyệt sửa" (đường
	# xin sửa). `duyet_sua()`/`tu_choi_sua()` phải tự kiểm đang đứng ĐÚNG ở
	# "Chờ duyệt sửa" — thiếu chốt đó, gọi trên một phiếu "Chờ duyệt" (chưa
	# từng xin sửa, chưa có Sales Order) đẩy thẳng phiếu sang "Đã duyệt" mà
	# không có đơn nào đứng sau, và vì "Đã duyệt" chỉ còn cạnh ra là "Chờ
	# duyệt sửa", `duyet()` thật (nơi duy nhất tạo khối truy vết + sinh đơn)
	# không còn cách nào chạy lại — phiếu chết vĩnh viễn ở trạng thái nói dối.

	def _phieu_dang_cho_duyet_lan_dau(self):
		"""Phiếu ở "Chờ duyệt" — CHƯA từng được duyệt lần nào, chưa có Sales
		Order đứng sau. Khác `self.phieu_da_duyet` (đã duyệt thật, có đơn)."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"loai_don": "Mua lẻ",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 3}],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		return doc

	def test_duyet_sua_tu_trang_thai_cho_duyet_thi_bi_chan(self):
		doc = self._phieu_dang_cho_duyet_lan_dau()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.duyet_sua()
		self.assertIn("không có yêu cầu xin sửa", str(ctx.exception))
		doc.reload()
		# Chốt của cả I3 — phiếu KHÔNG bị đẩy sang "Đã duyệt" giả (không có
		# Sales Order đứng sau).
		self.assertEqual(doc.trang_thai, "Chờ duyệt")
		self.assertFalse(doc.sales_order)

	def test_tu_choi_sua_tu_trang_thai_cho_duyet_thi_bi_chan(self):
		doc = self._phieu_dang_cho_duyet_lan_dau()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.tu_choi_sua("không hợp lệ")
		self.assertIn("không có yêu cầu xin sửa", str(ctx.exception))
		doc.reload()
		self.assertEqual(doc.trang_thai, "Chờ duyệt")
		self.assertFalse(doc.sales_order)

	# ---- I1 (review Task 9) — nhánh "không đi qua đề xuất" chưa ai chạm --
	#
	# `test_don_KHONG_qua_duong_de_xuat_thi_giu_nguyen_hanh_vi_cu` ở trên
	# dùng `user_quan_ly` → `la_quan_ly()` trả True → guard `return` NGAY
	# dòng đầu, CHƯA BAO GIỜ chạm nhánh `if not so.get("custom_de_xuat"):
	# return`. Gọi THẲNG hàm ở đây, không qua endpoint: nhân viên gọi
	# `portal_order_sua_so_luong` trên đơn cũ sẽ bị `dam_bao_xem_duoc` chặn
	# SỚM HƠN (đơn cũ không có `custom_khoa_phong`) — một test xuyên endpoint
	# sẽ xanh vì lý do KHÁC, không phải vì guard này đúng.

	def test_dam_bao_duoc_sua_don_da_duyet_tra_ve_khi_khong_co_custom_de_xuat(self):
		so_stub = frappe._dict({"custom_de_xuat": None})
		with patch.object(portal_context, "la_quan_ly", return_value=False), \
			patch.object(portal_context, "_cot_de_xuat_ton_tai", return_value=True):
			# Không ném gì — đây chính là khẳng định. Nếu nhánh "return" bị
			# xoá/hỏng, dòng dưới ném PermissionError và test này đỏ.
			portal_context.dam_bao_duoc_sua_don_da_duyet(so_stub, user=self.user_huyethoc)

	# ---- I2 (review Task 9) — so_luong_xin_sua = 0 là một yêu cầu THẬT ---

	def test_nhan_vien_xin_bo_mot_dong_ve_0_quan_ly_duyet_sua_thi_dong_do_mat_that(self):
		"""`so_luong_xin_sua = 0` là một giá trị XIN SỬA hợp lệ (đúng quy
		ước "Số lượng 0 = bỏ dòng đó" của `portal_order_sua_so_luong`),
		KHÔNG phải "chưa có yêu cầu". Trước bản vá, mọi tầng coi 0 là falsy
		nên yêu cầu này bị bỏ qua LẶNG LẼ ở khắp nơi — phiếu báo "Chờ duyệt
		sửa" thành công, quản lý bấm duyệt sửa, và không có gì xảy ra."""
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xin_sua(self.phieu_da_duyet, {
			"items": [{"item_code": self.item, "qty": 0}],
		})
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_da_duyet)
		self.assertEqual(doc.items[0].so_luong_xin_sua, 0)   # KHÔNG bị bỏ qua

		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_duyet_sua(self.phieu_da_duyet)

		so = frappe.get_doc("Sales Order", self.don_da_duyet)
		ma_con_lai = {i.item_code for i in so.items}
		self.assertNotIn(self.item, ma_con_lai)   # dòng xin bỏ THẬT SỰ mất
		self.assertIn(self.item2, ma_con_lai)     # dòng KHÔNG xin sửa còn nguyên
