"""Chứng từ đề xuất mua của khoa phòng (spec §5).

KHÔNG dùng module Workflow của Frappe — `trang_thai` là Select thường, đúng
khuôn `Portal Item Request`. Lý do: máy trạng thái ở §5.4 có cạnh quay lui
(`Từ chối --sửa--> Chờ duyệt`) và vài chốt theo nội dung (bắt buộc lý do khi
từ chối) mà Workflow không biểu diễn gọn hơn một bảng viết tay.

Zero DocPerm cho role `Customer` — khách chỉ vào qua `api/de_xuat.py`, suy
khách và khoa từ phiên đăng nhập. Nhân sự Miyano CÓ quyền desk (như mọi
doctype cổng khác) để hỗ trợ được khi bệnh viện gọi. Bảo đảm "Miyano không
thấy đơn chưa duyệt" của §5.1 do việc đây là một doctype RIÊNG mang lại —
không có `SAL-ORD` nào sinh ra trước khi bệnh viện chốt, nên không có đơn ma
nào lọt vào danh sách, báo cáo, dashboard của Miyano — chứ không do DocPerm.

(Sửa spec §5.1 — vòng sửa 19/08/2026: bản đầu của §5.1 viết "Miyano không
được cấp quyền nào trên doctype này", mạnh hơn thứ mà chính §5.1 cần và trái
với tiền lệ ba doctype cổng khác (`Portal Item Request`/`Portal Delivery
Inspection`/`Portal Member`, cả ba đều cấp desk cho System Manager/Sales
Manager/Sales User, zero cho `Customer`). Bất biến thật của app là "zero
DocPerm cho Customer", không phải "zero DocPerm tuyệt đối" — bắt được bởi
`test_kho_isolation.py::TestKhoDocPermConfig.test_staff_roles_keep_desk_
permissions`.)
"""

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from miyano_portal.ma_de_xuat import sinh_ma

TRANG_THAI_NHAP = "Nháp"
TRANG_THAI_CHO_DUYET = "Chờ duyệt"
TRANG_THAI_DA_DUYET = "Đã duyệt"
TRANG_THAI_TU_CHOI = "Từ chối"
TRANG_THAI_DA_HUY = "Đã huỷ"
# Task 9 dùng — vòng sửa sau khi bị từ chối. Khai sẵn hằng ở đây để Task 9
# không phải sửa lại chỗ này, dù chưa có cạnh nào của máy trạng thái đi tới
# nó trong task này (chưa thêm vào options của field `trang_thai`).
TRANG_THAI_CHO_DUYET_SUA = "Chờ duyệt sửa"

# Task 9, I2 (review) — sentinel cho "dòng này CHƯA có yêu cầu xin sửa".
# KHÔNG dùng `0`/`None`:
#   - `0` tự nó là một giá trị xin sửa HỢP LỆ — đúng quy ước "Số lượng 0 =
#     bỏ dòng đó" mà `portal_order_sua_so_luong` đã định nghĩa. Coi `0` là
#     falsy = "chưa có yêu cầu" (bản đầu của Task 9) làm mất LẶNG LẼ đúng
#     yêu cầu nguy hiểm nhất: khoa xin BỎ một mặt hàng.
#   - `None` không sống sót qua một lần `save()`: field Float đi qua
#     `BaseDocument.get_valid_dict()` (frappe/model/base_document.py), nơi
#     mọi field thuộc `float_like_fields` bị ép `flt(value)` nếu chưa phải
#     `float` — `flt(None)` trả `0.0`, tức Frappe tự đổi `None` thành `0`
#     ngay trong lần lưu kế tiếp, quay lại đúng chỗ mơ hồ vừa nêu.
# Số lượng thật không bao giờ âm (`portal_order_sua_so_luong` chặn `qty <
# 0`), nên `-1` là sentinel AN TOÀN — không trùng bất kỳ giá trị hợp lệ nào.
SO_LUONG_XIN_SUA_TRONG = -1


class PortalDeXuatMua(Document):
	CHUYEN_HOP_LE = {
		TRANG_THAI_NHAP: {TRANG_THAI_CHO_DUYET},
		TRANG_THAI_CHO_DUYET: {TRANG_THAI_DA_DUYET, TRANG_THAI_TU_CHOI, TRANG_THAI_DA_HUY},
		TRANG_THAI_TU_CHOI: {TRANG_THAI_CHO_DUYET, TRANG_THAI_DA_HUY},
		# Task 9 (§12 Q4) — `Đã duyệt` THÔI là trạng thái kết thúc. Cạnh này
		# là chỗ DUY NHẤT đi ra, và nó quay về đúng `Đã duyệt` sau khi quản
		# lý xử lý yêu cầu xin sửa (đồng ý hoặc từ chối). Trước task này,
		# "Đã duyệt" là một lá trong CHUYEN_HOP_LE (không xuất hiện làm
		# chìa khoá) — thay đổi này là CỐ Ý, không phải sơ suất bỏ quên
		# một cạnh: nhân viên khoa xin sửa số lượng một đơn đã duyệt phải
		# đi qua đây, không được chạm thẳng Sales Order (xem `dam_bao_duoc_
		# sua_don_da_duyet` ở `portal_context.py`).
		TRANG_THAI_DA_DUYET: {TRANG_THAI_CHO_DUYET_SUA},
		TRANG_THAI_CHO_DUYET_SUA: {TRANG_THAI_DA_DUYET},
	}
	# Trạng thái kết thúc CỐ Ý không xuất hiện làm chìa khoá — không có cạnh
	# đi ra từ chúng. Cùng khuôn với `Portal Item Request`.

	def validate(self):
		self._chan_khoa_phong_khac_benh_vien()
		self._chan_sua_so_luong_de_xuat()
		# I3 (review tổng) — SAU `_chan_sua_so_luong_de_xuat()` CỐ Ý: khi
		# một thao tác vi phạm cả hai luật (thêm dòng trùng mã VỚI số lượng
		# đề xuất khác 0 sau khi đã gửi duyệt), thông điệp về cột đã khoá
		# vẫn là thông điệp đúng và cụ thể hơn cho người dùng.
		self._chan_trung_ma_hang()
		self._suy_tu_duyet()

	def _chan_trung_ma_hang(self):
		"""I3 (review tổng 19/08) — hai dòng cùng `item_code` làm số trên
		phiếu GẤP ĐÔI số trên đơn.

		Hậu quả đi vòng qua BA tầng, không tầng nào tự phát hiện được:
		  * `api/de_xuat._ap_dieu_chinh` dựng `{d.item_code: d}` → chỉ dòng
		    CUỐI nhận điều chỉnh của quản lý;
		  * `dat_hang.tao_sales_order` GỘP hai dòng thành MỘT dòng SO;
		  * `api/portal._dong_bo_so_luong_duyet_ve_phieu` ghi số ĐÃ GỘP
		    ngược lên CẢ HAI dòng.
		Phiếu X:6 + X:4 → SO X:10 → quản lý sửa còn 7 → phiếu nói 14, đơn
		nói 7.

		Chốt ở TẦNG THẤP NHẤT (`validate()` của doctype), không ở endpoint:
		bốn đường ghi khác nhau (`de_xuat_luu_nhap`, `_ap_dieu_chinh`,
		`portal_order_place` → `_dam_bao_phieu_tu_duyet`, và desk của nhân
		sự Miyano) đều phải chịu cùng một luật, và một luật lặp ở bốn nơi
		sớm muộn cũng lệch.
		"""
		da_thay = set()
		for d in self.items:
			if d.item_code in da_thay:
				frappe.throw(
					f'Mã hàng "{d.item_code}" xuất hiện nhiều hơn một dòng '
					"trên phiếu. Gộp lại thành một dòng với tổng số lượng — "
					"đơn hàng sinh ra luôn gộp các dòng cùng mã, nên để hai "
					"dòng sẽ làm số trên phiếu và số trên đơn nói khác nhau.",
					frappe.ValidationError,
				)
			da_thay.add(d.item_code)

	def _suy_tu_duyet(self):
		"""`tu_duyet` LUÔN suy từ `nguoi_duyet == owner`, không bao giờ nhận
		trực tiếp — kể cả từ `.duyet()` (Task 3) chính nó. Chuyển vào
		`validate()` (Task 7, review M4) thay vì chỉ tính tay trong
		`.duyet()`: đường `portal_order_place` → `_dam_bao_phieu_tu_duyet()`
		(§5.5) tạo THẲNG một phiếu "Đã duyệt" mà KHÔNG đi qua `.duyet()`
		(không có ai "đang chờ duyệt" để mà chuyển trạng thái tới) — nếu chỉ
		tính trong `.duyet()`, đường đó buộc phải tự tính tay lần thứ hai,
		đúng kiểu hai chỗ cùng viết một sự thật rồi sớm muộn lệch nhau mà
		module này đã tự nhắc chính nó tránh (`de_xuat_duyet.py`,
		"Ruling preflight C2"). `nguoi_duyet` rỗng (phiếu chưa từng duyệt)
		thì bỏ qua — không ép `tu_duyet` về 0 sớm hơn cần thiết, dù giá trị
		mặc định của field vốn đã là 0."""
		if self.nguoi_duyet:
			self.tu_duyet = 1 if self.nguoi_duyet == self.owner else 0

	def _kiem_chuyen(self, dich):
		if dich not in self.CHUYEN_HOP_LE.get(self.trang_thai, set()):
			frappe.throw(
				f'Không chuyển được phiếu từ "{self.trang_thai}" sang "{dich}".',
				frappe.ValidationError,
			)

	def gui_duyet(self):
		self._kiem_chuyen(TRANG_THAI_CHO_DUYET)
		if not (self.ly_do_yeu_cau or "").strip():
			frappe.throw(
				"Lý do yêu cầu là bắt buộc khi gửi duyệt.", frappe.ValidationError
			)
		if not self.ma_de_xuat:
			# Sinh ĐÚNG MỘT LẦN. Phiếu bị từ chối rồi gửi lại giữ nguyên mã cũ:
			# quản lý và khoa đã gọi tên nó bằng mã đó trong lúc trao đổi.
			self.ma_de_xuat = sinh_ma(self.customer, self.khoa_phong)
		self.thoi_diem_gui = now_datetime()
		self._dong_dau_gia()
		self._dong_dau_so_luong_duyet()
		self.trang_thai = TRANG_THAI_CHO_DUYET
		self.save(ignore_permissions=True)
		# Task 8 (§5.8) — CHỈ quản lý cần biết có phiếu chờ duyệt. Hàm này
		# không bao giờ ném lỗi (xem docstring nó) nên an toàn gọi ngay sau
		# save(): một trục trặc ở khâu thông báo không được cuốn theo trạng
		# thái "Chờ duyệt" vừa ghi thành công.
		from miyano_portal.portal_thong_bao_khach import bao_de_xuat_gui_duyet
		bao_de_xuat_gui_duyet(self)

	def _dong_dau_so_luong_duyet(self):
		"""C2 (review tổng 19/08) — đóng dấu `so_luong_duyet = so_luong_de_
		xuat` CÙNG LÚC cột đề xuất bị khoá (`_chan_sua_so_luong_de_xuat`).

		§5.3 nói "Quản lý chỉ chạm `so_luong_duyet`. Bỏ một mặt hàng = HẠ VỀ
		0" — "hạ về 0" chỉ có nghĩa nếu nó KHỞI ĐẦU KHÁC 0. Trước bản vá,
		`so_luong_duyet` giữ default `"0"` từ lúc lưu nháp và không hàm nào
		trong app đụng tới nó, nên quản lý bấm "duyệt nguyên trạng"
		(`de_xuat_duyet_phieu(ten)` KHÔNG truyền `dieu_chinh` — chữ ký
		`dieu_chinh=None` HỨA rằng đường đó chạy được) ăn thẳng
		`frappe.throw("Không còn dòng nào có số lượng duyệt lớn hơn 0.")`
		trên MỌI phiếu: không đơn nào sinh ra.

		GHI CHÚ có chủ ý: phiếu bị Từ chối rồi sửa rồi GỬI LẠI đi qua đây
		lần thứ hai, và lần đó sẽ ĐẶT LẠI `so_luong_duyet` theo cột đề xuất,
		xoá điều chỉnh quản lý đã gõ ở vòng trước. Đúng ý: vòng trước kết
		thúc bằng TỪ CHỐI (không có gì được duyệt), và phiếu gửi lại là một
		đề nghị MỚI của khoa — quản lý phải nhìn lại từ đầu, không thừa
		hưởng con số của một lần từ chối.

		`_chan_sua_so_luong_de_xuat()` không cản: guard đó chỉ khoá
		`so_luong_de_xuat`/`item_code`/việc xoá dòng, KHÔNG khoá cột duyệt
		(xem `test_de_xuat_doctype.py::test_so_luong_duyet_van_sua_duoc_sau_
		khi_gui`).
		"""
		for row in self.items:
			row.so_luong_duyet = row.so_luong_de_xuat

	def _dong_dau_gia(self):
		"""§5.6 bẫy #2 (vòng sửa Task 6) — đóng dấu `don_gia` = giá hiện hành
		TẠI THỜI ĐIỂM GỬI DUYỆT, cùng lúc `so_luong_de_xuat` bị khoá vĩnh
		viễn (`_chan_sua_so_luong_de_xuat`). Đây là "giá khoa đã thấy" mà
		`de_xuat_duyet.duyet_va_tao_don()` so với giá tính lại lúc DUYỆT để
		cảnh báo quản lý — không cảnh báo được gì nếu không có số này.

		Dùng ĐÚNG nguồn giá `dat_hang` dùng (`_gia_hien_hanh`) — hai đường
		tra giá khác nhau sớm muộn cũng lệch, cùng lý do module đó không tự
		viết một hàm tra giá thứ hai cho nhánh HĐNT/mua lẻ của chính nó.

		CHỈ áp dụng HĐNT — mua lẻ không tra giá ở đâu cả trong toàn bộ luồng
		(§4.5, `rate = 0`, sales điền khi báo giá), nên không có "giá khoa
		đã thấy" nào để đóng dấu. Mặt hàng không tra được giá (chưa có
		trong bảng giá hợp đồng) thì để `don_gia` RỖNG, KHÔNG throw — gửi
		duyệt chưa phải lúc chặn vì thiếu giá, đó là việc của lúc duyệt/tạo
		đơn (`dat_hang._xay_don_hdnt`).
		"""
		if self.loai_don != "HĐNT" or not self.hdnt:
			return
		price_list = frappe.db.get_value("Customer", self.customer, "default_price_list")
		if not price_list:
			return
		from miyano_portal import dat_hang
		for row in self.items:
			rate = dat_hang._gia_hien_hanh(row.item_code, price_list)
			if rate:
				row.don_gia = rate

	def duyet(self, nguoi_duyet, tu_cach="Quản lý chính", uy_quyen=None):
		"""Nơi DUY NHẤT ghi `Đã duyệt` LẦN ĐẦU — cùng cả khối truy vết
		(người duyệt, thời điểm, tư cách). SỬA (Minor, review Task 9):
		`duyet_sua()`/`tu_choi_sua()` ở dưới, từ Task 9, cũng hợp lệ ghi
		`Đã duyệt` — đó là VÒNG SỬA đi qua "Chờ duyệt sửa", KHÔNG tạo khối
		truy vết mới (không đụng `nguoi_duyet`/`thoi_diem_duyet`/`duyet_voi_
		tu_cach` — khối đó vẫn chỉ mang dấu của lần duyệt ĐẦU TIÊN, xem nợ
		kỹ thuật điều phối viên đã ghi nhận), nên hàm NÀY vẫn là nơi DUY
		NHẤT ghi khối truy vết đó — chỉ không còn là nơi duy nhất ghi TÊN
		trạng thái "Đã duyệt" nữa.

		`tu_duyet` SUY RA từ `nguoi_duyet == self.owner`, không nhận tham số
		riêng: một cờ tự khai đúng lúc cần nhất (chính người tạo phiếu tự
		duyệt cho mình) sẽ không được khai nếu để caller tự truyền. Việc
		tính giờ nằm ở `_suy_tu_duyet()` (gọi từ `validate()`), KHÔNG viết
		tay ở đây nữa (Task 7, review M4) — để `portal_order_place` (tạo
		THẲNG một phiếu "Đã duyệt", không qua `.duyet()`) không phải tự tính
		lại phép suy này lần thứ hai.
		"""
		self._kiem_chuyen(TRANG_THAI_DA_DUYET)
		self.nguoi_duyet = nguoi_duyet
		self.thoi_diem_duyet = now_datetime()
		self.duyet_voi_tu_cach = tu_cach
		self.uy_quyen = uy_quyen
		self.trang_thai = TRANG_THAI_DA_DUYET
		self.save(ignore_permissions=True)
		# Task 8 (§5.8) — quản lý (luôn) + thành viên khác của khoa đứng
		# tên phiếu. Không bao giờ ném lỗi — cùng lý do gọi trong gui_duyet().
		from miyano_portal.portal_thong_bao_khach import bao_de_xuat_duyet
		bao_de_xuat_duyet(self)

	def tu_choi(self, ly_do):
		self._kiem_chuyen(TRANG_THAI_TU_CHOI)
		if not (ly_do or "").strip():
			frappe.throw(
				"Lý do từ chối là bắt buộc khi từ chối phiếu.", frappe.ValidationError
			)
		self.ly_do_tu_choi = ly_do
		self.trang_thai = TRANG_THAI_TU_CHOI
		self.save(ignore_permissions=True)
		# Task 8 (§5.8) — cùng bảng người nhận với duyệt().
		from miyano_portal.portal_thong_bao_khach import bao_de_xuat_tu_choi
		bao_de_xuat_tu_choi(self)

	def huy(self):
		"""§5.4b — phiếu còn nguyên, chỉ đổi trạng thái. Khác XOÁ THẬT ở chỗ
		vẫn truy vết được sau này."""
		self._kiem_chuyen(TRANG_THAI_DA_HUY)
		self.trang_thai = TRANG_THAI_DA_HUY
		self.save(ignore_permissions=True)

	def xin_sua(self, dong: list[dict]):
		"""Task 9 (§12 Q4) — nhân viên khoa xin sửa số lượng một đơn ĐÃ
		được quản lý duyệt. Ghi lên CỘT THỨ BA `so_luong_xin_sua`, KHÔNG đè
		`so_luong_duyet` (§5.3, không xoá dữ liệu gốc để ghi dữ liệu mới):
		quản lý phải nhìn thấy song song "đã duyệt bao nhiêu" / "khoa xin
		đổi thành bao nhiêu". Đơn Sales Order KHÔNG bị chạm ở đây — chỉ khi
		quản lý gọi `duyet_sua()` (qua lõi `portal_order_sua_so_luong`) thì
		đơn mới thật sự đổi.

		`dong` — danh sách `{"item_code": str, "qty": float}`, cùng hình
		dạng phần `items` của `dong` trong `portal.portal_order_sua_so_
		luong`. Mã hàng không khớp dòng nào trên phiếu bị bỏ qua lặng lẽ —
		endpoint gọi hàm này (`de_xuat.de_xuat_xin_sua`) không cho thêm
		dòng mới, cùng luật `portal_order_sua_so_luong` đã áp cho khách.

		I2 (review Task 9) — `qty` THIẾU (không có khoá, hoặc `None`) thì
		BỎ QUA dòng đó (giữ nguyên sentinel `SO_LUONG_XIN_SUA_TRONG`, không
		phải "chưa có yêu cầu"); `qty = 0` GHI THẲNG `0` — đó là một yêu cầu
		THẬT ("xin bỏ dòng này"), không phải giá trị rỗng. Trước bản vá,
		`float(row.get("qty") or 0)` gộp cả hai trường hợp làm một.

		C1 + I2 (review TỔNG 19/08) — MỌI chốt nằm TRƯỚC khi phiếu rời "Đã
		duyệt". Xem `_kiem_don_dung_duoc_xin_sua()` và `_loc_thay_doi_that()`
		ngay dưới: một phiếu đã sang "Chờ duyệt sửa" rồi mới chết ở bước
		quản lý bấm Đồng ý là NGÕ CỤT — `CHUYEN_HOP_LE["Chờ duyệt sửa"]` chỉ
		có đúng một cạnh ra (`Đã duyệt`), không có cạnh sang "Đã huỷ", nên
		đường ra duy nhất là `tu_choi_sua()`: bắt buộc lý do, ghi lý do đó
		vào `ghi_chu_quan_ly` mọi dòng như thể quản lý đã cân nhắc, và yêu
		cầu của khoa mất trắng.
		"""
		self._kiem_chuyen(TRANG_THAI_CHO_DUYET_SUA)
		self._kiem_don_dung_duoc_xin_sua()
		theo_ma = {d.item_code: d for d in self.items}
		thay_doi = self._loc_thay_doi_that(dong, theo_ma)
		for ma, qty in thay_doi.items():
			theo_ma[ma].so_luong_xin_sua = qty
		self.trang_thai = TRANG_THAI_CHO_DUYET_SUA
		self.save(ignore_permissions=True)

	def _kiem_don_dung_duoc_xin_sua(self):
		"""C1 (review tổng 19/08) — đơn đứng sau có SỬA ĐƯỢC không.

		Lõi `portal.portal_order_sua_so_luong` (nơi `de_xuat_duyet_sua` bắt
		buộc phải đi qua để sửa Sales Order thật) có HAI chốt cứng:
		`workflow_state == "Chờ khách đồng ý"` và `custom_loai_don == "Mua
		lẻ"`. Trước bản vá, `xin_sua()` không hỏi chốt nào — nên:

		  * đơn HĐNT (`dat_hang.py` ghi `custom_loai_don = "Theo HĐNT"` cho
		    MỌI đơn HĐNT) và
		  * đơn Mua lẻ CHƯA tới "Chờ khách đồng ý" — tức MỌI đơn ngay sau
		    khi duyệt, vì đơn sinh ra ở "Chờ xác nhận"

		đều cho phiếu rời "Đã duyệt" vào ngõ cụt, rồi quản lý bấm Đồng ý mới
		nhận một lỗi 500 khó hiểu ("Chỉ áp dụng cho đơn Mua lẻ.") — đúng thứ
		spec §5.5 cấm.

		Chốt ở TẦNG DOCTYPE, không ở endpoint: `de_xuat.de_xuat_xin_sua` chỉ
		là một trong các đường vào, và bất biến "phiếu không được rời Đã
		duyệt khi đơn không sửa được" thuộc về chính chứng từ này.

		KHÔNG mở rộng thành xây tính năng sửa-đơn-HĐNT: phạm vi ở đây là TỪ
		CHỐI SỚM kèm thông điệp nói đúng vì sao và khoa nên làm gì.
		"""
		from miyano_portal.portal_mua_le import TRANG_THAI_CHO_KHACH

		if not self.sales_order:
			frappe.throw(
				"Phiếu này chưa có đơn hàng nào đứng sau nên không có số "
				"lượng nào để xin sửa. Liên hệ quản lý của quý đơn vị.",
				frappe.ValidationError,
			)
		don = frappe.db.get_value(
			"Sales Order", self.sales_order,
			["custom_loai_don", "workflow_state"], as_dict=True,
		)
		if not don:
			frappe.throw(
				f'Không tìm thấy đơn hàng "{self.sales_order}" đứng sau '
				"phiếu này. Liên hệ Miyano để được hỗ trợ.",
				frappe.ValidationError,
			)
		if don.custom_loai_don != "Mua lẻ":
			frappe.throw(
				f'Đơn "{self.sales_order}" đặt theo hợp đồng nguyên tắc '
				"(HĐNT). Cổng không sửa được số lượng đơn HĐNT — số lượng "
				"đã chốt theo hợp đồng. Liên hệ quản lý của quý đơn vị "
				"hoặc Miyano nếu cần điều chỉnh.",
				frappe.ValidationError,
			)
		if don.workflow_state != TRANG_THAI_CHO_KHACH:
			frappe.throw(
				f'Đơn "{self.sales_order}" đang ở bước '
				f'"{don.workflow_state}". Chỉ xin sửa được số lượng khi đơn '
				f'ở bước "{TRANG_THAI_CHO_KHACH}" (Miyano đã báo giá xong). '
				"Liên hệ quản lý của quý đơn vị hoặc Miyano nếu cần đổi số "
				"lượng ở giai đoạn này.",
				frappe.ValidationError,
			)

	def _loc_thay_doi_that(self, dong: list[dict], theo_ma: dict) -> dict:
		"""I2 (review tổng 19/08) — trả `{item_code: qty}` của những dòng
		THẬT SỰ đổi số, sau khi đã chặn số âm.

		Hai lỗ được bịt ở đây, cả hai đều dẫn tới CÙNG một ngõ cụt "Chờ
		duyệt sửa" không lối ra:

		  1. `qty < 0`. `qty = -1` ghi ĐÚNG sentinel `SO_LUONG_XIN_SUA_TRONG`
		     → yêu cầu biến mất không dấu vết trong khi phiếu vẫn báo đang
		     chờ duyệt sửa. `qty = -5` lọt mọi bộ lọc `>= 0` của các tầng
		     trên → lõi ném "Không có thay đổi số lượng nào để gửi".
		  2. KHÔNG có thay đổi thật nào — kể cả khi khoa xin ĐÚNG số đang
		     có (10 → 10), một cửa vào hoàn toàn vô hại về ý định. Lõi cũng
		     ném "Không có thay đổi số lượng nào để gửi", và lúc đó phiếu đã
		     rời "Đã duyệt" rồi.

		So với `so_luong_duyet` (số đang nằm trên đơn — `_dong_bo_so_luong_
		duyet_ve_phieu` giữ hai chứng từ khớp nhau), KHÔNG so với
		`so_luong_de_xuat`. Dòng không đổi bị bỏ qua lặng lẽ: ghi nó xuống
		`so_luong_xin_sua` chỉ tạo một "yêu cầu" rỗng để tầng dưới lọc lại.
		"""
		thay_doi: dict[str, float] = {}
		for row in dong:
			ma = row.get("item_code")
			if ma not in theo_ma:
				continue
			qty = row.get("qty")
			if qty is None:
				continue
			try:
				qty = float(qty)
			except (TypeError, ValueError):
				frappe.throw(
					f'Số lượng xin sửa của "{ma}" không hợp lệ.',
					frappe.ValidationError,
				)
			if qty < 0:
				frappe.throw(
					f'Số lượng xin sửa của "{ma}" không hợp lệ: số lượng '
					"không được âm. Nhập 0 nếu muốn bỏ hẳn mặt hàng này.",
					frappe.ValidationError,
				)
			if qty != float(theo_ma[ma].so_luong_duyet or 0):
				thay_doi[ma] = qty
		if not thay_doi:
			frappe.throw(
				"Không có thay đổi số lượng nào để gửi — số quý vị nhập "
				"đúng bằng số đang có trên đơn. Nhập số MỚI cho mặt hàng "
				"cần đổi (0 nếu muốn bỏ hẳn mặt hàng đó).",
				frappe.ValidationError,
			)
		return thay_doi

	def duyet_sua(self):
		"""Quản lý ĐỒNG Ý với yêu cầu xin sửa — chép `so_luong_xin_sua`
		sang `so_luong_duyet`, dọn `so_luong_xin_sua`, quay lại "Đã duyệt".

		KHÔNG tự đụng Sales Order: endpoint gọi hàm này (`de_xuat.de_xuat_
		duyet_sua`) PHẢI gọi lõi `portal_order_sua_so_luong` TRƯỚC — hàm đó
		mới là nơi sửa đơn thật (và tự đồng bộ ngược `so_luong_duyet` lên
		đúng phiếu này, xem "Ruling preflight C4" ở `api/portal.py`).
		Hàm này chỉ dọn phần còn lại (`so_luong_xin_sua`) và đổi trạng
		thái.

		I3 (review Task 9) — TỰ KIỂM đang đứng ĐÚNG ở `TRANG_THAI_CHO_
		DUYET_SUA` TRƯỚC khi gọi `_kiem_chuyen`: cạnh `-> Đã duyệt` cũng hợp
		lệ từ `Chờ duyệt` (đường duyệt LẦN ĐẦU thật). Thiếu chốt này, gọi
		hàm trên một phiếu đang "Chờ duyệt" (chưa từng xin sửa, chưa có
		Sales Order) sẽ đẩy thẳng phiếu sang "Đã duyệt" MÀ KHÔNG CÓ ĐƠN NÀO
		đứng sau — và vì "Đã duyệt" chỉ còn đúng một cạnh ra
		(`TRANG_THAI_CHO_DUYET_SUA`), `duyet()` thật (nơi duy nhất tạo khối
		truy vết + sinh đơn) không còn cách nào chạy lại: phiếu chết vĩnh
		viễn ở trạng thái nói dối. (Trước bản vá, hàm chỉ "tình cờ" an toàn
		nhờ `doc.sales_order` rỗng làm `portal_order_sua_so_luong` ném lỗi
		trước — đó là tác dụng phụ của endpoint gọi nó, không phải chốt của
		chính hàm này; gọi trực tiếp trên `Document` như test dưới đây thì
		không có tác dụng phụ đó để mà dựa vào.)

		I2 (review Task 9) — so `so_luong_xin_sua >= 0`, KHÔNG so truthy:
		`0` là một yêu cầu THẬT ("xin bỏ dòng này"), không phải "chưa có gì
		để duyệt". Dọn về sentinel `SO_LUONG_XIN_SUA_TRONG`, KHÔNG về `0`."""
		if self.trang_thai != TRANG_THAI_CHO_DUYET_SUA:
			frappe.throw(
				f'Phiếu đang ở trạng thái "{self.trang_thai}", không có yêu '
				"cầu xin sửa nào đang chờ để duyệt.",
				frappe.ValidationError,
			)
		self._kiem_chuyen(TRANG_THAI_DA_DUYET)
		for d in self.items:
			if d.so_luong_xin_sua >= 0:
				d.so_luong_duyet = d.so_luong_xin_sua
				d.so_luong_xin_sua = SO_LUONG_XIN_SUA_TRONG
		self.trang_thai = TRANG_THAI_DA_DUYET
		self.save(ignore_permissions=True)

	def tu_choi_sua(self, ly_do):
		"""Quản lý TỪ CHỐI yêu cầu xin sửa — đơn giữ NGUYÊN số đã duyệt
		trước đó (không đụng Sales Order), chỉ dọn `so_luong_xin_sua` và
		ghi lý do vào `ghi_chu_quan_ly` của từng dòng có yêu cầu.

		I3 (review Task 9) — cùng chốt TỰ KIỂM trạng thái với `duyet_sua()`
		ở trên: xem docstring hàm đó để biết vì sao `_kiem_chuyen` một mình
		không đủ.

		I2 (review Task 9) — so `so_luong_xin_sua >= 0`, KHÔNG so truthy:
		`0` là một yêu cầu THẬT, không phải "chưa có gì để từ chối"."""
		if self.trang_thai != TRANG_THAI_CHO_DUYET_SUA:
			frappe.throw(
				f'Phiếu đang ở trạng thái "{self.trang_thai}", không có yêu '
				"cầu xin sửa nào đang chờ để từ chối.",
				frappe.ValidationError,
			)
		self._kiem_chuyen(TRANG_THAI_DA_DUYET)
		if not (ly_do or "").strip():
			frappe.throw(
				"Lý do từ chối là bắt buộc khi từ chối yêu cầu xin sửa.",
				frappe.ValidationError,
			)
		for d in self.items:
			if d.so_luong_xin_sua >= 0:
				d.ghi_chu_quan_ly = ly_do
				d.so_luong_xin_sua = SO_LUONG_XIN_SUA_TRONG
		self.trang_thai = TRANG_THAI_DA_DUYET
		self.save(ignore_permissions=True)

	def on_trash(self):
		if self.trang_thai != TRANG_THAI_NHAP:
			frappe.throw(
				"Phiếu đã gửi duyệt thì không xoá được. Dùng Huỷ phiếu để giữ "
				"lại dấu vết.",
				frappe.ValidationError,
			)

	def _chan_sua_so_luong_de_xuat(self):
		"""§5.3 — cột đề xuất khoá vĩnh viễn từ lúc Gửi duyệt.

		Review vòng 1 (19/08): bản đầu chỉ so khớp `d.name in truoc`, để lọt
		BA đường — sửa cả ba ở đây:
		  1. Thêm dòng mới sau khi gửi duyệt: dòng mới không có trong
		     `truoc` nên phải tự chặn riêng, không dựa vào vòng so khớp.
		  2. Xoá một dòng đã khoá: vòng lặp chỉ chạy trên `self.items` HIỆN
		     TẠI nên không bao giờ thấy dòng đã biến mất — phải soát chiều
		     ngược lại, từ `truoc` xem còn đủ trong `self.items` không.
		  3. Đổi `item_code` giữ nguyên số lượng: guard cũ chỉ so
		     `so_luong_de_xuat`, không so `item_code`.

		GIỚI HẠN ĐÃ BIẾT (QĐ-A2): `frappe.db.set_value`/`doc.db_set()` đi
		vòng được guard này — cùng loại giới hạn với `_chan_hai_quan_ly`
		trong `portal_member.py`. Chấp nhận: Miyano không có DocPerm nào
		trên doctype này nên không có màn desk để bấm, và không đường code
		nào trong app gọi db_set lên field này.
		"""
		if self.is_new() or self.trang_thai == TRANG_THAI_NHAP:
			return
		truoc = {d.name: d for d in self.get_doc_before_save().items}
		hien_co = {d.name for d in self.items}

		# Đường lọt #2 — xoá dòng đã khoá: soát từ phía `truoc`, không phải
		# từ `self.items`, vì dòng bị xoá không còn mặt ở đó để mà soát.
		for ten, d_truoc in truoc.items():
			if ten not in hien_co:
				frappe.throw(
					f'Không xoá được dòng "{d_truoc.item_code}" đã khoá số '
					"lượng đề xuất. Bỏ mặt hàng thì hạ Số lượng duyệt về 0, "
					"không xoá dòng.",
					frappe.ValidationError,
				)

		for d in self.items:
			if d.name not in truoc:
				# Đường lọt #1 — dòng mới do quản lý thêm: dòng khoa xin chỉ
				# sinh được lúc Gửi duyệt, nên dòng mới sau đó bắt buộc Số
				# lượng đề xuất bằng 0 — không được mạo danh dòng khoa xin.
				if float(d.so_luong_de_xuat or 0) != 0:
					frappe.throw(
						f'Dòng "{d.item_code}" là dòng mới thêm sau khi gửi '
						"duyệt nên Số lượng đề xuất phải bằng 0 — chỉ dòng "
						"khoa xin lúc Gửi duyệt mới mang số lượng đề xuất.",
						frappe.ValidationError,
					)
				continue

			d_truoc = truoc[d.name]
			# Đường lọt #3 — đổi item_code giữ nguyên số lượng.
			if d.item_code != d_truoc.item_code:
				frappe.throw(
					f'Không đổi được Mã hàng của dòng đã khoá (từ '
					f'"{d_truoc.item_code}" sang "{d.item_code}").',
					frappe.ValidationError,
				)
			if float(d.so_luong_de_xuat or 0) != float(d_truoc.so_luong_de_xuat or 0):
				frappe.throw(
					f'Số lượng đề xuất của "{d.item_code}" đã khoá từ lúc gửi '
					"duyệt. Quản lý điều chỉnh ở cột Số lượng duyệt.",
					frappe.ValidationError,
				)

	def _chan_khoa_phong_khac_benh_vien(self):
		"""Khoa phòng phải thuộc chính bệnh viện đứng tên phiếu.

		`khoa_phong` rỗng là HỢP LỆ — đó là phiếu cấp bệnh viện của quản lý
		("Toàn viện", §5.5), mang mã khoa dành riêng CHUNG.
		"""
		if not self.khoa_phong:
			return
		cua = frappe.db.get_value("Customer Department", self.khoa_phong, "customer")
		if cua != self.customer:
			frappe.throw(
				f'Khoa phòng "{self.khoa_phong}" không thuộc đơn vị '
				f'"{self.customer}".',
				frappe.ValidationError,
			)
