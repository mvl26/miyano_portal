"""Mẫu in theo chế độ kế toán — yêu cầu chủ đầu tư 2026-08-16.

Điều file này canh giữ: **không chứng từ nào rơi về mẫu Standard của ERPNext**.
Cài đủ mẫu mà quên gán mặc định thì mẫu chỉ nằm đó chờ ai nhớ chọn trong
dropdown — đúng hiện trạng trước bản này, và không test nào bắt được.
"""

import contextlib
import hashlib
import importlib
import io
import re

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.www.printview import get_html_and_style

from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

from miyano_portal.patches.v1_28.cap_nhat_02vt_bien_ban_ban_giao import (
	TIEU_DE_LOG,
	execute as cap_nhat_02vt,
)
from miyano_portal.patches.v1_29.tat_mau_in_02vt_khong_tien_to import (
	execute as tat_mau_tran,
)
from miyano_portal.setup.gan_mau_in_mac_dinh import MAC_DINH, gan_mau_in_mac_dinh
from miyano_portal.setup.install_bien_ban_print_formats import (
	FORMATS,
	HTML_PHIEU_XUAT_02VT,
	NAME_BIEN_BAN_TT107,
	NAME_BIEN_BAN_TT200,
	NAME_PHIEU_XUAT_02VT,
	install_bien_ban_print_formats,
)
from miyano_portal.tien_bang_chu import tien_bang_chu

# Chỉ số cột của mẫu 02-VT bản TT 99/2025 (10 cột), đặt tên để khẳng định đọc
# được: STT, Mã vật tư, Tên hàng, ĐVT, SL yêu cầu, SL thực xuất, Số lô, Hạn
# dùng, Đơn giá, Thành tiền.
# Ruling P47 — hai vế của đoạn cam kết cuối phiếu.
CAU_GIAO_DU = "được bàn giao đầy đủ"
CAU_GIAO_THIEU = "đúng số lượng ghi trên phiếu này"

O_SL_YEU_CAU = 4
O_SL_THUC_XUAT = 5
O_SO_LO = 6
O_HAN_DUNG = 7


def _doc_patches_txt() -> list[str]:
	"""Các mục patch trong `patches.txt`, giữ nguyên thứ tự, bỏ tiêu đề mục
	(`[pre_model_sync]`) và dòng chú thích."""
	duong = frappe.get_app_path("miyano_portal", "patches.txt")
	with open(duong, encoding="utf-8") as fh:
		return [
			d.strip() for d in fh
			if d.strip() and not d.startswith("#") and not d.startswith("[")
		]


def _doan_cam_ket(html: str) -> str:
	"""Đoạn cam kết KHÁCH ĐỌC, đã bỏ chú thích HTML.

	Khẳng định trên cả trang không dùng được ở đây: chú thích trong mẫu in có
	giải thích vì sao câu này lệch so với bản mẫu docx, và chú thích đó tất
	nhiên có chứa chữ "đầy đủ". Chú thích không bao giờ in ra giấy — thứ khách
	đặt bút ký là đoạn `<p class="cam-ket">`.
	"""
	khong_chu_thich = re.sub(r"<!--.*?-->", "", html, flags=re.S)
	doan = re.findall(
		r'<p class="cam-ket">(.*?)</p>', khong_chu_thich, re.S
	)
	assert len(doan) == 1, f"phải có ĐÚNG một đoạn cam kết, đang có {len(doan)}"
	return re.sub(r"\s+", " ", doan[0]).strip()


def _o_cua_dong(html: str, idx: int = 0) -> list[str]:
	"""Các ô `<td>` của MỘT dòng hàng trên bản in, theo ĐÚNG thứ tự cột.

	Vì sao không dùng `assertIn` trên cả trang: quy tắc cần ghim là "ô SL yêu
	cầu lấy từ ĐƠN HÀNG, và để TRỐNG khi không có đơn". Một `assertNotIn` trên
	cả trang không phát biểu được điều đó — con số ấy còn nằm ở cột khác, ở
	tiền, ở ngày tháng. Chỉ VỊ TRÍ ô mới nói đúng thứ đang canh.
	"""
	tbody = re.search(r"<tbody>(.*?)</tbody>", html, re.S).group(1)
	dong = re.findall(r"<tr>(.*?)</tr>", tbody, re.S)[idx]
	return [
		re.sub(r"<[^>]+>", "", o).strip()
		for o in re.findall(r"<td[^>]*>(.*?)</td>", dong, re.S)
	]


class TestMauInDaCai(FrappeTestCase):
	def test_cai_idempotent(self):
		install_bien_ban_print_formats()
		lan_hai = install_bien_ban_print_formats()
		self.assertEqual(lan_hai, [], "Chạy lại phải không tạo thêm mẫu nào.")
		for name, doc_type, _html in FORMATS:
			self.assertTrue(frappe.db.exists("Print Format", name), f"thiếu mẫu {name}")
			self.assertEqual(
				frappe.db.get_value("Print Format", name, "doc_type"), doc_type
			)

	def test_moi_doctype_deu_co_mau_mac_dinh(self):
		"""Chốt chính của cả file: không chứng từ nào dùng mẫu ERPNext."""
		gan_mau_in_mac_dinh()
		for doctype, mau, ly_do in MAC_DINH:
			with self.subTest(doctype=doctype):
				gan = frappe.db.get_value(
					"Property Setter",
					{"doc_type": doctype, "property": "default_print_format"},
					"value",
				)
				self.assertEqual(
					gan, mau,
					f"{doctype} chưa gán mẫu mặc định ({ly_do}) → bấm In sẽ ra "
					"mẫu Standard của ERPNext.",
				)
				self.assertTrue(
					frappe.db.exists("Print Format", mau),
					f"{doctype} trỏ vào mẫu KHÔNG TỒN TẠI — Frappe sẽ im lặng "
					"quay lại mẫu Standard, tệ hơn cả không gán.",
				)


class TestMauBienBanKiemNghiem(FrappeTestCase):
	"""Mẫu 03-VT phải render qua ĐÚNG pipeline Desk, với context tối thiểu
	{doc, frappe} — đọc docstring install_kho_print_formats về hai đường render."""

	def setUp(self):
		install_bien_ban_print_formats()
		# Bốc biên bản CÓ CẢ hàng hỏng lẫn hàng thiếu, không bốc tuỳ ý: một
		# `get_value` không điều kiện sẽ trúng biên bản nhận đủ và test cột
		# "Thiếu" tự bỏ qua chính mình — một test bỏ qua trong im lặng là một
		# test không tồn tại (bài học Ruling 18).
		self.bb = frappe.db.sql("""
			select distinct p.name from `tabPortal Delivery Inspection` p
			inner join `tabPortal Delivery Inspection Item` i on i.parent = p.name
			where p.docstatus = 1
			  and ifnull(i.sl_giao,0) - ifnull(i.sl_nhan,0) - ifnull(i.sl_tra,0) > 0
			order by p.creation desc limit 1
		""")
		self.bb = self.bb[0][0] if self.bb else None
		if not self.bb:
			self.bb = self._tao_bien_ban_co_thieu()

	def _render(self, pf):
		doc = frappe.get_doc("Portal Delivery Inspection", self.bb)
		return get_html_and_style(doc=doc.as_json(), print_format=pf)["html"]

	def test_dung_cau_truc_mau_03_vt(self):
		h = self._render(NAME_BIEN_BAN_TT107)
		for phai_co in (
			"Mẫu số 03 - VT",
			"BIÊN BẢN KIỂM NGHIỆM",
			"Ban kiểm nghiệm",
			"Số lượng đúng quy cách, phẩm chất",
			"Số lượng không đúng quy cách, phẩm chất",
			"Ý kiến của Ban kiểm nghiệm",
			"Trưởng ban",
		):
			self.assertIn(phai_co, h, f"mẫu 03-VT thiếu «{phai_co}»")

	def test_hai_bien_the_trich_dung_thong_tu(self):
		h107 = self._render(NAME_BIEN_BAN_TT107)
		h200 = self._render(NAME_BIEN_BAN_TT200)
		self.assertIn("107/2017/TT-BTC", h107)
		self.assertNotIn("200/2014/TT-BTC", h107)
		self.assertIn("200/2014/TT-BTC", h200)
		self.assertNotIn("107/2017/TT-BTC", h200)

	def test_hang_thieu_khong_bi_gop_vao_cot_hang_hong(self):
		"""Thiếu hàng và hàng hỏng là HAI sự việc. Gộp chúng vào cùng cột
		"không đúng quy cách" là khai sai trên một chứng từ pháp lý."""
		h = self._render(NAME_BIEN_BAN_TT107)
		self.assertIn("Thiếu", h, "Phần hàng thiếu phải hiện ở cột Ghi chú")
		# ...và KHÔNG bị cộng dồn vào cột "không đúng quy cách".
		doc = frappe.get_doc("Portal Delivery Inspection", self.bb)
		for r in doc.items:
			thieu = (r.sl_giao or 0) - (r.sl_nhan or 0) - (r.sl_tra or 0)
			if thieu > 0:
				gop = (r.sl_tra or 0) + thieu
				self.assertNotIn(
					f'class="num">{gop:g}<', h,
					"Số hàng hỏng bị cộng dồn với số hàng thiếu — hai sự việc "
					"khác nhau bị khai thành một.",
				)

	def _tao_bien_ban_co_thieu(self):
		"""Dựng biên bản có CẢ hỏng lẫn thiếu khi site chưa có cái nào.

		Không `skipTest`: mẫu in này tồn tại chính vì trường hợp đó, và một
		test tự bỏ qua mình khi thiếu dữ liệu là một test không bảo vệ gì.
		"""
		from miyano_portal.tests.test_e9_kiem_hang import _KiemHangBase  # noqa: F401

		doc = frappe.get_doc({
			"doctype": "Portal Delivery Inspection",
			"customer": frappe.db.get_value("Customer", {}, "name"),
			"delivery_note": f"DN-MAUIN-{frappe.generate_hash(length=6)}",
			"ngay_kiem": frappe.utils.nowdate(),
			"nguoi_kiem": "test@mauin.miyano",
			"trang_thai": "Nháp",
			"items": [{
				"item_code": frappe.db.get_value("Item", {"disabled": 0}, "name"),
				"item_name": "Vật tư test mẫu in", "uom": "Hộp",
				"sl_giao": 10, "sl_nhan": 6, "sl_tra": 2,
				"ly_do": "2 hỏng, 2 không tới",
			}],
		})
		doc.insert(ignore_permissions=True)
		doc.flags.ignore_permissions = True
		doc.submit()
		return doc.name


class TestMauPhieuXuat02VT(FrappeTestCase):
	"""Mẫu 02-VT bản **TT 99/2025** — "Phiếu xuất kho kiêm biên bản bàn giao".

	Nội dung của mẫu chép từ `docs/04_MVL_PhieuXuatKho_GiaoHang(DN).docx` — tệp
	Word có thật trong repo, siêu dữ liệu ghi: tạo 30/07/2026, sửa lần cuối
	06/08/2026 bởi "Tạ Trường Xuân". Bài dưới đây ghim cả vế DƯƠNG (có 99/2025)
	lẫn vế ÂM (không còn 200/2014): thêm dòng mới mà quên gỡ dòng cũ là in ra
	một chứng từ trích hai thông tư.

	**Lớp này TỰ DỰNG phiếu giao của nó.** Bản trước bốc một `Delivery Note`
	bất kỳ đã ghi sổ trên site, và `skipTest` khi không tìm thấy — trên một CSDL
	sạch (CI, máy mới) cả lớp lặng lẽ bỏ qua, tức không canh gì. Nó cũng render
	mẫu ĐANG NẰM TRONG CSDL, nên trên site chưa chạy patch v1_28 mọi khẳng định
	dưới đây kiểm HTML cũ. Cả hai chỗ sửa ở `setUp`: dựng dữ liệu riêng, và
	đồng bộ HTML trong CSDL về đúng hằng số của mã nguồn trước khi render.
	"""

	KHACH = "ZZTESTMAUIN Benh Vien"
	COMPANY = "Miyano Việt Nam"
	KHO = "Kho Miyano - MYN"
	COST_CENTER = "Main - MYN"
	ITEM = "MYN-GLOVE-M"
	ITEM_2 = "MYN-SYR-10"
	ITEM_LO = "ZZTESTMAUIN-LO"
	LO_A = "ZZTESTMAUIN-LO-A"
	LO_B = "ZZTESTMAUIN-LO-B"
	HAN_A = "2027-03-31"
	HAN_B = "2027-09-30"

	def setUp(self):
		install_bien_ban_print_formats()
		# `install_...` idempotent kiểu "bỏ qua nếu đã có", nên trên site đã
		# cài mẫu từ trước nó KHÔNG cập nhật HTML. Render thẳng mẫu trong CSDL
		# thì bộ test này kiểm bản HTML của lần cài đầu tiên chứ không kiểm mã
		# nguồn đang sửa. Đồng bộ về đúng hằng số trước mọi khẳng định.
		frappe.db.set_value(
			"Print Format", NAME_PHIEU_XUAT_02VT, "html", HTML_PHIEU_XUAT_02VT,
			update_modified=False,
		)
		if not frappe.db.exists("Customer", self.KHACH):
			frappe.get_doc({
				"doctype": "Customer", "customer_name": self.KHACH,
				"customer_type": "Company", "customer_group": "All Customer Groups",
				"territory": "All Territories",
			}).insert(ignore_permissions=True)

	# ------------------------------------------------------------- dựng phiếu
	def _don_va_phieu(self, sl_yeu_cau, sl_giao):
		"""Đơn hàng ĐÃ GHI SỔ `sl_yeu_cau` → phiếu giao NHÁP giao `sl_giao`.

		Giao thiếu, hoặc giao làm nhiều đợt, là chuyện thường ở đây — và đó
		đúng là ca mà cột "SL yêu cầu" sinh ra để nói. Một fixture giao ĐỦ sẽ
		xanh với cả mẫu in chép số lượng thực xuất sang cột yêu cầu, tức là
		không canh gì.
		"""
		so = frappe.new_doc("Sales Order")
		so.customer = self.KHACH
		so.company = self.COMPANY
		so.transaction_date = frappe.utils.today()
		so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 3)
		so.append("items", {
			"item_code": self.ITEM, "qty": sl_yeu_cau, "rate": 88000,
			"warehouse": self.KHO, "delivery_date": so.delivery_date,
			"cost_center": self.COST_CENTER,
		})
		so.insert(ignore_permissions=True)
		so.submit()
		dn = make_delivery_note(so.name)
		dn.items[0].qty = sl_giao
		# NHÁP: bản in không phụ thuộc `docstatus`, còn submit thì đòi tồn kho
		# thật và kéo theo hook kho khách — hai thứ không liên quan gì tới mẫu
		# in, nhưng đủ sức làm bộ test này đỏ vì lý do khác.
		dn.insert(ignore_permissions=True)
		return so, dn

	def _don_va_phieu_nhieu_dong(self, dong):
		"""`dong`: danh sách (mã vật tư, SL đặt, SL giao trên phiếu này."""
		so = frappe.new_doc("Sales Order")
		so.customer = self.KHACH
		so.company = self.COMPANY
		so.transaction_date = frappe.utils.today()
		so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 3)
		for ma, yc, _giao in dong:
			so.append("items", {
				"item_code": ma, "qty": yc, "rate": 88000,
				"warehouse": self.KHO, "delivery_date": so.delivery_date,
				"cost_center": self.COST_CENTER,
			})
		so.insert(ignore_permissions=True)
		so.submit()
		dn = make_delivery_note(so.name)
		for row, (_ma, _yc, giao) in zip(dn.items, dong):
			row.qty = giao
		dn.insert(ignore_permissions=True)
		return so, dn

	def _phieu_khong_don(self, qty=7):
		"""Phiếu giao THẲNG — không có đơn hàng nào đứng sau (`so_detail` rỗng).

		Có thật trong nghiệp vụ: hàng đổi/hàng bù giao thẳng, ERP không hề biết
		một "số lượng yêu cầu" nào cho dòng đó.
		"""
		dn = frappe.new_doc("Delivery Note")
		dn.company = self.COMPANY
		dn.customer = self.KHACH
		dn.posting_date = frappe.utils.today()
		dn.posting_time = frappe.utils.nowtime()
		dn.set_posting_time = 1
		dn.append("items", {
			"item_code": self.ITEM, "qty": qty, "rate": 88000,
			"warehouse": self.KHO, "cost_center": self.COST_CENTER,
		})
		dn.insert(ignore_permissions=True)
		return dn

	def _vat_tu_co_lo(self):
		"""Vật tư quản theo lô + hai lô hạn dùng khác nhau + tồn kho thật."""
		if not frappe.db.exists("Item", self.ITEM_LO):
			frappe.get_doc({
				"doctype": "Item", "item_code": self.ITEM_LO,
				"item_name": "Vật tư test mẫu in theo lô",
				"item_group": frappe.get_all(
					"Item Group", filters={"is_group": 0}, pluck="name"
				)[0],
				"stock_uom": "Hộp", "is_stock_item": 1,
				"has_batch_no": 1, "create_new_batch": 0,
			}).insert(ignore_permissions=True)
		for lo, han in ((self.LO_A, self.HAN_A), (self.LO_B, self.HAN_B)):
			if not frappe.db.exists("Batch", lo):
				frappe.get_doc({
					"doctype": "Batch", "batch_id": lo,
					"item": self.ITEM_LO, "expiry_date": han,
				}).insert(ignore_permissions=True)
			make_stock_entry(
				item_code=self.ITEM_LO, qty=50, to_warehouse=self.KHO, rate=1000,
				batch_no=lo, company=self.COMPANY, purpose="Material Receipt",
			)

	def _bundle(self, batches, qty):
		from erpnext.stock.doctype.serial_and_batch_bundle.test_serial_and_batch_bundle import (
			make_serial_batch_bundle,
		)

		return make_serial_batch_bundle({
			"item_code": self.ITEM_LO, "warehouse": self.KHO, "qty": qty,
			"batches": frappe._dict(batches), "voucher_type": "Delivery Note",
			"posting_date": frappe.utils.today(), "posting_time": frappe.utils.nowtime(),
			"type_of_transaction": "Outward", "company": self.COMPANY,
			"do_not_submit": True,
		}).name

	def _render(self, doc):
		return get_html_and_style(
			doc=doc.as_json(), print_format=NAME_PHIEU_XUAT_02VT
		)["html"]

	# --------------------------------------------------------------- cấu trúc
	def test_dung_cau_truc_mau_02_vt(self):
		h = self._render(self._don_va_phieu(50, 20)[1])
		for phai_co in (
			"Mẫu số: 02 - VT",
			"Kèm theo Thông tư số 99/2025/TT-BTC",
			"ngày 27 tháng 10 năm 2025",
			"PHIẾU XUẤT KHO KIÊM BIÊN BẢN BÀN GIAO",
			"Số đơn hàng (SO/PO)", "Ngày, giờ bàn giao",
			"Số lô", "Hạn dùng", "SL thực xuất",
			"Tổng số tiền (viết bằng chữ)",
			"Hai bên đã kiểm tra và xác nhận",
			# Khối ký của bản mẫu: ĐÚNG bốn ô.
			"Người lập phiếu", "Thủ kho", "Người giao hàng", "Người nhận hàng",
			"info@miyano.com.vn",
		):
			self.assertIn(phai_co, h, f"mẫu 02-VT thiếu «{phai_co}»")

	def test_khong_con_dau_vet_ban_TT200(self):
		"""Vế ÂM. Không có bài này, một bản vá "thêm dòng TT 99/2025" mà quên
		gỡ dòng cũ vẫn xanh — và chứng từ in ra trích hai thông tư."""
		h = self._render(self._don_va_phieu(50, 20)[1])
		for khong_duoc_con in (
			"200/2014", "22/12/2014",
			# Bản mẫu bỏ hai ô ký này; giữ lại là bắt bệnh viện ký một biên
			# bản có ô trống mà không ai được phép ký vào.
			"Kế toán trưởng", "Giám đốc",
		):
			self.assertNotIn(khong_duoc_con, h, f"còn sót bản cũ: «{khong_duoc_con}»")

	def test_in_ra_DU_LIEU_THAT_cua_phieu(self):
		"""Răng cho bài cấu trúc: mọi khẳng định `assertIn` ở trên vẫn xanh
		khi từng ô dữ liệu TRỐNG. Bài này ghim đúng số liệu của phiếu."""
		so, dn = self._don_va_phieu(50, 20)
		h = self._render(dn)
		self.assertIn(dn.name, h, "thiếu Mã phiếu")
		self.assertIn(self.KHACH, h, "thiếu tên khách")
		self.assertIn(so.name, h, "thiếu Số đơn hàng (SO/PO)")
		for i in dn.items:
			self.assertIn(i.item_code, h, f"thiếu mã vật tư {i.item_code}")

	# ----------------------------------------------------- SL yêu cầu (P43)
	def test_cot_SL_yeu_cau_lay_tu_DON_HANG_khong_lap_lai_SL_thuc_xuat(self):
		"""**Ruling P43.** Cột "SL yêu cầu" phải lấy từ ĐƠN HÀNG
		(`Delivery Note Item.so_detail` → `Sales Order Item.qty`), không phải
		chép lại chính `i.qty` của dòng phiếu.

		Vì sao đây là lỗi pháp lý chứ không phải chuyện hiển thị: ngay dưới
		bảng này là đoạn cam kết *"hàng hóa được bàn giao đầy đủ về số lượng"*
		mà khách ĐẶT BÚT KÝ. Hai cột bằng nhau nghĩa là tờ giấy khai "yêu cầu
		20, giao 20 — đầy đủ" cho một đơn đặt 50. Giao thiếu/giao nhiều đợt là
		chuyện thường ở đây, nên đây không phải ca hiếm.

		Đã chứng minh trên dữ liệu thật: `MAT-DN-2026-00003` (đã ghi sổ) có đơn
		50 / giao 20 và in ra hai ô cùng là 20.
		"""
		so, dn = self._don_va_phieu(sl_yeu_cau=50, sl_giao=20)
		o = _o_cua_dong(self._render(dn))
		self.assertEqual(o[O_SL_THUC_XUAT], "20", "cột SL thực xuất sai")
		self.assertEqual(
			o[O_SL_YEU_CAU], "50",
			"cột SL yêu cầu không lấy từ đơn hàng — biên bản có chữ ký khai "
			f"khống số lượng đã đặt (các ô: {o})",
		)

	def test_khong_co_don_hang_thi_o_SL_yeu_cau_de_TRONG(self):
		"""Ruling P43, vế còn lại: phiếu giao THẲNG không có `so_detail` thì
		ERP thật sự KHÔNG biết một số lượng yêu cầu nào. Ô để TRỐNG — nhân
		viên điền tay như các ô không thể biết khác (ngày giờ bàn giao, nhiệt
		độ, Nợ/Có). Lui về `i.qty` chính là lỗi đang sửa, chỉ đổi chỗ."""
		dn = self._phieu_khong_don(qty=7)
		o = _o_cua_dong(self._render(dn))
		self.assertEqual(o[O_SL_THUC_XUAT], "7", "cột SL thực xuất sai")
		self.assertEqual(
			o[O_SL_YEU_CAU], "",
			"phiếu không có đơn hàng mà cột SL yêu cầu vẫn in ra một con số — "
			f"bịa số liệu trên chứng từ có chữ ký (các ô: {o})",
		)

	# ------------------------------------------------- đoạn cam kết (P47)
	def test_giao_DU_thi_giu_NGUYEN_cau_cam_ket_cua_ban_mau(self):
		"""Ruling P47, vế dương. Giao đủ thì câu gốc của docx đúng — và phải
		giữ nguyên từng chữ, vì mọi chữ trong một đoạn cam kết có chữ ký đều
		là chữ của bản mẫu chứ không phải của người viết mã."""
		_so, dn = self._don_va_phieu(sl_yeu_cau=10, sl_giao=10)
		cam_ket = _doan_cam_ket(self._render(dn))
		self.assertIn(
			CAU_GIAO_DU, cam_ket, "giao đủ mà không dùng câu gốc của bản mẫu"
		)
		self.assertNotIn(CAU_GIAO_THIEU, cam_ket)

	def test_giao_THIEU_thi_KHONG_duoc_khang_dinh_day_du(self):
		"""Ruling P47, ca gây hại thật — dựng lại đúng `MAT-DN-2026-00033`:
		đơn `SAL-ORD-2026-00132` đặt 10, giao làm năm đợt, tờ phiếu in
		`10 | 1` NGAY TRÊN câu "hàng hóa được bàn giao đầy đủ về số lượng".
		Khách đặt bút ký vào một câu sai với chính con số phía trên nó.
		"""
		_so, dn = self._don_va_phieu(sl_yeu_cau=10, sl_giao=1)
		o = _o_cua_dong(self._render(dn))
		self.assertEqual([o[O_SL_YEU_CAU], o[O_SL_THUC_XUAT]], ["10", "1"])
		cam_ket = _doan_cam_ket(self._render(dn))
		self.assertIn(
			CAU_GIAO_THIEU, cam_ket, "giao thiếu mà không đổi câu cam kết"
		)
		self.assertNotIn(
			"đầy đủ", cam_ket,
			"phiếu giao 1 trên đơn đặt 10 vẫn khẳng định 'đầy đủ' — khách ký "
			"vào một câu sai với con số ngay phía trên",
		)

	def test_MOT_dong_thieu_thi_CA_PHIEU_dung_cau_thay_the(self):
		"""Câu cam kết nằm CUỐI phiếu nên nó nói về CẢ PHIẾU, không nói về một
		dòng. Một dòng thiếu là cả tờ giấy không được khẳng định "đầy đủ"."""
		_so, dn = self._don_va_phieu_nhieu_dong([
			(self.ITEM, 5, 5),        # dòng ĐỦ
			(self.ITEM_2, 10, 2),     # dòng THIẾU
		])
		cam_ket = _doan_cam_ket(self._render(dn))
		self.assertIn(CAU_GIAO_THIEU, cam_ket)
		self.assertNotIn("đầy đủ", cam_ket)

	def test_dong_KHONG_co_don_hang_khong_bi_coi_la_giao_thieu(self):
		"""Không có `so_detail` thì KHÔNG có gì để so — im lặng coi là thiếu
		sẽ đổi câu cam kết trên mọi phiếu giao thẳng, tức bỏ câu gốc của bản
		mẫu ở đúng những ca mà nó vẫn đúng."""
		cam_ket = _doan_cam_ket(self._render(self._phieu_khong_don(qty=7)))
		self.assertIn(CAU_GIAO_DU, cam_ket)
		self.assertNotIn(CAU_GIAO_THIEU, cam_ket)

	def test_phieu_TRA_HANG_khong_khang_dinh_day_du(self):
		"""Phiếu trả hàng: số lượng ÂM, hàng đi ngược về Miyano. Phép so
		"đủ/thiếu" với số lượng đã đặt là vô nghĩa ở đây, nên `giao_du_theo_don`
		chặn ngay từ đầu và cả phiếu dùng câu thay thế — câu đó đúng với mọi
		dấu, còn "bàn giao đầy đủ" thì không có nghĩa gì trên một tờ trả hàng.
		"""
		_so, dn = self._don_va_phieu(sl_yeu_cau=10, sl_giao=10)
		phieu = frappe.copy_doc(dn)
		phieu.is_return = 1
		for r in phieu.items:
			r.qty = -r.qty
		h = self._render(phieu)
		self.assertIn("PHIẾU TRẢ HÀNG", h, "tiền đề: nhãn phiếu trả hàng")
		cam_ket = _doan_cam_ket(h)
		self.assertIn(CAU_GIAO_THIEU, cam_ket)
		self.assertNotIn("đầy đủ", cam_ket)

	# --------------------------------------------------------- lô và hạn dùng
	def test_cot_so_lo_han_dung_doc_QUA_BUNDLE_khi_batch_no_RONG(self):
		"""Hai cột mới của bản TT 99/2025, ĐÚNG cái bẫy chúng sinh ra để chặn.

		Quy tắc đọc lô của build này là **bundle TRƯỚC, `batch_no` sau**: v15
		bật `Stock Settings.use_serial_batch_fields`, và
		`make_bundle_using_old_serial_batch_fields()` chạy trong
		`DeliveryNote.on_submit`. Một dòng TÁCH NHIỀU LÔ thì `batch_no` RỖNG và
		chỉ bundle mới kể được — nên một mẫu tự viết `{{ i.batch_no }}` in ô
		TRỐNG, im lặng, trên biên bản dược phẩm có chữ ký hai bên.

		Bản test trước dựng dòng CÓ `batch_no` và KHÔNG có bundle, tức đi đúng
		nhánh dự phòng: `{{ i.batch_no }}` cũng thoả khẳng định đó. Bài này
		dựng bundle THẬT hai lô và để `batch_no` rỗng — chỉ đường bundle mới
		qua được. Hai lô chứ không một: một lô thì một mẫu sai vẫn có thể trúng
		nhờ may.

		Phiếu để NHÁP có chủ đích: submit sẽ khiến ERPNext tự dựng lại bundle
		từ `batch_no`, xoá mất chính điều kiện đang dựng.
		"""
		self._vat_tu_co_lo()
		bundle = self._bundle({self.LO_A: -3, self.LO_B: -2}, qty=-5)
		dn = frappe.new_doc("Delivery Note")
		dn.company = self.COMPANY
		dn.customer = self.KHACH
		dn.posting_date = frappe.utils.today()
		dn.posting_time = frappe.utils.nowtime()
		dn.set_posting_time = 1
		dn.append("items", {
			"item_code": self.ITEM_LO, "qty": 5, "rate": 12000,
			"warehouse": self.KHO, "cost_center": self.COST_CENTER,
			"serial_and_batch_bundle": bundle,
		})
		# Tiền đề của bài: dòng này KHÔNG có `batch_no`. Nếu fixture lỡ điền
		# nó, bài test tự biến thành bài cũ và không canh gì nữa.
		self.assertFalse(
			dn.items[0].get("batch_no"),
			"fixture đã tự điền batch_no — bẫy đang kiểm biến mất",
		)

		o = _o_cua_dong(self._render(dn))
		self.assertEqual(
			o[O_SO_LO], f"{self.LO_A}, {self.LO_B}",
			f"cột Số lô không đọc qua bundle (các ô: {o})",
		)
		self.assertEqual(
			o[O_HAN_DUNG],
			"{}, {}".format(
				frappe.utils.formatdate(self.HAN_A, "dd/MM/yyyy"),
				frappe.utils.formatdate(self.HAN_B, "dd/MM/yyyy"),
			),
			f"cột Hạn dùng không đọc qua bundle (các ô: {o})",
		)

	def test_khong_in_sentinel_KHONG_LO_len_chung_tu(self):
		"""`LOT_KHONG_CO` ("KHONG-LO") là quy ước NỘI BỘ của sổ kho cho hàng
		không quản theo lô. Nó lọt lên một chứng từ pháp lý là một chuỗi vô
		nghĩa với bệnh viện — và không ai đọc lại bản in để phát hiện."""
		h = self._render(self._phieu_khong_don())
		self.assertNotIn("KHONG-LO", h)

	def test_tien_bang_chu_la_TIENG_VIET(self):
		"""frappe.utils.money_in_words đọc theo ngôn ngữ hệ thống — site để
		tiếng Anh nên từng in ra "Nine Hundred And Fifty Thousand" trên một
		chứng từ kế toán Việt Nam."""
		h = self._render(self._don_va_phieu(50, 20)[1])
		self.assertIn("đồng.", h)
		for tieng_anh in ("Thousand", "Hundred", "Million", "only."):
			self.assertNotIn(tieng_anh, h, f"còn sót tiếng Anh: {tieng_anh}")


class TestTienBangChu(FrappeTestCase):
	"""Cách đọc số tiếng Việt có bốn chỗ bẫy mà một vòng lặp ngây thơ sẽ sai:
	mốt/tư/lăm ở hàng đơn vị, và "linh" khi hàng chục bằng 0."""

	def test_cac_truong_hop_dac_biet(self):
		for so, mong in (
			(0, "Không đồng."),
			(15, "Mười lăm đồng."),
			(21, "Hai mươi mốt đồng."),
			(24, "Hai mươi tư đồng."),
			(25, "Hai mươi lăm đồng."),
			(105, "Một trăm linh năm đồng."),
			(1000, "Một nghìn đồng."),
			(1105, "Một nghìn một trăm linh năm đồng."),
			(1000005, "Một triệu không trăm linh năm đồng."),
			(1005000, "Một triệu không trăm linh năm nghìn đồng."),
			(28500000, "Hai mươi tám triệu năm trăm nghìn đồng."),
		):
			with self.subTest(so=so):
				self.assertEqual(tien_bang_chu(so), mong)

	def test_lam_tron_va_gia_tri_la(self):
		# VND không có phần lẻ trên chứng từ — làm tròn, không đọc "phẩy".
		self.assertEqual(tien_bang_chu(1000.4), "Một nghìn đồng.")
		self.assertEqual(tien_bang_chu(None), "Không đồng.")
		self.assertEqual(tien_bang_chu("x"), "")


class TestPatchCapNhat02VTDeLaiDauVet(FrappeTestCase):
	"""Patch v1_28 ghi đè HTML của một mẫu in đang chạy thật — phải để lại dấu.

	Bản trước ghi đè VÔ ĐIỀU KIỆN, không so sánh, kèm `update_modified=False`.
	Đã đo trên `erptest.local`: `tabPatch Log` ghi patch chạy 25/08 12:14 trong
	khi `Print Format.modified` vẫn là 16/08 — người vận hành lẫn kiểm toán
	viên không có cách nào nhìn ra mẫu đã bị thay.

	Vì sao đáng kể: site chạy thật (`miyano`) CHƯA chạy patch này. Nếu ở đó
	mẫu in từng được sửa tay (logo, số tài khoản, mẫu tiêu đề thư), patch sẽ
	xoá bản sửa ấy trong im lặng. Không thể giữ lại bản sửa tay đó — mẫu phải
	hội tụ về mã nguồn — nhưng phải NÓI RA là đã thay cái gì.
	"""

	HTML_SUA_TAY = "<p>bản mẫu một site đã sửa tay</p>"

	def setUp(self):
		install_bien_ban_print_formats()
		self.addCleanup(
			frappe.db.set_value, "Print Format", NAME_PHIEU_XUAT_02VT, "html",
			HTML_PHIEU_XUAT_02VT,
		)
		# `tabError Log` khai engine MyISAM — bảng PHI GIAO DỊCH, nên MỌI phép
		# xoá ở đây KHÔNG bị rollback cuối class cuốn lại. Vì thế bài test chỉ
		# được dọn ĐÚNG những dòng do CHÍNH NÓ sinh ra: xoá theo `method` sẽ
		# cuốn theo cả biên nhận thật do `bench migrate` ghi — chính bản ghi
		# kiểm toán mà patch này dựng ra. Ghi lại danh sách có sẵn TRƯỚC.
		self._log_co_san = set(self._ten_log_hien_co())
		self.addCleanup(self._don_log_cua_bai_nay)

	def _ten_log_hien_co(self):
		return frappe.get_all("Error Log", filters={"method": TIEU_DE_LOG}, pluck="name")

	def _don_log_cua_bai_nay(self):
		for ten in self._ten_log_hien_co():
			if ten not in self._log_co_san:
				frappe.db.delete("Error Log", {"name": ten})

	def _log_moi(self):
		"""Chỉ những dòng log SINH RA trong bài này."""
		return [
			r for r in frappe.get_all(
				"Error Log", filters={"method": TIEU_DE_LOG}, fields=["name", "error"]
			)
			if r.name not in self._log_co_san
		]

	def test_ghi_de_de_lai_do_dai_va_hash_cua_ban_bi_thay(self):
		frappe.db.set_value(
			"Print Format", NAME_PHIEU_XUAT_02VT,
			{"html": self.HTML_SUA_TAY, "modified": "2020-01-01 00:00:00"},
			update_modified=False,
		)
		with contextlib.redirect_stdout(io.StringIO()) as ra:
			cap_nhat_02vt()
		in_ra = ra.getvalue()

		self.assertEqual(
			frappe.db.get_value("Print Format", NAME_PHIEU_XUAT_02VT, "html"),
			HTML_PHIEU_XUAT_02VT,
			"patch không đưa mẫu về đúng mã nguồn",
		)
		# Người chạy `bench migrate` phải THẤY chuyện này ngay trên màn hình —
		# một dòng Error Log chỉ tìm được khi đã biết mà đi tìm.
		self.assertIn(
			NAME_PHIEU_XUAT_02VT, in_ra,
			"bench migrate ghi đè một mẫu in mà không in ra tín hiệu nào",
		)
		log = self._log_moi()
		self.assertEqual(
			len(log), 1,
			"ghi đè một mẫu in đang chạy thật mà không để lại dấu vết nào",
		)
		self.assertIn(
			str(len(self.HTML_SUA_TAY)), log[0].error,
			"dấu vết không nói được độ dài bản bị thay",
		)
		self.assertIn(
			hashlib.sha256(self.HTML_SUA_TAY.encode("utf-8")).hexdigest(),
			log[0].error,
			"dấu vết không có hash để nhận ra bản bị thay",
		)
		# Thông điệp KHÔNG được hứa một bản sao lưu mà chưa ai xác lập là có.
		self.assertIn(
			"KHÔNG được lưu lại ở đâu", log[0].error,
			"thông điệp bảo người vận hành đối chiếu với một bản sao lưu mà "
			"không gì bảo họ chụp trước khi migrate",
		)
		self.assertNotEqual(
			str(frappe.db.get_value("Print Format", NAME_PHIEU_XUAT_02VT, "modified")),
			"2020-01-01 00:00:00",
			"`modified` đứng yên sau khi nội dung đã bị thay — đúng cái làm "
			"người vận hành không nhìn ra chuyện gì đã xảy ra",
		)

	def test_chay_lai_khi_da_dung_thi_KHONG_ghi_gi(self):
		"""Vế răng: dấu vết phải THẬT. `bench migrate` chạy lại trên site đã
		đúng nội dung thì không được sinh thêm log, cũng không được đụng vào
		`modified` — nếu không, mỗi lần migrate lại thêm một dòng "đã ghi đè"
		giả và dấu vết mất hết giá trị."""
		frappe.db.set_value(
			"Print Format", NAME_PHIEU_XUAT_02VT,
			{"html": HTML_PHIEU_XUAT_02VT, "modified": "2020-01-01 00:00:00"},
			update_modified=False,
		)
		cap_nhat_02vt()

		self.assertEqual(
			len(self._log_moi()), 0,
			"không ghi đè gì mà vẫn ghi một dòng 'đã ghi đè'",
		)
		self.assertEqual(
			str(frappe.db.get_value("Print Format", NAME_PHIEU_XUAT_02VT, "modified")),
			"2020-01-01 00:00:00",
			"nội dung không đổi mà `modified` vẫn bị dời",
		)

	def test_patches_txt_GIAO_DUOC_ban_sua_mau_02vt_toi_site(self):
		"""Blocking-1 của vòng sửa 2: sửa hằng số HTML là CHƯA giao được gì.

		Frappe chạy mỗi patch ĐÚNG MỘT LẦN (`tabPatch Log`). Site nào đã chạy
		`v1_28.cap_nhat_02vt_bien_ban_ban_giao` sẽ KHÔNG bao giờ chạy lại nó,
		nên mọi sửa đổi sau đó trong `HTML_PHIEU_XUAT_02VT` — kể cả bản vá cột
		"SL yêu cầu" — không tới được site đó bằng `bench migrate`. Site giữ
		vĩnh viễn tờ phiếu bịa số, và phục hồi từ một bản sao lưu chụp trong
		khoảng đó cũng âm thầm quay lại tờ phiếu ấy.

		Bài này không kiểm tên patch (tên nào cũng được) mà kiểm HÀNH VI: đặt
		mẫu về một bản CŨ rồi chạy lần lượt các patch khai SAU v1_28, phải có
		một patch kéo mẫu về đúng hằng số hiện tại.
		"""
		cac_patch = _doc_patches_txt()
		moc = "miyano_portal.patches.v1_28.cap_nhat_02vt_bien_ban_ban_giao"
		self.assertIn(moc, cac_patch, "patches.txt không còn khai v1_28")
		sau_v1_28 = cac_patch[cac_patch.index(moc) + 1:]

		frappe.db.set_value(
			"Print Format", NAME_PHIEU_XUAT_02VT, "html", self.HTML_SUA_TAY,
			update_modified=False,
		)
		with contextlib.redirect_stdout(io.StringIO()):
			for ten in sau_v1_28:
				importlib.import_module(ten).execute()
				if frappe.db.get_value(
					"Print Format", NAME_PHIEU_XUAT_02VT, "html"
				) == HTML_PHIEU_XUAT_02VT:
					break
		self.assertEqual(
			frappe.db.get_value("Print Format", NAME_PHIEU_XUAT_02VT, "html"),
			HTML_PHIEU_XUAT_02VT,
			"không patch nào SAU v1_28 đồng bộ lại mẫu 02-VT — bản vá không "
			"tới được site nào bằng `bench migrate`",
		)

	def test_KHONG_xoa_bien_nhan_cua_lan_migrate_TRUOC(self):
		"""Bản ghi kiểm toán không được chết dưới tay chính bộ test canh nó.

		`tabError Log` khai engine MyISAM — bảng PHI GIAO DỊCH, nên
		`frappe.db.delete` trên đó KHÔNG bị rollback cuối class cuốn lại. Bản
		trước của lớp này dọn bằng `delete("Error Log", {"method": TIEU_DE_LOG})`,
		tức cuốn theo CẢ dòng do một lần `bench migrate` THẬT ghi ra — đúng bản
		ghi mà bản vá vòng trước dựng lên để người vận hành nhìn ra mẫu in đã bị
		thay. Đã đo trên `erptest.local`: dòng biên nhận ghi lúc 14:18 biến mất
		sau lần chạy full suite ngay sau đó.

		Dựng lại đúng trình tự đó: có sẵn một biên nhận thật → bộ test chạy →
		biên nhận phải CÒN, còn dòng do bài test sinh ra thì phải đi.
		"""
		that = frappe.get_doc({
			"doctype": "Error Log", "method": TIEU_DE_LOG,
			"error": "BIEN NHAN THAT cua mot lan bench migrate truoc do",
		}).insert(ignore_permissions=True)
		self.addCleanup(frappe.db.delete, "Error Log", {"name": that.name})

		# Mô phỏng một lần chạy bộ test BẮT ĐẦU khi biên nhận đã nằm sẵn đó.
		self._log_co_san = set(self._ten_log_hien_co())
		self.assertIn(that.name, self._log_co_san, "tiền đề: biên nhận đã có sẵn")

		frappe.db.set_value(
			"Print Format", NAME_PHIEU_XUAT_02VT, "html", self.HTML_SUA_TAY,
			update_modified=False,
		)
		cap_nhat_02vt()
		cua_bai_nay = [r.name for r in self._log_moi()]
		self.assertEqual(len(cua_bai_nay), 1, "tiền đề: bài này sinh đúng 1 dòng")

		self._don_log_cua_bai_nay()

		self.assertTrue(
			frappe.db.exists("Error Log", that.name),
			"bộ test đã xoá mất biên nhận của một lần bench migrate thật",
		)
		self.assertFalse(
			frappe.db.exists("Error Log", cua_bai_nay[0]),
			"dòng do chính bài test sinh ra thì phải được dọn",
		)

	def test_mau_chua_co_thi_chi_dung_DUNG_mot_mau(self):
		"""Nhánh "site chưa từng cài". Bản trước gọi
		`install_bien_ban_print_formats()` — hàm đó dựng CẢ BA mẫu, hồi sinh cả
		mẫu mà một site có thể đã CỐ Ý gỡ. Một patch tên "cập nhật 02-VT"
		không được tự ý dựng lại hai mẫu biên bản kiểm nghiệm."""
		frappe.delete_doc(
			"Print Format", NAME_BIEN_BAN_TT200, force=True, ignore_permissions=True
		)
		frappe.delete_doc(
			"Print Format", NAME_PHIEU_XUAT_02VT, force=True, ignore_permissions=True
		)
		cap_nhat_02vt()

		self.assertEqual(
			frappe.db.get_value("Print Format", NAME_PHIEU_XUAT_02VT, "html"),
			HTML_PHIEU_XUAT_02VT,
			"patch không dựng lại mẫu 02-VT khi site chưa có",
		)
		self.assertFalse(
			frappe.db.exists("Print Format", NAME_BIEN_BAN_TT200),
			"patch hồi sinh một mẫu KHÁC mà site có thể đã cố ý gỡ bỏ",
		)


class TestTatMauIn02VTKhongTienTo(FrappeTestCase):
	"""Ruling P46 — tắt mẫu in `Phiếu xuất kho (02-VT)` (KHÔNG tiền tố Miyano).

	Site mang **ba** mẫu in cho `Delivery Note`, trong đó mẫu trần này (module
	`Regional`, `creation = modified = 16/07/2026 10:00:00` — dấu vết của một
	bản nhập tay, không do app này cài) chỉ khác mẫu của Miyano đúng tiền tố
	"Miyano - " trong cùng một dropdown "In". Bấm nhầm là in ra tờ trích
	TT 99/2025 nhưng KHÔNG có cột Số lô/Hạn dùng, không đoạn cam kết bàn giao,
	không bốn ô ký của bản mẫu.

	**Tắt, KHÔNG xoá.** Giữ bản ghi thì còn trả lời được "tờ phiếu tháng 7 đó
	in bằng mẫu nào"; xoá thì mất luôn khả năng đó.
	"""

	TEN_TRAN = "Phiếu xuất kho (02-VT)"

	def setUp(self):
		install_bien_ban_print_formats()
		if not frappe.db.exists("Print Format", self.TEN_TRAN):
			# Bộ test tự dựng mồi: trên CSDL sạch không có mẫu trần nào, và một
			# bài tự bỏ qua mình khi thiếu dữ liệu là một bài không canh gì.
			frappe.get_doc({
				"doctype": "Print Format", "name": self.TEN_TRAN,
				"doc_type": "Delivery Note", "standard": "No",
				"custom_format": 1, "print_format_type": "Jinja",
				"html": "<p>mẫu trần nhập tay 16/07</p>",
			}).insert(ignore_permissions=True)
		frappe.db.set_value("Print Format", self.TEN_TRAN, "disabled", 0)
		frappe.db.set_value("Print Format", NAME_PHIEU_XUAT_02VT, "disabled", 0)

	def test_tat_mau_tran_nhung_GIU_LAI_ban_ghi(self):
		tat_mau_tran()
		self.assertEqual(
			frappe.db.get_value("Print Format", self.TEN_TRAN, "disabled"), 1,
			"mẫu trần vẫn hiện trong dropdown In cạnh mẫu của Miyano",
		)
		self.assertTrue(
			frappe.db.exists("Print Format", self.TEN_TRAN),
			"XOÁ mẫu là mất luôn khả năng tra 'phiếu tháng 7 in bằng mẫu nào'",
		)

	def test_KHONG_dung_toi_mau_CO_tien_to_Miyano(self):
		"""Bẫy khớp mờ: tên mẫu của Miyano CHỨA nguyên văn tên mẫu trần
		("Miyano - " + "Phiếu xuất kho (02-VT)"). Một phép `like` sẽ tắt luôn
		mẫu mà cả cổng lẫn nhân viên đang dùng."""
		tat_mau_tran()
		self.assertEqual(
			frappe.db.get_value("Print Format", NAME_PHIEU_XUAT_02VT, "disabled"), 0,
			"patch tắt nhầm mẫu 02-VT của Miyano — cổng mất mẫu đang phát",
		)

	def test_chay_lai_khong_doi_gi_va_KHONG_hoi_sinh_mau_da_go(self):
		tat_mau_tran()
		tat_mau_tran()
		self.assertEqual(
			frappe.db.get_value("Print Format", self.TEN_TRAN, "disabled"), 1
		)
		frappe.delete_doc(
			"Print Format", self.TEN_TRAN, force=True, ignore_permissions=True
		)
		tat_mau_tran()  # không được ném lỗi
		self.assertFalse(
			frappe.db.exists("Print Format", self.TEN_TRAN),
			"patch dựng lại một mẫu mà site đã cố ý gỡ bỏ",
		)
