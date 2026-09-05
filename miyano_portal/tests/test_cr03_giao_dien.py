"""Lưới REGEX cho phần GIAO DIỆN của CR-03 (chín field mới của "hàng chưa có
trong hệ thống" — xem `docs/superpowers/specs/2026-09-05-cr03-hang-chua-co-
trong-he-thong-design.md` §7/§8). Backend đã có lưới riêng
(`test_cr03_dat_ngoai.py`); file NÀY canh phần frontend — cổng KHÔNG có hạ
tầng test JS (`package.json` chỉ có `vite build`), nên đây là lưới DUY NHẤT
bắt được một field bị bỏ sót ở màn hình.

Cùng khuôn `test_nhat_ky_giao_dien.py`: đọc `.vue`/`.js`/`.py` bằng REGEX có
chủ đích, KHÔNG parse JS/Vue thật. HAI bài học đắt đã ghi lại ở file đó áp
lại nguyên vẹn ở đây — canh chỗ DÙNG (không canh dòng import/khai báo suông),
và không canh nhãn tiếng Việt hiển thị cho người dùng cuối.

BA ĐIỂM RỦI RO CAO NHẤT mà bộ lưới này nhắm tới (đã đo được, không phải giả
định):

1. `napTuPhieu()` — nạp một phiếu Nháp đã lưu vào form. Trước bản vá CR-03
   chỉ map bốn field gốc; đây là đường "dữ liệu khách đã khai bị xoá lặng lẽ
   khi họ sửa phiếu" NGHIÊM TRỌNG NHẤT vì nó xảy ra ở thao tác bình thường
   nhất (gõ nửa chừng, lưu, quay lại) chứ không phải một ca biên.
2. `datNgoaiPayload` — chiều NGƯỢC LẠI (client → server) của cùng rủi ro:
   thiếu field ở đây thì field đó không bao giờ tới được CSDL dù khách đã gõ
   trên màn hình.
3. Hai `<details>` PHẢI tách biệt (mô tả kỹ thuật / thương mại) — thiết kế
   §7 nói rõ lý do: NCC + giá đang mua là thông tin thương mại của bệnh
   viện, gộp chung với model/hãng là làm người ta khai ra mà không nhận ra
   mình vừa khai gì.
"""

import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"
LAP_PHIEU = FRONTEND_SRC / "views" / "LapPhieu.vue"
KHOI_BAO_GIA = FRONTEND_SRC / "components" / "chi-tiet" / "KhoiBaoGia.vue"
API_JS = FRONTEND_SRC / "api.js"

# Chín field mới, ĐÚNG THỨ TỰ đặc tả §3 liệt kê — dùng lại một danh sách DUY
# NHẤT cho mọi bài canh "đủ chín field", tránh chín bài gõ tay chín danh
# sách gần giống nhau rồi một danh sách lệch mà không ai để ý.
CHIN_FIELD = (
	"model_ma", "hang_san_xuat", "nuoc_san_xuat", "quy_cach",
	"ncc_hien_tai", "gia_hien_tai", "anh", "khong_co_anh", "mo_ta_nhan_dang",
)


def _bo_comment(text: str) -> str:
	"""Bóc chú thích — bản sao của `test_nhat_ky_giao_dien.py::_bo_comment`.

	KHÔNG import chéo giữa hai file test (mỗi file test phải tự đứng được,
	không phụ thuộc lẫn nhau) — đây là bản sao CÓ CHỦ Ý, không phải trùng lặp
	quên dọn."""
	text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
	text = re.sub(r"(?<!:)//.*$", "", text, flags=re.M)
	return text


def _than_ngoac(text: str, i_mo: int, mo="{", dong="}") -> str:
	"""Cắt thân một khối bằng ĐẾM NGOẶC, bắt đầu từ vị trí ký tự mở `mo` đầu
	tiên TỪ `i_mo` trở đi. Trả chuỗi TỪ dấu mở TỚI dấu đóng khớp (kể cả hai
	đầu). Cùng kỹ thuật `test_nhat_ky_giao_dien.py::_than_object`, tổng quát
	hoá cho cả `{}` lẫn `()` (dùng cho `_than_ham` bên dưới)."""
	i = text.find(mo, i_mo)
	assert i != -1, f"Không tìm thấy dấu mở '{mo}' từ vị trí {i_mo}"
	sau = 0
	for j in range(i, len(text)):
		if text[j] == mo:
			sau += 1
		elif text[j] == dong:
			sau -= 1
			if sau == 0:
				return text[i:j + 1]
	raise AssertionError(f"Không tìm thấy dấu đóng '{dong}' khớp với vị trí {i}")


def _than_ham(js_text: str, ten_ham: str) -> str:
	"""Cắt THÂN một hàm `function ten_ham(...) { ... }` bằng đếm ngoặc `{}`
	— không parse JS đầy đủ, cùng khuôn `_than_object` của `test_nhat_ky_
	giao_dien.py`. Tìm chữ ký hàm trước (`function ten_ham(`), rồi cắt thân
	từ dấu `{` đầu tiên SAU chữ ký đó — tránh khớp nhầm một lời GỌI hàm cùng
	tên (`ten_ham(...)` không có `function` phía trước, ví dụ trong comment
	hoặc ở một hàm khác gọi tới nó)."""
	m = re.search(r"function\s+" + re.escape(ten_ham) + r"\s*\(", js_text)
	assert m is not None, f"Không tìm thấy khai báo `function {ten_ham}(` trong file"
	return _than_ngoac(js_text, m.end())


class TestNapTuPhieuMangDuChinTruong(FrappeTestCase):
	"""Rủi ro #1 (xem docstring module) — `napTuPhieu()` nạp lại MỘT phiếu
	Nháp đã lưu. Đây là thao tác BÌNH THƯỜNG NHẤT (gõ nửa chừng buổi sáng,
	lưu, quay lại buổi chiều) hoặc thu hồi một phiếu bị từ chối rồi sửa tiếp
	— không phải ca biên.

	PHÁ THỬ ĐỂ CHỨNG MINH ĐỎ: xoá năm dòng field CR-03 khỏi object map
	trong `napTuPhieu`, giữ lại bốn field gốc (đúng bản TRƯỚC khi vá) — chín
	assertion `model_ma`..`mo_ta_nhan_dang` bên dưới đỏ với lỗi "Không tìm
	thấy field `<tên>` trong napTuPhieu() — dữ liệu khách đã khai bị xoá
	lặng lẽ khi họ sửa phiếu", đúng mô tả rủi ro #1. Đã tự chạy phép phá này
	(xoá `model_ma` tới `mo_ta_nhan_dang` khỏi object, build lại) và xác
	nhận bài `test_ca_chin_field_deu_co_mat` đỏ đúng field bị xoá."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		raw = LAP_PHIEU.read_text(encoding="utf-8")
		cls.than = _than_ham(_bo_comment(raw), "napTuPhieu")

	def test_ca_chin_field_deu_co_mat(self):
		# `\s*:[^,\n]*dn\.<field>\b` — KHÔNG đòi `field: dn.field` NGUYÊN VĂN:
		# hai field (`anh`, `khong_co_anh`) đi qua một hàm/phép biến đổi
		# (`parseAnhTho(dn.anh)`, `!!dn.khong_co_anh`) trước khi gán, nhưng
		# vẫn PHẢI đọc từ đúng `dn.<field>` nguồn, trên CÙNG MỘT DÒNG với
		# tên field bên trái dấu `:` (chặn khớp nhầm sang một dòng khác vô
		# tình nhắc tới cùng tên field).
		thieu = []
		for field in CHIN_FIELD:
			if not re.search(r"\b" + field + r"\s*:[^,\n]*dn\." + field + r"\b", self.than):
				thieu.append(field)
		self.assertEqual(
			thieu, [],
			f"napTuPhieu() KHÔNG map field {thieu} từ `dn.<field>` — dữ liệu khách "
			"đã khai bị xoá lặng lẽ ngay lần lưu/gửi kế tiếp sau khi mở lại phiếu",
		)

	def test_anh_duoc_giai_ma_tu_chuoi_json_khong_giu_nguyen_van(self):
		"""`anh` là CHUỖI JSON trên CSDL (Small Text) nhưng client cần MẢNG để
		lặp `v-for` — map thẳng `anh: dn.anh` (khớp lưới bài trên vì tên field
		đúng) vẫn là một lỗi khác: template sẽ lặp qua TỪNG KÝ TỰ của chuỗi
		thay vì từng `file_url`. Bài RIÊNG này đòi phải đi qua một hàm phân
		giải (`parseAnhTho`), không chấp nhận gán thẳng."""
		self.assertRegex(
			self.than, r"anh\s*:\s*parseAnhTho\(\s*dn\.anh\s*\)",
			"napTuPhieu() không giải mã `dn.anh` qua parseAnhTho() — field `anh` "
			"trên CSDL là CHUỖI JSON, gán thẳng sẽ làm `v-for` lặp theo KÝ TỰ",
		)


class TestDatNgoaiPayloadMangDuChinTruong(FrappeTestCase):
	"""Rủi ro #2 — chiều NGƯỢC LẠI của rủi ro #1: `datNgoaiPayload` dịch dòng
	CLIENT sang dòng gửi lên SERVER (`de_xuat_luu_nhap` THAY TOÀN BỘ bảng
	`dat_ngoai`). Thiếu field ở đây thì field đó không bao giờ tới được CSDL
	dù khách đã gõ đủ trên màn hình — khác lỗi #1 (mất khi ĐỌC), đây là mất
	khi GHI.

	PHÁ THỬ: xoá `anh: JSON.stringify(d.anh || [])` khỏi object trả về —
	`test_ca_chin_field_deu_co_mat` đỏ vì thiếu khớp field `anh` (không tìm
	thấy `anh\\s*:`), đúng field vừa xoá."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		raw = LAP_PHIEU.read_text(encoding="utf-8")
		code = _bo_comment(raw)
		i = code.find("const datNgoaiPayload = computed(() =>")
		assert i != -1, "Không tìm thấy khai báo `const datNgoaiPayload = computed(() =>`"
		# Cắt tới điểm neo THẬT kế tiếp trong file (khai báo `ghiPhieu`, đứng
		# NGAY SAU computed này) — mảnh này chỉ chứa THÂN của computed, không
		# lẫn code phía sau.
		j = code.find("async function ghiPhieu(ten)", i)
		assert j != -1, "Không tìm thấy mốc `async function ghiPhieu(ten)` đứng sau computed"
		cls.than = code[i:j]

	def test_ca_chin_field_deu_co_mat(self):
		thieu = [f for f in CHIN_FIELD if not re.search(r"\b" + f + r"\s*:", self.than)]
		self.assertEqual(
			thieu, [],
			f"datNgoaiPayload KHÔNG gửi field {thieu} lên server — khách gõ trên "
			"màn hình nhưng field không bao giờ tới được CSDL",
		)

	def test_bon_field_goc_van_con(self):
		"""Vế chống-bẫy: một bản vá thêm chín field mới rồi LỠ TAY xoá một
		trong bốn field GỐC (`ten_hang`/`dvt`/`so_luong`/`ghi_chu`) khi viết
		lại object vẫn phải bị bắt — không chỉ chín field mới mới đáng canh."""
		for f in ("ten_hang", "dvt", "so_luong", "ghi_chu"):
			with self.subTest(field=f):
				self.assertRegex(self.than, r"\b" + f + r"\s*:", f"Thiếu field gốc `{f}`")


class TestApiJsCoDuongTaiVaXemAnh(FrappeTestCase):
	"""`api.js` phải có HAI hàm mới CHO CR-03 và PHẢI xuất chúng ở export mặc
	định — bài học `test_nhat_ky_giao_dien.py` #1: một hàm CÓ khai báo nhưng
	không được nơi khác import/dùng vẫn xanh nếu lưới chỉ tìm dòng khai báo."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.raw = API_JS.read_text(encoding="utf-8")
		cls.code = _bo_comment(cls.raw)

	def test_tai_anh_dat_ngoai_gui_du_ba_khoa_multipart(self):
		"""`portal_dat_ngoai_tai_anh(de_xuat, dong_idx)` + tệp — thiếu MỘT
		trong ba khoá multipart (`file`/`de_xuat`/`dong_idx`) là server nhận
		thiếu tham số bắt buộc và ném lỗi ngay từ vòng kiểm đầu tiên."""
		than = _than_ham(self.code, "taiAnhDatNgoai")
		for khoa in ("'file'", "'de_xuat'", "'dong_idx'"):
			with self.subTest(khoa=khoa):
				self.assertIn(
					f"body.append({khoa}", than,
					f"taiAnhDatNgoai() không append {khoa} vào FormData",
				)

	def test_dat_ngoai_xem_anh_url_mang_du_hai_tham_so(self):
		than = _than_ham(self.code, "datNgoaiXemAnhUrl")
		self.assertIn("de_xuat", than)
		self.assertIn("file_url", than)
		self.assertIn("portal_dat_ngoai_xem_anh", than)

	def test_export_mac_dinh_co_ca_hai_ham_moi(self):
		"""Canh CHỖ XUẤT, không chỉ chỗ khai báo `export async function` —
		một hàm khai báo `export` riêng lẻ vẫn dùng được qua `import { ten }`,
		nhưng MỌI nơi khác trong app import qua `import api from '../api'`
		(export mặc định, xem `LapPhieu.vue`) — thiếu ở đây là component gọi
		`api.taiAnhDatNgoai` nhận `undefined is not a function`."""
		m = re.search(r"export default \{([^}]*)\}", self.code, flags=re.S)
		self.assertIsNotNone(m, "Không tìm thấy `export default { ... }` trong api.js")
		than_export = m.group(1)
		self.assertIn("taiAnhDatNgoai", than_export)
		self.assertIn("datNgoaiXemAnhUrl", than_export)


class TestLapPhieuGoiApiAnhDungThamSo(FrappeTestCase):
	"""`chuanBiAnh`/`chonAnh`/`xoaAnh` — ràng buộc #1 của brief ("ảnh chỉ
	tải được khi phiếu đã có tên") VÀ chốt "dong_idx là chỉ số trong
	`datNgoaiHopLe`, KHÔNG PHẢI chỉ số `v-for` thô" (mảng client có thể còn
	dòng gõ dở/trống ở cuối — trộn hai không gian chỉ số này gắn nhầm ảnh
	vào MỘT DÒNG KHÁC trên server)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		raw = LAP_PHIEU.read_text(encoding="utf-8")
		cls.code = _bo_comment(raw)

	def test_chuan_bi_anh_dam_bao_co_ten_truoc_khi_dung_anh(self):
		"""Ràng buộc #1 — dòng đặt ngoài thêm TRƯỚC khi phiếu tồn tại
		(`tenPhieu` rỗng cho tới lần Lưu/Gửi đầu, xem `damBaoCoTen()`) phải
		được LƯU NHÁP trước, không được ném lỗi khó hiểu."""
		than = _than_ham(self.code, "chuanBiAnh")
		self.assertRegex(
			than, r"await\s+damBaoCoTen\(\)",
			"chuanBiAnh() không đảm bảo phiếu đã có tên trước khi thao tác ảnh",
		)
		self.assertRegex(
			than, r"await\s+ghiPhieu\(",
			"chuanBiAnh() không lưu nháp trước khi thao tác ảnh — mảng dat_ngoai "
			"phía server có thể LỆCH với client, làm dong_idx trỏ sai dòng",
		)

	def test_dong_idx_tinh_tu_dat_ngoai_hop_le_khong_phai_chi_so_v_for(self):
		"""PHÁ THỬ: đổi `datNgoaiHopLe.value.indexOf(d)` thành tham số `i` của
		`v-for` (chỉ số thô trong `datNgoai`, mảng có thể còn dòng trống ở
		cuối) — bài này đỏ vì không còn khớp `datNgoaiHopLe.value.indexOf`."""
		than = _than_ham(self.code, "chuanBiAnh")
		self.assertRegex(
			than, r"datNgoaiHopLe\.value\.indexOf\(\s*d\s*\)",
			"chuanBiAnh() không tính dong_idx từ datNgoaiHopLe.indexOf(d) — trộn "
			"nhầm không gian chỉ số sẽ gắn ảnh vào MỘT DÒNG KHÁC trên server",
		)

	def test_chon_anh_goi_tai_anh_dat_ngoai_dung_ba_tham_so(self):
		than = _than_ham(self.code, "chonAnh")
		self.assertRegex(
			than, r"api\.taiAnhDatNgoai\(\s*file\s*,\s*ten\s*,\s*idx\s*\)",
			"chonAnh() không gọi api.taiAnhDatNgoai(file, ten, idx) đúng chữ ký",
		)

	def test_xoa_anh_goi_dung_endpoint_voi_dong_idx_va_file_url(self):
		than = _than_ham(self.code, "xoaAnh")
		self.assertRegex(
			than,
			r"api\.call\(\s*'portal_dat_ngoai_xoa_anh'\s*,\s*\{\s*de_xuat:\s*ten\s*,"
			r"\s*dong_idx:\s*idx\s*,\s*file_url:\s*fileUrl\s*\}\s*\)",
			"xoaAnh() không gọi portal_dat_ngoai_xoa_anh với đủ de_xuat/dong_idx/file_url",
		)

	def test_thu_nho_di_qua_anh_cache_khong_tro_thang_file_url(self):
		"""Ràng buộc #2 của brief — xem ảnh PHẢI qua `portal_dat_ngoai_xem_
		anh`, KHÔNG BAO GIỜ trỏ thẳng `/private/files/…` (role Customer có
		ZERO DocPerm, đường mặc định của Frappe sẽ 403 với chính người vừa
		tải ảnh lên). PHÁ THỬ: đổi `<img :src="anhCache[u]">` thành
		`:src="u"` (gán thẳng `file_url`) — bài này đỏ."""
		self.assertRegex(
			self.code, r':src="anhCache\[u\]"',
			"Thẻ <img> không dùng anhCache[u] — có nguy cơ trỏ thẳng file_url "
			"(đường /private/files mặc định của Frappe) và bị 403",
		)
		self.assertNotIn(
			"/private/files", self.code,
			"LapPhieu.vue có chuỗi '/private/files' trong code thật — ảnh CR-03 "
			"phải phục vụ qua endpoint portal_dat_ngoai_xem_anh, không trỏ thẳng "
			"đường tệp riêng tư mặc định",
		)
		self.assertRegex(
			self.code, r"api\.fetchBlobUrl\(\s*api\.datNgoaiXemAnhUrl\(",
			"Không tìm thấy lời gọi api.fetchBlobUrl(api.datNgoaiXemAnhUrl(...)) — "
			"thiếu đường dựng blob URL cho ảnh riêng tư",
		)


class TestHaiKhoiDetailsTachRieng(FrappeTestCase):
	"""Thiết kế §7 — bốn ô MÔ TẢ KỸ THUẬT (model/hãng/nước/quy cách) và hai ô
	THƯƠNG MẠI (NCC/giá đang mua) phải nằm trong HAI khối `<details>` TÁCH
	RIÊNG, không gộp chung. Lý do: NCC + giá đang mua là thông tin thương
	mại của bệnh viện — gộp chung với mô tả kỹ thuật (thứ khách nghĩ là "vô
	hại") sẽ làm người ta khai ra mà không nhận thấy mình vừa khai một thứ
	nhạy cảm.

	PHÁ THỬ ĐỂ CHỨNG MINH ĐỎ: gộp `ncc_hien_tai`/`gia_hien_tai` vào CHUNG
	`<details>` với `model_ma` (xoá cặp thẻ `<details>...</details>` thứ
	hai, chuyển hai input NCC/giá vào cuối khối thứ nhất) —
	`test_khoi_mo_ta_khong_chua_field_thuong_mai` đỏ vì `ncc_hien_tai` nay
	CÓ mặt trong khối mô tả."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		raw = LAP_PHIEU.read_text(encoding="utf-8")
		code = _bo_comment(raw)
		i1 = code.find("<details")
		assert i1 != -1, "Không tìm thấy khối <details> đầu tiên"
		e1 = code.find("</details>", i1)
		assert e1 != -1, "Không tìm thấy </details> đóng khối đầu tiên"
		cls.khoi_mo_ta = code[i1:e1]

		i2 = code.find("<details", e1)
		assert i2 != -1, "Không tìm thấy khối <details> THỨ HAI"
		e2 = code.find("</details>", i2)
		assert e2 != -1, "Không tìm thấy </details> đóng khối thứ hai"
		cls.khoi_thuong_mai = code[i2:e2]

	def test_khoi_mo_ta_chua_bon_field_ky_thuat(self):
		for f in ("model_ma", "hang_san_xuat", "nuoc_san_xuat", "quy_cach"):
			with self.subTest(field=f):
				self.assertIn(f"d.{f}", self.khoi_mo_ta, f"Khối mô tả kỹ thuật thiếu ô `{f}`")

	def test_khoi_mo_ta_khong_chua_field_thuong_mai(self):
		for f in ("ncc_hien_tai", "gia_hien_tai"):
			with self.subTest(field=f):
				self.assertNotIn(
					f"d.{f}", self.khoi_mo_ta,
					f"Khối MÔ TẢ KỸ THUẬT lẫn field THƯƠNG MẠI `{f}` — gộp chung làm "
					"khách khai ra thông tin nhạy cảm mà không nhận ra",
				)

	def test_khoi_thuong_mai_chua_hai_field_ncc_va_gia(self):
		for f in ("ncc_hien_tai", "gia_hien_tai"):
			with self.subTest(field=f):
				self.assertIn(f"d.{f}", self.khoi_thuong_mai, f"Khối thương mại thiếu ô `{f}`")

	def test_khoi_thuong_mai_khong_chua_field_mo_ta_ky_thuat(self):
		for f in ("model_ma", "hang_san_xuat", "nuoc_san_xuat", "quy_cach"):
			with self.subTest(field=f):
				self.assertNotIn(
					f"d.{f}", self.khoi_thuong_mai,
					f"Khối THƯƠNG MẠI lẫn field mô tả kỹ thuật `{f}`",
				)


class TestAnhDatTruocCacOMoTaTrongVongLap(FrappeTestCase):
	"""Thiết kế §7 — khối Ảnh đặt NGAY DƯỚI tên hàng, TRÊN cả các ô mô tả:
	nó là dữ kiện giá trị nhất và là thứ bắt buộc. Canh bằng VỊ TRÍ tương đối
	trong thân vòng lặp — cùng kỹ thuật cắt-đoạn-thân-`v-for` đã dùng thành
	công ở `test_nhat_ky_giao_dien.py::_doan_vong_lap`."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		raw = LAP_PHIEU.read_text(encoding="utf-8")
		code = _bo_comment(raw)
		i_vfor = code.find('v-for="(d, i) in datNgoai"')
		assert i_vfor != -1, 'Không tìm thấy v-for="(d, i) in datNgoai"'
		i_them_dong = code.find('@click="themDongDatNgoai"', i_vfor)
		assert i_them_dong != -1, 'Không tìm thấy nút "+ Thêm dòng" đứng ngay sau vòng lặp'
		cls.than_vong_lap = code[i_vfor:i_them_dong]

	def test_o_ten_hang_dung_truoc_khoi_anh(self):
		i_ten_hang = self.than_vong_lap.find("d.ten_hang")
		i_anh = self.than_vong_lap.find('v-for="u in d.anh"')
		self.assertNotEqual(i_ten_hang, -1, "Không tìm thấy ô Tên hàng trong thân vòng lặp")
		self.assertNotEqual(i_anh, -1, "Không tìm thấy khối lặp thu nhỏ ảnh (v-for=\"u in d.anh\")")
		self.assertLess(i_ten_hang, i_anh, "Khối Ảnh phải đứng SAU ô Tên hàng")

	def test_khoi_anh_dung_truoc_ca_hai_khoi_mo_ta(self):
		"""PHÁ THỬ: dời khối Ảnh xuống sau hai `<details>` — bài này đỏ vì
		`i_anh` (chỉ số nút "+ Chọn ảnh") sẽ LỚN HƠN chỉ số `<details>` đầu
		tiên."""
		i_chon_anh = self.than_vong_lap.find("+ Chọn ảnh")
		i_details_1 = self.than_vong_lap.find("<details")
		self.assertNotEqual(i_chon_anh, -1, 'Không tìm thấy nút "+ Chọn ảnh"')
		self.assertNotEqual(i_details_1, -1, "Không tìm thấy khối <details> mô tả")
		self.assertLess(
			i_chon_anh, i_details_1,
			"Khối Ảnh (nút + Chọn ảnh) phải đứng TRƯỚC cả hai khối <details> mô tả — "
			"thiết kế §7 coi ảnh là dữ kiện giá trị nhất, phải hiện trước tiên",
		)


class TestKhoiBaoGiaChuyenTiepDuChinTruong(FrappeTestCase):
	"""`KhoiBaoGia.vue::moGuiLai()` — đường "sửa và gửi lại" của
	`ChiTietYeuCau.vue` (`dongGuiLai`) đi qua ĐÂY để dựng payload
	`dat_ngoai`. LƯU Ý (đã ghi trong `cr03-report.md`): tại thời điểm này
	`portal_order_track` CHƯA trả chín field CR-03 trong `dat_ngoai`, nên
	việc chuyển tiếp ở đây hiện KHÔNG có tác dụng thật (server nguồn dữ liệu
	`d` không có các field này, và `portal_order_sua_so_luong` cũng chỉ đọc
	`name`/`qty`) — bài dưới đây canh ĐÚNG YÊU CẦU CỦA BRIEF (mang đủ chín
	field qua `.map()`), không khẳng định tính năng này đã có tác dụng đầu
	cuối."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		raw = KHOI_BAO_GIA.read_text(encoding="utf-8")
		cls.than = _than_ham(_bo_comment(raw), "moGuiLai")

	def test_doi_dat_ngoai_mang_du_chin_field(self):
		thieu = [f for f in CHIN_FIELD if not re.search(r"\b" + f + r"\s*:\s*d\." + f + r"\b", self.than)]
		self.assertEqual(
			thieu, [],
			f"moGuiLai() không chuyển tiếp field {thieu} từ dòng đặt ngoài gốc",
		)


class TestMauInBoSungModelHangQuyCach(FrappeTestCase):
	"""Thiết kế §8 — mẫu in "Miyano - Báo giá" (khối "Hàng đang tìm nguồn",
	dựng từ `custom_dat_ngoai` chưa khớp mã) phải in thêm Model/Hãng SX/Quy
	cách: tờ giấy đó chính là thứ purchasing cầm đi hỏi nhà cung cấp.

	PHÁ THỬ: xoá ba `<td>` mới khỏi bảng — bài dưới đỏ vì không còn khớp
	`d.model_ma`/`d.hang_san_xuat`/`d.quy_cach` trong đúng đoạn bảng này
	(đoạn cắt riêng khối "Hàng đang tìm nguồn", không phải toàn bộ HTML_BG —
	tránh khớp nhầm sang bảng "Hàng đặt ngoài đã khớp mã" ở dưới, vốn KHÔNG
	yêu cầu ba cột này theo đặc tả)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from miyano_portal.setup.install_print_formats import HTML_BG
		i = HTML_BG.find("Hàng đang tìm nguồn")
		assert i != -1, 'Không tìm thấy tiêu đề "Hàng đang tìm nguồn" trong HTML_BG'
		j = HTML_BG.find("</table>", i)
		assert j != -1, "Không tìm thấy </table> đóng bảng Hàng đang tìm nguồn"
		cls.khoi_bang = HTML_BG[i:j]

	def test_bang_cho_nguon_co_ba_cot_moi(self):
		for f in ("model_ma", "hang_san_xuat", "quy_cach"):
			with self.subTest(field=f):
				self.assertIn(
					f"d.{f}", self.khoi_bang,
					f"Bảng 'Hàng đang tìm nguồn' thiếu cột `{f}` — purchasing vẫn phải "
					"quay lại Desk hỏi lại thông tin khách đã khai trên cổng",
				)

	def test_patch_dong_bo_ban_ghi_da_cai_ton_tai(self):
		"""Vế chống-bẫy: sửa `HTML_BG` trong mã nguồn KHÔNG tự cập nhật bản
		ghi `Print Format` đã cài trên site cũ (`install_portal_print_
		formats()` bỏ qua bản ghi đã tồn tại — xem `v1_15.dong_bo_dinh_dang_
		tien_bao_gia`, tiền lệ đã có trong repo). Thiếu patch đồng bộ thì
		field mới CÓ trong mã nguồn nhưng KHÔNG BAO GIỜ lên được tờ giấy thật
		của một site đã chạy `install_portal_print_formats()` từ trước — bài
		này canh patch đồng bộ TỒN TẠI và ĐĂNG KÝ trong `patches.txt`."""
		import miyano_portal.patches.v1_32.dong_bo_mau_bao_gia_cr03 as patch_mod

		self.assertTrue(hasattr(patch_mod, "execute"))
		patches_txt = (
			Path(frappe.get_app_path("miyano_portal")) / "patches.txt"
		).read_text(encoding="utf-8")
		self.assertIn(
			"miyano_portal.patches.v1_32.dong_bo_mau_bao_gia_cr03", patches_txt,
			"Patch đồng bộ mẫu in chưa được đăng ký trong patches.txt — sẽ "
			"KHÔNG BAO GIỜ tự chạy trên site nào, kể cả khi bench migrate",
		)

	def test_patch_dong_bo_dung_bien_html_bg_hien_hanh(self):
		"""Patch phải đọc `HTML_BG` TỪ `install_print_formats` (không phải
		một bản chép tay riêng) — nếu không, patch sẽ đồng bộ một chuỗi HTML
		KHÁC với chuỗi thật đang dùng để cài mới, và hai đường (cài mới /
		đồng bộ lại) trôi lệch nhau ngay từ patch tiếp theo sửa `HTML_BG`."""
		import inspect

		import miyano_portal.patches.v1_32.dong_bo_mau_bao_gia_cr03 as patch_mod
		from miyano_portal.setup.install_print_formats import HTML_BG, NAME_BG

		nguon = inspect.getsource(patch_mod)
		self.assertIn("HTML_BG", nguon)
		self.assertIn("NAME_BG", nguon)
		self.assertIn("install_print_formats", nguon)
		# Xác nhận NAME_BG/HTML_BG THẬT SỰ import được từ đúng module nguồn
		# (nếu ai đó xoá import và định nghĩa lại một bản HTML_BG cục bộ
		# trong patch, dòng import ở TRÊN sẽ tự ném ImportError trước khi
		# chạy tới đây).
		self.assertTrue(NAME_BG and HTML_BG)
