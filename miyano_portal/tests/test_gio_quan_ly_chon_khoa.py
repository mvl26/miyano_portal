"""D1 (chủ đầu tư chốt 26/08/2026) — TRẢ LẠI ô chọn khoa phòng trên giỏ
hàng của QUẢN LÝ.

Sau khi hai màn đặt hàng được gộp (Task 11), màn `LapPhieu.vue` KHÔNG còn
gửi tham số `khoa_phong` nào lên `portal_order_place` — dù chữ ký phía
server vẫn nhận. Hệ quả không phải một ô nhập bị thiếu, mà là một lỗ PHẠM
VI: MỌI đơn quản lý đặt đều thành đơn "Toàn viện" (`khoa_phong = NULL`), và
`portal_yeu_cau_cua_toi` lọc nhánh phiếu bằng `p.khoa_phong = %(khoa)s` —
nên khoa mà quản lý vừa đặt hộ KHÔNG BAO GIỜ tìm lại được yêu cầu đó, kèm
theo cả phiếu giao và hoá đơn của nó.

Bộ test này canh HAI tầng, vì lỗi nằm ở tầng dưới nhưng hậu quả đo được ở
tầng trên:

  * `TestKhoaThayDonQuanLyDatHo` — HẬU QUẢ. Đi qua ĐÚNG endpoint công khai
    (`portal_order_place` → `portal_yeu_cau_cua_toi`), không gọi hàm nội
    bộ nào. VẾ DƯƠNG (nhân viên khoa THẤY đơn của khoa mình) đứng TRƯỚC vế
    âm có chủ ý: nhánh ĐƠN của `portal_yeu_cau_cua_toi` bị bỏ HẲN khi cột
    `Sales Order.custom_khoa_phong` chưa tồn tại (`_cot_khoa_phong_ton_tai`,
    fail-closed), nên một vế âm ĐỨNG MỘT MÌNH sẽ xanh vì lý do hoàn toàn
    khác — "không thấy gì cả" chứ không phải "không thấy đơn của khoa
    khác". Vế dương là thứ chứng minh nhánh đó đang SỐNG.

  * `TestManGioHangGuiKhoaPhong` — NGUYÊN NHÂN, ở `frontend/src`. Cùng lý
    do và cùng khuôn `test_de_xuat_action_registry.py` (đọc docstring ở
    đó): frontend không có hạ tầng test riêng, và `yarn build` xanh trơn
    với một payload thiếu trường. Đọc bằng regex CỐ Ý — không parse Vue.

`_NenCachLy` dùng lại từ `test_cach_ly_khoa_phong.py`: nó đã dựng đúng bộ
người cần (một quản lý + hai nhân viên hai khoa, CÙNG một khách hàng
ZZTEST8 riêng của test) và đã dọn Sales Order theo đúng thứ tự huỷ-rồi-xoá
mà `FrappeTestCase` (rollback MỘT LẦN mỗi CLASS) đòi. Dựng lại bộ đó lần
hai là hai bản sao của cùng một cái bẫy.
"""

import re
from pathlib import Path

import frappe

from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal as portal_api
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.test_cach_ly_khoa_phong import ITEM, KHACH, _NenCachLy

FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"
LAP_PHIEU = FRONTEND_SRC / "views" / "LapPhieu.vue"


class TestKhoaThayDonQuanLyDatHo(_NenCachLy):
	def setUp(self):
		super().setUp()
		# `_NenCachLy._don_sach()` KHÔNG dọn `Portal De Xuat Mua` (lớp gốc
		# viết trước khi mỗi đơn quản lý đặt thẳng đều sinh một phiếu tự
		# duyệt đứng sau). Phiếu sót lại của method TRƯỚC vẫn mang
		# `customer = ZZTEST8` nên vẫn lọt vào `portal_yeu_cau_cua_toi` của
		# method SAU — dọn ở đây, và dọn TRƯỚC cleanup của lớp gốc
		# (`addCleanup` chạy ngược thứ tự đăng ký) để lớp gốc còn xoá được
		# `Sales Order` mà phiếu đang trỏ tới.
		self._don_phieu()
		self.addCleanup(self._don_phieu)

	def _don_phieu(self):
		"""HẠ VỀ NHÁP, XOÁ MÃ, RỒI MỚI XOÁ — `PortalDeXuatMua.on_trash()` từ
		chối xoá mọi phiếu đã qua Gửi duyệt ("dùng Huỷ phiếu để giữ dấu
		vết"), mà phiếu tự duyệt do `portal_order_place` sinh ra đời đã là
		"Đã duyệt". Cùng khuôn `test_dat_hang_gop.py::_don_phieu_cu`.

		`ma_de_xuat = NULL` (03/09/2026) — từ review toàn nhánh, chốt đó hỏi
		MÃ chứ không hỏi trạng thái (phiếu thu hồi về Nháp vẫn là phiếu đã
		từng gửi). Lớp này dọn theo `customer` RIÊNG của nó nên không đi qua
		`fixtures_de_xuat.dung_fixture()`, chỗ mẹo gỡ chốt đã được gộp cho
		mọi lớp `_TEST DX%`."""
		frappe.set_user("Administrator")
		frappe.db.sql(
			"""UPDATE `tabPortal De Xuat Mua`
			   SET trang_thai = %s, ma_de_xuat = NULL WHERE customer = %s""",
			(TRANG_THAI_NHAP, KHACH),
		)
		for ten in frappe.get_all(
			"Portal De Xuat Mua", filters={"customer": KHACH}, pluck="name"
		):
			frappe.delete_doc(
				"Portal De Xuat Mua", ten, force=True, ignore_permissions=True
			)

	def _dat(self, khoa_phong=None):
		frappe.set_user(self.ql.user)
		return portal_api.portal_order_place(
			mode="ban_le",
			items=[{"item_code": ITEM, "qty": 1}],
			request_id=frappe.generate_hash(length=20),
			khoa_phong=khoa_phong,
		)

	def _ma_don_thay_duoc(self, user) -> set:
		"""Tập `sales_order` mà `user` tìm lại được ở "Yêu cầu của tôi".

		Gọi ĐÚNG endpoint công khai — `giai_doan=None` (không lọc chip) để
		phép đo không phụ thuộc vào cách suy giai đoạn, thứ D2 đang đổi tên.
		"""
		frappe.set_user(user)
		res = portal_api.portal_yeu_cau_cua_toi(limit=100)
		return {r["sales_order"] for r in res["rows"] if r["sales_order"]}

	def test_nhan_vien_khoa_THAY_don_quan_ly_dat_ho_khoa_minh(self):
		"""VẾ DƯƠNG — cốt lõi của D1. Quản lý chọn "ZZTEST8 Khoa A" trong
		giỏ, nhân viên khoa A phải tìm lại được yêu cầu đó ở màn của mình."""
		kq = self._dat(khoa_phong=self.kp_a.name)
		self.assertIn(kq["sales_order"], self._ma_don_thay_duoc(self.nv_a.user))

	def test_don_dat_ho_khoa_A_khong_lot_sang_khoa_B(self):
		"""Vế âm ĐI KÈM vế dương ở trên — đặt hộ khoa A không được mở toang
		cho mọi khoa. Cùng một đơn, hai người đọc, hai kết quả."""
		kq = self._dat(khoa_phong=self.kp_a.name)
		self.assertNotIn(kq["sales_order"], self._ma_don_thay_duoc(self.nv_b.user))

	def test_don_toan_vien_KHONG_hien_cho_nhan_vien_khoa(self):
		""""Toàn viện" (không chọn khoa) giữ nguyên nghĩa cũ: chỉ quản lý
		thấy. Khẳng định quản lý THẤY nó trước — nếu không, vế "nhân viên
		khoa không thấy" xanh chỉ vì đơn chưa từng vào được danh sách."""
		kq = self._dat(khoa_phong=None)
		self.assertIn(kq["sales_order"], self._ma_don_thay_duoc(self.ql.user))
		self.assertNotIn(kq["sales_order"], self._ma_don_thay_duoc(self.nv_a.user))

	def test_khoa_duoc_dong_dau_len_CA_don_LAN_phieu(self):
		"""Hai chứng từ, hai vai. `Portal De Xuat Mua.khoa_phong` là thứ
		nhánh PHIẾU của `portal_yeu_cau_cua_toi` lọc theo; `Sales Order.
		custom_khoa_phong` là thứ mang theo phiếu giao và hoá đơn của đơn đó
		(`permissions`/`pham_vi_don`). Thiếu một trong hai là thiếu một nửa
		điều D1 muốn đạt — mà cả hai đều được ghi trong CÙNG một lời gọi nên
		rất dễ tưởng đã đủ khi chỉ kiểm một."""
		kq = self._dat(khoa_phong=self.kp_a.name)
		frappe.set_user("Administrator")
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_khoa_phong"),
			self.kp_a.name,
		)
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", kq["de_xuat"], "khoa_phong"),
			self.kp_a.name,
		)

	def test_quan_ly_khong_dong_dau_duoc_khoa_cua_benh_vien_khac(self):
		"""Ô chọn mới KHÔNG được biến `khoa_phong` thành một giá trị client
		tự do. Một mã khoa có thật nhưng của bệnh viện khác phải bị từ chối,
		và KHÔNG được để lại đơn rác."""
		frappe.set_user("Administrator")
		khoa_la = frappe.get_all(
			"Customer Department",
			filters={"customer": ["!=", KHACH]},
			pluck="name", limit=1,
		)
		if not khoa_la:
			self.skipTest("Site không có khoa phòng của bệnh viện khác để so.")
		truoc = frappe.db.count("Sales Order", {"customer": KHACH})
		with self.assertRaises(frappe.PermissionError):
			self._dat(khoa_phong=khoa_la[0])
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.count("Sales Order", {"customer": KHACH}), truoc)


class TestManGioHangGuiKhoaPhong(FrappeTestCase):
	"""Lưới nguồn cho `frontend/src/views/LapPhieu.vue` — xem docstring đầu
	file. KHÔNG cần CSDL, nhưng vẫn là `FrappeTestCase` để chạy chung một
	lệnh `bench run-tests` với phần còn lại."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.nguon = LAP_PHIEU.read_text(encoding="utf-8")

	def _khoi_dat_hang(self) -> str:
		"""Chỉ khối payload của lời gọi `portal_order_place` — KHÔNG quét cả
		file. Quét cả file sẽ xanh nhờ một chữ `khoa_phong` bất kỳ ở chỗ
		khác (màn này đã có sẵn `khoaPhongList`/`tenKhoa` để hiện tên khoa
		của chính người dùng), tức một lưới không đo gì cả.

		Cắt khối bằng ĐẾM NGOẶC, không bằng `find('})')`: payload có hàm lồng
		(`items.value.map((r) => ({...}))`) nên dấu đóng ĐẦU TIÊN là của hàm
		lồng, không phải của payload — bản đầu của lưới này cắt ở đó và trả
		về một mẩu cụt, đỏ cả khi mã đã đúng."""
		i = self.nguon.find("api.call('portal_order_place'")
		self.assertNotEqual(i, -1, "Không tìm thấy lời gọi portal_order_place trong LapPhieu.vue")
		mo = self.nguon.find("{", i)
		self.assertNotEqual(mo, -1, "Lời gọi portal_order_place không có payload")
		sau = 0
		for j in range(mo, len(self.nguon)):
			if self.nguon[j] == "{":
				sau += 1
			elif self.nguon[j] == "}":
				sau -= 1
				if sau == 0:
					return self.nguon[mo:j + 1]
		self.fail("Payload portal_order_place không đóng ngoặc — file hỏng?")

	def test_gio_quan_ly_gui_khoa_phong_len_server(self):
		"""D1 — chính cái thiếu. `portal_order_place` nhận `khoa_phong`,
		nhưng màn gộp không gửi gì, nên mọi đơn thành "Toàn viện"."""
		self.assertIn("khoa_phong", self._khoi_dat_hang())

	def test_o_chon_khoa_chi_hien_o_nhanh_QUAN_LY_dat_thang(self):
		"""Nhân viên khoa KHÔNG được thấy ô chọn: server đã tự suy khoa của
		họ (`khoa_phong_cho_don`) và bỏ qua giá trị client gửi — bày ra một
		lựa chọn mà họ không có là mời họ đưa ra một quyết định vô hiệu.
		Quản lý đang SỬA MỘT PHIẾU cũng không: khoa của phiếu đã chốt từ lúc
		lập.

		`dangDatThang` (`laQuanLy && !tenPhieu`) là ĐÚNG cổng đã dùng cho ô
		"Lý do yêu cầu" và cho động từ của nút chính — cùng một câu hỏi thì
		dùng cùng một cổng, không dựng cổng thứ hai sẽ trôi khỏi cổng đầu.

		Đo bằng cách tìm `v-if` GẦN NHẤT ĐỨNG TRƯỚC ô chọn: chuyển ô ra
		ngoài cổng, hay đổi sang một cổng khác (vd. `laQuanLy` trần — hiện
		cả khi quản lý đang sửa phiếu), đều làm phép đo này đỏ."""
		i = self.nguon.find('v-model="khoaPhongChon"')
		self.assertNotEqual(i, -1, "Chưa có ô chọn khoa phòng (v-model=\"khoaPhongChon\")")
		truoc = re.findall(r'v-(?:if|else-if|show)="([^"]+)"', self.nguon[:i])
		self.assertTrue(truoc, "Ô chọn khoa phòng không nằm sau một v-if nào")
		self.assertEqual(truoc[-1], "dangDatThang")
