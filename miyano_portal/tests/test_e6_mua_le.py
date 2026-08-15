"""E6 phần B — Mua lẻ ngoài HĐNT, giỏ 2 ngăn, báo giá hết hiệu lực.

Xem docs/Miyano-Portal(Client)_V2/DevHandoff/15_PRD_E6_MuaLe_YeuCauHang.md
(US-E6.1/E6.2/E6.5), 30_API_Spec.md (§1.1, §2.2, §2.4), 40_TestCases.md
(TC-E6-01…04, 09…11), BA §4.10 (BR-R1…R7, NL-10.x).

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

from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO, han_hieu_luc_bao_gia
from miyano_portal.setup.seed_demo import COMPANY, PRICE_LIST, seed_demo

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

    _dam_bao_item_ban_le(RETAIL_CO_GIA, "Khẩu trang y tế lẻ", 25000)
    _dam_bao_item_ban_le(RETAIL_THIEU_GIA, "Kit test nhanh lẻ", None)

    # §4.5 — item KHÔNG hoạt động (disabled=1) là chốt phòng thủ tầng hai
    # của `_xay_don_ban_le` (§4.1 chỉ còn `disabled` làm điều kiện thành
    # viên danh mục, `custom_ban_le_portal` đã xoá — Việc 2(a)).
    _dam_bao_item_ban_le(RETAIL_NGUNG_KD, "Hàng ngừng kinh doanh", None)
    frappe.db.set_value("Item", RETAIL_NGUNG_KD, "disabled", 1)


class TestCatalogBanLe(FrappeTestCase):
    def setUp(self):
        _seed_mua_le()
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- TC-E6-01 ----------
    def test_khach_chua_bat_co_bi_403(self):
        frappe.set_user(USER_PXN)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_catalog_ban_le()
        self.assertEqual(frappe.local.response.get("ly_do"), "khong_duoc_mua_le")

    # ---------- thiết kế lại mua lẻ §4.1 — bỏ lọc custom_ban_le_portal ----------
    def test_danh_muc_khong_con_loc_theo_custom_ban_le_portal(self):
        """HC0009 không hề nằm trong fixture "bán lẻ" — trước đây một cờ
        `custom_ban_le_portal` (BR-R6 cũ) quyết định thành viên danh mục,
        giờ danh mục là TOÀN BỘ `Item` với `disabled=0` (§4.1: "khách không
        cần biết Miyano có gì"). Cờ đó đã xoá hẳn (Việc 2(a),
        `patches/v1_16/xoa_custom_field_ban_le_portal.py`), tên test giữ
        nguyên để chỉ thẳng chốt hồi quy đang bảo vệ. Dùng `tim_kiem` để
        khoanh kết quả về đúng fixture, không đọc cả `tabItem` của site
        (seed_demo/demo_kho_flow còn nhiều Item khác)."""
        frappe.set_user(USER_BVBM)
        out = portal.portal_catalog_ban_le(tim_kiem="HC0009")["items"]
        ma = {r["item_code"] for r in out}
        self.assertIn("HC0009", ma, "danh mục không được lọc theo bất kỳ cờ bán lẻ nào (§4.1)")

    def test_danh_muc_van_gom_ca_item_da_bat_co_ban_le_cu(self):
        """RETAIL_CO_GIA/RETAIL_THIEU_GIA (item bình thường, không còn cờ gì
        đặc biệt kể từ khi `custom_ban_le_portal` bị xoá) vẫn phải xuất
        hiện trong danh mục — chúng hợp lệ vì có `disabled=0`, không nhờ
        một cờ bán lẻ nào."""
        frappe.set_user(USER_BVBM)
        out = portal.portal_catalog_ban_le(tim_kiem="RTL-E6-00")["items"]
        ma = {r["item_code"] for r in out}
        self.assertIn(RETAIL_CO_GIA, ma)
        self.assertIn(RETAIL_THIEU_GIA, ma)

    def test_danh_muc_khong_hien_gia(self):
        """§4.1 — "Không trả giá": không còn field `gia_ban_le`/`co_gia` nào
        trong phong bì trả về, kể cả với mặt hàng CÓ giá thật trong price
        list cũ (RETAIL_CO_GIA)."""
        frappe.set_user(USER_BVBM)
        out = portal.portal_catalog_ban_le(tim_kiem=RETAIL_CO_GIA)["items"]
        self.assertEqual(len(out), 1)
        self.assertNotIn("gia_ban_le", out[0])
        self.assertNotIn("co_gia", out[0])

    def test_item_disabled_khong_hien_trong_danh_muc(self):
        """`disabled=1` là điều kiện thành viên danh mục DUY NHẤT còn lại
        (§4.1) — mặt hàng ngừng kinh doanh vẫn phải bị loại."""
        frappe.set_user(USER_BVBM)
        out = portal.portal_catalog_ban_le(tim_kiem=RETAIL_NGUNG_KD)["items"]
        ma = {r["item_code"] for r in out}
        self.assertNotIn(RETAIL_NGUNG_KD, ma)

    def test_item_thuoc_hdnt_hieu_luc_duoc_danh_dau_br_r7(self):
        """§4.2 — GIỮ NGUYÊN: mặt hàng thuộc HĐNT còn hiệu lực vẫn hiện ra
        (khác trước: KHÔNG biến mất im lặng) nhưng phải mang cờ `thuoc_hdnt`
        để client hiện mờ + khoá nút thêm giỏ Mua lẻ."""
        frappe.set_user(USER_BVBM)
        out = portal.portal_catalog_ban_le(tim_kiem=VT_HDNT)["items"]
        theo_ma = {r["item_code"]: r for r in out}
        self.assertIn(VT_HDNT, theo_ma)
        self.assertTrue(theo_ma[VT_HDNT]["thuoc_hdnt"], "phải đánh dấu thuoc_hdnt=True (BR-R7/NL-10.7)")

        out2 = portal.portal_catalog_ban_le(tim_kiem=RETAIL_CO_GIA)["items"]
        self.assertFalse(out2[0]["thuoc_hdnt"], "item lẻ thuần không được đánh dấu nhầm")

    # ---------- thiết kế lại mua lẻ §4.1 — phân trang phía server ----------
    def test_phan_trang_khong_chong_lap_khong_bo_sot(self):
        """DoD "phân trang phía server" của thiết kế: gộp NHIỀU trang nhỏ
        (limit=1) phải phủ ĐÚNG tập fixture của test này, không thừa không
        thiếu, không trùng lặp giữa các trang — khẳng định theo TÊN bản ghi
        của chính fixture (ba mã RTL-E6-00x), không đếm tuyệt đối trên toàn
        bộ `tabItem` của site."""
        frappe.set_user(USER_BVBM)
        ky_vong = {RETAIL_CO_GIA, RETAIL_THIEU_GIA, RETAIL_NGUNG_KD}
        # RETAIL_NGUNG_KD bị lọc bởi disabled=0 — không nằm trong danh mục,
        # nên tập fixture "nhìn thấy được" chỉ còn hai mã.
        ky_vong_hien = {RETAIL_CO_GIA, RETAIL_THIEU_GIA}

        trang0 = portal.portal_catalog_ban_le(tim_kiem="RTL-E6-00", start=0, limit=1)
        self.assertEqual(len(trang0["items"]), 1)
        self.assertEqual(trang0["tong"], 2, "tong phải đếm ĐÚNG bộ filter/or_filters của trang")

        trang1 = portal.portal_catalog_ban_le(tim_kiem="RTL-E6-00", start=1, limit=1)
        self.assertEqual(len(trang1["items"]), 1)

        gop = {trang0["items"][0]["item_code"], trang1["items"][0]["item_code"]}
        self.assertEqual(gop, ky_vong_hien, "hai trang limit=1 phải PHỦ ĐỦ, không trùng, đúng hai mã fixture")

        trang2 = portal.portal_catalog_ban_le(tim_kiem="RTL-E6-00", start=2, limit=1)
        self.assertEqual(trang2["items"], [], "hết dữ liệu ở trang thứ ba")

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
        # thẳng `ordered_qty` — trường ERPNext THẬT dùng để tính hạn mức còn
        # lại (`han_muc_con`, portal_context.py) và được ERPNext core ghi
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

        res = portal.portal_order_place(
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

    # ---------- review C-1 (Critical) — chốt BR-R1 PHẢI có ở đường GHI ----------
    def test_c1_khach_chua_bat_co_khong_dat_le_duoc_qua_duong_ghi(self):
        """Bản trước chỉ kiểm `custom_cho_phep_mua_le` ở `portal_catalog_
        ban_le` (đường đọc) — PXN (chưa bật cờ) POST THẲNG `mode="ban_le"`,
        bỏ qua hẳn danh mục, vẫn nhận về một Sales Order hợp lệ. Đây là ca
        PHẢI đỏ nếu chốt này biến mất — không phải suy luận, thử phá code
        rồi khôi phục (xem báo cáo)."""
        frappe.set_user(USER_PXN)
        rid = _rid()
        with self.assertRaises(frappe.PermissionError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
                mode="ban_le", request_id=rid,
            )
        self.assertEqual(frappe.local.response.get("ly_do"), "khong_duoc_mua_le")
        self.assertFalse(frappe.db.exists("Sales Order", {"custom_request_id": rid}))

    # ---------- review C-2 (Critical) — BR-R7 không được lách qua hoa/thường ----------
    def test_c2_ma_hang_viet_thuong_van_bi_br_r7_chan(self):
        """`tabItem` chạy collation `utf8mb4_unicode_ci` (case-insensitive):
        MariaDB coi "vt0005" và "VT0005" là CÙNG một bản ghi, nhưng phép so
        `item_code in thuoc_hdnt` (Python `in` trên `set`) không biết điều
        đó. Gửi thẳng mã viết thường của mặt hàng dual-listed (VT_HDNT —
        thuộc HĐNT hiệu lực CỦA seed_demo) — PHẢI vẫn bị BR-R7 chặn, và
        lỗi phải báo đúng mã CHÍNH TẮC (không phải chuỗi thô client gõ) vì
        đó là mã Frappe thực sự sẽ lưu nếu chốt không chặn kịp."""
        rid = _rid()
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": VT_HDNT.lower(), "qty": 1}]),
                mode="ban_le", request_id=rid,
            )
        loi = frappe.local.response.get("loi")
        self.assertIsNotNone(loi)
        self.assertEqual(loi[0]["ly_do"], "thuoc_hdnt_hieu_luc")
        self.assertEqual(
            loi[0]["item_code"], VT_HDNT,
            "lỗi phải mang mã CHÍNH TẮC (Item.name), không phải chuỗi thô client gửi",
        )
        self.assertFalse(frappe.db.exists("Sales Order", {"custom_request_id": rid}))

    def test_c2_khong_ton_tai_bi_tu_choi_ngay(self):
        """Mã hàng không tra ra Item thật nào (kể cả sau chuẩn hoá) phải bị
        từ chối ngay tại vòng gộp, không lọt xuống tầng kiểm hạn mức/giá rồi
        hiện một thông điệp khó hiểu về một mặt hàng không tồn tại."""
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": "KHONG-TON-TAI-XYZ", "qty": 1}]),
                mode="ban_le", request_id=_rid(),
            )

    def test_c2_gop_dong_trung_ma_qua_khac_hoa_thuong_nhanh_hdnt(self):
        """Hệ luỵ CÙNG một lỗ ở nhánh HĐNT (không riêng BR-R7): hai dòng
        "VT0005"/"vt0005" phải GỘP thành một khi kiểm hạn mức, không tách
        đôi mỗi dòng đi qua `han_muc_con` độc lập (duplicate-line quota
        bypass qua khác hoa/thường — nợ từ E1, vá cùng chỗ với C-2)."""
        bo = portal.portal_contracts()[0]["name"]
        frappe.db.set_value(
            "Blanket Order Item", {"parent": bo, "item_code": VT_HDNT},
            {"qty": 200, "ordered_qty": 195},  # còn đúng 5
        )
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                bo,
                json.dumps([
                    {"item_code": VT_HDNT, "qty": 3},
                    {"item_code": VT_HDNT.lower(), "qty": 3},  # tổng thật = 6 > 5
                ]),
                mode="hdnt", request_id=_rid(),
            )
        loi = frappe.local.response.get("loi")
        self.assertIsNotNone(loi)
        self.assertEqual(loi[0]["ly_do"], "vuot_han_muc")

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
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(so.items[0].item_code, RETAIL_THIEU_GIA)
        self.assertEqual(float(so.items[0].rate), 0.0)
        self.assertEqual(so.workflow_state, "Chờ xác nhận")

    # ---------- TC-E6-03 / BR-R7 — chốt an ninh nghiệp vụ ----------
    def test_br_r7_item_thuoc_hdnt_hieu_luc_khong_dat_le_duoc(self):
        rid = _rid()
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal.portal_order_place(
                items=json.dumps([{"item_code": VT_HDNT, "qty": 1}]),
                mode="ban_le", request_id=rid,
            )
        loi = frappe.local.response.get("loi")
        self.assertIsNotNone(loi, "phải có phong bì lỗi máy đọc được (BR-O3)")
        self.assertEqual(loi[0]["ly_do"], "thuoc_hdnt_hieu_luc")
        self.assertIn(VT_HDNT, str(ctx.exception))
        # Không có Sales Order "Mua lẻ" nào được tạo ra cho request_id này —
        # BR-R7 phải chặn TRƯỚC khi ghi, không phải ghi rồi mới xin lỗi.
        self.assertFalse(frappe.db.exists("Sales Order", {"custom_request_id": rid}))

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

    def test_hdnt_mode_item_ngoai_hop_dong_van_bi_chan(self):
        """Chiều ngược lại của "trộn dòng": mode=hdnt nhưng gửi một mã hàng
        không nằm trong chính hợp đồng đó — vẫn phải bị chặn (không lọt qua
        vì "nó có trong danh mục lẻ").

        review I-1 — bản trước chỉ `assertRaises(ValidationError)` không
        khẳng định `ly_do`; trên thực tế ca này đỏ vì `thieu_gia` (RETAIL_
        CO_GIA không có giá trong `PRICE_LIST` của HĐNT), KHÔNG PHẢI vì
        "ngoài hợp đồng" — hai lý do khác hẳn nhau về mặt nghiệp vụ, test
        cũ tình cờ pass mà không kiểm đúng thứ nó tuyên bố. Khẳng định rõ
        `ly_do == "het_han_muc"`, và thêm ca thứ hai dùng mặt hàng CÓ giá
        trong price list của khách nhưng KHÔNG có trong HĐNT — tách bạch
        "thiếu giá" khỏi "ngoài hợp đồng"."""
        bo = portal.portal_contracts()[0]["name"]
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                bo, json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
                mode="hdnt", request_id=_rid(),
            )
        loi = frappe.local.response.get("loi")
        self.assertIsNotNone(loi)
        self.assertEqual(
            loi[0]["ly_do"], "thieu_gia",
            "RETAIL_CO_GIA không có Item Price trong PRICE_LIST của HĐNT",
        )

        # Ca thứ hai: mặt hàng CÓ giá trong price list của khách (không bị
        # chặn vì thiếu giá) nhưng KHÔNG nằm trong Blanket Order Item của
        # hợp đồng — phải bị chặn đúng vì lý do hạn mức (không thuộc HĐNT),
        # tách bạch khỏi "thiếu giá" của ca trên.
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

        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                bo, json.dumps([{"item_code": ngoai, "qty": 1}]),
                mode="hdnt", request_id=_rid(),
            )
        loi2 = frappe.local.response.get("loi")
        self.assertIsNotNone(loi2)
        self.assertEqual(
            loi2[0]["ly_do"], "het_han_muc",
            "có giá không đồng nghĩa có hạn mức — mặt hàng không có dòng "
            "trong Blanket Order Item nên con_lai=0 (het_han_muc)",
        )

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
        self.assertEqual(res1["sales_order"], res2["sales_order"])
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
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(len(so.custom_dat_ngoai), 1)
        dong = so.custom_dat_ngoai[0]
        self.assertEqual(dong.ten_hang, "Găng tay phẫu thuật cỡ 7.5")
        self.assertEqual(dong.dvt, "Đôi")
        self.assertEqual(float(dong.so_luong), 20.0)
        self.assertEqual(dong.ghi_chu, "Hiệu Ansell")
        self.assertFalse(dong.item_khop)
        self.assertFalse(dong.da_xu_ly, "chưa khớp mã hàng thì chưa 'đã xử lý'")
        # Dòng "đặt ngoài" KHÔNG được lọt vào `items` (ERPNext bắt buộc
        # item_code trên mỗi Sales Order Item, §3).
        self.assertEqual(len(so.items), 1)
        self.assertEqual(so.items[0].item_code, RETAIL_CO_GIA)

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

    def test_dat_ngoai_khong_ap_dung_cho_hdnt(self):
        """§4.3/§4.7 — nhóm "đặt ngoài" chỉ áp dụng cho Mua lẻ; một HĐNT chỉ
        gồm đúng các mặt hàng đã ký, không có khái niệm "chưa có trong kho,
        cần đặt ngoài". Server phải TỪ CHỐI RÕ, không lặng lẽ bỏ qua."""
        bo = portal.portal_contracts()[0]["name"]
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                bo, json.dumps([{"item_code": VT_HDNT, "qty": 1}]),
                dat_ngoai=json.dumps([{"ten_hang": "X", "dvt": "Cái", "so_luong": 1}]),
                mode="hdnt", request_id=_rid(),
            )
        # Chưa insert đơn nào — lỗi phải chặn TRƯỚC khi ghi.

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
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual([i.item_code for i in so.items], [ITEM_GIU_CHO])

    # ---------- thiết kế lại mua lẻ §4.3/§4.4 — đồng bộ da_xu_ly + chốt xác nhận ----------
    def test_da_xu_ly_tu_dong_theo_item_khop(self):
        """Nhân viên khớp `item_khop` (đi qua Desk, mô phỏng bằng `doc.save()`
        THẬT — không phải `frappe.db.set_value` bypass, vì chính hook đang
        được kiểm ở đây) — `da_xu_ly` phải TỰ chuyển 1, không ai được tự tay
        tick field `read_only` này."""
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            dat_ngoai=json.dumps([{"ten_hang": "Kim luồn 24G", "dvt": "Cái", "so_luong": 10}]),
            mode="ban_le", request_id=_rid(),
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertFalse(so.custom_dat_ngoai[0].da_xu_ly)

        so.custom_dat_ngoai[0].item_khop = RETAIL_CO_GIA
        so.save(ignore_permissions=True)
        so.reload()
        self.assertEqual(so.custom_dat_ngoai[0].item_khop, RETAIL_CO_GIA)
        self.assertTrue(so.custom_dat_ngoai[0].da_xu_ly, "item_khop có giá trị -> da_xu_ly phải tự =1")

    def test_khong_xac_nhan_duoc_khi_con_dong_dat_ngoai_chua_xu_ly(self):
        """thiết kế lại mua lẻ §4.4 — CHỐT MỚI: `before_submit` chặn khi còn
        dòng đặt ngoài chưa khớp `item_khop`. Không có chốt này, một đơn có
        thể được duyệt/giao trong khi khách vẫn còn yêu cầu chưa ai đụng
        tới — khách trả tiền cho thứ họ không nhận được."""
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            dat_ngoai=json.dumps([{"ten_hang": "Kim luồn 24G", "dvt": "Cái", "so_luong": 10}]),
            mode="ban_le", request_id=_rid(),
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        so.items[0].rate = 25000
        so.taxes = []
        so.taxes_and_charges = None
        with self.assertRaises(frappe.ValidationError):
            so.submit()
        so.reload()
        self.assertEqual(so.docstatus, 0, "chốt phải chặn TRƯỚC khi ghi nhận submit")

        # Khớp mã hàng cho dòng đặt ngoài rồi mới submit được.
        so.custom_dat_ngoai[0].item_khop = RETAIL_THIEU_GIA
        so.save(ignore_permissions=True)
        so.reload()
        so.submit()
        self.assertEqual(so.docstatus, 1)

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
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(so.docstatus, 0, "đơn phải TẠO ĐƯỢC dù phép giao company rỗng")
        self.assertEqual(
            so.company, frappe.defaults.get_global_default("company"),
            "company phải rơi về Global Defaults.default_company khi không suy được",
        )


def _tao_so_bao_gia(customer, item_code, gia, ngay_lap=None, yeu_cau=None):
    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = COMPANY
    so.transaction_date = ngay_lap or frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(so.transaction_date, 7)
    so.selling_price_list = PRICE_LIST
    so.custom_nguon_don = "Client Portal"
    so.custom_loai_don = "Mua lẻ"
    if yeu_cau:
        so.custom_yeu_cau_goc = yeu_cau
    so.append("items", {
        "item_code": item_code, "qty": 1, "rate": gia,
        "delivery_date": so.delivery_date,
    })
    so.taxes = []
    so.taxes_and_charges = None
    so.insert(ignore_permissions=True)
    # BẪY 4 — không gán workflow_state trước insert().
    frappe.db.set_value(
        "Sales Order", so.name, "workflow_state", "Chờ khách đồng ý",
        update_modified=False,
    )
    so.reload()
    return so


def _tao_yeu_cau_da_bao_gia(customer, nguoi_yeu_cau) -> str:
    """Mô phỏng US-E6.5: sales đã chốt giá cho một Portal Item Request, đưa
    nó về "Đã báo giá" (đi qua đúng cạnh hợp lệ Mới -> Đang tìm nguồn ->
    Đã báo giá của BR-Y1, không nhảy cóc)."""
    doc = frappe.new_doc("Portal Item Request")
    doc.customer = customer
    doc.nguoi_yeu_cau = nguoi_yeu_cau
    doc.trang_thai = "Mới"
    doc.loai = "Báo giá mua lẻ"
    doc.ten_hang = "Kit test nhanh lẻ (yêu cầu báo giá)"
    doc.dvt = "Hộp"
    doc.so_luong_du_kien = 5
    doc.insert(ignore_permissions=True)
    doc.trang_thai = "Đang tìm nguồn"
    doc.save(ignore_permissions=True)
    doc.trang_thai = "Đã báo giá"
    doc.gia_bao = 25000
    doc.save(ignore_permissions=True)
    return doc.name


class TestBaoGiaChoKhachDongY(FrappeTestCase):
    def setUp(self):
        _seed_mua_le()
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- TC-E6-09 ----------
    def test_dong_y_chuyen_yeu_cau_goc_thanh_da_chuyen_don(self):
        yc = _tao_yeu_cau_da_bao_gia(BVBM, USER_BVBM)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, yeu_cau=yc)

        frappe.set_user(USER_BVBM)
        kq = portal.portal_order_accept(so.name, "dong_y")
        self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")

        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Portal Item Request", yc, "trang_thai"),
            "Đã chuyển thành đơn",
        )
        self.assertEqual(
            frappe.db.get_value("Portal Item Request", yc, "don_lien_ket"), so.name
        )

    # ---------- TC-E6-10 ----------
    def test_khong_dong_y_luu_ly_do_tren_ca_so_va_yeu_cau_goc(self):
        """TC-E6-10 — vế "lý do lưu": BA §4.10/review I-5 đòi lý do không
        đồng ý lưu vào CẢ đơn LẪN yêu cầu gốc (`cap_nhat_yeu_cau_goc` không
        chạy cho `khong_dong_y`; `portal_order_accept` tự thêm Comment thứ
        hai lên `Portal Item Request` — xem đoạn code ngay dưới nhánh
        `elif action == "khong_dong_y"`). Trước bản sửa này, module E6 KHÔNG
        có test nào gọi `khong_dong_y` — báo cáo kiểm thử hệ thống mục 1 nêu
        "cả hai module vẫn xanh" khi hạ ngưỡng lý do, nhưng với module này lý
        do đơn giản là chưa ai đứng trên đường nó đi qua, không phải vì có
        chốt bảo vệ. Ranh giới độ dài (5/15 ký tự) đã có ở
        `test_e2_workflow_va_accept.py`; test này bổ sung phần LƯU TRỮ mà
        module đó không dựng được (không có `custom_yeu_cau_goc`)."""
        yc = _tao_yeu_cau_da_bao_gia(BVBM, USER_BVBM)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, yeu_cau=yc)
        ly_do_15 = "Giá quá cao rồi"
        self.assertEqual(len(ly_do_15), 15, "fixture sai — TC đòi đúng 15 ký tự")

        frappe.set_user(USER_BVBM)
        kq = portal.portal_order_accept(so.name, "khong_dong_y", ly_do=ly_do_15)
        self.assertEqual(kq["trang_thai_moi"], "Chờ xác nhận")

        frappe.set_user("Administrator")
        cmt_so = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Sales Order", "reference_name": so.name},
            pluck="content",
        )
        self.assertTrue(
            any(ly_do_15 in (c or "") for c in cmt_so),
            "lý do phải truy vết được trên chính đơn hàng",
        )
        cmt_yc = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Portal Item Request", "reference_name": yc},
            pluck="content",
        )
        self.assertTrue(
            any(ly_do_15 in (c or "") for c in cmt_yc),
            "lý do phải truy vết được trên yêu cầu gốc — BA §4.10 đòi lưu CẢ HAI nơi",
        )

    # ---------- TC-E6-11 ----------
    def test_qua_han_hieu_luc_bi_chan_417(self):
        """Lập SO với ngày lập 8 ngày trước — hiệu lực mặc định 7 ngày nên
        đã hết hạn 1 ngày. `portal_order_accept` phải chặn TRƯỚC khi xử lý
        action (kể cả 'dong_y'), không cho khách chốt một báo giá đã nguội."""
        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -8)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, ngay_lap=ngay_lap)

        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_accept(so.name, "dong_y")
        self.assertEqual(frappe.local.response.get("ly_do"), "qua_han_hieu_luc")

        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "workflow_state"),
            "Chờ khách đồng ý",
            "chưa quá job daily quét thì trạng thái đơn KHÔNG được tự đổi bởi accept",
        )

    def test_dung_han_7_ngay_van_dong_y_duoc(self):
        """Biên: ngày lập = hôm nay, hiệu lực 7 ngày — accept phải ĐI QUA
        được, không lệch một ngày so với job daily."""
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000)
        frappe.set_user(USER_BVBM)
        kq = portal.portal_order_accept(so.name, "dong_y")
        self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")

    def test_settings_chua_cau_hinh_hieu_luc_roi_ve_mac_dinh_7(self):
        """`hieu_luc_bao_gia_ngay` không có dòng trong Singles (xoá tường
        minh, mô phỏng site chưa từng lưu Settings) — `get_single_value`
        trả `None`, code PHẢI tự rơi về 7, không phải 0 hay lỗi."""
        frappe.db.sql(
            "delete from `tabSingles` where doctype='Miyano Portal Settings' and field='hieu_luc_bao_gia_ngay'"
        )
        # review T-3 — SQL thô đi THẲNG xuống DB, không qua
        # `frappe.db.set_value`/`set_single_value` nên KHÔNG tự xoá
        # `Database.value_cache`. `_seed_mua_le()` gọi `set_single_value(...,
        # 7)` trước đó trong `setUp` — nếu bất cứ gì đọc field này giữa lúc
        # đó và dòng SQL trên (rất dễ xảy ra khi code thay đổi sau này) thì
        # cache còn giữ 7 và DELETE phía trên trở thành vô nghĩa — ca này
        # trước đây "còn ý nghĩa" chỉ vì TÌNH CỜ không có gì đọc field ở
        # giữa. Xoá cache tường minh, không phụ thuộc vào sự tình cờ đó.
        frappe.db.value_cache.pop("Miyano Portal Settings", None)
        # Ngày lập 6 ngày trước: còn hạn nếu mặc định ĐÚNG LÀ 7, đã quá hạn
        # nếu code lỡ rơi về 0 (mọi báo giá coi như hết hạn ngay khi lập).
        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -6)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, ngay_lap=ngay_lap)
        frappe.set_user(USER_BVBM)
        kq = portal.portal_order_accept(so.name, "dong_y")
        self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")

    def test_chap_nhan_trong_order_track_khi_dang_cho_khach(self):
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000)
        frappe.set_user(USER_BVBM)
        info = portal.portal_order_track(so.name)
        self.assertIsNotNone(info["chap_nhan"])
        self.assertTrue(info["chap_nhan"]["can_dong_y"])
        self.assertEqual(
            info["chap_nhan"]["han_hieu_luc"],
            str(frappe.utils.add_days(so.transaction_date, 7)),
        )

    # ---------- review I-2(a) round 2 — mốc hiệu lực là NGÀY GỬI, không phải NGÀY LẬP ----------
    def test_han_hieu_luc_tinh_tu_ngay_gui_khach_duyet_khong_phai_ngay_lap(self):
        """Sales lập nháp 10 ngày trước, HÔM NAY mới bấm 'Gửi khách duyệt'.
        Dùng transition THẬT qua `apply_workflow` (đúng đường Desk sales
        dùng, kích hoạt hook `validate`) — không phải `db.set_value` bypass
        như các fixture khác trong file này (`_tao_so_bao_gia`), vì chính
        hook đang được kiểm ở đây. Hạn hiệu lực phải tính từ HÔM NAY (ngày
        gửi), không phải 10 ngày trước (ngày lập) — đúng quyết định nghiệp
        vụ: "ngày lập báo giá" = ngày báo giá đến tay khách."""
        from frappe.model.workflow import apply_workflow

        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -10)
        so = frappe.new_doc("Sales Order")
        so.customer = BVBM
        so.company = COMPANY
        so.transaction_date = ngay_lap
        so.delivery_date = frappe.utils.add_days(ngay_lap, 20)
        so.selling_price_list = PRICE_LIST
        so.custom_nguon_don = "Client Portal"
        so.custom_loai_don = "Mua lẻ"
        so.append("items", {
            "item_code": RETAIL_CO_GIA, "qty": 1, "rate": 25000,
            "delivery_date": so.delivery_date,
        })
        so.taxes = []
        so.taxes_and_charges = None
        so.insert(ignore_permissions=True)  # workflow_state mặc định "Chờ xác nhận"

        frappe.set_user("Administrator")
        so = apply_workflow(so, "Gửi khách duyệt")  # transition THẬT — kích hoạt hook validate

        self.assertEqual(
            so.custom_ngay_gui_khach_duyet, frappe.utils.today(),
            "hook validate phải tự ghi NGÀY HÔM NAY khi đơn chuyển vào Chờ khách đồng ý",
        )
        # `han_hieu_luc_bao_gia` trả `date` (qua `getdate`); `add_days` giữ
        # nguyên kiểu chuỗi của `frappe.utils.today()` — bọc `getdate()` ở
        # vế kỳ vọng để so đúng kiểu, không phải so lệch kiểu ngẫu nhiên.
        han = han_hieu_luc_bao_gia(so)
        self.assertEqual(
            han, frappe.utils.getdate(frappe.utils.add_days(frappe.utils.today(), 7)),
            "hạn phải tính từ ngày GỬI (hôm nay), không phải transaction_date",
        )
        self.assertNotEqual(
            han, frappe.utils.getdate(frappe.utils.add_days(ngay_lap, 7)),
            "phải KHÁC hạn tính từ ngày lập 10 ngày trước — đây chính là bug I-2(a)",
        )

    def test_ngay_gui_khach_duyet_reset_khi_gui_lai_sau_khi_bi_tu_choi(self):
        """Khách Không đồng ý -> đơn về 'Chờ xác nhận' -> sales sửa giá rồi
        gửi lại -> đồng hồ hiệu lực phải RESET theo lần gửi MỚI, không giữ
        mốc của lần gửi đầu đã bị từ chối."""
        from frappe.model.workflow import apply_workflow

        so = frappe.new_doc("Sales Order")
        so.customer = BVBM
        so.company = COMPANY
        so.transaction_date = frappe.utils.today()
        so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 10)
        so.selling_price_list = PRICE_LIST
        so.custom_nguon_don = "Client Portal"
        so.custom_loai_don = "Mua lẻ"
        so.append("items", {
            "item_code": RETAIL_CO_GIA, "qty": 1, "rate": 25000,
            "delivery_date": so.delivery_date,
        })
        so.taxes = []
        so.taxes_and_charges = None
        so.insert(ignore_permissions=True)

        frappe.set_user("Administrator")
        so = apply_workflow(so, "Gửi khách duyệt")
        lan_1 = so.custom_ngay_gui_khach_duyet
        self.assertEqual(lan_1, frappe.utils.today())

        # Giả lập "vài ngày sau" khách không đồng ý — lùi ngày gửi lần 1 lại
        # để phân biệt được với lần gửi lại (nếu không reset, hai giá trị
        # sẽ trùng nhau và test không phân biệt được lỗi).
        frappe.db.set_value(
            "Sales Order", so.name, "custom_ngay_gui_khach_duyet",
            frappe.utils.add_days(frappe.utils.today(), -3), update_modified=False,
        )
        so.reload()
        so = apply_workflow(so, "Khách không đồng ý")
        self.assertEqual(so.workflow_state, "Chờ xác nhận")

        # Sales sửa giá rồi gửi lại — mốc phải RESET về hôm nay.
        so = apply_workflow(so, "Gửi khách duyệt")
        self.assertEqual(
            so.custom_ngay_gui_khach_duyet, frappe.utils.today(),
            "gửi lại sau khi bị từ chối phải reset mốc hiệu lực về ngày gửi lại",
        )


    # ---------- thiết kế lại mua lẻ §4.6 — thông báo khi báo giá sẵn sàng ----------
    def test_thong_bao_bao_gia_san_sang_khi_vao_cho_khach_dong_y(self):
        """§4.6 — khách nhận thông báo TRÊN CHÍNH đơn (Notification Log,
        "trên chính đơn đặt hàng") kèm email, khi đơn CHUYỂN VÀO "Chờ khách
        đồng ý". Nội dung phải nêu mã đơn, tổng giá trị, VÀ hạn hiệu lực báo
        giá — mốc đọc từ `custom_ngay_gui_khach_duyet` (không phải
        `transaction_date`, review I-2(a) round 2).

        Transition THẬT qua `apply_workflow` (đúng đường sales dùng trên
        Desk), không phải `frappe.db.set_value` bypass — chính sự kiện
        "Value Change" của cơ chế Notification chuẩn Frappe cần một
        `doc.save()` thật để kích hoạt (`Document.run_notifications`)."""
        from frappe.model.workflow import apply_workflow

        frappe.flags.mute_emails = True
        self.addCleanup(frappe.flags.pop, "mute_emails", None)

        so = frappe.new_doc("Sales Order")
        so.customer = BVBM
        so.company = COMPANY
        so.transaction_date = frappe.utils.today()
        so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 10)
        so.selling_price_list = PRICE_LIST
        so.custom_nguon_don = "Client Portal"
        so.custom_loai_don = "Mua lẻ"
        so.contact_email = USER_BVBM
        so.append("items", {
            "item_code": RETAIL_CO_GIA, "qty": 2, "rate": 25000,
            "delivery_date": so.delivery_date,
        })
        so.taxes = []
        so.taxes_and_charges = None
        so.insert(ignore_permissions=True)

        # Dọn sạch trước — mã `so.name` mới `insert()` xong nên về lý
        # thuyết không thể trùng dữ liệu cũ, nhưng dọn tường minh vẫn rẻ hơn
        # là tin vào đó.
        frappe.db.delete("Notification Log", {"document_name": so.name})
        frappe.db.delete("Email Queue", {"reference_name": so.name})

        frappe.set_user("Administrator")
        so = apply_workflow(so, "Gửi khách duyệt")
        self.assertEqual(so.workflow_state, "Chờ khách đồng ý")

        han_ky_vong = han_hieu_luc_bao_gia(so).strftime("%d/%m/%Y")

        logs = frappe.get_all(
            "Notification Log",
            filters={"document_type": "Sales Order", "document_name": so.name},
            fields=["email_content", "subject", "for_user"],
        )
        self.assertTrue(logs, "phải có Notification Log TRÊN CHÍNH đơn (§4.6)")
        log = logs[0]
        self.assertEqual(log.for_user, USER_BVBM)
        self.assertIn(so.name, log.email_content)
        self.assertIn(han_ky_vong, log.email_content, "phải nêu đúng hạn hiệu lực báo giá")
        tong_ky_vong = frappe.utils.fmt_money(so.grand_total, currency="VND")
        self.assertIn(tong_ky_vong, log.email_content, "phải nêu tổng giá trị đơn")

        nguoi_nhan_email = set(frappe.get_all(
            "Email Queue Recipient",
            filters={"parent": ["in", frappe.get_all(
                "Email Queue", filters={"reference_name": so.name}, pluck="name",
            )]},
            pluck="recipient",
        ))
        self.assertIn(USER_BVBM, nguoi_nhan_email, "phải kèm email (§4.6: 'kèm email theo khuôn Notification')")


class TestJobBaoGiaHetHan(FrappeTestCase):
    def setUp(self):
        _seed_mua_le()
        self.addCleanup(frappe.set_user, "Administrator")

    def test_quet_dong_don_qua_han_va_cap_nhat_yeu_cau_goc(self):
        # review T-2 — KHÔNG đếm tuyệt đối (`assertEqual(dem, 1)`): `dem` là
        # tổng số đơn quá hạn TRONG TOÀN DB tại thời điểm gọi, không phải
        # dữ liệu do `setUp` của lớp này kiểm soát — một class test khác
        # chạy trước trong CÙNG tiến trình `run-tests` mà lỡ để lại một SO
        # "Mua lẻ"/"Chờ khách đồng ý" quá hạn sẽ âm thầm đổi con số này.
        # Khẳng định theo TÊN bản ghi của chính test này.
        from miyano_portal.portal_bao_gia import quet_bao_gia_het_han

        yc = _tao_yeu_cau_da_bao_gia(BVBM, USER_BVBM)
        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -8)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, ngay_lap=ngay_lap, yeu_cau=yc)

        # Một SO KHÁC còn trong hạn — không được job này đụng tới.
        so_con_han = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000)

        quet_bao_gia_het_han()

        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "workflow_state"),
            "Báo giá hết hạn",
        )
        self.assertEqual(
            frappe.db.get_value("Sales Order", so_con_han.name, "workflow_state"),
            "Chờ khách đồng ý",
            "đơn còn hạn không được job đụng tới",
        )
        self.assertEqual(
            frappe.db.get_value("Portal Item Request", yc, "trang_thai"), "Hết hạn"
        )

    def test_quet_khong_dong_lai_don_da_dong(self):
        """Chạy job hai lần liên tiếp không được đóng lại đơn đã đóng (job
        chạy `daily`, không phải một lần trong đời).

        review T-2 — không đếm tuyệt đối `dem`, khẳng định qua `modified`
        của ĐÚNG bản ghi của test này: nếu job lỡ xử lý lại đơn đã đóng,
        `apply_workflow`/`add_comment` sẽ đổi `modified`, dù `dem` trả về ở
        lần gọi thứ hai có thể vẫn là 0 vì lý do khác (ví dụ đơn khác trong
        DB làm `dem` lệch) — đếm tuyệt đối không phát hiện được ca đó.
        """
        from miyano_portal.portal_bao_gia import quet_bao_gia_het_han

        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -8)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, ngay_lap=ngay_lap)

        quet_bao_gia_het_han()
        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "workflow_state"), "Báo giá hết hạn"
        )
        modified_lan_1 = frappe.db.get_value("Sales Order", so.name, "modified")

        quet_bao_gia_het_han()
        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "modified"), modified_lan_1,
            "job chạy lần 2 không được đụng lại đơn đã đóng ở lần 1",
        )

    def test_gui_email_hai_phia(self):
        # Site test không cấu hình Email Account mặc định — `frappe.sendmail`
        # ném `OutgoingEmailError` ngay ở bước resolve tài khoản gửi (trước
        # cả khi kịp queue), bất kể `now=False`. `EmailAccount.find_outgoing`
        # tự rơi về một tài khoản "dummy" khi `frappe.flags.mute_emails`
        # được bật (are_emails_muted()) — đây là cơ chế test chuẩn của
        # Frappe, không phải patch riêng của app này. Đặt/thu hồi cờ đúng
        # phạm vi MỘT test: `frappe.flags` là dict toàn tiến trình, KHÔNG
        # theo giao dịch DB nên không tự rollback theo `FrappeTestCase` —
        # rò cờ này sang class test khác chạy sau trong CÙNG tiến trình
        # `run-tests` sẽ khiến các test khác vô tình mute email thật.
        frappe.flags.mute_emails = True
        self.addCleanup(frappe.flags.pop, "mute_emails", None)

        frappe.db.set_value("Customer", BVBM, "account_manager", "sales_user@demo.miyano")
        from miyano_portal.portal_bao_gia import quet_bao_gia_het_han

        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -8)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, ngay_lap=ngay_lap)
        frappe.db.set_value("Sales Order", so.name, "contact_email", USER_BVBM, update_modified=False)

        frappe.db.delete("Email Queue", {"reference_name": so.name})
        quet_bao_gia_het_han()

        nguoi_nhan = set(frappe.get_all(
            "Email Queue Recipient",
            filters={"parent": ["in", frappe.get_all(
                "Email Queue", filters={"reference_name": so.name}, pluck="name",
            )]},
            pluck="recipient",
        ))
        self.assertIn(USER_BVBM, nguoi_nhan, "khách phải nhận email báo hết hạn")
        self.assertIn(
            "sales_user@demo.miyano", nguoi_nhan, "sales phụ trách (Miyano) phải nhận email — 'hai phía'",
        )


def _tao_so_dat_ngoai_cho_khach(customer, user, items=None, dat_ngoai=None):
    """Dựng SO "Chờ khách đồng ý" đi qua ĐÚNG `portal_order_place` (không
    viết tay `Sales Order`/`custom_dat_ngoai`) — cùng lý do
    `test_han_hieu_luc_tinh_tu_ngay_gui_khach_duyet_khong_phai_ngay_lap` dùng
    `apply_workflow` thật thay vì `db.set_value` khi test đang cần bảng con
    `custom_dat_ngoai` có `name`/`idx` THẬT như production (không phải một
    dict tay không có định danh ổn định để khớp trong
    `portal_order_sua_so_luong`)."""
    frappe.set_user(user)
    res = portal.portal_order_place(
        items=json.dumps(items or []),
        dat_ngoai=json.dumps(dat_ngoai or []),
        mode="ban_le", request_id=_rid(),
    )
    frappe.set_user("Administrator")
    frappe.db.set_value(
        "Sales Order", res["sales_order"], "workflow_state", "Chờ khách đồng ý",
        update_modified=False,
    )
    return frappe.get_doc("Sales Order", res["sales_order"])


# ---------- Việc 1/brief 2026-08-15 (bao-gia-hai-chieu) — portal_order_sua_so_luong ----------
class TestSuaSoLuong(FrappeTestCase):
    def setUp(self):
        _seed_mua_le()
        self.addCleanup(frappe.set_user, "Administrator")

    def test_sua_so_luong_ve_cho_xac_nhan_rate_ve_0(self):
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000)
        row_name = so.items[0].name

        frappe.set_user(USER_BVBM)
        kq = portal.portal_order_sua_so_luong(
            so.name, json.dumps({"items": [{"item_code": RETAIL_CO_GIA, "qty": 5}]})
        )
        self.assertEqual(kq["trang_thai_moi"], "Chờ xác nhận")

        # Đọc THẲNG từ DB (không phải doc trong bộ nhớ) — chứng minh giá trị
        # đã THỰC SỰ được lưu qua `so.save()`, không chỉ đúng trên object
        # Python đang giữ trước khi `apply_workflow` load lại từ DB.
        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "workflow_state"), "Chờ xác nhận"
        )
        self.assertEqual(float(frappe.db.get_value("Sales Order Item", row_name, "qty")), 5.0)
        self.assertEqual(
            float(frappe.db.get_value("Sales Order Item", row_name, "rate")), 0.0,
            "báo giá cũ không còn hiệu lực ở số lượng mới — rate phải về 0",
        )

        cmt = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Sales Order", "reference_name": so.name},
            pluck="content",
        )
        self.assertTrue(
            any(RETAIL_CO_GIA in (c or "") and "5" in (c or "") and "1" in (c or "") for c in cmt),
            "Comment phải ghi rõ cũ -> mới",
        )

    def test_qua_han_hieu_luc_bi_chan(self):
        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -8)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, ngay_lap=ngay_lap)

        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_sua_so_luong(
                so.name, json.dumps({"items": [{"item_code": RETAIL_CO_GIA, "qty": 3}]})
            )
        self.assertEqual(frappe.local.response.get("ly_do"), "qua_han_hieu_luc")
        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "workflow_state"), "Chờ khách đồng ý",
            "báo giá hết hạn bị chặn TRƯỚC khi đụng gì tới đơn",
        )

    def test_don_khach_khac_bi_chan(self):
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000)

        frappe.set_user(USER_PXN)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_order_sua_so_luong(
                so.name, json.dumps({"items": [{"item_code": RETAIL_CO_GIA, "qty": 3}]})
            )

    def test_payload_co_doi_rate_bi_bo_qua(self):
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000)
        row_name = so.items[0].name

        frappe.set_user(USER_BVBM)
        portal.portal_order_sua_so_luong(
            so.name,
            json.dumps({"items": [{"item_code": RETAIL_CO_GIA, "qty": 3, "rate": 999999}]}),
        )
        self.assertEqual(
            float(frappe.db.get_value("Sales Order Item", row_name, "rate")), 0.0,
            "rate client gửi lên phải bị bỏ qua hoàn toàn — server luôn tự đặt 0",
        )

    def test_payload_them_dong_moi_bi_tu_choi(self):
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000)

        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_sua_so_luong(
                so.name,
                json.dumps({"items": [{"item_code": RETAIL_THIEU_GIA, "qty": 2}]}),
            )
        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "workflow_state"), "Chờ khách đồng ý",
            "thêm dòng mới bị từ chối thì đơn KHÔNG được đổi trạng thái",
        )

    def test_bo_het_moi_dong_bi_chan_huong_sang_nut_huy(self):
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000)

        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.ValidationError) as cm:
            portal.portal_order_sua_so_luong(
                so.name, json.dumps({"items": [{"item_code": RETAIL_CO_GIA, "qty": 0}]})
            )
        self.assertIn("Huỷ", str(cm.exception))

    def test_khong_ap_dung_cho_don_hdnt(self):
        """Đơn HĐNT ở "Chờ khách đồng ý" (luồng E2 gốc, US-E2.5) không phải
        Mua lẻ — sửa số lượng chỉ có nghĩa cho nhánh QT10."""
        so = frappe.new_doc("Sales Order")
        so.customer = BVBM
        so.company = COMPANY
        so.transaction_date = frappe.utils.today()
        so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 7)
        so.selling_price_list = PRICE_LIST
        so.custom_nguon_don = "Client Portal"
        so.append("items", {
            "item_code": VT_HDNT, "qty": 1, "rate": 1000, "delivery_date": so.delivery_date,
        })
        so.taxes = []
        so.taxes_and_charges = None
        so.insert(ignore_permissions=True)
        frappe.db.set_value(
            "Sales Order", so.name, "workflow_state", "Chờ khách đồng ý", update_modified=False
        )

        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_sua_so_luong(
                so.name, json.dumps({"items": [{"item_code": VT_HDNT, "qty": 2}]})
            )

    def test_dat_ngoai_ve_0_khong_can_placeholder_khi_con_hang_that(self):
        so = _tao_so_dat_ngoai_cho_khach(
            BVBM, USER_BVBM,
            items=[{"item_code": RETAIL_CO_GIA, "qty": 2}],
            dat_ngoai=[{"ten_hang": "Kim luồn 24G", "dvt": "Cái", "so_luong": 5}],
        )
        dn_name = so.custom_dat_ngoai[0].name

        frappe.set_user(USER_BVBM)
        kq = portal.portal_order_sua_so_luong(
            so.name, json.dumps({"dat_ngoai": [{"name": dn_name, "qty": 0}]})
        )
        self.assertEqual(kq["trang_thai_moi"], "Chờ xác nhận")

        so.reload()
        self.assertEqual(len(so.custom_dat_ngoai), 0)
        self.assertEqual(len(so.items), 1, "mặt hàng thật vẫn còn — không cần chèn placeholder")
        self.assertEqual(so.items[0].item_code, RETAIL_CO_GIA)

    def test_items_ve_0_con_dat_ngoai_thi_chen_placeholder(self):
        so = _tao_so_dat_ngoai_cho_khach(
            BVBM, USER_BVBM,
            items=[{"item_code": RETAIL_CO_GIA, "qty": 2}],
            dat_ngoai=[{"ten_hang": "Kim luồn 24G", "dvt": "Cái", "so_luong": 5}],
        )

        frappe.set_user(USER_BVBM)
        kq = portal.portal_order_sua_so_luong(
            so.name, json.dumps({"items": [{"item_code": RETAIL_CO_GIA, "qty": 0}]})
        )
        self.assertEqual(kq["trang_thai_moi"], "Chờ xác nhận")

        so.reload()
        ma = {i.item_code for i in so.items}
        self.assertIn(
            ITEM_GIU_CHO, ma,
            "items rỗng hàng thật nhưng còn dat_ngoai -> phải chèn dòng giữ chỗ để ERPNext lưu được",
        )
        self.assertEqual(len(so.custom_dat_ngoai), 1, "dòng đặt ngoài không đổi phải còn nguyên")

    def test_khong_the_sua_dong_giu_cho(self):
        """Đơn TOÀN dat_ngoai đã có sẵn dòng giữ chỗ trong `items` — payload
        không được phép nhắm vào chính dòng kỹ thuật nội bộ đó."""
        so = _tao_so_dat_ngoai_cho_khach(
            BVBM, USER_BVBM, items=[],
            dat_ngoai=[{"ten_hang": "Kim luồn 24G", "dvt": "Cái", "so_luong": 5}],
        )
        ma = {i.item_code for i in so.items}
        self.assertIn(ITEM_GIU_CHO, ma, "fixture phải có sẵn placeholder để test có ý nghĩa")

        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_sua_so_luong(
                so.name, json.dumps({"items": [{"item_code": ITEM_GIU_CHO, "qty": 5}]})
            )

    def test_hai_lan_sua_lien_tiep_dat_ngoai_van_khop_ten(self):
        """review — chốt hồi quy cho cách viết KHÔNG rebuild bằng dict tay:
        sửa dat_ngoai LẦN 1 (không đổi tới 0) rồi sửa LẦN 2 vẫn phải khớp
        được đúng `name` cũ — nếu implementation từng sinh `name` MỚI cho
        dòng giữ nguyên, khớp theo `name` ở lần 2 sẽ IM LẶNG không tìm thấy
        gì (bug lớp `_init_child` mà brief round-trip review đã cảnh báo)."""
        so = _tao_so_dat_ngoai_cho_khach(
            BVBM, USER_BVBM,
            items=[{"item_code": RETAIL_CO_GIA, "qty": 2}],
            dat_ngoai=[{"ten_hang": "Kim luồn 24G", "dvt": "Cái", "so_luong": 5}],
        )
        dn_name = so.custom_dat_ngoai[0].name

        frappe.set_user(USER_BVBM)
        portal.portal_order_sua_so_luong(
            so.name, json.dumps({"items": [{"item_code": RETAIL_CO_GIA, "qty": 3}]})
        )
        frappe.set_user("Administrator")
        frappe.db.set_value(
            "Sales Order", so.name, "workflow_state", "Chờ khách đồng ý", update_modified=False
        )

        frappe.set_user(USER_BVBM)
        kq = portal.portal_order_sua_so_luong(
            so.name, json.dumps({"dat_ngoai": [{"name": dn_name, "qty": 8}]})
        )
        self.assertEqual(kq["trang_thai_moi"], "Chờ xác nhận")
        self.assertEqual(float(frappe.db.get_value("Sales Order Dat Ngoai Item", dn_name, "so_luong")), 8.0)
