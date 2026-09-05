"""CR-04 (phần GIAO DIỆN) — căn cứ tồn kho ngay cạnh dòng hàng khi quản lý
duyệt. `test_cr04_can_cu_duyet.py` đã canh phép tính (`kho/can_cu_duyet.py`)
và việc `portal_order_track` trả `can_cu_kho`. File này canh HAI VIỆC KHÁC
mà đặc tả GIAO DIỆN cần nhưng backend đã commit trước đó CHƯA nối dây tới:

1. **`de_xuat_chi_tiet` cũng phải trả `can_cu_kho`.** Phát hiện quan trọng
   nhất của vòng làm giao diện này: `Sales Order` chỉ được TẠO tại thời
   điểm DUYỆT (`de_xuat_duyet_phieu` → `duyet_va_tao_don`) — nghĩa là
   ĐÚNG lúc quản lý đang xem màn duyệt (`phieu.trang_thai === 'Chờ
   duyệt'`), CHƯA hề có Sales Order nào. `ChiTietYeuCau.vue` chỉ nạp `don`
   (nguồn `can_cu_kho` cũ, gắn trong `portal_order_track`) khi
   `phieu.sales_order` đã có — tức KHÔNG BAO GIỜ ở đúng khoảnh khắc quản lý
   cần căn cứ để duyệt. `can_cu_cho_don()` chỉ đọc `.customer`, `.name`,
   `.get("items")[].item_code` — phiếu `Portal De Xuat Mua` có đủ ba, nên
   gọi thẳng ĐƯỢC với chính doc phiếu, không cần đợi Sales Order.

   Bài dưới soi BẰNG CÂY CÚ PHÁP (không tìm chuỗi thô) — cùng kỹ thuật
   `test_cr04_can_cu_duyet.py::test_khong_goi_get_portal_kho` — vì chính
   docstring giải thích CR-04 (ở `de_xuat.py` lẫn ở đây) sẽ nhắc tới đúng
   những chữ `can_cu_kho`/`can_cu_cho_don` mà một bài `assertIn` chuỗi
   thô sẽ khớp NHẦM vào lời giải thích thay vì dòng code thật.

2. **Lưới REGEX cho `BangMatHang.vue`** — frontend KHÔNG có hạ tầng test
   (`package.json` chỉ có `vite build`), cùng khuôn `test_nhat_ky_giao_
   dien.py`: bóc chú thích (`<!-- -->` LẪN `//`) trước khi regex chạy, và
   canh CHỖ DÙNG bên trong thân `v-for`, không canh dòng khai báo/import —
   ba lần đỏ giả của phiên trước đều rơi đúng bẫy này.
"""

import ast
import inspect
import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.kho import can_cu_duyet as cc
from miyano_portal.tests.test_nhat_ky_giao_dien import _bo_comment

FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"
BANG_MAT_HANG = FRONTEND_SRC / "components" / "chi-tiet" / "BangMatHang.vue"
CHI_TIET_YEU_CAU = FRONTEND_SRC / "views" / "ChiTietYeuCau.vue"


class TestDeXuatChiTietTraCanCuKho(FrappeTestCase):
	"""Đây là chỗ THỰC SỰ cần `can_cu_kho` — màn duyệt đọc `phieu.items`,
	không đọc `don.items`, và tại "Chờ duyệt" thì `don` luôn `null`."""

	def test_de_xuat_chi_tiet_gan_can_cu_kho_tu_can_cu_cho_don_cua_doc(self):
		from miyano_portal.api import de_xuat

		cay = ast.parse(inspect.getsource(de_xuat.de_xuat_chi_tiet))
		khop = False
		for node in ast.walk(cay):
			if not isinstance(node, ast.Assign):
				continue
			for target in node.targets:
				if not (
					isinstance(target, ast.Subscript)
					and isinstance(target.slice, ast.Constant)
					and target.slice.value == "can_cu_kho"
				):
					continue
				gia_tri = node.value
				if (
					isinstance(gia_tri, ast.Call)
					and isinstance(gia_tri.func, ast.Attribute)
					and gia_tri.func.attr == "can_cu_cho_don"
					# Đối số ĐẦU phải là `doc` (chính phiếu) — truyền `kq` (dict
					# đã as_dict()) sẽ mất `.customer`/`.get("items")` kiểu
					# Document, và `can_cu_cho_don` cần đúng hai thuộc tính đó.
					and gia_tri.args
					and isinstance(gia_tri.args[0], ast.Name)
					and gia_tri.args[0].id == "doc"
				):
					khop = True
		self.assertTrue(
			khop,
			"`de_xuat_chi_tiet` không gán kq['can_cu_kho'] = can_cu_duyet."
			"can_cu_cho_don(doc) — màn duyệt (trước khi Sales Order tồn tại) "
			"sẽ không bao giờ có căn cứ tồn kho, dù portal_order_track đã có",
		)


class TestBangMatHangCanCuKho(FrappeTestCase):
	"""Lưới regex cho năm cột mới + gạch ngang + cờ + sổ kho xổ tại dòng
	trên `BangMatHang.vue` (spec §3-§6)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.raw = BANG_MAT_HANG.read_text(encoding="utf-8")
		cls.code = _bo_comment(cls.raw)

	# --- §3: năm cột, bên trái "SL đề xuất" ------------------------------

	def test_bon_cot_moi_dat_ben_trai_sl_de_xuat_theo_dung_thu_tu(self):
		"""Bốn cột mới (Tồn hiện có/Đang về/Dùng TB/ngày/Còn dùng được) phải
		đứng TRƯỚC `<th>SL đề xuất</th>` — cột thứ năm ("NV đặt") CHÍNH LÀ
		"SL đề xuất" đã có (quyết định ghi trong báo cáo), không dựng cột
		thứ sáu song song (sẽ in `so_luong_de_xuat` hai lần)."""
		nhan = ["Tồn hiện có", "Đang về", "Dùng TB/ngày", "Còn dùng được", "SL đề xuất"]
		vi_tri = []
		for n in nhan:
			i = self.code.find(f">{n}<")
			self.assertNotEqual(i, -1, f"Không tìm thấy tiêu đề cột '{n}'")
			vi_tri.append(i)
		self.assertEqual(
			vi_tri, sorted(vi_tri),
			f"Thứ tự cột sai — mong đợi {nhan} theo đúng thứ tự này",
		)

	def test_bon_cot_moi_gate_theo_dieu_kien_dang_duyet_khong_theo_du_lieu(self):
		"""Ràng buộc quan trọng: cột phải hiện khi ĐANG Ở MÀN DUYỆT (có ô SL
		duyệt), KHÔNG được gate theo "có canCuKho hay không" — khách CHƯA MỞ
		KHO (1/6) chính là nhóm PHẢI thấy gạch ngang + dòng giải thích, ẩn cột
		đi vì thiếu dữ liệu sẽ xoá mất đúng thông tin quan trọng nhất."""
		for n in ("Tồn hiện có", "Đang về", "Dùng TB/ngày", "Còn dùng được"):
			i = self.code.find(f">{n}<")
			doan_truoc = self.code[max(0, i - 120):i]
			self.assertRegex(
				doan_truoc, r'<th\s+v-if="coCanCuKho"',
				f"Cột '{n}' không gate bằng v-if=\"coCanCuKho\"",
			)

	def test_khong_dung_du_lieu_can_cu_kho_de_gate_cot(self):
		"""VẾ ÂM — cấm gate kiểu `v-if=\"canCuKho[...]\"`/`Object.keys(canCuKho)
		.length` trên chính bốn `<th>` đó, đúng lỗi đã nêu ở bài trên."""
		for n in ("Tồn hiện có", "Đang về", "Dùng TB/ngày", "Còn dùng được"):
			i = self.code.find(f">{n}<")
			doan_truoc = self.code[max(0, i - 120):i]
			self.assertNotRegex(
				doan_truoc, r'v-if="[^"]*canCuKho\[',
				f"Cột '{n}' gate theo DỮ LIỆU canCuKho thay vì theo điều kiện màn duyệt",
			)

	# --- §4: gạch ngang khi không tra được, KHÔNG hiện 0 -----------------

	def _than_v_for(self) -> str:
		"""Cắt thân `v-for="row in dong"` — cùng kỹ thuật `_doan_vong_lap()`
		của `test_nhat_ky_giao_dien.py`, mốc kết thúc là dòng đặt ngoài
		(`datNgoaiDaKhop`) — vòng lặp dòng hàng CHÍNH luôn đứng trước khối
		đó trong file."""
		i_mo = self.code.find('v-for="row in dong"')
		self.assertNotEqual(i_mo, -1, 'Không tìm thấy v-for="row in dong"')
		# `datNgoaiDaKhop` xuất hiện LẦN ĐẦU trong <script setup> (khai báo
		# computed), TRƯỚC cả <template> — tìm mốc kết thúc bắt đầu TỪ SAU
		# `i_mo`, đúng lần xuất hiện trong template (khối "Đã khớp mã").
		i_dong_ngoai = self.code.find("datNgoaiDaKhop", i_mo)
		self.assertNotEqual(i_dong_ngoai, -1, "Không tìm thấy mốc kết thúc (datNgoaiDaKhop)")
		self.assertLess(i_mo, i_dong_ngoai)
		return self.code[i_mo:i_dong_ngoai]

	def test_ham_dinh_dang_so_luong_phan_biet_null_voi_0(self):
		"""Hàm định dạng SL/ngày cho bốn cột mới phải kiểm `null`/`undefined`
		TƯỜNG MINH — `v || 0` (bẫy `fmtVND` đã né ở nơi khác trong CHÍNH file
		này, xem "Ruling preflight #1") sẽ biến "không tra được" thành "0",
		đúng thứ CR-04 sinh ra để cấm."""
		self.assertRegex(
			self.code,
			r"function fmt\w*\([^)]*\)\s*\{\s*(//[^\n]*\n\s*)*if\s*\([^)]*===\s*null",
			"Không tìm thấy hàm định dạng có kiểm tường minh `=== null`",
		)

	def test_khong_dung_v_hoac_0_cho_bon_cot_moi(self):
		"""Bốn field `ton`/`dang_ve`/`adu`/`con_dung_duoc` không được đi qua
		mẫu `<field> || 0`, dù trực tiếp hay qua `Number(<field> || 0)`."""
		for field in ("ton", "dang_ve", "adu", "con_dung_duoc"):
			self.assertNotRegex(
				self.code, rf"\.{field}\s*\|\|\s*0",
				f"Trường `{field}` bị `|| 0` — sẽ hiện SỐ 0 thay vì gạch ngang "
				"khi không tra được (đúng lỗi CR-04 sinh ra để cấm)",
			)

	def test_dong_giai_thich_ba_ly_do_gate_theo_co_dong_khong_tra_duoc(self):
		"""§4 — một dòng giải thích ngắn TRÊN bảng khi có ít nhất một dòng
		không tra được, nêu đủ BA lý do (chưa mở kho / vật tư chưa nối mã /
		hàng không có trong danh mục kho), KHÔNG hiện vô điều kiện."""
		self.assertRegex(
			self.code, r'v-if="coDongKhongTraDuoc"',
			"Dòng giải thích không gate theo coDongKhongTraDuoc",
		)
		m = re.search(r'v-if="coDongKhongTraDuoc"[^>]*>(.*?)</p>', self.code, re.S)
		self.assertIsNotNone(m, "Không tìm thấy nội dung dòng giải thích")
		cau = m.group(1)
		for tu_khoa in ("chưa mở kho", "chưa nối", "danh mục kho"):
			self.assertIn(
				tu_khoa, cau,
				f"Dòng giải thích thiếu lý do '{tu_khoa}' — quản lý phải tự đoán vì sao cột trống",
			)

	# --- §5: chấm màu + cờ ⚠, ngưỡng khớp Python -------------------------

	def test_cham_mau_dong_theo_muc_trong_v_for(self):
		"""Chấm màu phải mang class ĐỘNG theo `muc` do SERVER trả (không suy
		lại ở client) — canh CHỖ DÙNG thật trong thân vòng lặp, không phải
		một class tĩnh nào đó nằm ngoài `v-for`."""
		than = self._than_v_for()
		self.assertRegex(
			than, r':class="[^"]*\bmuc\b[^"]*"',
			"Không tìm thấy chấm màu gắn class ĐỘNG theo `muc` bên trong v-for",
		)

	def test_hang_so_canh_bao_dat_khi_chua_can_khop_python(self):
		"""Ngưỡng ⚠ ("Còn dùng được ≥ 30 ngày và NV vẫn đặt") không tính được
		ở server (thiếu `nv_dat`) nên PHẢI lặp ở JS — Ruling #19 đòi con số
		đó đặt Ở MỘT hằng số có tên, và test đối chiếu với chính hằng số
		Python (`NGUONG_DAT_KHI_CHUA_CAN`) để một lần đổi ngưỡng ở backend
		không lặng lẽ để JS lệch theo."""
		m = re.search(r"NGUONG_DAT_KHI_CHUA_CAN\w*\s*=\s*(\d+)", self.code)
		self.assertIsNotNone(m, "Không tìm thấy hằng số ngưỡng cảnh báo trong BangMatHang.vue")
		self.assertEqual(
			int(m.group(1)), cc.NGUONG_DAT_KHI_CHUA_CAN,
			"Hằng số ngưỡng cảnh báo ở JS LỆCH với kho/can_cu_duyet.py::NGUONG_DAT_KHI_CHUA_CAN",
		)

	def test_co_dau_canh_bao_trong_v_for(self):
		than = self._than_v_for()
		self.assertIn("⚠", than, "Không tìm thấy dấu ⚠ trong thân vòng lặp dòng hàng")

	# --- §6: sổ kho xổ tại dòng -------------------------------------------

	def test_goi_kho_the_kho_dung_lai_endpoint_da_co(self):
		self.assertRegex(
			self.code, r"api\.callKho\(\s*'kho_the_kho'\s*,\s*\{",
			"Không tìm thấy lời gọi api.callKho('kho_the_kho', {...})",
		)

	def test_nut_xo_so_kho_khong_hien_khi_khong_tra_duoc(self):
		"""'Dòng không tra được thì không có gì để xổ — đừng hiện nút chết'
		— HAI PHẦN: (a) nút mở sổ kho trong v-for phải gate qua MỘT hàm
		điều kiện (không hiện vô điều kiện), (b) hàm điều kiện đó phải thật
		sự đọc `vat_tu` — canh cả chỗ GỌI lẫn chỗ hàm THỰC SỰ kiểm tra, để
		một bản vá sau đổi hàm thành `return true` (gate giả, luôn hiện nút)
		vẫn bị bắt dù phần (a) còn xanh."""
		than = self._than_v_for()
		m_goi = re.search(r'<button\b[^>]*v-if="(\w+)\(row\)"', than)
		self.assertIsNotNone(
			m_goi, "Không tìm thấy nút mở sổ kho gate bằng v-if=\"<hàm>(row)\" trong v-for",
		)
		ten_ham = m_goi.group(1)
		m_ham = re.search(rf"function {ten_ham}\(row\)\s*\{{(.*?)\n\}}", self.code, re.S)
		self.assertIsNotNone(m_ham, f"Không tìm thấy định nghĩa hàm `{ten_ham}`")
		self.assertIn(
			"vat_tu", m_ham.group(1),
			f"Hàm `{ten_ham}` (gate của nút sổ kho) không đọc `vat_tu` — không chặn được "
			"dòng không tra được, nút sổ kho sẽ hiện ra CHẾT (bấm không có gì để xổ)",
		)

	def test_dung_lai_the_kho_columns_khong_tu_khai_cot_thu_hai(self):
		"""Sổ kho xổ tại dòng phải dùng lại `THE_KHO_COLUMNS` (nguồn cột
		DUY NHẤT, đã canh khớp `reports.py` bởi `test_kho_reports.py`) —
		không tự liệt kê lại tên cột thành một bảng thứ hai dễ trôi lệch.

		Review (advisor) — bản đầu của bài này soi `self.raw` (CHƯA bóc chú
		thích) bằng `assertIn("THE_KHO_COLUMNS", ...)`: xoá SẠCH cả hai
		`v-for="c in THE_KHO_COLUMNS"` (chỗ DÙNG thật) mà GIỮ NGUYÊN dòng
		chú thích phía trên (nhắc tên `THE_KHO_COLUMNS`) vẫn làm bài xanh —
		đúng bẫy "khớp chỗ NÓI thay cho chỗ DÙNG" mà chính brief đặt tên
		(ba lần đỏ giả của phiên trước). Soi `self.code` (đã bóc comment) và
		đòi cú pháp GỌI THẬT (`v-for="c in THE_KHO_COLUMNS"`), không phải
		một `assertIn` tên chuỗi suông."""
		self.assertRegex(
			self.code, r'v-for="c in THE_KHO_COLUMNS"',
			"BangMatHang.vue không có v-for=\"c in THE_KHO_COLUMNS\" — "
			"sổ kho xổ tại dòng không dùng lại nguồn cột chung",
		)

	# --- Bảng cuộn ngang trong khung riêng --------------------------------

	def test_bang_cuon_ngang_trong_khung_rieng(self):
		"""§5 ràng buộc — bảng rộng cuộn ngang trong khung riêng (`overflow-x:
		auto`), không để cả trang cuộn ngang trên điện thoại. Bảng gốc đã có
		MỘT khung; sổ kho xổ tại dòng thêm bảng thứ hai nên cần khung RIÊNG
		thứ hai — đếm ít nhất 2 khung `overflow-x: auto` trong file."""
		so_khung = len(re.findall(r"overflow-x:\s*auto", self.code))
		self.assertGreaterEqual(
			so_khung, 2,
			"Thiếu khung overflow-x:auto RIÊNG cho bảng sổ kho xổ tại dòng — "
			"bảng đó sẽ kéo cả trang cuộn ngang trên điện thoại",
		)


class TestChiTietYeuCauNoiDayCanCuKho(FrappeTestCase):
	"""`BangMatHang` phải NHẬN được `can_cu_kho` — component render đúng chỗ
	nhưng không có prop truyền xuống là đúng kiểu "nửa-sống" đã lặp ở nhánh
	nhật ký thao tác (`test_nhat_ky_giao_dien.py::...duoc_truyen_prop_dong`)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.raw = CHI_TIET_YEU_CAU.read_text(encoding="utf-8")
		cls.code = _bo_comment(cls.raw)

	def test_bang_mat_hang_nhan_prop_can_cu_kho(self):
		m = re.search(r"<BangMatHang\b[^>]*>", self.code, re.S)
		self.assertIsNotNone(m, "Không tìm thấy thẻ <BangMatHang> trong template")
		the = m.group(0)
		self.assertRegex(
			the, r':can-cu-kho="[^"]*can_cu_kho[^"]*"',
			"<BangMatHang> không truyền prop can-cu-kho — cột mới sẽ RỖNG VĨNH VIỄN dù "
			"backend đã trả đủ dữ liệu",
		)
