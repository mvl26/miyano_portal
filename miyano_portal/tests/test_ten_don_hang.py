"""Tên đơn hàng do nhân viên gõ ở giỏ hàng (chủ đầu tư 08/09/2026).

*"khi trong giỏ hàng em thêm 1 trường là tên đơn hàng để nhân viên điền vào
khi đặt hàng, và tên này cũng được hiển thị tại list đơn hàng, tên đơn hàng
có thể dài"*

BÀI QUAN TRỌNG NHẤT Ở ĐÂY LÀ BÀI ĐI QUA CẦU PHIẾU → ĐƠN, và nó khẳng định
GIÁ TRỊ THẬT trong CSDL chứ không phải sự có mặt của một dòng mã. Cây cầu đó
(`de_xuat_duyet.duyet_va_tao_don` / `dat_hang._xay_don`) đã đánh rơi trọn
chín trường CR-03 một lần trong chính phiên này (`999b39d`): lưới regex lúc
ấy XANH vì mã hiển thị có thật, chỉ dữ liệu là không bao giờ tới nơi.

HAI ĐƯỜNG từ CÙNG một giỏ hàng, và cả hai đều phải mang tên đi:
  * nhân viên khoa → `de_xuat_gui_duyet` → quản lý duyệt → `duyet_va_tao_don`;
  * quản lý        → `portal_order_place` → `_dam_bao_phieu_tu_duyet`.
Sửa một nhánh mà quên nhánh kia là đúng một nửa người dùng gõ tên xong không
thấy tên đâu — và không lỗi nào nổ ra.
"""

import json
import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import de_xuat_duyet
from miyano_portal.api import de_xuat as api_de_xuat
from miyano_portal.api import portal as api_portal
from miyano_portal.tests.fixtures_de_xuat import dung_fixture
from miyano_portal.tests.test_de_xuat_duyet import _don_phieu_cu

TEN = "Bổ sung vật tư tiêu hao khoa Huyết học tháng 9/2026 — đợt sau kiểm kê"

FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"


def _bo_chu_thich(ma: str) -> str:
	"""Lột chú thích HTML lẫn JS trước khi soi.

	Chú thích trong các file này GIẢI THÍCH đúng thứ bài dưới tìm ("tên đơn
	hàng", `ten_don_hang`), nên soi bản thô là khớp trúng LỜI GIẢI THÍCH.
	Lớp lỗi này đã lọt nhiều lần trong nhánh — lần gần nhất ở bài canh
	`<details>` của khối dòng thời gian, đo được là bài vẫn xanh khi thẻ thật
	đã bị đổi.
	"""
	ma = re.sub(r"<!--.*?-->", "", ma, flags=re.S)
	return "\n".join(d for d in ma.splitlines() if not d.strip().startswith("//"))


class TestTenDonHangDiTuPhieuSangDon(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# `_don_phieu_cu()` TRƯỚC `dung_fixture()` — bẫy đã ghi sẵn trong
		# `test_de_xuat_duyet.py` và bài này vấp đúng nó: `dung_fixture` xoá
		# phiếu, Frappe LÙI bộ đếm đặt tên, nên phiếu của method sau được cấp
		# LẠI tên của method trước — và Sales Order cũ còn sống với đúng
		# `custom_request_id` đó làm chốt chống trùng đơn (BR-O12) ném
		# "đã được tạo trước đó". Đo được: hai method đầu XANH khi chạy riêng,
		# ĐỎ khi chạy cả lớp. Dọn đơn test trước là cắt đứt đúng dây đó.
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa = f.khoa_huyethoc

	def _phieu_cho_duyet(self, ten_don_hang=TEN):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa,
			"ten_don_hang": ten_don_hang,
			"ly_do_yeu_cau": "cần gấp",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 3}],
		})
		doc.insert(ignore_permissions=True)
		doc.gui_duyet()
		doc.reload()
		return doc

	def test_ten_TOI_DUOC_don_hang_khi_quan_ly_duyet(self):
		"""Cầu phiếu → đơn. Khẳng định GIÁ TRỊ trong CSDL."""
		doc = self._phieu_cho_duyet()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(
			frappe.db.get_value(
				"Sales Order", kq["sales_order"], "custom_ten_don_hang"
			),
			TEN,
			"Tên nhân viên gõ ở giỏ hàng KHÔNG sang tới đơn — nhánh đơn của "
			"danh sách và phía Miyano sẽ không bao giờ thấy tên",
		)

	def test_phieu_KHONG_dat_ten_thi_don_de_rong_khong_no(self):
		"""Tên là tuỳ chọn — một phiếu không tên vẫn phải duyệt được."""
		doc = self._phieu_cho_duyet(ten_don_hang="")
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(
			frappe.db.get_value(
				"Sales Order", kq["sales_order"], "custom_ten_don_hang"
			) or "",
			"",
		)

	def test_ten_DAI_khong_bi_cat(self):
		"""Chủ đầu tư nói rõ *"tên đơn hàng có thể dài"* — lưu tròn, không
		cắt ở một độ dài nào đó rồi im lặng."""
		dai = "Đơn " + ("vật tư tiêu hao " * 7).strip()   # ~119 ký tự
		doc = self._phieu_cho_duyet(ten_don_hang=dai)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(
			frappe.db.get_value(
				"Sales Order", kq["sales_order"], "custom_ten_don_hang"
			),
			dai,
		)


class TestTenDonHangQuaEndpointLuuNhap(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa = f.khoa_huyethoc
		self.nv = self._thanh_vien("tendon.nv@demo.miyano")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _thanh_vien(self, email):
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "TenDon",
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		gia_tri = {"customer": self.kh_a, "vai_tro": "Nhân viên khoa",
		           "khoa_phong": self.khoa, "active": 1}
		ten = frappe.db.get_value("Portal Member", {"user": email}, "name")
		if ten:
			frappe.db.set_value("Portal Member", ten, gia_tri)
		else:
			frappe.get_doc({"doctype": "Portal Member", "user": email,
			                **gia_tri}).insert(ignore_permissions=True)
		return email

	def _nhap(self):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa,
		})
		doc.insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.nv,
		                    update_modified=False)
		frappe.set_user(self.nv)
		return doc.name

	def test_luu_nhap_GHI_ten_va_chi_tiet_TRA_lai(self):
		ten = self._nhap()
		api_de_xuat.de_xuat_luu_nhap(ten, ten_don_hang=TEN)
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", ten, "ten_don_hang"), TEN
		)
		self.assertEqual(api_de_xuat.de_xuat_chi_tiet(ten).get("ten_don_hang"), TEN)

	def test_XOA_TRANG_ten_thi_ten_cu_KHONG_song_lai(self):
		"""`de_xuat_luu_nhap` coi `None` là "đừng đụng vào field này". Một ô
		vừa bị xoá trắng phải gửi xuống chuỗi RỖNG, không phải `null` — nếu
		không thì tên cũ sống lại sau khi lưu, và người dùng xoá mãi không
		được. Bài này canh nửa SERVER của luật đó; nửa client (`?? ''` ở
		`LapPhieu.vue`) do `TestGiaoDienTenDonHang` canh."""
		ten = self._nhap()
		api_de_xuat.de_xuat_luu_nhap(ten, ten_don_hang=TEN)
		api_de_xuat.de_xuat_luu_nhap(ten, ten_don_hang="")
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", ten, "ten_don_hang") or "", ""
		)

	def test_danh_sach_yeu_cau_TRA_ten_o_nhanh_PHIEU(self):
		"""*"tên này cũng được hiển thị tại list đơn hàng"* — nửa SERVER."""
		ten = self._nhap()
		api_de_xuat.de_xuat_luu_nhap(ten, ten_don_hang=TEN)
		kq = api_portal.portal_yeu_cau_cua_toi(limit=50)
		dong = [r for r in kq["rows"] if r.get("de_xuat") == ten]
		self.assertTrue(dong, "Phiếu vừa lập không có trong danh sách yêu cầu")
		self.assertEqual(dong[0].get("ten_don_hang"), TEN)


class TestTenDonHangDuongQuanLyDatThang(FrappeTestCase):
	"""Đường THỨ HAI từ cùng giỏ hàng: quản lý bấm "Đặt hàng" một phát ra đơn
	(`portal_order_place`), KHÔNG qua phiếu chờ duyệt.

	Bài này khẳng định GIÁ TRỊ ở CẢ HAI chứng từ đường đó sinh ra — đơn VÀ
	phiếu tự duyệt đứng sau nó (§5.5: mọi đơn đều có đúng một chứng từ đề
	nghị). Lưới regex ở `TestGiaoDienTenDonHang` chỉ chứng minh màn hình GỬI
	tên đi; nó không nói được tên có TỚI NƠI không — đúng khoảng cách đã để
	lọt chín trường CR-03 một lần trong phiên này.
	"""

	def setUp(self):
		from miyano_portal.setup.seed_demo import seed_demo

		seed_demo()
		frappe.set_user("bvbm@demo.miyano")
		self.addCleanup(frappe.set_user, "Administrator")
		self.bo = api_portal.portal_contracts()[0]["name"]

	def test_ten_TOI_DUOC_ca_don_LAN_phieu_tu_duyet(self):
		res = api_portal.portal_order_place(
			self.bo, json.dumps([{"item_code": "VT0005", "qty": 10}]),
			request_id=frappe.generate_hash(length=12),
			ten_don_hang=TEN,
		)
		self.assertEqual(
			frappe.db.get_value(
				"Sales Order", res["sales_order"], "custom_ten_don_hang"
			),
			TEN,
			"Quản lý đặt thẳng: tên không sang tới ĐƠN",
		)
		self.assertEqual(
			frappe.db.get_value(
				"Portal De Xuat Mua", res["de_xuat"], "ten_don_hang"
			),
			TEN,
			"Quản lý đặt thẳng: tên không sang tới PHIẾU tự duyệt — mở lại "
			"yêu cầu để sửa sẽ thấy ô tên trống",
		)

	def test_KHONG_dat_ten_van_dat_duoc_hang(self):
		"""Tên là tuỳ chọn ở mọi đường — không được biến thành cửa chặn."""
		res = api_portal.portal_order_place(
			self.bo, json.dumps([{"item_code": "VT0005", "qty": 10}]),
			request_id=frappe.generate_hash(length=12),
		)
		self.assertTrue(res.get("sales_order"))
		self.assertEqual(
			frappe.db.get_value(
				"Sales Order", res["sales_order"], "custom_ten_don_hang"
			) or "",
			"",
		)


class TestGiaoDienTenDonHang(FrappeTestCase):
	"""Lưới regex — frontend không có hạ tầng test JS."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.gio = _bo_chu_thich(
			(FRONTEND_SRC / "views" / "LapPhieu.vue").read_text(encoding="utf-8")
		)
		cls.ds = _bo_chu_thich(
			(FRONTEND_SRC / "views" / "YeuCauList.vue").read_text(encoding="utf-8")
		)

	def test_gio_hang_co_O_NHAP_ten(self):
		self.assertRegex(
			self.gio, r'v-model="tenDonHang"',
			"Giỏ hàng không có ô nhập tên đơn hàng",
		)

	def test_gio_hang_gui_ten_o_CA_HAI_duong_dat(self):
		"""Nhân viên khoa lưu nháp (`de_xuat_luu_nhap`) và quản lý đặt thẳng
		(`portal_order_place`) là HAI đường từ cùng một giỏ. Thiếu một đường
		là đúng một nửa người dùng gõ tên xong mất tên."""
		self.assertRegex(
			self.gio, r"ten_don_hang:\s*tenDonHang\.value\s*\?\?\s*''",
			"Đường LƯU NHÁP không gửi tên (hoặc gửi `|| null` — xem bài "
			"`test_XOA_TRANG_ten_thi_ten_cu_KHONG_song_lai`: `null` làm tên cũ "
			"sống lại khi người dùng xoá trắng ô)",
		)
		self.assertRegex(
			self.gio, r"ten_don_hang:\s*tenDonHang\.value\s*\|\|\s*null",
			"Đường QUẢN LÝ ĐẶT THẲNG (`portal_order_place`) không gửi tên",
		)

	def test_gio_hang_NAP_LAI_ten_khi_mo_phieu_cu(self):
		"""Mở lại phiếu nháp mà ô tên trống trơn thì lần lưu kế tiếp xoá mất
		tên đã gõ — mất dữ liệu im lặng."""
		self.assertRegex(
			self.gio, r"tenDonHang\.value = d\.ten_don_hang",
			"Không nạp lại tên khi mở phiếu cũ",
		)

	def test_danh_sach_hien_ten_o_CA_HAI_bo_cuc(self):
		"""Danh sách có HAI nhánh render: bảng (desktop) và thẻ (điện thoại).
		Sửa một nhánh mà quên nhánh kia là đúng một nửa người dùng không thấy
		tên — và người dùng bệnh viện phần lớn đứng ở nhánh điện thoại."""
		i_bang = self.ds.find("<table>")
		i_the = self.ds.find("MOBILE") if "MOBILE" in self.ds else -1
		# Chú thích đã bị lột, nên cắt theo mốc CODE: thẻ điện thoại là nhánh
		# `v-else` sau khối bảng.
		i_the = self.ds.find("</table>")
		self.assertNotEqual(i_bang, -1, "Không tìm thấy bảng desktop")
		self.assertNotEqual(i_the, -1, "Không tìm thấy mốc kết thúc bảng")
		bang, the = self.ds[i_bang:i_the], self.ds[i_the:]
		self.assertIn("r.ten_don_hang", bang, "Bảng desktop không hiện tên đơn hàng")
		self.assertIn("r.ten_don_hang", the, "Thẻ điện thoại không hiện tên đơn hàng")

	def test_ten_dai_KHONG_bi_cat_bang_css(self):
		"""*"tên đơn hàng có thể dài"* — cho xuống dòng, KHÔNG `text-overflow:
		ellipsis`/`line-clamp`: cắt là giấu đi đúng thứ người dùng cố ý gõ."""
		for cam in ("text-overflow", "line-clamp", "white-space: nowrap"):
			self.assertNotIn(
				cam, self.ds[self.ds.find(".ten-don"):],
				f"Tên đơn hàng bị cắt bằng `{cam}` — chủ đầu tư nói tên có thể dài",
			)
		self.assertIn(
			"overflow-wrap", self.ds,
			"Tên dài liền mạch sẽ đẩy vỡ bảng nếu không cho ngắt dòng",
		)
