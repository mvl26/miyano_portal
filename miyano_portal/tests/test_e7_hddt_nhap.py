"""E7b — HOÁ ĐƠN NHÁP hiện trên cổng, neo theo PHIẾU GIAO (không phải hoá đơn).

Khác `test_e7_hddt.py` ở đúng một điểm, và đó là lý do file này tồn tại riêng:
khối HĐĐT cũ neo theo `Sales Invoice`, còn bản ghi HĐĐT do
`builder.create_from_delivery_note` sinh ra CHỈ có `delivery_note` — chưa chắc
đã có `Sales Invoice` nào (Miyano có thể lập hoá đơn bán hàng sau, gộp cuối
kỳ). Neo theo Sales Invoice là khách KHÔNG thấy gì ở đúng thời điểm kế toán
bấm nút "Tạo HĐĐT từ phiếu giao" — chính là yêu cầu của tính năng này.

Ràng buộc CỐ Ý của bộ test này: KHÔNG được đổi hành vi khối HĐĐT cũ. 40 test
trong `test_e7_hddt.py` khoá nhãn "Đang phát hành HĐĐT" + `tai_duoc = False`
cho toàn nhóm trạng thái 01–05 ở TRANG HOÁ ĐƠN, và nhãn đó vẫn đúng ở đó —
`TestKhongDoiHanhViCu` dưới đây canh chừng.

Ba sự thật của module HĐĐT mà mọi test dưới đây phải tôn trọng (đã đọc
`erpnext/einvoice/`, không suy đoán):

1. `create_from_delivery_note` chèn bản ghi ở `01 - Nháp` **không kèm file
   nào**. `draft_pdf` chỉ có sau khi kế toán bấm tiếp "Xem bản nháp"
   (`actions.preview_draft`, gọi Fast `action=600`), và lúc đó trạng thái đã
   nhảy `02 - Đã xem nháp`. Vì vậy "có khối nháp" và "tải được PDF nháp" là
   HAI điều kiện độc lập, test riêng.
2. `FastEInvoiceDocument._compute_totals()` tự tính `amount`/`tax_amount`/
   `total_amount` từ dòng hàng khi bản ghi còn sửa được — fixture dưới đây
   chỉ khai qty/price/tax_rate, KHÔNG khai tổng, để test đọc đúng con số hệ
   thống thật sẽ sinh ra chứ không phải con số test tự bịa.
3. `lineage._COPIED_FIELDS` copy `delivery_note` từ bản gốc sang bản điều
   chỉnh/thay thế, nên một phiếu giao ĐÃ phát hành hoá đơn vẫn có thể sinh
   thêm một bản NHÁP mới (hoá đơn điều chỉnh đang soạn). Đó là dữ liệu thật,
   không phải rác — khối nháp phải hiện và phải nói rõ đó là loại gì.
"""

from unittest.mock import patch

import frappe
from frappe.utils import today

from miyano_portal import einvoice
from miyano_portal.api import portal
from miyano_portal.tests.test_e7_hddt import (
    BM_USER,
    COMPANY,
    COST_CENTER,
    CUSTOMER_BM,
    CUSTOMER_PXN,
    FEI,
    ITEM,
    PXN_USER,
    WAREHOUSE,
    _E7Fixture,
)


class _NhapFixture(_E7Fixture):
    def _tao_fei_nhap(self, customer, dn, status="01 - Nháp", dong=None, **overrides):
        """Bản ghi HĐĐT còn ở vòng nháp, CÓ dòng hàng (khối nháp trên cổng là
        dòng hàng + tổng tiền, nên fixture rỗng dòng sẽ xanh giả)."""
        if dong is None:
            dong = [
                {
                    "process_type": "1", "item_code": ITEM, "item_name": "Vật tư test",
                    "uom": "Cái", "qty": 2, "price": 100000, "tax_rate": "10",
                    "line_number": 1,
                },
                {
                    "process_type": "1", "item_code": "VT0006", "item_name": "Vật tư test 2",
                    "uom": "Hộp", "qty": 1, "price": 50000, "tax_rate": "5",
                    "line_number": 2,
                },
            ]
        return self._tao_fei(customer, dn, status=status, lines=dong, **overrides)

    def _dinh_pdf_nhap(self, fei_doc):
        """Mô phỏng `actions.preview_draft`: đính PDF nháp + ghi `draft_pdf`.
        Dùng PDF THẬT parse được (`File.before_insert` quét JavaScript nhúng,
        byte giả bị từ chối) — cùng lý do với `_dinh_pdf` của lớp cha."""
        from erpnext.einvoice.test_fixtures import minimal_pdf_bytes
        from frappe.utils.file_manager import save_file

        f = save_file(
            f"Nhap_{fei_doc.name}_1.pdf", minimal_pdf_bytes(), FEI, fei_doc.name, is_private=1
        )
        frappe.db.set_value(FEI, fei_doc.name, "draft_pdf", f.file_url, update_modified=False)
        fei_doc.reload()
        return f

    def _so_va_dn(self, customer=CUSTOMER_BM, qty=2):
        """Sales Order + Delivery Note NỐI VỚI NHAU qua `against_sales_order`
        — `portal_order_track` chỉ tìm thấy phiếu giao qua liên kết đó, nên
        `_tao_dn` của lớp cha (DN đứng một mình) không dùng được ở đây."""
        from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
        from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

        make_stock_entry(
            item_code=ITEM, qty=qty, to_warehouse=WAREHOUSE, rate=1000,
            company=COMPANY, purpose="Material Receipt",
        )
        so = frappe.new_doc("Sales Order")
        so.company = COMPANY
        so.customer = customer
        so.transaction_date = today()
        so.delivery_date = frappe.utils.add_days(today(), 2)
        so.append("items", {
            "item_code": ITEM, "qty": qty, "rate": 100000, "warehouse": WAREHOUSE,
            "delivery_date": frappe.utils.add_days(today(), 2),
        })
        so.insert(ignore_permissions=True)
        so.submit()

        dn = make_delivery_note(so.name)
        dn.posting_date = today()
        dn.set_posting_time = 1
        for r in dn.items:
            r.warehouse = WAREHOUSE
            r.cost_center = COST_CENTER
        dn.insert(ignore_permissions=True)
        dn.submit()
        return so, dn


# ===================================================== Adapter (einvoice.py)
class TestAdapterNhap(_NhapFixture):
    """`einvoice.nhap_cho_delivery_note()` — tra cứu thuần, không kiểm quyền
    (người gọi chịu trách nhiệm), nhưng LUÔN tự đối chiếu `fei.customer`."""

    def test_dn_vua_tao_hddt_da_co_khoi_nhap(self):
        """Yêu cầu gốc: kế toán bấm "Tạo HĐĐT từ phiếu giao" (trạng thái 01,
        CHƯA có file nào) → cổng đã phải thấy được nội dung."""
        dn = self._tao_dn(CUSTOMER_BM)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn)
        khoi = einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM)
        self.assertIsNotNone(khoi)
        self.assertEqual(khoi["fei"], fei.name)
        self.assertFalse(khoi["nhap_tai_duoc"], "Trạng thái 01 chưa bao giờ có PDF")

    def test_chua_lap_hddt_thi_khong_co_khoi(self):
        dn = self._tao_dn(CUSTOMER_BM)
        self.assertIsNone(einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM))

    def test_da_phat_hanh_khong_con_la_nhap(self):
        """06 trở đi có hoá đơn thật — đi đường HĐĐT chính thức ở trang Hoá
        đơn, không được hiện lại như một bản nháp."""
        dn = self._tao_dn(CUSTOMER_BM)
        self._tao_fei_nhap(CUSTOMER_BM, dn, status="06 - Đã phát hành")
        self.assertIsNone(einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM))

    def test_dang_phat_hanh_05_khong_con_la_nhap(self):
        """05 là "đã bấm phát hành, đang chờ Fast" — nội dung đã chốt, không
        còn là bản để khách góp ý; ranh giới nhóm nháp dừng ở 04."""
        dn = self._tao_dn(CUSTOMER_BM)
        self._tao_fei_nhap(CUSTOMER_BM, dn, status="05 - Đang phát hành")
        self.assertIsNone(einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM))

    def test_ca_bon_trang_thai_nhap_deu_hien(self):
        for status in ("01 - Nháp", "02 - Đã xem nháp", "03 - Chờ khách duyệt", "04 - Khách đã duyệt"):
            with self.subTest(status=status):
                dn = self._tao_dn(CUSTOMER_BM)
                self._tao_fei_nhap(CUSTOMER_BM, dn, status=status)
                self.assertIsNotNone(einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM))

    def test_ban_ghi_cua_khach_khac_khong_lo(self):
        """Lỗi dữ liệu ở module HĐĐT (gõ nhầm khách trên bản ghi) không được
        biến thành rò dữ liệu ở cổng — cùng chốt `fei.customer` mà
        `block_for` đã có."""
        dn = self._tao_dn(CUSTOMER_BM)
        self._tao_fei_nhap(CUSTOMER_PXN, dn)
        self.assertIsNone(einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM))

    def test_dong_hang_va_tong_tien_dung_so_lieu_he_thong(self):
        dn = self._tao_dn(CUSTOMER_BM)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn)
        khoi = einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM)

        self.assertEqual(len(khoi["dong"]), 2)
        d1, d2 = khoi["dong"]
        self.assertEqual(d1["ma"], ITEM)
        self.assertEqual(d1["so_luong"], 2)
        self.assertEqual(d1["don_gia"], 100000)
        self.assertEqual(d1["thanh_tien"], 200000)
        self.assertEqual(d1["thue_suat"], "10")
        self.assertEqual(d1["tien_thue"], 20000)
        self.assertEqual(d2["ma"], "VT0006")

        # Tổng đọc từ bản ghi thật (doc tự tính), không phải test tự cộng.
        self.assertEqual(khoi["tien_hang"], fei.amount)
        self.assertEqual(khoi["tien_thue"], fei.tax_amount)
        self.assertEqual(khoi["tong_tien"], fei.total_amount)
        self.assertEqual(khoi["tien_hang"], 250000)
        self.assertEqual(khoi["tong_tien"], 272500)

    def test_khong_lo_duong_dan_file(self):  # BR-E4 / quyết định nền tảng #8
        """Không có URL file công khai: khối trả về chỉ được mang CỜ, tuyệt
        đối không mang `draft_pdf`. Quét TOÀN BỘ giá trị (kể cả dòng hàng),
        không chỉ các key biết trước."""
        import json

        dn = self._tao_dn(CUSTOMER_BM)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        f = self._dinh_pdf_nhap(fei)

        khoi = einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM)
        self.assertTrue(khoi["nhap_tai_duoc"])
        self.assertNotIn(f.file_url, json.dumps(khoi, default=str))
        self.assertNotIn("draft_pdf", khoi)

    def test_ban_dieu_chinh_dang_soan_hien_dung_loai(self):
        """Phiếu giao đã có hoá đơn phát hành, kế toán đang soạn bản điều
        chỉnh (con "01 - Nháp", cùng `delivery_note` — `lineage._COPIED_FIELDS`).
        Khách phải thấy, và phải biết đây là hoá đơn ĐIỀU CHỈNH, không phải
        hoá đơn gốc."""
        dn = self._tao_dn(CUSTOMER_BM)
        goc = self._tao_fei_nhap(CUSTOMER_BM, dn, status="06 - Đã phát hành")
        self._tao_fei_nhap(
            CUSTOMER_BM, dn, status="01 - Nháp",
            invoice_type="Hóa đơn điều chỉnh", original_document=goc.name,
            adjustment_reason="Sai đơn giá", adjustment_type="1 - Điều chỉnh giảm",
        )
        khoi = einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM)
        self.assertIsNotNone(khoi)
        self.assertEqual(khoi["loai"], "Hóa đơn điều chỉnh")

    def test_nhieu_ban_nhap_lay_ban_moi_nhat(self):
        dn = self._tao_dn(CUSTOMER_BM)
        self._tao_fei_nhap(CUSTOMER_BM, dn, status="01 - Nháp")
        moi = self._tao_fei_nhap(CUSTOMER_BM, dn, status="01 - Nháp")
        khoi = einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM)
        self.assertEqual(khoi["fei"], moi.name)

    def test_khong_phu_thuoc_cong_tac_fast(self):
        """Module HĐĐT ship ở trạng thái TẮT (`Fast EInvoice Settings.enabled`
        mặc định 0, `_validate_credentials_before_enabling()` không cho bật
        khi chưa có credential Fast thật). Đường ĐỌC của cổng không được gọi
        `check_enabled()` — gọi là chết cả trang chi tiết đơn ở mọi site chưa
        cấu hình Fast.

        TẮT công tắc ngay trong test thay vì assert trạng thái sẵn có của
        site: site dev có thể đã bật Fast, và một fixture "giả định site đang
        tắt" sẽ xanh giả đúng ở nơi cần bắt lỗi nhất."""
        frappe.db.set_single_value("Fast EInvoice Settings", "enabled", 0)
        dn = self._tao_dn(CUSTOMER_BM)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn)
        self.assertIsNotNone(einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM))
        self.assertEqual(einvoice.dn_co_hoa_don_nhap([dn.name], CUSTOMER_BM), {dn.name})

        # Và cả đường TẢI: `_dinh_pdf_nhap` mô phỏng file đã có sẵn từ trước
        # khi ai đó tắt công tắc.
        self._dinh_pdf_nhap(fei)
        frappe.db.set_value(FEI, fei.name, "status", "02 - Đã xem nháp", update_modified=False)
        frappe.set_user(BM_USER)
        frappe.local.response = frappe._dict()
        portal.portal_einvoice_nhap_pdf(dn.name)
        self.assertEqual(frappe.local.response.type, "pdf")


# ================================================== Endpoint xem khối nháp
class TestEndpointNhap(_NhapFixture):
    def test_chu_phieu_giao_xem_duoc(self):
        dn = self._tao_dn(CUSTOMER_BM)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn)
        frappe.set_user(BM_USER)
        khoi = portal.portal_einvoice_nhap(dn.name)
        self.assertEqual(khoi["fei"], fei.name)

    def test_khach_khac_bi_chan(self):
        dn = self._tao_dn(CUSTOMER_BM)
        self._tao_fei_nhap(CUSTOMER_BM, dn)
        frappe.set_user(PXN_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_einvoice_nhap(dn.name)

    def test_chua_dang_nhap_bi_chan(self):
        dn = self._tao_dn(CUSTOMER_BM)
        self._tao_fei_nhap(CUSTOMER_BM, dn)
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            portal.portal_einvoice_nhap(dn.name)

    def test_chua_co_nhap_tra_none(self):
        dn = self._tao_dn(CUSTOMER_BM)
        frappe.set_user(BM_USER)
        self.assertIsNone(portal.portal_einvoice_nhap(dn.name))

    def test_chot_fei_customer_doc_lap_voi_chot_so_huu_phieu_giao(self):
        """`_dn_cua_khach` có HAI chốt độc lập (`check_permission` +
        `dn.customer`) và `ban_nhap_tho` có chốt THỨ BA (`fei.customer`).
        `test_khach_khac_bi_chan` xanh ngay ở chốt đầu nên KHÔNG chứng minh
        được chốt thứ ba — dựng riêng ca mà hai chốt đầu ĐỀU CHO QUA (phiếu
        giao đúng là của BM, khách BM đang đăng nhập) trong khi bản ghi HĐĐT
        bị gán nhầm sang khách khác. Đây chính là lỗi dữ liệu module HĐĐT mà
        quyết định nền tảng #7 phải chặn, và là khuôn của
        `test_e7_hddt.py::test_khach_le_bang_gia_tri_customer`."""
        dn = self._tao_dn(CUSTOMER_BM)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        self._dinh_pdf_nhap(fei)
        frappe.db.set_value(FEI, fei.name, "customer", CUSTOMER_PXN, update_modified=False)

        frappe.set_user(BM_USER)
        self.assertIsNone(portal.portal_einvoice_nhap(dn.name))
        with self.assertRaises(frappe.ValidationError):
            portal.portal_einvoice_nhap_pdf(dn.name)


# ======================================================== Tải PDF bản nháp
class TestTaiPdfNhap(_NhapFixture):
    def test_tai_thanh_cong_dung_noi_dung_va_ghi_log(self):
        from erpnext.einvoice.test_fixtures import minimal_pdf_bytes

        dn = self._tao_dn(CUSTOMER_BM)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        self._dinh_pdf_nhap(fei)

        frappe.set_user(BM_USER)
        truoc = frappe.db.count("Access Log", {"export_from": FEI, "reference_document": fei.name})
        frappe.local.response = frappe._dict()
        portal.portal_einvoice_nhap_pdf(dn.name)

        noi_dung = frappe.local.response.filecontent
        if isinstance(noi_dung, str):
            noi_dung = noi_dung.encode()
        self.assertEqual(noi_dung, minimal_pdf_bytes())
        self.assertEqual(frappe.local.response.type, "pdf")
        self.assertIn("Nhap", frappe.local.response.filename)
        sau = frappe.db.count("Access Log", {"export_from": FEI, "reference_document": fei.name})
        self.assertEqual(sau, truoc + 1)

    def test_khach_khac_bi_chan(self):
        dn = self._tao_dn(CUSTOMER_BM)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        self._dinh_pdf_nhap(fei)
        frappe.set_user(PXN_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_einvoice_nhap_pdf(dn.name)

    def test_da_phat_hanh_khong_tai_ban_nhap_qua_duong_nay(self):
        """Chốt trạng thái độc lập với chốt file: bản ghi ĐÃ phát hành vẫn
        còn `draft_pdf` cũ trên field, nhưng bản nháp đó không còn là thứ
        được phục vụ — hoá đơn thật đi qua `portal_einvoice_download`."""
        dn = self._tao_dn(CUSTOMER_BM)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        self._dinh_pdf_nhap(fei)
        frappe.db.set_value(FEI, fei.name, "status", "06 - Đã phát hành", update_modified=False)
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_einvoice_nhap_pdf(dn.name)

    def test_chua_co_pdf_nhap_bao_loi_ro_rang(self):
        """Trạng thái 01: kế toán chưa bấm "Xem bản nháp" nên chưa có file."""
        dn = self._tao_dn(CUSTOMER_BM)
        self._tao_fei_nhap(CUSTOMER_BM, dn, status="01 - Nháp")
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_einvoice_nhap_pdf(dn.name)

    def test_file_bi_xoa_du_field_con_gia_tri_cu(self):  # NL-12.4
        dn = self._tao_dn(CUSTOMER_BM)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        self._dinh_pdf_nhap(fei)
        frappe.db.delete("File", {"attached_to_doctype": FEI, "attached_to_name": fei.name})
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_einvoice_nhap_pdf(dn.name)

    def test_doc_chi_khong_dong_cham_ban_ghi_hddt(self):  # BR-E5
        dn = self._tao_dn(CUSTOMER_BM)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        self._dinh_pdf_nhap(fei)
        truoc = frappe.get_doc(FEI, fei.name).as_json()
        frappe.set_user(BM_USER)
        portal.portal_einvoice_nhap(dn.name)
        frappe.local.response = frappe._dict()
        portal.portal_einvoice_nhap_pdf(dn.name)
        sau = frappe.get_doc(FEI, fei.name).as_json()
        self.assertEqual(truoc, sau)


# =========================================== Cờ trên khối phiếu giao của đơn
class TestCoTrenChiTietDon(_NhapFixture):
    def test_dot_giao_bat_co_khi_co_hoa_don_nhap(self):
        so, dn = self._so_va_dn()
        self._tao_fei_nhap(CUSTOMER_BM, dn)
        frappe.set_user(BM_USER)
        data = portal.portal_order_track(so.name)
        dot = next(d for d in data["deliveries"] if d["name"] == dn.name)
        self.assertTrue(dot["co_hoa_don_nhap"])
        self.assertTrue(
            next(d for d in data["dot_giao"] if d["delivery_note"] == dn.name)["co_hoa_don_nhap"]
        )

    def test_khong_co_hddt_thi_co_tat(self):
        so, dn = self._so_va_dn()
        frappe.set_user(BM_USER)
        data = portal.portal_order_track(so.name)
        dot = next(d for d in data["deliveries"] if d["name"] == dn.name)
        self.assertFalse(dot["co_hoa_don_nhap"])

    def test_ban_ghi_gan_nham_khach_khong_bat_co(self):
        """Cùng chốt `fei.customer` như `TestEndpointNhap` — kiểm ở đường CỜ
        vì đó là truy vấn GỘP (`dn_co_hoa_don_nhap`), một chỗ dễ quên lọc
        khách hơn hẳn đường đọc từng bản ghi."""
        so, dn = self._so_va_dn()
        self._tao_fei_nhap(CUSTOMER_PXN, dn)
        frappe.set_user(BM_USER)
        data = portal.portal_order_track(so.name)
        dot = next(d for d in data["deliveries"] if d["name"] == dn.name)
        self.assertFalse(dot["co_hoa_don_nhap"])

    def test_module_hddt_loi_khong_lam_vo_chi_tiet_don(self):
        """Cùng nguyên tắc `_chay_an_toan` của hook kho và khối bọc lỗi ở
        `portal_invoices`: module HĐĐT của team khác hỏng thì mất CÁI CỜ,
        không được mất cả trang chi tiết đơn hàng."""
        so, dn = self._so_va_dn()
        self._tao_fei_nhap(CUSTOMER_BM, dn)
        frappe.set_user(BM_USER)
        with patch.object(
            portal.einvoice, "dn_co_hoa_don_nhap", side_effect=Exception("module HĐĐT hỏng")
        ):
            data = portal.portal_order_track(so.name)
        dot = next(d for d in data["deliveries"] if d["name"] == dn.name)
        self.assertFalse(dot["co_hoa_don_nhap"])
        self.assertTrue(data["items"], "Chi tiết đơn phải còn nguyên")


# ============================== Hai đường đọc phải nói CÙNG một điều
class TestHaiDuongDocKhopNhau(_NhapFixture):
    """Cổng có HAI đường đọc cùng một chứng từ HĐĐT: khối cũ neo theo Sales
    Invoice (`block_for`, trang Hoá đơn & công nợ) và khối này neo theo
    Delivery Note (chi tiết đơn hàng). Hai đường lệch nhau nghĩa là khách mở
    hai màn hình thấy hai câu chuyện khác nhau về cùng một hoá đơn."""

    def test_cung_mot_chung_tu_thi_hai_duong_cung_bao_la_nhap(self):
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        self._dinh_pdf_nhap(fei)

        theo_hoa_don = einvoice.block_for(si.name, CUSTOMER_BM)["chinh"]
        theo_phieu_giao = einvoice.nhap_cho_delivery_note(dn.name, CUSTOMER_BM)

        self.assertEqual(theo_hoa_don["trang_thai"], "nhap")
        self.assertEqual(theo_hoa_don["fei"], theo_phieu_giao["fei"])
        self.assertTrue(theo_hoa_don["nhap_tai_duoc"])
        self.assertTrue(theo_phieu_giao["nhap_tai_duoc"])

    def test_nhap_statuses_suy_tu_status_meta(self):
        """Một tập trạng thái khai ở hai nơi là hai nơi lệch nhau được. Nếu
        `_STATUS_META` đổi nhóm một mã, đường đọc theo phiếu giao phải đổi
        theo NGAY, không cần ai nhớ sửa chỗ thứ hai."""
        tu_meta = {ma for ma, (nhom, _l, _b) in einvoice._STATUS_META.items() if nhom == "nhap"}
        self.assertEqual(set(einvoice._NHAP_STATUSES), tu_meta)
        self.assertEqual(len(tu_meta), 4)
