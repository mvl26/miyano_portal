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

# Mỗi DÒNG tự mang nguồn giá của nó (Task 2 gộp luồng đặt hàng, Ruling P7 —
# thay cho `loai_don` cấp PHIẾU đã xoá). KHÔNG có giá trị "Hỗn hợp" nào —
# xem `co_dong_cho_bao_gia()`.
#
# Spec 2026-10-09 §3.2 — nguồn giá suy từ Price List của khách: có giá →
# "Bảng giá", chưa có → "Chờ báo giá". "Hợp đồng" chỉ còn trên dòng CŨ đã
# đóng băng trước thay đổi này; không dòng mới nào nhận nó nữa.
NGUON_GIA_HOP_DONG = "Hợp đồng"
NGUON_GIA_BANG_GIA = "Bảng giá"
NGUON_GIA_CHO_BAO_GIA = "Chờ báo giá"


def nguon_gia_theo_ma_cho_khach(customer: str) -> dict:
	"""`{item_code: blanket_order}` — hợp đồng khung THẮNG CUỘC cho mỗi mã
	hàng, trong số các Blanket Order CÒN HIỆU LỰC của `customer`.

	Spec 2026-10-09 — phiếu đề xuất KHÔNG còn gọi hàm này: `PortalDeXuatMua.
	_suy_nguon_gia()` suy nguồn giá từ Price List của khách (`bang_gia_khach`),
	và đường duyệt (`de_xuat_duyet`) cũng không còn hỏi hợp đồng. Hàm nằm lại
	ở module này vì nơi gọi DUY NHẤT còn lại import nó từ đây:
	`gia_hdnt.dong_bo_khach` (chép giá hợp đồng vào Price List của khách — khi
	nhiều hợp đồng cùng khai một mã, hàm này quyết hợp đồng nào được ghi).
	Không nhận
	`Document` làm tham số (chỉ `customer: str`) để gọi được từ ngữ cảnh
	không có phiếu nào đang mở.

	PHÂN ĐỊNH khi một mã hàng nằm trong NHIỀU hợp đồng còn hiệu lực (Ruling
	P14) — hợp đồng hết hạn SỚM NHẤT thắng, trùng `to_date` thì `name` nhỏ
	hơn thắng (`gia_hdnt.THU_TU_PHAN_DINH`; `dict.setdefault` chỉ nhận giá
	trị ĐẦU khi duyệt theo đúng thứ tự đó). "Hết hạn sớm nhất" là hành vi
	đúng nghiệp vụ (tiêu hợp đồng sắp hết hạn trước), nhưng điều BẮT BUỘC là
	kết quả phải TẤT ĐỊNH — hai lần hỏi cho cùng một mã không được ra hai
	hợp đồng khác nhau.

	Ruling P18 (review vòng 1) — "còn hiệu lực" đòi `docstatus == 1` (ĐÃ
	NỘP/ký), KHÔNG phải `docstatus < 2` (bản đầu — chỉ loại "Đã huỷ", vẫn
	cho Nháp lọt qua). Một hợp đồng NHÁP là sales còn đang soạn, CHƯA
	trình ký — có thể đổi/xoá bất cứ lúc nào, không được làm nguồn giá.
	Từ 12/10/2026 đây là nơi DUY NHẤT trong app định nghĩa "hợp đồng còn
	hiệu lực" (bản thứ hai, `portal_mua_le.items_thuoc_hdnt_hieu_luc()` của
	BR-R7, đã gỡ cùng cờ `dat_duoc_hdnt`)."""
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
		# `Nháp → Đã huỷ` (review toàn nhánh 03/09/2026) — mở lại đường GIỮ
		# DẤU VẾT cho phiếu đã thu hồi. Trước cạnh này, một phiếu thu hồi về
		# Nháp không còn cách nào kết thúc tử tế: `on_trash` (đúng §5.4b)
		# cấm xoá vì nó ĐÃ TỪNG gửi, mà `huy()` cũng cấm vì nó ĐANG ở Nháp
		# — đường xoá sạch thì mở, đường §5.4b bắt phải dùng thì bất khả
		# thi. Cạnh này cũng cho phép huỷ một phiếu CHƯA TỪNG gửi (không có
		# mã) — nới rộng có chủ ý, nhưng KHÔNG phải "vô hại vì vẫn xoá được
		# sau": một khi sang "Đã huỷ", `on_trash` từ chối vĩnh viễn (nó hỏi
		# TRẠNG THÁI trước, và "Đã huỷ" != "Nháp"), nên bản ghi đó không ai
		# dọn được nữa. Giao diện không dẫn tới ca này (`de-xuat-actions.js`
		# chỉ hiện "Huỷ phiếu" cho phiếu CÓ mã, và "Xoá" cho phiếu không có),
		# nhưng `de_xuat_huy` là endpoint whitelist nên một quản lý gọi thẳng
		# API vẫn tạo ra được. Chấp nhận: một phiếu "Đã huỷ" không xoá được
		# đúng bằng một phiếu "Đã huỷ" bình thường của §5.4b — dấu vết là thứ
		# §5.4b muốn giữ, không phải thứ cần dọn.
		TRANG_THAI_NHAP: {TRANG_THAI_CHO_DUYET, TRANG_THAI_DA_HUY},
		# `Chờ duyệt → Nháp` (03/09/2026) — nhân viên THU HỒI phiếu mình vừa
		# gửi để sửa lại. Cạnh này là cách DUY NHẤT chủ đầu tư nhận được
		# "NV sửa được đơn ở trạng thái Chờ duyệt" mà không phải nới
		# `_chan_sua_so_luong_de_xuat()`: guard đó nằm ở `validate()` vì BỐN
		# đường ghi dùng chung nó, và nới theo trạng thái sẽ mở luôn cho
		# `_ap_dieu_chinh` sửa cột đề xuất — đúng thứ §5.3 cấm. Xem
		# `thu_hoi()` và `test_de_xuat_thu_hoi.py`.
		TRANG_THAI_CHO_DUYET: {
			TRANG_THAI_DA_DUYET, TRANG_THAI_TU_CHOI, TRANG_THAI_DA_HUY,
			TRANG_THAI_NHAP,
		},
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

	def _kiem_dat_ngoai_du_nhan_dang(self):
		"""CR-03/BR-Y5 — mỗi dòng hàng chưa có trong hệ thống phải có ÍT NHẤT
		MỘT ẢNH, hoặc một mô tả nhận dạng đủ dài.

		VÌ SAO Ở `gui_duyet()`, KHÔNG Ở `validate()`: khách gõ nửa chừng rồi
		lưu lại làm tiếp buổi chiều là việc bình thường. Đặt chốt ở
		`validate()` là biến nút Lưu thành một cái bẫy — mỗi lần lưu nháp
		lại đòi đủ ảnh cho MỌI dòng, kể cả dòng vừa mở ra chưa gõ gì.
		`gui_duyet()` là đúng chỗ: nó là ranh giới "phiếu đã đủ điều kiện đi
		tiếp", cùng chỗ chốt `ly_do_yeu_cau` đang đứng.

		VÌ SAO Ở CHA, KHÔNG Ở BẢNG CON: Frappe KHÔNG gọi `validate()` của
		controller bảng con khi cha lưu — `SalesOrderDatNgoaiItem` có nguyên
		một docstring nói điều đó. Một chốt viết ở đó sẽ không bao giờ chạy,
		và người đọc sau tưởng chốt đã có.

		Ảnh là dữ kiện tìm nguồn giá trị nhất: một tấm ảnh nhãn hộp thay được
		cả bốn ô mô tả. Lối thoát `khong_co_anh` có thật (nhãn mờ, hộp đã bỏ,
		hàng chưa từng mua) nên không chặn cứng: tích cờ đó là đủ.

		Mô tả nhận dạng (`mo_ta_nhan_dang`) là TUỲ CHỌN — chủ đầu tư bỏ ngưỡng
		50 ký tự ngày 29/09/2026 (*"không yêu cầu 50 ký tự nữa, có thể nhập
		hoặc không nhập"*). Chốt còn lại chỉ là: không ảnh thì phải CỐ Ý tích
		"Tôi không chụp được ảnh", không để lọt một dòng quên ảnh.
		"""
		for i, r in enumerate(self.get("dat_ngoai") or [], start=1):
			ten = (r.ten_hang or f"dòng {i}").strip()

			# `anh` là chuỗi JSON. `"[]"` KHÁC RỖNG nên một phép kiểm
			# `if not r.anh` sẽ cho nó đi qua — đó là "đã có trường, chưa có
			# ảnh", ca dễ lọt nhất của chốt này.
			try:
				danh_sach = frappe.parse_json(r.anh) if r.anh else []
			except Exception:
				danh_sach = []
			co_anh = bool(danh_sach)

			if co_anh:
				continue

			if not r.khong_co_anh:
				frappe.throw(
					f'Mặt hàng "{ten}" chưa có ảnh. Miyano cần ảnh để tìm đúng '
					"hàng — chụp nhãn trên hộp là đủ. Nếu thật sự không chụp "
					'được, tích "Tôi không chụp được ảnh" (có thể mô tả thêm '
					"bằng lời nếu muốn).",
					frappe.ValidationError,
				)

	def kiem_truoc_gui_duyet(self):
		"""Mọi điều kiện một phiếu phải đạt TRƯỚC khi gửi duyệt, không ghi
		gì. Công khai vì có HAI nơi cần đúng bộ kiểm này: `gui_duyet()` ngay
		dưới, và `tach_phieu.gui_duyet_co_tach()` — nơi phải biết phiếu gửi
		được hay không TRƯỚC khi cắt dòng sang phiếu thứ hai. Hai bản chép
		tay của cùng ba phép kiểm là hai bản sẽ lệch nhau."""
		self._kiem_chuyen(TRANG_THAI_CHO_DUYET)
		if not (self.ly_do_yeu_cau or "").strip():
			frappe.throw(
				"Lý do yêu cầu là bắt buộc khi gửi duyệt.", frappe.ValidationError
			)
		self._kiem_dat_ngoai_du_nhan_dang()

	def gui_duyet(self):
		self.kiem_truoc_gui_duyet()
		if not self.ma_de_xuat:
			# Ruling R8 — LẦN GỬI ĐẦU: suy lại nguồn giá của MỌI dòng từ
			# Price List hiện hành, TRƯỚC khi cấp mã. Nguồn giá trên phiếu
			# Nháp là của lần LƯU gần nhất, và giá có thể đổi từ lúc đó;
			# một khi mã đã cấp thì `_suy_nguon_gia()` coi mọi dòng đã lưu
			# là đóng băng (kể cả lời gọi trong `_dong_dau_gia()` ngay
			# dưới), nên đây là cơ hội cuối để dòng mang đúng nguồn giá của
			# LÚC GỬI. Gửi lại (đã có mã) không đi qua đây — dòng đóng băng
			# giữ nguyên, trừ ngoại lệ R5 trong `_dong_dau_gia()`. Phiếu
			# không có mã mà đã rời Nháp (khách chưa có Mã ngắn) có đi qua,
			# nhưng `_suy_nguon_gia()` tự đóng băng theo trạng thái.
			self._suy_nguon_gia()
			# Sinh ĐÚNG MỘT LẦN. Phiếu bị từ chối rồi gửi lại giữ nguyên mã cũ:
			# quản lý và khoa đã gọi tên nó bằng mã đó trong lúc trao đổi.
			self.ma_de_xuat = sinh_ma(self.customer, self.khoa_phong)
		self.thoi_diem_gui = now_datetime()
		self._dong_dau_gia()
		self._dong_dau_so_luong_duyet()
		self.trang_thai = TRANG_THAI_CHO_DUYET
		self.save(ignore_permissions=True)
		# Task 2 (nhật ký thao tác) — CÙNG CHỖ, CÙNG LÝ DO với `bao_de_xuat_
		# gui_duyet` ngay dưới: `nhat_ky.ghi()` không bao giờ ném lỗi (xem
		# docstring nó), nên an toàn gọi ngay sau save() — một trục trặc ở
		# khâu ghi sổ không được cuốn theo trạng thái "Chờ duyệt" vừa ghi
		# thành công.
		from miyano_portal import nhat_ky
		nhat_ky.ghi(
			nhat_ky.SK_KHOA_GUI_DUYET,
			customer=self.customer, khoa_phong=self.khoa_phong,
			de_xuat=self.name, vai=nhat_ky.VAI_KHOA,
			ghi_chu=(self.ly_do_yeu_cau or "").strip() or None,
		)
		# Task 8 (§5.8) — CHỈ quản lý cần biết có phiếu chờ duyệt. Hàm này
		# không bao giờ ném lỗi (xem docstring nó) nên an toàn gọi ngay sau
		# save(): một trục trặc ở khâu thông báo không được cuốn theo trạng
		# thái "Chờ duyệt" vừa ghi thành công.
		#
		# `flags.khong_bao_gui_duyet` — chỉ `tach_phieu.gui_duyet_co_tach` đặt:
		# hai phiếu của MỘT lần gửi được báo bằng một thông báo chung ở đó.
		if not self.flags.get("khong_bao_gui_duyet"):
			from miyano_portal.portal_thong_bao_khach import bao_de_xuat_gui_duyet
			bao_de_xuat_gui_duyet(self)

	def thu_hoi(self):
		"""Nhân viên rút phiếu đang "Chờ duyệt" về "Nháp" để sửa lại
		(03/09/2026). Chốt AI được gọi nằm ở endpoint (`de_xuat.
		de_xuat_thu_hoi`, chỉ chủ phiếu) — doctype không biết ai đang gọi
		nó, cùng lập trường `gui_duyet()`/`huy()` đã giữ.

		Vì sao XOÁ `thoi_diem_gui`: màn chi tiết in thẳng field này ("Thời
		điểm gửi: … / Chưa gửi") ngay cạnh badge trạng thái, nên một phiếu
		Nháp còn mang giờ gửi cũ làm hai dòng trên CÙNG một khối truy vết
		nói ngược nhau. Giá trị cũ không mất: doctype bật `track_changes`,
		`Version` giữ lại lần gửi trước.

		KHÔNG đụng `ma_de_xuat` (mã sinh đúng một lần — quản lý và khoa đã
		gọi tên phiếu bằng nó). Từ review toàn nhánh 03/09/2026, việc giữ
		field này còn CHỊU TẢI: nó là dấu "đã từng gửi duyệt" duy nhất sống
		sót qua thu hồi, và HAI chốt hỏi thẳng nó thay vì hỏi trạng thái —
		`on_trash` (không cho xoá vĩnh viễn thứ quản lý đã thấy) và gate
		đóng băng của `_suy_nguon_gia()` (không cho nguồn giá của dòng cũ bị
		tính lại). Xoá mã ở đây là mở lại cả hai.

		KHÔNG đụng `so_luong_duyet`/`don_gia`: cả
		hai được `gui_duyet()` đóng dấu lại ở lần gửi sau, nên xoá tay ở
		đây chỉ là một nơi thứ hai phải nhớ cập nhật khi luật đóng dấu đổi.

		KHÔNG báo cho quản lý. §5.8 không có hàng nào cho việc này, và một
		phiếu rời hàng chờ là thứ badge/danh sách của quản lý tự phản ánh ở
		lần nạp kế tiếp. Quản lý đang mở đúng phiếu đó lúc nó bị thu hồi sẽ
		ăn `_kiem_chuyen()` khi bấm Duyệt — chặn đúng chỗ, không phải một
		trạng thái nửa vời.
		"""
		self._kiem_chuyen(TRANG_THAI_NHAP)
		self.thoi_diem_gui = None
		self.trang_thai = TRANG_THAI_NHAP
		self.save(ignore_permissions=True)
		# Task 2 (nhật ký thao tác) — cùng chỗ, cùng lý do đã nêu ở
		# `gui_duyet()`: ngay sau save() thành công, `nhat_ky.ghi()` không
		# bao giờ ném lỗi.
		from miyano_portal import nhat_ky
		nhat_ky.ghi(
			nhat_ky.SK_KHOA_THU_HOI,
			customer=self.customer, khoa_phong=self.khoa_phong,
			de_xuat=self.name, vai=nhat_ky.VAI_KHOA,
		)

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
		"""Spec 2026-10-09 §4.3 (kế thừa §5.6 bẫy #2) — đóng dấu `don_gia` =
		giá Price List của khách TẠI THỜI ĐIỂM GỬI DUYỆT, cùng lúc `so_luong_
		de_xuat` bị khoá (`_chan_sua_so_luong_de_xuat`). Đây là "giá khoa đã
		thấy" mà `de_xuat_duyet._kiem_gia_doi()` so với giá hiện hành lúc
		DUYỆT để cảnh báo quản lý — không cảnh báo được gì nếu không có số
		này.

		Hỏi ĐÚNG nguồn giá `dat_hang._xay_don` hỏi (`bang_gia_khach`) — hai
		đường tra giá khác nhau sớm muộn cũng lệch.

		Đóng dấu THEO TỪNG DÒNG, chỉ dòng `nguon_gia == "Bảng giá"`:
		  * dòng "Chờ báo giá" chưa có giá ở đâu cả (sales điền khi báo giá)
		    nên không có "giá khoa đã thấy" nào để đóng dấu;
		  * dòng CŨ còn mang "Hợp đồng" (đóng băng trước spec 2026-10-09) giữ
		    nguyên `don_gia` đã đóng dấu từ hồi đó — đơn của nó vẫn được dựng
		    theo Price List lúc duyệt, và `_kiem_gia_doi()` bỏ qua nó.

		Tự gọi `_suy_nguon_gia()` TRƯỚC khi đọc `nguon_gia` — hàm này chạy
		TRONG `gui_duyet()`, TRƯỚC `self.save()` (nên trước `validate()` của
		chính lần lưu này), nên KHÔNG được tin `self.items[].nguon_gia` trong
		bộ nhớ đã chắc chắn mới. Ở lần gửi ĐẦU, `gui_duyet()` đã suy lại mọi
		dòng ngay trước khi cấp mã (Ruling R8), nên lời gọi ở đây chỉ còn
		chạm dòng chưa lưu. Trên đường gửi lại (sau "Từ chối" hoặc sau
		thu hồi) lời gọi đó bỏ qua các dòng ĐÃ đóng băng (xem `dong_bang` ở
		đó) và chỉ còn tác dụng cho dòng MỚI thêm.

		GHI VÔ ĐIỀU KIỆN: phiếu gửi lại đi qua đây lần thứ hai, và con dấu
		phải nói về LẦN GỬI ẤY. Dòng "Bảng giá" đã đóng băng mà giá vừa ĐỔI
		được đóng dấu lại theo giá hiện hành.

		Ruling R5 (12/10/2026) — dòng "Bảng giá" mà mặt hàng KHÔNG CÒN giá
		thì chuyển sang "Chờ báo giá" với `don_gia = 0`, DÙ dòng đã đóng
		băng. Đây là ngoại lệ DUY NHẤT của chốt đóng băng, và nó phải có:
		`_kiem_gia_doi()` chặn duyệt dòng "Bảng giá" mất giá và bảo quản lý
		từ chối để khoa gửi lại — nếu lần gửi lại vẫn giữ "Bảng giá" thì
		phiếu bị chặn mãi (ở "Từ chối" khoa không xoá/đổi được dòng). Hạ
		`don_gia` về 0 cùng lúc là bắt buộc: vòng lặp này bỏ qua dòng "Chờ
		báo giá" ở các lần gửi sau, nên con số của lần gửi trước sẽ sống
		mãi nếu không xoá ngay tại đây.

		Đặt ở ĐÂY chứ không ở `_suy_nguon_gia()`/`validate()`: chỉ một lần
		GỬI DUYỆT — một đề nghị mới của khoa — mới được viết lại nguồn giá
		của dòng đã đóng băng; một lần lưu bất kỳ thì không. Chiều ngược lại
		("Chờ báo giá" vừa có giá) và dòng cũ "Hợp đồng" KHÔNG được đụng tới.
		"""
		from miyano_portal import bang_gia_khach
		self._suy_nguon_gia()
		gia = bang_gia_khach.gia_bang_gia_nhieu(
			self.customer, [r.item_code for r in self.items]
		)
		for row in self.items:
			if row.nguon_gia != NGUON_GIA_BANG_GIA:
				continue
			gia_moi = gia.get(row.item_code)
			if gia_moi is None:
				row.nguon_gia = NGUON_GIA_CHO_BAO_GIA
				row.don_gia = 0
				continue
			row.don_gia = gia_moi

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
		# Task 2 (nhật ký thao tác) — cùng chỗ, cùng lý do với `bao_de_xuat_
		# duyet` ngay dưới.
		from miyano_portal import nhat_ky
		# Việc #5 (vòng sửa sau review toàn nhánh) — §6/§9.4 đòi `ghi_chu`
		# mang CẢ HAI: số dòng đã điều chỉnh LẪN tư cách duyệt, ví dụ §9.4:
		# "Hạ 2 dòng so với số khoa xin · Tư cách: Quản lý chính". Chỉ có
		# tư cách một mình (bản trước bản vá này) không nói cho khoa biết
		# phiếu của họ có bị cắt hay không — đó chính là nửa mang thông tin.
		# Đếm theo `so_luong_de_xuat` (khoa xin) so với `so_luong_duyet`
		# (quản lý chốt) — KHÔNG dùng độ dài danh sách hay đếm dòng bị xoá:
		# §5.3 chốt bỏ một mặt hàng = HẠ `so_luong_duyet` VỀ 0, KHÔNG xoá
		# dòng, nên dòng bị bỏ hẳn vẫn phải nằm trong phép đếm này (nó vẫn
		# là một dòng có `so_luong_duyet != so_luong_de_xuat`).
		so_dong_dieu_chinh = sum(
			1 for d in self.items
			if float(d.so_luong_duyet or 0) != float(d.so_luong_de_xuat or 0)
		)
		ghi_chu = f"Tư cách: {self.duyet_voi_tu_cach}"
		if so_dong_dieu_chinh:
			# Duyệt NGUYÊN SI (so_dong_dieu_chinh == 0) thì KHÔNG in mệnh đề
			# này — im lặng đúng hơn một câu "Hạ 0 dòng" vô nghĩa.
			ghi_chu = f"Hạ {so_dong_dieu_chinh} dòng so với số khoa xin · {ghi_chu}"
		nhat_ky.ghi(
			nhat_ky.SK_QUAN_LY_DUYET,
			customer=self.customer, khoa_phong=self.khoa_phong,
			de_xuat=self.name, vai=nhat_ky.VAI_QUAN_LY,
			ghi_chu=ghi_chu,
		)
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
		# Task 2 (nhật ký thao tác) — cùng chỗ, cùng lý do với `bao_de_xuat_
		# tu_choi` ngay dưới.
		from miyano_portal import nhat_ky
		nhat_ky.ghi(
			nhat_ky.SK_QUAN_LY_TU_CHOI,
			customer=self.customer, khoa_phong=self.khoa_phong,
			de_xuat=self.name, vai=nhat_ky.VAI_QUAN_LY,
			ghi_chu=ly_do,
		)
		# Task 8 (§5.8) — cùng bảng người nhận với duyệt().
		from miyano_portal.portal_thong_bao_khach import bao_de_xuat_tu_choi
		bao_de_xuat_tu_choi(self)

	def huy(self):
		"""§5.4b — phiếu còn nguyên, chỉ đổi trạng thái. Khác XOÁ THẬT ở chỗ
		vẫn truy vết được sau này."""
		self._kiem_chuyen(TRANG_THAI_DA_HUY)
		self.trang_thai = TRANG_THAI_DA_HUY
		self.save(ignore_permissions=True)
		# Task 2 (nhật ký thao tác) — cùng chỗ, cùng lý do đã nêu ở
		# `gui_duyet()`.
		from miyano_portal import nhat_ky
		nhat_ky.ghi(
			nhat_ky.SK_QUAN_LY_HUY_PHIEU,
			customer=self.customer, khoa_phong=self.khoa_phong,
			de_xuat=self.name, vai=nhat_ky.VAI_QUAN_LY,
		)

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
		# Task 2 (nhật ký thao tác) — cùng chỗ, cùng lý do đã nêu ở
		# `gui_duyet()`.
		from miyano_portal import nhat_ky
		nhat_ky.ghi(
			nhat_ky.SK_KHOA_XIN_SUA,
			customer=self.customer, khoa_phong=self.khoa_phong,
			de_xuat=self.name, vai=nhat_ky.VAI_KHOA,
			ghi_chu=f"{len(thay_doi)} dòng xin sửa",
		)

	def _kiem_don_dung_duoc_xin_sua(self):
		"""C1 (review tổng 19/08) — đơn đứng sau có SỬA ĐƯỢC không.

		Lõi `portal.portal_order_sua_so_luong` (nơi `de_xuat_duyet_sua` bắt
		buộc phải đi qua để sửa Sales Order thật) có HAI chốt cứng ở MỨC
		ĐƠN mà trả lời được ngay: `workflow_state == "Chờ khách đồng ý"` và
		`portal_mua_le.di_vong_bao_gia(so)` (Task 6; trước đó là chuỗi
		`custom_loai_don == "Mua lẻ"` viết tại chỗ), cộng chốt hiệu lực
		BR-R5. Trước bản vá, `xin_sua()` không hỏi chốt nào — nên:

		  * đơn KHÔNG đi vòng báo giá (`dat_hang.py` đóng dấu `custom_loai_
		    don = "Theo bảng giá"` khi mọi dòng đã có giá, ngược lại là "Mua
		    lẻ") và
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
		# Task 2 (nhật ký thao tác) — cùng chỗ, cùng lý do đã nêu ở
		# `gui_duyet()`. Dòng này VÁ khoản nợ kỹ thuật §7 mục 3b của HDSD:
		# khối truy vết ở đầu phiếu (`nguoi_duyet`/`thoi_diem_duyet`) vẫn
		# chỉ mang dấu của lần DUYỆT ĐẦU TIÊN (xem docstring `duyet()`),
		# nhưng giờ vòng "duyệt sửa" có dòng nhật ký RIÊNG của chính nó.
		from miyano_portal import nhat_ky
		nhat_ky.ghi(
			nhat_ky.SK_QUAN_LY_DUYET_SUA,
			customer=self.customer, khoa_phong=self.khoa_phong,
			de_xuat=self.name, vai=nhat_ky.VAI_QUAN_LY,
		)

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
		# Task 2 (nhật ký thao tác) — cùng chỗ, cùng lý do đã nêu ở
		# `gui_duyet()`.
		from miyano_portal import nhat_ky
		nhat_ky.ghi(
			nhat_ky.SK_QUAN_LY_TU_CHOI_SUA,
			customer=self.customer, khoa_phong=self.khoa_phong,
			de_xuat=self.name, vai=nhat_ky.VAI_QUAN_LY,
			ghi_chu=ly_do,
		)

	def on_trash(self):
		"""§5.4b — "phiếu đã gửi duyệt thì không xoá được, dùng Huỷ phiếu để
		giữ lại dấu vết".

		Review TOÀN NHÁNH (03/09/2026, Critical) — hỏi `ma_de_xuat`, KHÔNG
		chỉ hỏi `trang_thai`. Bản trước hỏi `trang_thai != "Nháp"`, đúng chỉ
		chừng nào bất biến "Nháp ⇒ chưa từng gửi" còn đứng; `thu_hoi()`
		(cùng phiên này) đưa một phiếu ĐÃ gửi duyệt về lại Nháp nên hai cú
		bấm `Thu hồi để sửa → Xoá` đi vòng qua chốt. Cái mất không phải bản
		ghi: `frappe.delete_doc` cuốn theo CẢ `Version` (toàn bộ `track_
		changes` — chính thứ `thu_hoi()` viện dẫn khi nói "giá trị cũ không
		mất") lẫn `Notification Log` trỏ tới chứng từ, còn số `sinh_ma()` đã
		tiêu thì để lại một lỗ vĩnh viễn trong dãy mã của bệnh viện.

		`ma_de_xuat` là dấu "ĐÃ TỪNG GỬI" duy nhất sống sót sau thu hồi —
		`thu_hoi()` CỐ Ý giữ nó (mã sinh đúng một lần), và không đường nào
		trong app xoá nó đi. Trạng thái chỉ nói phiếu ĐANG ở đâu; câu hỏi
		§5.4b thật sự cần là phiếu ĐÃ TỪNG ra khỏi khoa hay chưa.
		"""
		if self.trang_thai != TRANG_THAI_NHAP or self.ma_de_xuat:
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
		"""Spec 2026-10-09 §3.2 — ghi `nguon_gia` cho MỌI dòng, KHÔNG tin giá
		trị client gửi (QĐ-G1): mã hàng CÓ giá trong Price List của `self.
		customer` (`bang_gia_khach.gia_bang_gia_nhieu` — cùng phép hỏi với
		danh mục và `dat_hang._xay_don`) → `Bảng giá`; ngược lại (kể cả
		`item_code` rỗng) → `Chờ báo giá`. `blanket_order` luôn để RỖNG:
		phiếu không còn gắn hợp đồng khung nào lên dòng. Luôn GHI ĐÈ, kể cả
		khi `self.items` rỗng — không có nhánh nào bỏ qua để giá trị cũ/giá
		trị client gửi sống sót. `self.hdnt` ở đầu phiếu chỉ còn là field
		LEGACY, không được đọc ở đây.

		I3 (review vòng 1) — TRỪ khi phiếu đã qua khỏi Nháp: ĐÓNG BĂNG
		`nguon_gia`/`blanket_order` của các dòng đã có lúc Gửi duyệt. Nguồn
		giá của dòng là điều khoa ĐÃ THẤY lúc gửi ("có giá sẵn" hay "chờ báo
		giá"), và phiếu đã được tách theo đúng loại đó lúc gửi (§4.1). Không
		có chốt này, một lần lưu BẤT KỲ sau đó (VD: `duyet_sua()`, luồng xin
		sửa/duyệt sửa số lượng) sẽ tính lại theo Price List HIỆN TẠI và âm
		thầm ghi đè bằng chứng đó. Ngoại lệ duy nhất nằm ở `_dong_dau_gia()`
		(Ruling R5): lúc GỬI DUYỆT, dòng "Bảng giá" đã mất giá chuyển sang
		"Chờ báo giá". Chốt này cũng là thứ giữ nguyên các dòng
		CŨ mang `Hợp đồng` + `blanket_order` (đóng băng trước spec
		2026-10-09): chúng không bị tính lại, và đường duyệt vẫn chạy được
		với chúng vì `dat_hang._xay_don` tự hỏi Price List cho mọi dòng.

		SỬA (review TOÀN NHÁNH, 03/09/2026) — gate hỏi `ma_de_xuat`, KHÔNG
		hỏi trạng thái, nên nó CỐ Ý KHÁC điều kiện của `_chan_sua_so_luong_
		de_xuat`. Vì sao hai khoá tách đôi:

		  * khoá SỐ LƯỢNG phải MỞ LẠI khi thu hồi — đó là toàn bộ lý do
		    `thu_hoi()` tồn tại (nhân viên sửa lại đơn mình vừa gửi);
		  * khoá NGUỒN GIÁ thì KHÔNG — "dòng này đã gửi đi với nguồn giá
		    nào" là bằng chứng, không phải một ô để sửa, và không ai bấm Thu
		    hồi để xin đổi nó.

		Nếu gate này hỏi trạng thái, chính `thu_hoi()` mở nó ra: hàm đó đặt
		`trang_thai = "Nháp"` TRƯỚC `save()`, nên `validate()` của lần lưu
		đó chạy với `dong_bang = False` và tính lại MỌI dòng. Ca thật: dòng
		đang là "Bảng giá", giá bị gỡ khỏi Price List trong lúc chờ duyệt →
		thu hồi lật nó sang "Chờ báo giá" mà KHÔNG hạ `don_gia`; lần gửi
		duyệt sau `_dong_dau_gia` bỏ qua dòng chờ báo giá nên `don_gia` cũ
		SỐNG NGUYÊN — quản lý duyệt một dòng chờ báo giá còn khoe con số
		của một giá đã bị gỡ. Việc chuyển dòng đó sang "Chờ báo giá" là của
		`_dong_dau_gia()` lúc gửi lại, nơi nó xoá con dấu cùng lúc. Xem
		`test_nguon_gia_dong.py::test_thu_hoi_KHONG_mo_bang_nguon_gia_cua_
		dong_cu`.

		`ma_de_xuat` là dấu "ĐÃ TỪNG gửi duyệt" duy nhất sống sót qua thu
		hồi (`thu_hoi()` cố ý giữ nó) — cùng dấu mà `on_trash` đã chuyển
		sang hỏi, một sự thật chứ không phải hai.

		SỬA (advisor, ngay sau review vòng 1) — đóng băng theo TỪNG DÒNG đã
		có lúc gửi duyệt, KHÔNG `return` sớm cho CẢ `self.items`:
		`_chan_sua_so_luong_de_xuat` vẫn CHO PHÉP thêm dòng MỚI sau khi gửi
		duyệt (Đường lọt #1 của gate đó — quản lý điều chỉnh qua `_ap_dieu_
		chinh`, dòng mới bắt buộc `so_luong_de_xuat = 0`). `return` sớm cho
		cả tập dòng sẽ khiến dòng MỚI đó không bao giờ được `_suy_nguon_
		gia()` chạm tới — nó giữ nguyên default Select "Hợp đồng" (lựa chọn
		ĐẦU trong `options`), một nguồn giá không dòng mới nào được phép
		mang nữa.
		"""
		from miyano_portal import bang_gia_khach
		dong_bang = not self.is_new() and (
			bool(self.ma_de_xuat) or self.trang_thai != TRANG_THAI_NHAP
		)
		# SỬA (advisor, ngay sau bản sửa I3 đầu) — KHÔNG dùng `self.get_doc_
		# before_save()` làm nguồn `da_khoa`: property đó chỉ được Frappe
		# điền trong một chu trình `save()` ĐÃ XẢY RA trên CHÍNH object
		# Python này (`base_document.py`, gán trong `_get_doc_before_save`
		# gọi từ `run_before_save_hooks`), mà hàm này còn được gọi từ
		# `gui_duyet()`/`_dong_dau_gia()` chạy TRỰC TIẾP, TRƯỚC `self.
		# save()`. Lần gửi ĐẦU vô hại: lời gọi của `gui_duyet()` chạy khi
		# chưa có mã (`dong_bang` False, không đọc `da_khoa`); lời gọi của
		# `_dong_dau_gia()` chạy sau khi mã đã cấp (`dong_bang` True) nên
		# cũng phải đi đường đọc DB dưới đây.
		# Đường RESUBMIT-SAU-TỪ-CHỐI (`gui_duyet()` hợp lệ từ "Từ chối")
		# THÌ VỠ nếu dùng property đó: endpoint thật nạp `Document` MỚI qua `frappe.get_doc()`
		# mỗi request rồi gọi `.gui_duyet()` ngay — không có `save()` nào
		# trước đó trên object đó để điền `_doc_before_save`, `get_doc_
		# before_save()` trả `None`, `.items` ném `AttributeError` → HTTP
		# 500 thật cho người dùng bấm "Gửi duyệt lại" sau khi bị từ chối.
		# Đọc THẲNG DB thay thế — đúng bất kể chu trình save() đã bắt đầu
		# hay chưa, vì nó không phụ thuộc trạng thái nội bộ của object.
		da_khoa = set(frappe.get_all(
			"Portal De Xuat Mua Item", filters={"parent": self.name}, pluck="name"
		)) if dong_bang else set()
		co_gia = bang_gia_khach.gia_bang_gia_nhieu(
			self.customer, [r.item_code for r in self.items]
		)
		for row in self.items:
			if dong_bang and row.name in da_khoa:
				# Dòng đã có lúc gửi duyệt — đóng băng, không tính lại.
				continue
			row.blanket_order = None
			row.nguon_gia = (
				NGUON_GIA_BANG_GIA if row.item_code in co_gia
				else NGUON_GIA_CHO_BAO_GIA
			)

	def co_dong_cho_bao_gia(self) -> bool:
		"""Task 2, Ruling P7 — THAY THẾ mọi chỗ trước đây hỏi `loai_don`
		(nay đã xoá khỏi doctype). `True` khi có ít nhất một dòng `Chờ báo
		giá` HOẶC có dòng đặt ngoài (`self.dat_ngoai` — chưa có mã, nên
		không có giá nào trong Price List). Dòng `Bảng giá` và dòng CŨ còn
		mang `Hợp đồng` đều KHÔNG tính là chờ báo giá.

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
