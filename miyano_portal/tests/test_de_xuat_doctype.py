"""Guard cấu trúc của `Portal De Xuat Mua` (spec §5.2).

Ba guard ở đây đều là chốt DỮ LIỆU, không phải chốt phân quyền — chốt phân
quyền theo phiên đăng nhập nằm ở endpoint (Task 5) và hook (Task 4). Doctype
không tự biết ai đang gọi nó, nên không giả vờ kiểm điều đó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestDeXuatGuard(FrappeTestCase):
	def setUp(self):
		# FrappeTestCase rollback MỘT LẦN cho cả class → fixture tự dọn phiếu
		# cũ bên trong `dung_fixture`.
		f = dung_fixture(self)
		self.kh_a, self.kh_b = f.kh_a, f.kh_b
		self.khoa_a, self.khoa_b = f.khoa_huyethoc, f.khoa_duoc
		self.item = f.item

	def _phieu(self, customer, khoa_phong, **kw):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": customer, "khoa_phong": khoa_phong,
			"items": kw.pop("items", [
				{"item_code": self.item, "so_luong_de_xuat": 5},
			]),
			**kw,
		})
		return doc

	def test_khoa_phong_phai_thuoc_dung_benh_vien(self):
		"""Khoa của bệnh viện B không gắn được lên phiếu của bệnh viện A."""
		doc = self._phieu(self.kh_a, self.khoa_b)
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert(ignore_permissions=True)
		# KHÔNG dùng assertRaises(ValidationError) trần: frappe.MandatoryError
		# là con của ValidationError nên một phiếu thiếu field bắt buộc cũng
		# làm test này XANH vì lý do hoàn toàn khác.
		self.assertIn("không thuộc", str(ctx.exception))

	def test_khoa_phong_dung_benh_vien_thi_luu_duoc(self):
		"""VẾ DƯƠNG — bắt buộc theo Global Constraints."""
		doc = self._phieu(self.kh_a, self.khoa_a)
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.trang_thai, "Nháp")
		self.assertFalse(doc.ma_de_xuat)


class TestDeXuatVongDoi(FrappeTestCase):
	"""Máy trạng thái §5.4, khoá số lượng gốc §5.3, xoá vs huỷ §5.4b."""

	def setUp(self):
		# `on_trash` chặn xoá phiếu đã gửi (§5.4b) — kể cả `force=True`, vì
		# `force` chỉ bỏ kiểm tra liên kết, KHÔNG bỏ `on_trash` (xem
		# `frappe/model/delete_doc.py`). `FrappeTestCase` rollback MỘT LẦN
		# cho cả class, nên phiếu Chờ duyệt/Đã duyệt/Từ chối của test TRƯỚC
		# trong lớp này còn nằm đó khi test SAU chạy. Hạ chúng về Nháp bằng
		# SQL thô — dọn của CHÍNH lớp này — rồi mới gọi `dung_fixture` (dùng
		# `delete_doc(force=True)`, giờ sẽ thành công vì mọi phiếu đều Nháp).
		# KHÔNG sửa `fixtures_de_xuat.py`: nó dùng chung với Task 2 và các
		# task sau, nới guard ở đó ảnh hưởng cả app, không chỉ lớp test này.
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
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		})
		doc.insert(ignore_permissions=True)
		return doc

	def _cho_duyet(self):
		doc = self._nhap()
		doc.ly_do_yeu_cau = "x"
		doc.gui_duyet()
		return doc

	def _item_khac(self):
		"""Vật tư THỨ HAI — riêng của lớp test này, không đụng
		`fixtures_de_xuat.py` (dùng chung Task 2/4/5/6) — chỉ cần tồn tại
		để đổi `item_code` trên một dòng, không cần đúng nghiệp vụ gì khác.
		"""
		ten = "_TEST DX ITEM 2"
		if not frappe.db.exists("Item", ten):
			frappe.get_doc({
				"doctype": "Item", "item_code": ten, "item_name": ten,
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"stock_uom": "Nos", "is_stock_item": 0,
			}).insert(ignore_permissions=True)
		return ten

	def test_gui_duyet_sinh_ma_va_dong_bang_so_luong(self):
		doc = self._nhap()
		self.assertFalse(doc.ma_de_xuat)
		doc.ly_do_yeu_cau = "Hết găng tay cỡ M"
		doc.gui_duyet()
		self.assertEqual(doc.trang_thai, "Chờ duyệt")
		self.assertTrue(doc.ma_de_xuat)
		self.assertTrue(doc.thoi_diem_gui)

	def test_gui_duyet_thieu_ly_do_thi_chan(self):
		"""§5.2 — `ly_do_yeu_cau` bắt buộc Ở BƯỚC GỬI, không phải lúc lưu nháp."""
		doc = self._nhap()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.gui_duyet()
		self.assertIn("Lý do", str(ctx.exception))

	def test_nhap_luu_duoc_khi_chua_co_ly_do(self):
		"""VẾ DƯƠNG của test trên — bắt điền ngay từ dòng đầu sẽ khiến
		người ta gõ 'abc' cho xong (§5.2)."""
		doc = self._nhap()
		self.assertEqual(doc.trang_thai, "Nháp")

	def test_so_luong_de_xuat_khoa_vinh_vien_sau_khi_gui(self):
		"""§5.3 — không ai sửa được nữa, kể cả quản lý, kể cả Miyano."""
		doc = self._nhap()
		doc.ly_do_yeu_cau = "x"
		doc.gui_duyet()
		doc.items[0].so_luong_de_xuat = 999
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.save(ignore_permissions=True)
		self.assertIn("đã khoá", str(ctx.exception))

	def test_so_luong_duyet_van_sua_duoc_sau_khi_gui(self):
		"""VẾ DƯƠNG — khoá cột đề xuất KHÔNG được khoá luôn cột duyệt."""
		doc = self._nhap()
		doc.ly_do_yeu_cau = "x"
		doc.gui_duyet()
		doc.items[0].so_luong_duyet = 3
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.items[0].so_luong_duyet, 3)

	def test_gui_duyet_roi_them_dong_so_luong_khac_khong_thi_chan(self):
		"""Review vòng 1 — đường lọt #1: `truoc` chỉ chứa dòng CŨ, dòng MỚI
		luôn `d.name not in truoc` nên guard cũ bỏ qua hoàn toàn, cho thêm
		dòng với số lượng đề xuất tuỳ ý sau khi đã gửi duyệt."""
		doc = self._cho_duyet()
		doc.append("items", {"item_code": self.item, "so_luong_de_xuat": 7})
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.save(ignore_permissions=True)
		self.assertIn("Số lượng đề xuất", str(ctx.exception))

	def test_gui_duyet_roi_them_dong_so_luong_khong_thi_duoc(self):
		"""VẾ DƯƠNG của test trên — quản lý VẪN thêm được dòng mới, miễn Số
		lượng đề xuất bằng 0 (dòng khoa xin phải sinh từ lúc Gửi duyệt,
		dòng quản lý thêm không được mạo danh dòng khoa xin).

		I3 (review tổng 19/08) — dòng thêm vào dùng MÃ HÀNG KHÁC
		(`_item_khac()`), không lặp lại `self.item`: từ bản vá I3, hai dòng
		cùng `item_code` bị `validate()` chặn thẳng. Dùng mã trùng ở đây
		vốn chỉ là tiện tay — kịch bản THẬT của §5.3 ("quản lý thêm mặt hàng
		khoa chưa xin") luôn là một mã KHÁC; `_ap_dieu_chinh` cũng chỉ
		`append` khi mã CHƯA có trên phiếu."""
		doc = self._cho_duyet()
		doc.append("items", {"item_code": self._item_khac(), "so_luong_de_xuat": 0})
		doc.save(ignore_permissions=True)
		self.assertEqual(len(doc.items), 2)

	# ---- I3 (review tổng) — hai dòng cùng mã hàng ------------------------
	#
	# Không chỗ nào chặn hai dòng cùng `item_code`, và hậu quả đi vòng qua
	# BA tầng: `api/de_xuat._ap_dieu_chinh` dựng `{d.item_code: d}` nên chỉ
	# dòng CUỐI nhận điều chỉnh; `dat_hang.tao_sales_order` GỘP hai dòng
	# thành một dòng SO; `api/portal._dong_bo_so_luong_duyet_ve_phieu` ghi
	# số ĐÃ GỘP ngược lên CẢ HAI dòng. Phiếu X:6 + X:4 → SO X:10 → quản lý
	# sửa còn 7 → phiếu nói 14, đơn nói 7. Chặn ở tầng THẤP NHẤT
	# (`validate()` của doctype), không ở endpoint.

	def test_hai_dong_cung_ma_hang_bi_chan(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.get_doc({
				"doctype": "Portal De Xuat Mua",
				"customer": self.kh_a, "khoa_phong": self.khoa_a,
				"items": [
					{"item_code": self.item, "so_luong_de_xuat": 6},
					{"item_code": self.item, "so_luong_de_xuat": 4},
				],
			}).insert(ignore_permissions=True)
		self.assertIn("nhiều hơn một dòng", str(ctx.exception))

	def test_hai_dong_khac_ma_hang_van_luu_duoc(self):
		"""VẾ DƯƠNG — chốt chống trùng không được cấm phiếu nhiều mặt hàng."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"items": [
				{"item_code": self.item, "so_luong_de_xuat": 6},
				{"item_code": self._item_khac(), "so_luong_de_xuat": 4},
			],
		}).insert(ignore_permissions=True)
		self.assertEqual(len(doc.items), 2)

	def test_gui_duyet_roi_xoa_dong_da_khoa_thi_chan(self):
		"""Review vòng 1 — đường lọt #2: vòng lặp cũ chỉ chạy trên
		`self.items` HIỆN TẠI nên không bao giờ thấy dòng đã biến mất —
		xoá một dòng đã khoá làm mất số lượng đã khoá KHÔNG DẤU VẾT."""
		doc = self._cho_duyet()
		doc.items = []
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.save(ignore_permissions=True)
		self.assertIn("Không xoá được", str(ctx.exception))

	def test_gui_duyet_roi_doi_item_code_dong_cu_thi_chan(self):
		"""Review vòng 1 — đường lọt #3: guard cũ chỉ so `so_luong_de_xuat`,
		không so `item_code` — đổi mã hàng, giữ nguyên số lượng thì lọt."""
		doc = self._cho_duyet()
		doc.items[0].item_code = self._item_khac()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.save(ignore_permissions=True)
		self.assertIn("Mã hàng", str(ctx.exception))

	def test_xoa_phieu_nhap_duoc(self):
		doc = self._nhap()
		ten = doc.name
		frappe.delete_doc("Portal De Xuat Mua", ten, force=True)
		self.assertFalse(frappe.db.exists("Portal De Xuat Mua", ten))

	def test_khong_xoa_duoc_phieu_da_gui(self):
		"""§5.4b — đã có mã, quản lý đã nhìn thấy → huỷ chứ không xoá."""
		doc = self._nhap()
		doc.ly_do_yeu_cau = "x"
		doc.gui_duyet()
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.delete_doc("Portal De Xuat Mua", doc.name)
		self.assertIn("Huỷ phiếu", str(ctx.exception))

	def test_tu_choi_bat_buoc_ly_do(self):
		doc = self._cho_duyet()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.tu_choi("")
		self.assertIn("Lý do từ chối", str(ctx.exception))

	def test_tu_choi_roi_sua_roi_gui_lai(self):
		"""Cạnh quay lui của §5.4 — mã KHÔNG sinh lại lần hai."""
		doc = self._cho_duyet()
		ma_cu = doc.ma_de_xuat
		doc.tu_choi("Vượt dự toán")
		self.assertEqual(doc.trang_thai, "Từ chối")
		doc.gui_duyet()
		self.assertEqual(doc.trang_thai, "Chờ duyệt")
		self.assertEqual(doc.ma_de_xuat, ma_cu)

	def test_khong_di_tat_tu_nhap_sang_da_duyet(self):
		"""Bare assertRaises KHÔNG đủ ở đây: một phiếu Nháp thiếu field
		bắt buộc ném MandatoryError — con của ValidationError — nên test
		sẽ xanh vì lý do hoàn toàn khác cái nó định canh.
		"""
		doc = self._nhap()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.duyet("Administrator")
		self.assertIn("Không chuyển được phiếu", str(ctx.exception))

	def test_duyet_ghi_du_khoi_truy_vet_va_suy_tu_duyet(self):
		"""`.duyet()` là nơi DUY NHẤT viết `Đã duyệt` — kèm cả khối truy vết
		và `tu_duyet` suy từ `nguoi_duyet == owner`, không nhận từ ngoài."""
		doc = self._cho_duyet()
		doc.duyet("quanly@benhvien.test", tu_cach="Được uỷ quyền", uy_quyen="UQ-001")
		self.assertEqual(doc.trang_thai, "Đã duyệt")
		self.assertEqual(doc.nguoi_duyet, "quanly@benhvien.test")
		self.assertTrue(doc.thoi_diem_duyet)
		self.assertEqual(doc.duyet_voi_tu_cach, "Được uỷ quyền")
		self.assertEqual(doc.uy_quyen, "UQ-001")
		self.assertFalse(doc.tu_duyet)

	def test_duyet_tu_duyet_khi_nguoi_duyet_la_owner(self):
		"""`tu_duyet` là CỜ SUY RA, không nhận từ tham số ngoài — nếu nhận từ
		ngoài, một cờ tự khai đúng lúc cần nhất sẽ không được khai."""
		doc = self._cho_duyet()
		doc.duyet(doc.owner)
		self.assertTrue(doc.tu_duyet)

	def test_huy_tu_cho_duyet(self):
		doc = self._cho_duyet()
		doc.huy()
		self.assertEqual(doc.trang_thai, "Đã huỷ")

	def test_huy_tu_tu_choi(self):
		doc = self._cho_duyet()
		doc.tu_choi("Vượt dự toán")
		doc.huy()
		self.assertEqual(doc.trang_thai, "Đã huỷ")

	def test_huy_duoc_tu_nhap(self):
		"""ĐẢO NGƯỢC khẳng định cũ (`test_khong_huy_duoc_tu_nhap`, bỏ
		03/09/2026 cùng cạnh `Nháp → Đã huỷ`).

		Điều đổi ý kiến: `thu_hoi()` đưa một phiếu ĐÃ gửi duyệt về lại Nháp,
		và `on_trash` (đúng §5.4b) cấm xoá phiếu đã từng gửi. Không có cạnh
		này thì phiếu vừa thu hồi không còn lối ra nào — đường xoá sạch bị
		cấm, đường giữ dấu vết chưa mở. Xem `CHUYEN_HOP_LE` và
		`test_de_xuat_thu_hoi.py::TestThuHoiRoiXoaHoacHuy`.

		Phiếu Nháp CHƯA TỪNG gửi (ca của bài này) cũng huỷ được theo — nới
		rộng có chủ ý, không phải tác dụng phụ bỏ sót: người dùng vẫn xoá
		hẳn được nó (`test_xoa_phieu_nhap_duoc`), huỷ chỉ là lựa chọn thứ
		hai và nó KHÔNG mất gì."""
		doc = self._nhap()
		doc.huy()
		self.assertEqual(doc.trang_thai, "Đã huỷ")
