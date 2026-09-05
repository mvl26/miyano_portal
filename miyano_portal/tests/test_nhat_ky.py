"""Sổ nhật ký thao tác — luật CHỈ-THÊM và luật KHÔNG-NÉM-LỖI.

Một bản ghi ở đây là một câu khẳng định về QUÁ KHỨ. Sửa nó là nói dối về
quá khứ, nên doctype chặn cả sửa lẫn xoá — kể cả từ Desk của nhân sự
Miyano, kể cả `ignore_permissions`.

Luật thứ hai quan trọng ngang: ghi nhật ký KHÔNG ĐƯỢC ném lỗi ra ngoài.
Nó được gọi ngay sau những chuyển trạng thái đã thành công (`gui_duyet`,
`duyet`, hook giao hàng…); một trục trặc ở khâu ghi mà cuốn theo cả
transaction sẽ làm mất đúng thứ vừa làm được. Cùng ràng buộc tuyệt đối mà
`portal_thong_bao_khach.bao_*` đang chịu.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import nhat_ky
from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestNhatKyChiThem(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item

	def _ghi(self, **kw):
		return nhat_ky.ghi(
			nhat_ky.SK_KHOA_GUI_DUYET,
			customer=self.kh_a, khoa_phong=self.khoa_a,
			de_xuat=self._phieu(), vai=nhat_ky.VAI_KHOA,
			**kw,
		)

	def _phieu(self):
		# `self.item` lấy trong setUp, KHÔNG gọi lại `dung_fixture()` ở đây:
		# hàm đó XOÁ SẠCH mọi phiếu `_TEST DX%` mỗi lần chạy, nên gọi lại
		# giữa chừng là tự xoá dữ liệu bài test vừa dựng — và triệu chứng sẽ
		# nổ ra ở một bài khác, khó lần ngược.
		if not getattr(self, "_ten_phieu", None):
			doc = frappe.get_doc({
				"doctype": "Portal De Xuat Mua",
				"customer": self.kh_a, "khoa_phong": self.khoa_a,
				"items": [{"item_code": self.item, "so_luong_de_xuat": 1}],
			}).insert(ignore_permissions=True)
			self._ten_phieu = doc.name
		return self._ten_phieu

	def test_ghi_duoc_mot_dong(self):
		ten = self._ghi(ghi_chu="Hết găng tay")
		self.assertTrue(ten)
		d = frappe.get_doc(nhat_ky.DOCTYPE, ten)
		self.assertEqual(d.su_kien, nhat_ky.SK_KHOA_GUI_DUYET)
		self.assertEqual(d.vai, nhat_ky.VAI_KHOA)
		self.assertEqual(d.customer, self.kh_a)
		self.assertTrue(d.thoi_diem)

	def test_nguoi_thao_tac_mac_dinh_la_phien_dang_goi(self):
		"""Người thao tác là NGƯỜI ĐANG GỌI tại khoảnh khắc đó — không phải
		thứ người gọi phải nhớ truyền vào. Bắt mỗi chỗ gọi tự truyền là tạo
		ra một chỗ để quên, và quên ở đây nghĩa là một dòng nhật ký không
		có ai."""
		ten = self._ghi()
		self.assertEqual(
			frappe.db.get_value(nhat_ky.DOCTYPE, ten, "nguoi_thao_tac"),
			frappe.session.user,
		)

	def test_vai_he_thong_khong_gan_nguoi(self):
		"""VẾ ÂM của bài trên. `don_tao` là việc của HỆ THỐNG — gán tên
		người đang chạy vào đó là vu cho họ một thao tác họ không làm."""
		ten = nhat_ky.ghi(
			nhat_ky.SK_DON_TAO, customer=self.kh_a,
			de_xuat=self._phieu(), vai=nhat_ky.VAI_HE_THONG,
		)
		self.assertFalse(
			frappe.db.get_value(nhat_ky.DOCTYPE, ten, "nguoi_thao_tac")
		)

	def test_khong_sua_duoc_dong_da_ghi(self):
		ten = self._ghi()
		d = frappe.get_doc(nhat_ky.DOCTYPE, ten)
		d.ghi_chu = "sửa lại"
		with self.assertRaises(frappe.ValidationError) as ctx:
			d.save(ignore_permissions=True)
		self.assertIn("chỉ ghi thêm", str(ctx.exception))

	def test_khong_xoa_duoc_dong_da_ghi(self):
		ten = self._ghi()
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.delete_doc(nhat_ky.DOCTYPE, ten, force=True, ignore_permissions=True)
		self.assertIn("không xoá được", str(ctx.exception))

	def test_phai_gan_vao_mot_chung_tu(self):
		"""Một dòng nhật ký không gắn vào phiếu lẫn đơn là một dòng không ai
		đọc tới được."""
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({
				"doctype": nhat_ky.DOCTYPE, "customer": self.kh_a,
				"su_kien": nhat_ky.SK_DON_TAO, "vai": nhat_ky.VAI_HE_THONG,
				"thoi_diem": frappe.utils.now_datetime(),
			}).insert(ignore_permissions=True)

	def test_ghi_hong_KHONG_nem_loi_ra_ngoai(self):
		"""Ràng buộc tuyệt đối. Hàm này chạy ngay sau những chuyển trạng
		thái ĐÃ THÀNH CÔNG; ném lỗi ở đây là cuốn theo cả transaction và
		làm mất đúng thứ vừa làm được.

		KHÔNG chỉ khẳng định `ghi()` trả None — bài đó xanh y hệt nếu ai đó
		lỡ xoá lời gọi `frappe.log_error` bên trong, và luật "không rơi im
		lặng" chết mà không ai biết. `tabError Log` khai engine MyISAM (phi
		giao dịch, cùng lưu ý ở test_khoa_phong_theo_khach.py/test_e3_doi_
		soat.py/test_kho_delivery_hook.py) — rollback theo CLASS của
		FrappeTestCase không dọn được bảng này, nên dọn tay cả trước lẫn sau.

		`frappe.log_error(title=...)` đổ vào cột `method` của Error Log (quy
		ước riêng của Frappe) — lọc đúng tiêu đề `ghi()` dùng, không đếm mọi
		dòng Error Log trên site (site test dùng chung, có thể có rác từ
		lượt chạy khác)."""
		tieu_de = f"Nhật ký thao tác: không ghi được sự kiện {nhat_ky.SK_KHOA_GUI_DUYET}"
		frappe.db.delete("Error Log", {"method": tieu_de})
		self.addCleanup(frappe.db.delete, "Error Log", {"method": tieu_de})

		ten = nhat_ky.ghi(
			nhat_ky.SK_KHOA_GUI_DUYET, customer="_KHACH_KHONG_TON_TAI_",
			de_xuat=self._phieu(), vai=nhat_ky.VAI_KHOA,
		)
		self.assertIsNone(ten)

		log = frappe.get_all("Error Log", filters={"method": tieu_de})
		self.assertEqual(
			len(log), 1,
			"ghi() nuot loi nhung khong duoc roi im lang: phai co dung mot dong "
			"Error Log cho lan goi hong nay",
		)


class TestNhatKyKhongLoRaChoKhach(FrappeTestCase):
	"""Lớp chịu lực RIÊNG cho `Portal Nhat Ky Yeu Cau` — tách khỏi
	TestNhatKyChiThem vì không cần fixture (khách/khoa/vật tư), chỉ cần đọc
	`tabDocPerm`.

	Sau bản vá phân loại `Portal Nhat Ky Yeu Cau` vào `KHONG_PHAI_DOCTYPE_KHO`
	trong test_kho_isolation.py, doctype này đứng NGOÀI kho_doctypes() nên
	KHÔNG được TestKhoDocPermConfig (lưới "zero DocPerm cho Customer" chung
	của mọi doctype kho) đo tới nữa — đúng khuôn `Portal Member` (xem
	TestPortalMemberKhongLoRaChoKhach trong test_portal_member.py, và comment
	KÍCH HOẠT PHÂN LOẠI LẠI ngay trên entry của doctype này trong
	test_kho_isolation.py).

	Hỏng ra sao nếu không có lưới riêng: một cú click trong Role Permission
	Manager cấp `read` cho role `Customer` trên `Portal Nhat Ky Yeu Cau`.
	Doctype này không có hook permission_query_conditions/has_permission nào
	(đúng như lý do nó nằm trong KHONG_PHAI_DOCTYPE_KHO — chưa từng được
	thiết kế để khách tự đọc), nên DocPerm đó sẽ là ĐƯỜNG DUY NHẤT quyết định
	quyền: bệnh viện A đọc được lý do từ chối/ghi chú duyệt trong phiếu của
	bệnh viện B qua get_list thẳng trên doctype này — không ai biết cho tới
	khi có người tình cờ phát hiện. Toàn bộ phần còn lại của bộ test vẫn xanh
	vì không có test nào khác động tới doctype này.

	Đọc `tabDocPerm`/`tabCustom DocPerm` THẬT (không đọc file JSON): điều cần
	canh là trạng thái trên CSDL sau khi migrate — cấp quyền qua Role
	Permission Manager tạo `Custom DocPerm`, không đụng vào JSON, nên một bài
	chỉ đọc `portal_nhat_ky_yeu_cau.json` sẽ không bắt được lỗ này."""

	def test_khong_co_docperm_nao_cho_role_customer(self):
		rows = frappe.get_all(
			"DocPerm", filters={"parent": nhat_ky.DOCTYPE, "role": "Customer"}
		)
		self.assertEqual(
			rows, [],
			"Portal Nhat Ky Yeu Cau không được có DocPerm nào cho role Customer "
			"trong JSON — nếu đỏ, ai đó đã thêm quyền đọc trực tiếp cho khách "
			"vào portal_nhat_ky_yeu_cau.json.",
		)

	def test_khong_co_custom_docperm_nao_cho_role_customer(self):
		rows = frappe.get_all(
			"Custom DocPerm", filters={"parent": nhat_ky.DOCTYPE, "role": "Customer"}
		)
		self.assertEqual(
			rows, [],
			"Chưa ai được chỉnh quyền Portal Nhat Ky Yeu Cau qua Role Permission "
			"Manager — nếu đỏ, một Custom DocPerm đã cấp quyền cho role Customer, "
			"mở toang sổ nhật ký của MỌI bệnh viện cho MỌI tài khoản cổng vì "
			"doctype này không có hook cách ly nào đứng sau.",
		)
