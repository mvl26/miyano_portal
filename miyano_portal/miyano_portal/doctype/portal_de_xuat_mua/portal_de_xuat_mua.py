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
	}
	# Trạng thái kết thúc CỐ Ý không xuất hiện làm chìa khoá — không có cạnh
	# đi ra từ chúng. Cùng khuôn với `Portal Item Request`.

	def validate(self):
		self._chan_khoa_phong_khac_benh_vien()
		self._chan_sua_so_luong_de_xuat()

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
		self.trang_thai = TRANG_THAI_CHO_DUYET
		self.save(ignore_permissions=True)

	def duyet(self, nguoi_duyet, tu_cach="Quản lý chính", uy_quyen=None):
		"""Nơi DUY NHẤT ghi `Đã duyệt` — cùng cả khối truy vết.

		`tu_duyet` SUY RA từ `nguoi_duyet == self.owner`, không nhận tham số
		riêng: một cờ tự khai đúng lúc cần nhất (chính người tạo phiếu tự
		duyệt cho mình) sẽ không được khai nếu để caller tự truyền.
		"""
		self._kiem_chuyen(TRANG_THAI_DA_DUYET)
		self.nguoi_duyet = nguoi_duyet
		self.thoi_diem_duyet = now_datetime()
		self.duyet_voi_tu_cach = tu_cach
		self.uy_quyen = uy_quyen
		self.tu_duyet = 1 if nguoi_duyet == self.owner else 0
		self.trang_thai = TRANG_THAI_DA_DUYET
		self.save(ignore_permissions=True)

	def tu_choi(self, ly_do):
		self._kiem_chuyen(TRANG_THAI_TU_CHOI)
		if not (ly_do or "").strip():
			frappe.throw(
				"Lý do từ chối là bắt buộc khi từ chối phiếu.", frappe.ValidationError
			)
		self.ly_do_tu_choi = ly_do
		self.trang_thai = TRANG_THAI_TU_CHOI
		self.save(ignore_permissions=True)

	def huy(self):
		"""§5.4b — phiếu còn nguyên, chỉ đổi trạng thái. Khác XOÁ THẬT ở chỗ
		vẫn truy vết được sau này."""
		self._kiem_chuyen(TRANG_THAI_DA_HUY)
		self.trang_thai = TRANG_THAI_DA_HUY
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
