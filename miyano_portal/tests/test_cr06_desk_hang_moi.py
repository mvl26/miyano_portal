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
