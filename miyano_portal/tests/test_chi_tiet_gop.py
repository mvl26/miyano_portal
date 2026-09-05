"""Màn chi tiết GỘP (03/09/2026) — hai nửa của MỘT yêu cầu trên một màn.

Trước bản này, chi tiết một yêu cầu nằm ở HAI màn: `DeXuatDetail.vue`
(`/yeu-cau/phieu/:ten`) và `OrderDetail.vue` (`/yeu-cau/don/:name`). Khoa
xin 100, quản lý duyệt 40, Miyano giao 25 — ba con số của MỘT việc, ở hai
trang, nối với nhau bằng một cái link.

Hai bổ sung backend ở đây là thứ làm màn gộp CHẠY ĐƯỢC:
  * `portal_order_track` trả `de_xuat` — vào bằng đường ĐƠN thì phải tìm
    ngược ra phiếu, mà `Sales Order.name` KHÔNG suy ra `Portal De Xuat
    Mua.name` (hai naming khác nhau);
  * `de_xuat_chi_tiet` trả giá/đã giao THEO DÒNG — bảng mặt hàng gộp làm
    một, và phép nối phiếu↔đơn phải làm ở SERVER: `frontend/` không có hạ
    tầng test nào (package.json chỉ có `build`), nên một hàm nối viết bằng
    JS là một hàm không ai canh.
"""

import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import de_xuat, portal
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture
from miyano_portal.tests.test_de_xuat_action_registry import _bo_chu_thich

COMPANY = "Miyano Việt Nam"


def _don_phieu_cu():
	"""Dọn Sales Order test TRƯỚC khi dọn phiếu, và hạ phiếu cũ về Nháp
	TRƯỚC KHI `dung_fixture()` force-delete (`on_trash` chặn xoá phiếu đã
	gửi duyệt). Cùng khuôn `test_yeu_cau_list.py::_don_phieu_cu`."""
	for r in frappe.get_all(
		"Sales Order", filters={"customer": ["like", "_TEST DX%"]},
		fields=["name", "docstatus"],
	):
		if r.docstatus == 1:
			frappe.get_doc("Sales Order", r.name).cancel()
		frappe.delete_doc("Sales Order", r.name, force=True, ignore_permissions=True)
	frappe.db.sql(
		"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
		   WHERE customer LIKE '\\_TEST DX%%'""",
		TRANG_THAI_NHAP,
	)


class TestChiTietGopBackend(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item
		self.quan_ly = self._thanh_vien("dxgop.ql@demo.miyano", "Quản lý", None)
		self.nhan_vien = self._thanh_vien(
			"dxgop.nv@demo.miyano", "Nhân viên khoa", self.khoa_a
		)

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
		contact = frappe.db.get_value("Contact", {"user": email})
		if contact and not frappe.db.exists("Dynamic Link", {
			"parent": contact, "parenttype": "Contact",
			"link_doctype": "Customer", "link_name": self.kh_a,
		}):
			c = frappe.get_doc("Contact", contact)
			c.append("links", {"link_doctype": "Customer", "link_name": self.kh_a})
			c.save(ignore_permissions=True)
		return email

	def _phieu_da_duyet(self, so_luong=10):
		"""Phiếu đi qua ĐƯỜNG DUYỆT THẬT (`de_xuat_duyet.duyet_va_tao_don`),
		KHÔNG gán tay `phieu.sales_order` — gán tay là ghim một trạng thái
		rồi đo lại chính nó, đúng kiểu fixture-che-cổng dự án đã dính bảy
		lần (xem docstring `test_yeu_cau_list.py`)."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"ly_do_yeu_cau": "Hết găng tay cỡ M",
			"items": [{"item_code": self.item, "so_luong_de_xuat": so_luong}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.nhan_vien)
		doc.reload()
		doc.gui_duyet()
		from miyano_portal import de_xuat_duyet
		de_xuat_duyet.duyet_va_tao_don(doc.name, self.quan_ly)
		doc.reload()
		return doc

	def test_order_track_tra_ten_phieu_dung_sau_don(self):
		"""Vào màn bằng đường ĐƠN thì phải tìm ngược ra phiếu — `Sales
		Order.name` không suy ra được `Portal De Xuat Mua.name`."""
		phieu = self._phieu_da_duyet()
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_track(order=phieu.sales_order)
		self.assertEqual(kq["de_xuat"], phieu.name)

	def test_order_track_tra_phan_tram_da_giao(self):
		"""Giai đoạn "Đã giao" đòi `per_delivered >= 100` (Ruling P42) —
		`milestones[delivering].done` KHÔNG thay được: cờ đó là `> 0`, giao
		một thùng cũng bật. Màn gộp dùng giai đoạn này để quyết định thu gọn
		khối "Yêu cầu & duyệt", nên suy sai là thu gọn quá sớm."""
		phieu = self._phieu_da_duyet()
		frappe.db.set_value(
			"Sales Order", phieu.sales_order, "per_delivered", 40,
			update_modified=False,
		)
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_track(order=phieu.sales_order)
		self.assertEqual(float(kq["per_delivered"]), 40.0)

	def test_order_track_don_khong_co_phieu_tra_chuoi_rong(self):
		"""~102 đơn cũ có TRƯỚC luồng duyệt không có phiếu nào đứng sau.
		Trả `""` (không phải thiếu khoá): màn gộp đọc khoá này để quyết
		định có nạp nửa phiếu hay không, và một khoá vắng mặt buộc client
		phải đoán."""
		so = frappe.get_doc({
			"doctype": "Sales Order", "customer": self.kh_a, "company": COMPANY,
			"transaction_date": frappe.utils.today(),
			"delivery_date": frappe.utils.add_days(frappe.utils.today(), 3),
			"items": [{
				"item_code": self.item, "qty": 1, "rate": 1000,
				"delivery_date": frappe.utils.add_days(frappe.utils.today(), 3),
			}],
		}).insert(ignore_permissions=True)
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_track(order=so.name)
		self.assertEqual(kq["de_xuat"], "")

	def test_chi_tiet_tra_gia_va_da_giao_theo_dong(self):
		"""Bảng mặt hàng của màn gộp là MỘT bảng: SL xin / SL duyệt (của
		phiếu) đứng cạnh Đơn giá / Đã giao (của đơn). Phép nối làm ở ĐÂY,
		không ở JS — `frontend/` không có test nào, và đây cũng là truy vấn
		`Sales Order Item` mà hàm này ĐÃ chạy sẵn cho `so_luong_tren_don`
		(Ruling P51), nên không tốn thêm một vòng hỏi CSDL nào."""
		# `delivered_qty` PHẢI khác 0: `frappe._dict` trả `None` cho khoá
		# vắng mặt (không ném lỗi), nên nếu ai lỡ xoá "delivered_qty" khỏi
		# `fields=[...]` của truy vấn, `float(tren_don.delivered_qty or 0)`
		# vẫn ra 0.0 y hệt kỳ vọng cũ — test xanh giả. Chọn 3 (khác 1500 và
		# 15000) để nếu code map nhầm cột thì khẳng định cũng đỏ.
		phieu = self._phieu_da_duyet(so_luong=10)
		frappe.db.set_value(
			"Sales Order Item",
			{"parent": phieu.sales_order, "item_code": self.item},
			{"rate": 1500, "amount": 15000, "delivered_qty": 3},
			update_modified=False,
		)
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=phieu.name)
		dong = next(d for d in kq["items"] if d["item_code"] == self.item)
		self.assertEqual(float(dong["don_gia_tren_don"]), 1500.0)
		self.assertEqual(float(dong["thanh_tien_tren_don"]), 15000.0)
		self.assertEqual(float(dong["da_giao_tren_don"]), 3.0)

	def test_chi_tiet_phieu_chua_co_don_tra_None_khong_phai_0(self):
		"""`0` và "chưa có đơn" là HAI ca khác nhau, đừng gộp — cùng lý do
		`so_luong_tren_don` đã trả `None` (Ruling P51). Một bảng in `0 ₫`
		cho phiếu Chờ duyệt là nói với khoa rằng hàng của họ giá 0."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"ly_do_yeu_cau": "x",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.nhan_vien)
		doc.reload()
		doc.gui_duyet()
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=doc.name)
		dong = kq["items"][0]
		self.assertIsNone(dong["don_gia_tren_don"])
		self.assertIsNone(dong["thanh_tien_tren_don"])
		self.assertIsNone(dong["da_giao_tren_don"])

	# --- Review Task 7a (Critical 1) — `giai_doan` phải là ĐÚNG kết quả của
	# `_sql_giai_doan()`, không phải một bản suy lại ở client. Hai bài dưới
	# đây khớp trực tiếp hai chỗ lệch reviewer đã đối chiếu tay và bắt được
	# trong `ChiTietYeuCau.vue` bản đầu — cả hai đều phải ĐỎ nếu backend
	# thôi không trả `giai_doan`, hoặc trả sai theo đúng lỗi cũ.

	def test_order_track_tra_giai_doan_tu_choi_khi_miyano_tu_choi(self):
		"""Bài canh đúng ca đang hỏng: `status_vi` của một đơn Miyano từ chối
		là "Miyano đã từ chối" (`_so_status_vi_full`), một chuỗi KHÁC hằng
		trạng thái PHIẾU 'Từ chối' — bản suy client cũ so `d.status_vi ===
		'Từ chối'`, không bao giờ khớp, và đơn rơi hết nhánh ra 'da_duyet'.
		`portal_order_track` phải tự trả đúng khoá `giai_doan`, không để
		client đoán lại phép so đó."""
		phieu = self._phieu_da_duyet()
		frappe.db.set_value(
			"Sales Order", phieu.sales_order, "workflow_state", "Từ chối",
			update_modified=False,
		)
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_track(order=phieu.sales_order)
		self.assertEqual(kq["giai_doan"], "tu_choi")

	def test_chi_tiet_giai_doan_phieu_thang_truoc_du_da_co_don(self):
		"""Thứ tự nhánh của `_sql_giai_doan()` là CÓ CHỦ Ý: trạng thái PHIẾU
		thắng trước trạng thái ĐƠN. Một phiếu đang 'Chờ duyệt' dù `sales_
		order` đã có giá trị (ca xin sửa/khớp lại) thì thứ nó đang CHỜ vẫn là
		quản lý, không phải Miyano — phải ra 'cho_duyet', không phải
		'da_duyet' hay giai đoạn nào suy từ đơn."""
		phieu = self._phieu_da_duyet()
		frappe.db.set_value(
			"Portal De Xuat Mua", phieu.name, "trang_thai", "Chờ duyệt",
			update_modified=False,
		)
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=phieu.name)
		self.assertEqual(kq["giai_doan"], "cho_duyet")


class TestManGopTrenRouter(FrappeTestCase):
	"""Đọc `router.js`/thư mục `views` bằng regex — cùng lý do và cùng tiền
	lệ `test_yeu_cau_list.py::TestDuongCuVaSoCua`: frontend không có hạ
	tầng test, và "hai đường trỏ về một màn" không có bước build nào bắt
	được."""

	FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"

	def _router(self) -> str:
		return (self.FRONTEND_SRC / "router.js").read_text(encoding="utf-8")

	def _dong_route(self, path: str) -> str:
		"""Dòng vật lý khai báo route có `path: '<path>'`.

		Review Task 7b (reviewer, thực nghiệm) — bản trước dùng đúng
		`_khoi_route()` hai bước của `TestDuongCuVaSoCua` (đa dòng, DOTALL,
		dừng ở dòng đóng `},` đứng riêng). Ở ĐÂY nó cho XANH GIẢ: hai route
		`order-detail`/`de-xuat-detail` nằm SÁT NHAU, MỖI route MỘT DÒNG,
		không có dòng `},` riêng để dừng — `.*?\n\s*\},?\n` ăn xuyên qua CẢ
		route hàng xóm (và cụm chú thích kế tiếp) trước khi tìm được điểm
		dừng thật (khối `/orders/:name` phía sau). `assertIn("ChiTietYeuCau",
		...)` khi đó khớp vào phần của HÀNG XÓM, không phải route đang kiểm
		— reviewer đã chứng minh bằng cách đổi component của `order-detail`
		sang sai rồi chạy lại: bài vẫn xanh.

		Neo theo DÒNG thay vì tìm ngoặc đóng: một dòng vật lý không thể "ăn"
		sang dòng khác, nên không còn kẽ hở này. Áp dụng ĐÚNG cho hai route
		ở đây (luôn một dòng, theo quy ước Task 7b) — KHÔNG đụng
		`TestDuongCuVaSoCua._khoi_route` (đọc route đa dòng thật, và phần
		lớn khẳng định ở đó là `assertNotIn("component:")` nên ăn rộng sẽ tự
		lộ thành đỏ, không có lỗ như ở đây)."""
		for dong in self._router().splitlines():
			if re.search(r"path:\s*'" + re.escape(path) + r"'", dong):
				return dong
		self.fail(f"router.js không còn khai báo {path}")

	def test_hai_duong_cu_van_con_va_deu_tro_vao_man_gop(self):
		"""Hai đường này nằm trong bookmark của khách VÀ trong link của MỌI
		thông báo tự động đã gửi đi (`api/portal.py::_lien_ket_thong_bao`, chốt
		bởi `test_thong_bao_endpoint.py`). Kế hoạch gộp CỐ Ý không đổi
		đường — đổi là kéo theo một lớp tương thích mà không ai được lợi."""
		for path in ("/yeu-cau/don/:name", "/yeu-cau/phieu/:ten"):
			dong = self._dong_route(path)
			self.assertIn(
				"ChiTietYeuCau", dong,
				f"{path} không trỏ vào màn gộp — hai cửa lại dẫn về hai phòng.",
			)

	def test_hai_man_cu_da_nghi(self):
		"""Còn file là còn đường một route lạc quay lại nửa màn cũ."""
		for ten in ("OrderDetail.vue", "DeXuatDetail.vue"):
			self.assertFalse(
				(self.FRONTEND_SRC / "views" / ten).exists(),
				f"{ten} phải nghỉ (gộp vào ChiTietYeuCau.vue)",
			)

	def test_man_gop_noi_CA_HAI_registry_hanh_dong(self):
		"""Thanh hành động là điểm được nhiều nhất của việc gộp: nhân viên
		khoa và quản lý có hai đường sửa số lượng khác nhau, trước đây nằm ở
		hai màn. Nối thiếu một registry là trả lại đúng cái hố đó.

		Review TOÀN NHÁNH (03/09/2026) — bản trước `assertIn("de-xuat-
		actions", man)` chỉ khớp DÒNG IMPORT. Xoá hai dòng NỐI thật bên
		trong `const hanhDong = computed(...)` để lại `computed(() => [])`,
		tức thanh hành động RỖNG HOÀN TOÀN trên mọi phiếu và mọi đơn — mà
		hai `import` vẫn nằm nguyên đó nên bài vẫn xanh. Một import không
		phải một lời gọi.

		Neo vào CHÍNH khối `hanhDong`: hai hàm lọc phải được GỌI bên trong
		nó. Hình thức `.filter((a) => !a.dacBiet)` phía sau lời gọi thứ hai
		cố ý KHÔNG bị khoá — đó là một quyết định hiển thị riêng (xem chú
		thích ngay trên khối), không phải phần của bất biến "nối cả hai
		registry"."""
		man = (self.FRONTEND_SRC / "views" / "ChiTietYeuCau.vue").read_text(encoding="utf-8")
		self.assertIn("de-xuat-actions", man)
		self.assertIn("don-actions", man)
		khoi = re.search(r"const hanhDong = computed\(.*?\n\]\)", man, re.S)
		self.assertIsNotNone(
			khoi, "ChiTietYeuCau.vue không còn `const hanhDong = computed([...])`"
		)
		for goi in ("hanhDongChoPhep(", "hanhDongDonChoPhep("):
			self.assertIn(
				goi, khoi.group(0),
				f"`{goi}` không được GỌI trong khối `hanhDong` — thanh hành động "
				"mất nguyên một registry (hoặc rỗng hẳn), dù dòng import vẫn còn.",
			)

	def test_man_gop_GIEO_ghi_chu_quan_ly(self):
		"""Một quy tắc mà chốt duy nhất là văn xuôi trong tài liệu thì không
		phải một chốt. `BangMatHang.vue` chỉ GHI vào `ghiChuSua`, không tự
		gieo; quên gieo ở màn cha thì quản lý bấm Duyệt sẽ gửi chuỗi rỗng đè
		lên ghi chú họ viết vòng trước — mất dữ liệu trong im lặng, build
		vẫn xanh.

		Review Task 7b (reviewer, IMPORTANT 2) — bản trước chỉ `assertIn(
		"ghi_chu_quan_ly", man)`: chuỗi đó xuất hiện ít nhất BA lần trong
		file (gieo, so sánh dirty ở `ghiChuDoi()`, ghi vào payload ở
		`nhanDuyet()`), nên xoá ĐÚNG dòng GIEO — chính bug bài này sinh ra để
		chặn — mà vẫn còn hai chỗ kia thì bài vẫn xanh. Neo vào ĐÚNG câu lệnh
		gán `ghiChuSua.value = ...ghi_chu_quan_ly...` (chỉ có MỘT lần gán như
		vậy trong toàn file — hai chỗ còn lại là ĐỌC `ghiChuSua.value[...]`,
		không khớp `\\s*=` ngay sau `.value`)."""
		man = (self.FRONTEND_SRC / "views" / "ChiTietYeuCau.vue").read_text(encoding="utf-8")
		# Review TOÀN NHÁNH (03/09/2026) — khẳng định dưới đây neo vào THÂN
		# hàm `dungLaiDieuChinh()`, tức nó chỉ canh hàm gieo CÒN ĐÚNG. Nó
		# KHÔNG canh việc hàm đó được GỌI. Xoá riêng lời gọi ở nhánh nạp qua
		# đường ĐƠN (`napPhieu()`) thì vào màn bằng link đơn — đường mà MỌI
		# thông báo tự động gửi đi đang dùng — `ghiChuSua` không bao giờ được
		# gieo, quản lý bấm Duyệt gửi chuỗi rỗng đè lên ghi chú vòng trước.
		# Canh CẢ HAI lời gọi, theo HÀM BAO chứ không theo số lần xuất hiện:
		# một phép đếm gộp cả dòng ĐỊNH NGHĨA và sẽ đỏ giả nếu mai này có
		# nhánh nạp thứ ba gọi thêm một lần nữa.
		for ten_ham in ("load", "napPhieu"):
			than = re.search(
				r"async function " + ten_ham + r"\([^)]*\)\s*\{.*?\n\}", man, re.S
			)
			self.assertIsNotNone(
				than, f"Không tìm thấy hàm {ten_ham}() trong ChiTietYeuCau.vue"
			)
			self.assertIn(
				"dungLaiDieuChinh()", than.group(0),
				f"{ten_ham}() không gọi `dungLaiDieuChinh()` — nhánh nạp này để "
				"`ghiChuSua` rỗng, và cú bấm Duyệt kế tiếp xoá trắng ghi chú "
				"quản lý đã viết vòng trước.",
			)
		self.assertRegex(
			man,
			# Bó buộc trong CỬA SỔ 200 ký tự ngay sau lệnh gán, KHÔNG dùng
			# `[\s\S]*?ghi_chu_quan_ly` không giới hạn: tự kiểm thấy bản đó
			# vẫn XANH khi xoá đúng dòng gieo (thay bằng `ghiChuSua.value =
			# {}`) — non-greedy chỉ dừng ở lần khớp ĐẦU TIÊN của
			# `ghi_chu_quan_ly` SAU ĐÓ trong file, kể cả khi lần khớp đó nằm
			# ở một hàm khác hẳn (`ghiChuDoi()`/payload `nhanDuyet()`).
			# Buộc `Object.fromEntries(` đứng NGAY SAU lệnh gán, đúng hình
			# dạng gieo thật, xong mới cho phép `ghi_chu_quan_ly` xuất hiện
			# trong khoảng ngắn kế tiếp.
			r"ghiChuSua\.value\s*=\s*Object\.fromEntries\([\s\S]{0,200}?ghi_chu_quan_ly",
			"ChiTietYeuCau.vue không còn dòng GIEO `ghiChuSua.value = "
			"Object.fromEntries(...ghi_chu_quan_ly...)` — bấm Duyệt sẽ xoá trắng ghi chú "
			"quản lý cũ.",
		)

	def test_hop_thoai_HUY_DON_van_noi_ro_KHONG_HOAN_TAC(self):
		"""Review TOÀN NHÁNH (Important) — "🗑 Huỷ đơn…" mất lời cảnh báo.

		`OrderDetail.vue` (màn cũ, đã nghỉ) mở một hộp thoại RIÊNG cho hành
		động này: *"Đơn sẽ ĐÓNG NGAY, không thể hoàn tác từ phía khách. Vui
		lòng nêu lý do (≥ 10 ký tự) — được gửi kèm email cho Miyano."* kèm
		placeholder gợi ý. Màn gộp đẩy nó qua `ReasonModal` CHUNG với `desc`
		sinh máy móc từ nhãn args, nên tất cả những gì khách còn đọc được là
		*"Lý do huỷ đơn (≥ 10 ký tự) — bắt buộc."* — một câu nói về ĐỊNH
		DẠNG Ô NHẬP, không nói chuyện gì sắp xảy ra.

		Trên CÙNG màn đó, "Xoá" và "Thu hồi để sửa" vẫn có `window.confirm`
		nói rõ hệ quả. Nên huỷ đơn đang là hành động KHÔNG ĐẢO NGƯỢC duy
		nhất chỉ hỏi lý do mà không cảnh báo gì.

		Bài canh CẢ HAI nửa: registry PHẢI mang câu cảnh báo, và màn PHẢI
		truyền nó vào modal. Thiếu nửa nào cũng đưa khách về đúng câu máy
		móc cũ."""
		registry = _bo_chu_thich(
			(self.FRONTEND_SRC / "don-actions.js").read_text(encoding="utf-8")
		)
		muc = [
			d for d in registry.split("{ method:")
			if d.startswith(" 'portal_order_huy'")
		]
		self.assertEqual(
			len(muc), 1,
			"Không thấy (hoặc thấy nhiều hơn một) mục `portal_order_huy` trong "
			"don-actions.js.",
		)
		self.assertIn(
			"không thể hoàn tác", muc[0],
			"Mục 'Huỷ đơn' không còn mang câu cảnh báo KHÔNG HOÀN TÁC — khách "
			"bấm một hành động đóng đơn ngay lập tức mà chỉ được hỏi lý do.",
		)
		self.assertIn(
			"placeholder", muc[0],
			"Mục 'Huỷ đơn' không còn placeholder gợi ý — màn cũ có, và ô trống "
			"không nói được rằng lý do này đi thẳng vào email gửi Miyano.",
		)

		man = (self.FRONTEND_SRC / "views" / "ChiTietYeuCau.vue").read_text(encoding="utf-8")
		self.assertRegex(
			man, r"argModalArg\.value(\?)?\.desc",
			"ChiTietYeuCau.vue không đọc `desc` của mục args — câu cảnh báo nằm "
			"trong registry nhưng không tới được hộp thoại.",
		)
		self.assertRegex(
			man, r"argModalArg\.value(\?)?\.placeholder",
			"ChiTietYeuCau.vue không đọc `placeholder` của mục args.",
		)
		for buoc in (':desc="argModalDesc"', ':placeholder="argModalPlaceholder"'):
			self.assertIn(
				buoc, man,
				f"ReasonModal của thanh hành động không nhận `{buoc}` — hai "
				"computed được khai nhưng không ai hỏi chúng.",
			)

	def test_man_gop_KHONG_tu_suy_giai_doan(self):
		"""Giai đoạn phải do SERVER trả (`_sql_giai_doan()` là định nghĩa duy
		nhất). Một bản suy thứ hai ở client đã trôi khỏi bản gốc ba nhánh
		ngay trong task đầu tiên dùng nó — trong đó có ca đơn BỊ TỪ CHỐI
		hiện badge xanh "Đã duyệt".

		Review Task 7b (reviewer, IMPORTANT 3) — bản trước khoá literal
		`'cho_khach_dong_y'` (một NHÁNH của bản suy cũ), nhưng bug ví dụ
		trong docstring sinh từ nhánh KHÁC (`d.status_vi === 'Từ chối'`). Ai
		khôi phục đúng nhánh gây bug, hoặc chỉ đổi kiểu dấu nháy, vẫn qua
		được `assertNotIn` đó. Đổi sang khẳng định DƯƠNG, neo đúng dòng
		một-liner đọc `giai_doan` từ CẢ HAI nửa: một bản suy lại (bất kể
		nhánh nào) không thể vừa giữ được form này vừa còn logic suy diễn
		riêng, vì `computed()` chỉ còn đúng một biểu thức ngắn — thắt chặt
		hơn hẳn việc cấm một literal đơn lẻ."""
		man = (self.FRONTEND_SRC / "views" / "ChiTietYeuCau.vue").read_text(encoding="utf-8")
		self.assertRegex(
			man,
			r"giaiDoan\s*=\s*computed\(\(\)\s*=>\s*phieu\.value\?\.giai_doan\s*\|\|\s*"
			r"don\.value\?\.giai_doan",
			"ChiTietYeuCau.vue không còn đọc `giai_doan` thẳng từ CẢ HAI nửa "
			"(phieu/don) do server trả — nghi ngờ đang tự suy giai đoạn ở client.",
		)

	def test_man_gop_chayHanhDong_KHONG_tu_hoi_xac_nhan(self):
		"""Review Task 7b (reviewer, IMPORTANT 4) — biến việc đã BẤM THỬ
		TAY (thu hồi phiếu chỉ hỏi xác nhận một lần) thành một chốt tự
		động; thao tác tay không để lại gì, và bug này ĐÃ giao đi một lần.

		Hình dạng bug gốc: một `window.confirm()` bị đặt NHẦM vào
		`chayHanhDong()` — hàm THỰC THI hành động (gọi API, điều hướng) —
		thay vì vào hàm GỌI TRƯỚC nó (`onClickAction()`/`nhanDuyet()`, nơi
		đã có đúng một `window.confirm()` cho mỗi hành động cần hỏi). Nếu
		lặp lại lỗi đó, phiếu "Thu hồi để sửa" sẽ hỏi xác nhận HAI lần (một
		lần ở `onClickAction()`, một lần nữa khi `chayHanhDong()` thực thi
		— hoặc hỏi xác nhận SAU KHI API đã gọi xong, vô nghĩa). Khoá đúng
		hình dạng: trích riêng THÂN hàm `chayHanhDong()` (dừng ở dòng `}`
		đóng đầu tiên, không thụt lề — hàm này không lồng hàm con) rồi cấm
		`window.confirm` xuất hiện bên trong."""
		man = (self.FRONTEND_SRC / "views" / "ChiTietYeuCau.vue").read_text(encoding="utf-8")
		than_ham = re.search(r"async function chayHanhDong\([^)]*\)\s*\{.*?\n\}", man, re.S)
		self.assertIsNotNone(than_ham, "Không tìm thấy hàm chayHanhDong() trong ChiTietYeuCau.vue")
		self.assertNotIn(
			"window.confirm", than_ham.group(0),
			"chayHanhDong() gọi window.confirm() BÊN TRONG hàm THỰC THI — đúng hình dạng "
			"bug gốc (hỏi xác nhận hai lần, hoặc hỏi sau khi API đã gọi xong). "
			"window.confirm() phải nằm ở hàm GỌI TRƯỚC (onClickAction()/nhanDuyet()), "
			"không phải trong chayHanhDong().",
		)

	def test_danh_sach_khong_con_hai_cua_cho_mot_dong(self):
		"""Review Task 8+9 (IMPORTANT) — bản đầu chỉ cấm chuỗi
		`"Đơn hàng</button>"`, tức khoá theo NHÃN HIỂN THỊ: một cửa thứ hai
		mang nhãn khác ("Xem đơn", "Chi tiết đơn"...), hoặc gọi thẳng
		`router.push({ name: 'order-detail' })` từ một chỗ khác trong cùng
		dòng (không qua `moYeuCau()`), vẫn lọt lưới cũ mà không ai biết.

		Khoá đúng bất biến bằng CẤU TRÚC thay vì chữ: route `order-detail`
		chỉ được GỌI đúng MỘT chỗ trong cả file, và chỗ đó phải nằm TRONG
		hàm `moYeuCau()` — tức một dòng có ĐÚNG MỘT hàm quyết định đích, bất
		kể nút nào (nhãn gì) kích hoạt nó. Bắt được cả hai ca lưới cũ bỏ
		sót: thêm nút nhãn khác gọi thẳng route, VÀ thêm một hàm kiểu
		`moDon()` mới gọi route từ ngoài `moYeuCau()`."""
		man = (self.FRONTEND_SRC / "views" / "YeuCauList.vue").read_text(encoding="utf-8")
		so_lan = man.count("name: 'order-detail'")
		self.assertEqual(
			so_lan, 1,
			f"route 'order-detail' xuất hiện {so_lan} lần trong YeuCauList.vue — "
			"phải đúng MỘT chỗ, nếu không một dòng lại có hai đích.",
		)
		than_ham = re.search(r"function moYeuCau\([^)]*\)\s*\{.*?\n\}", man, re.S)
		self.assertIsNotNone(than_ham, "Không tìm thấy hàm moYeuCau() trong YeuCauList.vue")
		self.assertIn(
			"name: 'order-detail'", than_ham.group(0),
			"route 'order-detail' không nằm TRONG moYeuCau() — một cửa khác "
			"đang tự gọi route này, ngoài hàm quyết định đích duy nhất.",
		)
		# Phụ — tín hiệu con người dễ đọc, KHÔNG phải chốt chính (chốt chính
		# là hai khẳng định cấu trúc ở trên). Giữ lại vì nó vẫn đúng và rẻ.
		self.assertNotIn(
			"Đơn hàng</button>", man,
			"YeuCauList.vue còn nút 'Đơn hàng' — hai cửa cho một dòng.",
		)
