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
from miyano_portal import portal_hen_giao as hen_giao

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


def _skip(ten: str, ly_do: str) -> None:
	"""Bước KHÔNG chạy được. Tách khỏi PASS và KHÔNG tính vào mẫu số: một
	bước bị bỏ qua mà in ra PASS là cách một chốt kiểm chết trong im lặng —
	đúng loại lỗi codebase này đã cảnh báo ở nhiều chỗ khác."""
	_ket_qua.append(("SKIP", f"{ten} — {ly_do}"))


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


def _don_va_phieu_giao(customer=KHACH, rows=None):
	"""Đơn hàng THẬT rồi mới tới phiếu giao của nó.

	Bản đầu của script dựng thẳng Delivery Note không gắn đơn nào, nên bước
	"trạng thái kiểm hàng hiện trên chi tiết đơn" không có gì để chạy — và
	tệ hơn, nó in ra PASS. Một phiếu giao mồ côi cũng không phải hình dạng dữ
	liệu thật: mọi phiếu giao của Miyano đều sinh từ một đơn.
	"""
	rows = rows or [{"item_code": ITEM, "qty": 10}, {"item_code": ITEM_2, "qty": 5}]
	so = frappe.new_doc("Sales Order")
	so.company = COMPANY
	so.customer = customer
	so.transaction_date = frappe.utils.today()
	so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 3)
	for r in rows:
		so.append("items", {
			"item_code": r["item_code"], "qty": r["qty"], "rate": 95000,
			"warehouse": KHO_MYN, "cost_center": COST_CENTER,
			"delivery_date": frappe.utils.getdate(so.delivery_date),
		})
	so.flags.ignore_permissions = True
	so.insert(ignore_permissions=True)
	so.submit()

	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

	dn = make_delivery_note(so.name)
	dn.company = COMPANY
	for r in dn.items:
		r.warehouse = KHO_MYN
		r.cost_center = COST_CENTER
	dn.insert(ignore_permissions=True)
	dn.submit()
	return so, dn


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

	so_goc, dn = _don_va_phieu_giao()
	_, dn_khac = _don_va_phieu_giao(customer=KHACH_KHAC)

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
		_skip("Trạng thái kiểm hàng hiện trên chi tiết đơn",
		      "phiếu giao này không gắn đơn hàng nào")

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

	# ------------------------------- đường lùi: bị từ chối rồi gửi lại (spec §4.3)
	frappe.set_user("Administrator")
	_, dn2 = _don_va_phieu_giao()
	frappe.set_user(USER_KHACH)
	bb2 = api.portal_kiem_hang_gui(
		dn2.name, [{"item_code": ITEM, "sl_nhan": 7, "sl_tra": 3, "ly_do": "Móp hộp"}]
	)["name"]
	frappe.set_user(staff)
	kh.kiem_hang_tu_choi(bb2, "Biên bản ký nhận ghi hàng nguyên vẹn")
	frappe.set_user(USER_KHACH)
	xem = api.portal_kiem_hang_get(dn2.name)
	if xem["bien_ban"]["co_the_gui_lai"]:
		_ok("Bị từ chối → cổng mở đường gửi lại", bb2)
	else:
		_fail("Bị từ chối → cổng mở đường gửi lại",
		      "màn kiểm hàng khoá cứng, khách hết đường đi")
	bb3 = api.portal_kiem_hang_gui(
		dn2.name, [{"item_code": ITEM, "sl_nhan": 9, "sl_tra": 1, "ly_do": "Đếm lại: 1 hỏng"}]
	)["name"]
	lai = api.portal_kiem_hang_get(dn2.name)["bien_ban"]
	if bb3 != bb2 and lai["name"] == bb3 and lai["trang_thai"] == kh.TT_CHO_XU_LY:
		_ok("Khách gửi lại được, và thấy đúng bản mới", f"{bb2} → {bb3}")
	else:
		_fail("Khách gửi lại được, và thấy đúng bản mới", str(lai)[:120])
	frappe.set_user("Administrator")
	if frappe.db.get_value("Portal Delivery Inspection", bb2, "trang_thai") == kh.TT_TU_CHOI:
		_ok("Bản bị từ chối giữ nguyên làm lịch sử", bb2)
	else:
		_fail("Bản bị từ chối giữ nguyên làm lịch sử", "đã bị đổi/huỷ")

	# ------------------- vai nhân viên: hàng thiếu, hẹn giao, kho hàng trả về
	from miyano_portal.kho_hang_tra_ve import dam_bao_kho

	tra.reload()
	kho_tra = dam_bao_kho(tra.company)
	if kho_tra and all(r.warehouse == kho_tra for r in tra.items):
		_ok("Hàng hỏng trả về vào kho «Hàng trả về», không lẫn tồn bán được", kho_tra)
	else:
		_fail("Hàng hỏng trả về vào kho «Hàng trả về»",
		      f"đang ghi vào {[r.warehouse for r in tra.items]}")

	# Biên bản VỪA hỏng VỪA thiếu — chỗ bản trước bỏ rơi nửa "thiếu".
	frappe.set_user("Administrator")
	so3, dn3 = _don_va_phieu_giao(rows=[{"item_code": ITEM, "qty": 10}])
	frappe.set_user(USER_KHACH)
	bb4 = api.portal_kiem_hang_gui(
		dn3.name, [{"item_code": ITEM, "sl_nhan": 6, "sl_tra": 2, "ly_do": "2 vỡ, 2 không tới"}]
	)["name"]
	frappe.set_user(staff)
	kh.kiem_hang_duyet_tra(bb4)
	try:
		r_hen = kh.kiem_hang_hen_giao(
			bb4, frappe.utils.add_days(frappe.utils.today(), 7),
			"Sẽ giao bù", "Hàng về kho tuần sau",
		)
		_ok("Biên bản vừa hỏng vừa thiếu: trả lời được CẢ phần thiếu",
		    f"{r_hen['loai']} {r_hen['ngay_hen_giao']}")
	except Exception as e:  # noqa: BLE001
		_fail("Biên bản vừa hỏng vừa thiếu: trả lời được CẢ phần thiếu", str(e)[:120])

	frappe.set_user("Administrator")
	so3.reload()
	if str(so3.custom_ngay_hen_giao) and so3.custom_loai_hen_giao == "Sẽ giao bù":
		_ok("Lời hẹn ghi lên CHÍNH đơn hàng", f"{so3.name} → {so3.custom_ngay_hen_giao}")
	else:
		_fail("Lời hẹn ghi lên CHÍNH đơn hàng", "đơn không mang lời hẹn nào")

	frappe.set_user(USER_KHACH)
	track3 = api.portal_order_track(so3.name)
	if track3.get("hen_giao") and track3["hen_giao"]["loai"] == "Sẽ giao bù":
		_ok("Khách thấy lời hẹn trên chi tiết đơn", track3["hen_giao"]["ngay"])
	else:
		_fail("Khách thấy lời hẹn trên chi tiết đơn", str(track3.get("hen_giao")))

	frappe.set_user(staff)
	_mong_loi(
		"Ngoại lệ: không xử lý phần thiếu hai lần",
		lambda: kh.kiem_hang_da_xu_ly(bb4, "đổi ý"), frappe.ValidationError,
	)
	_mong_loi(
		"Ngoại lệ: không hẹn giao vào ngày quá khứ",
		lambda: hen_giao.hen_giao_lai(
			so3.name, frappe.utils.add_days(frappe.utils.today(), -1),
			"Sẽ giao bù", "ngày quá khứ",
		),
		frappe.ValidationError,
	)

	# "Đã đổi ngày giao" phải dời CẢ dòng — mọi báo cáo trễ hạn của ERPNext
	# đọc `Sales Order Item.delivery_date`.
	ngay_moi = frappe.utils.add_days(frappe.utils.today(), 14)
	frappe.set_user(staff)
	hen_giao.hen_giao_lai(so_goc.name, ngay_moi, "Đã đổi ngày giao", "Khách đồng ý dời lịch")
	frappe.set_user("Administrator")
	so_goc.reload()
	if so_goc.delivery_date == frappe.utils.getdate(ngay_moi) and all(
		r.delivery_date == frappe.utils.getdate(ngay_moi) for r in so_goc.items
	):
		_ok("«Đã đổi ngày giao» dời cả đơn lẫn từng dòng", str(ngay_moi))
	else:
		_fail("«Đã đổi ngày giao» dời cả đơn lẫn từng dòng",
		      f"đơn={so_goc.delivery_date} dòng={[str(r.delivery_date) for r in so_goc.items]}")

	# ---------------------------------------------------------------- kết quả
	frappe.set_user("Administrator")
	rot = [x for x in _ket_qua if x[0] == "FAIL"]
	bo_qua = [x for x in _ket_qua if x[0] == "SKIP"]
	chay = [x for x in _ket_qua if x[0] != "SKIP"]
	print("\n=== UAT KIỂM HÀNG ===")
	for tt, mo_ta in _ket_qua:
		print(f"  [{tt}] {mo_ta}")
	print(f"\n{len(chay) - len(rot)}/{len(chay)} bước đạt"
	      + (f", {len(bo_qua)} bước KHÔNG chạy được." if bo_qua else "."))
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
