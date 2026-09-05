"""Quản lý duyệt phải NHÌN THẤY các dòng "hàng chưa có trong hệ thống".

Chủ đầu tư báo 05/09/2026: *"lúc thêm dòng hàng chưa có trong hệ thống,
quản lý duyệt không thấy — chỉ có những mặt hàng đã có"*.

Đây là lỗi nặng nhất trong loại của nó: quản lý **duyệt một thứ họ không
nhìn thấy**. Và với CR-03 vừa xong, nhân viên còn khai model, hãng, quy
cách, ảnh nhãn hộp — không ai đọc được gì trong số đó.

NGUYÊN NHÂN (đã lần ra, không suy đoán): `BangMatHang.vue` đọc
`props.don?.dat_ngoai` — tức từ ĐƠN HÀNG. Nhưng đơn hàng chỉ tồn tại SAU khi
duyệt; ở "Chờ duyệt" chỉ có PHIẾU. Nên đúng khoảnh khắc quản lý bấm duyệt,
các dòng đó vô hình.

Đây là lần thứ BẢY dự án này vấp cùng một gốc mà `docs/BAN-DO-CHUC-NANG.md`
mục 4 ghi nhận: dữ liệu có, người tiêu thụ có, nhưng hai bên không gặp nhau.
"""

import re

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import de_xuat
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

_ANH = '["/private/files/_test_cr05.jpg"]'


class TestEndpointTraDongHangMoi(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.ctx = dung_fixture(self)
		# `de_xuat_chi_tiet` đi qua `_phieu_cua_toi()` -> `get_portal_member()`.
		# Chạy dưới Administrator sẽ ném "Tài khoản chưa gắn với khách hàng
		# nào" TRƯỚC khi tới thứ bài này canh — và một bài đỏ vì lý do đó
		# trông y hệt một bài đỏ vì tính năng hỏng.
		self.nv = self._thanh_vien(
			"_test_cr05@miyano-test.local", self.ctx.kh_a, self.ctx.khoa_huyethoc
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _thanh_vien(self, email, customer, khoa_phong):
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "CR05",
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		gia_tri = {"customer": customer, "vai_tro": "Nhân viên khoa",
		           "khoa_phong": khoa_phong, "active": 1}
		ten = frappe.db.get_value("Portal Member", {"user": email}, "name")
		if ten:
			frappe.db.set_value("Portal Member", ten, gia_tri)
		else:
			frappe.get_doc({"doctype": "Portal Member", "user": email,
			                **gia_tri}).insert(ignore_permissions=True)
		return email

	def _phieu(self, **dong_dat_ngoai):
		"""Mặc định là dòng hợp lệ nhất có thể (đã có ảnh) — bài cần một biến
		thể (VD "không có ảnh") tự truyền đè qua `dong_dat_ngoai`."""
		dong = {
			"ten_hang": "Thuốc thử Glucose XYZ", "dvt": "Hộp", "so_luong": 20,
			"anh": _ANH, "model_ma": "GLU-500", "hang_san_xuat": "Roche",
			"nuoc_san_xuat": "Đức", "quy_cach": "hộp 100 test",
			"ncc_hien_tai": "Công ty ABC", "gia_hien_tai": 1250000,
			"ghi_chu": "máy Cobas c311",
		}
		dong.update(dong_dat_ngoai)
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.ctx.kh_a, "khoa_phong": self.ctx.khoa_huyethoc,
			"ly_do_yeu_cau": "Khoa cần vật tư mới",
			"dat_ngoai": [dong],
		})
		doc.insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.nv,
		                    update_modified=False)
		doc.reload()
		frappe.set_user(self.nv)
		return doc

	def test_chi_tiet_phieu_TRA_dong_dat_ngoai(self):
		"""Không trả thì màn hình không có gì để hiện, dù người dùng đã khai."""
		doc = self._phieu()
		kq = de_xuat.de_xuat_chi_tiet(doc.name)
		self.assertIn("dat_ngoai", kq, "`de_xuat_chi_tiet` không trả `dat_ngoai`")
		self.assertEqual(len(kq["dat_ngoai"]), 1)

	def test_tra_du_CHIN_TRUONG_CR03_khong_chi_ten_va_so_luong(self):
		"""Chín trường CR-03 là LÝ DO khối này tồn tại.

		Chủ đầu tư nói rõ: *"hàng này có nhiều trường và là hàng mới cần xem
		xét kĩ trước khi duyệt"*. Trả mỗi tên + số lượng là trả lại đúng tình
		trạng trước CR-03, chỉ khác chỗ hiện.

		Khẳng định GIÁ TRỊ THẬT, không chỉ khẳng định khoá có mặt: một bài
		`assertIn("model_ma", row)` vẫn xanh khi endpoint trả chuỗi rỗng cho
		mọi dòng — tức xanh trong khi dữ liệu khách khai đã mất.
		"""
		doc = self._phieu()
		r = de_xuat.de_xuat_chi_tiet(doc.name)["dat_ngoai"][0]
		mong_doi = {
			"ten_hang": "Thuốc thử Glucose XYZ", "dvt": "Hộp",
			"model_ma": "GLU-500", "hang_san_xuat": "Roche",
			"nuoc_san_xuat": "Đức", "quy_cach": "hộp 100 test",
			"ncc_hien_tai": "Công ty ABC", "anh": _ANH,
		}
		for k, v in mong_doi.items():
			with self.subTest(truong=k):
				self.assertEqual(r.get(k), v)
		self.assertEqual(float(r.get("so_luong") or 0), 20.0)
		self.assertEqual(float(r.get("gia_hien_tai") or 0), 1250000.0)

	def test_tra_ca_khong_co_anh_va_mo_ta_nhan_dang(self):
		"""Hai trường CÒN LẠI trong chín trường CR-03 (`khong_co_anh`,
		`mo_ta_nhan_dang`) — bài trên chỉ canh bảy trường của dòng CÓ ảnh,
		không bật cờ "không có ảnh" nên không chứng minh được hai trường này.

		`de_xuat_chi_tiet` trả THẲNG `doc.as_dict()` (không hand-build từng
		khoá như `portal_order_track`, xem `api/portal.py` dòng ~1750), nên
		VỀ LÝ THUYẾT hai trường này roundtrip sẵn — bài này CHỨNG MINH bằng
		dữ liệu thật, không dừng ở suy luận từ đọc code (đúng bẫy "dữ liệu
		có, người tiêu thụ có, hai bên không gặp nhau" mà docstring đầu file
		này cảnh — chỉ khác chỗ nay là tự kiểm phía SINH, không phải phía
		TIÊU THỤ)."""
		doc = self._phieu(
			anh=None, khong_co_anh=1,
			mo_ta_nhan_dang="Hộp giấy trắng, chữ đỏ, logo tam giác",
		)
		r = de_xuat.de_xuat_chi_tiet(doc.name)["dat_ngoai"][0]
		self.assertEqual(bool(r.get("khong_co_anh")), True)
		self.assertEqual(r.get("mo_ta_nhan_dang"), "Hộp giấy trắng, chữ đỏ, logo tam giác")


class TestGiaoDienKhoiHangMoi(FrappeTestCase):
	"""Lưới regex — không có hạ tầng test JS.

	CR-05 gộp bảng (05/09/2026, chủ đầu tư: *"anh chưa ưng hiển thị 2 bảng
	xem hàng sau khi tạo phiếu"*) — kiến trúc ĐỔI: `KhoiHangMoi.vue` không
	còn đứng RIÊNG ngoài bảng (điều lớp test này canh TRƯỚC ĐÂY); nó ĐỔI VAI
	thành nội dung xổ của MỘT dòng trong `BangMatHang.vue`. Các bài dưới sửa
	lại ĐÚNG kiến trúc mới nhưng giữ NGUYÊN sức canh: vẫn phải đọc từ PHIẾU
	(không phải ĐƠN), vẫn phải hiện đủ chín trường CR-03, vẫn phải xem ảnh
	qua endpoint riêng — cộng thêm hai bài MỚI cho hai chốt của lần gộp này:
	nhãn "hàng mới" phải NỔI, và cột tồn kho của dòng đó phải gạch ngang
	(không phải 0).
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		import re
		from pathlib import Path

		goc = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"
		def _bo_chu_thich(ma: str) -> str:
			"""Lột CẢ chú thích HTML LẪN chú thích JS `//`.

			Chú thích ở đây GIẢI THÍCH vì sao không được trỏ thẳng
			`/private/files/…`, nên nó chứa đúng chuỗi mà bài dưới cấm. Chỉ
			lột chú thích HTML là bài tự đỏ vì lời giải thích của chính nó —
			đúng lớp lỗi "khớp chỗ nói thay cho chỗ dùng" mà nhánh này đã trả
			giá BA lần trong phiên.
			"""
			ma = re.sub(r"<!--.*?-->", "", ma, flags=re.S)
			return "\n".join(
				d for d in ma.splitlines() if not d.strip().startswith("//")
			)

		cls._bo_chu_thich = staticmethod(_bo_chu_thich)
		cls.man_tho = (goc / "views" / "ChiTietYeuCau.vue").read_text(encoding="utf-8")
		cls.man = _bo_chu_thich(cls.man_tho)
		p = goc / "components" / "chi-tiet" / "KhoiHangMoi.vue"
		cls.khoi_tho = p.read_text(encoding="utf-8") if p.exists() else ""
		cls.khoi = _bo_chu_thich(cls.khoi_tho)
		b = goc / "components" / "chi-tiet" / "BangMatHang.vue"
		cls.bang_tho = b.read_text(encoding="utf-8") if b.exists() else ""
		cls.bang = _bo_chu_thich(cls.bang_tho)

	def _than_v_for_bang(self) -> str:
		"""Thân `v-for="row in dong"` của `BangMatHang.vue` — cùng kỹ thuật
		`test_cr04_giao_dien.py::TestBangMatHangCanCuKho._than_v_for`: mốc bắt
		đầu là chính `v-for`, mốc kết thúc là `datNgoaiDaKhop` (khối "Đã khớp
		mã" luôn đứng SAU vòng lặp dòng hàng chính trong template)."""
		i_mo = self.bang.find('v-for="row in dong"')
		self.assertNotEqual(i_mo, -1, 'Không tìm thấy v-for="row in dong" trong BangMatHang.vue')
		i_cuoi = self.bang.find("datNgoaiDaKhop", i_mo)
		self.assertNotEqual(i_cuoi, -1, "Không tìm thấy mốc kết thúc (datNgoaiDaKhop)")
		return self.bang[i_mo:i_cuoi]

	def test_component_khoi_hang_moi_ton_tai(self):
		"""`KhoiHangMoi.vue` vẫn phải tồn tại — nó ĐỔI VAI (nội dung xổ tại
		dòng), không nghỉ hưu. Chín trường CR-03 vẫn phải render ở ĐÚNG một
		chỗ (không chép lại lần hai trong `BangMatHang.vue`)."""
		self.assertTrue(self.khoi, "Chưa có `components/chi-tiet/KhoiHangMoi.vue`")

	def test_khoi_hang_moi_khong_con_dung_rieng_ngoai_bang(self):
		"""Chốt MỚI 05/09/2026 đảo NGƯỢC chốt cũ (`b4d3325`): MỘT bảng, không
		hai. `ChiTietYeuCau.vue` không còn dùng `<KhoiHangMoi>` như một khối
		đứng riêng cạnh `BangMatHang` — nó phải nằm BÊN TRONG `BangMatHang.vue`
		(dòng xổ tại chỗ), test kế tiếp canh đúng vị trí đó."""
		self.assertNotIn(
			"<KhoiHangMoi", self.man,
			"ChiTietYeuCau.vue vẫn còn dùng <KhoiHangMoi> đứng riêng — "
			"đúng hai bảng chủ đầu tư báo chưa ưng (05/09/2026)",
		)

	def test_bang_mat_hang_nhan_prop_phieu(self):
		"""`BangMatHang` phải nhận được `phieu` — nó tự đọc `phieu.dat_ngoai`
		để dựng dòng hàng mới, không ai truyền `dat_ngoai` rời cho nó nữa."""
		m = re.search(r"<BangMatHang\b[^>]*>", self.man, re.S)
		self.assertIsNotNone(m, "Không tìm thấy thẻ <BangMatHang> trong ChiTietYeuCau.vue")
		self.assertRegex(
			m.group(0), r':phieu\s*=\s*"phieu"',
			"<BangMatHang> không truyền prop phieu — dòng hàng mới sẽ RỖNG VĨNH VIỄN",
		)

	def test_khoi_hien_dung_ben_trong_v_for_cua_bang(self):
		"""`<KhoiHangMoi>` phải được GỌI THẬT bên trong thân vòng lặp dòng
		hàng của `BangMatHang.vue` — canh CHỖ DÙNG, không phải canh dòng
		import suông (import mà không dùng vẫn là "hai bảng" y hệt cũ, chỉ
		khác chỗ đứng của khối rỗng)."""
		than = self._than_v_for_bang()
		self.assertIn(
			"<KhoiHangMoi", than,
			"Không tìm thấy <KhoiHangMoi> được gọi bên trong v-for của BangMatHang.vue",
		)

	def test_khoi_doc_tu_PHIEU_khong_doc_tu_DON(self):
		"""Gốc của lỗi (`b4d3325` vá): đọc `don.dat_ngoai` thì ở "Chờ duyệt"
		không có gì, vì đơn hàng chỉ tồn tại SAU khi duyệt.

		Sau khi gộp bảng, nơi tính dòng hàng mới chuyển từ `ChiTietYeuCau.vue`
		sang `BangMatHang.vue` (computed `dongHangMoi`) — bài này dời theo
		đúng chỗ, KHÔNG canh gián tiếp qua chỗ gọi component con nữa (chỗ đó
		nay chỉ truyền `row._dat_ngoai`, một object đã tính sẵn, không còn
		chuỗi `phieu.dat_ngoai`/`don.dat_ngoai` để mà canh)."""
		i0 = self.bang.find("const dongHangMoi = computed")
		self.assertNotEqual(i0, -1, "Không tìm thấy `dongHangMoi` trong BangMatHang.vue")
		i1 = self.bang.find("const dong = computed", i0)
		self.assertNotEqual(i1, -1, "Không tìm thấy mốc kết thúc `const dong = computed`")
		self.assertLess(i0, i1)
		than = self.bang[i0:i1]
		self.assertRegex(
			than, r"props\.phieu\??\.dat_ngoai",
			"`dongHangMoi` không đọc `props.phieu.dat_ngoai`",
		)
		self.assertNotRegex(
			than, r"props\.don\b|\bdon\??\.dat_ngoai\b",
			"`dongHangMoi` đọc từ ĐƠN (`don`) — đúng lỗi gốc: ở \"Chờ duyệt\" "
			"đơn luôn null nên dòng hàng mới sẽ vô hình đúng lúc quản lý cần "
			"nhìn nhất",
		)

	def test_hien_du_chin_truong_cr03(self):
		"""Chín trường CR-03 là LÝ DO khối này tồn tại — kiểm ĐỦ CHÍN, không
		chỉ bảy như bài gốc (thiếu `khong_co_anh`/`anh`)."""
		for truong in ("model_ma", "hang_san_xuat", "nuoc_san_xuat", "quy_cach",
		               "ncc_hien_tai", "gia_hien_tai", "khong_co_anh",
		               "mo_ta_nhan_dang", "anh"):
			with self.subTest(truong=truong):
				self.assertIn(truong, self.khoi, f"Khối không hiện `{truong}`")

	def test_anh_xem_qua_endpoint_rieng_khong_tro_thang_private_files(self):
		"""Role `Customer` có ZERO DocPerm — đường `/private/files/…` mặc định
		của Frappe sẽ 403 với chính người vừa tải ảnh lên."""
		self.assertIn("portal_dat_ngoai_xem_anh", self.khoi)
		self.assertNotIn("/private/files/", self.khoi)

	def test_nhan_hang_moi_noi_bat_trong_bang(self):
		"""Nhãn "hàng mới" phải NỔI — đó là dòng quản lý cần xem kỹ NHẤT.

		Đòi một `<span class="badge ...">` (không phải chữ thường/`.tag`)
		mang đúng chữ "hàng mới", VÀ không dùng lại đúng class của badge
		"Quản lý thêm" (`b-purple`) — hai loại dòng khác hẳn nhau (một dòng
		là "quản lý tự thêm vào đơn", một dòng là "nhân viên khai hàng chưa
		có mã") phải phân biệt được bằng mắt, không lẫn thành một màu."""
		than = self._than_v_for_bang()
		# `re.IGNORECASE` — KHÔNG tự liệt kê [Hh][Aà]ng: "HÀNG" (IN HOA, cho
		# "nổi") dùng chữ "À" (U+00C0) chứ không phải "A" thường, một class
		# ký tự tay dễ bỏ sót biến thể hoa/thường có dấu.
		m = re.search(r'<span[^>]*class="badge[^"]*"[^>]*>[^<]*hàng mới', than, re.IGNORECASE)
		self.assertIsNotNone(
			m, 'Không tìm thấy badge NỔI mang nhãn "hàng mới" trong thân v-for của BangMatHang.vue',
		)
		self.assertNotIn(
			"b-purple", m.group(0),
			'Badge "hàng mới" không được dùng chung class với badge "Quản lý thêm" (b-purple)',
		)

	def test_hang_moi_khong_co_item_code_de_ton_kho_tu_gach_ngang(self):
		"""Cột tồn kho (CR-04) đọc qua `canCu(row)` = `canCuKho[row.item_code]`.

		Dòng hàng mới KHÔNG được gán `item_code` — đó là cách DUY NHẤT đảm
		bảo `canCu(row)` trả về `undefined` (gạch ngang "—", đúng nghĩa
		"không tra được") thay vì vô tình khớp một mã tồn kho có thật, hoặc
		tệ hơn, đổi ý nghĩa gạch ngang thành "0" (hết hàng — SAI hoàn toàn
		với "hàng mới, chưa có trong kho")."""
		i0 = self.bang.find("const dongHangMoi = computed")
		self.assertNotEqual(i0, -1, "Không tìm thấy `dongHangMoi` trong BangMatHang.vue")
		i1 = self.bang.find("const dong = computed", i0)
		self.assertNotEqual(i1, -1, "Không tìm thấy mốc kết thúc `const dong = computed`")
		than = self.bang[i0:i1]
		self.assertNotRegex(
			than, r"item_code\s*:",
			"Dòng hàng mới bị gán `item_code` — sẽ làm hỏng gạch ngang CR-04 "
			"(có thể vô tình khớp một mã thật, hoặc hiện SỐ THẬT thay vì "
			'"chưa có trong kho")',
		)

	def test_cot_ton_kho_cua_hang_moi_khong_bi_ep_thanh_0(self):
		"""VẾ ÂM bổ sung — cấm mọi nhánh ĐẶC CÁCH cho `_la_hang_moi` bên trong
		bốn cột CR-04 mà tự tay in ra "0" (dù literal hay qua `Number(...||0)`)
		thay vì đi qua đúng `canCu(row)`/`fmtSl`/`fmtNgay` như hàng có mã.
		"0" nghĩa "hết hàng" — một khẳng định SAI cho hàng chưa từng có mã."""
		than = self._than_v_for_bang()
		self.assertNotRegex(
			than, r"_la_hang_moi[^\n]*[?:][^\n]*\b0\b",
			'Có nhánh đặc cách theo `_la_hang_moi` ép cột tồn kho ra "0" thay vì gạch ngang',
		)

	def test_hang_moi_xo_san_khi_cho_duyet(self):
		"""§2 việc gộp bảng — dòng hàng mới XỔ SẴN khi phiếu "Chờ duyệt" (đúng
		lúc quản lý phải xét), THU LẠI ở trạng thái khác. Quản lý không được
		bắt bấm thêm một lần mới thấy thứ mình phải duyệt.

		So khớp `'Chờ duyệt'` (đóng ngoặc kép NGAY sau chữ) để KHÔNG lẫn với
		`'Chờ duyệt sửa'` — hằng trạng thái khác đã dùng ở `coCotXinSua` cùng
		file, chỉ khác một chữ "sửa" ở cuối."""
		self.assertRegex(
			self.bang, r"trang_thai\s*===\s*'Chờ duyệt'",
			"Không tìm thấy điều kiện mặc định XỔ SẴN theo trạng thái "
			"'Chờ duyệt' cho dòng hàng mới trong BangMatHang.vue",
		)
