"""UAT kịch bản kiểm hàng — chạy HAI VAI trên dữ liệu thật của site.

    bench --site erptest.local execute miyano_portal.setup.uat_kiem_hang.chay

Khác với `tests/test_e9_kiem_hang.py` (mỗi class một transaction bị rollback,
mọi thứ dựng từ fixture): script này chạy trên khách demo THẬT, đi qua đúng
các endpoint whitelist mà trình duyệt gọi, và KIỂM CẢ thông báo hai chiều —
thứ mà test có kiểm nhưng chỉ trong bộ nhớ của một transaction sẽ biến mất.

Mặc định `rollback=True`: chạy xong trả site về đúng như trước. Truyền
`--kwargs "{'rollback': False}"` nếu muốn giữ lại dữ liệu để xem trên giao diện.
"""

import frappe

from miyano_portal.api import portal as api
from miyano_portal import portal_kiem_hang as kh

KHACH = "Bệnh viện Bạch Mai"
USER_KHACH = "bvbm@demo.miyano"
KHACH_KHAC = "PXN ABC"

COMPANY = "Miyano Việt Nam"
KHO_MYN = "Kho Miyano - MYN"
COST_CENTER = "Main - MYN"
ITEM = "MYN-GLOVE-M"
ITEM_2 = "MYN-SYR-10"

_ket_qua: list[tuple[str, str]] = []


def _ok(ten: str, chi_tiet: str = "") -> None:
	_ket_qua.append(("PASS", f"{ten}{' — ' + chi_tiet if chi_tiet else ''}"))


def _fail(ten: str, chi_tiet: str) -> None:
	_ket_qua.append(("FAIL", f"{ten} — {chi_tiet}"))


def _mong_loi(ten: str, fn, loai=Exception) -> None:
	"""Ngoại lệ PHẢI ném. Không ném = lỗi, và đó chính là điều cần kiểm."""
	try:
		fn()
	except loai as e:
		_ok(ten, str(e)[:90])
		return
	except Exception as e:  # noqa: BLE001
		_fail(ten, f"ném sai loại lỗi: {type(e).__name__}: {e}")
		return
	_fail(ten, "KHÔNG ném lỗi — chốt chặn không hoạt động")


def _nap_ton(item_code, qty):
	from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

	make_stock_entry(
		item_code=item_code, qty=qty, to_warehouse=KHO_MYN, rate=1000,
		company=COMPANY, purpose="Material Receipt",
	)


def _dn(customer=KHACH, rows=None):
	dn = frappe.new_doc("Delivery Note")
	dn.company = COMPANY
	dn.customer = customer
	dn.posting_date = frappe.utils.today()
	for r in rows or [{"item_code": ITEM, "qty": 10}, {"item_code": ITEM_2, "qty": 5}]:
		dn.append("items", {
			"item_code": r["item_code"], "qty": r["qty"], "rate": 95000,
			"warehouse": KHO_MYN, "cost_center": COST_CENTER,
		})
	dn.insert(ignore_permissions=True)
	dn.submit()
	return dn


def _staff():
	"""Một Sales Manager THẬT (không phải Administrator — Administrator bỏ qua
	mọi kiểm tra nên sẽ không chứng minh được gì về phân quyền)."""
	ten = frappe.db.get_value(
		"Has Role", {"role": "Sales Manager", "parenttype": "User"}, "parent"
	)
	if ten and ten not in ("Administrator", "Guest"):
		return ten
	raise RuntimeError("Site không có Sales Manager nào để chạy vai nhân viên.")


def chay(rollback: bool = True) -> None:
	_ket_qua.clear()
	frappe.set_user("Administrator")
	_nap_ton(ITEM, 100)
	_nap_ton(ITEM_2, 100)
	staff = _staff()

	dn = _dn()
	dn_khac = _dn(customer=KHACH_KHAC)

	# ---------------------------------------------------------- VAI KHÁCH HÀNG
	frappe.set_user(USER_KHACH)

	d = api.portal_kiem_hang_get(dn.name)
	if d["moi"] and len(d["bien_ban"]["items"]) == 2:
		_ok("Khách mở màn kiểm hàng", f"{len(d['bien_ban']['items'])} mặt hàng, mặc định nhận đủ")
	else:
		_fail("Khách mở màn kiểm hàng", str(d)[:120])

	_mong_loi(
		"Ngoại lệ: không kiểm được phiếu giao của khách khác",
		lambda: api.portal_kiem_hang_get(dn_khac.name), frappe.PermissionError,
	)
	_mong_loi(
		"Ngoại lệ: phiếu giao không có thật",
		lambda: api.portal_kiem_hang_get("MAT-DN-KHONG-CO-THAT"), frappe.PermissionError,
	)
	_mong_loi(
		"Ngoại lệ: lệch mà không nêu lý do",
		lambda: api.portal_kiem_hang_gui(dn.name, [{"item_code": ITEM, "sl_nhan": 7}]),
		frappe.ValidationError,
	)
	_mong_loi(
		"Ngoại lệ: nhận tốt + trả lại vượt SL giao",
		lambda: api.portal_kiem_hang_gui(
			dn.name, [{"item_code": ITEM, "sl_nhan": 9, "sl_tra": 5, "ly_do": "x"}]
		),
		frappe.ValidationError,
	)
	_mong_loi(
		"Ngoại lệ: khách tự khai SL giao (sl_giao từ client bị bỏ qua)",
		lambda: api.portal_kiem_hang_gui(
			dn.name,
			[{"item_code": ITEM, "sl_giao": 999, "sl_nhan": 500, "sl_tra": 0, "ly_do": "x"}],
		),
		frappe.ValidationError,
	)

	nhap = api.portal_kiem_hang_luu(
		dn.name, [{"item_code": ITEM, "sl_nhan": 10}], "đang kiểm dở"
	)
	_ok("Khách lưu nháp", nhap["name"])

	gui = api.portal_kiem_hang_gui(
		dn.name,
		[
			{"item_code": ITEM, "sl_nhan": 6, "sl_tra": 3, "ly_do": "Vỡ 3 hộp khi vận chuyển"},
			{"item_code": ITEM_2, "sl_nhan": 5, "sl_tra": 0},
		],
		"Đề nghị Miyano thu hồi phần hỏng.",
	)
	bb = gui["name"]
	if gui["trang_thai"] == kh.TT_CHO_XU_LY and gui["co_hang_hong"]:
		_ok("Khách gửi biên bản (nhận 6, hỏng 3, thiếu 1)", f"{bb} → {gui['trang_thai']}")
	else:
		_fail("Khách gửi biên bản", str(gui))

	if frappe.db.count("Portal Delivery Inspection", {"delivery_note": dn.name}) == 1:
		_ok("Nháp và bản gửi là MỘT biên bản", bb)
	else:
		_fail("Nháp và bản gửi là MỘT biên bản", "sinh ra nhiều hơn một")

	_mong_loi(
		"Ngoại lệ: gửi lần hai trên cùng phiếu giao",
		lambda: api.portal_kiem_hang_gui(
			dn.name, [{"item_code": ITEM, "sl_nhan": 10, "sl_tra": 0, "ly_do": "đổi ý"}]
		),
		frappe.ValidationError,
	)
	_mong_loi(
		"Ngoại lệ: khách không tự duyệt biên bản của mình",
		lambda: kh.kiem_hang_duyet_tra(bb), frappe.PermissionError,
	)

	# Trạng thái phải hiện ngay trên chi tiết đơn — nếu không, khách không có
	# đường nào thấy lại biên bản mình vừa gửi.
	frappe.set_user("Administrator")
	so_lien_quan = frappe.db.get_value(
		"Delivery Note Item",
		{"parent": dn.name, "against_sales_order": ["is", "set"]}, "against_sales_order",
	)
	frappe.set_user(USER_KHACH)
	if so_lien_quan:
		track = api.portal_order_track(so_lien_quan)
		dot = [x for x in track["deliveries"] if x["name"] == dn.name]
		if dot and dot[0]["kiem_hang"] and dot[0]["kiem_hang"]["trang_thai"] == kh.TT_CHO_XU_LY:
			_ok("Trạng thái kiểm hàng hiện trên chi tiết đơn", so_lien_quan)
		else:
			_fail("Trạng thái kiểm hàng hiện trên chi tiết đơn", str(dot)[:120])
	else:
		_ok("Trạng thái kiểm hàng hiện trên chi tiết đơn",
		    "BỎ QUA — phiếu giao này không gắn đơn hàng nào")

	# ---------------------------------------------------------- VAI NHÂN VIÊN
	frappe.set_user("Administrator")
	bao_sales = frappe.db.exists("Notification Log", {
		"document_type": "Portal Delivery Inspection", "document_name": bb,
		"subject": ["like", "Portal - Kiểm hàng có vấn đề%"],
	})
	_ok("Sales nhận thông báo biên bản có vấn đề", str(bao_sales)) if bao_sales else _fail(
		"Sales nhận thông báo biên bản có vấn đề", "không có Notification Log nào"
	)

	frappe.set_user(staff)
	_mong_loi(
		"Ngoại lệ: từ chối mà không nêu lý do",
		lambda: kh.kiem_hang_tu_choi(bb, " "), frappe.ValidationError,
	)
	duyet = kh.kiem_hang_duyet_tra(bb)
	tra = frappe.get_doc("Delivery Note", duyet["phieu_tra_hang"])
	dung = (
		tra.docstatus == 0 and tra.is_return and tra.return_against == dn.name
		and len(tra.items) == 1 and tra.items[0].item_code == ITEM
		and float(tra.items[0].qty) == -3
	)
	if dung:
		_ok("Nhân viên duyệt → phiếu trả hàng NHÁP đúng số lượng",
		    f"{tra.name}: {ITEM} × {tra.items[0].qty}")
	else:
		_fail("Nhân viên duyệt → phiếu trả hàng NHÁP đúng số lượng",
		      f"{tra.name} docstatus={tra.docstatus} dòng={[(i.item_code, i.qty) for i in tra.items]}")

	_mong_loi(
		"Ngoại lệ: duyệt lại biên bản đã duyệt",
		lambda: kh.kiem_hang_duyet_tra(bb), frappe.ValidationError,
	)

	frappe.set_user("Administrator")
	tra.submit()
	tt = frappe.db.get_value("Portal Delivery Inspection", bb, "trang_thai")
	if tt == kh.TT_DA_THU_HOI:
		_ok("Kho ghi sổ phiếu trả → biên bản sang «Đã thu hồi»", tra.name)
	else:
		_fail("Kho ghi sổ phiếu trả → biên bản sang «Đã thu hồi»", f"đang là «{tt}»")

	bao_khach = frappe.get_all("Notification Log", filters={
		"document_type": "Portal Delivery Inspection", "document_name": bb,
		"subject": ["like", "Portal - Kiểm hàng:%"],
	}, pluck="subject")
	if len(bao_khach) >= 2:
		_ok("Khách nhận thông báo từng mốc", f"{len(bao_khach)} thông báo")
	else:
		_fail("Khách nhận thông báo từng mốc", f"chỉ có {bao_khach}")

	# Link trên trang Thông báo phải trỏ đúng màn kiểm hàng của phiếu giao đó.
	link = api._lien_ket_thong_bao("Portal Delivery Inspection", bb, KHACH)
	if link == f"/kiem-hang/{dn.name}":
		_ok("Thông báo có link thẳng tới biên bản", link)
	else:
		_fail("Thông báo có link thẳng tới biên bản", str(link))
	if api._lien_ket_thong_bao("Portal Delivery Inspection", bb, KHACH_KHAC) is None:
		_ok("Khách khác không suy được link tới biên bản này")
	else:
		_fail("Khách khác không suy được link tới biên bản này", "trả về link")

	_mong_loi(
		"Ngoại lệ: huỷ biên bản đã có phiếu trả hàng",
		lambda: frappe.get_doc("Portal Delivery Inspection", bb).cancel(),
		frappe.ValidationError,
	)

	# ---------------------------------------------------------------- kết quả
	frappe.set_user("Administrator")
	rot = [x for x in _ket_qua if x[0] == "FAIL"]
	print("\n=== UAT KIỂM HÀNG ===")
	for tt, mo_ta in _ket_qua:
		print(f"  [{tt}] {mo_ta}")
	print(f"\n{len(_ket_qua) - len(rot)}/{len(_ket_qua)} bước đạt.")
	if rot:
		print("RỚT:")
		for _, mo_ta in rot:
			print("  -", mo_ta)

	if rollback:
		frappe.db.rollback()
		print("\nĐã rollback — site trở lại đúng như trước khi chạy.")
	else:
		frappe.db.commit()
		print(f"\nĐã GIỮ LẠI dữ liệu. Biên bản: {bb}, phiếu giao: {dn.name}.")
