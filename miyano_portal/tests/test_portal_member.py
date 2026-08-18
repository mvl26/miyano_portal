"""`Portal Member` — nguồn sự thật duy nhất cho danh tính cổng (bước 3)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import portal_context, portal_thong_bao_khach

# VÒNG SỬA 3 (F5, re-review độc lập): bản trước dùng trực tiếp "Bệnh viện
# Bạch Mai"/"PXN ABC" — hai khách THẬT trên site dùng chung erptest.local.
# Điều đó khiến MỌI test trong file này ngầm giả định "chưa có quản lý
# active thật nào cho Bạch Mai", một giả định sẽ vỡ đúng ngày Task 5 chạy
# backfill (xem "Vòng sửa 3" trong task-4-report.md, mục F4/F5 — F4 tự bắt
# đúng bẫy này trong chính vòng sửa 2). Chuyển hẳn sang hai Customer RIÊNG
# của bộ test này, tiền tố ZZTEST, tự tạo trong setUp và tự xoá sạch (Portal
# Member + Customer Department + Customer) trong addCleanup — cắt đứt phụ
# thuộc vào dữ liệu thật thay vì vá từng chỗ giả định.
KHACH_BM = "ZZTEST Benh Vien A"
KHACH_PXN = "ZZTEST Benh Vien B"

# Mã ngắn hợp lệ dùng riêng cho bộ test này. Không phải "ZZ..." như quy ước
# dữ liệu khác vì field bị giới hạn 10 ký tự.
MA_NGAN_TEST_BM = "ZZTBM"


class _NenThanhVien(FrappeTestCase):
	def setUp(self):
		self._don_sach()
		self.addCleanup(self._don_sach)
		for ten in (KHACH_BM, KHACH_PXN):
			frappe.get_doc({
				"doctype": "Customer", "customer_name": ten,
				"customer_type": "Company", "customer_group": "All Customer Groups",
				"territory": "All Territories",
			}).insert(ignore_permissions=True)
		self.kp_bm = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_BM,
			"ten_khoa_phong": "ZZTEST Huyết học", "ma_khoa": "ZZHH",
		}).insert(ignore_permissions=True)
		self.kp_pxn = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_PXN,
			"ten_khoa_phong": "ZZTEST Xét nghiệm", "ma_khoa": "ZZXN",
		}).insert(ignore_permissions=True)
		# Khách này do TA tạo, không phải Bạch Mai thật — không cần lưu/trả
		# lại giá trị cũ (addCleanup ở trên xoá thẳng cả Customer).
		frappe.db.set_value("Customer", KHACH_BM, "custom_ma_ngan", MA_NGAN_TEST_BM)

	def _don_sach(self):
		"""Dọn sạch TOÀN BỘ dấu vết của bộ test này — chạy cả ở ĐẦU setUp
		(phòng lần chạy trước bị ngắt giữa chừng để lại rác) lẫn ở CUỐI qua
		addCleanup (dọn cho chính lần chạy này, và cho `bench run-tests`
		chạy hai lần liên tiếp không tích rác — xem "Vòng sửa 3", F5)."""
		frappe.db.delete("Portal Member", {"user": ["like", "zztest%"]})
		frappe.db.delete("Customer Department", {"customer": ["in", (KHACH_BM, KHACH_PXN)]})
		frappe.db.delete("Customer", {"name": ["in", (KHACH_BM, KHACH_PXN)]})

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
	TOÀN BỘ bảng danh tính: mọi bệnh viện, mọi email, mọi vai trò. Bộ test
	còn lại vẫn xanh hết vì không cái nào động tới doctype này. Ba test dưới
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
		# khuôn BM_USER trong test_kho_isolation.py. Test này không đếm dữ
		# liệu của Portal Member (chỉ hỏi có/không có quyền), nên KHÔNG dính
		# giả định trạng thái dữ liệu như F4/F5 — an toàn giữ nguyên user
		# thật.
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
	kiểm một luật đang đứng vững ở CHIỀU DƯƠNG; nó xác nhận GIỚI HẠN ĐÃ BIẾT
	này thật sự tồn tại (xem docstring `_chan_hai_quan_ly` trong
	portal_member.py), để không ai tưởng nhầm là lỗ hổng mới phát hiện ở
	vòng sau — và để nhắc: Task 5 (backfill phía server) PHẢI luôn đi qua
	doc.save()."""

	def test_db_set_di_vong_qua_luat_mot_quan_ly(self):
		self._tv("zztest.ql7@demo.miyano")
		# Tạo quản lý thứ hai ở trạng thái INACTIVE — guard bỏ qua ngay từ
		# đầu (`not self.active`), nên insert này không đỏ.
		user2 = self._user("zztest.ql8@demo.miyano")
		ql2 = frappe.get_doc({
			"doctype": "Portal Member", "user": user2,
			"customer": KHACH_BM, "vai_tro": "Quản lý", "active": 0,
		}).insert(ignore_permissions=True)

		# CHIỀU DƯƠNG trước (vòng sửa 3, F4 — góp ý của re-review): guard vẫn
		# phải SỐNG trên đường chính thống. doc.save() với cùng dữ liệu này
		# (bật active=1 qua validate()) phải bị chặn đúng như
		# test_moi_benh_vien_dung_mot_quan_ly_dang_hoat_dong ở trên.
		ql2.active = 1
		with self.assertRaises(frappe.ValidationError) as cm:
			ql2.save(ignore_permissions=True)
		self.assertIn("đã có quản lý", str(cm.exception))
		# save() ném lỗi thì DB chưa đổi, nhưng field trong bộ nhớ của ql2 đã
		# bị ta gán active=1 phía trên — nạp lại từ DB trước khi đi tiếp.
		ql2.reload()
		self.assertEqual(ql2.active, 0)

		# CHIỀU ÂM: db_set đi vòng qua validate() hoàn toàn — đây mới là lỗ
		# đang được tài liệu hoá (KHÔNG phải điều test này chứng minh là an
		# toàn).
		ql2.db_set("active", 1)
		# Đo trên ĐÚNG bản ghi (vòng sửa 3, F4) — không đếm tuyệt đối trên cả
		# bảng `Portal Member` bằng frappe.db.count(): trước vòng sửa 3, con
		# số kỳ vọng là "2" giả định BÊN CẠNH `Customer` ZZTEST không có
		# quản lý active thật nào khác — giả định đó không còn đúng sau khi
		# Task 5 backfill (dù nay `Customer` này là ZZTEST riêng của bộ test,
		# vẫn giữ nguyên tắc "đo đúng bản ghi" làm chuẩn cho mọi test tương
		# tự sau này).
		self.assertEqual(
			frappe.db.get_value("Portal Member", ql2.name, "active"), 1,
			"Giới hạn đã biết: db_set() đi vòng được _chan_hai_quan_ly — "
			"xem docstring _chan_hai_quan_ly trong portal_member.py.",
		)


class TestPhamViTheoVaiTro(_NenThanhVien):
	def test_quan_ly_khong_bi_gioi_han_khoa(self):
		tv = self._tv("zztest.ql7@demo.miyano")
		self.assertEqual(portal_context.pham_vi_don(tv.user), {})
		self.assertTrue(portal_context.la_quan_ly(tv.user))

	def test_nhan_vien_khoa_bi_gioi_han_dung_khoa_cua_minh(self):
		frappe.db.set_value("Customer", KHACH_BM, "custom_ma_ngan", "ZZBM")
		self._tv("zztest.ql8@demo.miyano")
		tv = self._tv(
			"zztest.nv4@demo.miyano", vai_tro="Nhân viên khoa",
			khoa_phong=self.kp_bm.name,
		)
		self.assertEqual(
			portal_context.pham_vi_don(tv.user),
			{"custom_khoa_phong": self.kp_bm.name},
		)
		self.assertFalse(portal_context.la_quan_ly(tv.user))

	def test_get_allowed_customers_doc_portal_member(self):
		tv = self._tv("zztest.ql9@demo.miyano")
		self.assertEqual(portal_context.get_allowed_customers(tv.user), [KHACH_BM])

	def test_thanh_vien_da_tat_khong_con_pham_vi_nao(self):
		tv = self._tv("zztest.ql10@demo.miyano")
		frappe.db.set_value("Portal Member", tv.name, "active", 0)
		self.assertEqual(portal_context.get_allowed_customers(tv.user), [])

	def test_nhan_vien_khoa_active_thieu_khoa_phong_fail_closed(self):
		"""VÒNG SỬA 3 (F5, review độc lập, Important): `khoa_phong` rỗng ở
		`active=1` không đi qua được validate() bình thường
		(_chan_vai_tro_va_khoa_phong chặn) — chỉ tới được đây bằng đúng lỗ
		đã biết (`db_set()` đi vòng qua validate(), xem `_chan_hai_quan_ly`/
		`TestPortalMemberGioiHanDaBiet` ở trên). `pham_vi_don()` phải FAIL-
		CLOSED (ném PermissionError), không được trả một bộ lọc trông hợp lệ
		nhưng vô nghĩa (`{"custom_khoa_phong": None}`) — chỗ ĐỌC phải tự vệ
		vì chỗ GHI có giới hạn đã biết không tự vệ được."""
		self._tv("zztest.ql11@demo.miyano")
		tv = self._tv(
			"zztest.nv5@demo.miyano", vai_tro="Nhân viên khoa",
			khoa_phong=self.kp_bm.name,
		)
		tv.db_set("khoa_phong", None)
		with self.assertRaises(frappe.PermissionError) as cm:
			portal_context.pham_vi_don(tv.user)
		self.assertIn("chưa được gán khoa phòng", str(cm.exception))


class TestTuongThichNguoc(FrappeTestCase):
	def test_sau_patch_moi_tai_khoan_cong_cu_deu_la_quan_ly(self):
		"""Ràng buộc tự đặt cho cả đề án: không làm phiền khách đang dùng."""
		for user in ("bvbm@demo.miyano", "bvminhduc@demo.miyano"):
			tv = frappe.db.get_value(
				"Portal Member", {"user": user}, ["vai_tro", "khoa_phong", "active"],
				as_dict=True,
			)
			self.assertIsNotNone(tv, f"{user} chưa có Portal Member sau patch")
			self.assertEqual(tv.vai_tro, "Quản lý")
			self.assertFalse(tv.khoa_phong)
			self.assertEqual(tv.active, 1)
			self.assertEqual(portal_context.pham_vi_don(user), {})


class TestChieuNguocDanhTinh(_NenThanhVien):
	"""Task 6 — chiều NGƯỢC của `portal_context.get_allowed_customers`:
	`_portal_users_cua_khach` (Customer -> User) trong portal_thong_bao_khach
	còn đi qua Contact trong khi chiều XUÔI đã chuyển sang Portal Member từ
	Task 5. Hai test dưới đây khoá lại đúng hai kiểu sai đối xứng mà việc đó
	để lại."""

	def test_nguoi_nhan_thong_bao_lay_tu_portal_member(self):
		"""User có Portal Member nhưng KHÔNG có Contact gắn đúng khách hàng
		này vẫn phải nhận thông báo.

		Lệch một chữ so với brief gốc: brief giả định fixture "user KHÔNG có
		Contact" (`frappe.db.exists("Contact", {"user": ...})` falsy). Thực
		tế không đúng — `User.on_update()` (frappe/core/doctype/user/user.py)
		LUÔN enqueue `create_contact()` cho mọi User mới (đồng bộ khi
		`frappe.flags.in_test`), tự tạo một Contact "mồ côi" gắn `user`
		nhưng KHÔNG có `Dynamic Link` nào tới Customer nào cả. Test chạy y
		hệt code brief cho ra RED sai lý do (assertFalse tự nó đỏ vì Contact
		mồ côi này tồn tại, chưa kịp chạm tới nhánh `_portal_users_cua_khach`
		đang muốn kiểm). Đổi sang khẳng định đúng tiền đề mà đường Contact
		CŨ cần để tìm ra ai đó: không có `Dynamic Link` nào nối Contact tới
		đúng khách hàng KHACH_BM — đó mới là điều kiện khiến đường Contact cũ
		trả về rỗng."""
		tv = self._tv("zztest.ql11@demo.miyano")
		self.assertFalse(
			frappe.db.exists(
				"Dynamic Link",
				{
					"parenttype": "Contact",
					"link_doctype": "Customer",
					"link_name": KHACH_BM,
				},
			),
			"fixture phải là trạng thái mà đường Contact CŨ (Dynamic Link) "
			"không tra ra ai cho khách hàng này",
		)
		self.assertIn(
			tv.user, portal_thong_bao_khach._portal_users_cua_khach(KHACH_BM)
		)

	def test_thanh_vien_da_tat_khong_nhan_thong_bao(self):
		"""Portal Member `active=0` thì KHÔNG được trả về — dù đường Contact
		CŨ vẫn còn tìm ra được (Contact không biết gì về cờ `active` của
		Portal Member).

		Nếu chỉ tắt Portal Member mà không gắn thêm Contact + Dynamic Link
		nào ở đây, test này XANH GIẢ dưới cả code CŨ lẫn MỚI: đường Contact
		cũ vốn dĩ đã trả về [] cho user này (không có Dynamic Link nào tới
		KHACH_BM — xem giải thích Contact "mồ côi" ở test phía trên), nên
		`assertNotIn` không kiểm được gì. Tự tạo Contact + Dynamic Link tới
		KHACH_BM ở đây để dưới code CŨ, user này VẪN bị trả về (đường Contact
		không lọc theo active của Portal Member) → assertNotIn phải ĐỎ; chỉ
		sau khi sửa sang lọc theo Portal Member.active mới XANH thật."""
		tv = self._tv("zztest.ql12@demo.miyano")
		contact_name = f"{KHACH_BM}-{tv.user}-zztest"
		ct = frappe.get_doc({
			"doctype": "Contact", "first_name": "ZZTEST", "user": tv.user,
		})
		ct.name = contact_name
		ct.append("email_ids", {"email_id": tv.user, "is_primary": 1})
		ct.append("links", {"link_doctype": "Customer", "link_name": KHACH_BM})
		ct.insert(ignore_permissions=True)
		# Dùng frappe.delete_doc (không phải frappe.db.delete) — xoá đúng cả
		# bảng con Contact Email/Dynamic Link, tránh đúng lỗ đã bắt ở Task 5.
		self.addCleanup(
			frappe.delete_doc, "Contact", contact_name,
			ignore_permissions=True, force=True,
		)

		frappe.db.set_value("Portal Member", tv.name, "active", 0)
		self.assertNotIn(
			tv.user, portal_thong_bao_khach._portal_users_cua_khach(KHACH_BM)
		)

	def test_user_bi_khoa_khong_duoc_tinh(self):
		"""Khoá lại đúng ràng buộc brief nêu rõ ("Chỉ trả User còn `enabled`
		— giữ nguyên tính chất này của hàm cũ") NGAY TRÊN nguồn dữ liệu MỚI
		(Portal Member), không chỉ dựa vào `test_user_bi_khoa_khong_duoc_tinh`
		cũ trong test_thong_bao_khach.py — file đó dùng fixture seed_demo()
		vẫn còn tạo cả Contact, nên không tách bạch được việc lọc enabled có
		thật sự chạy trên nhánh Portal Member hay không.

		Test này XANH GIẢ dưới cả code CŨ lẫn MỚI trước khi có ai động tới
		bộ lọc `enabled` (code cũ, nếu còn nguyên, cũng lọc enabled ở đúng
		bước cuối) — không phải một bài RED-first, mà là một chốt chặn hồi
		quy cho đúng ràng buộc đã nêu trong brief. `frappe.db.set_value`
		trên User đi vòng qua `on_update`, nên không tự sinh thêm Contact."""
		tv = self._tv("zztest.ql13@demo.miyano")
		frappe.db.set_value("User", tv.user, "enabled", 0)
		self.addCleanup(frappe.db.set_value, "User", tv.user, "enabled", 1)
		self.assertNotIn(
			tv.user, portal_thong_bao_khach._portal_users_cua_khach(KHACH_BM)
		)
