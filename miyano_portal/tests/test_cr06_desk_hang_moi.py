"""Phía Miyano (Desk) phải ĐỌC ĐƯỢC thứ khách khai, và KHỚP MÃ được.

Chủ đầu tư báo 05/09/2026: *"sao không hiển thị các thông tin mà khách hàng
đã nhập cho hàng mới trên phần back của Miyano, em còn làm mất chức năng
khớp hàng thì sao mà khớp hàng để gửi cho khách"*.

Cả hai đều đúng, và cả hai đều do bản CR-03 gây ra:

1. **NGÂN SÁCH CỘT LƯỚI.** `grid.js` dựng cột bảng con theo một ngân sách:
   `total_colsize += df.colsize; if (total_colsize > 11) return false;`.
   Thêm `model_ma` (columns 2) vào lưới đẩy tổng từ 10 lên 12, nên vòng lặp
   BỎ DỞ và cột "Đã xử lý" rơi mất. Hỏng NGẦM — không lỗi, không cảnh báo,
   chỉ là một cột lặng lẽ biến mất khỏi màn của người đang khớp hàng.

2. **BẢY TRƯỜNG CR-03 `in_list_view: 0`**, tức chỉ hiện khi bung từng dòng;
   và `anh` là Small Text chứa JSON THÔ, nên người khớp hàng nhìn thấy chuỗi
   `["/private/files/…"]` chứ không thấy ảnh. Khách bỏ công chụp nhãn hộp
   CHÍNH LÀ để Miyano tìm được nguồn — để nó sau hai cú bấm và một chuỗi
   JSON là vứt bỏ đúng thứ CR-03 sinh ra để lấy.
"""

import json
import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

# `grid.js`: `if (total_colsize > 11) return false;` — VƯỢT 11 mới dừng, nên
# 11 là mức tối đa dùng được, không phải 10.
NGAN_SACH_COT = 11


def _goc() -> Path:
	return Path(frappe.get_app_path("miyano_portal"))


class TestNganSachCotLuoi(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.dt = json.loads(
			(_goc() / "miyano_portal" / "doctype" / "sales_order_dat_ngoai_item"
			 / "sales_order_dat_ngoai_item.json").read_text(encoding="utf-8")
		)

	def _trong_luoi(self):
		return [f for f in self.dt["fields"] if f.get("in_list_view")]

	def test_tong_cot_khong_vuot_ngan_sach(self):
		"""Vượt ngân sách thì Frappe BỎ DỞ vòng dựng cột — im lặng.

		Đây là bài quan trọng nhất file này: lỗi không ném exception, không
		ghi log, không bài test nào khác đỏ. Nó chỉ làm một cột biến mất khỏi
		màn hình của người đang làm việc, và chỉ người đó phát hiện ra.
		"""
		tong = sum(f.get("columns", 0) for f in self._trong_luoi())
		self.assertLessEqual(
			tong, NGAN_SACH_COT,
			f"Tổng `columns` của các field `in_list_view` là {tong}, vượt ngân "
			f"sách {NGAN_SACH_COT} của Frappe (`grid.js`). Lưới sẽ BỎ DỞ và "
			"những field cuối danh sách biến mất khỏi bảng con — không lỗi, "
			"không cảnh báo. Muốn thêm field vào lưới thì phải bỏ bớt field khác.",
		)

	def test_hai_cot_lam_viec_cua_MIYANO_phai_con_trong_luoi(self):
		"""`item_khop` và `da_xu_ly` là CÔNG CỤ LÀM VIỆC, không phải trang trí.

		`item_khop` là chỗ nhân viên gõ mã hàng khớp — mất nó là mất luôn
		chức năng khớp hàng. `da_xu_ly` là dấu cho biết dòng nào đã xong —
		mất nó thì không quét mắt biết còn dòng nào chưa khớp, mà một đơn còn
		dòng chưa khớp thì KHÔNG xác nhận được (`kiem_dat_ngoai_da_xu_ly`).
		"""
		ten = [f["fieldname"] for f in self._trong_luoi()]
		for f in ("item_khop", "da_xu_ly"):
			with self.subTest(field=f):
				self.assertIn(
					f, ten,
					f"`{f}` rơi khỏi lưới bảng con — nhân viên Miyano không "
					"khớp mã được nữa",
				)

	def test_model_ma_van_trong_luoi(self):
		"""Dữ kiện tìm nguồn giá trị nhất sau ảnh — người khớp hàng cần thấy
		ngay ở lưới, không phải bung từng dòng."""
		self.assertIn("model_ma", [f["fieldname"] for f in self._trong_luoi()])


class TestDeskHienThongTinKhachKhai(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.js = (_goc() / "public" / "js" / "sales_order.js").read_text(encoding="utf-8")
		# Lột chú thích JS trước khi soi: chính chú thích giải thích tính năng
		# này có chứa mọi chuỗi bài dưới tìm. Lỗi "khớp chỗ nói thay cho chỗ
		# dùng" đã xảy ra BỐN lần trong phiên.
		cls.ma = "\n".join(
			d for d in cls.js.splitlines() if not d.strip().startswith("//")
		)

	def test_co_khoi_hien_thong_tin_hang_moi(self):
		self.assertIn("hien_thong_tin_hang_moi", self.ma)
		self.assertRegex(
			self.ma, r"function\s+hien_thong_tin_hang_moi",
			"Không có hàm dựng khối thông tin hàng mới trên Desk",
		)

	def test_duoc_GOI_trong_refresh_khong_chi_dinh_nghia(self):
		"""Định nghĩa mà không gọi thì đúng bằng không có.

		Đây là lớp lỗi mà `docs/BAN-DO-CHUC-NANG.md` mục 4 ghi nhận đã lọt
		BẢY lần trong dự án này.
		"""
		i_ham = self.ma.find("function hien_thong_tin_hang_moi")
		truoc = self.ma[:i_ham] if i_ham != -1 else self.ma
		self.assertIn(
			"hien_thong_tin_hang_moi(frm)", truoc,
			"`hien_thong_tin_hang_moi` được định nghĩa nhưng KHÔNG được gọi "
			"trong `refresh` — khối sẽ không bao giờ hiện",
		)

	def test_hien_du_BAY_truong_khach_khai(self):
		for truong in ("model_ma", "hang_san_xuat", "nuoc_san_xuat", "quy_cach",
		               "ncc_hien_tai", "gia_hien_tai", "mo_ta_nhan_dang"):
			with self.subTest(truong=truong):
				self.assertIn(truong, self.ma, f"Desk không hiện `{truong}`")

	def test_anh_render_thanh_HINH_khong_phai_JSON_tho(self):
		"""`anh` là Small Text chứa JSON. In thẳng ra là người khớp hàng đọc
		một chuỗi `["/private/files/…"]` thay vì nhìn thấy nhãn hộp."""
		self.assertIn("JSON.parse", self.ma, "Không tách danh sách ảnh khỏi JSON")
		self.assertIn("<img", self.ma, "Không render ảnh thành hình")

	def test_escape_du_lieu_khach_go(self):
		"""Tên hàng, ghi chú, mô tả đều do KHÁCH gõ và được nhồi vào HTML.

		Không escape là mở một đường chèn HTML vào màn Desk của nhân viên
		Miyano — dữ liệu người dùng nhập, dựng thành thẻ, hiển thị cho người
		khác: đủ ba vế.
		"""
		self.assertIn("escape_html", self.ma, "Không escape dữ liệu khách gõ")


class TestCotDonGiaBangDaKhopMa(FrappeTestCase):
	"""Bảng "Đã khớp mã" trên cổng phải có cột ĐƠN GIÁ.

	Chủ đầu tư 05/09/2026. Trước bản này bảng đó nối được món khách xin với
	mã Miyano tìm ra, nhưng KHÔNG có giá — khách phải nhìn sang bảng mặt hàng
	chính mới biết được báo bao nhiêu. Câu đơn giản nhất của họ, *"món tôi
	xin, Miyano báo bao nhiêu?"*, bắt phải ghép hai chỗ.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		import re

		tho = (_goc().parent / "frontend" / "src" / "components" / "chi-tiet"
		       / "BangMatHang.vue").read_text(encoding="utf-8")
		# Lột chú thích HTML lẫn JS: chú thích giải thích tính năng này chứa
		# đúng những chuỗi bài dưới tìm. Lỗi "khớp chỗ nói thay cho chỗ dùng"
		# đã xảy ra BỐN lần trong phiên.
		tho2 = re.sub(r"<!--.*?-->", "", tho, flags=re.S)
		cls.ma = "\n".join(
			d for d in tho2.splitlines() if not d.strip().startswith("//")
		)

	def _doan_bang_da_khop(self) -> str:
		"""Cắt riêng bảng "Đã khớp mã".

		Cắt trước khi soi: ngay dưới nó là bảng "Đang chờ Miyano xác nhận
		nguồn" — bảng đó CỐ Ý không có giá (chưa khớp mã thì chưa có dòng
		hàng nào để mà có giá). Soi cả file sẽ không phân biệt được hai bảng.
		"""
		i = self.ma.find("Đã khớp mã (từ yêu cầu đặt ngoài)")
		self.assertNotEqual(i, -1, "Không tìm thấy bảng 'Đã khớp mã'")
		j = self.ma.find("Đang chờ Miyano xác nhận nguồn", i)
		self.assertNotEqual(j, -1, "Không tìm thấy mốc cắt (bảng kế tiếp)")
		return self.ma[i:j]

	def test_bang_da_khop_co_cot_don_gia(self):
		doan = self._doan_bang_da_khop()
		self.assertIn("Đơn giá", doan, "Bảng 'Đã khớp mã' không có cột Đơn giá")
		self.assertIn("giaDaKhop(d)", doan, "Cột giá không gọi `giaDaKhop(d)`")

	def test_gia_tra_theo_DONG_HANG_khong_theo_dong_dat_ngoai(self):
		"""Giá KHÔNG nằm trên dòng đặt ngoài.

		Khi khớp mã, `chuyen_dong_dat_ngoai_thanh_hang` dựng (hoặc gộp vào)
		một dòng hàng THẬT trong `items`, và giá sống ở đó. Đọc `d.rate` hay
		`d.don_gia` của dòng đặt ngoài sẽ luôn ra rỗng — một cột trống vĩnh
		viễn mà không ai đỏ.
		"""
		self.assertRegex(
			self.ma,
			r"function\s+giaDaKhop[\s\S]{0,400}?don\?\.items[\s\S]{0,200}?item_khop",
			"`giaDaKhop` không tra đơn giá từ `don.items` theo `item_khop`",
		)

	def test_gia_0_hien_CHO_BAO_GIA_khong_hien_so_0(self):
		"""Giá 0 nghĩa là MIYANO CHƯA BÁO GIÁ, không phải "miễn phí".

		Khớp được mã CHƯA CHẮC đã có giá: `_gop_hoac_them_dong_hang` chỉ tự
		lấy đơn giá khi mặt hàng thuộc một hợp đồng khung còn hiệu lực; ngoài
		ra để 0 và chờ Miyano điền.

		In "0 ₫" là nói với khoa một con số SAI — cùng luật với "—" của CR-04:
		chưa biết thì đừng in một con số.
		"""
		doan = self._doan_bang_da_khop()
		self.assertIn(
			"Chờ Miyano báo giá", doan,
			"Giá 0 không được in thành số — phải nói rõ là chưa báo giá",
		)
		self.assertRegex(
			doan, r"v-if\s*=\s*\"giaDaKhop\(d\)\"",
			"Không có nhánh phân biệt đã-có-giá với chưa-báo-giá",
		)


class TestOAnhVeHinhTrongDongLuoi(FrappeTestCase):
	"""Ô ảnh trong dòng lưới phải VẼ HÌNH, không in chuỗi JSON.

	Chủ đầu tư báo 06/09/2026, dán nguyên thứ họ nhìn thấy:
	`["/private/files/CR03_DXM-2026-00038_0_99fb6d_Chụp màn hình….png"]`

	`anh` là `Small Text` chứa JSON — Frappe in ra y nguyên thứ nó lưu. Khối
	tóm tắt ở đầu form (`sales_order.js`) CÓ vẽ ảnh, nhưng người khớp hàng làm
	việc TRONG dòng lưới, và ở đó họ vẫn thấy chuỗi thô. Sửa một chỗ mà bỏ
	quên chỗ người ta thật sự đứng là chưa sửa.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		import re

		cls.js = (_goc() / "public" / "js" / "dat_ngoai_anh.js").read_text(encoding="utf-8")
		cls.ma = "\n".join(
			d for d in cls.js.splitlines() if not d.strip().startswith("//")
		)
		cls.dt = json.loads(
			(_goc() / "miyano_portal" / "doctype" / "sales_order_dat_ngoai_item"
			 / "sales_order_dat_ngoai_item.json").read_text(encoding="utf-8")
		)
		cls.hooks = (_goc() / "hooks.py").read_text(encoding="utf-8")

	def _field(self, ten):
		return next((f for f in self.dt["fields"] if f["fieldname"] == ten), None)

	def test_co_o_HTML_rieng_de_ve_anh(self):
		f = self._field("anh_xem")
		self.assertIsNotNone(f, "Chưa có ô `anh_xem` để vẽ ảnh")
		self.assertEqual(f["fieldtype"], "HTML")

	def test_o_JSON_tho_bi_AN(self):
		"""`anh` giữ nguyên dữ liệu nhưng KHÔNG hiện — nếu không thì cạnh ô
		ảnh vẫn còn nguyên chuỗi JSON, tức chưa sửa được gì cho người đọc."""
		f = self._field("anh")
		self.assertTrue(f.get("hidden"), "Ô `anh` (JSON thô) vẫn hiện trên form")

	def test_ve_the_img_khong_in_chuoi(self):
		self.assertIn("JSON.parse", self.ma, "Không tách danh sách ảnh khỏi JSON")
		self.assertIn("<img", self.ma, "Không vẽ ảnh thành thẻ <img>")

	def test_doc_parentfield_TU_DONG_khong_go_cung(self):
		"""Bảng con này sống trên CẢ `Sales Order` (`custom_dat_ngoai`) LẪN
		`Portal De Xuat Mua` (`dat_ngoai`).

		Gõ cứng một tên là ô ảnh chỉ chạy ở MỘT màn, và màn kia vẫn hiện chuỗi
		JSON mà không ai biết — đúng kiểu hỏng vừa phải sửa.
		"""
		self.assertIn("row.parentfield", self.ma,
		              "Không đọc `parentfield` từ chính dòng")
		self.assertNotIn('"custom_dat_ngoai"', self.ma,
		                 "Gõ cứng tên bảng con của Sales Order")

	def test_nap_o_CA_HAI_form(self):
		"""Handler đăng ký theo BẢNG CON, nên phải nạp ở cả hai doctype cha —
		nếu không thì màn không nạp vẫn hiện chuỗi thô."""
		# Tìm KHỐI KHAI THẬT, không phải dòng chú thích `# doctype_js = ...`
		# ở ngay trên nó — bản đầu của bài này cắt trúng dòng chú thích và
		# đỏ dù hooks hoàn toàn đúng. Cắt tới dấu `}` đóng khối để không phụ
		# thuộc vào độ dài chú thích bên trong.
		i = self.hooks.find("\ndoctype_js = {")
		self.assertNotEqual(i, -1, "Không tìm thấy khối khai `doctype_js`")
		khoi = self.hooks[i:self.hooks.index("\n}", i)]
		self.assertIn("dat_ngoai_anh.js", khoi)
		self.assertIn('"Portal De Xuat Mua"', khoi,
		              "Chưa nạp cho form phiếu — màn đó vẫn hiện JSON thô")

	def test_escape_duong_dan_tep(self):
		"""Tên tệp do khách đặt (ảnh họ tải lên) và được nhồi vào HTML."""
		self.assertIn("escape_html", self.ma)

	def test_json_hong_khong_lam_chet_dong(self):
		self.assertIn("catch", self.ma,
		              "Field `anh` hỏng sẽ ném lỗi và làm chết cả dòng lưới")
