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

	def _phieu(self):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.ctx.kh_a, "khoa_phong": self.ctx.khoa_huyethoc,
			"ly_do_yeu_cau": "Khoa cần vật tư mới",
			"dat_ngoai": [{
				"ten_hang": "Thuốc thử Glucose XYZ", "dvt": "Hộp", "so_luong": 20,
				"anh": _ANH, "model_ma": "GLU-500", "hang_san_xuat": "Roche",
				"nuoc_san_xuat": "Đức", "quy_cach": "hộp 100 test",
				"ncc_hien_tai": "Công ty ABC", "gia_hien_tai": 1250000,
				"ghi_chu": "máy Cobas c311",
			}],
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


class TestGiaoDienKhoiHangMoi(FrappeTestCase):
	"""Lưới regex — không có hạ tầng test JS."""

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

		cls.man_tho = (goc / "views" / "ChiTietYeuCau.vue").read_text(encoding="utf-8")
		cls.man = _bo_chu_thich(cls.man_tho)
		p = goc / "components" / "chi-tiet" / "KhoiHangMoi.vue"
		cls.khoi_tho = p.read_text(encoding="utf-8") if p.exists() else ""
		cls.khoi = _bo_chu_thich(cls.khoi_tho)

	def test_co_component_rieng_khong_nhet_vao_bang_mat_hang(self):
		"""Chủ đầu tư chốt: hiện RIÊNG, không nhét vào bảng.

		Lý do của chính họ: *"hàng này có nhiều trường và là hàng mới cần xem
		xét kĩ"*. Chín trường nhồi vào một hàng của bảng thì hoặc bảng tràn
		ngang, hoặc phải giấu bớt trường — mà giấu bớt đúng là thứ vừa gây ra
		lỗi này.
		"""
		self.assertTrue(self.khoi, "Chưa có `components/chi-tiet/KhoiHangMoi.vue`")

	def test_khoi_doc_tu_PHIEU_khong_doc_tu_DON(self):
		"""Gốc của lỗi: đọc `don.dat_ngoai` thì ở "Chờ duyệt" không có gì.

		Đơn hàng chỉ tồn tại SAU khi duyệt. Đọc từ đơn là đúng lúc quản lý
		cần nhìn nhất thì không thấy gì.
		"""
		self.assertRegex(
			self.man, r"<KhoiHangMoi[^>]*:dong\s*=\s*\"phieu\??\.dat_ngoai",
			"`KhoiHangMoi` không nhận dòng từ `phieu.dat_ngoai`",
		)

	def test_khoi_nam_NGOAI_luoi_hai_cot_hai_bang_xep_DOC(self):
		"""`KhoiHangMoi` phải nằm NGOÀI `.grid2`, không phải con của nó.

		Chủ đầu tư báo 05/09/2026: *"hiển thị 2 bảng dọc chứ không phải
		ngang"*. `.grid2` là lưới HAI CỘT `2fr 1fr` (style.css). Đặt khối này
		làm con đầu tiên của lưới khiến nó chiếm cột RỘNG, đẩy `BangMatHang`
		sang cột HẸP 1fr, và làm khối giao hàng/hoá đơn rớt xuống hàng sau.

		Cả hai đều là bảng nhiều cột: đặt cạnh nhau thì cột nào cũng chật và
		mắt phải nhảy ngang giữa hai lưới khác nhau để đọc cùng một đơn.

		Bài này canh THỨ TỰ VỊ TRÍ trong file — `KhoiHangMoi` phải xuất hiện
		TRƯỚC thẻ mở `<div class="grid2">`. Canh sự tồn tại của chuỗi thì
		không phát hiện được gì: cả hai đều đã tồn tại suốt lúc bố cục hỏng.
		"""
		i_khoi = self.man.find("<KhoiHangMoi")
		i_luoi = self.man.find('<div class="grid2">')
		self.assertNotEqual(i_khoi, -1, "Không tìm thấy `<KhoiHangMoi>`")
		self.assertNotEqual(i_luoi, -1, "Không tìm thấy `<div class=\"grid2\">`")
		self.assertLess(
			i_khoi, i_luoi,
			"`KhoiHangMoi` đang nằm TRONG `.grid2` — hai bảng sẽ hiện NGANG "
			"cạnh nhau và bảng mặt hàng bị bóp vào cột hẹp 1fr",
		)

	def test_hien_du_chin_truong_cr03(self):
		for truong in ("model_ma", "hang_san_xuat", "nuoc_san_xuat", "quy_cach",
		               "ncc_hien_tai", "gia_hien_tai", "mo_ta_nhan_dang"):
			with self.subTest(truong=truong):
				self.assertIn(truong, self.khoi, f"Khối không hiện `{truong}`")

	def test_truong_xep_theo_LUOI_nhan_gia_tri_khong_phai_day_chip(self):
		"""Bốn trường "thông tin trên hộp" xếp thành LƯỚI nhãn/giá trị.

		Bản trước xếp chúng thành `<span class="tag">Model: X</span>` cạnh
		nhau — mọi trường cùng một sức nặng thị giác, nhãn và giá trị cùng cỡ
		cùng màu, nên mắt phải đọc từng chữ mới tách được đâu là nhãn đâu là
		dữ liệu. Chủ đầu tư yêu cầu sắp xếp lại 05/09/2026.

		`<dl>/<dt>/<dd>` không chỉ là trình bày: nó nói với trình đọc màn hình
		rằng đây là cặp nhãn-giá trị, thứ một dãy `<span>` không nói được.
		"""
		self.assertIn("<dl", self.khoi, "Các trường không xếp thành lưới nhãn/giá trị")
		self.assertIn("<dt>", self.khoi)
		self.assertIn("<dd>", self.khoi)

	def test_moi_kich_thuoc_deu_CO_GIAN_khong_ghim_px(self):
		"""Chủ đầu tư 05/09/2026: *"tất cả những gì hiển thị đều phải scale
		theo màn hình"*.

		Bài này canh khối `<style scoped>` KHÔNG còn kích thước ghim bằng
		`px`. Lý do không chỉ là màn hẹp: `rem` co giãn theo cỡ chữ người
		dùng đặt trong trình duyệt, thứ `px` bỏ qua hoàn toàn — một điều
		dưỡng để cỡ chữ lớn vì mắt kém sẽ thấy chữ to ra mà khung ảnh thì
		không, và bố cục vỡ.

		Ảnh trước đây ghim `96px`: tràn trên điện thoại nhỏ, phí chỗ trên màn
		rộng. Nay `minmax(min(100%, 7rem), 1fr)` + `aspect-ratio`.
		"""
		import re

		i = self.khoi_tho.find("<style")
		self.assertNotEqual(i, -1, "Component không có khối <style> riêng")
		style = self.khoi_tho[i:]
		# `1px`/`2px` cho ĐƯỜNG VIỀN được phép: viền không phải kích thước bố
		# cục, và một đường kẻ nửa rem thì mờ nhoè. Chỉ cấm px ở các thuộc
		# tính CHIẾM CHỖ.
		xau = re.findall(
			r"(?:width|height|min-width|max-width|padding|margin|gap|font-size)\s*:[^;]*?\d+px",
			style,
		)
		self.assertEqual(
			xau, [],
			f"Còn kích thước ghim bằng px trong <style>: {xau}. Dùng rem/%/clamp() "
			"để bố cục co giãn theo cả bề ngang màn hình LẪN cỡ chữ người dùng đặt.",
		)

	def test_anh_xem_qua_endpoint_rieng_khong_tro_thang_private_files(self):
		"""Role `Customer` có ZERO DocPerm — đường `/private/files/…` mặc định
		của Frappe sẽ 403 với chính người vừa tải ảnh lên."""
		self.assertIn("portal_dat_ngoai_xem_anh", self.khoi)
		self.assertNotIn("/private/files/", self.khoi)
