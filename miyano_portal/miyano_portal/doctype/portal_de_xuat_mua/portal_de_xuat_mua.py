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
		self._suy_tu_duyet()

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
		self.trang_thai = TRANG_THAI_CHO_DUYET
		self.save(ignore_permissions=True)
		# Task 8 (§5.8) — CHỈ quản lý cần biết có phiếu chờ duyệt. Hàm này
		# không bao giờ ném lỗi (xem docstring nó) nên an toàn gọi ngay sau
		# save(): một trục trặc ở khâu thông báo không được cuốn theo trạng
		# thái "Chờ duyệt" vừa ghi thành công.
		from miyano_portal.portal_thong_bao_khach import bao_de_xuat_gui_duyet
		bao_de_xuat_gui_duyet(self)

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
		"""Nơi DUY NHẤT ghi `Đã duyệt` — cùng cả khối truy vết.

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
		"""
		self._kiem_chuyen(TRANG_THAI_CHO_DUYET_SUA)
		theo_ma = {d.item_code: d for d in self.items}
		for row in dong:
			ma = row.get("item_code")
			if ma in theo_ma:
				theo_ma[ma].so_luong_xin_sua = float(row.get("qty") or 0)
		self.trang_thai = TRANG_THAI_CHO_DUYET_SUA
		self.save(ignore_permissions=True)

	def duyet_sua(self):
		"""Quản lý ĐỒNG Ý với yêu cầu xin sửa — chép `so_luong_xin_sua`
		sang `so_luong_duyet`, dọn `so_luong_xin_sua`, quay lại "Đã duyệt".

		KHÔNG tự đụng Sales Order: endpoint gọi hàm này (`de_xuat.de_xuat_
		duyet_sua`) PHẢI gọi lõi `portal_order_sua_so_luong` TRƯỚC — hàm đó
		mới là nơi sửa đơn thật (và tự đồng bộ ngược `so_luong_duyet` lên
		đúng phiếu này, xem "Ruling preflight C4" ở `api/portal.py`).
		Hàm này chỉ dọn phần còn lại (`so_luong_xin_sua`) và đổi trạng
		thái."""
		self._kiem_chuyen(TRANG_THAI_DA_DUYET)
		for d in self.items:
			if d.so_luong_xin_sua:
				d.so_luong_duyet = d.so_luong_xin_sua
				d.so_luong_xin_sua = 0
		self.trang_thai = TRANG_THAI_DA_DUYET
		self.save(ignore_permissions=True)

	def tu_choi_sua(self, ly_do):
		"""Quản lý TỪ CHỐI yêu cầu xin sửa — đơn giữ NGUYÊN số đã duyệt
		trước đó (không đụng Sales Order), chỉ dọn `so_luong_xin_sua` và
		ghi lý do vào `ghi_chu_quan_ly` của từng dòng có yêu cầu."""
		self._kiem_chuyen(TRANG_THAI_DA_DUYET)
		if not (ly_do or "").strip():
			frappe.throw(
				"Lý do từ chối là bắt buộc khi từ chối yêu cầu xin sửa.",
				frappe.ValidationError,
			)
		for d in self.items:
			if d.so_luong_xin_sua:
				d.ghi_chu_quan_ly = ly_do
				d.so_luong_xin_sua = 0
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
