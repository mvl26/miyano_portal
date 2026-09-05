"""Nhân viên SỬA được đơn đang ở "Chờ duyệt" — bằng cách THU HỒI về Nháp.

Yêu cầu gốc (chủ đầu tư, 03/09/2026): "NV sửa được đơn ở trạng thái Chờ
duyệt". Cách làm KHÔNG phải nới `_chan_sua_so_luong_de_xuat()` theo trạng
thái, mà là thêm ĐÚNG MỘT cạnh `Chờ duyệt → Nháp`. Lý do nằm ở tầng: guard
đó sống trong `validate()` của doctype vì BỐN đường ghi dùng chung nó
(`de_xuat_luu_nhap`, `_ap_dieu_chinh`, `_dam_bao_phieu_tu_duyet`, desk của
nhân sự Miyano — xem docstring của chính nó). Nới theo trạng thái sẽ mở
luôn cho `_ap_dieu_chinh` sửa `so_luong_de_xuat`/`item_code` ở "Chờ duyệt"
— đúng thứ §5.3 cấm — và tầng doctype KHÔNG phân biệt được người gọi
(mọi đường đều tới với `ignore_permissions=True`).

Thu hồi giữ nguyên guard (nó tự `return` sớm ở "Nháp"), dùng lại màn Đặt
hàng và `de_xuat_luu_nhap` sẵn có, và không mở thêm bề mặt quyền nào.

CHỈ CHỦ PHIẾU thu hồi được — cùng chốt owner-only của `de_xuat_gui_duyet`,
không phải chốt phạm vi mặc định của `_phieu_cua_toi()` (vốn cho cả quản lý
và đồng nghiệp cùng khoa đi qua). Quản lý "thu hồi" phiếu của nhân viên
chính là TỪ CHỐI mà không ghi lý do — mà `de_xuat_tu_choi` đã tồn tại cho
việc đó và nó BẮT BUỘC lý do. Quản lý cũng không mất gì: họ đã sửa được số
lượng tại chỗ qua `dieu_chinh` của `de_xuat_duyet_phieu` (§5.3).
"""

import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import de_xuat
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_CHO_DUYET,
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture
from miyano_portal.tests.test_de_xuat_action_registry import _bo_chu_thich


class TestThuHoiDoctype(FrappeTestCase):
	"""Máy trạng thái §5.4 — cạnh `Chờ duyệt → Nháp` và hệ quả của nó."""

	def setUp(self):
		# `on_trash` chặn xoá phiếu đã gửi duyệt, kể cả `force=True` — hạ
		# phiếu cũ của CHÍNH lớp này về Nháp bằng SQL thô trước khi
		# `dung_fixture()` force-delete. Cùng khuôn `test_de_xuat_doctype.py`.
		frappe.db.sql(
			"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
			   WHERE customer LIKE '\\_TEST DX%%'""",
			TRANG_THAI_NHAP,
		)
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item

	def _nhap(self):
		return frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		}).insert(ignore_permissions=True)

	def _cho_duyet(self):
		doc = self._nhap()
		doc.ly_do_yeu_cau = "Hết găng tay cỡ M"
		doc.gui_duyet()
		return doc

	def test_thu_hoi_dua_phieu_ve_nhap(self):
		doc = self._cho_duyet()
		doc.thu_hoi()
		self.assertEqual(doc.trang_thai, TRANG_THAI_NHAP)

	def test_thu_hoi_roi_sua_duoc_so_luong_de_xuat(self):
		"""ĐÂY là điều cả bản vá tồn tại vì nó. Trước bản này, cột đề xuất
		khoá vĩnh viễn từ lúc Gửi duyệt nên nhân viên gõ nhầm 5 thay vì 50
		chỉ còn hai đường: xin quản lý từ chối, hoặc chờ duyệt rồi xin sửa
		sau khi đã thành đơn."""
		doc = self._cho_duyet()
		doc.thu_hoi()
		doc.items[0].so_luong_de_xuat = 50
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.items[0].so_luong_de_xuat, 50)

	def test_thu_hoi_roi_xoa_duoc_dong(self):
		"""Vế thứ hai của cùng một chốt — guard khoá CẢ việc xoá dòng, nên
		"sửa được" mà vẫn không bỏ được một mặt hàng gõ nhầm là sửa nửa
		vời. Thêm dòng mới đi qua `_chan_trung_ma_hang` chứ không qua guard
		này, nên không cần một bài riêng."""
		doc = self._cho_duyet()
		doc.thu_hoi()
		doc.items = []
		doc.save(ignore_permissions=True)
		self.assertEqual(len(doc.items), 0)

	def test_thu_hoi_xoa_thoi_diem_gui(self):
		"""Một phiếu Nháp KHÔNG được mang thời điểm gửi: màn chi tiết in
		thẳng field này ("Thời điểm gửi: … / Chưa gửi") ngay cạnh badge
		trạng thái, nên giữ lại giờ gửi cũ là để hai dòng trên CÙNG một
		khối truy vết nói ngược nhau. `track_changes` của doctype vẫn giữ
		giá trị cũ trong `Version` — mất trên màn, không mất trong sổ."""
		doc = self._cho_duyet()
		self.assertTrue(doc.thoi_diem_gui)
		doc.thu_hoi()
		self.assertFalse(doc.thoi_diem_gui)

	def test_thu_hoi_giu_ma_de_xuat(self):
		"""Mã sinh ĐÚNG MỘT LẦN (xem `gui_duyet`) — quản lý và khoa đã gọi
		tên phiếu bằng mã đó trong lúc trao đổi. Cùng luật với phiếu bị Từ
		chối rồi gửi lại."""
		doc = self._cho_duyet()
		ma = doc.ma_de_xuat
		self.assertTrue(ma)
		doc.thu_hoi()
		self.assertEqual(doc.ma_de_xuat, ma)

	def test_thu_hoi_roi_gui_lai_duoc_va_giu_ma_cu(self):
		doc = self._cho_duyet()
		ma = doc.ma_de_xuat
		doc.thu_hoi()
		doc.gui_duyet()
		self.assertEqual(doc.trang_thai, TRANG_THAI_CHO_DUYET)
		self.assertEqual(doc.ma_de_xuat, ma)
		self.assertTrue(doc.thoi_diem_gui)

	def test_khong_thu_hoi_duoc_phieu_dang_nhap(self):
		"""Không có cạnh `Nháp → Nháp`: một nút "thu hồi" hiện trên phiếu
		chưa gửi là một nút không trả lời được câu hỏi nó đặt ra."""
		doc = self._nhap()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.thu_hoi()
		self.assertIn("Không chuyển được phiếu", str(ctx.exception))

	def test_khong_thu_hoi_duoc_phieu_da_duyet(self):
		"""Đơn đã sinh ra và đã gửi Miyano — đường sửa của "Đã duyệt" là
		`xin_sua()` (§12 Q4), không phải thu hồi."""
		doc = self._cho_duyet()
		doc.db_set("trang_thai", "Đã duyệt")
		doc.reload()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.thu_hoi()
		self.assertIn("Không chuyển được phiếu", str(ctx.exception))


class TestThuHoiEndpoint(FrappeTestCase):
	"""Chốt quyền của `de_xuat_thu_hoi` — owner-only, CỘNG phạm vi khách
	hàng/khoa mà `_phieu_cua_toi()` đã hỏi."""

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.sql(
			"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
			   WHERE customer LIKE '\\_TEST DX%%'""",
			TRANG_THAI_NHAP,
		)
		f = dung_fixture(self)
		self.kh_a, self.kh_b = f.kh_a, f.kh_b
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item

		self.chu_phieu = self._thanh_vien(
			"dxthuhoi.nv@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_a
		)
		self.dong_nghiep = self._thanh_vien(
			"dxthuhoi.nv2@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_a
		)
		self.quan_ly = self._thanh_vien(
			"dxthuhoi.ql@demo.miyano", self.kh_a, "Quản lý", None
		)
		self.khach_khac = self._thanh_vien(
			"dxthuhoi.khachb@demo.miyano", self.kh_b, "Nhân viên khoa", f.khoa_duoc
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _thanh_vien(self, email, customer, vai_tro, khoa_phong):
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
		return email

	def _phieu_cho_duyet(self, owner):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"ly_do_yeu_cau": "Hết găng tay cỡ M",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", owner)
		doc.reload()
		doc.gui_duyet()
		return doc.name

	def test_chu_phieu_thu_hoi_duoc(self):
		ten = self._phieu_cho_duyet(self.chu_phieu)
		frappe.set_user(self.chu_phieu)
		de_xuat.de_xuat_thu_hoi(ten)
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", ten, "trang_thai"),
			TRANG_THAI_NHAP,
		)

	def test_chu_phieu_thu_hoi_roi_luu_nhap_duoc_so_luong_moi(self):
		"""VẾ DƯƠNG đi hết đường của người dùng thật: thu hồi rồi sửa qua
		ĐÚNG endpoint mà màn Đặt hàng gọi, không phải qua `doc.save()`."""
		ten = self._phieu_cho_duyet(self.chu_phieu)
		frappe.set_user(self.chu_phieu)
		de_xuat.de_xuat_thu_hoi(ten)
		de_xuat.de_xuat_luu_nhap(
			ten, items=[{"item_code": self.item, "so_luong_de_xuat": 50}]
		)
		doc = frappe.get_doc("Portal De Xuat Mua", ten)
		self.assertEqual(doc.items[0].so_luong_de_xuat, 50)

	def test_dong_nghiep_cung_khoa_khong_thu_hoi_duoc(self):
		"""`_phieu_cua_toi()` mặc định cho đồng nghiệp cùng khoa đi qua
		(vòng kiểm chủ sở hữu của nó chấp nhận cả quản lý). Chốt owner-only
		phải là một phép kiểm RIÊNG sau đó — cùng khuôn `de_xuat_gui_duyet`."""
		ten = self._phieu_cho_duyet(self.chu_phieu)
		frappe.set_user(self.dong_nghiep)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_thu_hoi(ten)

	def test_quan_ly_khong_thu_hoi_duoc_phieu_cua_nhan_vien(self):
		"""Quản lý thu hồi phiếu người khác = từ chối mà không ghi lý do.
		`de_xuat_tu_choi` đã có cho việc đó và nó bắt buộc lý do."""
		ten = self._phieu_cho_duyet(self.chu_phieu)
		frappe.set_user(self.quan_ly)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_thu_hoi(ten)

	def test_quan_ly_thu_hoi_duoc_phieu_CUA_CHINH_MINH(self):
		"""VẾ DƯƠNG của bài trên — chốt là CHỦ PHIẾU, không phải "không phải
		quản lý". Một quản lý tự lập phiếu cho mình vẫn là chủ phiếu."""
		ten = self._phieu_cho_duyet(self.quan_ly)
		frappe.set_user(self.quan_ly)
		de_xuat.de_xuat_thu_hoi(ten)
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", ten, "trang_thai"),
			TRANG_THAI_NHAP,
		)

	def test_khach_khac_khong_thu_hoi_duoc(self):
		"""Trục KHÁCH HÀNG — `_phieu_cua_toi()` chặn trước cả chốt owner."""
		ten = self._phieu_cho_duyet(self.chu_phieu)
		frappe.set_user(self.khach_khac)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_thu_hoi(ten)


class TestNutThuHoiTrenRegistry(FrappeTestCase):
	"""Đọc `de-xuat-actions.js` bằng regex — cùng lý do và cùng tiền lệ
	`test_de_xuat_action_registry.py`/`test_yeu_cau_list.py`: frontend
	không có hạ tầng test, và một `when()` lệch quyền không có bước build
	nào bắt được.

	`test_de_xuat_action_registry.py` đã canh rằng `de_xuat_thu_hoi` là
	endpoint CÓ THẬT. Bài này canh vế còn lại: nút chỉ hiện cho người
	server sẽ cho đi qua. Hiện một nút chắc chắn ăn 403 lúc bấm là cách
	nhanh nhất dạy người dùng sợ cả thanh công cụ."""

	REGISTRY = (
		Path(frappe.get_app_path("miyano_portal")).parent
		/ "frontend" / "src" / "de-xuat-actions.js"
	)

	def _muc(self, method: str) -> str:
		"""Mục registry của `method`, đã lọc chú thích. Cùng phép cắt
		`_dong_thu_hoi()` dùng, tách ra vì hai bài dưới hỏi mục KHÁC."""
		noi_dung = _bo_chu_thich(self.REGISTRY.read_text(encoding="utf-8"))
		moc = [
			d for d in noi_dung.split("{ method:")
			if d.startswith(f" '{method}'")
		]
		self.assertEqual(
			len(moc), 1,
			f"Không thấy (hoặc thấy nhiều hơn một) mục `{method}` trong "
			"de-xuat-actions.js.",
		)
		return moc[0]

	def test_nut_XOA_bien_mat_tren_phieu_DA_TUNG_GUI(self):
		"""Hệ quả trực tiếp của việc chốt server đổi từ TRẠNG THÁI sang MÃ
		(review toàn nhánh, Việc 1). `when()` cũ hỏi `trang_thai === 'Nháp'`
		— soi gương chốt CŨ — nên trên một phiếu VỪA THU HỒI (Nháp, đã có
		mã) nút "Xoá" vẫn hiện và giờ CHẮC CHẮN ném lỗi lúc bấm. Đúng thứ
		docstring của chính registry này cấm: "hiện một nút chắc chắn ăn 403
		lúc bấm là cách nhanh nhất dạy người dùng sợ cả thanh công cụ".

		Một `when()` soi gương một chốt server ĐÃ ĐỔI là cùng họ lỗi mà Việc
		5 vừa sửa cho một nút khác — chỉ khác là ở đây nó do CHÍNH bản vá
		Việc 1 sinh ra."""
		muc = self._muc("de_xuat_xoa_nhap")
		# CHIỀU, không chỉ SỰ XUẤT HIỆN: `assertIn("ma_de_xuat", …)` một mình
		# vẫn xanh khi ai đó đảo thành `d.ma_de_xuat` — đúng bug NGƯỢC LẠI,
		# nút Xoá biến mất khỏi mọi phiếu nháp thật. `(?<!!)` chặn đúng chỗ
		# đó: chuỗi `!!d.ma_de_xuat` (điều kiện của nút Huỷ) không được tính
		# là khớp.
		self.assertRegex(
			muc, r"(?<!!)!d\.ma_de_xuat",
			"Nút 'Xoá' không hỏi `!d.ma_de_xuat` — hoặc nó vẫn hiện trên phiếu "
			"vừa thu hồi (nơi server chắc chắn từ chối), hoặc điều kiện bị đảo "
			"và nó biến mất khỏi mọi phiếu nháp thật.",
		)

	def test_nut_HUY_hien_tren_phieu_DA_THU_HOI(self):
		"""Vế còn lại: cạnh `Nháp → Đã huỷ` mở ở doctype và endpoint mà
		`when()` không biết thì đường GIỮ DẤU VẾT vẫn không có cửa nào để
		đi. Quản lý mở một phiếu vừa bị thu hồi phải thấy "Huỷ phiếu" —
		không thì phiếu đó nằm lại vĩnh viễn: xoá thì server cấm (đã từng
		gửi), huỷ thì không có nút.

		CHỈ quản lý, không nới: `de_xuat_huy` là quản lý-only từ §5.4b và
		bản vá này không đụng tới quyền đó."""
		muc = self._muc("de_xuat_huy")
		self.assertIn(
			"'Nháp'", muc,
			"Nút 'Huỷ phiếu' không nhận trạng thái Nháp — phiếu vừa thu hồi "
			"không còn lối ra nào trên giao diện.",
		)
		# CHIỀU, không chỉ SỰ XUẤT HIỆN — cùng lý do bài Xoá ở trên. Ở đây
		# chiều đúng là KHẲNG ĐỊNH (`!!`): nút chỉ hiện khi phiếu ĐÃ có mã.
		self.assertRegex(
			muc, r"!!d\.ma_de_xuat",
			"Nút 'Huỷ phiếu' không hỏi `!!d.ma_de_xuat` — hoặc nó hiện trên MỌI "
			"phiếu Nháp (kể cả phiếu chưa từng gửi, nơi 'Xoá' mới là việc đúng "
			"và hai nút đỏ cạnh nhau là chỗ để bấm nhầm), hoặc điều kiện bị đảo "
			"và phiếu vừa thu hồi lại mất lối ra.",
		)
		self.assertIn(
			"la_quan_ly", muc,
			"Nút 'Huỷ phiếu' thôi hỏi vai trò — `de_xuat_huy` là quản lý-only.",
		)

	def _dong_thu_hoi(self) -> str:
		"""Review TOÀN NHÁNH (03/09/2026) — LỌC CHÚ THÍCH trước khi cắt.

		Bản trước `split("{ method:")` trên TOÀN VĂN THÔ. Chú thích-hoá mục
		"Thu hồi để sửa" (thêm `// ` vào hai dòng) làm nút BIẾN MẤT khỏi
		giao diện mà cả ba bài của lớp này vẫn xanh — đây là lưới canh
		CHÍNH của cả tính năng thu hồi, và nó không đỏ được khi mã hỏng.

		Dùng lại `_bo_chu_thich` của `test_de_xuat_action_registry.py`
		(IMPORT, không chép: hai bản sao của cùng một bộ lọc sớm muộn cũng
		trôi khỏi nhau, đúng luật file kia tự đặt ra cho chính nó). GIỚI HẠN
		THỪA HƯỞNG: nó chỉ bỏ dòng bắt đầu bằng `//`, không hiểu `/* */` —
		một mục bị bọc trong block comment vẫn lọt. Chấp nhận: đó không phải
		hình dạng chú thích nào trong repo này dùng, và bịt nó đòi một trình
		phân tích JS thật."""
		noi_dung = _bo_chu_thich(self.REGISTRY.read_text(encoding="utf-8"))
		moc = [
			d for d in noi_dung.split("{ method:")
			if d.startswith(" 'de_xuat_thu_hoi'")
		]
		self.assertEqual(
			len(moc), 1,
			"Không thấy (hoặc thấy nhiều hơn một) mục `de_xuat_thu_hoi` trong "
			"de-xuat-actions.js — nhân viên không có lối vào việc sửa đơn đang "
			"chờ duyệt.",
		)
		return moc[0]

	def test_nut_chi_hien_o_trang_thai_cho_duyet(self):
		self.assertIn("'Chờ duyệt'", self._dong_thu_hoi())

	def test_nut_chi_hien_cho_CHU_PHIEU(self):
		"""ĐÚNG chốt owner-only của `de_xuat_thu_hoi`. Quản lý và đồng
		nghiệp cùng khoa đi qua được `_phieu_cua_toi()` nhưng bị chốt riêng
		đó chặn — nút hiện cho họ là một nút chỉ biết báo lỗi."""
		self.assertIn("d.owner === me.user", self._dong_thu_hoi())


class TestThuHoiRoiXoaHoacHuy(FrappeTestCase):
	"""Review TOÀN NHÁNH 03/09/2026 (Critical) — hai tính năng đúng riêng lẻ,
	ghép lại thì mất dữ liệu.

	`on_trash` canh §5.4b ("phiếu đã gửi duyệt thì không xoá được, dùng Huỷ
	phiếu để giữ dấu vết") bằng cách hỏi `trang_thai != "Nháp"`. Câu hỏi đó
	chỉ đúng khi "Nháp ⇒ chưa từng gửi" — và `thu_hoi()` (thêm trong chính
	phiên này) PHÁ đúng bất biến ấy: nó đưa một phiếu ĐÃ gửi duyệt về lại
	Nháp. Hai cú bấm `Thu hồi để sửa → Xoá` đi vòng qua chốt và `frappe.
	delete_doc` cuốn theo CẢ `Version` (toàn bộ `track_changes` — chính thứ
	docstring `thu_hoi()` viện dẫn khi nói "giá trị cũ không mất") lẫn
	`Notification Log` trỏ tới chứng từ, còn số của `sinh_ma()` thì thủng
	một lỗ vĩnh viễn trong dãy mã của bệnh viện.

	Không lớp test nào của riêng từng tính năng thấy được điều này: lớp canh
	xoá (`test_de_xuat_doctype`/`test_de_xuat_endpoint`) chưa biết tới thu
	hồi, lớp canh thu hồi (bên trên) chưa hỏi tới xoá.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item
		self.chu_phieu = self._thanh_vien(
			"dxxoa.nv@demo.miyano", "Nhân viên khoa", self.khoa_a
		)
		self.quan_ly = self._thanh_vien("dxxoa.ql@demo.miyano", "Quản lý", None)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _thanh_vien(self, email, vai_tro, khoa_phong):
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
			"customer": self.kh_a, "vai_tro": vai_tro,
			"khoa_phong": khoa_phong, "active": 1,
		}
		if ten_tv:
			frappe.db.set_value("Portal Member", ten_tv, gia_tri)
		else:
			frappe.get_doc({
				"doctype": "Portal Member", "user": email, **gia_tri,
			}).insert(ignore_permissions=True)
		return email

	def _nhap(self):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"ly_do_yeu_cau": "Hết găng tay cỡ M",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.chu_phieu)
		doc.reload()
		return doc

	def _da_thu_hoi(self):
		doc = self._nhap()
		doc.gui_duyet()
		doc.thu_hoi()
		self.assertEqual(doc.trang_thai, TRANG_THAI_NHAP)
		self.assertTrue(doc.ma_de_xuat, "thu_hoi() phải GIỮ mã — dấu 'đã từng gửi'")
		return doc

	def test_thu_hoi_roi_xoa_bi_chan_o_DOCTYPE(self):
		"""Chốt cuối là `on_trash`, nên bài này phải đi thẳng `delete_doc`
		— `force=True` CÓ CHỦ Ý: `force` chỉ bỏ kiểm liên kết, không bỏ
		`on_trash`, và đây đúng là đường mà mọi hàm dọn fixture của app đi."""
		doc = self._da_thu_hoi()
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.delete_doc("Portal De Xuat Mua", doc.name, force=True)
		self.assertIn("Huỷ phiếu", str(ctx.exception))
		self.assertTrue(frappe.db.exists("Portal De Xuat Mua", doc.name))

	def test_thu_hoi_roi_xoa_bi_chan_o_ENDPOINT(self):
		"""Cửa người dùng thật bấm. Chốt ở `de_xuat_xoa_nhap` chỉ để báo lỗi
		dễ hiểu — nhưng nó phải hỏi CÙNG câu hỏi với `on_trash`, nếu không
		hai tầng nói hai luật khác nhau."""
		doc = self._da_thu_hoi()
		frappe.set_user(self.chu_phieu)
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat.de_xuat_xoa_nhap(doc.name)
		self.assertIn("Huỷ phiếu", str(ctx.exception))
		frappe.set_user("Administrator")
		self.assertTrue(frappe.db.exists("Portal De Xuat Mua", doc.name))

	def test_thu_hoi_roi_HUY_duoc_va_phieu_con_nguyen(self):
		"""NGHỊCH LÝ KHÉP KÍN của bản trước: `CHUYEN_HOP_LE[Nháp]` chỉ có
		`{Chờ duyệt}` — không có cạnh sang "Đã huỷ". Đường XOÁ SẠCH thì mở,
		đường GIỮ DẤU VẾT mà chính §5.4b bắt phải dùng thì bất khả thi. Bài
		này canh cạnh mới, ĐI QUA ENDPOINT THẬT (`de_xuat_huy` là quản lý
		-only) chứ không chỉ `doc.huy()`: nếu chỉ cạnh doctype mở mà endpoint
		không với tới được thì người dùng vẫn đứng trước cùng một ngõ cụt."""
		doc = self._da_thu_hoi()
		ma = doc.ma_de_xuat
		frappe.set_user(self.quan_ly)
		de_xuat.de_xuat_huy(doc.name)
		frappe.set_user("Administrator")
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", doc.name, "trang_thai"),
			"Đã huỷ",
		)
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", doc.name, "ma_de_xuat"), ma
		)

	def test_phieu_NHAP_chua_tung_gui_van_xoa_duoc(self):
		"""VẾ DƯƠNG — thiếu bài này thì bản vá có thể khoá cứng MỌI đường
		xoá (VD: đổi `on_trash` thành "không bao giờ xoá") mà không ai biết:
		cả ba bài trên vẫn xanh, và nhân viên gõ nhầm một phiếu nháp thì
		vĩnh viễn không dọn được nó khỏi danh sách của mình."""
		doc = self._nhap()
		self.assertFalse(doc.ma_de_xuat, "Phiếu chưa gửi thì chưa được cấp mã")
		frappe.set_user(self.chu_phieu)
		de_xuat.de_xuat_xoa_nhap(doc.name)
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Portal De Xuat Mua", doc.name))


class TestNutXoaTrenManDatHang(FrappeTestCase):
	"""TẤM GƯƠNG THỨ BA của chốt server mà Việc 1 đổi — ngoài hai registry.

	`LapPhieu.vue` (màn Đặt hàng, `/dat-hang/:ten`) có nút "Xoá phiếu"
	RIÊNG, không đi qua registry nào, và `v-if` của nó chỉ hỏi `tenPhieu`.
	Nó nằm ĐÚNG trên đường đi chính của luồng Thu hồi: nhân viên bấm "Thu
	hồi để sửa" → `ChiTietYeuCau.vue` đẩy thẳng sang `{name: 'dat-hang'}`
	= chính màn này → thấy nút đỏ "Xoá phiếu" → hộp xác nhận hứa "Dữ liệu
	sẽ bị xoá VĨNH VIỄN khỏi hệ thống — KHÔNG thể khôi phục" → bấm OK →
	nhận toast lỗi. Trước Việc 1 nút đó chạy được; sau Việc 1 nó LUÔN
	hỏng. Lối vào thứ hai: `YeuCauList.vue::coTheSuaNhap()` đưa mọi dòng
	giai đoạn `nhap` — kể cả phiếu vừa thu hồi — vào đúng màn này.

	BẪY của bản vá, và lý do lớp này canh việc GÁN chứ không canh việc
	template có nhắc tên ref: `napTuPhieu()` KHÔNG giữ `ma_de_xuat` vào ref
	nào. Viết `v-if="tenPhieu && !maDeXuat"` với một ref chưa bao giờ được
	gán thì điều kiện LUÔN đúng, nút vẫn hiện, và một lưới chỉ tìm chuỗi
	`maDeXuat` trong file vẫn xanh — đúng bài học "một dòng import không
	phải một lời gọi" của Việc 3.
	"""

	MAN = (
		Path(frappe.get_app_path("miyano_portal")).parent
		/ "frontend" / "src" / "views" / "LapPhieu.vue"
	)

	def _than_ham(self, ten: str) -> str:
		noi_dung = self.MAN.read_text(encoding="utf-8")
		moc = re.search(
			r"function " + ten + r"\([^)]*\)\s*\{.*?\n\}", noi_dung, re.S
		)
		self.assertIsNotNone(moc, f"Không tìm thấy hàm {ten}() trong LapPhieu.vue")
		return moc.group(0)

	def test_napTuPhieu_GIU_ma_de_xuat_tu_response(self):
		"""Vế "gán thật". `de_xuat_chi_tiet` trả nguyên `doc.as_dict()` nên
		field có sẵn — thứ thiếu là một dòng giữ nó lại."""
		self.assertRegex(
			self._than_ham("napTuPhieu"),
			r"maDeXuat\.value\s*=\s*d\.ma_de_xuat",
			"napTuPhieu() không giữ `ma_de_xuat` từ response — mọi điều kiện "
			"`v-if` dựa trên nó sẽ đọc một ref rỗng vĩnh viễn và luôn cho nút "
			"'Xoá phiếu' hiện.",
		)

	def test_resetState_DON_ma_de_xuat(self):
		"""Vế NGƯỢC LẠI, cũng hỏng lặng lẽ: `LapPhieu.vue` tái dùng cùng một
		instance khi chỉ `route.params.ten` đổi (xem `watch` của nó). Mở một
		phiếu ĐÃ TỪNG GỬI rồi bấm "Đặt hàng" để lập phiếu MỚI mà không dọn
		ref thì mã cũ ở lại, và nút "Xoá phiếu" biến mất khỏi một phiếu nháp
		hoàn toàn xoá được."""
		self.assertIn(
			"maDeXuat", self._than_ham("resetState"),
			"resetState() không dọn `maDeXuat` — mã của phiếu trước ở lại và "
			"giấu nút 'Xoá phiếu' khỏi phiếu nháp mới.",
		)

	def test_nut_XOA_PHIEU_bien_mat_khi_phieu_da_tung_gui(self):
		"""Vế "template thật sự hỏi". Ba nút Xoá của app giờ hỏi CÙNG một
		câu hỏi mà server hỏi (`ma_de_xuat`), không phải câu hỏi cũ
		(`trang_thai`)."""
		noi_dung = self.MAN.read_text(encoding="utf-8")
		self.assertIn(
			'v-if="tenPhieu && !maDeXuat"', noi_dung,
			"Nút 'Xoá phiếu' trên màn Đặt hàng không hỏi `maDeXuat` — nó vẫn "
			"hiện trên phiếu vừa thu hồi, hứa xoá vĩnh viễn rồi trả về toast lỗi.",
		)
