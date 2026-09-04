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

	def _doan_vong_lap(self):
		"""Cắt riêng đoạn thân TỪ `v-for="(d, i) in dong"` TỚI mốc
		`margin-top: 10px` (thuộc tính style THẬT của khối chú giải màu,
		không phải comment — sống sót qua `_bo_comment()`) — đây là đoạn
		DUY NHẤT chứa vòng lặp, tách biệt khỏi khối chú giải tĩnh và câu
		giải thích chung phía dưới. Dùng chung cho mọi bài canh CHỖ DÙNG
		bên trong vòng lặp (bài học lặp lại ba lần ở review vòng 1: khớp
		một chỗ khai báo/dùng KHÁC thay cho chỗ cần canh là lưới giả)."""
		i_vfor = self.code.find('v-for="(d, i) in dong"')
		self.assertNotEqual(i_vfor, -1, "Không tìm thấy vòng lặp v-for=\"(d, i) in dong\"")
		i_legend = self.code.find("margin-top: 10px")
		self.assertNotEqual(i_legend, -1, "Không tìm thấy mốc khối chú giải màu (margin-top: 10px)")
		self.assertLess(i_vfor, i_legend, "Vòng lặp phải đứng TRƯỚC khối chú giải trong file")
		return self.code[i_vfor:i_legend]

	def test_cham_trong_vong_lap_mang_class_dong_mau_cham(self):
		"""Review vòng 1 (Important, phá thủ công) — reviewer xoá
		`:class="mauChamSuKien(d.su_kien, d.vai)"` khỏi chấm TRONG `v-for`,
		để trơ `<div class="vdot"></div>`. `test_dung_lai_lop_bo_cuc_co_
		khong_tu_them_style` ở trên VẪN XANH cho phép phá đó vì nó chỉ tìm
		literal `class="vdot"` CÓ MẶT Ở ĐÂU ĐÓ trong file — và chuỗi đó vẫn
		sống nhờ khối chú giải màu cuối file (`class="vdot benh-vien"`…),
		dù chấm THẬT trong vòng lặp đã mất class động. Hậu quả: MỌI chấm ra
		một màu — đúng thứ §9.3 sinh ra để tránh.

		Regex đòi `mauChamSuKien(d.su_kien, d.vai)` xuất hiện Ở ĐÂU ĐÓ BÊN
		TRONG chính thuộc tính `:class="..."` của `class="vdot"` (không đòi
		nó là TOÀN BỘ giá trị) — review vòng 2 đổi cú pháp sang mảng
		`:class="[mauChamSuKien(...), { 'suy-ra': d.suy_ra }]"` để ghép
		thêm class `suy-ra` (xem `test_cham_suy_ra_mang_class_dong`), nên
		lưới không còn đòi khớp NGUYÊN VĂN cả biểu thức."""
		doan_vong_lap = self._doan_vong_lap()
		self.assertRegex(
			doan_vong_lap,
			r'class="vdot"\s+:class="[^"]*mauChamSuKien\(\s*d\.su_kien\s*,\s*d\.vai\s*\)[^"]*"',
			"Chấm TRONG vòng lặp không mang class ĐỘNG theo mauChamSuKien(d.su_kien, "
			"d.vai) — mọi chấm sẽ ra MỘT màu, đúng thứ §9.3 sinh ra để tránh",
		)

	def test_cham_suy_ra_mang_class_dong(self):
		"""Review vòng 2 (Important) — `d.suy_ra` do `portal_nhat_ky_yeu_
		cau` trả về (§9.6, dòng DỰNG LẠI từ bốn trường trên phiếu cho
		chứng từ CŨ) nhưng TRƯỚC bản vá này KHÔNG được đọc ở đâu trong
		template — đúng lỗi "lần thứ tư" `docs/BAN-DO-CHUC-NANG.md` mục 4
		ghi nhận (`boi_so` được API trả về nhưng không màn nào đọc): một
		trường chỉ có người SINH ra mà không người TIÊU THỤ thì không tồn
		tại đối với người dùng. Hậu quả cụ thể: dòng DỰNG LẠI (độ tin cậy
		thấp hơn, không phải ghi ngay lúc việc xảy ra) hiện Y HỆT dòng ghi
		THẬT — mời người dùng trích dẫn một suy luận như thể đó là bằng
		chứng.

		Canh CHỖ DÙNG bằng đúng kỹ thuật cắt-đoạn-thân-`v-for` đã dùng
		thành công ở review vòng 1 (`_doan_vong_lap()`), đòi lớp `suy-ra`
		gắn ĐỘNG theo `d.suy_ra` — KHÔNG đòi nó là toàn bộ `:class`, chỉ
		đòi nó CÓ MẶT bên trong thuộc tính đó."""
		doan_vong_lap = self._doan_vong_lap()
		self.assertRegex(
			doan_vong_lap,
			r":class=\"[^\"]*\{\s*'suy-ra'\s*:\s*d\.suy_ra\s*\}[^\"]*\"",
			"Chấm TRONG vòng lặp không gắn lớp `suy-ra` theo d.suy_ra — dòng DỰNG "
			"LẠI (độ tin cậy thấp hơn) hiện y hệt dòng ghi THẬT, không ai phân biệt được",
		)

	def test_nhan_dung_lai_tu_phieu_hien_khi_suy_ra(self):
		"""Review vòng 2 (Important) — nhãn CHỮ THẬT "Dựng lại từ phiếu"
		phải hiện cạnh mốc giờ khi `d.suy_ra`. Chủ đầu tư/reviewer nêu rõ:
		đừng CHỈ làm mờ đi — mờ đọc ra "ít quan trọng", không phải "độ tin
		cậy khác"; người dùng bệnh viện không đọc chú thích kỹ thuật, nên
		tín hiệu phải là CHỮ, không chỉ màu/độ mờ."""
		doan_vong_lap = self._doan_vong_lap()
		self.assertRegex(
			doan_vong_lap,
			r'v-if="d\.suy_ra"[^>]*>Dựng lại từ phiếu<',
			"Thiếu nhãn CHỮ THẬT \"Dựng lại từ phiếu\" cạnh mốc giờ cho dòng suy_ra — "
			"chỉ đổi màu/độ mờ không đủ, người dùng bệnh viện không đọc chú thích kỹ thuật",
		)

	def test_cau_giai_thich_chung_chi_hien_khi_co_dong_suy_ra(self):
		"""Review vòng 2 (mục 2 của yêu cầu sửa, tự quyết CÓ làm) — một câu
		giải thích chung ở cuối khối khi CÓ ít nhất một dòng suy_ra. Canh
		HAI thứ: (a) câu ĐƯỢC GATE bằng `v-if="coDongSuyRa"` — không hiện
		vô điều kiện; (b) câu KHÔNG nêu một ngày cụ thể kiểu "Nhật ký bắt
		đầu ghi từ <ngày>" — cùng lý do đã từ chối câu đó ở trạng thái
		RỖNG (component không có cách xác nhận đúng ngày nhật ký được BẬT
		trên site khách hàng cụ thể); nêu ngày cụ thể ở đây là tái phạm
		đúng lỗi đã tránh chỗ khác trong CÙNG file."""
		self.assertRegex(
			self.code,
			r'v-if="coDongSuyRa"',
			"Câu giải thích chung (nếu có) phải GATE bằng v-if=\"coDongSuyRa\", "
			"không hiện vô điều kiện cho mọi yêu cầu",
		)
		self.assertNotRegex(
			self.code,
			r"bắt đầu ghi từ \d{1,2}/\d{1,2}/\d{4}",
			"Câu giải thích nêu một NGÀY CỤ THỂ — component không có cách xác nhận "
			"đúng ngày nhật ký được BẬT trên site khách hàng, tái phạm lỗi đã tránh "
			"ở trạng thái RỖNG phía trên",
		)

	def test_nhan_su_kien_goi_qua_nhanSuKien_khong_hien_khoa_tho(self):
		"""Review vòng 1 (Important, phá thủ công) — reviewer đổi
		`{{ nhanSuKien(d.su_kien) }}` thành `{{ d.su_kien }}`. Hai bài
		`TestFormatJsNhanSuKien` chỉ đọc `format.js` (đối chiếu bảng NHÃN
		có đủ 18 khoá), KHÔNG bài nào canh CHÍNH component có GỌI
		`nhanSuKien()` để tra bảng đó hay không — bảng nhãn đầy đủ không
		cứu được nếu component không gọi tới nó. Hậu quả: chuỗi khoá thô
		(`khoa_gui_duyet`) hiện thẳng trước mặt bệnh viện — đúng hậu quả
		mà ràng buộc "đủ 18 khoá" sinh ra để chặn, xảy ra dù bảng nhãn vẫn
		đầy đủ."""
		self.assertRegex(
			self.code,
			r"<b>\{\{\s*nhanSuKien\(d\.su_kien\)\s*\}\}</b>",
			"Tầng 1 (việc) không gọi nhanSuKien(d.su_kien) — nếu bị đổi thành "
			"{{ d.su_kien }} thì khoá THÔ hiện thẳng trước mặt bệnh viện",
		)


class TestChiTietYeuCauLapNhatKy(FrappeTestCase):
	"""Task 8 — `ChiTietYeuCau.vue` phải GỌI `portal_nhat_ky_yeu_cau` cho
	CẢ HAI đường vào (`/yeu-cau/phieu/:ten` lẫn `/yeu-cau/don/:name` — note
	(d) của brief) và RENDER `KhoiDongThoiGian` ngay sau `KhoiTienTrinh`,
	trước `KhoiTruyVet` (§9.1).

	Canh CHỖ GỌI THẬT (cú pháp `api.call('portal_nhat_ky_yeu_cau', {khoá:
	...})` với ĐÚNG khoá `de_xuat`/`order`), không phải một `assertIn` tên
	chuỗi suông — bài học Task 7b của phiên trước: một bài chỉ khớp dòng
	import thì xoá sạch phần DÙNG vẫn xanh."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.raw = CHI_TIET_YEU_CAU.read_text(encoding="utf-8")
		cls.code = _bo_comment(cls.raw)

	def test_goi_nhat_ky_ca_hai_nhanh_phieu_va_don(self):
		"""HAI khẳng định RIÊNG, không gộp một `assertRegex` chung chung —
		một lưới gộp sẽ xanh khi CHỈ MỘT nhánh được nối dây (đúng nửa-sống
		mà note (d) cảnh báo: quên một nhánh thì nửa số người dùng — những
		ai vào bằng link `/yeu-cau/don/...` trong thông báo — thấy khối
		dòng thời gian trống, không ai biết vì sao)."""
		self.assertRegex(
			self.code,
			r"api\.call\(\s*'portal_nhat_ky_yeu_cau'\s*,\s*\{\s*de_xuat:",
			"Thiếu lời gọi portal_nhat_ky_yeu_cau ở NHÁNH VÀO BẰNG PHIẾU (đối số de_xuat)",
		)
		self.assertRegex(
			self.code,
			r"api\.call\(\s*'portal_nhat_ky_yeu_cau'\s*,\s*\{\s*order:",
			"Thiếu lời gọi portal_nhat_ky_yeu_cau ở NHÁNH VÀO BẰNG ĐƠN (đối số order)",
		)

	def test_khoi_dong_thoi_gian_render_sau_tien_trinh_truoc_truy_vet(self):
		"""§9.1 — dòng thời gian là PHẦN NỞ RA của Tiến trình: ngay dưới
		`KhoiTienTrinh`, trước `KhoiTruyVet` (khối "Yêu cầu & duyệt")."""
		i_tien_trinh = self.code.find("<KhoiTienTrinh")
		i_dong_thoi_gian = self.code.find("<KhoiDongThoiGian")
		i_truy_vet = self.code.find("<KhoiTruyVet")
		for ten, i in (("KhoiTienTrinh", i_tien_trinh), ("KhoiDongThoiGian", i_dong_thoi_gian), ("KhoiTruyVet", i_truy_vet)):
			self.assertNotEqual(i, -1, f"ChiTietYeuCau.vue không render <{ten}>")
		self.assertLess(
			i_tien_trinh, i_dong_thoi_gian,
			"<KhoiDongThoiGian> phải nằm SAU <KhoiTienTrinh> trong template",
		)
		self.assertLess(
			i_dong_thoi_gian, i_truy_vet,
			"<KhoiDongThoiGian> phải nằm TRƯỚC <KhoiTruyVet> trong template",
		)

	def test_khoi_dong_thoi_gian_khong_gate_rieng_tren_don(self):
		"""VẾ ÂM của note (d) — `KhoiTienTrinh` cũ gate `v-if="don"` (đúng,
		nó ĐỌC `don.milestones`). Copy y nguyên điều kiện đó cho `KhoiDong
		ThoiGian` là SAI: ca mắt số 1 của Task 8 ("Phiếu vừa gửi duyệt")
		CHƯA CÓ đơn — nếu gate theo `don`, đúng ca đầu tiên chủ đầu tư sẽ
		mở lên để soi lại thấy khối RỖNG TRƠN, không phải một dòng xanh
		dương "Khoa gửi duyệt"."""
		m = re.search(r"<KhoiDongThoiGian\b[^>]*>", self.code)
		self.assertIsNotNone(m, "Không tìm thấy thẻ <KhoiDongThoiGian> trong template")
		the = m.group(0)
		self.assertNotRegex(
			the, r'v-if="don"',
			"<KhoiDongThoiGian> gate CHỈ theo `don` — ca 'Phiếu vừa gửi duyệt' "
			"(chưa có đơn) sẽ không render gì cả",
		)
		self.assertIn(
			"phieu", the,
			"<KhoiDongThoiGian> phải render được khi đã nạp PHIẾU (kể cả chưa có đơn)",
		)

	def test_khoi_dong_thoi_gian_duoc_truyen_prop_dong(self):
		"""Review vòng 1 (Important, phá thủ công) — reviewer xoá
		`:dong="nhatKy"` khỏi thẻ `<KhoiDongThoiGian>`. Bài `test_goi_nhat_
		ky_ca_hai_nhanh_phieu_va_don` canh lời GỌI API đúng, bài `test_
		khoi_dong_thoi_gian_render_sau_tien_trinh_truoc_truy_vet`/`...
		khong_gate_rieng_tren_don` canh VỊ TRÍ và GATE của thẻ — nhưng
		không bài nào canh thẻ có TRUYỀN prop `dong` xuống hay không. Hậu
		quả: API gọi đúng, component render đúng chỗ, nhưng khối RỖNG
		VĨNH VIỄN vì component không bao giờ nhận được dữ liệu — đúng
		kiểu "nửa-sống" note (d) đã cảnh, chỉ dịch từ "quên nhánh gọi"
		sang "gọi đúng nhưng quên nối dây"."""
		m = re.search(r"<KhoiDongThoiGian\b[^>]*>", self.code)
		self.assertIsNotNone(m, "Không tìm thấy thẻ <KhoiDongThoiGian> trong template")
		the = m.group(0)
		self.assertIn(
			':dong="nhatKy"', the,
			"<KhoiDongThoiGian> không truyền prop dong=\"nhatKy\" — API gọi đúng, "
			"render đúng chỗ, nhưng khối RỖNG VĨNH VIỄN vì không nhận dữ liệu",
		)
