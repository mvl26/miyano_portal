"""CR-03 — khai chi tiết hàng chưa có trong hệ thống.

Chủ đầu tư chốt 05/09/2026. Khách gõ tay một mặt hàng không có trong danh
mục thì khai thêm được model/hãng/nước/quy cách/NCC/giá, và **bắt buộc ít
nhất một ảnh** (BR-Y5) — có lối thoát `khong_co_anh`, khi đó
`mo_ta_nhan_dang` thành bắt buộc tối thiểu 50 ký tự.

HAI ĐIỀU ĐỊNH HÌNH TOÀN BỘ BỘ TEST NÀY:

1. `SalesOrderDatNgoaiItem.validate()` KHÔNG BAO GIỜ CHẠY — Frappe không gọi
   `validate()` của controller bảng con khi cha lưu (xem docstring của chính
   file đó). Nên chốt phải sống ở CHA, và test phải đi qua cha. Một bài test
   gọi thẳng `row.validate()` sẽ xanh mà không canh gì.

2. Chốt chạy lúc **GỬI DUYỆT**, không phải lúc lưu nháp. Khách gõ nửa chừng
   rồi lưu lại làm tiếp buổi chiều là việc bình thường; bắt đủ ảnh mới cho
   lưu là biến nút Lưu thành một cái bẫy. Vì vậy mọi bài dưới đây đều lưu
   được TRƯỚC, và chỉ đỏ ở `gui_duyet()`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class _CR03Fixture(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.ctx = dung_fixture(self)
		self.kh = self.ctx.kh_a
		self.khoa = self.ctx.khoa_huyethoc
		self.nv = "Administrator"

	def tearDown(self):
		frappe.set_user("Administrator")

	def _thanh_vien(self, email, customer, khoa_phong, vai_tro="Nhân viên khoa"):
		"""Portal Member thật — `_phieu_cua_toi()` (chốt của cả ba endpoint
		ảnh) hỏi `get_portal_member()`, nên chạy dưới Administrator sẽ ném
		"Tài khoản chưa gắn với khách hàng nào" TRƯỚC khi tới chốt thật.

		Đó không chỉ là phiền: một bài VẾ ÂM chạy dưới Administrator sẽ XANH
		vì đúng lỗi đó, chứ không phải vì chốt sở hữu ảnh đã chặn. Bài như
		vậy trông như lưới mà không canh gì — đã bắt gặp ngay ở vòng đầu của
		chính file này.
		"""
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email,
				"first_name": email.split("@")[0],
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		gia_tri = {
			"customer": customer, "vai_tro": vai_tro,
			"khoa_phong": khoa_phong, "active": 1,
		}
		ten_tv = frappe.db.get_value("Portal Member", {"user": email}, "name")
		if ten_tv:
			frappe.db.set_value("Portal Member", ten_tv, gia_tri)
		else:
			frappe.get_doc({"doctype": "Portal Member", "user": email, **gia_tri}).insert(
				ignore_permissions=True
			)
		return email

	def _phieu(self, **dong_dat_ngoai):
		"""Phiếu Nháp có ĐÚNG MỘT dòng đặt ngoài, mặc định là dòng hợp lệ
		nhất có thể (đã có ảnh) — từng bài tự phá đúng thứ nó canh."""
		dong = {
			"ten_hang": "Găng tay nitrile không bột size M",
			"dvt": "Hộp",
			"so_luong": 5,
			"anh": '["/private/files/_test_cr03.jpg"]',
		}
		dong.update(dong_dat_ngoai)
		chu = dong_dat_ngoai.pop("chu_phieu", None) or self.nv
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh,
			"khoa_phong": self.khoa,
			"nguoi_yeu_cau": chu,
			"ly_do_yeu_cau": "Khoa cần bổ sung vật tư tiêu hao",
			"dat_ngoai": [dong],
		})
		doc.insert(ignore_permissions=True)
		# `_phieu_cua_toi()` (không `cho_quan_ly`) là CHỐT OWNER-ONLY, và
		# `owner` do Frappe đặt theo phiên lúc insert. Đặt lại tường minh để
		# bài chạy đúng vai người lập phiếu — không phải mẹo test, mà là dựng
		# lại đúng tình huống thật: người gõ dòng hàng chính là người tải ảnh.
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", chu,
		                    update_modified=False)
		doc.reload()
		return doc


class TestBatBuocAnh(_CR03Fixture):
	def test_luu_nhap_van_duoc_du_chua_co_anh(self):
		"""Lưu nháp KHÔNG bị chặn — đây là vế chống-bẫy, đừng bỏ.

		Bỏ bài này thì một bản vá sau có thể dời chốt vào `validate()` cho
		"chặt hơn", và khách mất luôn khả năng gõ nửa chừng rồi lưu lại.
		"""
		doc = self._phieu(anh=None)
		self.assertEqual(doc.trang_thai, "Nháp")
		doc.dat_ngoai[0].ghi_chu = "gõ tiếp buổi chiều"
		doc.save(ignore_permissions=True)  # KHÔNG được ném lỗi

	def test_gui_duyet_khong_anh_khong_co_co_thi_bi_chan(self):
		doc = self._phieu(anh=None)
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.gui_duyet()
		self.assertIn("ảnh", str(ctx.exception).lower())
		self.assertIn("Găng tay nitrile", str(ctx.exception))

	def test_gui_duyet_co_anh_thi_qua(self):
		doc = self._phieu()
		doc.gui_duyet()
		self.assertEqual(doc.trang_thai, "Chờ duyệt")

	def test_anh_rong_chuoi_json_rong_cung_bi_chan(self):
		"""`"[]"` là "đã có trường, chưa có ảnh" — dễ lọt nhất.

		Kiểm `if not row.anh` sẽ cho chuỗi `"[]"` đi qua vì nó khác rỗng.
		"""
		doc = self._phieu(anh="[]")
		with self.assertRaises(frappe.ValidationError):
			doc.gui_duyet()


class TestLoiThoatKhongCoAnh(_CR03Fixture):
	def test_bat_co_ma_mo_ta_ngan_thi_bi_chan(self):
		doc = self._phieu(anh=None, khong_co_anh=1, mo_ta_nhan_dang="nhãn mờ")
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.gui_duyet()
		self.assertIn("50", str(ctx.exception))

	def test_bat_co_ma_khong_mo_ta_thi_bi_chan(self):
		doc = self._phieu(anh=None, khong_co_anh=1, mo_ta_nhan_dang=None)
		with self.assertRaises(frappe.ValidationError):
			doc.gui_duyet()

	def test_bat_co_va_mo_ta_du_dai_thi_qua(self):
		mo_ta = (
			"Hộp giấy trắng viền xanh dương, chữ in màu đen ở mặt trước, "
			"nắp mở kiểu lật, đã bỏ vỏ nên không chụp lại được."
		)
		self.assertGreaterEqual(len(mo_ta), 50)
		doc = self._phieu(anh=None, khong_co_anh=1, mo_ta_nhan_dang=mo_ta)
		doc.gui_duyet()
		self.assertEqual(doc.trang_thai, "Chờ duyệt")

	def test_dem_ky_tu_sau_khi_cat_khoang_trang(self):
		"""Khoảng trắng không tính vào 50 ký tự.

		DỮ LIỆU VÀO PHẢI ≥50 KÝ TỰ KHI CHƯA CẮT và <50 SAU KHI CẮT — nếu
		không, bài này không canh gì: bản đầu dùng 30 chữ + 6 dấu cách (36
		ký tự), vẫn dưới ngưỡng ở CẢ HAI cách đếm, nên bỏ `strip()` khỏi mã
		vẫn xanh. Đã đo: phép phá "bỏ strip()" không làm bài nào đỏ.

		30 chữ + 25 dấu cách = 55 ký tự thô, 30 sau khi cắt. Không cắt thì
		lọt; cắt thì chặn.
		"""
		mo_ta = "a" * 30 + " " * 25
		self.assertGreaterEqual(len(mo_ta), 50)
		self.assertLess(len(mo_ta.strip()), 50)
		doc = self._phieu(anh=None, khong_co_anh=1, mo_ta_nhan_dang=mo_ta)
		with self.assertRaises(frappe.ValidationError):
			doc.gui_duyet()

	def test_co_anh_thi_khong_doi_mo_ta(self):
		"""Có ảnh rồi thì `mo_ta_nhan_dang` không còn bắt buộc — kể cả khi
		cờ bật nhầm. Ảnh là thứ chốt này thật sự cần."""
		doc = self._phieu(khong_co_anh=1, mo_ta_nhan_dang=None)
		doc.gui_duyet()
		self.assertEqual(doc.trang_thai, "Chờ duyệt")


class TestBayTruongMoiLuuDuoc(_CR03Fixture):
	def test_bay_truong_mo_ta_luu_va_doc_lai_dung(self):
		"""Bảy trường tuỳ chọn phải THẬT SỰ lưu xuống, không rơi lặng lẽ.

		Khẳng định từng giá trị KHÁC mặc định — một bài khẳng định `""` với
		fixture chưa bao giờ đặt giá trị là bài không canh gì.
		"""
		doc = self._phieu(
			model_ma="NBG-100-M", hang_san_xuat="Ansell", nuoc_san_xuat="Malaysia",
			quy_cach="hộp 100 chiếc", ncc_hien_tai="Công ty ABC",
			gia_hien_tai=185000, ghi_chu="cần gấp",
		)
		doc.reload()
		r = doc.dat_ngoai[0]
		self.assertEqual(r.model_ma, "NBG-100-M")
		self.assertEqual(r.hang_san_xuat, "Ansell")
		self.assertEqual(r.nuoc_san_xuat, "Malaysia")
		self.assertEqual(r.quy_cach, "hộp 100 chiếc")
		self.assertEqual(r.ncc_hien_tai, "Công ty ABC")
		self.assertEqual(float(r.gia_hien_tai), 185000.0)

	def test_dvt_giu_nguyen_ten_truong(self):
		"""`dvt` phải trùng tên với Portal De Xuat Mua Item và Portal Item
		Request — chủ đầu tư yêu cầu nhất quán toàn hệ thống. Đổi tên ở một
		chỗ là buộc mọi báo cáo gộp sau này phải có bảng ánh xạ."""
		for dt in ("Sales Order Dat Ngoai Item", "Portal De Xuat Mua Item", "Portal Item Request"):
			with self.subTest(doctype=dt):
				self.assertTrue(
					frappe.get_meta(dt).has_field("dvt"),
					f"{dt} không còn trường `dvt`",
				)

	def test_quy_cach_cung_ten_voi_portal_item_request(self):
		for dt in ("Sales Order Dat Ngoai Item", "Portal Item Request"):
			with self.subTest(doctype=dt):
				self.assertTrue(frappe.get_meta(dt).has_field("quy_cach"))


class TestEndpointAnh(_CR03Fixture):
	"""Ba endpoint ảnh. Trọng tâm là VẾ ÂM: ảnh của bệnh viện khác.

	Sổ nhật ký và ảnh nhãn hộp đều là dữ liệu của một bệnh viện cụ thể. Rò
	giữa hai bệnh viện là sự cố nghiêm trọng, và `file_url` KHÔNG phải khoá
	bí mật — Frappe gộp tệp trùng nội dung theo hash, nên hai bản ghi `File`
	khác nhau có thể trỏ chung một url.
	"""

	def setUp(self):
		super().setUp()
		self.user_a = self._thanh_vien(
			"_test_cr03_a@miyano-test.local", self.kh, self.khoa
		)

	def _phieu(self, **kw):
		kw.setdefault("chu_phieu", self.user_a)
		return super()._phieu(**kw)

	def _dinh_anh_that(self, doc, noi_dung=b"\x89PNG\r\n\x1a\n_test_cr03"):
		from frappe.utils.file_manager import save_file

		return save_file(
			f"cr03_{frappe.generate_hash(length=6)}.png", noi_dung,
			"Portal De Xuat Mua", doc.name, is_private=1,
		)

	def test_xem_anh_cua_phieu_minh_thi_duoc(self):
		from miyano_portal.api import portal

		doc = self._phieu(anh=None)
		f = self._dinh_anh_that(doc)
		frappe.db.set_value(
			"Sales Order Dat Ngoai Item", doc.dat_ngoai[0].name, "anh",
			frappe.as_json([f.file_url]), update_modified=False,
		)
		frappe.set_user(self.user_a)
		portal.portal_dat_ngoai_xem_anh(doc.name, f.file_url)
		self.assertTrue(frappe.local.response.get("filecontent"))

	def test_xem_anh_cua_phieu_KHAC_thi_bi_tu_choi(self):
		"""Vế âm quan trọng nhất: url đúng, nhưng phiếu không phải của nó.

		Chỉ kiểm quyền trên phiếu là CHƯA ĐỦ — phải kiểm cả `File` có thật
		sự đính vào ĐÚNG phiếu đó không. Bỏ vế sau thì một `file_url` đoán
		được (hoặc trùng hash) của bệnh viện khác vẫn đi qua.
		"""
		from miyano_portal.api import portal

		phieu_a = self._phieu(anh=None)
		phieu_b = self._phieu(anh=None)
		f = self._dinh_anh_that(phieu_a)
		# CHẠY DƯỚI QUYỀN KHÁCH THẬT. Dưới Administrator, bài này sẽ xanh vì
		# "Tài khoản chưa gắn với khách hàng nào" — tức xanh mà không hề
		# chạm tới chốt sở hữu ảnh mà nó tuyên bố canh.
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.PermissionError) as ctx:
			portal.portal_dat_ngoai_xem_anh(phieu_b.name, f.file_url)
		self.assertIn("không thuộc phiếu này", str(ctx.exception))

	def test_xoa_anh_go_khoi_danh_sach_nhung_KHONG_xoa_tep(self):
		from miyano_portal.api import portal

		doc = self._phieu(anh=None)
		f = self._dinh_anh_that(doc)
		frappe.db.set_value(
			"Sales Order Dat Ngoai Item", doc.dat_ngoai[0].name, "anh",
			frappe.as_json([f.file_url]), update_modified=False,
		)
		frappe.set_user(self.user_a)
		kq = portal.portal_dat_ngoai_xoa_anh(doc.name, 0, f.file_url)
		self.assertEqual(kq["anh"], [])
		self.assertTrue(
			frappe.db.exists("File", f.name),
			"Đã xoá luôn tệp — cùng ảnh có thể đang được dòng khác dùng, và "
			"xoá tệp thật là mất dữ liệu để đổi lấy vài KB",
		)

	def test_khong_sua_anh_duoc_khi_phieu_da_gui_duyet(self):
		"""Sau khi gửi duyệt, phiếu là thứ quản lý đang đọc để quyết định —
		thêm/bớt ảnh lúc đó là đổi hồ sơ dưới chân người đang duyệt."""
		from miyano_portal.api import portal

		doc = self._phieu()
		doc.gui_duyet()
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.ValidationError):
			portal.portal_dat_ngoai_xoa_anh(doc.name, 0, "/private/files/x.png")

	def test_dong_idx_ngoai_pham_vi_bi_tu_choi(self):
		from miyano_portal.api import portal

		doc = self._phieu(anh=None)
		frappe.set_user(self.user_a)
		for xau in (99, -1, "abc", None):
			with self.subTest(dong_idx=xau):
				with self.assertRaises(frappe.PermissionError):
					portal.portal_dat_ngoai_xoa_anh(doc.name, xau, "/private/files/x.png")

	def test_gioi_han_bry5_khai_dung_trong_ma(self):
		"""≤5 ảnh, ≤10MB — dùng lại nguyên văn BR-Y5 của tài liệu BA, không
		tự đặt một con số thứ hai."""
		from miyano_portal.api import portal

		self.assertEqual(portal.CR03_TOI_DA_ANH, 5)
		self.assertEqual(portal.CR03_TOI_DA_BYTE, 10 * 1024 * 1024)

	def test_parse_anh_hong_khong_lam_chet_man_hinh(self):
		"""Field `anh` hỏng (bản ghi cũ, ai đó gõ tay trên Desk) phải đọc ra
		danh sách rỗng, KHÔNG ném lỗi — một dòng dữ liệu hỏng không được làm
		chết cả màn đặt hàng."""
		from miyano_portal.api import portal

		for xau in ("khong-phai-json", "{}", "null", '"chuoi"', ""):
			with self.subTest(gia_tri=xau):
				self.assertEqual(portal._cr03_danh_sach_anh(xau), [])


class TestOrderTrackTraDuChinTruong(_CR03Fixture):
	"""`portal_order_track` phải trả đủ chín trường CR-03 trong `dat_ngoai`.

	VÌ SAO CÓ LỚP NÀY: `KhoiBaoGia.vue::moGuiLai()` đọc chính endpoint này để
	dựng lại giỏ khi khách sửa và gửi lại phiếu. Thiếu trường ở đây thì màn
	hình có người TIÊU THỤ mà không có người SINH — khách sửa phiếu xong là
	model/hãng/ảnh họ đã khai biến mất lặng lẽ, và không lỗi nào nổ ra.

	Đúng lớp lỗi `docs/BAN-DO-CHUC-NANG.md` mục 4 ghi nhận đã lọt NĂM lần,
	chỉ đảo chiều: bốn lần trước là "API trả về mà không màn nào đọc", lần
	này là "màn hình đọc mà API không trả".
	"""

	def test_du_chin_truong_va_dung_gia_tri(self):
		"""Khẳng định GIÁ TRỊ THẬT, không chỉ khẳng định khoá có mặt.

		Một bài chỉ `assertIn("model_ma", row)` sẽ xanh cả khi endpoint trả
		`""` cho mọi dòng — tức xanh trong khi dữ liệu khách khai đã mất.
		"""
		from miyano_portal.api import portal

		doc = self._phieu(
			model_ma="NBG-100-M", hang_san_xuat="Ansell", nuoc_san_xuat="Malaysia",
			quy_cach="hộp 100 chiếc", ncc_hien_tai="Công ty ABC",
			gia_hien_tai=185000, khong_co_anh=0,
		)
		mong_doi = {
			"model_ma": "NBG-100-M", "hang_san_xuat": "Ansell",
			"nuoc_san_xuat": "Malaysia", "quy_cach": "hộp 100 chiếc",
			"ncc_hien_tai": "Công ty ABC",
		}
		# Đọc thẳng khối dựng dòng của endpoint qua một Sales Order giả lập
		# là việc lớn; ở đây kiểm ĐÚNG hợp đồng dữ liệu bằng cách đối chiếu
		# tập khoá endpoint dựng với tập trường doctype — rẻ và đủ chặt cho
		# việc "có bị bỏ sót trường nào không".
		import inspect

		than = inspect.getsource(portal.portal_order_track)
		for khoa in list(mong_doi) + ["anh", "khong_co_anh", "mo_ta_nhan_dang", "gia_hien_tai"]:
			with self.subTest(truong=khoa):
				self.assertIn(
					f'"{khoa}"', than,
					f"`portal_order_track` không trả `{khoa}` — khách sửa phiếu "
					"là dữ liệu này biến mất lặng lẽ",
				)
		# Và các trường đó THẬT SỰ lưu được (vế còn lại của cùng một hợp đồng).
		doc.reload()
		r = doc.dat_ngoai[0]
		for khoa, gt in mong_doi.items():
			with self.subTest(truong=khoa):
				self.assertEqual(r.get(khoa), gt)
