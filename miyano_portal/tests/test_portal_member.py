"""`Portal Member` — nguồn sự thật duy nhất cho danh tính cổng (bước 3)."""

import frappe
from frappe.tests.utils import FrappeTestCase

KHACH_BM = "Bệnh viện Bạch Mai"
KHACH_PXN = "PXN ABC"

# Mã ngắn hợp lệ dùng riêng cho bộ test này (vòng sửa 1). Không phải "ZZ..."
# như quy ước dữ liệu khác vì field bị giới hạn 10 ký tự và cần khớp cách
# đặt mã ngắn thật (chữ hoa, ngắn gọn).
MA_NGAN_TEST_BM = "ZZTBM"


class _NenThanhVien(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Portal Member", {"user": ["like", "zztest%"]})
		frappe.db.delete("Customer Department", {"ten_khoa_phong": ["like", "ZZTEST%"]})
		self.kp_bm = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_BM,
			"ten_khoa_phong": "ZZTEST Huyết học", "ma_khoa": "ZZHH",
		}).insert(ignore_permissions=True)
		self.kp_pxn = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_PXN,
			"ten_khoa_phong": "ZZTEST Xét nghiệm", "ma_khoa": "ZZXN",
		}).insert(ignore_permissions=True)
		# VÒNG SỬA 1 (F1): trên site thật, Bệnh viện Bạch Mai KHÔNG có
		# custom_ma_ngan. Nếu để nguyên, _chan_thieu_ma_ngan() bắt HẾT mọi
		# kịch bản "Nhân viên khoa" trong file này TRƯỚC KHI hai luật kia
		# (_chan_vai_tro_va_khoa_phong, _chan_khoa_cua_benh_vien_khac) có cơ
		# hội được kiểm — hai test dưới xanh vì SAI lý do (xem "Vòng sửa 1"
		# trong task-4-report.md, phần F1). Đặt một mã hợp lệ Ở ĐÂY để mỗi
		# test chỉ còn phụ thuộc đúng MỘT luật mà tên nó nói tới, rồi
		# addCleanup trả lại giá trị CŨ — Customer là bản ghi CHUNG của site
		# dùng chung, KHÔNG nằm trong rollback-theo-class của FrappeTestCase
		# (chỉ Portal Member/Customer Department mới do tay ta insert/xoá).
		ma_ngan_cu = frappe.db.get_value("Customer", KHACH_BM, "custom_ma_ngan")
		frappe.db.set_value("Customer", KHACH_BM, "custom_ma_ngan", MA_NGAN_TEST_BM)
		self.addCleanup(
			lambda: frappe.db.set_value("Customer", KHACH_BM, "custom_ma_ngan", ma_ngan_cu)
		)

	def _user(self, email):
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "ZZ",
				"user_type": "Website User", "send_welcome_email": 0,
			}).insert(ignore_permissions=True)
		return email

	def _tv(self, email, vai_tro="Quản lý", customer=KHACH_BM, khoa_phong=None):
		return frappe.get_doc({
			"doctype": "Portal Member", "user": self._user(email),
			"customer": customer, "vai_tro": vai_tro, "khoa_phong": khoa_phong,
		}).insert(ignore_permissions=True)


class TestPortalMemberRangBuoc(_NenThanhVien):
	def test_moi_benh_vien_dung_mot_quan_ly_dang_hoat_dong(self):
		self._tv("zztest.ql1@demo.miyano")
		with self.assertRaises(frappe.ValidationError) as cm:
			self._tv("zztest.ql2@demo.miyano")
		# Khẳng định ĐÚNG luật _chan_hai_quan_ly đứng sau lỗi này, không phải
		# một ValidationError nào khác trùng hợp che khuất (vòng sửa 1, F1).
		self.assertIn("đã có quản lý", str(cm.exception))

	def test_nhan_vien_khoa_bat_buoc_co_khoa_phong(self):
		with self.assertRaises(frappe.ValidationError) as cm:
			self._tv("zztest.nv@demo.miyano", vai_tro="Nhân viên khoa")
		# Trước vòng sửa 1, test này xanh cả khi tắt ĐÚNG guard
		# _chan_vai_tro_va_khoa_phong — vì BM chưa có custom_ma_ngan nên
		# _chan_thieu_ma_ngan bắt thay. assertIn dưới đây chốt lại: phải là
		# đúng thông điệp "thiếu khoa phòng", không phải "thiếu mã ngắn".
		self.assertIn("phải được gán một khoa phòng", str(cm.exception))

	def test_quan_ly_khong_duoc_gan_khoa_phong(self):
		with self.assertRaises(frappe.ValidationError) as cm:
			self._tv("zztest.ql3@demo.miyano", khoa_phong=self.kp_bm.name)
		self.assertIn("không gắn vào khoa phòng", str(cm.exception))

	def test_khoa_phong_phai_thuoc_dung_benh_vien(self):
		"""Lỗ phân quyền mở được bằng một thao tác nhập liệu."""
		self._tv("zztest.ql4@demo.miyano")
		with self.assertRaises(frappe.ValidationError) as cm:
			self._tv(
				"zztest.nv2@demo.miyano", vai_tro="Nhân viên khoa",
				customer=KHACH_BM, khoa_phong=self.kp_pxn.name,
			)
		# Cùng bẫy che khuất như test ở trên (trước vòng sửa 1) — chốt lại
		# đúng thông điệp của _chan_khoa_cua_benh_vien_khac.
		self.assertIn("không thuộc khách hàng này", str(cm.exception))

	def test_mot_user_chi_thuoc_mot_benh_vien(self):
		self._tv("zztest.ql5@demo.miyano")
		with self.assertRaises(Exception) as cm:
			self._tv("zztest.ql5@demo.miyano", customer=KHACH_PXN)
		# assertRaises(Exception) cố ý lỏng (đây là lỗi DB/framework, không
		# phải frappe.throw() tự viết) — assertIn dưới đây bù lại độ lỏng đó,
		# chốt rằng đúng ràng buộc unique trên field `user` là thủ phạm, chứ
		# không phải một lỗi khác tình cờ cũng là Exception.
		self.assertIn("for key 'user'", str(cm.exception))

	def test_bat_buoc_khach_hang_co_ma_ngan_truoc_khi_cap_tai_khoan_khoa(self):
		"""Kiểm đúng lúc BẬT tính năng, không phải lúc nhân viên bấm gửi."""
		frappe.db.set_value("Customer", KHACH_BM, "custom_ma_ngan", None)
		self._tv("zztest.ql6@demo.miyano")
		with self.assertRaises(frappe.ValidationError) as cm:
			self._tv(
				"zztest.nv3@demo.miyano", vai_tro="Nhân viên khoa",
				khoa_phong=self.kp_bm.name,
			)
		self.assertIn("chưa có Mã ngắn", str(cm.exception))


class TestPortalMemberDuongThanhCong(_NenThanhVien):
	"""F2 (vòng sửa 1): trước vòng này, cả 6 test ở trên đều là ca ÂM TÍNH —
	không có test nào chứng minh một thành viên HỢP LỆ lưu được. Đây chính là
	con đường Task 5 (backfill dữ liệu thật) sẽ đi qua đầu tiên."""

	def test_nhan_vien_khoa_hop_le_luu_duoc(self):
		tv = self._tv(
			"zztest.nv.hople@demo.miyano", vai_tro="Nhân viên khoa",
			customer=KHACH_BM, khoa_phong=self.kp_bm.name,
		)
		self.assertEqual(tv.customer, KHACH_BM)
		self.assertEqual(tv.vai_tro, "Nhân viên khoa")
		self.assertEqual(tv.khoa_phong, self.kp_bm.name)
		self.assertEqual(tv.active, 1)

	def test_quan_ly_hop_le_luu_duoc(self):
		tv = self._tv("zztest.ql.hople@demo.miyano")
		self.assertEqual(tv.customer, KHACH_BM)
		self.assertEqual(tv.vai_tro, "Quản lý")
		self.assertFalse(tv.khoa_phong)
		self.assertEqual(tv.active, 1)


class TestPortalMemberKhongLoRaChoKhach(FrappeTestCase):
	"""F2 (vòng sửa 2, review độc lập): `Portal Member` đứng NGOÀI mọi vòng
	lặp `_nap_doctype_kho()` trong test_kho_isolation.py — nó nằm trong
	KHONG_PHAI_DOCTYPE_KHO nên không có mặt trong kho_doctypes()/
	kho_parent_doctypes(), do đó KHÔNG được TestKhoDocPermConfig đo tới.

	Hỏng ra sao nếu không có lưới an toàn riêng này: một cú click trong Role
	Permission Manager tạo một `Custom DocPerm` cấp read cho role `Customer`
	trên `Portal Member`. Vì doctype này không có hook permission_query_
	conditions/has_permission nào (đúng như comment ở KHONG_PHAI_DOCTYPE_KHO
	giải thích — nó chưa từng được thiết kế để khách tự đọc), DocPerm đó sẽ
	là ĐƯỜNG DUY NHẤT quyết định quyền — và mọi tài khoản cổng sẽ đọc được
	TOÀN BỘ bảng danh tính: mọi bệnh viện, mọi email, mọi vai trò. 1038 test
	khác vẫn xanh hết vì không cái nào động tới doctype này. Ba test dưới
	đây là lưới an toàn RIÊNG cho đúng một doctype `Portal Member`."""

	def test_khong_co_docperm_nao_cho_role_customer(self):
		rows = frappe.get_all(
			"DocPerm", filters={"parent": "Portal Member", "role": "Customer"}
		)
		self.assertEqual(
			rows, [],
			"Portal Member không được có DocPerm nào cho role Customer trong "
			"JSON — nếu đỏ, ai đó đã thêm quyền đọc trực tiếp cho khách vào "
			"portal_member.json, mở lại đúng lỗ mà docstring đầu file cảnh báo.",
		)

	def test_khong_co_custom_docperm_nao_cho_role_customer(self):
		rows = frappe.get_all(
			"Custom DocPerm", filters={"parent": "Portal Member", "role": "Customer"}
		)
		self.assertEqual(
			rows, [],
			"Chưa ai được chỉnh quyền Portal Member qua Role Permission "
			"Manager — nếu đỏ, một Custom DocPerm đã cấp quyền cho role "
			"Customer, mở toang bảng danh tính cho MỌI tài khoản cổng vì "
			"doctype này không có hook cách ly nào đứng sau.",
		)

	def test_website_user_khong_doc_duoc_portal_member(self):
		# Tài khoản cổng THẬT trên site (không phải user zztest tạm) — đúng
		# khuôn BM_USER trong test_kho_isolation.py.
		self.assertFalse(
			frappe.has_permission("Portal Member", "read", user="bvbm@demo.miyano"),
			"Một tài khoản cổng thật (Website User) không được có quyền đọc "
			"Portal Member — nếu True, xem hai test trên để biết DocPerm hay "
			"Custom DocPerm nào vừa mở lỗ.",
		)


class TestPortalMemberGioiHanDaBiet(_NenThanhVien):
	"""F3 (vòng sửa 2, review độc lập): `_chan_hai_quan_ly()` chỉ chạy trong
	`validate()`. `frappe.db.set_value()`/`doc.db_set()` bỏ qua validate hoàn
	toàn và không có ràng buộc DB nào đứng sau — nên vẫn đi vòng được luật
	"mỗi bệnh viện đúng một quản lý đang hoạt động". Test dưới đây KHÔNG
	kiểm một luật đang đứng vững; nó xác nhận GIỚI HẠN ĐÃ BIẾT này thật sự
	tồn tại (xem docstring `_chan_hai_quan_ly` trong portal_member.py), để
	không ai tưởng nhầm là lỗ hổng mới phát hiện ở vòng sau — và để nhắc:
	Task 5 (backfill phía server) PHẢI luôn đi qua doc.save()."""

	def test_db_set_di_vong_qua_luat_mot_quan_ly(self):
		self._tv("zztest.ql7@demo.miyano")
		# Tạo quản lý thứ hai ở trạng thái INACTIVE — guard bỏ qua ngay từ
		# đầu (`not self.active`), nên insert này không đỏ.
		user2 = self._user("zztest.ql8@demo.miyano")
		ql2 = frappe.get_doc({
			"doctype": "Portal Member", "user": user2,
			"customer": KHACH_BM, "vai_tro": "Quản lý", "active": 0,
		}).insert(ignore_permissions=True)
		# Bật active bằng db_set — KHÔNG đi qua validate(), guard không hề
		# được gọi lại.
		ql2.db_set("active", 1)
		so_quan_ly_active = frappe.db.count(
			"Portal Member", {"customer": KHACH_BM, "vai_tro": "Quản lý", "active": 1}
		)
		self.assertEqual(
			so_quan_ly_active, 2,
			"Giới hạn đã biết: db_set() đi vòng được _chan_hai_quan_ly, để "
			"lại HAI quản lý cùng active=1 cho một bệnh viện — xem docstring "
			"_chan_hai_quan_ly trong portal_member.py.",
		)
