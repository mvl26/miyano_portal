"""E6 phần B — Mua lẻ ngoài HĐNT, giỏ 2 ngăn.

Xem docs/Miyano-Portal(Client)_V2/DevHandoff/15_PRD_E6_MuaLe_YeuCauHang.md
(US-E6.1/E6.2), 30_API_Spec.md (§1.1, §2.2), 40_TestCases.md
(TC-E6-01…04), BA §4.10 (BR-R1…R7, NL-10.x).

Fixtures riêng của module này (KHÔNG sửa `setup/seed_demo.py`): một Price
List bán lẻ + hai item bán lẻ, gắn thêm vào dữ liệu `seed_demo()` sẵn có
(Bệnh viện Bạch Mai có HĐNT với VT0005/HC0009). `FrappeTestCase` rollback
một lần mỗi CLASS — mỗi `setUp` tự đặt lại field có thể bị ca trước bẻ
(`custom_cho_phep_mua_le`...) để các test method trong cùng class không ăn
theo trạng thái của nhau.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bang_gia_khach
from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.setup.seed_demo import COMPANY, PRICE_LIST, seed_demo
from miyano_portal.tests import don_mua_le_cu
from miyano_portal.tests.fixtures_hop_dong import hop_dong_hieu_luc_dau_tien

BVBM = "Bệnh viện Bạch Mai"
USER_BVBM = "bvbm@demo.miyano"
PXN = "PXN ABC"
USER_PXN = "pxnabc@demo.miyano"

PL_BAN_LE = "Bán lẻ E6 Test"
RETAIL_CO_GIA = "RTL-E6-001"
RETAIL_THIEU_GIA = "RTL-E6-002"
RETAIL_NGUNG_KD = "RTL-E6-003"  # disabled=1 — thiết kế lại mua lẻ §4.1/§4.5
VT_HDNT = "VT0005"  # Item đã nằm trong HĐNT-BVBM-2026 (seed_demo)


def _rid() -> str:
    return frappe.generate_hash(length=12)


def _kho_mac_dinh():
    return frappe.db.get_value(
        "Warehouse", {"company": COMPANY, "is_group": 0, "warehouse_name": "Stores"}
    )


def _dam_bao_item_ban_le(item_code: str, ten: str, gia) -> None:
    """Item với Item Default (company/kho) để `resolve_ban_le_company` suy
    được company, và (tuỳ `gia`) một dòng Item Price trong `PL_BAN_LE`.

    Việc 2(a) — KHÔNG còn set `custom_ban_le_portal`: cờ này đã xoá (custom
    field xoá bằng `patches/v1_16/xoa_custom_field_ban_le_portal.py`), danh
    mục lẻ không lọc theo nó từ thiết kế lại §4.1."""
    kho = _kho_mac_dinh()
    if not frappe.db.exists("Item", item_code):
        doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": ten,
            "item_group": "Vật tư tiêu hao",
            "stock_uom": "Cái",
            "is_stock_item": 1,
            "description": "Hộp 10 cái",
        })
        if kho:
            doc.append("item_defaults", {"company": COMPANY, "default_warehouse": kho})
        doc.insert(ignore_permissions=True)
    else:
        doc = frappe.get_doc("Item", item_code)
        if kho and not any(d.company == COMPANY and d.default_warehouse for d in doc.item_defaults):
            doc.append("item_defaults", {"company": COMPANY, "default_warehouse": kho})
            doc.save(ignore_permissions=True)

    existing = frappe.db.get_value(
        "Item Price", {"item_code": item_code, "price_list": PL_BAN_LE, "selling": 1}, "name"
    )
    if gia is None:
        if existing:
            frappe.delete_doc("Item Price", existing, ignore_permissions=True, force=True)
        return
    if existing:
        frappe.db.set_value("Item Price", existing, "price_list_rate", gia)
    else:
        frappe.get_doc({
            "doctype": "Item Price",
            "item_code": item_code,
            "price_list": PL_BAN_LE,
            "uom": "Cái",
            "selling": 1,
            "price_list_rate": gia,
            "currency": "VND",
        }).insert(ignore_permissions=True)


def _seed_mua_le():
    seed_demo()
    if not frappe.db.exists("Price List", PL_BAN_LE):
        frappe.get_doc({
            "doctype": "Price List", "price_list_name": PL_BAN_LE,
            "selling": 1, "currency": "VND",
        }).insert(ignore_permissions=True)

    frappe.db.set_single_value("Miyano Portal Settings", "hieu_luc_bao_gia_ngay", 7)

    frappe.db.set_value("Customer", BVBM, "custom_cho_phep_mua_le", 1)
    frappe.db.set_value("Customer", PXN, "custom_cho_phep_mua_le", 0)

    # Spec 2026-10-09 — giá lấy từ Price List RIÊNG của khách. seed_demo chỉ
    # ghi giá VT0005 vào bảng hợp đồng; khi khách đã có bảng riêng thì bảng
    # đó có thể thiếu dòng này, và mọi bài đặt VT0005 rơi sang Quotation.
    pl_bvbm = bang_gia_khach.dam_bao_bang_gia_rieng(BVBM)
    if not frappe.db.exists(
        "Item Price", {"item_code": VT_HDNT, "price_list": pl_bvbm, "selling": 1}
    ):
        frappe.get_doc({
            "doctype": "Item Price", "item_code": VT_HDNT, "price_list": pl_bvbm,
            "price_list_rate": 1200, "selling": 1,
        }).insert(ignore_permissions=True)

    _dam_bao_item_ban_le(RETAIL_CO_GIA, "Khẩu trang y tế lẻ", 25000)
    _dam_bao_item_ban_le(RETAIL_THIEU_GIA, "Kit test nhanh lẻ", None)

    # §4.5 — item KHÔNG hoạt động (disabled=1) là chốt phòng thủ tầng hai
    # của `_xay_don_ban_le` (§4.1 chỉ còn `disabled` làm điều kiện thành
    # viên danh mục, `custom_ban_le_portal` đã xoá — Việc 2(a)).
    _dam_bao_item_ban_le(RETAIL_NGUNG_KD, "Hàng ngừng kinh doanh", None)
    frappe.db.set_value("Item", RETAIL_NGUNG_KD, "disabled", 1)


def _bao_gia_cua(case, res, don=None):
    """Spec 2026-10-12 §5 — giỏ còn hàng chưa có giá hoặc dòng gõ tay không còn
    sinh Sales Order "Mua lẻ": đường đặt trả `sales_order = None` cùng một
    Quotation ở "Chờ Miyano báo giá", và phiếu đứng sau mang `bao_gia`."""
    don = don or res
    case.assertIsNone(don["sales_order"])
    bg = frappe.get_doc("Quotation", don["bao_gia"])
    case.assertEqual(bg.workflow_state, "Chờ Miyano báo giá")
    case.assertEqual(
        frappe.db.get_value("Portal De Xuat Mua", don["de_xuat"], "bao_gia"), bg.name
    )
    return bg


class TestDatHangBanLe(FrappeTestCase):
    def setUp(self):
        _seed_mua_le()
        frappe.set_user(USER_BVBM)
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- TC-E6-02 ----------
    def test_dat_le_item_co_gia_khong_tru_han_muc(self):
        # review T-1 — bản trước đọc qty/ordered_qty của VT0005 sau khi đặt
        # LẺ mặt hàng RETAIL_CO_GIA — hai mặt hàng không liên quan, phép so
        # sánh không khẳng định được gì (VT0005 không đổi vì không ai đụng
        # tới nó, chứ không phải vì "đơn mua lẻ không trừ hạn mức"). Phần
        # chịu tải thật của US-E6.2/BR-R4 là ba assertFalse dưới đây: dòng
        # đơn không mang blanket_order/against_blanket_order/custom_hdnt.
        #
        # review P0 (kiểm thử hệ thống, mục "TC-E6-02") — ba assertFalse chỉ
        # khẳng định dòng đơn không GẮN link tới Blanket Order; chưa ai đọc
        # thẳng `ordered_qty` — trường ERPNext THẬT ghi số đã đặt luỹ kế của
        # dòng hợp đồng (cổng thôi đọc nó từ spec 2026-10-09; Desk và báo cáo
        # ERPNext vẫn đọc), được ERPNext core ghi
        # đè lúc submit (`StockController.update_blanket_order`, chạy khi
        # dòng đơn CÓ `blanket_order` — xem
        # apps/erpnext/erpnext/controllers/stock_controller.py). Dựng thêm
        # MỘT Blanket Order Item CÓ THẬT cho ĐÚNG mã hàng vừa mua lẻ
        # (RETAIL_CO_GIA) — của một HĐNT đã HẾT HIỆU LỰC (`to_date` hôm
        # qua) để BR-R7 không chặn mua lẻ, nhưng dòng Blanket Order Item vẫn
        # là một bản ghi thật trong CSDL — rồi đọc `ordered_qty` TRƯỚC/SAU,
        # và SUBMIT hẳn đơn mua lẻ để chạm đúng code path duy nhất có khả
        # năng ghi vào trường này. Nếu đơn lẻ lỡ trừ hạn mức, khách mất
        # quyền đặt theo hợp đồng — mất tiền trực tiếp, không phải suy diễn.
        bo_het_han = frappe.get_doc({
            "doctype": "Blanket Order",
            "blanket_order_type": "Selling",
            "customer": BVBM,
            "company": COMPANY,
            "from_date": frappe.utils.add_months(frappe.utils.today(), -13),
            "to_date": frappe.utils.add_days(frappe.utils.today(), -1),
            "items": [{"item_code": RETAIL_CO_GIA, "qty": 100, "rate": 25000}],
        })
        bo_het_han.insert(ignore_permissions=True)
        bo_het_han.submit()
        boi_name = bo_het_han.items[0].name
        frappe.db.set_value("Blanket Order Item", boi_name, "ordered_qty", 30)
        ordered_qty_truoc = frappe.db.get_value("Blanket Order Item", boi_name, "ordered_qty")
        self.assertEqual(float(ordered_qty_truoc), 30.0)

        # Spec 2026-10-12 §5 — `portal_order_place` nay sinh Quotation cho giỏ
        # này; đơn "Mua lẻ" đang dở dựng bằng `dat_hang.tao_sales_order` trực tiếp.
        res = don_mua_le_cu.dat_truc_tiep(
            BVBM,
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 2}]),
            mode="ban_le", request_id=_rid(),
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(so.docstatus, 0)
        self.assertEqual(so.custom_loai_don, "Mua lẻ")
        self.assertEqual(so.workflow_state, "Chờ xác nhận")
        self.assertEqual(so.items[0].item_code, RETAIL_CO_GIA)
        # §4.5 — TC-E6-02 đổi: không còn khái niệm "item có giá lẻ", đơn vào
        # "Chờ xác nhận" với rate = 0 (sales điền giá khi báo giá).
        self.assertEqual(float(so.items[0].rate), 0.0)
        # BR-R4 — không gắn Blanket Order lên dòng đơn mua lẻ.
        self.assertFalse(so.items[0].blanket_order)
        self.assertFalse(so.items[0].against_blanket_order)
        self.assertFalse(so.custom_hdnt)

        # Submit THẬT — `update_blanket_order` (ERPNext core) chỉ chạy ở
        # on_submit, không ở draft. Khách không có quyền submit Sales Order
        # (workflow chỉ mở transition cho System Manager) nên đổi sang
        # Administrator để submit, đúng đường Miyano xác nhận đơn thật sự đi.
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", so.name)
        so.taxes = []
        so.taxes_and_charges = None
        so.submit()
        frappe.set_user(USER_BVBM)

        ordered_qty_sau = frappe.db.get_value("Blanket Order Item", boi_name, "ordered_qty")
        self.assertEqual(
            float(ordered_qty_sau), float(ordered_qty_truoc),
            "đặt/submit đơn mua lẻ KHÔNG được đổi ordered_qty của HĐNT — "
            "mất thì khách mất quyền đặt theo hợp đồng",
        )

    # ---------- đảo ngược 21/08 (từng là review C-1) — BR-R1 bỏ hẳn, cả ở
    # đường GHI, không chỉ đường đọc ----------
    def test_c1_khach_chua_bat_co_van_dat_le_duoc_qua_duong_ghi(self):
        """PXN — vẫn giữ `custom_cho_phep_mua_le=0` tường minh trong fixture
        — phải ĐẶT ĐƯỢC đơn mua lẻ qua đường GHI (POST thẳng `mode="ban_le"`,
        bỏ qua hẳn danh mục). Chủ đầu tư chốt 19/08: không còn khách nào bị
        BR-R1 chặn, bất kể field cũ đang mang giá trị gì."""
        frappe.set_user(USER_PXN)
        rid = _rid()
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            mode="ban_le", request_id=rid,
        )
        bg = _bao_gia_cua(self, res)
        self.assertEqual(bg.party_name, PXN)
        self.assertEqual(bg.items[0].item_code, RETAIL_CO_GIA)

    # ---------- review C-2 (Critical) — BR-R7 không được lách qua hoa/thường ----------
    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_c2_ma_hang_viet_thuong_van_duoc_chuan_hoa_ve_ma_chinh_tac(self):
        """`tabItem` chạy collation `utf8mb4_unicode_ci` (case-insensitive):
        MariaDB coi "vt0005" và "VT0005" là CÙNG một bản ghi, nhưng phép so
        chuỗi của Python không biết điều đó. Lỗ đó (review C-2, từng là
        Critical) vẫn phải kín.

        Lịch sử: ban đầu khẳng định "bị BR-R7 chặn kèm mã chính tắc"; Task 4
        (21/08/2026) đảo thành "mã viết thường phải tra ra đúng hợp đồng".
        Từ spec 2026-10-09 hợp đồng không còn được hỏi, nhưng phép CHUẨN HOÁ
        vẫn gánh đúng việc đó với nguồn giá mới: mã viết thường phải tra ra
        GIÁ của mã chính tắc trong Price List của khách — nếu không, một
        dòng CÓ giá bị đóng dấu "Báo giá" với `rate = 0`."""
        rid = _rid()
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": VT_HDNT.lower(), "qty": 1}]),
            mode="ban_le", request_id=rid,
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(
            so.items[0].item_code, VT_HDNT,
            "dòng phải mang mã CHÍNH TẮC (Item.name), không phải chuỗi thô client gửi",
        )
        self.assertEqual(
            so.items[0].custom_nguon_gia, "Bảng giá",
            "mã viết thường vẫn phải tra ra ĐÚNG giá bảng giá của mã chính tắc",
        )
        self.assertTrue(float(so.items[0].rate) > 0, "phải mang giá bảng giá")
        self.assertFalse(so.items[0].blanket_order)

    def test_c2_khong_ton_tai_bi_tu_choi_ngay(self):
        """Mã hàng không tra ra Item thật nào (kể cả sau chuẩn hoá) phải bị
        từ chối ngay tại vòng gộp, không lọt xuống tầng kiểm hạn mức/giá rồi
        hiện một thông điệp khó hiểu về một mặt hàng không tồn tại."""
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": "KHONG-TON-TAI-XYZ", "qty": 1}]),
                mode="ban_le", request_id=_rid(),
            )

    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_c2_gop_dong_trung_ma_qua_khac_hoa_thuong(self):
        """Hệ luỵ CÙNG một lỗ ở vòng gộp giỏ: hai dòng "VT0005"/"vt0005"
        phải GỘP thành MỘT dòng đơn mang tổng số lượng, không tách đôi.

        Trước spec 2026-10-09 bài này chứng minh điều đó qua hạn mức (tổng 6
        vượt hạn mức còn 5 → bị chặn `vuot_han_muc`). Hạn mức không còn được
        kiểm lúc dựng đơn, nên giờ khẳng định thẳng kết quả của phép gộp —
        kể cả khi tổng VƯỢT số lượng còn lại trên hợp đồng."""
        bo = hop_dong_hieu_luc_dau_tien()
        frappe.db.set_value(
            "Blanket Order Item", {"parent": bo, "item_code": VT_HDNT},
            {"qty": 200, "ordered_qty": 195},  # hợp đồng chỉ còn đúng 5
        )
        res = portal.portal_order_place(
            bo,
            json.dumps([
                {"item_code": VT_HDNT, "qty": 3},
                {"item_code": VT_HDNT.lower(), "qty": 3},
            ]),
            mode="hdnt", request_id=_rid(),
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual([d.item_code for d in so.items], [VT_HDNT])
        self.assertEqual(float(so.items[0].qty), 6.0)
        self.assertIsNone(frappe.local.response.get("loi"))

    def test_dat_le_item_khong_co_gia_van_dat_duoc_rate_0(self):
        """§4.5 — "portal_order_place(mode='ban_le') không còn đòi giá":
        RETAIL_THIEU_GIA (KHÔNG có Item Price trong PL_BAN_LE) trước đây bị
        chặn với `ly_do=thieu_gia`; giờ phải ĐẶT ĐƯỢC bình thường, dòng vào
        đơn với rate=0 — bù cho test TC-E6-02 (dùng RETAIL_CO_GIA), chứng
        minh có/không có giá cũ không còn ảnh hưởng gì tới đường ghi."""
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_THIEU_GIA, "qty": 1}]),
            mode="ban_le", request_id=_rid(),
        )
        bg = _bao_gia_cua(self, res)
        self.assertEqual(bg.items[0].item_code, RETAIL_THIEU_GIA)
        self.assertEqual(float(bg.items[0].rate), 0.0)

    # ---------- TC-E6-03 / BR-R7 — đảo ở Task 4, đảo lần nữa theo spec
    # 2026-10-09 (hợp đồng khung không còn được hỏi lúc dựng đơn) ----------
    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_item_thuoc_hdnt_duoc_dinh_gia_theo_bang_gia_khong_gan_hop_dong(self):
        """Lịch sử: BR-R7 ban đầu TỪ CHỐI mặt hàng thuộc hợp đồng còn hiệu
        lực khỏi giỏ "mua lẻ"; Task 4 (21/08/2026) đảo thành "dòng đó LUÔN
        được định giá theo hợp đồng và trừ hạn mức".

        Spec 2026-10-09 §4.2 đảo lần nữa: cổng không còn hỏi hợp đồng khung.
        Mặt hàng thuộc hợp đồng đi vào đơn như mọi mặt hàng khác — giá lấy
        từ Price List của khách, dòng KHÔNG gắn hợp đồng, đơn không mang
        `custom_hdnt`, và vì mọi dòng đã có giá nên đơn là "Theo bảng giá"."""
        price_list = frappe.db.get_value("Customer", BVBM, "default_price_list")
        gia_bang = frappe.db.get_value(
            "Item Price",
            {"item_code": VT_HDNT, "price_list": price_list, "selling": 1},
            "price_list_rate",
        )
        self.assertTrue(gia_bang, "fixture phải có giá bảng giá để bài này có nghĩa")

        rid = _rid()
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": VT_HDNT, "qty": 1}]),
            mode="ban_le", request_id=rid,
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(so.items[0].item_code, VT_HDNT)
        self.assertEqual(float(so.items[0].rate), float(gia_bang))
        self.assertEqual(so.items[0].custom_nguon_gia, "Bảng giá")
        self.assertFalse(so.items[0].blanket_order)
        self.assertFalse(so.items[0].against_blanket_order)
        self.assertFalse(so.custom_hdnt)
        self.assertEqual(so.custom_loai_don, "Theo bảng giá")

    # ---------- TC-E6-04 — server từ chối đặt mặt hàng đã ngừng kinh doanh ----------
    def test_item_disabled_bi_chan_du_gui_thang_ma_hang(self):
        """thiết kế lại mua lẻ §4.1/§4.5 — TC-E6-04 đổi ý nghĩa cụ thể (cờ
        `custom_ban_le_portal` không còn là điều kiện thành viên danh mục,
        §4.1 đã bỏ hẳn lọc theo nó) nhưng GIỮ tinh thần: server không tin
        payload, tự kiểm lại đúng điều kiện danh mục THẬT SỰ đang dùng
        (`disabled=0`). Khách (hoặc client bị sửa) gửi thẳng một mã hàng đã
        `disabled=1` vào giỏ mode=ban_le — catalog không hề hiện mã này
        (test_item_disabled_khong_hien_trong_danh_muc), nhưng endpoint vẫn
        phải tự chặn lại."""
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": RETAIL_NGUNG_KD, "qty": 1}]),
                mode="ban_le", request_id=_rid(),
            )
        loi = frappe.local.response.get("loi")
        self.assertEqual(loi[0]["ly_do"], "mat_hang_ngung_kinh_doanh")

    def test_hdnt_mode_item_ngoai_hop_dong_thanh_dong_cho_bao_gia(self):
        """ĐẢO NGƯỢC 21/08/2026 (Task 4). Tên cũ `test_hdnt_mode_item_ngoai_
        hop_dong_van_bi_chan`, khẳng định cũ: mode=hdnt + một mã hàng KHÔNG
        nằm trong hợp đồng → bị chặn (`ly_do = thieu_gia` cho mặt hàng
        không có giá trong bảng giá hợp đồng, `het_han_muc` cho mặt hàng
        có giá nhưng không có dòng trong Blanket Order Item).

        Vì sao đảo: cả hai thông điệp đó đều là hệ quả của việc ÉP một
        mặt hàng ngoài hợp đồng đi qua luật của hợp đồng — `het_han_muc`
        cho một mặt hàng chưa từng có hạn mức là một câu vô nghĩa với
        khoa phòng, và `thieu_gia` biến "Miyano chưa báo giá" thành một
        lỗi CHẶN thay vì một việc cần làm. Task 4 hạ quyết định xuống
        từng dòng: mã ngoài mọi hợp đồng còn hiệu lực là DÒNG TẦNG 2 —
        vào đơn với `rate = 0` và chờ Miyano báo giá, đúng ba tầng của
        kế hoạch "gộp luồng đặt hàng".

        Bằng chứng ĐỎ của lần đảo: `AssertionError: ValidationError not
        raised`."""
        bo = hop_dong_hieu_luc_dau_tien()
        # Ca 1 — mặt hàng KHÔNG có giá trong bảng giá của hợp đồng: không
        # còn là lỗi `thieu_gia`, chỉ là một dòng chờ báo giá.
        res = portal.portal_order_place(
            bo, json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            mode="hdnt", request_id=_rid(),
        )
        # Spec 2026-10-12 §5 — "vòng báo giá của Miyano" nay là một Quotation,
        # không còn là Sales Order "Mua lẻ".
        bg = _bao_gia_cua(self, res)
        self.assertEqual(bg.items[0].item_code, RETAIL_CO_GIA)
        self.assertEqual(float(bg.items[0].rate), 0.0)
        self.assertFalse(bg.items[0].blanket_order)

        # Ca thứ hai: mặt hàng CÓ giá trong price list của khách nhưng
        # KHÔNG nằm trong Blanket Order Item của hợp đồng. Ca này chịu tải
        # NẶNG hơn ca 1 sau Task 4: nó chứng minh `rate = 0` đến từ "ngoài
        # hợp đồng", KHÔNG phải từ "tình cờ không tra được giá" — chính là
        # bẫy `price_list_rate` của ERPNext (`taxes_and_totals.calculate_
        # item_values` thay `rate = 0` bằng giá bảng giá) mà `dat_hang.
        # _xay_don` phải chặn tường minh.
        ngoai = "NGO-E6-001"
        if not frappe.db.exists("Item", ngoai):
            kho = _kho_mac_dinh()
            doc = frappe.get_doc({
                "doctype": "Item", "item_code": ngoai,
                "item_name": "Hàng ngoài HĐNT có giá HĐNT", "item_group": "Vật tư tiêu hao",
                "stock_uom": "Cái", "is_stock_item": 1,
            })
            if kho:
                doc.append("item_defaults", {"company": COMPANY, "default_warehouse": kho})
            doc.insert(ignore_permissions=True)
        if not frappe.db.exists("Item Price", {"item_code": ngoai, "price_list": PRICE_LIST, "selling": 1}):
            frappe.get_doc({
                "doctype": "Item Price", "item_code": ngoai, "price_list": PRICE_LIST,
                "uom": "Cái", "selling": 1, "price_list_rate": 15000, "currency": "VND",
            }).insert(ignore_permissions=True)

        res2 = portal.portal_order_place(
            bo, json.dumps([{"item_code": ngoai, "qty": 1}]),
            mode="hdnt", request_id=_rid(),
        )
        bg2 = _bao_gia_cua(self, res2)
        self.assertEqual(bg2.items[0].item_code, ngoai)
        self.assertEqual(
            float(bg2.items[0].rate), 0.0,
            "có giá trong bảng giá KHÔNG đồng nghĩa có hợp đồng — dòng ngoài "
            "hợp đồng phải vào đơn với rate 0 để Miyano báo giá, chứ không "
            "được âm thầm lấy giá 15000 của bảng giá",
        )
        self.assertFalse(bg2.items[0].blanket_order)

    def test_boi_so_ngay_giao_dia_chi_van_kiem_o_che_do_le(self):
        """BR-O11/O13 vẫn áp cho nhánh mua lẻ — dùng lại đúng
        `kiem_boi_so`/`kiem_ngay_giao` của nhánh HĐNT."""
        frappe.db.set_value("Item", RETAIL_CO_GIA, "custom_boi_so_dat", 5)
        try:
            with self.assertRaises(frappe.ValidationError):
                portal.portal_order_place(
                    items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 3}]),
                    mode="ban_le", request_id=_rid(),
                )
            loi = frappe.local.response.get("loi")
            self.assertEqual(loi[0]["ly_do"], "sai_boi_so")
        finally:
            frappe.db.set_value("Item", RETAIL_CO_GIA, "custom_boi_so_dat", 0)

    def test_idempotent_request_id_tra_don_cu(self):
        rid = _rid()
        res1 = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            mode="ban_le", request_id=rid,
        )
        res2 = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            mode="ban_le", request_id=rid,
        )
        # Spec 2026-10-12 §5 — giỏ này sinh Quotation; bấm lại trả đúng
        # Quotation và phiếu cũ.
        _bao_gia_cua(self, res1)
        self.assertEqual(res1["bao_gia"], res2["bao_gia"])
        self.assertEqual(res1["de_xuat"], res2["de_xuat"])
        self.assertIsNone(res2["sales_order"])
        self.assertTrue(res2["da_ton_tai"])

    # ---------- thiết kế lại mua lẻ §4.3 — dòng "đặt ngoài" ----------
    def test_dat_ngoai_luu_dung_qua_endpoint(self):
        """Dòng khách gõ thẳng (không tìm thấy mã trong danh mục) phải lưu
        vào bảng con `custom_dat_ngoai` của CHÍNH đơn đang đặt — KHÔNG sinh
        chứng từ thứ hai (§3: "không sinh chứng từ thứ hai cho khách nhìn
        thấy"). Đi qua ĐÚNG endpoint `portal_order_place`, không gọi hàm nội
        bộ với `customer` tiêm tay."""
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            dat_ngoai=json.dumps([
                {"ten_hang": "Găng tay phẫu thuật cỡ 7.5", "dvt": "Đôi", "so_luong": 20, "ghi_chu": "Hiệu Ansell"},
            ]),
            mode="ban_le", request_id=_rid(),
        )
        # Spec 2026-10-12 §5 — chứng từ đang đặt nay là một Quotation.
        bg = _bao_gia_cua(self, res)
        self.assertEqual(len(bg.custom_dat_ngoai), 1)
        dong = bg.custom_dat_ngoai[0]
        self.assertEqual(dong.ten_hang, "Găng tay phẫu thuật cỡ 7.5")
        self.assertEqual(dong.dvt, "Đôi")
        self.assertEqual(float(dong.so_luong), 20.0)
        self.assertEqual(dong.ghi_chu, "Hiệu Ansell")
        self.assertFalse(dong.item_khop)
        self.assertFalse(dong.da_xu_ly, "chưa khớp mã hàng thì chưa 'đã xử lý'")
        # Dòng "đặt ngoài" KHÔNG được lọt vào `items` (ERPNext bắt buộc
        # item_code trên mỗi Sales Order Item, §3).
        self.assertEqual(len(bg.items), 1)
        self.assertEqual(bg.items[0].item_code, RETAIL_CO_GIA)

    def test_dat_ngoai_thieu_ten_hang_bi_chan(self):
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
                dat_ngoai=json.dumps([{"ten_hang": "", "dvt": "Cái", "so_luong": 1}]),
                mode="ban_le", request_id=_rid(),
            )
        loi = frappe.local.response.get("loi")
        self.assertEqual(loi[0]["ly_do"], "dat_ngoai_thieu_ten_hang")

    def test_dat_ngoai_thieu_dvt_bi_chan(self):
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
                dat_ngoai=json.dumps([{"ten_hang": "Kim luồn 24G", "dvt": "", "so_luong": 1}]),
                mode="ban_le", request_id=_rid(),
            )
        loi = frappe.local.response.get("loi")
        self.assertEqual(loi[0]["ly_do"], "dat_ngoai_thieu_dvt")

    def test_dat_ngoai_so_luong_khong_hop_le_bi_chan(self):
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
                dat_ngoai=json.dumps([{"ten_hang": "Kim luồn 24G", "dvt": "Cái", "so_luong": 0}]),
                mode="ban_le", request_id=_rid(),
            )
        loi = frappe.local.response.get("loi")
        self.assertEqual(loi[0]["ly_do"], "dat_ngoai_so_luong_khong_hop_le")

    def test_dat_ngoai_so_luong_khong_phai_so_bi_chan_khong_500(self):
        """review Minor — `float("abc")` ném `ValueError` CHƯA BẮT trước bản
        sửa này, lọt thẳng thành HTTP 500 thay vì mã lỗi
        `dat_ngoai_so_luong_khong_hop_le` đã có sẵn cho đúng tình huống này."""
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
                dat_ngoai=json.dumps([{"ten_hang": "Kim luồn 24G", "dvt": "Cái", "so_luong": "abc"}]),
                mode="ban_le", request_id=_rid(),
            )
        loi = frappe.local.response.get("loi")
        self.assertEqual(loi[0]["ly_do"], "dat_ngoai_so_luong_khong_hop_le")

    def test_dat_ngoai_di_kem_dong_hop_dong_duoc_chap_nhan(self):
        """ĐẢO NGƯỢC 21/08/2026 (Task 4). Tên cũ `test_dat_ngoai_khong_ap_
        dung_cho_hdnt`, khẳng định cũ: "đặt ngoài" đi kèm giỏ HĐNT bị TỪ
        CHỐI RÕ ("Dòng đặt ngoài chỉ áp dụng cho chế độ Mua lẻ",
        `dat_hang.py:651`).

        Vì sao đảo: chốt đó CHÍNH LÀ vách ngăn Task 4 được giao xoá. Lập
        luận cũ ("một HĐNT chỉ gồm đúng các mặt hàng đã ký") đúng về HỢP
        ĐỒNG nhưng sai về GIỎ HÀNG: dòng đặt ngoài không nằm trong hợp
        đồng và không đòi hỏi gì ở hợp đồng — nó nằm trên `custom_dat_
        ngoai` của chính đơn, `items` không hề đụng tới. Chốt cũ buộc một
        khoa cần cả hai loại hàng phải chia làm hai đơn, hoặc bỏ cuộc.

        Bằng chứng ĐỎ của lần đảo: `AssertionError: ValidationError not
        raised`."""
        bo = hop_dong_hieu_luc_dau_tien()
        res = portal.portal_order_place(
            bo, json.dumps([{"item_code": VT_HDNT, "qty": 1}]),
            dat_ngoai=json.dumps([{"ten_hang": "X", "dvt": "Cái", "so_luong": 1}]),
            mode="hdnt", request_id=_rid(),
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        # VẾ DƯƠNG — dòng hợp đồng vẫn nguyên vẹn trong `items`, dòng đặt
        # ngoài nằm ở bảng con của nó, KHÔNG lẫn vào nhau.
        self.assertEqual([d.item_code for d in so.items], [VT_HDNT])
        # Đảo theo spec 2026-10-09 (giá theo Price List). Dòng không còn gắn
        # hợp đồng khung (§4.2).
        self.assertFalse(so.items[0].blanket_order)
        # Đảo theo spec 2026-10-09 (giá theo Price List). §4.1 — dòng gõ tay
        # luôn thuộc nhóm chờ báo giá, nên giỏ này ra HAI chứng từ: giỏ vẫn
        # được CHẤP NHẬN trong một lần bấm (điều test này canh), nhưng dòng
        # đặt ngoài nằm ở chứng từ thứ hai chứ không chung đơn với dòng có giá.
        self.assertEqual(len(res["don"]), 2)
        # Spec 2026-10-12 §5 — chứng từ thứ hai nay là một Quotation.
        bg2 = _bao_gia_cua(self, res, res["don"][1])
        self.assertEqual(len(bg2.custom_dat_ngoai), 1)
        self.assertEqual(bg2.custom_dat_ngoai[0].ten_hang, "X")

    def test_gio_hang_chi_co_dat_ngoai_van_dat_duoc(self):
        """SUPERSEDED bởi spec 2026-08-15 §3.4 (xem
        `tests/test_dat_ngoai_giu_cho.py` cho bộ test đầy đủ của thay đổi
        này). Trước §3.4, ERPNext không lưu được một Sales Order với bảng
        `items` RỖNG nên giỏ CHỈ có dòng "đặt ngoài" bị từ chối thẳng —
        nhưng đó ngược nguyên tắc nền "khách đặt hàng, Miyano có trách nhiệm
        gửi". §3.4 chèn Item giữ chỗ `HANG-DAT-NGOAI` (`portal_mua_le.
        ITEM_GIU_CHO`) để ERPNext lưu được đơn; test này giữ nguyên vị trí
        (không xoá) để đánh dấu rõ hành vi ĐÃ ĐỔI, không phải quên cập nhật."""
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps([{"ten_hang": "X", "dvt": "Cái", "so_luong": 1}]),
            mode="ban_le", request_id=_rid(),
        )
        bg = _bao_gia_cua(self, res)
        self.assertEqual([i.item_code for i in bg.items], [ITEM_GIU_CHO])

    # ---------- Việc 1 — company rỗng KHÔNG được chết đơn ----------
    def test_giao_company_rong_van_dat_duoc_don_roi_ve_company_mac_dinh(self):
        """Chủ dự án đã quyết: khi phép giao company của
        `resolve_ban_le_company()` rỗng (giỏ gồm hai mặt hàng mà Item
        Default của chúng không CHUNG company nào), đơn khách KHÔNG được
        chết vì lỗi cấu hình admin — phải tạo được, với `company` rơi về
        `Global Defaults.default_company`, để nhân viên back-office tự sửa
        trên đơn nháp nếu cần (`Sales Order.company` là `reqd=1` nên không
        thể để trống).

        Site test có sẵn HAI company thật (không phải fixture dựng riêng
        cho test này): "Miyano Việt Nam" (COMPANY, dùng bởi RETAIL_CO_GIA
        qua `_kho_mac_dinh()`) và "Miyano" (`default_company` toàn hệ
        thống). Dựng thêm MỘT item mới có Item Default CHỈ trỏ company
        "Miyano" — giao với company của RETAIL_CO_GIA ("Miyano Việt Nam")
        là tập rỗng."""
        item_khac_cong_ty = "RTL-E6-004"
        kho_mac_dinh_khac = frappe.db.get_value(
            "Warehouse", {"company": "Miyano", "is_group": 0, "warehouse_name": "Stores"}
        )
        self.assertTrue(kho_mac_dinh_khac, "fixture site phải có kho Stores cho company Miyano")
        if not frappe.db.exists("Item", item_khac_cong_ty):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": item_khac_cong_ty,
                "item_name": "Mặt hàng company khác (test rơi về mặc định)",
                "item_group": "Vật tư tiêu hao",
                "stock_uom": "Cái",
                "is_stock_item": 1,
                "item_defaults": [{"company": "Miyano", "default_warehouse": kho_mac_dinh_khac}],
            }).insert(ignore_permissions=True)

        res = portal.portal_order_place(
            items=json.dumps([
                {"item_code": RETAIL_CO_GIA, "qty": 1},
                {"item_code": item_khac_cong_ty, "qty": 1},
            ]),
            mode="ban_le", request_id=_rid(),
        )
        # Spec 2026-10-12 §5 — giỏ này sinh Quotation; phép rơi về company mặc
        # định là của `dat_hang._xay_don`, Quotation chép lại company đó.
        bg = _bao_gia_cua(self, res)
        self.assertEqual(bg.docstatus, 0, "yêu cầu phải TẠO ĐƯỢC dù phép giao company rỗng")
        self.assertEqual(
            bg.company, frappe.defaults.get_global_default("company"),
            "company phải rơi về Global Defaults.default_company khi không suy được",
        )

