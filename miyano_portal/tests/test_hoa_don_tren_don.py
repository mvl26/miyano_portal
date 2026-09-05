"""Khối "Hoá đơn của đơn này" trên màn chi tiết đơn hàng.

Chủ đầu tư chốt 05/09/2026, ba việc:
  1. Nút PDF phải giao BẢN THỂ HIỆN HOÁ ĐƠN ĐIỆN TỬ của Fast, không phải bản
     in của ERP.
  2. Số hoá đơn bấm được, mở trang Hoá đơn với đúng dòng đó.
  3. Nhãn bỏ chữ "nháp" — nhưng GIỮ chốt chặn và giữ sự phân biệt.

Lỗi gốc: khối này gọi `portal_document_download` (bản in ERP) trong khi trang
"Hoá đơn & công nợ" gọi `portal_einvoice_download` (bản Fast). Cùng một nút
"PDF" trên hai màn hình giao HAI TỜ GIẤY KHÁC NHAU cho cùng một hoá đơn, và
tờ ở màn chi tiết không phải chứng từ thuế.

Không có hạ tầng test JS, nên phần giao diện được canh bằng lưới Python đọc
`.vue` bằng regex — cùng khuôn `test_nhat_ky_giao_dien.py`.
"""

import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase


def _doc(*phan) -> str:
	return (Path(frappe.get_app_path("miyano_portal")).parent.joinpath(*phan)).read_text(
		encoding="utf-8"
	)


class TestKhoiHoaDonGiaoDien(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.khoi = _doc("frontend", "src", "components", "chi-tiet", "KhoiHoaDonTaiLieu.vue")

	def _than_vong_lap(self) -> str:
		"""Cắt riêng thân `v-for` của danh sách hoá đơn.

		Cắt trước khi soi, KHÔNG soi cả file: ngay dưới vòng lặp còn nút "PDF
		đơn hàng" dùng ĐÚNG bản in ERP một cách hợp lệ (đơn hàng là chứng từ
		của ERP, không phải hoá đơn). Soi cả file thì bài dưới sẽ khớp nhầm
		vào nút đó và không canh gì.
		"""
		i = self.khoi.find('v-for="h in don.hoa_don"')
		self.assertNotEqual(i, -1, "Không tìm thấy vòng lặp danh sách hoá đơn")
		j = self.khoi.find("PDF đơn hàng", i)
		self.assertNotEqual(j, -1, "Không tìm thấy mốc cắt (nút PDF đơn hàng)")
		return self.khoi[i:j]

	def test_nut_pdf_hoa_don_dung_duong_hddt_khong_dung_ban_in_erp(self):
		"""Trong thân vòng lặp hoá đơn KHÔNG được còn `portal_document_download`.

		Đây là chính lỗi chủ đầu tư báo. Bài này đỏ khi ai đó đổi ngược lại,
		hoặc thêm một nút thứ hai dùng bản in ERP cho hoá đơn.
		"""
		than = self._than_vong_lap()
		# HAI ĐẦU, cố ý: chỗ DÙNG (thân vòng lặp gọi `hddtUrl`) và chỗ ĐỊNH
		# NGHĨA (hàm đó dựng URL từ `portal_einvoice_download`). Chỉ canh chỗ
		# định nghĩa thì đổi nút sang hàm khác vẫn xanh; chỉ canh chỗ gọi thì
		# đổi ruột `hddtUrl` sang bản in ERP vẫn xanh. Đây đúng lớp lỗi
		# "khớp chỗ khai thay cho chỗ dùng" mà nhánh này đã trả giá nhiều lần.
		self.assertIn(
			"hddtUrl(h.name)",
			than,
			"Nút PDF trong danh sách hoá đơn không gọi `hddtUrl(h.name)`",
		)
		self.assertRegex(
			self.khoi,
			r"function\s+hddtUrl\b[\s\S]{0,400}?portal_einvoice_download",
			"`hddtUrl()` không dựng URL từ `portal_einvoice_download` — khách "
			"sẽ nhận bản in ERP thay cho bản thể hiện hoá đơn điện tử của Fast.",
		)
		self.assertNotIn(
			"portal_document_download",
			than,
			"Thân vòng lặp hoá đơn vẫn còn `portal_document_download` (bản in "
			"ERP) — đúng lỗi đã vá ngày 05/09/2026.",
		)

	def test_nut_pdf_chi_hien_khi_tai_duoc(self):
		""""Hide, don't disable" — chưa phát hành thì không hiện nút.

		Không có `v-if` này thì khách bấm vào một nút chắc chắn ném lỗi
		("Hoá đơn điện tử này chưa có file để tải"), và một thanh công cụ
		bấm đâu cũng lỗi dạy người ta thôi bấm.
		"""
		than = self._than_vong_lap()
		self.assertRegex(
			than,
			r'v-if\s*=\s*"h\.hddt_tai_duoc"',
			"Nút PDF hoá đơn không bọc `v-if=\"h.hddt_tai_duoc\"`",
		)
		self.assertIn(
			"h.hddt_nhan",
			than,
			"Không hiện trạng thái thay cho nút khi chưa tải được — khách "
			"thấy một khoảng trống và không biết hoá đơn đang ở đâu.",
		)

	def test_so_hoa_don_bam_duoc_sang_trang_hoa_don(self):
		"""Số hoá đơn phải là `router-link` sang route `invoices` kèm tham số.

		Canh cả TÊN ROUTE lẫn TÊN THAM SỐ: đổi một trong hai mà quên chỗ kia
		là một liên kết mở đúng trang nhưng không mở đúng dòng — hỏng im lặng.
		"""
		than = self._than_vong_lap()
		self.assertIn("<router-link", than, "Số hoá đơn không phải liên kết")
		self.assertRegex(than, r"name:\s*'invoices'")
		self.assertRegex(than, r"'hoa-don':\s*h\.name")


class TestManHoaDonMoDungDong(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.man = _doc("frontend", "src", "views", "Invoices.vue")

	def test_loc_o_server_khong_loc_tren_trang_dang_tai(self):
		"""Tham số `ten` phải được gửi cho `portal_invoices`.

		Lọc trên mảng đã tải chỉ mở được hoá đơn nằm ở TRANG ĐANG XEM. Một
		bệnh viện giao dịch nhiều năm có hàng trăm hoá đơn, nên liên kết sẽ
		chạy với hoá đơn mới và im lặng không làm gì với hoá đơn cũ — thứ
		hỏng-lúc-được-lúc-không khó báo lỗi hơn hẳn thứ hỏng hẳn.
		"""
		self.assertRegex(
			self.man,
			r"ten:\s*locHoaDon\.value",
			"`Invoices.vue` không gửi tham số `ten` cho `portal_invoices`",
		)

	def test_co_duong_quay_lai_xem_tat_ca(self):
		"""Đang lọc một hoá đơn thì phải có đường thoát.

		Không có nút này, khách bấm từ màn đơn hàng sang thấy danh sách một
		dòng và tưởng mọi hoá đơn cũ đã biến mất.
		"""
		self.assertIn("xemTatCa", self.man)
		self.assertIn("Xem tất cả hoá đơn", self.man)


class TestNhanBoChuNhapNhungGiuPhanBiet(FrappeTestCase):
	"""Bỏ chữ "nháp" ở nhãn là việc của tầng hiển thị. Ba thứ dưới đây KHÔNG
	được đi theo — chúng là thứ ngăn một bản in thử được mang đi quyết toán."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.hoa_don_nhap = _doc("frontend", "src", "components", "HoaDonNhap.vue")
		cls.giao_hang = _doc("frontend", "src", "components", "chi-tiet", "KhoiGiaoHang.vue")

	def _chu_nguoi_dung_doc(self, ma: str) -> str:
		"""Bỏ chú thích JS (`//`) và chú thích HTML trước khi soi.

		Chú thích GIẢI THÍCH quyết định này nên đương nhiên có chữ "nháp";
		soi cả file là bài tự đỏ vì chính lời giải thích của nó.
		"""
		ma = re.sub(r"<!--.*?-->", "", ma, flags=re.S)
		return "\n".join(d for d in ma.splitlines() if not d.strip().startswith("//"))

	def test_khong_con_chu_nhap_o_phan_nguoi_dung_doc(self):
		for ten, ma in (("HoaDonNhap.vue", self.hoa_don_nhap), ("KhoiGiaoHang.vue", self.giao_hang)):
			with self.subTest(file=ten):
				self.assertNotIn("hoá đơn nháp", self._chu_nguoi_dung_doc(ma).lower())

	def test_van_giu_huy_hieu_noi_ro_chua_phat_hanh(self):
		"""Bỏ chữ "nháp" mà bỏ luôn dấu hiệu phân biệt là giao một bản in thử
		cho bệnh viện như thể nó là chứng từ thuế."""
		self.assertIn("Chưa phát hành", self.giao_hang)

	def test_van_giu_canh_bao_phap_ly_do_server_tra(self):
		"""Câu cảnh báo pháp lý (`einvoice.CANH_BAO_NHAP`) do SERVER trả —
		giao diện chỉ in ra, không gõ lại. Rơi mất nó là rơi mất thứ duy nhất
		nói với khách rằng đây chưa phải hoá đơn thật."""
		self.assertIn("duLieu.canh_bao", self.hoa_don_nhap)

	def test_chot_chan_o_server_khong_doi(self):
		"""`co_the_tai()` vẫn phải loại toàn nhóm nháp — nới nó là mở đường
		giao bản in thử qua đúng đường của hoá đơn thật."""
		from miyano_portal import einvoice

		for ma_trang_thai, (nhom, _l, _b) in einvoice._STATUS_META.items():
			if nhom == "nhap":
				with self.subTest(trang_thai=ma_trang_thai):
					self.assertFalse(
						einvoice.co_the_tai(frappe._dict(status=ma_trang_thai)),
						f"Trạng thái nháp {ma_trang_thai} lại tải được như hoá đơn thật",
					)
