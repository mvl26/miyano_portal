"""E7 — Hoá đơn điện tử trên cổng, chỉ đọc (QT12).

Nhóm TC-E7 (`DevHandoff/40_TestCases.md`) + các ca biên nêu trong
`.superpowers/sdd/e7/brief-hddt.md`.

Điểm quan trọng nhất của module này: `Fast EInvoice Document` (module HĐĐT,
`apps/erpnext/erpnext/einvoice/`) hầu như KHÔNG BAO GIỜ có `sales_invoice`
được điền — luồng tạo bản ghi thật (`builder.py::create_from_delivery_note`)
chỉ gán `delivery_note`. Vì vậy fixture MẶC ĐỊNH của mọi test dưới đây (trừ
`test_lien_ket_truc_tiep_sales_invoice`, test riêng cho trường hợp NGOẠI LỆ)
để `sales_invoice` TRỐNG và chỉ nối qua `Sales Invoice Item.delivery_note` —
đúng đường THẬT `miyano_portal.einvoice.resolve()` phải đi qua. Nếu fixture
mặc định lại điền `sales_invoice` trực tiếp, mọi test sẽ xanh dù tầng 2 của
`resolve()` có bị xoá — đúng bẫy "một lớp input chưa từng được thử" mà brief
cảnh báo.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from miyano_portal import einvoice
from miyano_portal.api import portal
from miyano_portal.setup.seed_demo import seed_demo

CUSTOMER_BM = "Bệnh viện Bạch Mai"
CUSTOMER_PXN = "PXN ABC"
BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"
KE_TOAN_HDDT_USER = "ke_toan_hddt_e7@demo.miyano"

COMPANY = "Miyano Việt Nam"
DEBIT_TO = "Debtors - MYN"
INCOME_ACCOUNT = "Sales - MYN"
COST_CENTER = "Main - MYN"
WAREHOUSE = "Stores - MYN"
ITEM = "VT0005"

FEI = "Fast EInvoice Document"


def _ensure_ke_toan_hddt_user():
    """Fixture RIÊNG của module này (bẫy #4 của brief: không đếm trên dữ
    liệu ngoài tầm setUp) — site thật hiện KHÔNG có ai giữ role "Kế toán
    HĐĐT"/"Kế toán trưởng HĐĐT" (đã kiểm), nên test nhánh "có người nhận"
    phải tự gán role cho một user test riêng, không dựa vào dữ liệu ngoài."""
    if not frappe.db.exists("User", KE_TOAN_HDDT_USER):
        frappe.get_doc({
            "doctype": "User", "email": KE_TOAN_HDDT_USER, "first_name": "Ke Toan HDDT",
            "user_type": "System User", "send_welcome_email": 0,
            "roles": [{"role": "Kế toán HĐĐT"}],
        }).insert(ignore_permissions=True)
    return KE_TOAN_HDDT_USER


class _E7Fixture(FrappeTestCase):
    """`FrappeTestCase` rollback MỘT LẦN MỖI CLASS — mọi test trong lớp con
    dùng chung dữ liệu do `setUp` tạo, nên các hàm `_tao_*` dưới đây luôn
    sinh tên MỚI (không tái sử dụng bản ghi giữa các test method) để một
    test không vô tình đọc trúng dữ liệu của test khác chạy trước nó."""

    def setUp(self):
        seed_demo()
        self._seq = 0

    def tearDown(self):
        frappe.set_user("Administrator")

    def _ten_moi(self, tien_to):
        self._seq += 1
        return f"{tien_to}-E7-{self._seq}-{frappe.generate_hash(length=6)}"

    def _tao_dn(self, customer):
        # `Sales Invoice.check_prev_docstatus` (erpnext core) đòi DN tham
        # chiếu qua `Sales Invoice Item.delivery_note` PHẢI đã submit — nạp
        # tồn trước rồi submit thật, cùng khuôn `_nap_ton`/`_dn` của
        # `test_kho_delivery_hook.py`.
        from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

        make_stock_entry(
            item_code=ITEM, qty=1, to_warehouse=WAREHOUSE, rate=1000,
            company=COMPANY, purpose="Material Receipt",
        )
        dn = frappe.new_doc("Delivery Note")
        dn.company = COMPANY
        dn.customer = customer
        dn.posting_date = today()
        dn.set_posting_time = 1
        dn.append("items", {
            "item_code": ITEM, "qty": 1, "rate": 1200,
            "warehouse": WAREHOUSE, "cost_center": COST_CENTER,
        })
        dn.insert(ignore_permissions=True)
        dn.submit()
        return dn

    def _tao_si(self, customer, dn=None):
        si = frappe.new_doc("Sales Invoice")
        si.company = COMPANY
        si.customer = customer
        si.posting_date = today()
        si.set_posting_time = 1
        si.debit_to = DEBIT_TO
        si.update_stock = 0
        row = {
            "item_code": ITEM, "qty": 1, "rate": 1200,
            "income_account": INCOME_ACCOUNT, "cost_center": COST_CENTER,
        }
        if dn is not None:
            row["delivery_note"] = dn.name
        si.append("items", row)
        si.insert(ignore_permissions=True)
        si.submit()
        return si

    def _tao_fei(self, customer, dn, sales_invoice=None, **overrides):
        doc = frappe.new_doc(FEI)
        doc.delivery_note = dn.name
        doc.customer = customer
        doc.invoice_date = today()
        doc.customer_code = customer
        doc.customer_name = customer
        doc.address = "Địa chỉ test"
        doc.email_deliver = "ketoan@demo.miyano"
        doc.amount_in_words = "Một triệu hai trăm nghìn đồng"
        doc.human_name = "Kế toán test"
        if sales_invoice is not None:
            doc.sales_invoice = sales_invoice
        for k, v in overrides.items():
            doc.set(k, v)
        doc.flags.ignore_permissions = True
        doc.insert()
        return doc

    def _dinh_pdf(self, fei_doc, noi_dung=None):
        # PDF THẬT parse được — Frappe quét nội dung PDF đính kèm tìm
        # JavaScript nhúng, byte giả bị `pdf_contains_js` từ chối ngay ở
        # `File.before_insert`. Dùng lại đúng helper module HĐĐT đã tự viết
        # cho chính bài toán này (`erpnext/einvoice/test_fixtures.py`) thay
        # vì viết một bản PDF tối thiểu thứ hai.
        from erpnext.einvoice.test_fixtures import minimal_pdf_bytes
        from frappe.utils.file_manager import save_file

        noi_dung = noi_dung or minimal_pdf_bytes()
        f = save_file(f"HD_{fei_doc.name}.pdf", noi_dung, FEI, fei_doc.name, is_private=1)
        frappe.db.set_value(FEI, fei_doc.name, "official_pdf", f.file_url, update_modified=False)
        fei_doc.reload()
        return f

    # Đường THẬT (tầng 2 — qua delivery_note): dùng làm mặc định cho hầu hết
    # test, vì đó là đường mà mọi hoá đơn thật đi qua (xem docstring module).
    def _chain(self, customer, status="06 - Đã phát hành", dinh_pdf=True, **overrides):
        dn = self._tao_dn(customer)
        si = self._tao_si(customer, dn=dn)
        fei = self._tao_fei(customer, dn, status=status, **overrides)
        if dinh_pdf and status not in ("98 - Cần đối soát", "99 - Lỗi") and status[:2] not in ("01", "02", "03", "04", "05"):
            self._dinh_pdf(fei)
        return si, fei


class TestResolveBridge(_E7Fixture):
    """`einvoice.resolve()` — tầng 1 (sales_invoice trực tiếp) rồi mới tầng 2
    (qua delivery_note). Đây là phần dễ vỡ nhất: brief gốc coi `sales_invoice`
    là liên kết CHÍNH, nhưng đọc thẳng `builder.py` thì đường THẬT là tầng 2.
    """

    def test_lien_ket_qua_delivery_note_la_duong_mac_dinh(self):
        si, fei = self._chain(CUSTOMER_BM, dinh_pdf=False)
        self.assertFalse(fei.sales_invoice)
        found = einvoice.resolve(si.name)
        self.assertIsNotNone(found, "resolve() phải bắc cầu qua Sales Invoice Item.delivery_note")
        self.assertEqual(found.name, fei.name)

    def test_lien_ket_truc_tiep_sales_invoice(self):
        """Trường hợp NGOẠI LỆ (kế toán tự điền `sales_invoice`) — vẫn phải
        tìm đúng, và được ưu tiên hơn một bản ghi khác chỉ nối qua DN."""
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        fei = self._tao_fei(CUSTOMER_BM, dn, sales_invoice=si.name, status="06 - Đã phát hành")
        found = einvoice.resolve(si.name)
        self.assertEqual(found.name, fei.name)

    def test_khong_co_ban_ghi_hddt_nao_tra_none(self):
        si = self._tao_si(CUSTOMER_BM)
        self.assertIsNone(einvoice.resolve(si.name))

    def test_tang_1_chay_truoc_khong_can_di_qua_delivery_note(self):
        """`resolve()` không được tự ý quét MỌI Sales Invoice Item khi tầng
        1 đã trả kết quả — dựng một fixture mà nếu code lỡ đi tầng 2 trước sẽ
        ra một FEI SAI (nối qua DN của một hoá đơn KHÁC)."""
        dn1 = self._tao_dn(CUSTOMER_BM)
        si1 = self._tao_si(CUSTOMER_BM, dn=dn1)
        fei_qua_dn = self._tao_fei(CUSTOMER_BM, dn1, status="06 - Đã phát hành")

        dn2 = self._tao_dn(CUSTOMER_BM)
        si2 = self._tao_si(CUSTOMER_BM, dn=dn2)
        fei_truc_tiep = self._tao_fei(CUSTOMER_BM, dn2, sales_invoice=si1.name, status="06 - Đã phát hành")

        found = einvoice.resolve(si1.name)
        self.assertEqual(found.name, fei_truc_tiep.name)
        self.assertNotEqual(found.name, fei_qua_dn.name)


class TestBadgeGroups(_E7Fixture):
    def test_chua_ghi_so_hddt_khong_nut_tai_cong_no_van_hien(self):  # TC-E7-01
        si, fei = self._chain(CUSTOMER_BM, status="01 - Nháp", dinh_pdf=False)
        block = einvoice.block_for(si.name, si.customer)
        self.assertEqual(block["trang_thai"], "dang_phat_hanh")
        self.assertFalse(block["tai_duoc"])
        self.assertFalse(block["ho_tro"])
        # Công nợ vẫn hiển thị bình thường — cột outstanding_amount không bị
        # khối HĐĐT che mất, kiểm qua chính response `portal_invoices`.
        frappe.set_user(BM_USER)
        rows = {r["name"]: r for r in portal.portal_invoices(limit=200)}
        self.assertIn(si.name, rows)
        self.assertIn("outstanding_amount", rows[si.name])

    def test_khong_co_fei_cung_la_dang_phat_hanh(self):
        si = self._tao_si(CUSTOMER_BM)
        block = einvoice.block_for(si.name, si.customer)
        self.assertEqual(block["trang_thai"], "dang_phat_hanh")
        self.assertFalse(block["tai_duoc"])

    def test_da_phat_hanh_co_file_thi_tai_duoc(self):  # TC-E7-02
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        block = einvoice.block_for(si.name, si.customer)
        self.assertEqual(block["trang_thai"], "da_phat_hanh")
        self.assertTrue(block["tai_duoc"])
        self.assertFalse(block["ho_tro"])

    def test_da_phat_hanh_nhung_pdf_chua_co_la_trang_thai_rieng(self):
        """`official_pdf` được đính qua job NỀN (đợi ký số HSM) — trạng thái
        06 mà chưa có file là một tình huống THẬT, không phải lỗi test."""
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành", dinh_pdf=False)
        block = einvoice.block_for(si.name, si.customer)
        self.assertEqual(block["trang_thai"], "da_phat_hanh")
        self.assertFalse(block["tai_duoc"])
        self.assertTrue(block["ho_tro"])
        self.assertIn("file đang xử lý", block["nhan"])

    def test_cqt_tu_choi_van_tai_duoc_nhung_nhan_rieng(self):
        si, fei = self._chain(CUSTOMER_BM, status="09 - CQT từ chối")
        block = einvoice.block_for(si.name, si.customer)
        self.assertEqual(block["trang_thai"], "cqt_tu_choi")
        self.assertTrue(block["tai_duoc"])
        self.assertNotEqual(block["nhan"], "Đã phát hành")

    def test_da_huy_khong_giau_hoa_don_cu(self):  # NL-12.2
        si, fei = self._chain(
            CUSTOMER_BM, status="12 - Đã hủy nội bộ", cancel_reason="Sai mã số thuế",
        )
        block = einvoice.block_for(si.name, si.customer)
        self.assertEqual(block["trang_thai"], "da_huy")
        # "Không bị giấu": dòng hoá đơn vẫn có trong danh sách của khách.
        frappe.set_user(BM_USER)
        names = {r["name"] for r in portal.portal_invoices(limit=200)}
        self.assertIn(si.name, names)

    def test_trang_thai_loi_disable_tai_va_hien_ho_tro(self):  # NL-12.4
        for status in ("98 - Cần đối soát", "99 - Lỗi"):
            si, fei = self._chain(CUSTOMER_BM, status=status, dinh_pdf=False)
            block = einvoice.block_for(si.name, si.customer)
            self.assertEqual(block["trang_thai"], "loi", status)
            self.assertFalse(block["tai_duoc"], status)
            self.assertTrue(block["ho_tro"], status)

    def test_trang_thai_tho_khong_lo_ra_ngoai(self):
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        block = einvoice.block_for(si.name, si.customer)
        self.assertNotEqual(block["trang_thai"], fei.status)
        for v in block.values():
            if isinstance(v, str):
                self.assertNotIn(fei.status, v, "không được lộ nguyên văn mã trạng thái thô")

    def test_official_pdf_khong_lo_duong_dan(self):  # BR-E4 / quyết định #8
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        block = einvoice.block_for(si.name, si.customer)
        self.assertNotIn("official_pdf", block)
        for v in block.values():
            if isinstance(v, str):
                self.assertNotIn("/private/files", v)
                self.assertNotIn("/files/", v)


class TestLineage(_E7Fixture):  # NL-12.2 / NL-12.3
    def test_lien_ket_hai_chieu_dieu_chinh(self):
        dn_goc = self._tao_dn(CUSTOMER_BM)
        si_goc = self._tao_si(CUSTOMER_BM, dn=dn_goc)
        fei_goc = self._tao_fei(CUSTOMER_BM, dn_goc, status="08 - CQT chấp nhận")
        self._dinh_pdf(fei_goc)

        dn_moi = self._tao_dn(CUSTOMER_BM)
        si_moi = self._tao_si(CUSTOMER_BM, dn=dn_moi)
        fei_moi = self._tao_fei(
            CUSTOMER_BM, dn_moi, status="06 - Đã phát hành",
            invoice_type="Hóa đơn điều chỉnh", original_document=fei_goc.name,
            adjustment_type="1 - Điều chỉnh giảm", adjustment_reason="Sai đơn giá",
        )
        self._dinh_pdf(fei_moi)
        # `mark_original_superseded` (erpnext/einvoice/lineage.py) — nửa
        # NGƯỢC của brief gốc bỏ sót.
        frappe.db.set_value(FEI, fei_goc.name, "status", "10 - Đã điều chỉnh")
        frappe.db.set_value(FEI, fei_goc.name, "amended_from_fei", fei_moi.name)

        block_goc = einvoice.block_for(si_goc.name, CUSTOMER_BM)
        self.assertEqual(block_goc["trang_thai"], "da_dieu_chinh")
        self.assertIn("hoa_don_moi", block_goc)
        self.assertEqual(block_goc["hoa_don_moi"]["fei"], fei_moi.name)

        block_moi = einvoice.block_for(si_moi.name, CUSTOMER_BM)
        self.assertIn("hoa_don_goc", block_moi)
        self.assertEqual(block_moi["hoa_don_goc"]["fei"], fei_goc.name)

    def test_lien_ket_khac_khach_khong_lo(self):
        """Dữ liệu HĐĐT bị nối sai khách (module khác, có thể do kế toán gõ
        nhầm) không được lộ qua khối lineage."""
        dn_pxn = self._tao_dn(CUSTOMER_PXN)
        si_pxn = self._tao_si(CUSTOMER_PXN, dn=dn_pxn)
        fei_pxn = self._tao_fei(CUSTOMER_PXN, dn_pxn, status="06 - Đã phát hành")

        dn_bm = self._tao_dn(CUSTOMER_BM)
        si_bm = self._tao_si(CUSTOMER_BM, dn=dn_bm)
        fei_bm = self._tao_fei(
            CUSTOMER_BM, dn_bm, status="10 - Đã điều chỉnh",
            amended_from_fei=fei_pxn.name,  # trỏ nhầm sang bản ghi của KH khác
        )

        block = einvoice.block_for(si_bm.name, CUSTOMER_BM)
        self.assertNotIn("hoa_don_moi", block)

    def test_status_12_khong_bia_lien_ket(self):
        """`cancel.py` không để lại field nào nối bản ghi bị hủy với hoá đơn
        mới cho CÙNG delivery_note — `block_for` không được TỰ SUY ra một
        liên kết như vậy."""
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        self._tao_fei(CUSTOMER_BM, dn, status="12 - Đã hủy nội bộ", cancel_reason="CQT từ chối")
        # Một FEI mới cho CÙNG delivery_note (mô phỏng kế toán lập lại) —
        # không có field nào nối nó với bản ghi đã hủy.
        self._tao_fei(CUSTOMER_BM, dn, status="01 - Nháp")

        block = einvoice.block_for(si.name, CUSTOMER_BM)
        self.assertNotIn("hoa_don_moi", block)
        self.assertNotIn("hoa_don_goc", block)


class TestDownloadIsolation(_E7Fixture):  # BR-E4, NL-12.5, TC-E7-03
    def test_zero_docperm_premise(self):
        """Chốt nền tảng của toàn bộ thiết kế E7: role Customer không có
        DocPerm nào trên Fast EInvoice Document. Nếu ai đó lỡ cấp lại quyền,
        test này phải đỏ để nhắc kiểm lại toàn bộ luồng."""
        self.assertFalse(
            frappe.has_permission(FEI, "read", user=BM_USER),
            "Customer không được có quyền đọc trực tiếp Fast EInvoice Document",
        )

    def test_tai_thanh_cong_ghi_log_va_dung_noi_dung(self):
        from erpnext.einvoice.test_fixtures import minimal_pdf_bytes

        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        frappe.set_user(BM_USER)
        so_log_truoc = frappe.db.count("Access Log", {"export_from": FEI, "reference_document": fei.name})
        frappe.local.response = frappe._dict()
        portal.portal_einvoice_download(si.name, loai="pdf")
        noi_dung = frappe.local.response.filecontent
        # `File.get_content()` giải mã sang `str` khi nội dung là ASCII thuần
        # (đúng PDF tối thiểu dùng trong test) — PDF thật (nhị phân) sẽ luôn
        # ra `bytes`; so sánh không phụ thuộc nhánh nào đã chạy.
        if isinstance(noi_dung, str):
            noi_dung = noi_dung.encode()
        self.assertEqual(noi_dung, minimal_pdf_bytes())
        self.assertEqual(frappe.local.response.type, "pdf")
        so_log_sau = frappe.db.count("Access Log", {"export_from": FEI, "reference_document": fei.name})
        self.assertEqual(so_log_sau, so_log_truoc + 1)

    def test_khach_khac_khong_tai_duoc(self):  # TC-E7-03
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        frappe.set_user(PXN_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_einvoice_download(si.name, loai="pdf")

    def test_khach_le_bang_gia_tri_customer(self):
        """SI thuộc BM nhưng qua Party Restriction / trực tiếp gán sai customer
        trên FEI (dữ liệu module khác không khớp SI) — vẫn không lộ."""
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        # Ép fei.customer khác với si.customer, mô phỏng lỗi dữ liệu module HĐĐT.
        frappe.db.set_value(FEI, fei.name, "customer", CUSTOMER_PXN, update_modified=False)
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_einvoice_download(si.name, loai="pdf")

    def test_chua_dang_nhap_bi_chan(self):
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            portal.portal_einvoice_download(si.name, loai="pdf")

    def test_khong_con_xml_loai_bi_tu_choi(self):
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_einvoice_download(si.name, loai="xml")

    def test_trang_thai_chua_phat_hanh_khong_tai_duoc(self):
        si, fei = self._chain(CUSTOMER_BM, status="01 - Nháp", dinh_pdf=False)
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_einvoice_download(si.name, loai="pdf")

    def test_trang_thai_chua_phat_hanh_chan_du_co_file_that(self):
        """Chốt trạng thái (`sua_duoc_tai`) và chốt "file thật đọc được" là
        HAI điều kiện ĐỘC LẬP — dựng riêng ca có File THẬT đính kèm (dữ liệu
        bất thường: PDF bị đính trước khi phát hành) trong khi trạng thái
        vẫn "01 - Nháp", để một test không vô tình chỉ đi qua chốt file mà
        "tưởng" đã kiểm cả chốt trạng thái — nếu thiếu `sua_duoc_tai()`, chốt
        file một mình sẽ CHO QUA vì file đọc được thật."""
        si, fei = self._chain(CUSTOMER_BM, status="01 - Nháp", dinh_pdf=False)
        self._dinh_pdf(fei)
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_einvoice_download(si.name, loai="pdf")

    def test_file_thieu_du_field_con_gia_tri_cu(self):  # NL-12.4
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        # Field còn giá trị cũ nhưng File thật đã bị xoá khỏi hệ thống.
        frappe.db.delete("File", {"attached_to_doctype": FEI, "attached_to_name": fei.name})
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_einvoice_download(si.name, loai="pdf")


class TestHoTro(_E7Fixture):  # NL-12.4
    def test_gui_yeu_cau_ho_tro_tao_notification_cho_ke_toan_hddt(self):
        _ensure_ke_toan_hddt_user()
        si, fei = self._chain(CUSTOMER_BM, status="99 - Lỗi", dinh_pdf=False)
        frappe.set_user(BM_USER)
        result = portal.portal_einvoice_ho_tro(si.name)
        self.assertTrue(result["ok"])
        self.assertTrue(
            frappe.db.exists("Notification Log", {
                "for_user": KE_TOAN_HDDT_USER,
                "document_type": "Sales Invoice",
                "document_name": si.name,
            })
        )

    def test_ho_tro_khong_bi_chan_boi_thieu_nguoi_nhan(self):
        """Không ai giữ role Kế toán HĐĐT vẫn phải trả ok — yêu cầu của khách
        không được biến thành lỗi chỉ vì thiếu người nhận nội bộ."""
        si, fei = self._chain(CUSTOMER_BM, status="99 - Lỗi", dinh_pdf=False)
        frappe.set_user(BM_USER)
        result = portal.portal_einvoice_ho_tro(si.name)
        self.assertTrue(result["ok"])

    def test_ho_tro_khach_khac_bi_chan(self):
        si, fei = self._chain(CUSTOMER_BM, status="99 - Lỗi", dinh_pdf=False)
        frappe.set_user(PXN_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_einvoice_ho_tro(si.name)
