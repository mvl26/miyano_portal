"""Spec 2026-08-15 §3.4 — đơn mua lẻ TOÀN hàng chưa có mã.

ERPNext không lưu nổi Sales Order với `items` rỗng (đã kiểm thực nghiệm, ghi
ở api/portal.py:655). Item giữ chỗ `HANG-DAT-NGOAI` là lối ra — nhưng CHỈ khi
giỏ không còn mặt hàng thật nào: `resolve_ban_le_company()` GIAO tập company
của mọi mặt hàng trong giỏ, nên chèn vô điều kiện có thể làm RỖNG phép giao
và hỏng một đơn giỏ hỗn hợp vốn đang hợp lệ.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.tests.test_e6_mua_le import (
    BVBM, RETAIL_CO_GIA, USER_BVBM, _rid, _seed_mua_le,
)

DAT_NGOAI_MAU = [
    {"ten_hang": "Găng tay nitrile size M", "dvt": "Hộp", "so_luong": 5},
    {"ten_hang": "Dây truyền dịch", "dvt": "Cái", "so_luong": 20},
]


class TestDatNgoaiGiuCho(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_mua_le()

    def setUp(self):
        frappe.set_user(USER_BVBM)
        frappe.db.set_value("Customer", BVBM, "custom_cho_phep_mua_le", 1)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_don_toan_hang_chua_co_ma_van_dat_duoc(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(
            [i.item_code for i in so.items], [ITEM_GIU_CHO],
            "đơn toàn hàng lạ phải có đúng MỘT dòng giữ chỗ",
        )
        self.assertEqual(len(so.custom_dat_ngoai), 2)

    def test_gio_hon_hop_KHONG_chen_dong_giu_cho(self):
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 2}]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        ma = [i.item_code for i in so.items]
        self.assertNotIn(
            ITEM_GIU_CHO, ma,
            "chèn giữ chỗ vào giỏ hỗn hợp sẽ thu hẹp resolve_ban_le_company()",
        )
        self.assertEqual(ma, [RETAIL_CO_GIA])

    def test_gio_rong_hoan_toan_van_bi_tu_choi(self):
        """Không hàng có mã, KHÔNG cả dòng đặt ngoài — không có nhu cầu nào
        để phục vụ, đơn rỗng là lỗi client chứ không phải tình huống nghiệp vụ."""
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([]),
                dat_ngoai=json.dumps([]),
                request_id=_rid(),
                mode="ban_le",
            )

    def test_khong_submit_duoc_khi_con_dong_chua_khop_ma(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        with self.assertRaises(frappe.ValidationError):
            so.submit()

    def test_khong_submit_duoc_khi_con_dong_giu_cho_du_da_khop_het(self):
        """Việc thêm (controller, ngoài Task 9) — `kiem_dat_ngoai_da_xu_ly`
        (chốt cũ) chỉ nhìn `custom_dat_ngoai`, không hề nhìn `items`. Một đơn
        có TẤT CẢ dòng đặt ngoài đã khớp mã (chốt cũ hài lòng) nhưng sales
        quên GỠ dòng giữ chỗ `ITEM_GIU_CHO` khỏi `items` vẫn lọt qua chốt cũ
        — khách sẽ nhận PDF "Xác nhận đơn hàng" với một dòng kỹ thuật nội bộ.
        Chốt mới phải chặn đúng tình huống này.

        VIẾT LẠI ở Task 13 (QĐ-G13) — KHÔNG xoá, vì chốt
        `kiem_khong_con_dong_giu_cho` vẫn tồn tại và vẫn cần được canh.
        Nhưng TIỀN ĐỀ cũ của bài đã hết đường tới: từ Task 13, khớp mã cho
        mọi dòng đặt ngoài sẽ TỰ GỠ dòng giữ chỗ (bẫy 3), nên trạng thái
        "đã khớp hết mà giữ chỗ còn nguyên" không sinh ra được bằng cách
        khớp mã nữa. Bài dựng lại trạng thái đó bằng đúng tình huống chốt
        sinh ra để chặn — SALES TỰ TAY để sót dòng giữ chỗ trong `items`
        (thêm lại nó ở một lần lưu KHÔNG chuyển dòng nào, nên phép gỡ tự
        động không chạm tới).
        """
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual([i.item_code for i in so.items], [ITEM_GIU_CHO])
        # Khớp mã cho MỌI dòng đặt ngoài — chốt CŨ hài lòng, không còn dòng
        # nào "chưa xử lý".
        for dong in so.custom_dat_ngoai:
            dong.item_khop = RETAIL_CO_GIA
        so.save(ignore_permissions=True)
        so.reload()
        self.assertTrue(
            all(d.da_xu_ly for d in so.custom_dat_ngoai),
            "chốt cũ phải hài lòng — mọi dòng đặt ngoài đã khớp mã",
        )
        self.assertNotIn(
            ITEM_GIU_CHO, [i.item_code for i in so.items],
            "Task 13 (bẫy 3) — khớp hết thì phép chuyển đã tự gỡ dòng giữ chỗ",
        )
        # Sales TỰ TAY thêm lại dòng giữ chỗ và quên gỡ. Lần lưu này không
        # chuyển dòng nào (mọi dòng gõ tay đã `da_chuyen`), nên phép gỡ tự
        # động không chạy — đúng trạng thái chốt `kiem_khong_con_dong_giu_cho`
        # sinh ra để chặn.
        so.append("items", {
            "item_code": ITEM_GIU_CHO, "qty": 1, "rate": 0,
            "warehouse": so.items[0].warehouse,
            "delivery_date": so.delivery_date,
        })
        so.save(ignore_permissions=True)
        so.reload()
        self.assertIn(ITEM_GIU_CHO, [i.item_code for i in so.items])
        with self.assertRaises(frappe.ValidationError) as ctx:
            so.submit()
        self.assertIn("còn dòng giữ chỗ kỹ thuật", str(ctx.exception))
        so.reload()
        self.assertEqual(so.docstatus, 0, "chốt mới phải chặn TRƯỚC khi ghi nhận submit")

    def test_cong_khong_bao_gio_thay_dong_giu_cho(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        track = portal.portal_order_track(order=res["sales_order"])
        ma = [i["item_code"] for i in track["items"]]
        self.assertNotIn(
            ITEM_GIU_CHO, ma,
            "dòng giữ chỗ là chi tiết kỹ thuật nội bộ, không được lọt ra cổng",
        )
        self.assertEqual(len(track["dat_ngoai"]), 2)
        self.assertEqual(track["dat_ngoai"][0]["ten_hang"], DAT_NGOAI_MAU[0]["ten_hang"])
        self.assertFalse(track["dat_ngoai"][0]["da_xu_ly"])

    def test_danh_muc_ban_le_khong_chua_item_giu_cho(self):
        """review C-1(a) — `ITEM_GIU_CHO` có `disabled=0`, `is_sales_item=1`
        (bắt buộc để đơn toàn hàng chưa có mã lưu được, §3.4) nên nếu
        `portal_catalog_ban_le` không loại nó tường minh, nó lọt vào danh
        mục như một sản phẩm khách duyệt được — đã kiểm trên site thật,
        `tim_kiem="đặt ngoài"` khớp ngay chính tên item giữ chỗ."""
        res = portal.portal_catalog_ban_le(tim_kiem="đặt ngoài")
        ma = [r["item_code"] for r in res["items"]]
        self.assertNotIn(
            ITEM_GIU_CHO, ma,
            "item giữ chỗ là chi tiết kỹ thuật nội bộ, không phải sản phẩm",
        )
        # Danh mục không lọc theo `tim_kiem` (không có gì khác khớp từ khoá
        # này trong seed) — nếu khác 0 thì phải KHÔNG chứa ITEM_GIU_CHO ở tất
        # cả các trang, không chỉ trang đầu.
        res_toan_bo = portal.portal_catalog_ban_le(limit=1000)
        self.assertNotIn(ITEM_GIU_CHO, [r["item_code"] for r in res_toan_bo["items"]])

    def test_payload_gui_thang_item_giu_cho_bi_tu_choi(self):
        """review C-1(b) — đường ghi phải tự chốt lại, không tin danh mục đã
        lọc: khách (hoặc client bị sửa) gửi thẳng `item_code=ITEM_GIU_CHO`
        trong payload `items` như bất kỳ mã nào khác."""
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": ITEM_GIU_CHO, "qty": 1}]),
                dat_ngoai=json.dumps([]),
                request_id=_rid(),
                mode="ban_le",
            )
        # Đơn không được tạo ra — chốt phải chặn TRƯỚC khi ghi, không phải
        # sau (không có Sales Order rác nào ứng với request_id vừa gửi).

    def test_mau_xac_nhan_don_hang_khong_in_dong_giu_cho(self):
        """Việc thêm (controller, ngoài Task 9), lớp phòng thủ THỨ HAI — nếu
        chốt `kiem_khong_con_dong_giu_cho` (ở `before_submit`) đúng thì dòng
        giữ chỗ không bao giờ tới được một đơn ĐÃ SUBMIT, nên test này dựng
        thẳng đơn ở docstatus=0 (chưa submit, không cần đi qua chốt) để kiểm
        RIÊNG mẫu in — độc lập với chốt ở (a), không phụ thuộc chốt đó luôn
        đúng ở mọi đường ghi trong tương lai."""
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        html = frappe.get_print(
            "Sales Order", res["sales_order"],
            print_format="Miyano - Xác nhận đơn hàng", no_letterhead=1,
        )
        self.assertNotIn(ITEM_GIU_CHO, html)
