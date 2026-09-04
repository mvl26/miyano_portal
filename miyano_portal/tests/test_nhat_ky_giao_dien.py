"""Lưới REGEX cho phần GIAO DIỆN của "sổ nhật ký thao tác + dòng thời gian"
(Task 6/7/8, xem `.superpowers/sdd/2026-09-03-nhat-ky-thao-tac-va-timeline/
task-678-brief.md` và `docs/superpowers/specs/2026-09-03-nhat-ky-thao-tac-
va-timeline-design.md` §9).

Frontend KHÔNG có hạ tầng test tự động (`package.json` chỉ có `vite build`)
— đây là lưới DUY NHẤT canh các bất biến giao diện của khối này. Cùng khuôn
`test_de_xuat_action_registry.py`/`test_giai_doan_khoa_va_nhan.py`: đọc file
`.vue`/`.js` bằng REGEX có chủ đích, KHÔNG parse JS/Vue — một parser JS
trong test Python là thứ phải bảo trì mà không đổi lại được gì.

HAI BÀI HỌC ĐẮT của nhánh này, ghi lại để không lặp:

1. **Canh chỗ GỌI/DÙNG, không canh dòng import.** Một bài `assertIn(tên
   module, nội_dung_file)` chỉ khớp đúng dòng `import ... from '...'` —
   xoá sạch phần DÙNG module đó (nút gọi API, prop truyền xuống…) mà dòng
   import còn nguyên thì bài này vẫn xanh trong khi tính năng đã chết.
   Mọi bài "component X gọi Y" ở đây đều regex vào cú pháp GỌI THẬT (tên
   hàm kèm dấu ngoặc, hoặc thẻ component kèm thuộc tính), không phải một
   `assertIn` tên chuỗi suông.
2. **Không canh bằng nhãn tiếng Việt của nút/nhãn hiển thị.** Đổi nhãn vì
   lý do biên tập (chốt đổi chữ, chủ đầu tư yêu cầu diễn đạt khác) không
   được làm lưới đỏ — lưới phải canh KHOÁ/thuộc tính/tên hàm, không canh
   chữ hiển thị cho người dùng cuối.

`_bo_comment()` bóc chú thích TRƯỚC khi regex chạy — nếu không, một câu MÔ
TẢ luật trong docstring/chú thích (ví dụ nhắc tới `|| '—'` như một PHẢN VÍ
DỤ cần tránh) tự nó khớp lưới và tạo báo động giả. Lưới phải soi ĐÚNG DÒNG
CODE THẬT, không soi chú thích nói VỀ code.
"""

import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"
FORMAT_JS = FRONTEND_SRC / "format.js"
KHOI_TRUY_VET = FRONTEND_SRC / "components" / "chi-tiet" / "KhoiTruyVet.vue"
KHOI_DONG_THOI_GIAN = FRONTEND_SRC / "components" / "chi-tiet" / "KhoiDongThoiGian.vue"
CHI_TIET_YEU_CAU = FRONTEND_SRC / "views" / "ChiTietYeuCau.vue"
STYLE_CSS = FRONTEND_SRC / "style.css"


def _bo_comment(text: str) -> str:
	"""Bóc chú thích HTML (`<!-- -->`, nhiều dòng) và chú thích JS (`//`,
	CẢ dòng chiếm TRỌN một dòng riêng LẪN trailing comment cuối một dòng
	code) khỏi một file `.vue`/`.js`, để lưới regex chỉ soi CODE THẬT — xem
	docstring module.

	Bóc CẢ trailing comment — SỬA sau khi thấy thật một ca `//` cuối dòng
	code (`ChiTietYeuCau.vue:222`: `continue // dòng không đổi → KHÔNG
	gửi`), bản đầu của hàm này chỉ bóc comment chiếm trọn dòng và bỏ sót ca
	đó. `(?<!:)` bảo vệ chuỗi kiểu `http://` khỏi bị hiểu nhầm thành mở đầu
	comment — đã `grep -rn "://" frontend/src` TOÀN BỘ trước khi viết luật
	này, không ca nào tồn tại trong codebase hiện tại, nhưng rào vẫn rẻ hơn
	một lần đỏ giả sau này."""
	text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
	text = re.sub(r"(?<!:)//.*$", "", text, flags=re.M)
	return text


class TestKhoiTruyVetDienThoai(FrappeTestCase):
	"""Task 6, Step 5 — `KhoiTruyVet.vue` phải hiện số điện thoại (người yêu
	cầu LẪN người duyệt) bằng liên kết `tel:`, và KHÔNG bao giờ dùng dấu
	gạch `'—'` làm giá trị thế chỗ cho một số bị thiếu (§8: thiếu số thì
	không in gì, không ô trống, không dấu gạch)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.raw = KHOI_TRUY_VET.read_text(encoding="utf-8")
		cls.code = _bo_comment(cls.raw)

	def test_nguoi_yeu_cau_va_nguoi_duyet_deu_hien_tel(self):
		"""Canh chỗ DÙNG — cú pháp `href="'tel:' + <khoá số điện thoại>"` cho
		ĐÚNG cả hai khoá `nguoi_yeu_cau_dien_thoai` và `nguoi_duyet_dien_
		thoai` (brief Task 6, Interfaces). Thiếu MỘT trong hai là một nửa
		khối truy vết mất nút bấm-gọi mà không ai biết."""
		self.assertRegex(
			self.code, r"href=\"'tel:'\s*\+\s*phieu\.nguoi_yeu_cau_dien_thoai\"",
			"Thiếu liên kết tel: cho số điện thoại người YÊU CẦU",
		)
		self.assertRegex(
			self.code, r"href=\"'tel:'\s*\+\s*phieu\.nguoi_duyet_dien_thoai\"",
			"Thiếu liên kết tel: cho số điện thoại người DUYỆT",
		)

	def test_khong_dung_gach_ngang_lam_gia_tri_the_cho_so_dien_thoai(self):
		"""§8 + brief ràng buộc #5 — KHÔNG `|| '—'`. Sau khi đã bóc chú thích
		(dòng chỉ MÔ TẢ luật này, xem docstring module), mọi chuỗi `'—'` còn
		lại trong CODE THẬT là một giá trị thế chỗ đang được gán."""
		self.assertNotIn("'—'", self.code)
		self.assertNotIn('"—"', self.code)


def _than_object(js_text: str, ten_bang: str) -> str:
	"""Cắt THÂN một object literal `const TEN_BANG = { ... }` bằng ĐẾM
	NGOẶC — không parse JS đầy đủ, cùng khuôn `test_giai_doan_khoa_va_
	nhan.py::_bang_nhan`. Trả chuỗi TỪ dấu `{` mở đầu tới dấu `}` khớp
	(kể cả hai dấu ngoặc), tính từ lần xuất hiện ĐẦU TIÊN của `ten_bang`."""
	i = js_text.find(ten_bang)
	assert i != -1, f"Không tìm thấy `{ten_bang}` trong format.js"
	mo = js_text.find("{", i)
	assert mo != -1, f"`{ten_bang}` không có thân object"
	sau = 0
	for j in range(mo, len(js_text)):
		if js_text[j] == "{":
			sau += 1
		elif js_text[j] == "}":
			sau -= 1
			if sau == 0:
				return js_text[mo:j + 1]
	raise AssertionError(f"`{ten_bang}` không đóng ngoặc")


def _khoa_su_kien() -> set:
	"""TOÀN BỘ hằng `SK_*` của `nhat_ky.py` — nguồn DUY NHẤT của danh sách
	khoá sự kiện (brief Task 7, mục (b)). KHÔNG gõ tay lại 18 chuỗi ở test:
	một khoá thêm/bớt ở `nhat_ky.py` mà quên đồng bộ tay ở lưới này là
	đúng kiểu lệch mà lưới sinh ra để bắt."""
	from miyano_portal import nhat_ky
	return {getattr(nhat_ky, ten) for ten in dir(nhat_ky) if ten.startswith("SK_")}


# §9.3 của spec — bảng màu THIẾT KẾ, chép nguyên văn từ mục "Màu chấm nói
# ba điều" để đối chiếu với bảng THẬT trong `format.js`. Đây là bản ghi Ở
# TEST của Ý ĐỊNH thiết kế — không đọc lại từ chính `format.js` (đọc từ
# nguồn rồi so với chính nó không kiểm được gì).
MAU_MONG_DOI = {
	"khoa_gui_duyet": "benh-vien",
	"quan_ly_duyet": "benh-vien",
	"khach_dong_y": "benh-vien",
	"khoa_xin_sua": "benh-vien",
	"quan_ly_duyet_sua": "benh-vien",
	"khach_gui_lai_bao_gia": "benh-vien",
	"miyano_xac_nhan": "miyano",
	"miyano_bao_gia": "miyano",
	"giao_hang": "miyano",
	"hoa_don": "miyano",
	"quan_ly_tu_choi": "lui",
	"quan_ly_tu_choi_sua": "lui",
	"quan_ly_huy_phieu": "lui",
	"khoa_thu_hoi": "lui",
	"miyano_tu_choi": "lui",
	"khach_khong_dong_y": "lui",
	"khach_huy_don": "lui",
	"don_tao": "he-thong",
}


class TestFormatJsNhanSuKien(FrappeTestCase):
	"""Task 7, Step 1(a) — `format.js` phải có đủ 18 khoá sự kiện (nguồn:
	`nhat_ky.py`) trong CẢ HAI bảng: `NHAN_SU_KIEN` (khoá → nhãn tiếng
	Việt, khác rỗng) và bảng màu chấm nội bộ mà `mauChamSuKien()` tra
	(đúng đúng bảng §9.3 — không chỉ "có mặt", mà đúng MÀU).

	Kiểm CẢ HAI bảng, không chỉ nhãn: thiếu một khoá ở bảng NHÃN thì màn
	hình hiện chuỗi khoá thô (`khoa_gui_duyet`) — lỗi DỄ THẤY. Thiếu một
	khoá ở bảng MÀU thì hàm `mauChamSuKien()` lặng lẽ lui về màu mặc định
	(xám) cho đúng MỘT khoá đó — lỗi DỄ BỎ SÓT, vì nhãn vẫn đúng, chỉ có
	chấm sai màu. Một lưới chỉ soi bảng nhãn sẽ bỏ lọt đúng loại lỗi thứ
	hai này."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.format_js = FORMAT_JS.read_text(encoding="utf-8")

	def test_nhan_su_kien_du_18_khoa_khac_rong(self):
		than = _than_object(self.format_js, "NHAN_SU_KIEN")
		khoa_thieu = []
		for khoa in _khoa_su_kien():
			m = re.search(khoa + r"\s*:\s*'([^']*)'", than)
			if not m or not m.group(1).strip():
				khoa_thieu.append(khoa)
		self.assertEqual(
			khoa_thieu, [],
			f"NHAN_SU_KIEN thiếu nhãn (hoặc nhãn rỗng) cho: {khoa_thieu} — "
			"một sự kiện thật sẽ hiện ra CHUỖI KHOÁ THÔ trước mặt bệnh viện",
		)

	def test_mau_cham_dung_bang_thiet_ke_du_18_khoa(self):
		"""§9.3 — mỗi khoá phải map đúng MỘT trong bốn màu, ĐÚNG như bảng
		thiết kế `MAU_MONG_DOI` (không chỉ "khác rỗng"): một khoá "đi lùi"
		(`quan_ly_tu_choi`…) lỡ map nhầm sang `benh-vien` (xanh) là đúng
		lớp lỗi Ruling #19 (đơn bị từ chối đeo badge XANH) tái diễn ở một
		chỗ khác."""
		than = None
		for ten_bang in ("MAU_SU_KIEN", "MAU_CHAM_SU_KIEN"):
			if ten_bang in self.format_js:
				than = _than_object(self.format_js, ten_bang)
				break
		self.assertIsNotNone(
			than, "format.js chưa có bảng màu chấm nội bộ (MAU_SU_KIEN)"
		)
		sai = []
		for khoa, mau_dung in MAU_MONG_DOI.items():
			m = re.search(khoa + r"\s*:\s*'([^']*)'", than)
			mau_thuc = m.group(1) if m else None
			if mau_thuc != mau_dung:
				sai.append((khoa, mau_dung, mau_thuc))
		self.assertEqual(sai, [], f"Sai màu chấm (khoá, mong đợi, thực tế): {sai}")


class TestKhoiDongThoiGianGiaoDien(FrappeTestCase):
	"""Task 7, Step 1(b)/(c) — `KhoiDongThoiGian.vue` phải DÙNG LẠI đúng
	lớp bố cục `.vtl`/`.vst`/`.vdot`/`.vlb` đã có (§9.2 — không dựng lớp bố
	cục mới, không tự thêm `<style>` trong SFC), và số điện thoại phải bấm
	gọi được (`tel:`), không bao giờ dùng `'—'` thế chỗ một số bị thiếu —
	CÙNG luật §8 mà Task 6 đã canh cho `KhoiTruyVet.vue`, áp lại cho khối
	MỚI này."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.raw = KHOI_DONG_THOI_GIAN.read_text(encoding="utf-8")
		cls.code = _bo_comment(cls.raw)

	def test_dung_lai_lop_bo_cuc_co_khong_tu_them_style(self):
		for lop in ('class="vtl"', 'class="vst"', 'class="vdot"', 'class="vlb"'):
			self.assertIn(
				lop, self.code,
				f"KhoiDongThoiGian.vue không dùng lớp bố cục có sẵn `{lop}` — "
				"§9.2 cấm dựng một bộ lớp thứ hai làm cùng một việc",
			)
		self.assertNotRegex(
			self.code, r"<style",
			"KhoiDongThoiGian.vue tự thêm <style> riêng — §9.2 chỉ cho thêm "
			"BỐN lớp màu chấm vào style.css dùng chung, không dựng CSS cục bộ mới",
		)

	def test_hien_tel_khong_dung_gach_ngang(self):
		self.assertRegex(
			self.code, r"href=\"'tel:'\s*\+\s*d\.dien_thoai\"",
			"Thiếu liên kết tel: cho số điện thoại trong dòng thời gian",
		)
		self.assertNotIn("'—'", self.code)
		self.assertNotIn('"—"', self.code)

