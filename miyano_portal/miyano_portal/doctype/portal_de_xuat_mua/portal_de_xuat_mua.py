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
		# "Đã duyệt" lại là trạng thái kết thúc: khoa không còn xin sửa số
		# lượng sau duyệt (vòng đó cần đơn ở "Chờ khách đồng ý", đã bỏ ở patch
		# v1_44). Cạnh dưới chỉ để phiếu CŨ còn ở "Chờ duyệt sửa" được quản lý
		# từ chối (`tu_choi_sua`) và về "Đã duyệt".
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

	def tu_choi_sua(self, ly_do):
		"""Quản lý TỪ CHỐI yêu cầu xin sửa — đơn giữ NGUYÊN số đã duyệt
		trước đó (không đụng Sales Order), chỉ dọn `so_luong_xin_sua` và
		ghi lý do vào `ghi_chu_quan_ly` của từng dòng có yêu cầu. Lối ra duy
		nhất của phiếu cũ còn ở "Chờ duyệt sửa" (xin sửa đã bỏ, patch v1_44).

		I3 (review Task 9) — TỰ KIỂM đang đứng ĐÚNG ở `TRANG_THAI_CHO_DUYET_
		SUA` trước khi gọi `_kiem_chuyen`: cạnh `-> Đã duyệt` cũng hợp lệ từ
		`Chờ duyệt`, nên thiếu chốt này phiếu chưa có đơn bị đẩy thẳng sang
		"Đã duyệt".

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
