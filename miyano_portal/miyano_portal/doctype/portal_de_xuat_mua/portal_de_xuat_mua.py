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

from miyano_portal import gia_hdnt
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

# Task 2 (gộp luồng đặt hàng, 19/08/2026, Ruling P7) — thay cho `loai_don`
# cấp PHIẾU đã xoá. Mỗi DÒNG tự mang nguồn giá của nó; một phiếu được phép
# trộn cả hai. KHÔNG có giá trị "Hỗn hợp" nào — xem `co_dong_cho_bao_gia()`.
NGUON_GIA_HOP_DONG = "Hợp đồng"
NGUON_GIA_CHO_BAO_GIA = "Chờ báo giá"


def nguon_gia_theo_ma_cho_khach(customer: str) -> dict:
	"""`{item_code: blanket_order}` — hợp đồng khung THẮNG CUỘC cho mỗi mã
	hàng, trong số các Blanket Order CÒN HIỆU LỰC của `customer`.

	Tách ra module-level (Task 3, gộp luồng đặt hàng, 21/08/2026) khỏi
	`PortalDeXuatMua._nguon_gia_theo_ma()` — CÙNG một luật quyết định giá
	giờ có HAI nơi gọi: `PortalDeXuatMua.validate()` (qua `_suy_nguon_gia`)
	và `api/portal.portal_catalog_gop` (Task 3, endpoint tìm kiếm cho màn
	Lập phiếu). Hai đường tính "hợp đồng nào thắng" khác nhau sớm muộn
	cũng lệch — y hệt lý do `_gia_hien_hanh`/`kiem_boi_so` đã được tách
	thành hàm dùng chung thay vì để mỗi nơi tự viết một bản. Không nhận
	`Document` làm tham số (chỉ nhận `customer: str`) để gọi được từ một
	ngữ cảnh KHÔNG có `Portal De Xuat Mua` nào đang mở, đúng nhu cầu của
	`portal_catalog_gop` (một endpoint TÌM KIẾM, không gắn với phiếu nào).

	Xem đầy đủ lý do PHÂN ĐỊNH ("hết hạn sớm nhất thắng, trùng `to_date`
	thì `name` nhỏ hơn thắng", ngày hiệu lực) ở `PortalDeXuatMua._nguon_
	gia_theo_ma()` — docstring gốc giữ nguyên ở đó, không chép lại đây để
	tránh hai lời giải thích lệch nhau theo thời gian.

	Ruling P18 (review vòng 1) — "còn hiệu lực" đòi `docstatus == 1` (ĐÃ
	NỘP/ký), KHÔNG phải `docstatus < 2` (bản đầu — chỉ loại "Đã huỷ", vẫn
	cho Nháp lọt qua). Một hợp đồng NHÁP là sales còn đang soạn, CHƯA
	trình ký — để nó định giá một dòng trên phiếu đề xuất là để một bản
	nháp nội bộ, có thể đổi/xoá bất cứ lúc nào, làm bằng chứng giá cho
	khoa. Đây cũng là định nghĩa "còn hiệu lực" đã có sẵn ở nơi khác
	trong app (BR-R7, `items_thuoc_hdnt_hieu_luc()` tại `portal_mua_le.
	py`) — MỘT luật, không phải mỗi nơi tự định nghĩa một kiểu rồi sớm
	muộn lệch nhau."""
	bo_hieu_luc = frappe.get_all(
		"Blanket Order",
		filters={
			"customer": customer, "blanket_order_type": "Selling",
			"docstatus": 1,
			"from_date": ["<=", frappe.utils.today()],
			"to_date": [">=", frappe.utils.today()],
		},
		# Ruling P30 (review vòng 1) — chuỗi thứ tự này là LUẬT PHÂN ĐỊNH,
		# và giờ có nơi thứ hai phải tuân theo đúng nó (`gia_hdnt.
		# dong_bo_khach` ghi `Item Price`). Một hằng số, không phải hai
		# chuỗi giống nhau ở hai file — hai chuỗi thì sớm muộn cũng lệch,
		# và lần lệch trước đã suýt làm bệnh viện bị xuất hoá đơn sai giá.
		fields=["name"], order_by=gia_hdnt.THU_TU_PHAN_DINH,
	)
	if not bo_hieu_luc:
		return {}
	thang_cuoc: dict[str, str] = {}
	for bo in bo_hieu_luc:
		for item_code in frappe.get_all(
			"Blanket Order Item", filters={"parent": bo.name}, pluck="item_code"
		):
			thang_cuoc.setdefault(item_code, bo.name)
	return thang_cuoc


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
		self._suy_nguon_gia()
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

		Dùng ĐÚNG nguồn giá `dat_hang` dùng (`gia_hdnt.gia_dong_hop_dong`,
		QĐ-G12) — hai đường tra giá khác nhau sớm muộn cũng lệch, cùng lý do
		module đó không tự viết một hàm tra giá thứ hai cho nhánh HĐNT/mua lẻ
		của chính nó.

		Task 12 — BỎ gate `if not price_list: return` ở đầu hàm. Bước 1 của
		QĐ-G12 đọc `Blanket Order Item.rate`, không cần bảng giá nào; giữ
		gate đó thì khách chưa được gán `default_price_list` không bao giờ
		được đóng dấu giá dù hợp đồng khai đủ. `price_list` (có thể `None`)
		đi thẳng xuống `gia_dong_hop_dong()`, nơi phép kiểm nằm.

		`row.blanket_order` là hợp đồng dòng đó đã suy ra — ĐÚNG hợp đồng
		QĐ-G12 nói tới, và nó vừa được `_suy_nguon_gia()` ngay trên ghi lại.
		Dòng cũ do patch backfill mang `nguon_gia = "Hợp đồng"` mà
		`blanket_order` NULL (xem `de_xuat_duyet._kiem_han_muc`) rơi thẳng
		xuống bảng giá — đúng bằng hành vi trước Task 12, không xấu đi.

		Task 2 (gộp luồng đặt hàng) — HÀNH VI ĐỔI so với trước: trước đây
		hàm này áp cho CẢ PHIẾU (chỉ chạy khi `loai_don == "HĐNT"`, vì một
		phiếu khi đó CHỈ CÓ MỘT loại). Sau khi `loai_don` bị xoá, một phiếu
		được phép TRỘN — nên giờ đóng dấu THEO TỪNG DÒNG: chỉ dòng `nguon_
		gia == "Hợp đồng"` được đóng dấu, dòng `"Chờ báo giá"` (kể cả trong
		một phiếu trộn) bị BỎ QUA — mua lẻ/chờ báo giá không tra giá ở đâu
		cả trong toàn bộ luồng (§4.5, `rate = 0`, sales điền khi báo giá),
		nên không có "giá khoa đã thấy" nào để đóng dấu cho dòng đó. Mặt
		hàng không tra được giá (chưa có trong bảng giá hợp đồng) thì để
		`don_gia` RỖNG, KHÔNG throw — gửi duyệt chưa phải lúc chặn vì thiếu
		giá, đó là việc của lúc duyệt/tạo đơn (`dat_hang._xay_don_hdnt`).

		Tự gọi `_suy_nguon_gia()` TRƯỚC khi đọc `nguon_gia` — hàm này chạy
		TRONG `gui_duyet()`, TRƯỚC `self.save()` (nên trước `validate()`
		của chính lần lưu này), nên KHÔNG được tin `self.items[].nguon_gia`
		trong bộ nhớ đã chắc chắn mới; validate() của lần save() TRƯỚC ĐÓ
		mới ghi giá trị đó lần gần nhất.

		Ruling P14 — KHÔNG còn gate `if not self.hdnt: return` (field đó
		chỉ còn legacy, không quyết định phiếu có dòng Hợp đồng hay không
		nữa — xem `_nguon_gia_theo_ma()`). Vòng lặp bên dưới tự lọc theo
		`row.nguon_gia` sau khi `_suy_nguon_gia()` tính lại (customer-wide),
		nên không cần gate ngoài dựa trên `self.hdnt` nữa.

		I3 (review vòng 1) — trên đường resubmit-sau-từ-chối (`gui_duyet()`
		gọi được từ trạng thái "Từ chối", không chỉ "Nháp"), tự gọi `_suy_
		nguon_gia()` ở đây gần như KHÔNG LÀM GÌ cho các dòng ĐÃ CÓ từ lần
		gửi duyệt đầu tiên (đã đóng băng — xem guard `dong_bang` ở đó); nó
		vẫn còn tác dụng THẬT cho dòng MỚI thêm trong lúc "Từ chối" (chưa
		đóng băng), nên lời gọi này không phải no-op tuyệt đối, chỉ không
		còn tính lại phần đã khoá.
		"""
		price_list = frappe.db.get_value("Customer", self.customer, "default_price_list")
		self._suy_nguon_gia()
		from miyano_portal import gia_hdnt
		for row in self.items:
			if row.nguon_gia != NGUON_GIA_HOP_DONG:
				continue
			rate = gia_hdnt.gia_dong_hop_dong(
				row.item_code, row.blanket_order, price_list
			)
			# GHI VÔ ĐIỀU KIỆN (advisor, vòng sửa 1). Bản trước là `if rate:`,
			# nên con dấu CHỈ ĐI LÊN, không bao giờ hạ: phiếu bị TỪ CHỐI rồi
			# GỬI LẠI đi qua đây lần thứ hai, và nếu lúc đó không tra được
			# giá nữa (hợp đồng đã hết hiệu lực — Ruling P31 khiến bước 1 im,
			# hoặc bảng giá bị gỡ) thì `don_gia` vẫn khoe con số của LẦN GỬI
			# TRƯỚC. Đó là một con số không hợp đồng nào và không bảng giá
			# nào còn đỡ, in ra cho bệnh viện như bằng chứng "giá khoa đã
			# thấy". Cùng họ lỗi với `portal_reorder` tin `custom_hdnt` của
			# đơn cũ: giá trị ĐÓNG BĂNG được tin hơn phép tính LẠI.
			#
			# `0` là cách biểu diễn "chưa có giá" đã dùng sẵn ở đây (dòng
			# chưa bao giờ tra được giá cũng mang 0), và `_kiem_gia_doi()`
			# đã tự bỏ qua dòng `not row.don_gia`. Mất cảnh báo `gia_doi`
			# cho ca này KHÔNG phải mất tín hiệu: hợp đồng hết hiệu lực thì
			# `_kiem_gia_doi` vẫn báo `hop_dong_doi`, còn giá biến mất hẳn
			# thì `_xay_don` chặn thẳng lúc duyệt bằng "chưa có giá trong
			# hợp đồng". Không có đường nào đi qua im lặng.
			row.don_gia = rate or 0

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

		C1 + I2 (review TỔNG 19/08, hoàn tất ở vòng re-review) — phiếu chỉ
		rời "Đã duyệt" sau khi ĐỦ NĂM chốt của lõi `portal_order_sua_so_
		luong` đã được hỏi lại ở đây, cộng chốt riêng của I2. Kể tên thay vì
		nói "mọi chốt", để người sau đối chiếu được với lõi:

		  1. đơn phải ĐI VÒNG BÁO GIÁ        → `_kiem_don_dung_duoc_xin_sua`
		     (`portal_mua_le.di_vong_bao_gia`)
		  2. `workflow_state` = Chờ khách đồng ý → nt
		  3. báo giá còn hiệu lực (BR-R5)    → nt
		  4. mã hàng phải CÒN trên đơn       → `_kiem_thay_doi_ap_duoc_len_don`
		  5. đơn còn ít nhất một dòng sau sửa→ nt
		  (+) phải có thay đổi THẬT, không âm → `_loc_thay_doi_that` (I2);
		      so với SỐ TRÊN ĐƠN, giống lõi (Ruling P51)

		Task 7 — chốt 1 trước đây kể là `loại đơn phải "Mua lẻ"`. Đó là mô
		tả một phép so chuỗi mà mã KHÔNG còn thực hiện từ Task 6: đơn TRỘN
		(dòng hợp đồng + dòng chờ báo giá) cũng đi vòng báo giá theo QĐ-G3
		nên cũng sửa được, và chính chỗ hiểu "Mua lẻ" theo nghĩa cũ là gốc
		của C1.

		Vì sao thứ tự này quan trọng: một phiếu đã sang "Chờ duyệt sửa" rồi
		mới chết ở bước quản lý bấm Đồng ý là NGÕ CỤT — `CHUYEN_HOP_LE["Chờ
		duyệt sửa"]` chỉ có đúng một cạnh ra (`Đã duyệt`), không có cạnh
		sang "Đã huỷ", nên đường ra duy nhất là `tu_choi_sua()`: bắt buộc lý
		do, ghi lý do đó vào `ghi_chu_quan_ly` mọi dòng như thể quản lý đã
		cân nhắc, và yêu cầu của khoa mất trắng.

		Ba chốt đầu hỏi được ngay ở MỨC ĐƠN; hai chốt sau chỉ trả lời được
		sau khi đã biết khoa xin gì, nên chạy sau `_loc_thay_doi_that()`.
		"""
		self._kiem_chuyen(TRANG_THAI_CHO_DUYET_SUA)
		don = self._kiem_don_dung_duoc_xin_sua()
		theo_ma = {d.item_code: d for d in self.items}
		thay_doi = self._loc_thay_doi_that(dong, theo_ma, don)
		self._kiem_thay_doi_ap_duoc_len_don(don, thay_doi)
		for ma, qty in thay_doi.items():
			theo_ma[ma].so_luong_xin_sua = qty
		self.trang_thai = TRANG_THAI_CHO_DUYET_SUA
		self.save(ignore_permissions=True)

	def _kiem_don_dung_duoc_xin_sua(self):
		"""C1 (review tổng 19/08) — đơn đứng sau có SỬA ĐƯỢC không.

		Lõi `portal.portal_order_sua_so_luong` (nơi `de_xuat_duyet_sua` bắt
		buộc phải đi qua để sửa Sales Order thật) có HAI chốt cứng ở MỨC
		ĐƠN mà trả lời được ngay: `workflow_state == "Chờ khách đồng ý"` và
		`portal_mua_le.di_vong_bao_gia(so)` (Task 6; trước đó là chuỗi
		`custom_loai_don == "Mua lẻ"` viết tại chỗ), cộng chốt hiệu lực
		BR-R5. Trước bản vá, `xin_sua()` không hỏi chốt nào — nên:

		  * đơn KHÔNG đi vòng báo giá (thuần hợp đồng — `dat_hang.py` đóng
		    dấu `custom_loai_don = "Theo HĐNT"` khi mọi dòng đã có giá) và
		  * đơn ĐANG đi vòng báo giá nhưng CHƯA tới "Chờ khách đồng ý" —
		    tức MỌI đơn ngay sau khi duyệt, vì đơn sinh ra ở "Chờ xác nhận"

		đều cho phiếu rời "Đã duyệt" vào ngõ cụt, rồi quản lý bấm Đồng ý mới
		nhận một lỗi 500 khó hiểu từ lõi — đúng thứ spec §5.5 cấm.

		Chốt ở TẦNG DOCTYPE, không ở endpoint: `de_xuat.de_xuat_xin_sua` chỉ
		là một trong các đường vào, và bất biến "phiếu không được rời Đã
		duyệt khi đơn không sửa được" thuộc về chính chứng từ này.

		KHÔNG mở rộng thành xây tính năng sửa-đơn-đã-chốt-giá: phạm vi ở
		đây là TỪ CHỐI SỚM kèm thông điệp nói đúng vì sao và khoa nên làm gì.

		VÒNG SỬA (re-review 19/08) — soi gương ĐỦ CẢ NĂM chốt của lõi, chia
		hai bước. Hàm NÀY lo ba chốt ở MỨC ĐƠN (hỏi được ngay, chưa cần biết
		khoa xin gì); `_kiem_thay_doi_ap_duoc_len_don()` lo hai chốt ở MỨC
		DÒNG (chỉ trả lời được sau khi biết yêu cầu cụ thể). Trả về `so` để
		bước sau dùng lại, không tải đơn hai lần.

		Task 7 — LỆCH THỨ TỰ, CÓ CHỦ Ý, ĐÃ ĐO: lõi hỏi `workflow_state`
		TRƯỚC rồi mới `di_vong_bao_gia`; hàm này hỏi ngược lại. Bản trước
		của docstring khai là "đúng thứ tự lõi hỏi" — sai. Khác biệt chỉ
		nhìn thấy được khi CẢ HAI chốt cùng hỏng, và khi đó ở đây khoa được
		nghe lý do BỀN (đơn này chưa bao giờ sửa được) thay vì lý do TẠM
		(chưa tới bước) — lời khuyên đúng hơn. Đảo lại thứ tự an toàn về
		hành vi nhưng không đổi lại được gì, nên GIỮ và ghi ra đây.

		KHÔNG chép điều kiện: chốt hiệu lực gọi THẲNG `portal_mua_le.qua_han_
		hieu_luc()` — cùng hàm lõi gọi, cùng hàm banner `portal_order_track`
		và job `quet_bao_gia_het_han` gọi. Ba nơi tính ra một con số khác
		nhau là đúng thứ `han_hieu_luc_bao_gia` tự dặn phải tránh.
		"""
		from miyano_portal.portal_mua_le import (
			TRANG_THAI_CHO_KHACH,
			di_vong_bao_gia,
			han_hieu_luc_bao_gia,
			qua_han_hieu_luc,
		)

		if not self.sales_order:
			frappe.throw(
				"Phiếu này chưa có đơn hàng nào đứng sau nên không có số "
				"lượng nào để xin sửa. Liên hệ quản lý của quý đơn vị.",
				frappe.ValidationError,
			)
		if not frappe.db.exists("Sales Order", self.sales_order):
			frappe.throw(
				f'Không tìm thấy đơn hàng "{self.sales_order}" đứng sau '
				"phiếu này. Liên hệ Miyano để được hỗ trợ.",
				frappe.ValidationError,
			)
		# Tải CẢ đơn (không `db.get_value` vài cột): chốt hiệu lực nhận
		# nguyên `so`, và hai chốt mức dòng ở bước sau cần `so.items`.
		don = frappe.get_doc("Sales Order", self.sales_order)
		# Task 6 (QĐ-G2b) — CÙNG HÀM với lõi `portal.portal_order_sua_so_
		# luong`. Bản soi gương tự so chuỗi `custom_loai_don` sẽ trôi lệch
		# khỏi lõi ngay lần đầu ai đó đổi nghĩa chốt — và lệch ở đây nghĩa
		# là phiếu rời "Đã duyệt" vào ngõ cụt (lỗi C1 ngày 19/08).
		# Task 7 — LỜI TỪ CHỐI phải nói CÙNG MỘT LUẬT với lõi. Bản trước
		# nói "đặt theo hợp đồng nguyên tắc (HĐNT)" trong khi lõi nói "Chỉ
		# áp dụng cho đơn có dòng chờ báo giá": một luật, hai lời giải
		# thích, tuỳ khoa đi vào bằng cửa nào. Dưới mô hình gộp lời cũ còn
		# SAI THẬT — đơn bị từ chối chỉ là đơn KHÔNG còn dòng nào chờ báo
		# giá; nó không nhất thiết gắn với hợp đồng khung nào (đơn tự Miyano
		# lập trong Desk cũng rơi vào đây). Và `docs/CHANGELOG-khac-phuc-
		# BA-v2.md` cấm chữ "hợp đồng nguyên tắc" trong chữ người dùng đọc.
		# Nêu LUẬT DƯƠNG (khi nào sửa được), không nêu một khẳng định về
		# đơn mà hệ thống không kiểm.
		if not di_vong_bao_gia(don):
			frappe.throw(
				f'Đơn "{self.sales_order}" không có dòng nào chờ báo giá — '
				"cổng chỉ sửa được số lượng khi đơn đang trong vòng báo giá "
				"của Miyano. Số lượng của đơn này đã chốt. Liên hệ quản lý "
				"của quý đơn vị hoặc Miyano nếu cần điều chỉnh.",
				frappe.ValidationError,
			)
		if don.get("workflow_state") != TRANG_THAI_CHO_KHACH:
			frappe.throw(
				f'Đơn "{self.sales_order}" đang ở bước '
				f'"{don.get("workflow_state")}". Chỉ xin sửa được số lượng '
				f'khi đơn ở bước "{TRANG_THAI_CHO_KHACH}" (Miyano đã báo giá '
				"xong). Liên hệ quản lý của quý đơn vị hoặc Miyano nếu cần "
				"đổi số lượng ở giai đoạn này.",
				frappe.ValidationError,
			)
		# CỬA 1 (re-review) — chốt SẮC NHẤT vì nó tự đóng theo THỜI GIAN:
		# báo giá mặc định hết hiệu lực sau 7 ngày (BR-R5), nên một phiếu
		# nằm chờ qua cuối tuần là đủ. Không có chốt này, khoa xin sửa lọt
		# qua cả hai chốt trên rồi chết ở tay quản lý.
		if qua_han_hieu_luc(don):
			han = han_hieu_luc_bao_gia(don)
			frappe.throw(
				f'Báo giá cho đơn "{self.sales_order}" đã hết hiệu lực ngày '
				f"{frappe.utils.formatdate(han, 'dd/mm/yyyy')} nên không sửa "
				"được số lượng nữa. Gửi yêu cầu báo giá mới nếu vẫn cần "
				"hàng, hoặc liên hệ Miyano.",
				frappe.ValidationError,
			)
		return don

	def _kiem_thay_doi_ap_duoc_len_don(self, don, thay_doi: dict):
		"""Hai chốt MỨC DÒNG còn lại của lõi (re-review 19/08) — chỉ trả lời
		được sau khi đã biết khoa xin ĐÚNG những gì.

		CỬA 2 — `"Không tìm thấy mặt hàng {ma} trong đơn"`. Đường tới đây
		hoàn toàn tự nhiên: quản lý hạ một dòng về 0 lúc duyệt thì dòng đó
		KHÔNG vào đơn nhưng VẪN CÒN trên phiếu (§5.3, cố ý — đó là cách giữ
		"khoa xin gì / duyệt gì"). Khoa nhìn phiếu, thấy dòng đó, xin lại 5.
		`_loc_thay_doi_that` thấy `5 != 0` nên cho qua, và lõi mới là nơi
		phát hiện dòng ấy chưa từng có trên đơn.

		CỬA 3 — `"Đơn sẽ không còn dòng hàng nào sau khi sửa"` (ERPNext
		không lưu được `items` rỗng). Khoa xin 0 cho MỌI dòng.

		Soi gương phép tính của lõi, KHÔNG chép điều kiện: dùng chính
		`la_dong_giu_cho()` mà lõi dùng để loại dòng kỹ thuật, và cùng đọc
		`custom_dat_ngoai` — một đơn còn dòng đặt ngoài thì vẫn sống được
		(lõi tự chèn lại dòng giữ chỗ), nên chốt này không được bắt nhầm.
		"""
		from miyano_portal.portal_mua_le import la_dong_giu_cho

		ma_tren_don = {i.item_code for i in don.items}
		for ma in thay_doi:
			if ma not in ma_tren_don:
				frappe.throw(
					f'Mặt hàng "{ma}" không còn trên đơn "{don.name}" — quản '
					"lý đã bỏ mặt hàng này khi duyệt, nên không xin sửa số "
					"lượng của nó được. Nếu khoa vẫn cần, hãy lập một đề "
					"xuất mua mới cho mặt hàng đó.",
					frappe.ValidationError,
				)

		con_lai = [
			i for i in don.items
			if not la_dong_giu_cho(i.item_code)
			and thay_doi.get(i.item_code, float(i.qty or 0)) != 0
		]
		if not con_lai and not (don.get("custom_dat_ngoai") or []):
			frappe.throw(
				f'Yêu cầu này bỏ hết mọi mặt hàng của đơn "{don.name}" — đơn '
				"sẽ không còn dòng hàng nào. Nếu khoa muốn bỏ cả đơn, hãy "
				"liên hệ quản lý của quý đơn vị hoặc Miyano để huỷ đơn, "
				"thay vì hạ mọi dòng về 0.",
				frappe.ValidationError,
			)

	def _loc_thay_doi_that(self, dong: list[dict], theo_ma: dict, don) -> dict:
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

		Ruling P51 — SO VỚI `Sales Order Item.qty`, KHÔNG với `so_luong_
		duyet` của phiếu. Bản trước so với phiếu vì tin rằng hai con số luôn
		bằng nhau (`_dong_bo_so_luong_duyet_ve_phieu` giữ chúng khớp). **Sai
		— có một đường ghi lên đơn mà KHÔNG đi qua chỗ đồng bộ đó:**
		`portal_mua_le._gop_hoac_them_dong_hang` (hook `validate` của Sales
		Order, đường khớp mã dòng gõ tay — QĐ-G13) cộng thẳng vào
		`Sales Order Item.qty`; cả `portal_mua_le.py` không có một tham
		chiếu nào tới `so_luong_duyet`.

		Kịch bản dựng lại được (xem `test_de_xuat_sua_sau_duyet.py::_phieu_
		da_gop_dong_go_tay`): khoa xin mã A số lượng 10 kèm một dòng gõ tay;
		quản lý duyệt → phiếu ghi 10, đơn có 10; Miyano khớp dòng gõ tay về
		CHÍNH mã A → hook gộp → **đơn 15, phiếu vẫn 10**. Khoa mở đơn, THẤY
		15, gõ 15. Bản cũ thấy `15 != 10` nên CHO QUA, phiếu rời "Đã duyệt"
		— rồi lõi thấy `15 == 15` và ném "Không có thay đổi số lượng nào để
		gửi". `CHUYEN_HOP_LE["Chờ duyệt sửa"]` chỉ có ĐÚNG MỘT cạnh ra
		(`tu_choi_sua()`), nên đó là ngõ cụt C1 mà Task 7 sinh ra để dẹp.
		Triệu chứng soi gương của cùng lỗi: khoa gõ 10 thì bản cũ từ chối
		bằng câu "số quý vị nhập đúng bằng số đang có trên đơn" — SAI SỰ
		THẬT, đơn đang có 15.

		Việc của bản soi gương là ĐOÁN TRƯỚC lõi sẽ làm gì. Lõi so với đơn,
		nên ở đây cũng so với đơn — không phải vì con số nào "đúng hơn", mà
		vì hai bên phải hỏi CÙNG MỘT câu.
		*Sai thì mất gì:* nếu nghiệp vụ muốn khoá xin-sửa theo đúng thứ quản
		lý đã duyệt chứ không theo thứ đơn đang có, phải đảo lại — nhưng lúc
		đó chỗ phải sửa là HOOK GỘP, không phải chỗ này.

		Mã KHÔNG có trên đơn tính là `0` — giữ nguyên hành vi cũ (`so_luong_
		duyet` của dòng quản lý đã hạ về 0 cũng là 0): khoa xin lại 5 cho
		dòng đó vẫn lọt qua đây rồi bị CỬA 2 của `_kiem_thay_doi_ap_duoc_
		len_don` từ chối kèm lời giải thích đúng ngữ cảnh phiếu.

		Tư cách một dòng "xin sửa được" vẫn đọc từ PHIẾU (`theo_ma`), không
		từ đơn: phiếu là bản ghi khoa đã xin gì, và dòng đơn sinh ra ngoài
		phiếu (dòng gõ tay khớp sang một mã MỚI) không phải thứ khoa xin
		sửa qua đường này.
		"""
		# `don` BẮT BUỘC, không mặc định `None`: một mặc định sẽ khiến
		# người gọi quên truyền vẫn CHẠY, và chạy sai theo kiểu im lặng
		# (mọi số đều "khác 0" nên mọi thứ tính là thay đổi thật).
		qty_tren_don = {i.item_code: float(i.qty or 0) for i in don.items}
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
			if qty != qty_tren_don.get(ma, 0.0):
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

	def _suy_nguon_gia(self):
		"""Task 2 (gộp luồng đặt hàng), Ruling P14 (thay Ruling P7 — SỬA
		SAU review: bản đầu suy theo `self.hdnt` ở ĐẦU PHIẾU, hỏng KHÔNG
		CỨU ĐƯỢC ở tầng giao diện thật — xem `_nguon_gia_theo_ma()`) — ghi
		`nguon_gia` cho MỌI dòng, KHÔNG tin giá trị client gửi (QĐ-G1): mã
		hàng có dòng trong BẤT KỲ hợp đồng khung nào của `self.customer`
		còn hiệu lực → `Hợp đồng` (và `blanket_order` = hợp đồng THẮNG
		CUỘC); ngược lại (kể cả `item_code` rỗng) → `Chờ báo giá`
		(`blanket_order` để rỗng). Luôn GHI ĐÈ, kể cả khi `self.items` rỗng
		— không có nhánh nào bỏ qua để giá trị cũ/giá trị client gửi sống
		sót.

		I3 (review vòng 1) — TRỪ khi phiếu đã qua khỏi Nháp: ĐÓNG BĂNG
		`nguon_gia`/`blanket_order` ĐÚNG nơi `_chan_sua_so_luong_de_xuat`
		đã khoá `so_luong_de_xuat`/`don_gia` (từ lúc Gửi duyệt trở đi,
		"khoá vĩnh viễn" — §5.3). Không có chốt này, một lần lưu BẤT KỲ sau
		khi đã duyệt (VD: `duyet_sua()`, luồng xin sửa/duyệt sửa số lượng)
		sẽ tính lại theo trạng thái hợp đồng HIỆN TẠI — nếu hợp đồng đã hết
		hạn từ lúc đó, phiếu ĐÃ được duyệt dựa trên giá hợp đồng nào sẽ bị
		âm thầm ghi đè thành "Chờ báo giá", xoá mất bằng chứng đã dùng lúc
		duyệt. Cùng điều kiện `is_new() or trang_thai == Nháp` — một phiếu
		đã gửi duyệt thì khoá vĩnh viễn, không phải hai luật khoá lệch
		nhau vì viết hai điều kiện khác nhau ở hai nơi.

		SỬA (advisor, ngay sau review vòng 1) — đóng băng theo TỪNG DÒNG đã
		có lúc gửi duyệt, KHÔNG `return` sớm cho CẢ `self.items`:
		`_chan_sua_so_luong_de_xuat` (nơi I3 mô phỏng theo) vẫn CHO PHÉP
		thêm dòng MỚI sau khi gửi duyệt (Đường lọt #1 của gate đó — quản lý
		điều chỉnh qua `_ap_dieu_chinh`, dòng mới bắt buộc `so_luong_de_
		xuat = 0`). `return` sớm cho cả tập dòng sẽ khiến dòng MỚI đó không
		bao giờ được `_suy_nguon_gia()` chạm tới — nó giữ nguyên default
		Select "Hợp đồng" (lựa chọn ĐẦU trong `options`) dù mã hàng của nó
		không hề thuộc hợp đồng nào: đúng bẫy false-green đã ghi ở đầu task
		này, quay lại qua một cửa khác.
		"""
		dong_bang = not self.is_new() and self.trang_thai != TRANG_THAI_NHAP
		# SỬA (advisor, ngay sau bản sửa I3 đầu) — KHÔNG dùng `self.get_doc_
		# before_save()` làm nguồn `da_khoa`: property đó chỉ được Frappe
		# điền trong một chu trình `save()` ĐÃ XẢY RA trên CHÍNH object
		# Python này (`base_document.py`, gán trong `_get_doc_before_save`
		# gọi từ `run_before_save_hooks`), mà lời gọi DUY NHẤT của hàm này
		# ở `_dong_dau_gia()` chạy TRỰC TIẾP từ `gui_duyet()`, TRƯỚC `self.
		# save()`. Đường Nháp→Chờ duyệt vô hại (`dong_bang` False lúc đó).
		# Đường RESUBMIT-SAU-TỪ-CHỐI (`gui_duyet()` hợp lệ từ "Từ chối")
		# THÌ VỠ: endpoint thật nạp `Document` MỚI qua `frappe.get_doc()`
		# mỗi request rồi gọi `.gui_duyet()` ngay — không có `save()` nào
		# trước đó trên object đó để điền `_doc_before_save`, `get_doc_
		# before_save()` trả `None`, `.items` ném `AttributeError` → HTTP
		# 500 thật cho người dùng bấm "Gửi duyệt lại" sau khi bị từ chối.
		# Đọc THẲNG DB thay thế — đúng bất kể chu trình save() đã bắt đầu
		# hay chưa, vì nó không phụ thuộc trạng thái nội bộ của object.
		da_khoa = set(frappe.get_all(
			"Portal De Xuat Mua Item", filters={"parent": self.name}, pluck="name"
		)) if dong_bang else set()
		thang_cuoc = self._nguon_gia_theo_ma()
		for row in self.items:
			if dong_bang and row.name in da_khoa:
				# Dòng đã có lúc gửi duyệt — đóng băng, không tính lại.
				continue
			bo = thang_cuoc.get(row.item_code)
			if bo:
				row.nguon_gia = NGUON_GIA_HOP_DONG
				row.blanket_order = bo
			else:
				row.nguon_gia = NGUON_GIA_CHO_BAO_GIA
				row.blanket_order = None

	def _nguon_gia_theo_ma(self) -> dict:
		"""`{item_code: blanket_order}` — hợp đồng khung THẮNG CUỘC cho mỗi
		mã hàng, trong số các Blanket Order CÒN HIỆU LỰC của `self.customer`.

		Ruling P14 (review màn lập phiếu, 21/08/2026) — SỬA hẳn cách suy so
		với bản đầu (Ruling P7, đã xoá): bản đầu hỏi ĐÚNG một hợp đồng —
		`self.hdnt`, field ở ĐẦU PHIẾU — mô phỏng CHÍNH lỗi mà cả kế hoạch
		này sinh ra để sửa (`loai_don`, một field cấp ĐƠN ép "cả phiếu chỉ
		một loại"), chỉ lệch sang field khác. Vỡ thật ở tầng giao diện:
		`api/de_xuat.de_xuat_tao_nhap()` tạo phiếu Nháp TRƯỚC KHI người
		dùng chọn mặt hàng nào — `hdnt` lúc đó luôn `None` — và `de_xuat_
		luu_nhap()` (hàm DUY NHẤT ghi `items` sau đó) KHÔNG có tham số
		`hdnt` nào để sửa lại. Nghĩa là bản đầu khiến `hdnt` rỗng VĨNH VIỄN
		cho MỌI phiếu tạo qua đúng luồng UI thật, `_items_hop_dong_hieu_
		luc()` (cũ) luôn trả tập rỗng, MỌI dòng thành "Chờ báo giá" — tầng
		1 (Hợp đồng) không bao giờ chạy được, đúng tính năng chính của cả
		kế hoạch "gộp luồng đặt hàng".

		Sửa: hỏi CUSTOMER-WIDE (giống `portal_mua_le.items_thuoc_hdnt_hieu_
		luc()`, BR-R7) thay vì một hợp đồng cố định — `self.hdnt` KHÔNG còn
		được đọc ở đây nữa, chỉ còn là field LEGACY (giữ lại cho `_kiem_han_
		muc`/`dat_hang.tao_sales_order` tới Task 4/5, xem `de_xuat_duyet.py`).

		PHÂN ĐỊNH khi một mã hàng nằm trong NHIỀU hợp đồng còn hiệu lực —
		hợp đồng hết hạn SỚM NHẤT thắng (`order_by="to_date asc, name
		asc"`, `dict.setdefault` chỉ nhận giá trị ĐẦU khi duyệt theo đúng
		thứ tự ưu tiên đó). Chọn "hết hạn sớm nhất" vì đó là hành vi ĐÚNG
		nghiệp vụ (tiêu hợp đồng sắp hết hạn trước khi nó biến mất); nhưng
		điều BẮT BUỘC không phải là chọn tiêu chí nào, mà là kết quả phải
		TẤT ĐỊNH — lưu đi lưu lại một phiếu mà dòng của nó nhảy qua lại
		giữa hai hợp đồng là lỗi nặng hơn cả việc chọn nhầm hợp đồng nào.
		`name asc` phá vỡ hoà khi trùng `to_date`, để `order_by` không bao
		giờ mơ hồ.

		`docstatus == 1` (Ruling P18, review vòng 1 — SỬA, thay quyết định
		`docstatus < 2` bản đầu) — bản đầu chọn `< 2` (chỉ loại hợp đồng đã
		HUỶ, vẫn cho Nháp lọt qua) và biện minh bằng chính fixture của HAI
		bộ test đang tồn tại (`TestDeXuatDuyetHanMuc` và bộ test của chính
		task này), cả hai khi đó đều dựng Blanket Order chỉ `.insert()`
		không `.submit()`. Review chỉ đúng ra đó là một dạng fixture-
		patching trá hình quanh chính cái gate đang được kiểm: fixture tiện
		tay không phải là lý do nghiệp vụ. Định nghĩa "còn hiệu lực" đúng
		phải THỐNG NHẤT với nơi đã có sẵn trong app (BR-R7,
		`items_thuoc_hdnt_hieu_luc()` tại `portal_mua_le.py`, đòi
		`docstatus == 1`) — một hợp đồng NHÁP (sales còn soạn, chưa trình
		ký) không được định giá bất cứ dòng nào. Cả hai bộ test đã SỬA để
		`.submit()` Blanket Order của mình, không nới định nghĩa để né việc
		sửa fixture.

		Task 3 (21/08/2026) — phép tính THẬT SỰ chuyển sang hàm module-level
		`nguon_gia_theo_ma_cho_khach()` (đầu file), dùng CHUNG với
		`api/portal.portal_catalog_gop`. Docstring này giữ nguyên tại đây
		(không chuyển) vì nó gắn với lịch sử review/Ruling P14 của CHÍNH
		method này; hàm module-level chỉ trỏ ngược lại đây thay vì chép lại.
		"""
		return nguon_gia_theo_ma_cho_khach(self.customer)

	def co_dong_cho_bao_gia(self) -> bool:
		"""Task 2, Ruling P7 — THAY THẾ mọi chỗ trước đây hỏi `loai_don`
		(nay đã xoá khỏi doctype). `True` khi có ít nhất một dòng `Chờ báo
		giá` HOẶC có dòng đặt ngoài (`self.dat_ngoai` — chưa có mã, luôn
		không tra được giá hợp đồng).

		Đọc TRỰC TIẾP `self.items[].nguon_gia` đã suy sẵn ở `_suy_nguon_
		gia()` (validate()), KHÔNG tự tính lại — cùng cách `loai_don` cũ
		từng là một field ĐỌC THẲNG. `validate()` luôn chạy trước khi doc
		được lưu, nên giá trị trong bộ nhớ tại đây là giá trị đã qua
		`_suy_nguon_gia()` của lần lưu GẦN NHẤT (hoặc của chính request
		hiện tại nếu `_dong_dau_gia()` vừa gọi `_suy_nguon_gia()` trước khi
		gọi hàm này — xem docstring `_dong_dau_gia()`)."""
		if self.dat_ngoai:
			return True
		return any(row.nguon_gia == NGUON_GIA_CHO_BAO_GIA for row in self.items)
