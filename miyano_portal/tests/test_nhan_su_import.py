"""Nhập nhân sự bệnh viện từ Excel (Task 15) — tests/test_nhan_su_import.py.

Mỗi test dưới đây canh MỘT chốt cụ thể của `miyano_portal/api/nhan_su.py`.
Chốt lớn nhất là bước XEM TRƯỚC: tạo tài khoản đăng nhập là việc khó lùi,
nên "xem trước không ghi gì" được đo bằng cách đếm bản ghi của CẢ NĂM thứ
mà đường cấp tài khoản đụng tới (User, Contact, User Permission, Portal
Member, Customer Department), không phải chỉ hai cái cuối.

FrappeTestCase chỉ rollback MỘT LẦN cho cả lớp, mà `User.insert()` tự
commit bên trong — mọi thứ các test này tạo ra phải được dọn TƯỜNG MINH ở
setUp (dọn trước, không chỉ dọn sau: một lần chạy đứt gánh giữa chừng không
được để lại tài khoản đăng nhập được trên site).
"""

import io

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.password import check_password, update_password
from openpyxl import Workbook

from miyano_portal.api import nhan_su as nhan_su_api

CUST_A = "ZZTEST NS Bệnh viện A"
CUST_B = "ZZTEST NS Bệnh viện B"
CUST_KHONG_MA_NGAN = "ZZTEST NS Bệnh viện C"
DOMAIN = "@zztest.miyano"

HOA = f"hoa{DOMAIN}"
BINH = f"binh{DOMAIN}"
CUC = f"cuc{DOMAIN}"
DUNG = f"dung{DOMAIN}"

HEADERS = [label for label, _ in nhan_su_api.COLUMNS]


def _xlsx_bytes(rows, headers=None):
	wb = Workbook()
	ws = wb.active
	ws.append(headers if headers is not None else HEADERS)
	for row in rows:
		ws.append(row)
	buf = io.BytesIO()
	wb.save(buf)
	return buf.getvalue()


def _row(ho_ten, email, ten_khoa="", ma_khoa="", vai_tro="Nhân viên khoa"):
	return [ho_ten, email, ten_khoa, ma_khoa, vai_tro]


TEP_HOP_LE = [
	_row("Nguyễn Thị Hoa", HOA, vai_tro="Quản lý"),
	_row("Trần Văn Bình", BINH, "Huyết học", "HUYETHOC"),
	_row("Lê Thị Cúc", CUC, "Huyết học", "HUYETHOC"),
]


class _NhanSuTestBase(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._created_files = []
		self._don_sach()
		self.addCleanup(self._don_sach)
		self.addCleanup(frappe.set_user, "Administrator")
		self._tao_khach(CUST_A, "ZZNSA")
		self._tao_khach(CUST_B, "ZZNSB")

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in self._created_files:
			try:
				frappe.delete_doc("File", name, ignore_permissions=True, force=True)
			except Exception:
				pass

	def _don_sach(self):
		frappe.set_user("Administrator")
		khach = [CUST_A, CUST_B, CUST_KHONG_MA_NGAN]
		emails = frappe.get_all("User", filters={"name": ["like", f"%{DOMAIN}"]}, pluck="name")
		if emails:
			frappe.db.delete("User Permission", {"user": ["in", emails]})
			frappe.db.delete("Portal Member", {"user": ["in", emails]})
			frappe.db.delete("User", {"name": ["in", emails]})
		# Contact PHẢI xoá qua delete_doc, KHÔNG phải frappe.db.delete: mỗi
		# tài khoản mới sinh ra HAI Contact (Frappe tự tạo một cái ở
		# `user.py::create_contact`, `portal_provision` tạo thêm bản ghi liên
		# hệ của cổng), và mỗi cái mang bảng con `Contact Email`. Xoá thẳng
		# bảng cha để lại dòng con mồ côi; lần chạy sau, Contact mới trùng
		# tên "hút" lại đám con đó và vỡ ở "Only one Email ID can be set as
		# primary" — một cái bẫy chỉ nổ ở LẦN CHẠY THỨ HAI.
		mo_coi = frappe.get_all("Contact Email", filters={"email_id": ["like", f"%{DOMAIN}"]}, pluck="parent")
		lien_he = frappe.get_all("Contact", filters={"user": ["like", f"%{DOMAIN}"]}, pluck="name")
		for ten in set(mo_coi) | set(lien_he):
			frappe.delete_doc(
				"Contact", ten, force=True, ignore_permissions=True, ignore_missing=True
			)
			frappe.db.delete("Contact Email", {"parent": ten})
			frappe.db.delete("Contact Phone", {"parent": ten})
			frappe.db.delete("Dynamic Link", {"parenttype": "Contact", "parent": ten})
		frappe.db.delete("Portal Member", {"customer": ["in", khach]})
		frappe.db.delete("Customer Department", {"customer": ["in", khach]})
		frappe.db.delete("Dynamic Link", {"parenttype": "Contact", "link_name": ["in", khach]})
		frappe.db.delete("Customer", {"name": ["in", khach]})
		# `User.insert()` tự commit bên trong, nên rác của lần chạy trước ĐÃ
		# nằm ngoài transaction của test — dọn xong phải commit theo, nếu
		# không cú rollback cuối lớp sẽ HOÀN TÁC chính việc dọn này và trả
		# lại nguyên đám tài khoản đăng nhập được cho site.
		frappe.db.commit()

	def _tao_khach(self, ten, ma_ngan=None):
		doc = frappe.get_doc({
			"doctype": "Customer", "customer_name": ten, "customer_type": "Company",
			"customer_group": "All Customer Groups", "territory": "All Territories",
		})
		doc.insert(ignore_permissions=True)
		if ma_ngan:
			frappe.db.set_value("Customer", doc.name, "custom_ma_ngan", ma_ngan)
		return doc.name

	def _upload(self, content: bytes, filename="nhan_su.xlsx", user="Administrator"):
		frappe.set_user(user)
		file_doc = frappe.get_doc({
			"doctype": "File", "file_name": filename, "is_private": 1, "content": content,
		})
		file_doc.insert(ignore_permissions=True)
		self._created_files.append(file_doc.name)
		return file_doc

	def _counts(self):
		"""Đếm CẢ NĂM thứ mà đường cấp tài khoản ghi ra."""
		khach = [CUST_A, CUST_B, CUST_KHONG_MA_NGAN]
		return (
			frappe.db.count("User", {"name": ["like", f"%{DOMAIN}"]}),
			frappe.db.count("Contact", {"user": ["like", f"%{DOMAIN}"]}),
			frappe.db.count("User Permission", {"user": ["like", f"%{DOMAIN}"]}),
			frappe.db.count("Portal Member", {"customer": ["in", khach]}),
			frappe.db.count("Customer Department", {"customer": ["in", khach]}),
		)

	def _dong(self, ket_qua, email):
		for row in ket_qua["rows"]:
			if row["email"] == email:
				return row
		self.fail(f"Không thấy dòng {email} trong kết quả: {ket_qua['rows']}")


class TestXemTruoc(_NhanSuTestBase):
	def test_xem_truoc_khong_ghi_gi(self):
		"""Chốt chính của task: bước xem trước phải LIỆT KÊ mà KHÔNG GHI."""
		f = self._upload(_xlsx_bytes(TEP_HOP_LE))
		before = self._counts()

		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)

		self.assertEqual(before, self._counts(), "xem trước không được ghi gì vào database")
		self.assertEqual(ket_qua["total"], 3)
		self.assertEqual(ket_qua["so_tao_moi"], 3)
		for email in (HOA, BINH, CUC):
			self.assertEqual(self._dong(ket_qua, email)["trang_thai"], "tao_moi")

	def test_xem_truoc_noi_ro_se_tao_khoa_moi(self):
		"""QĐ-G20: khoa chưa có thì tự tạo, nhưng phải NÓI RÕ — gõ nhầm tên
		khoa không được lặng lẽ đẻ ra khoa rác."""
		f = self._upload(_xlsx_bytes(TEP_HOP_LE))
		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)

		# Hai dòng cùng trỏ về một khoa mới -> chỉ báo tạo MỘT khoa.
		self.assertEqual(len(ket_qua["khoa_se_tao"]), 1, ket_qua["khoa_se_tao"])
		self.assertEqual(ket_qua["khoa_se_tao"][0]["ten_khoa_phong"], "Huyết học")
		self.assertEqual(ket_qua["khoa_se_tao"][0]["ma_khoa"], "HUYETHOC")
		self.assertTrue(self._dong(ket_qua, BINH)["khoa_moi"])

	def test_khoa_da_co_thi_dung_lai_khong_tao_them(self):
		kp = frappe.get_doc({
			"doctype": "Customer Department", "customer": CUST_A,
			"ten_khoa_phong": "Huyết học", "ma_khoa": "HUYETHOC",
		}).insert(ignore_permissions=True)
		f = self._upload(_xlsx_bytes(TEP_HOP_LE))
		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)

		self.assertEqual(ket_qua["khoa_se_tao"], [])
		self.assertEqual(self._dong(ket_qua, BINH)["khoa"], kp.name)
		self.assertFalse(self._dong(ket_qua, BINH)["khoa_moi"])


class TestChotHopLe(_NhanSuTestBase):
	def test_nhan_vien_khoa_thieu_khoa_bi_tu_choi_kem_so_dong(self):
		"""Đúng trạng thái kẹt mà task này sinh ra để dẹp."""
		f = self._upload(_xlsx_bytes([
			_row("Nguyễn Thị Hoa", HOA, vai_tro="Quản lý"),
			_row("Trần Văn Bình", BINH),  # Nhân viên khoa, KHÔNG có khoa
		]))
		before = self._counts()
		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)

		dong = self._dong(ket_qua, BINH)
		self.assertEqual(dong["trang_thai"], "tu_choi")
		self.assertEqual(dong["line"], 3)  # 1 = header, 2 = Hoa, 3 = Bình
		self.assertIn("khoa", " ".join(dong["errors"]).lower())
		self.assertEqual(ket_qua["so_tu_choi"], 1)

		# Tất-cả-hoặc-không: một dòng lỗi thì KHÔNG dòng nào được ghi.
		with self.assertRaises(frappe.ValidationError) as cm:
			nhan_su_api.nhan_su_import_commit(CUST_A, f.file_url)
		self.assertIn("dòng 3", str(cm.exception))
		self.assertIn("chưa có dữ liệu nào được ghi", str(cm.exception))
		self.assertEqual(before, self._counts())

	def test_quan_ly_duoc_de_trong_khoa(self):
		"""Quản lý nhìn toàn viện — bỏ trống khoa là HỢP LỆ, không phải lỗi."""
		f = self._upload(_xlsx_bytes([_row("Nguyễn Thị Hoa", HOA, vai_tro="Quản lý")]))
		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)
		self.assertEqual(self._dong(ket_qua, HOA)["trang_thai"], "tao_moi")

		nhan_su_api.nhan_su_import_commit(CUST_A, f.file_url)
		tv = frappe.db.get_value(
			"Portal Member", {"user": HOA}, ["customer", "vai_tro", "khoa_phong", "active"],
			as_dict=True,
		)
		self.assertEqual(tv.customer, CUST_A)
		self.assertEqual(tv.vai_tro, "Quản lý")
		self.assertFalse(tv.khoa_phong)
		self.assertEqual(tv.active, 1)

	def test_quan_ly_co_khoa_bi_tu_choi(self):
		f = self._upload(_xlsx_bytes([
			_row("Nguyễn Thị Hoa", HOA, "Huyết học", "HUYETHOC", "Quản lý"),
		]))
		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)
		self.assertEqual(self._dong(ket_qua, HOA)["trang_thai"], "tu_choi")
		self.assertIn("Quản lý", " ".join(self._dong(ket_qua, HOA)["errors"]))

	def test_quan_ly_thu_hai_bi_tu_choi_kem_ten_quan_ly_dang_co(self):
		"""`_chan_hai_quan_ly` phải được chạy TRƯỚC ở bước xem trước — nếu
		không, người nhập chỉ biết khi commit nổ giữa chừng."""
		nhan_su_api.nhan_su_import_commit(
			CUST_A, self._upload(_xlsx_bytes([_row("Nguyễn Thị Hoa", HOA, vai_tro="Quản lý")])).file_url
		)
		f = self._upload(_xlsx_bytes([_row("Phạm Văn Dũng", DUNG, vai_tro="Quản lý")]))
		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)

		dong = self._dong(ket_qua, DUNG)
		self.assertEqual(dong["trang_thai"], "tu_choi")
		self.assertIn(HOA, " ".join(dong["errors"]))

	def test_hai_dong_quan_ly_trong_cung_tep_bi_tu_choi(self):
		f = self._upload(_xlsx_bytes([
			_row("Nguyễn Thị Hoa", HOA, vai_tro="Quản lý"),
			_row("Phạm Văn Dũng", DUNG, vai_tro="Quản lý"),
		]))
		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)
		self.assertEqual(self._dong(ket_qua, HOA)["trang_thai"], "tao_moi")
		self.assertEqual(self._dong(ket_qua, DUNG)["trang_thai"], "tu_choi")

	def test_trung_email_trong_cung_tep_bi_tu_choi(self):
		f = self._upload(_xlsx_bytes([
			_row("Nguyễn Thị Hoa", HOA, vai_tro="Quản lý"),
			_row("Hoa (gõ lại)", HOA, "Huyết học", "HUYETHOC"),
		]))
		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)
		self.assertEqual(ket_qua["so_tu_choi"], 1)
		self.assertEqual(ket_qua["rows"][1]["trang_thai"], "tu_choi")
		self.assertIn("dòng 2", " ".join(ket_qua["rows"][1]["errors"]))

	def test_email_noi_bo_miyano_bi_tu_choi(self):
		"""Gõ nhầm email nhân viên Miyano vào tệp của bệnh viện thì
		`portal_provision` sẽ gắn User Permission trên Customer cho tài khoản
		nội bộ đó — người ấy mất tầm nhìn ở khắp ERPNext và gần như không ai
		lần ra vì sao. Chặn ở xem trước, đừng để ghi rồi mới biết."""
		noi_bo = f"noibo{DOMAIN}"
		u = frappe.get_doc({
			"doctype": "User", "email": noi_bo, "first_name": "Nhân viên Miyano",
			"user_type": "System User", "send_welcome_email": 0,
		})
		# PHẢI có một role mở được Desk: `User.validate()` tự hạ user_type
		# xuống "Website User" cho tài khoản không có role nào vào được Desk —
		# thiếu dòng này, "System User" trong fixture chỉ là chữ, và bài test
		# sẽ canh một trạng thái mà code không bao giờ gặp.
		u.append("roles", {"role": "Sales User"})
		u.insert(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("User", noi_bo, "user_type"), "System User")

		f = self._upload(_xlsx_bytes([_row("Nhân viên Miyano", noi_bo, vai_tro="Quản lý")]))
		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)
		dong = ket_qua["rows"][0]
		self.assertEqual(dong["trang_thai"], "tu_choi")
		self.assertIn("System User", " ".join(dong["errors"]))

		with self.assertRaises(frappe.ValidationError) as cm:
			nhan_su_api.nhan_su_import_commit(CUST_A, f.file_url)
		self.assertIn("chưa có dữ liệu nào được ghi", str(cm.exception))
		self.assertFalse(frappe.db.exists("Portal Member", {"user": noi_bo}))
		self.assertFalse(frappe.db.exists(
			"User Permission", {"user": noi_bo, "allow": "Customer", "for_value": CUST_A}
		))

	def test_thieu_ma_ngan_thi_tu_choi_ca_tep_va_noi_ro(self):
		"""`_chan_thieu_ma_ngan` là chốt cấp KHÁCH HÀNG — nói ra ở xem trước,
		đừng để commit nổ."""
		self._tao_khach(CUST_KHONG_MA_NGAN)
		f = self._upload(_xlsx_bytes([_row("Trần Văn Bình", BINH, "Huyết học", "HUYETHOC")]))
		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_KHONG_MA_NGAN, f.file_url)

		self.assertIn("Mã ngắn", " ".join(ket_qua["loi_toan_tep"]))
		self.assertEqual(self._dong(ket_qua, BINH)["trang_thai"], "tu_choi")


class TestGhiThat(_NhanSuTestBase):
	def test_ghi_tao_du_tai_khoan_khoa_phong_va_phan_quyen(self):
		f = self._upload(_xlsx_bytes(TEP_HOP_LE))
		ket_qua = nhan_su_api.nhan_su_import_commit(CUST_A, f.file_url)

		self.assertEqual(ket_qua["so_tao_moi"], 3)
		# 3 User, SÁU Contact, 3 User Permission, 3 Portal Member, 1 khoa.
		# Sáu Contact là hành vi CÓ SẴN của `portal_provision` (không phải
		# của task này): Frappe tự tạo một Contact cho mỗi User mới
		# (`user.py::create_contact`), rồi `portal_provision` tạo thêm bản
		# ghi liên hệ riêng của cổng — cái NỐI Contact với Customer. Khẳng
		# định thẳng mối nối đó ở dưới để con số 6 không thành số ma.
		self.assertEqual(self._counts(), (3, 6, 3, 3, 1))
		lien_he = frappe.get_all("Contact", filters={"user": BINH}, pluck="name")
		self.assertEqual(len(lien_he), 2)
		self.assertTrue(frappe.db.exists("Dynamic Link", {
			"parenttype": "Contact", "parent": ["in", lien_he],
			"link_doctype": "Customer", "link_name": CUST_A,
		}))

		kp = frappe.db.get_value(
			"Customer Department", {"customer": CUST_A, "ma_khoa": "HUYETHOC"},
			["name", "ten_khoa_phong"], as_dict=True,
		)
		self.assertEqual(kp.ten_khoa_phong, "Huyết học")

		tv = frappe.db.get_value(
			"Portal Member", {"user": BINH}, ["customer", "vai_tro", "khoa_phong", "active"],
			as_dict=True,
		)
		self.assertEqual(tv.customer, CUST_A)
		self.assertEqual(tv.vai_tro, "Nhân viên khoa")
		self.assertEqual(tv.khoa_phong, kp.name)
		self.assertEqual(tv.active, 1, "tài khoản nhập từ tệp phải DÙNG ĐƯỢC ngay")

	def test_first_name_la_ten_nguoi_khong_phai_ten_benh_vien(self):
		"""QĐ-G21: `portal_provision` cũ đặt first_name = tên khách hàng —
		gốc của lỗi truy vết đã phải vá ở tầng hiển thị (97fd6e2). Ở đây
		tờ khai thắng."""
		f = self._upload(_xlsx_bytes(TEP_HOP_LE))
		nhan_su_api.nhan_su_import_commit(CUST_A, f.file_url)

		self.assertEqual(frappe.db.get_value("User", BINH, "first_name"), "Trần Văn Bình")
		self.assertNotEqual(frappe.db.get_value("User", BINH, "first_name"), CUST_A)

	def test_vai_tro_theo_to_khai_khong_theo_luat_ngam_nguoi_dau_tien(self):
		"""QĐ-G21 vế hai: `portal_provision` có luật ngầm "tài khoản đầu tiên
		của một bệnh viện là Quản lý". Tờ khai thắng — dòng đầu tệp là Nhân
		viên khoa thì nó PHẢI là Nhân viên khoa, dù bệnh viện chưa có ai."""
		f = self._upload(_xlsx_bytes([_row("Trần Văn Bình", BINH, "Huyết học", "HUYETHOC")]))
		nhan_su_api.nhan_su_import_commit(CUST_A, f.file_url)

		tv = frappe.db.get_value(
			"Portal Member", {"user": BINH}, ["vai_tro", "khoa_phong", "active"], as_dict=True,
		)
		self.assertEqual(tv.vai_tro, "Nhân viên khoa")
		self.assertTrue(tv.khoa_phong)
		self.assertEqual(tv.active, 1)

	def test_mat_khau_tra_ve_MOT_LAN_va_dat_that(self):
		"""QĐ-G19: Miyano đặt mật khẩu, màn hình hiện MỘT LẦN sau khi ghi để
		chép ra bàn giao. Không nằm trong tệp, không gửi email, không ghi log."""
		f = self._upload(_xlsx_bytes(TEP_HOP_LE))
		ket_qua = nhan_su_api.nhan_su_import_commit(CUST_A, f.file_url)

		self.assertEqual(sorted(ket_qua["mat_khau"]), sorted([HOA, BINH, CUC]))
		# Mật khẩu trả về phải là mật khẩu THẬT của tài khoản vừa tạo —
		# check_password ném AuthenticationError nếu sai.
		check_password(BINH, ket_qua["mat_khau"][BINH])

		# Bắt đổi ở lần đăng nhập đầu: Frappe v15 chỉ có chính sách theo
		# SỐ NGÀY ở System Settings (`force_user_to_reset_password`), không
		# có cờ cho từng người — đặt mốc đổi mật khẩu về quá khứ để chính
		# sách đó (khi bật) chộp đúng những tài khoản này ngay lần đầu.
		moc = frappe.db.get_value("User", BINH, "last_password_reset_date")
		self.assertTrue(moc)
		self.assertLess(frappe.utils.getdate(moc), frappe.utils.getdate(frappe.utils.today()))

	def test_nhap_lai_cung_tep_khong_de_trung(self):
		"""QĐ-G22 — khớp theo email."""
		f1 = self._upload(_xlsx_bytes(TEP_HOP_LE))
		nhan_su_api.nhan_su_import_commit(CUST_A, f1.file_url)
		sau_lan_1 = self._counts()

		f2 = self._upload(_xlsx_bytes(TEP_HOP_LE), filename="nhan_su_lan_2.xlsx")
		xem_truoc = nhan_su_api.nhan_su_import_preview(CUST_A, f2.file_url)
		self.assertEqual(xem_truoc["so_bo_qua"], 3)
		self.assertEqual(self._dong(xem_truoc, BINH)["trang_thai"], "bo_qua")

		ket_qua = nhan_su_api.nhan_su_import_commit(CUST_A, f2.file_url)
		self.assertEqual(ket_qua["so_tao_moi"], 0)
		self.assertEqual(ket_qua["mat_khau"], {})
		self.assertEqual(sau_lan_1, self._counts(), "nhập lại cùng tệp không được đẻ trùng")


class TestEmailCuaKhachKhac(_NhanSuTestBase):
	def test_chi_bao_o_xem_truoc_khong_tao_khong_doi_mat_khau(self):
		"""QĐ-G23 — có thể là người thật làm ở hai nơi, cũng có thể là gõ
		nhầm: báo và để Miyano quyết, không tự xử."""
		nhan_su_api.nhan_su_import_commit(
			CUST_A, self._upload(_xlsx_bytes([_row("Nguyễn Thị Hoa", HOA, vai_tro="Quản lý")])).file_url
		)
		mat_khau_cu = "ZZtest-MatKhau-Cu-1"
		update_password(HOA, mat_khau_cu)

		f = self._upload(_xlsx_bytes([
			_row("Nguyễn Thị Hoa", HOA, vai_tro="Quản lý"),
			_row("Phạm Văn Dũng", DUNG, "Hồi sức", "HOISUC"),
		]), filename="nhan_su_b.xlsx")
		xem_truoc = nhan_su_api.nhan_su_import_preview(CUST_B, f.file_url)

		dong = self._dong(xem_truoc, HOA)
		self.assertEqual(dong["trang_thai"], "canh_bao")
		self.assertIn(CUST_A, " ".join(dong["errors"]))
		self.assertEqual(xem_truoc["so_canh_bao"], 1)

		# Cảnh báo KHÔNG chặn các dòng còn lại — nhưng dòng cảnh báo thì
		# không tạo gì, không đổi gì.
		ket_qua = nhan_su_api.nhan_su_import_commit(CUST_B, f.file_url)
		self.assertEqual(ket_qua["so_tao_moi"], 1)
		self.assertEqual(ket_qua["so_canh_bao"], 1)
		self.assertNotIn(HOA, ket_qua["mat_khau"])
		self.assertEqual(
			frappe.db.get_value("Portal Member", {"user": HOA}, "customer"), CUST_A
		)
		self.assertFalse(frappe.db.exists(
			"User Permission", {"user": HOA, "allow": "Customer", "for_value": CUST_B}
		))
		check_password(HOA, mat_khau_cu)  # mật khẩu của họ KHÔNG bị đổi


class TestCachLy(_NhanSuTestBase):
	def test_tep_cua_khach_A_tao_dung_nguoi_cua_A_va_khong_dung_gi_cua_B(self):
		"""QĐ-G18: khách hàng chọn TRÊN MÀN HÌNH, không nằm trong tệp — một
		cột "tên bệnh viện" gõ tay là đường nhập nhầm người sang viện khác."""
		f = self._upload(_xlsx_bytes(TEP_HOP_LE))
		nhan_su_api.nhan_su_import_commit(CUST_A, f.file_url)

		# VẾ DƯƠNG: đúng ba người đó thuộc về A.
		self.assertEqual(
			sorted(frappe.get_all(
				"Portal Member", filters={"customer": CUST_A}, pluck="user")),
			sorted([HOA, BINH, CUC]),
		)
		self.assertEqual(
			frappe.get_all("Customer Department", filters={"customer": CUST_A}, pluck="ten_khoa_phong"),
			["Huyết học"],
		)
		# VẾ ÂM: không gì của B bị đụng tới.
		self.assertEqual(frappe.get_all("Portal Member", filters={"customer": CUST_B}), [])
		self.assertEqual(frappe.get_all("Customer Department", filters={"customer": CUST_B}), [])
		for email in (HOA, BINH, CUC):
			self.assertFalse(frappe.db.exists(
				"User Permission", {"user": email, "allow": "Customer", "for_value": CUST_B}
			))

	def test_khach_cong_khong_goi_duoc(self):
		"""Đây là màn của nhân viên Miyano trong Desk — một tài khoản cổng
		(Website User) không được cấp tài khoản cho bất kỳ ai."""
		f = self._upload(_xlsx_bytes(TEP_HOP_LE))
		nhan_su_api.nhan_su_import_commit(CUST_A, f.file_url)

		frappe.set_user(HOA)
		with self.assertRaises(frappe.PermissionError):
			nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)
		with self.assertRaises(frappe.PermissionError):
			nhan_su_api.nhan_su_import_commit(CUST_A, f.file_url)
		frappe.set_user("Administrator")

	def test_khach_hang_khong_ton_tai_bi_chan(self):
		f = self._upload(_xlsx_bytes(TEP_HOP_LE))
		with self.assertRaises(frappe.ValidationError) as cm:
			nhan_su_api.nhan_su_import_preview("ZZTEST KHONG CO KHACH NAY", f.file_url)
		self.assertIn("khách hàng", str(cm.exception).lower())


class TestTepMau(_NhanSuTestBase):
	def test_tai_mau_roi_nap_lai_ngay_thi_doc_duoc(self):
		"""Mẫu → xem trước phải đi lọt: tệp mẫu là thứ bệnh viện điền lên."""
		nhan_su_api.nhan_su_import_template()
		noi_dung = frappe.local.response.filecontent
		self.assertTrue(frappe.local.response.filename.endswith(".xlsx"))

		f = self._upload(noi_dung, filename="mau_tai_ve.xlsx")
		ket_qua = nhan_su_api.nhan_su_import_preview(CUST_A, f.file_url)
		self.assertEqual(ket_qua["loi_toan_tep"], [])
		self.assertEqual(ket_qua["so_tu_choi"], 0, ket_qua["rows"])
		self.assertGreaterEqual(ket_qua["total"], 1)
