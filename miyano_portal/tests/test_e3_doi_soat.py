"""E3 phần A — giao nhiều đợt trên một đơn & đối soát giao–nhận.

Phủ TC-E3-01, 02, 03, 04, 07, 08 (`.superpowers/sdd/e3/brief-A-hook-doi-soat.md`,
xem `docs/Miyano-Portal(Client)_V2/DevHandoff/12_PRD_E3_GiaoNhieuDot_DoiSoat.md`
và `40_TestCases.md`).

RÀNG BUỘC CAO NHẤT giống `test_kho_delivery_hook.py`: hook không bao giờ được
làm hỏng Delivery Note của Miyano. Test TC-E3-08 khẳng định đúng điều đó cho
PHẦN MỞ RỘNG mới thêm ở E3 (so_dot), không lặp lại test đã có cho phần lõi.
"""

import unittest.mock

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

from miyano_portal.api import kho as kho_api
from miyano_portal.kho import delivery_hook, desk_reports, ledger
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

COMPANY = "Miyano Việt Nam"
KHO_MYN = "Kho Miyano - MYN"
COST_CENTER = "Main - MYN"
KHACH = "Bệnh viện Bạch Mai"
ITEM = "MYN-GLOVE-M"  # không có batch/hạn — đúng tiền đề của TC-E3-07

# `seed_demo()` (được `seed_kho_demo()` gọi trước) tạo user cổng này cho
# đúng Customer KHACH — dùng để gọi endpoint kho_phieu_* NHƯ THỦ KHO THẬT,
# không phải qua frappe.get_doc trực tiếp (xem test_TC_E3_03_qua_api_...).
BM_USER = "bvbm@demo.miyano"

# Cùng địa chỉ với USER_SALES của test_e1_thieu_gia_va_reorder.py: dùng
# `bao_thieu_gia`/`bao_chenh_lech` chung một khuôn "sales phụ trách" của
# Customer, nên dùng lại đúng một user demo cho gọn. Tự tạo (idempotent) thay
# vì trông cậy vào việc site đã có sẵn từ trước.
SALES_USER = "sales_user@demo.miyano"


class TestE3DoiSoat(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.kho_bm = self.kho["kho_bm"]
		# `FrappeTestCase` rollback đúng MỘT LẦN mỗi CLASS (xem docstring cùng
		# đoạn trong test_kho_delivery_hook.py) — mọi mốc phải tự đưa về
		# chuẩn ở đây, không phụ thuộc thứ tự chạy giữa các test.
		frappe.db.set_value(
			"Customer Warehouse", self.kho_bm,
			{"active": 1, "ngay_bat_dau": "2026-01-01"},
		)
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho_bm})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho_bm})
		self._nap_ton(ITEM, 500)

		if not frappe.db.exists("User", SALES_USER):
			frappe.get_doc({
				"doctype": "User", "email": SALES_USER, "first_name": "Sales E3",
				"send_welcome_email": 0,
			}).insert(ignore_permissions=True)
		frappe.db.set_value("Customer", KHACH, "account_manager", SALES_USER)
		frappe.db.delete(
			"Notification Log",
			{"subject": ["like", "Portal - Chênh lệch nhận hàng%"]},
		)

		# `tabError Log` là MyISAM (phi giao dịch) — dòng test TC-E3-08 cố ý
		# sinh ra sẽ SỐNG SÓT qua rollback cuối class, phải tự dọn.
		self.addCleanup(
			frappe.db.delete, "Error Log", {"method": ["like", "Kho khách:%"]}
		)

	def tearDown(self):
		# Test gọi endpoint cổng (frappe.set_user(BM_USER)) không được để lại
		# phiên đăng nhập đó cho test chạy SAU nó trong cùng class.
		frappe.set_user("Administrator")

	# ------------------------------------------------------------------ setup
	def _nap_ton(self, item_code, qty):
		make_stock_entry(
			item_code=item_code, qty=qty, to_warehouse=KHO_MYN, rate=1000,
			company=COMPANY, purpose="Material Receipt",
		)

	def _sales_order(self, qty=10, rate=95000):
		so = frappe.new_doc("Sales Order")
		so.customer = KHACH
		so.company = COMPANY
		so.transaction_date = frappe.utils.today()
		so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 2)
		so.append("items", {
			"item_code": ITEM, "qty": qty, "rate": rate,
			"warehouse": KHO_MYN, "delivery_date": frappe.utils.add_days(frappe.utils.today(), 2),
		})
		so.insert(ignore_permissions=True)
		so.submit()
		return so

	def _dn_moi_tu_so(self, so, qty):
		"""Tạo Delivery Note (chưa submit) từ SO với `qty` mỗi dòng — dùng
		riêng cho TC-E3-01, nơi cần thao tác trên DN thứ hai TRƯỚC KHI submit
		(sửa qty sau lần submit đầu bị chặn)."""
		dn = make_delivery_note(so.name)
		dn.posting_date = frappe.utils.today()
		dn.set_posting_time = 1
		for r in dn.items:
			r.qty = qty
			r.warehouse = KHO_MYN
			r.cost_center = COST_CENTER
		dn.insert(ignore_permissions=True)
		return dn

	def _dn_tu_so(self, so, qty):
		dn = self._dn_moi_tu_so(so, qty)
		dn.submit()
		return dn

	def _phieu_cua(self, dn_name):
		return frappe.get_all(
			"Customer Stock Receipt",
			filters={"delivery_note": dn_name, "docstatus": ["<", 2]},
			pluck="name",
		)

	def _phieu_duy_nhat(self, dn):
		names = self._phieu_cua(dn.name)
		self.assertEqual(len(names), 1, f"Kỳ vọng đúng 1 phiếu cho {dn.name}, có {names}")
		return frappe.get_doc("Customer Stock Receipt", names[0])

	# ------------------------------------------------------------------ TC-E3-01
	def test_TC_E3_01_over_delivery_allowance_zero_chan_vuot_so(self):
		"""US-E3.1/BR-O10/QĐ-2: allowance=0 đã được ghim ở patch E1 — test này
		chỉ còn xác nhận HÀNH VI, không phải chỗ ghim cấu hình (xem
		patches/v1_3/ghim_over_delivery_zero.py)."""
		so = self._sales_order(qty=10)
		dn1 = self._dn_tu_so(so, 6)
		self.assertEqual(dn1.docstatus, 1)

		dn2 = self._dn_moi_tu_so(so, 5)
		# ERPNext kiểm allowance ở `on_submit` (`update_prevdoc_status` →
		# `validate_qty`), tức là SAU KHI docstatus=1 đã được `db_update()`
		# ghi vào transaction hiện tại — một request HTTP thật sẽ rollback
		# toàn bộ transaction đó khi exception thoát ra khỏi request handler,
		# nhưng trong test (cùng một kết nối DB, không tự rollback theo từng
		# lệnh) trạng thái nửa vời đó vẫn NẰM Ở ĐÓ nếu không tự dọn. Tự mô
		# phỏng đúng ranh giới rollback của một request thật bằng savepoint.
		diem_luu = "tc_e3_01_dn2_bi_chan"
		frappe.db.savepoint(diem_luu)
		try:
			dn2.submit()
			self.fail("DN2 = 5 phải bị ERPNext chặn (6 + 5 = 11 > 10, allowance = 0)")
		except frappe.ValidationError:
			frappe.db.rollback(save_point=diem_luu)

		dn2 = frappe.get_doc("Delivery Note", dn2.name)
		self.assertEqual(dn2.docstatus, 0, "DN2 bị chặn phải còn ở trạng thái nháp")

		for r in dn2.items:
			r.qty = 4
		dn2.save(ignore_permissions=True)
		dn2.submit()
		self.assertEqual(dn2.docstatus, 1, "6 + 4 = 10, đúng bằng số đặt — phải submit được")

	# ------------------------------------------------------------------ TC-E3-02
	def test_TC_E3_02_ba_dot_lien_tiep_so_dot_dung_khong_trung_phieu(self):
		"""US-E3.2/BR-K16: DN thứ n đã ghi sổ của cùng SO → so_dot = n."""
		so = self._sales_order(qty=9)
		dn1 = self._dn_tu_so(so, 3)
		dn2 = self._dn_tu_so(so, 3)
		dn3 = self._dn_tu_so(so, 3)

		p1 = self._phieu_duy_nhat(dn1)
		p2 = self._phieu_duy_nhat(dn2)
		p3 = self._phieu_duy_nhat(dn3)

		self.assertEqual(p1.so_dot, 1)
		self.assertEqual(p2.so_dot, 2)
		self.assertEqual(p3.so_dot, 3)

		for p in (p1, p2, p3):
			self.assertEqual(len(p.items), 1)
			self.assertEqual(p.items[0].sl_giao, 3, f"{p.name}: sl_giao phải đúng SL trên dòng DN")
			self.assertEqual(
				p.items[0].so_luong, p.items[0].sl_giao,
				f"{p.name}: so_luong (thực nhận) phải mặc định bằng sl_giao",
			)

		# Không sinh trùng phiếu cho một trong ba DN (BR-K11, đã có ở phần
		# lõi — kiểm lại ở đây vì đường đi qua Sales Order là đường mới của
		# chính test này, không chỉ test lại _phieu_duy_nhat của test khác).
		self.assertEqual(len(self._phieu_cua(dn1.name)), 1)
		self.assertEqual(len(self._phieu_cua(dn2.name)), 1)
		self.assertEqual(len(self._phieu_cua(dn3.name)), 1)

	# ---------------------------------------------------------------------- I1
	def test_I1_so_dot_theo_thu_tu_ghi_so_khong_theo_thu_tu_soan(self):
		"""I1 (E3 phần B review): `so_dot` phải theo THỨ TỰ GHI SỔ (submit),
		không phải thứ tự soạn nháp (creation). Bug cũ sắp theo `creation` rồi
		lấy `index` — DN soạn TRƯỚC nhưng ghi sổ SAU vẫn đứng đầu danh sách
		sắp theo creation, nên nhận lại so_dot=1 y hệt DN ghi sổ trước nó:
		hai phiếu cùng SO đều mang so_dot=1, không phiếu nào mang 2. Phiên bản
		đã sửa đếm SỐ DN docstatus=1 tại đúng thời điểm hook chạy (dn hiện tại
		đã docstatus=1 trong DB lúc này) — con số đó CHÍNH LÀ thứ tự ghi sổ,
		không cần sắp theo cột nào nữa."""
		so = self._sales_order(qty=20)
		dn_a = self._dn_moi_tu_so(so, 12)  # soạn TRƯỚC (chưa submit)
		dn_b = self._dn_tu_so(so, 8)       # soạn SAU nhưng ghi sổ TRƯỚC
		dn_a.submit()                       # ghi sổ SAU CÙNG

		phieu_b = self._phieu_duy_nhat(dn_b)
		phieu_a = self._phieu_duy_nhat(dn_a)

		self.assertEqual(phieu_b.so_dot, 1, "DN-B ghi sổ trước phải mang đợt 1")
		self.assertEqual(
			phieu_a.so_dot, 2,
			"DN-A ghi sổ sau phải mang đợt 2 — không được trùng đợt 1 dù soạn trước",
		)

	# ------------------------------------------------------------------ TC-E3-03
	def test_TC_E3_03_chenh_lech_khong_ly_do_bi_chan_co_ly_do_thi_ghi_so_duoc(self):
		"""US-E3.3/BR-K17/NL-3.3."""
		so = self._sales_order(qty=50)
		dn = self._dn_tu_so(so, 50)
		phieu = self._phieu_duy_nhat(dn)
		vat_tu = phieu.items[0].vat_tu
		so_lo = phieu.items[0].so_lo
		self.assertEqual(phieu.items[0].sl_giao, 50)

		phieu.items[0].so_luong = 48
		with self.assertRaises(frappe.ValidationError) as ctx:
			phieu.save(ignore_permissions=True)
		# Nguyên văn NL-3.3 / FormSpec §Ma trận lỗi.
		self.assertIn(
			"thực nhận 48 / giao 50. Nhập lý do chênh lệch để tiếp tục.",
			str(ctx.exception),
		)

		phieu.reload()
		self.assertEqual(
			phieu.items[0].so_luong, 50,
			"save() thất bại không được để lại so_luong nửa vời trên DB",
		)

		phieu.items[0].so_luong = 48
		phieu.items[0].ly_do_chenh_lech = "vỡ 2 hộp"
		phieu.save(ignore_permissions=True)
		phieu.submit()

		self.assertEqual(phieu.co_chenh_lech, 1)
		bal = ledger.get_lot_balance(self.kho_bm, vat_tu, so_lo)
		self.assertEqual(
			bal["so_luong"], 48, "sổ kho phải ghi ĐÚNG thực nhận (48), không phải sl_giao (50)"
		)

		self.assertTrue(
			frappe.db.exists("Notification Log", {
				"for_user": SALES_USER,
				"subject": ["like", f"%Chênh lệch nhận hàng%{phieu.name}%"],
			}),
			"sales phụ trách phải nhận thông báo chênh lệch",
		)

	# --------------------------------------------------------- BR-K17 qua API
	def test_TC_E3_03_qua_api_khong_lam_mat_sl_giao_khi_sua(self):
		"""Đường THẬT của thủ kho là `kho_phieu_nhap_save` (portal), không phải
		`frappe.get_doc` trực tiếp như test ở trên — role Customer không còn
		DocPerm nào trên doctype này (xem đầu `api/kho.py`), nên đây là CỔNG
		DUY NHẤT khách chạm được vào phiếu nháp do hook sinh ra.

		Endpoint đó XOÁ SẠCH bảng dòng cũ rồi dựng lại hoàn toàn từ payload
		(`doc.set("items", []); ... doc.append(...)`), và payload của client
		— đúng như `PhieuNhapDetail.vue::payload()` — KHÔNG hề gửi `sl_giao`
		(field đó là read-only, client thậm chí không biết nó tồn tại). Nếu
		endpoint không tự khôi phục lại `sl_giao`/`thieu_lo_han` cho dòng đã
		có từ trước, mốc đối soát biến mất ngay lần lưu đầu tiên và chốt chặn
		BR-K17 (`if not sl_giao: continue`) sẽ ÂM THẦM bỏ qua kiểm tra thay vì
		chặn đúng lúc cần — bài test này bắt đúng lỗi đó."""
		so = self._sales_order(qty=50)
		dn = self._dn_tu_so(so, 50)
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(phieu.items[0].sl_giao, 50)
		han = phieu.items[0].han_su_dung

		def _payload(so_luong, ly_do=None):
			row = {
				# C2 (E3 phần B review): server khớp mốc đối soát theo `name`
				# của dòng con, không còn theo giá trị (vat_tu, so_lo) — gửi
				# đúng như PhieuNhapDetail.vue::payload() làm (đọc `r.name` từ
				# lần load trước), nếu không server sẽ hiểu đây là dòng MỚI
				# (không có mốc) và, từ C1, coi dòng cũ như bị XOÁ.
				"name": phieu.items[0].name,
				"vat_tu": phieu.items[0].vat_tu,
				"so_lo": phieu.items[0].so_lo,
				"han_su_dung": str(han) if han else None,
				"so_luong": so_luong,
				"don_gia": phieu.items[0].don_gia,
				"ghi_chu": phieu.items[0].ghi_chu,
			}
			if ly_do is not None:
				row["ly_do_chenh_lech"] = ly_do
			return {
				"name": phieu.name,
				"ngay": str(phieu.ngay),
				"loai_nhap": phieu.loai_nhap,
				"nguoi_giao": phieu.nguoi_giao,
				"chung_tu_kem": phieu.chung_tu_kem,
				"dien_giai": phieu.dien_giai,
				"items": [row],
			}

		frappe.set_user(BM_USER)

		with self.assertRaises(frappe.ValidationError) as ctx:
			kho_api.kho_phieu_nhap_save(_payload(48))
		self.assertIn(
			"thực nhận 48 / giao 50. Nhập lý do chênh lệch để tiếp tục.",
			str(ctx.exception),
		)

		out = kho_api.kho_phieu_nhap_save(_payload(48, ly_do="vỡ 2 hộp"))
		self.assertEqual(out["items"][0]["so_luong"], 48)

		lai = frappe.get_doc("Customer Stock Receipt", phieu.name)
		self.assertEqual(
			lai.items[0].sl_giao, 50,
			"sl_giao phải SỐNG SÓT qua kho_phieu_nhap_save dù client không gửi lại nó",
		)
		self.assertEqual(lai.items[0].thieu_lo_han, phieu.items[0].thieu_lo_han)

		kho_api.kho_phieu_submit("Customer Stock Receipt", phieu.name)
		self.assertEqual(
			frappe.db.get_value("Customer Stock Receipt", phieu.name, "co_chenh_lech"), 1
		)
		bal = ledger.get_lot_balance(self.kho_bm, phieu.items[0].vat_tu, phieu.items[0].so_lo)
		self.assertEqual(bal["so_luong"], 48)

	# ---------------------------------------------------------------------- C1
	def _payload_don_dong(self, phieu, **overrides):
		row = {
			"name": phieu.items[0].name,
			"vat_tu": phieu.items[0].vat_tu,
			"so_lo": phieu.items[0].so_lo,
			"han_su_dung": str(phieu.items[0].han_su_dung) if phieu.items[0].han_su_dung else None,
			"so_luong": phieu.items[0].so_luong,
			"don_gia": phieu.items[0].don_gia,
			"ghi_chu": phieu.items[0].ghi_chu,
		}
		row.update(overrides)
		return {
			"name": phieu.name,
			"ngay": str(phieu.ngay), "loai_nhap": phieu.loai_nhap,
			"nguoi_giao": phieu.nguoi_giao, "chung_tu_kem": phieu.chung_tu_kem,
			"dien_giai": phieu.dien_giai,
			"items": [row],
		}

	def test_C1_xoa_dong_hook_sinh_bi_chan(self):
		"""C1 (E3 phần B review): trước bản này, DN giao VT-A 50 + VT-B 30,
		VT-B mất trên đường → `_check_so_luong` chặn cứng so_luong<=0 nên
		thủ kho KHÔNG CÒN CÁCH NÀO khác ngoài bấm ✕ xoá dòng VT-B để lưu
		được — lưu OK, ghi sổ OK, `co_chenh_lech=0`, không notification,
		report UC-48 không bao giờ thấy 30 đơn vị mất. Payload đánh rơi một
		dòng có `sl_giao > 0` (không còn `name` của nó) giờ phải bị CHẶN."""
		so = self._sales_order(qty=50)
		dn = self._dn_tu_so(so, 50)
		phieu = self._phieu_duy_nhat(dn)

		# Dòng "khác" hoàn toàn (name khác/không có) thay cho dòng hook sinh —
		# đúng hình dạng payload khi thủ kho bấm ✕ rồi (có thể) thêm dòng khác.
		payload = self._payload_don_dong(phieu)
		payload["items"] = [{
			"vat_tu": phieu.items[0].vat_tu, "so_lo": "LO-KHAC",
			"han_su_dung": None, "so_luong": 5,
			"don_gia": phieu.items[0].don_gia, "ghi_chu": "",
		}]

		frappe.set_user(BM_USER)
		with self.assertRaises(frappe.ValidationError) as ctx:
			kho_api.kho_phieu_nhap_save(payload)
		self.assertIn("không được xoá dòng do phiếu giao hàng sinh ra", str(ctx.exception))

		lai = frappe.get_doc("Customer Stock Receipt", phieu.name)
		self.assertEqual(len(lai.items), 1, "lưu thất bại không được để lại dữ liệu nửa vời")
		self.assertEqual(lai.items[0].so_luong, 50)

	def test_C1_nhan_0_di_qua_duong_bao_chenh_lech_khong_phai_xoa_dong(self):
		"""Hàng mất/thiếu HOÀN TOÀN giờ ghi được `so_luong=0` kèm lý do — thủ
		kho không còn phải xoá cả dòng để lưu được nữa. Notification và
		report UC-48 phải thấy đủ; sổ kho không được đẻ dòng rỗng cho một sự
		kiện qty=0."""
		so = self._sales_order(qty=50)
		dn = self._dn_tu_so(so, 50)
		phieu = self._phieu_duy_nhat(dn)
		ten_dong = phieu.items[0].name

		payload = self._payload_don_dong(
			phieu, so_luong=0, ly_do_chenh_lech="mất trên đường vận chuyển",
		)
		frappe.set_user(BM_USER)
		out = kho_api.kho_phieu_nhap_save(payload)
		self.assertEqual(out["items"][0]["so_luong"], 0)

		kho_api.kho_phieu_submit("Customer Stock Receipt", phieu.name)
		lai = frappe.get_doc("Customer Stock Receipt", phieu.name)
		self.assertEqual(lai.co_chenh_lech, 1)
		self.assertEqual(lai.items[0].sl_giao, 50)
		self.assertEqual(lai.items[0].so_luong, 0)

		self.assertFalse(
			frappe.db.exists("Customer Stock Ledger Entry", {
				"chung_tu_type": "Customer Stock Receipt", "chung_tu": phieu.name,
				"chung_tu_row": ten_dong,
			}),
			"sự kiện qty=0 không được đẻ dòng sổ rỗng",
		)
		self.assertIsNone(
			ledger.get_lot_balance(self.kho_bm, phieu.items[0].vat_tu, phieu.items[0].so_lo),
			"chưa từng có tồn cho lô này — không được tự sinh một dòng tồn 0",
		)
		self.assertTrue(
			frappe.db.exists("Notification Log", {
				"for_user": SALES_USER,
				"subject": ["like", f"%Chênh lệch nhận hàng%{phieu.name}%"],
			}),
			"hàng mất hoàn toàn vẫn phải báo sales phụ trách",
		)

		rows = desk_reports.doi_soat_giao_nhan_rows(chi_chenh_lech=True)
		row = next(r for r in rows if r["phieu_nhap"] == phieu.name)
		self.assertEqual(row["chenh"], -50, "report UC-48 phải thấy đủ 50 đơn vị mất")

	# ---------------------------------------------------------------------- C2
	def test_C2_sua_so_lo_khong_lam_mat_sl_giao(self):
		"""C2 (E3 phần B review): khớp mốc đối soát theo `name` của dòng con,
		KHÔNG PHẢI theo giá trị (vat_tu, so_lo). Trước bản này, thủ kho gõ
		lại số lô in trên thùng thay cho KHONG-LO (đúng giao diện mới cổ vũ,
		badge "⚠ Thiếu lô/hạn" nằm ngay cạnh ô Số lô) khiến khoá không còn
		khớp → sl_giao rơi về 0 ÂM THẦM, tắt vĩnh viễn BR-K17 cho dòng đó."""
		so = self._sales_order(qty=50)
		dn = self._dn_tu_so(so, 50)
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(phieu.items[0].sl_giao, 50)

		payload = self._payload_don_dong(phieu, so_lo="LO-THUC-TE-GHI-TREN-THUNG")
		frappe.set_user(BM_USER)
		out = kho_api.kho_phieu_nhap_save(payload)
		self.assertEqual(out["items"][0]["so_lo"], "LO-THUC-TE-GHI-TREN-THUNG")

		lai = frappe.get_doc("Customer Stock Receipt", phieu.name)
		self.assertEqual(
			lai.items[0].sl_giao, 50,
			"sửa Số lô không được làm mất mốc đối soát (khớp theo name, không theo giá trị)",
		)

		# Chốt BR-K17 vẫn phải sống: sửa thêm so_luong lệch mà không có lý do
		# phải bị chặn NGAY TRÊN dòng vừa đổi số lô — chứng minh sl_giao
		# không chỉ "còn giá trị cũ" mà THẬT SỰ vẫn được validate dùng.
		payload2 = self._payload_don_dong(
			phieu, so_lo="LO-THUC-TE-GHI-TREN-THUNG", so_luong=40,
		)
		with self.assertRaises(frappe.ValidationError) as ctx:
			kho_api.kho_phieu_nhap_save(payload2)
		self.assertIn("Nhập lý do chênh lệch để tiếp tục", str(ctx.exception))

	# --------------------------------------------------------------------- C2b
	def test_C2b_hai_dong_trung_vat_tu_so_lo_khong_dao_lon_moc(self):
		"""C2b: hook CÓ THỂ sinh hai dòng cùng (vat_tu, so_lo) thật (hai dòng
		DN khác giá/khác SO gộp lô — `_lo_cua_dong` chỉ gộp lô TRONG PHẠM VI
		một dòng DN). Bản khớp theo giá trị cũ sẽ gán mốc của dòng ĐẦU cho
		bất kỳ dòng payload nào khớp cùng giá trị — khớp theo `name` phải
		giữ ĐÚNG mốc riêng của từng dòng dù giá trị trùng nhau và thứ tự
		trong payload bị đảo."""
		so = self._sales_order(qty=50)
		dn = self._dn_tu_so(so, 50)
		phieu = self._phieu_duy_nhat(dn)
		vat_tu = phieu.items[0].vat_tu
		so_lo = phieu.items[0].so_lo
		han = phieu.items[0].han_su_dung
		don_gia = phieu.items[0].don_gia

		# Mô phỏng dòng thứ hai hook có thể sinh — cùng (vat_tu, so_lo),
		# sl_giao khác (10, thay vì 50 của dòng đầu).
		doc = frappe.get_doc("Customer Stock Receipt", phieu.name)
		doc.append("items", {
			"vat_tu": vat_tu, "so_lo": so_lo, "han_su_dung": han,
			"so_luong": 10, "sl_giao": 10, "don_gia": don_gia,
		})
		doc.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(len(doc.items), 2)
		ten_50 = next(r.name for r in doc.items if r.sl_giao == 50)
		ten_10 = next(r.name for r in doc.items if r.sl_giao == 10)

		def _row(ten, so_luong):
			return {
				"name": ten, "vat_tu": vat_tu, "so_lo": so_lo,
				"han_su_dung": str(han) if han else None,
				"so_luong": so_luong, "don_gia": don_gia, "ghi_chu": "",
			}

		frappe.set_user(BM_USER)
		payload = {
			"name": phieu.name, "ngay": str(doc.ngay), "loai_nhap": doc.loai_nhap,
			"nguoi_giao": doc.nguoi_giao, "chung_tu_kem": doc.chung_tu_kem,
			"dien_giai": doc.dien_giai,
			# Đảo thứ tự so với DB — khớp theo name phải KHÔNG bị ảnh hưởng.
			"items": [_row(ten_10, 10), _row(ten_50, 50)],
		}
		kho_api.kho_phieu_nhap_save(payload)

		lai = frappe.get_doc("Customer Stock Receipt", phieu.name)
		moc = {r.name: r.sl_giao for r in lai.items}
		self.assertEqual(moc[ten_50], 50, "dòng vốn sl_giao=50 phải giữ đúng 50")
		self.assertEqual(moc[ten_10], 10, "dòng vốn sl_giao=10 phải giữ đúng 10, không lẫn với dòng kia")

	# ------------------------------------------------------------------ TC-E3-04
	def test_TC_E3_04_vuot_sl_giao_bi_chan_ke_ca_co_ly_do(self):
		"""NL-3.10: nhận thừa thật sự không được "sửa" một phiếu tự sinh."""
		so = self._sales_order(qty=50)
		dn = self._dn_tu_so(so, 50)
		phieu = self._phieu_duy_nhat(dn)

		phieu.items[0].so_luong = 52
		phieu.items[0].ly_do_chenh_lech = "nhận thừa thật"
		with self.assertRaises(frappe.ValidationError) as ctx:
			phieu.save(ignore_permissions=True)
		self.assertIn("không được vượt", str(ctx.exception))
		self.assertIn("Nhập khác", str(ctx.exception))

	# ------------------------------------------------------------------ TC-E3-07
	def test_TC_E3_07_thieu_lo_han_danh_dau_nhung_khong_chan_giao(self):
		"""US-E3.6/NL-3.7: ITEM không bật Has Batch No → lô rơi về KHONG-LO."""
		so = self._sales_order(qty=10)
		dn = self._dn_tu_so(so, 10)
		self.assertEqual(dn.docstatus, 1, "Giao hàng không được chặn dù thiếu lô/hạn")

		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(phieu.items[0].so_lo, ledger.LOT_KHONG_CO)
		self.assertEqual(phieu.items[0].thieu_lo_han, 1)

	# ------------------------------------------------------------------ TC-E3-08
	def test_TC_E3_08_loi_gia_lap_trong_phan_mo_rong_khong_chan_dn(self):
		"""BR-K12: phần mở rộng E3 (so_dot) hỏng không được ném ra ngoài."""
		so = self._sales_order(qty=10)
		with unittest.mock.patch.object(
			delivery_hook, "_so_dot_cua", side_effect=RuntimeError("hỏng có chủ ý — E3")
		):
			dn = self._dn_tu_so(so, 10)

		self.assertEqual(dn.docstatus, 1, "DN phải submit được dù phần mở rộng E3 hỏng")
		self.assertEqual(
			frappe.db.get_value("Delivery Note", dn.name, "docstatus"), 1,
		)
		# Hỏng SAU khi đã bắt đầu dựng phiếu (trong _tao_phieu) → savepoint
		# phải cuốn lại toàn bộ, không để phiếu mồ côi thiếu so_dot.
		self.assertEqual(self._phieu_cua(dn.name), [])

		log = frappe.get_all(
			"Error Log",
			filters={"reference_doctype": "Delivery Note", "reference_name": dn.name},
			fields=["method", "error"],
		)
		self.assertEqual(len(log), 1, "Lỗi bị nuốt phải để lại đúng một dòng Error Log")
		self.assertIn("Kho khách", log[0].method)
		self.assertIn("hỏng có chủ ý — E3", log[0].error)
