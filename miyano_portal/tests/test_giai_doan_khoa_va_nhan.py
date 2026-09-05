"""Ruling P54 (chủ đầu tư chốt 26/08/2026) — TÁCH KHOÁ khỏi NHÃN cho dòng
đời "Yêu cầu của tôi".

Sự thật tìm ra khi soát đề nghị đổi tên "Chờ báo giá" → "Chờ quý vị đồng ý":
**một nhãn hiển thị đang bị dùng làm định danh.** Cùng một chuỗi tiếng Việt
vừa là chữ in trên chip, vừa là khoá lọc `giai_doan` của
`portal_yeu_cau_cua_toi`, vừa là giá trị đi trong URL (`?chip=`) mà các màn
chi tiết mang qua lại — nên sửa một chữ vì lý do BIÊN TẬP sẽ làm chết những
liên kết đã gửi cho bệnh viện. Đó đúng lớp lỗi "một thứ gánh hai vai".

Sau P54:

  * **Máy chủ nói KHOÁ.** `api/portal.py` giữ `GIAI_DOAN_*` là chuỗi ASCII
    không dấu (`cho_khach_dong_y`, …), `_sql_giai_doan()` sinh khoá, và
    `portal_yeu_cau_cua_toi` lọc theo khoá. Máy chủ KHÔNG nói tiếng Việt về
    giai đoạn nữa.
  * **Giao diện giữ NHÃN.** `frontend/src/format.js` là nơi DUY NHẤT ánh xạ
    khoá → nhãn. Không đặt thêm một bản nhãn ở máy chủ: chip phải vẽ được
    TRƯỚC khi có dòng nào tải về, nên giao diện buộc phải có bảng ánh xạ —
    thêm một bản nữa ở máy chủ là đúng vết xe `_so_status_vi`/
    `_so_status_vi_full` đã phải gộp lại một lần rồi.
  * **Bí danh cho chuỗi CŨ** (đóng băng, chỉ gồm nhãn đã từng phát ra
    ngoài) sống ở CẢ HAI phía: máy chủ cho người gọi API, giao diện cho
    `?chip=` trong link cũ.

Lớp này canh phía GIAO DIỆN (nhãn + bí danh chip + không còn so sánh bằng
nhãn), vì `yarn build` xanh trơn với mọi lỗi trong số đó. Cùng khuôn và
cùng lý do `test_de_xuat_action_registry.py` — đọc docstring ở đó. Phía máy
chủ (khoá trả ra + bí danh của endpoint) được canh ở
`test_yeu_cau_list.py`, nơi đã có sẵn fixture dựng đơn ở đúng giai đoạn.

VÌ SAO KHÔNG canh nhãn mới bằng một bài Python gọi endpoint: endpoint không
trả nhãn nữa. Đòi nó trả nhãn chỉ để test được chính là dựng lại bản sao
thứ hai mà P54 vừa bỏ.
"""

import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"
FORMAT_JS = FRONTEND_SRC / "format.js"
YEU_CAU_LIST = FRONTEND_SRC / "views" / "YeuCauList.vue"

KHOA_GIAI_DOAN = (
	"nhap", "cho_duyet", "da_duyet", "cho_khach_dong_y",
	"da_giao", "tu_choi", "da_huy",
)

# Nhãn CŨ từng vừa là chữ hiển thị vừa là khoá — chính là bộ chuỗi đã đi ra
# ngoài trong `?chip=`. Đóng băng: không thêm nhãn MỚI vào đây, nếu không ta
# lại buộc nhãn vào định danh đúng như trước P54.
NHAN_CU = ("Nháp", "Chờ duyệt", "Đã duyệt", "Chờ báo giá", "Đã giao", "Từ chối", "Đã huỷ")


class TestNhanGiaiDoanOTangHienThi(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.format_js = FORMAT_JS.read_text(encoding="utf-8")
		cls.yeu_cau_list = YEU_CAU_LIST.read_text(encoding="utf-8")

	def _bang_nhan(self) -> dict:
		"""Đọc bảng `NHAN_GIAI_DOAN` trong `format.js` thành dict.

		Cắt bằng đếm ngoặc rồi bóc từng cặp `khoa: 'nhãn'` — không parse JS
		(cùng lý do `test_de_xuat_action_registry.py` đã ghi: một parser JS
		trong test Python là thứ phải bảo trì mà không đổi lại được gì)."""
		i = self.format_js.find("NHAN_GIAI_DOAN")
		self.assertNotEqual(i, -1, "format.js chưa có bảng NHAN_GIAI_DOAN (khoá → nhãn)")
		mo = self.format_js.find("{", i)
		self.assertNotEqual(mo, -1, "NHAN_GIAI_DOAN không có thân object")
		sau = 0
		dong = None
		for j in range(mo, len(self.format_js)):
			if self.format_js[j] == "{":
				sau += 1
			elif self.format_js[j] == "}":
				sau -= 1
				if sau == 0:
					than = self.format_js[mo:j + 1]
					dong = dict(re.findall(r"(\w+)\s*:\s*'([^']*)'", than))
					break
		self.assertIsNotNone(dong, "NHAN_GIAI_DOAN không đóng ngoặc — tệp hỏng?")
		return dong

	def test_bay_khoa_deu_co_nhan(self):
		"""Một khoá thiếu nhãn sẽ hiện ra người dùng dưới dạng `cho_duyet` —
		chữ dành cho máy, rơi thẳng lên màn hình."""
		self.assertEqual(set(self._bang_nhan()), set(KHOA_GIAI_DOAN))

	def test_nhan_moi_dung_chu_chu_dau_tu_chot(self):
		"""Quyết định của chủ đầu tư (26/08/2026): giai đoạn mà BÁO GIÁ ĐÃ
		VỀ và bệnh viện đang giữ việc nay đọc là "Chờ quý vị đồng ý". Tên cũ
		("Chờ báo giá") nói NGƯỢC — nó đọc như đang chờ Miyano, trong khi
		đơn chờ Miyano ra giá lại nằm ở "Đã duyệt"."""
		self.assertEqual(self._bang_nhan()["cho_khach_dong_y"], "Chờ quý vị đồng ý")

	def test_khong_con_nhan_giai_doan_nao_ghi_Cho_bao_gia(self):
		"""Vế răng của bài trên. `Chờ báo giá` VẪN ĐÚNG và VẪN Ở LẠI ở nghĩa
		THỨ HAI — nhãn TẦNG GIÁ của một dòng hàng chưa có giá hợp đồng, trên
		`LapPhieu.vue`. Bài này vì thế chỉ soi bảng nhãn GIAI ĐOẠN, không
		soi cả kho: soi cả kho sẽ đỏ vì đúng những chỗ phải giữ nguyên."""
		self.assertNotIn("Chờ báo giá", self._bang_nhan().values())

	def test_badge_khoa_theo_KHOA_chu_khong_theo_nhan(self):
		"""Bảng màu badge cũng phải chuyển sang khoá. Còn khoá bằng nhãn thì
		mọi badge im lặng rơi về `b-gray` ngay khi nhãn đổi — hỏng đúng kiểu
		tệ nhất: màn vẫn chạy, chỉ mất hết màu."""
		i = self.format_js.find("giaiDoanBadge")
		self.assertNotEqual(i, -1, "format.js không còn giaiDoanBadge")
		than = self.format_js[i:i + 600]
		for khoa in KHOA_GIAI_DOAN:
			self.assertIn(khoa, than, f"giaiDoanBadge không nhận khoá {khoa}")

	def test_chip_trong_URL_mang_KHOA(self):
		"""`FILTERS` là thứ vừa vẽ chip, vừa được ghi vào `?chip=`, vừa gửi
		lên `giai_doan` — nên nó PHẢI là bộ khoá. Đây chính là chỗ trước P54
		buộc URL vào chữ tiếng Việt.

		Đo ở HAI vế vì `FILTERS` nay trải từ `GIAI_DOAN` của `format.js`
		(một nguồn, không chép tay lần hai): bộ khoá phải ĐỦ BẢY ở nơi khai,
		và `FILTERS` không được gài lại nhãn cũ ở nơi dùng."""
		i = self.format_js.find("export const GIAI_DOAN")
		self.assertNotEqual(i, -1, "format.js chưa khai bộ khoá GIAI_DOAN")
		khai = self.format_js[i:self.format_js.find("]", i)]
		self.assertEqual(
			set(re.findall(r"'(\w+)'", khai)), set(KHOA_GIAI_DOAN),
			"GIAI_DOAN không đúng bảy khoá của GIAI_DOAN_HOP_LE",
		)
		j = self.yeu_cau_list.find("const FILTERS")
		self.assertNotEqual(j, -1, "YeuCauList.vue không còn danh sách FILTERS")
		than = self.yeu_cau_list[j:self.yeu_cau_list.find("]", j)]
		for nhan in NHAN_CU:
			self.assertNotIn(f"'{nhan}'", than, f"FILTERS còn dùng nhãn cũ {nhan!r}")

	def test_link_cu_mang_chuoi_CU_van_khoi_phuc_duoc_chip(self):
		"""Ruling P54 mục 3 — và là chỗ dễ tưởng đã xong nhất.

		Bí danh phía MÁY CHỦ MỘT MÌNH KHÔNG CỨU được link cũ: đường đi thật
		là `?chip=Chờ báo giá` → `onMounted` → rào `FILTERS.includes(...)`.
		Khi `FILTERS` đã là bộ khoá, rào đó trả `false`, `filter` ở nguyên
		`''`, và máy chủ được gọi với `giai_doan=undefined` — bí danh máy
		chủ KHÔNG BAO GIỜ được chạm tới, còn bệnh viện thì thấy "Tất cả".
		Nên phía giao diện phải có bảng bí danh của CHÍNH nó."""
		# BỎ CHÚ THÍCH TRƯỚC KHI ĐO. Bản đầu của bài này chỉ tìm chữ
		# "khoaGiaiDoan" trong một cửa sổ quanh `route.query.chip`, và một
		# phép đột biến gỡ đúng lời gọi đó VẪN XANH — vì chính đoạn chú
		# thích giải thích cơ chế cũng chứa cái tên. Một lưới đọc mã nguồn
		# mà tính cả lời bình là một lưới đo văn xuôi.
		ma = re.sub(r"//[^\n]*", "", self.yeu_cau_list)
		self.assertIn(
			"khoaGiaiDoan(route.query.chip)", ma,
			"Đường khôi phục `?chip=` chưa đi qua bộ chuẩn hoá khoá/bí danh",
		)

	def test_khong_con_cho_nao_SO_SANH_bang_nhan_giai_doan(self):
		"""`coTheSuaNhap()` so `r.giai_doan === 'Nháp'`. Bỏ sót chỗ này thì
		nút "Sửa" IM LẶNG biến mất khỏi mọi phiếu Nháp — không lỗi, không
		toast, và chính chú thích quanh nó dặn client phải đoán ĐÚNG như
		server.

		Chỉ soi HAI tệp của tầng giai đoạn, và chỉ soi NGOÀI bảng nhãn:
		`LapPhieu.vue` giữ đúng chuỗi "Chờ báo giá" ở nghĩa TẦNG GIÁ và
		không được đụng tới."""
		than_nhan = str(self._bang_nhan())
		for ten, nguon in (
			("YeuCauList.vue", self.yeu_cau_list),
			("format.js", self.format_js),
		):
			for nhan in NHAN_CU:
				if nhan in than_nhan and ten == "format.js":
					continue
				self.assertNotIn(
					f"=== '{nhan}'", nguon,
					f"{ten} còn so sánh giai đoạn bằng NHÃN {nhan!r} thay vì khoá",
				)
