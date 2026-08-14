"""E7 — Hoá đơn điện tử trên cổng, chỉ đọc (QT12).

Nhóm TC-E7 (`DevHandoff/40_TestCases.md`) + các ca biên nêu trong
`.superpowers/sdd/e7/brief-hddt.md` + review round 1 (C-1/I-5): MỘT Sales
Invoice có thể khớp NHIỀU `Fast EInvoice Document` (bản gốc + điều chỉnh/thay
thế + bản lập lại sau huỷ nội bộ) — `lineage.py::_COPIED_FIELDS` copy CẢ
`delivery_note` LẪN `sales_invoice` từ cha sang con, nên cả nhà LUÔN dùng
chung một `delivery_note` (và thường CÙNG một `sales_invoice`, kể cả khi giá
trị đó là rỗng — rỗng thì con cũng thừa hưởng rỗng). Fixture của mọi test
NHIỀU BẢN GHI dưới đây vì thế phải dựng các bản ghi CÙNG một `dn`/`si` — dựng
`dn`/`si` RIÊNG cho "bản điều chỉnh" (như bản test round 1) là một hình dạng
module KHÔNG THỂ sinh ra, và đã từng khiến C-1 xanh giả (xem review).

Điểm quan trọng nhì: `Fast EInvoice Document` hầu như KHÔNG BAO GIỜ có
`sales_invoice` được điền — luồng tạo bản ghi thật
(`builder.py::create_from_delivery_note`) chỉ gán `delivery_note`. Vì vậy
fixture MẶC ĐỊNH của mọi test dưới đây (trừ các test riêng cho trường hợp
NGOẠI LỆ "kế toán tự điền") để `sales_invoice` TRỐNG và chỉ nối qua
`Sales Invoice Item.delivery_note` — đúng đường THẬT `einvoice.resolve_all()`
phải đi qua.
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


def _noi_dung_pdf_tra_ve():
    from erpnext.einvoice.test_fixtures import minimal_pdf_bytes

    noi_dung = frappe.local.response.filecontent
    # `File.get_content()` giải mã sang `str` khi nội dung là ASCII thuần
    # (đúng PDF tối thiểu dùng trong test) — PDF thật (nhị phân) sẽ luôn ra
    # `bytes`; chuẩn hoá về bytes để so sánh không phụ thuộc nhánh nào chạy.
    if isinstance(noi_dung, str):
        noi_dung = noi_dung.encode()
    return noi_dung, minimal_pdf_bytes()


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

    def _tao_si(self, customer, dn=None, dn_list=None):
        si = frappe.new_doc("Sales Invoice")
        si.company = COMPANY
        si.customer = customer
        si.posting_date = today()
        si.set_posting_time = 1
        si.debit_to = DEBIT_TO
        si.update_stock = 0
        for d in (dn_list or ([dn] if dn is not None else [])) or [None]:
            row = {
                "item_code": ITEM, "qty": 1, "rate": 1200,
                "income_account": INCOME_ACCOUNT, "cost_center": COST_CENTER,
            }
            if d is not None:
                row["delivery_note"] = d.name
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
    """`einvoice.resolve_all()` — gộp CẢ HAI tầng (liên kết trực tiếp
    `sales_invoice` VÀ bắc cầu qua `delivery_note`), KHÔNG dừng lại ở bản ghi
    đầu tiên tìm thấy (review round 1, C-1)."""

    def test_lien_ket_qua_delivery_note_la_duong_mac_dinh(self):
        si, fei = self._chain(CUSTOMER_BM, dinh_pdf=False)
        self.assertFalse(fei.sales_invoice)
        found = einvoice.resolve_all(si.name)
        self.assertEqual([f.name for f in found], [fei.name])

    def test_lien_ket_truc_tiep_sales_invoice(self):
        """Trường hợp NGOẠI LỆ (kế toán tự điền `sales_invoice`) — vẫn phải
        tìm thấy."""
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        fei = self._tao_fei(CUSTOMER_BM, dn, sales_invoice=si.name, status="06 - Đã phát hành")
        found = einvoice.resolve_all(si.name)
        self.assertEqual([f.name for f in found], [fei.name])

    def test_khong_co_ban_ghi_hddt_nao_tra_rong(self):
        si = self._tao_si(CUSTOMER_BM)
        self.assertEqual(einvoice.resolve_all(si.name), [])

    def test_gop_ca_hai_tang_khong_chi_tang_1(self):
        """C-1: một bản ghi nối qua `delivery_note` VÀ một bản ghi khác nối
        trực tiếp qua `sales_invoice` của CÙNG hoá đơn đều phải có mặt —
        không được "tầng 1 thắng thì bỏ qua tầng 2"."""
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        fei_qua_dn = self._tao_fei(CUSTOMER_BM, dn, status="06 - Đã phát hành")
        fei_truc_tiep = self._tao_fei(CUSTOMER_BM, dn, sales_invoice=si.name, status="01 - Nháp")
        found = {f.name for f in einvoice.resolve_all(si.name)}
        self.assertEqual(found, {fei_qua_dn.name, fei_truc_tiep.name})

    def test_sap_theo_creation_tang_dan(self):
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        fei1 = self._tao_fei(CUSTOMER_BM, dn, status="08 - CQT chấp nhận")
        fei2 = self._tao_fei(CUSTOMER_BM, dn, status="01 - Nháp")
        found = einvoice.resolve_all(si.name)
        self.assertEqual([f.name for f in found], [fei1.name, fei2.name])


class TestBadgeGroups(_E7Fixture):
    def test_chua_ghi_so_hddt_khong_nut_tai_cong_no_van_hien(self):  # TC-E7-01
        si, fei = self._chain(CUSTOMER_BM, status="01 - Nháp", dinh_pdf=False)
        block = einvoice.block_for(si.name, si.customer)["chinh"]
        # ĐỔI CÓ CHỦ Ý (E7b): 01–04 nay là nhóm "nhap" chứ không còn gộp vào
        # "dang_phat_hanh" — khách được XEM bản nháp. Điều KHÔNG đổi, và là
        # thứ ca này thật sự canh giữ: chưa có số hoá đơn thì không có nút tải
        # PDF chính thức, và công nợ vẫn hiển thị bình thường.
        self.assertEqual(block["trang_thai"], "nhap")
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
        block = einvoice.block_for(si.name, si.customer)["chinh"]
        self.assertEqual(block["trang_thai"], "dang_phat_hanh")
        self.assertFalse(block["tai_duoc"])

    def test_da_phat_hanh_co_file_thi_tai_duoc(self):  # TC-E7-02
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        block = einvoice.block_for(si.name, si.customer)["chinh"]
        self.assertEqual(block["trang_thai"], "da_phat_hanh")
        self.assertTrue(block["tai_duoc"])
        self.assertFalse(block["ho_tro"])

    def test_mau_so_di_kem_ky_hieu(self):  # review round 1, I-1
        si, fei = self._chain(
            CUSTOMER_BM, status="06 - Đã phát hành",
            fast_pattern="1", fast_serial="C26TAA",
        )
        block = einvoice.block_for(si.name, si.customer)["chinh"]
        self.assertEqual(block["mau_so"], "1")
        self.assertEqual(block["ky_hieu"], "C26TAA")

    def test_da_phat_hanh_nhung_pdf_chua_co_la_trang_thai_rieng(self):
        """`official_pdf` được đính qua job NỀN (đợi ký số HSM) — trạng thái
        06 mà chưa có file là một tình huống THẬT, không phải lỗi test."""
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành", dinh_pdf=False)
        block = einvoice.block_for(si.name, si.customer)["chinh"]
        self.assertEqual(block["trang_thai"], "da_phat_hanh")
        self.assertFalse(block["tai_duoc"])
        self.assertTrue(block["ho_tro"])
        self.assertIn("file đang xử lý", block["nhan"])

    def test_cqt_tu_choi_van_tai_duoc_nhung_nhan_rieng(self):
        si, fei = self._chain(CUSTOMER_BM, status="09 - CQT từ chối")
        block = einvoice.block_for(si.name, si.customer)["chinh"]
        self.assertEqual(block["trang_thai"], "cqt_tu_choi")
        self.assertTrue(block["tai_duoc"])
        self.assertNotEqual(block["nhan"], "Đã phát hành")

    def test_da_huy_khong_giau_hoa_don_cu(self):  # NL-12.2 / M-1
        si, fei = self._chain(
            CUSTOMER_BM, status="12 - Đã hủy nội bộ", cancel_reason="Sai mã số thuế",
        )
        block = einvoice.block_for(si.name, si.customer)["chinh"]
        self.assertEqual(block["trang_thai"], "da_huy")
        self.assertEqual(block["ly_do_huy"], "Sai mã số thuế")
        # "Không bị giấu": dòng hoá đơn vẫn có trong danh sách của khách.
        frappe.set_user(BM_USER)
        names = {r["name"] for r in portal.portal_invoices(limit=200)}
        self.assertIn(si.name, names)

    def test_trang_thai_loi_disable_tai_va_hien_ho_tro(self):  # NL-12.4
        for status in ("98 - Cần đối soát", "99 - Lỗi"):
            si, fei = self._chain(CUSTOMER_BM, status=status, dinh_pdf=False)
            block = einvoice.block_for(si.name, si.customer)["chinh"]
            self.assertEqual(block["trang_thai"], "loi", status)
            self.assertFalse(block["tai_duoc"], status)
            self.assertTrue(block["ho_tro"], status)

    def test_trang_thai_tho_khong_lo_ra_ngoai(self):
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        block = einvoice.block_for(si.name, si.customer)["chinh"]
        self.assertNotEqual(block["trang_thai"], fei.status)
        for v in block.values():
            if isinstance(v, str):
                self.assertNotIn(fei.status, v, "không được lộ nguyên văn mã trạng thái thô")

    def test_official_pdf_khong_lo_duong_dan(self):  # BR-E4 / quyết định #8
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        block = einvoice.block_for(si.name, si.customer)["chinh"]
        self.assertNotIn("official_pdf", block)
        for v in block.values():
            if isinstance(v, str):
                self.assertNotIn("/private/files", v)
                self.assertNotIn("/files/", v)

    def test_status_meta_khop_dung_14_ma_that(self):
        """Chốt từ vựng: `_STATUS_META` phải khớp CHÍNH XÁC 14 mã của
        `erpnext.einvoice.constants.STATUSES` — nếu module HĐĐT đổi/thêm mã
        mà không cập nhật adapter, test này đỏ thay vì badge âm thầm rơi về
        "Đang phát hành HĐĐT" sai sự thật cho một trạng thái đã biết."""
        from erpnext.einvoice.constants import STATUSES

        self.assertEqual(set(einvoice._STATUS_META), set(STATUSES))

    def test_bao_loi_khong_lam_mat_ca_danh_sach_hoa_don(self):
        """`portal_invoices` không được phụ thuộc module HĐĐT còn nguyên vẹn
        — một field đổi tên/`Fast EInvoice Document` bị sửa cấu trúc không
        được phép làm mất cả danh sách hoá đơn + công nợ (NL-12.1)."""
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        truoc = einvoice._FIELDS
        einvoice._FIELDS = ("name", "creation", "status", "truong_khong_ton_tai_xyz")
        try:
            frappe.set_user(BM_USER)
            rows = {r["name"]: r for r in portal.portal_invoices(limit=200)}
        finally:
            einvoice._FIELDS = truoc
        self.assertIn(si.name, rows)
        self.assertIn("outstanding_amount", rows[si.name])
        self.assertEqual(rows[si.name]["einvoice"]["chinh"]["trang_thai"], "dang_phat_hanh")


class TestLineage(_E7Fixture):  # NL-12.2 / NL-12.3
    """Tất cả fixture ở đây dùng CHUNG một `dn`/`si` cho cả gốc lẫn con —
    đúng hình dạng THẬT (`_COPIED_FIELDS` copy cả hai field), xem docstring
    module. Dựng `dn`/`si` riêng cho bản con (như trước review round 1) tạo
    ra một hình dạng module không thể sinh ra và che mất bug C-1."""

    def test_lien_ket_hai_chieu_dieu_chinh(self):
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        goc = self._tao_fei(CUSTOMER_BM, dn, status="08 - CQT chấp nhận")
        self._dinh_pdf(goc)

        con = self._tao_fei(
            CUSTOMER_BM, dn, status="06 - Đã phát hành",
            invoice_type="Hóa đơn điều chỉnh", original_document=goc.name,
            adjustment_type="1 - Điều chỉnh giảm", adjustment_reason="Sai đơn giá",
        )
        self._dinh_pdf(con)
        # review P0 (kiểm thử hệ thống, TC-E7-04) — GỌI THẬT
        # `mark_original_superseded` (erpnext/einvoice/lineage.py) thay vì
        # tự tay ghi `status`/`amended_from_fei`: bản trước dựng đúng hai
        # giá trị hàm này ghi, nhưng không bao giờ gọi hàm — upstream đổi
        # cách ghi (tên field, giá trị status) thì fixture vẫn "đúng" theo
        # trí nhớ cũ trong khi cổng hiển thị sai badge trên chứng từ thuế đã
        # huỷ, và test vẫn xanh. Gọi hàm thật đóng khoảng hở đó.
        from erpnext.einvoice.lineage import mark_original_superseded
        mark_original_superseded(con)

        block = einvoice.block_for(si.name, CUSTOMER_BM)
        # Con đã phát hành -> trở thành bản ghi CHÍNH; gốc (đã bị điều
        # chỉnh) chuyển sang `khac` nhưng KHÔNG biến mất (review round 1 C-1).
        self.assertEqual(block["chinh"]["fei"], con.name)
        self.assertIn("hoa_don_goc", block["chinh"])
        self.assertEqual(block["chinh"]["hoa_don_goc"]["fei"], goc.name)

        khac = {m["fei"]: m for m in block["khac"]}
        self.assertIn(goc.name, khac)
        self.assertEqual(khac[goc.name]["trang_thai"], "da_dieu_chinh")
        # Bản mẫu (id `einv-row`) đặt số hoá đơn liên quan NGAY TRONG NHÃN
        # thu gọn, không phải một nhãn tĩnh — khớp lại đúng hình dạng đó.
        self.assertIn(con.fast_invoice_no or con.name, khac[goc.name]["nhan"])
        # Bản gốc bị điều chỉnh VẪN còn giá trị pháp lý -> vẫn phải tải được
        # (review round 1, kịch bản (b) — lỗi trước đó khiến nó vĩnh viễn
        # không tải được).
        self.assertTrue(khac[goc.name]["tai_duoc"])

    def test_nhan_thay_the_khop_chu_ban_mau(self):
        """Prototype: badge thu gọn đọc "Đã huỷ — thay bằng {số}" cho hoá đơn
        đã bị THAY THẾ (11), không phải một nhãn tĩnh "Đã thay thế"."""
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        goc = self._tao_fei(CUSTOMER_BM, dn, status="08 - CQT chấp nhận")
        self._dinh_pdf(goc)

        con = self._tao_fei(
            CUSTOMER_BM, dn, status="06 - Đã phát hành",
            invoice_type="Hóa đơn thay thế", original_document=goc.name,
            adjustment_reason="Sai tên hàng hoá",
        )
        self._dinh_pdf(con)
        # review P0 (kiểm thử hệ thống, TC-E7-04) — gọi hàm thật, xem giải
        # thích ở `test_lien_ket_hai_chieu_dieu_chinh` phía trên.
        from erpnext.einvoice.lineage import mark_original_superseded
        mark_original_superseded(con)

        block = einvoice.block_for(si.name, CUSTOMER_BM)
        khac = {m["fei"]: m for m in block["khac"]}
        self.assertEqual(khac[goc.name]["trang_thai"], "da_thay_the")
        self.assertTrue(khac[goc.name]["nhan"].startswith("Đã huỷ — thay bằng "))
        self.assertIn(con.fast_invoice_no or con.name, khac[goc.name]["nhan"])

    def test_lien_ket_khac_khach_khong_lo(self):
        """Dữ liệu HĐĐT bị nối sai khách (module khác, có thể do kế toán gõ
        nhầm) không được lộ qua khối lineage."""
        dn_pxn = self._tao_dn(CUSTOMER_PXN)
        fei_pxn = self._tao_fei(CUSTOMER_PXN, dn_pxn, status="06 - Đã phát hành")

        dn_bm = self._tao_dn(CUSTOMER_BM)
        si_bm = self._tao_si(CUSTOMER_BM, dn=dn_bm)
        self._tao_fei(
            CUSTOMER_BM, dn_bm, status="10 - Đã điều chỉnh",
            amended_from_fei=fei_pxn.name,  # trỏ nhầm sang bản ghi của KH khác
        )

        block = einvoice.block_for(si_bm.name, CUSTOMER_BM)
        self.assertNotIn("hoa_don_moi", block["chinh"])


class TestMultiFEI(_E7Fixture):
    """Review round 1, C-1 — một Sales Invoice khớp NHIỀU `Fast EInvoice
    Document` cùng lúc. Bốn kịch bản trong review, đặt tên (a)-(d) khớp thứ
    tự đó."""

    def test_a_dieu_chinh_dang_soan_khong_che_ban_goc(self):
        """(a) Kế toán vừa bấm "Lập hoá đơn điều chỉnh" (con "01 - Nháp")
        cho một hoá đơn ĐÃ ĐƯỢC CQT CHẤP NHẬN — bản gốc còn NGUYÊN giá trị,
        badge chính KHÔNG được lật sang "Đang phát hành HĐĐT"."""
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        goc = self._tao_fei(CUSTOMER_BM, dn, status="08 - CQT chấp nhận")
        self._dinh_pdf(goc)
        con = self._tao_fei(CUSTOMER_BM, dn, status="01 - Nháp", original_document=goc.name)

        block = einvoice.block_for(si.name, CUSTOMER_BM)
        self.assertEqual(block["chinh"]["fei"], goc.name)
        self.assertEqual(block["chinh"]["trang_thai"], "da_phat_hanh")
        self.assertTrue(block["chinh"]["tai_duoc"])
        self.assertEqual({m["fei"] for m in block["khac"]}, {con.name})

        # Endpoint mặc định (không truyền `fei`) vẫn tải được bản GỐC.
        frappe.set_user(BM_USER)
        frappe.local.response = frappe._dict()
        portal.portal_einvoice_download(si.name, loai="pdf")
        thuc_te, ky_vong = _noi_dung_pdf_tra_ve()
        self.assertEqual(thuc_te, ky_vong)

    def test_b_ban_goc_van_tai_duoc_sau_khi_bi_dieu_chinh(self):
        """(b) Sau khi con phát hành xong, bản GỐC (điều chỉnh, không phải
        thay thế) vẫn còn giá trị pháp lý — phải tải được qua `fei=`."""
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        goc = self._tao_fei(CUSTOMER_BM, dn, status="08 - CQT chấp nhận")
        self._dinh_pdf(goc)
        con = self._tao_fei(
            CUSTOMER_BM, dn, status="06 - Đã phát hành",
            invoice_type="Hóa đơn điều chỉnh", original_document=goc.name,
            adjustment_type="1 - Điều chỉnh giảm", adjustment_reason="Sai đơn giá",
        )
        self._dinh_pdf(con)
        # review P0 (kiểm thử hệ thống, TC-E7-04) — gọi hàm thật, xem giải
        # thích ở `TestLineage.test_lien_ket_hai_chieu_dieu_chinh`.
        from erpnext.einvoice.lineage import mark_original_superseded
        mark_original_superseded(con)

        frappe.set_user(BM_USER)
        frappe.local.response = frappe._dict()
        portal.portal_einvoice_download(si.name, loai="pdf", fei=goc.name)
        thuc_te, ky_vong = _noi_dung_pdf_tra_ve()
        self.assertEqual(thuc_te, ky_vong)

    def test_c_ban_ghi_huy_van_hien_du_khong_co_lien_ket(self):
        """(c) Bản ghi bị huỷ nội bộ, kế toán lập bản MỚI cho CÙNG phiếu
        giao (không field nào nối hai bản) — bản đã huỷ KHÔNG được biến mất
        khỏi khối HĐĐT, và không bị bịa liên kết với bản mới."""
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        huy = self._tao_fei(CUSTOMER_BM, dn, status="12 - Đã hủy nội bộ", cancel_reason="CQT từ chối")
        self._dinh_pdf(huy)
        moi = self._tao_fei(CUSTOMER_BM, dn, status="01 - Nháp")

        block = einvoice.block_for(si.name, CUSTOMER_BM)
        toan_bo = {m["fei"]: m for m in [block["chinh"], *block["khac"]]}
        self.assertIn(huy.name, toan_bo, "hoá đơn đã huỷ không được biến mất khỏi khối HĐĐT")
        self.assertEqual(toan_bo[huy.name]["trang_thai"], "da_huy")
        self.assertEqual(toan_bo[huy.name]["ly_do_huy"], "CQT từ chối")
        self.assertNotIn("hoa_don_moi", toan_bo[huy.name])
        self.assertIn(moi.name, toan_bo)

    def test_d_hai_gia_dinh_doc_lap_deu_hien(self):
        """(d) Sales Invoice gộp HAI Delivery Note, mỗi DN một chứng từ HĐĐT
        độc lập (không lineage giữa chúng) — cả hai phải xuất hiện, không
        được chọn tuỳ ý một cái rồi bỏ quên cái còn lại."""
        dn1 = self._tao_dn(CUSTOMER_BM)
        dn2 = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn_list=[dn1, dn2])

        fei1 = self._tao_fei(CUSTOMER_BM, dn1, status="06 - Đã phát hành")
        self._dinh_pdf(fei1)
        fei2 = self._tao_fei(CUSTOMER_BM, dn2, status="08 - CQT chấp nhận")
        self._dinh_pdf(fei2)

        block = einvoice.block_for(si.name, CUSTOMER_BM)
        toan_bo = {block["chinh"]["fei"], *[m["fei"] for m in block["khac"]]}
        self.assertEqual(toan_bo, {fei1.name, fei2.name})


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
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        frappe.set_user(BM_USER)
        so_log_truoc = frappe.db.count("Access Log", {"export_from": FEI, "reference_document": fei.name})
        frappe.local.response = frappe._dict()
        portal.portal_einvoice_download(si.name, loai="pdf")
        thuc_te, ky_vong = _noi_dung_pdf_tra_ve()
        self.assertEqual(thuc_te, ky_vong)
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

    def test_fei_tham_so_khong_thuoc_hoa_don_bi_chan(self):
        """`fei` do client gửi CHỈ được dùng để lọc trong tập đã tự resolve
        — một FEI CÓ THẬT nhưng thuộc HOÁ ĐƠN KHÁC của CÙNG khách không được
        chọn bừa."""
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        si2, fei2 = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_einvoice_download(si.name, loai="pdf", fei=fei2.name)

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
        """Chốt trạng thái (`co_the_tai`) và chốt "file thật đọc được" là
        HAI điều kiện ĐỘC LẬP — dựng riêng ca có File THẬT đính kèm (dữ liệu
        bất thường: PDF bị đính trước khi phát hành) trong khi trạng thái
        vẫn "01 - Nháp", để một test không vô tình chỉ đi qua chốt file mà
        "tưởng" đã kiểm cả chốt trạng thái — nếu thiếu `co_the_tai()`, chốt
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

    def test_doc_chi_khong_dong_cham_fast_einvoice_document(self):  # BR-E5
        """Cổng chỉ đọc: gọi đủ ba endpoint đọc (danh sách, tải, xem chi
        tiết qua block_for) không được đổi bất kỳ trường nào — chưa nói tới
        `modified` — trên `Fast EInvoice Document`, doctype của module khác."""
        si, fei = self._chain(CUSTOMER_BM, status="06 - Đã phát hành")
        truoc = frappe.get_doc(FEI, fei.name).as_json()
        frappe.set_user(BM_USER)
        portal.portal_invoices(limit=200)
        frappe.local.response = frappe._dict()
        portal.portal_einvoice_download(si.name, loai="pdf")
        einvoice.block_for(si.name, CUSTOMER_BM)
        sau = frappe.get_doc(FEI, fei.name).as_json()
        self.assertEqual(truoc, sau)


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

    def test_dedupe_theo_ngay_khong_tao_notification_thua(self):  # review M-8
        _ensure_ke_toan_hddt_user()
        si, fei = self._chain(CUSTOMER_BM, status="99 - Lỗi", dinh_pdf=False)
        frappe.set_user(BM_USER)
        portal.portal_einvoice_ho_tro(si.name)
        portal.portal_einvoice_ho_tro(si.name)
        so_luong = frappe.db.count("Notification Log", {
            "for_user": KE_TOAN_HDDT_USER, "document_name": si.name,
        })
        self.assertEqual(so_luong, 1, "bấm lại trong cùng ngày không được tạo thêm Notification Log")

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


class TestKhongNoiSaiPhapLy(FrappeTestCase):  # review round 1, M-6
    """BR-E1: cổng chỉ giao PDF (bản thể hiện), không có XML (bản gốc). Câu
    chú thích cố định của bản mẫu ("File XML là bản gốc có giá trị pháp lý;
    PDF là bản thể hiện") nói SAI trong hoàn cảnh đó — khoá vĩnh viễn quy tắc
    "không lặp lại câu đó" bằng một test rẻ, thay vì chỉ tin hai chuỗi viết
    tay trong Vue không ai canh gác."""

    def test_khong_ton_tai_cau_chu_thich_sai_phap_ly(self):
        import pathlib

        # apps/miyano_portal/miyano_portal/tests/test_e7_hddt.py
        #   parents[0]=tests  [1]=miyano_portal(package)  [2]=miyano_portal(app root)
        duong_dan = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "views" / "Invoices.vue"
        noi_dung = duong_dan.read_text(encoding="utf-8")
        self.assertNotIn(
            "File XML là bản gốc có giá trị pháp lý", noi_dung,
            "câu chú thích của bản mẫu nói SAI khi cổng chỉ giao PDF — không được lặp lại nguyên văn",
        )


class TestNhomNhap(_E7Fixture):
    """01–04 là BẢN NHÁP có thật, khách xem được — khác hẳn "đang phát hành"
    (05, nội dung đã chốt, đang chờ Fast) và khác "chưa có chứng từ nào"
    (NL-12.1 — công nợ vẫn hiện bình thường)."""

    def _dinh_pdf_nhap(self, fei_doc):
        from erpnext.einvoice.test_fixtures import minimal_pdf_bytes
        from frappe.utils.file_manager import save_file

        f = save_file(f"Nhap_{fei_doc.name}.pdf", minimal_pdf_bytes(), FEI, fei_doc.name, is_private=1)
        frappe.db.set_value(FEI, fei_doc.name, "draft_pdf", f.file_url, update_modified=False)
        fei_doc.reload()
        return f

    def test_bon_trang_thai_nhap_deu_vao_nhom_nhap(self):
        for status in ("01 - Nháp", "02 - Đã xem nháp", "03 - Chờ khách duyệt", "04 - Khách đã duyệt"):
            with self.subTest(status=status):
                si, fei = self._chain(CUSTOMER_BM, status=status, dinh_pdf=False)
                block = einvoice.block_for(si.name, CUSTOMER_BM)["chinh"]
                self.assertEqual(block["trang_thai"], "nhap")
                self.assertEqual(block["nhan"], "Hoá đơn nháp")

    def test_co_pdf_nhap_thi_nhap_tai_duoc(self):
        si, fei = self._chain(CUSTOMER_BM, status="02 - Đã xem nháp", dinh_pdf=False)
        self._dinh_pdf_nhap(fei)
        block = einvoice.block_for(si.name, CUSTOMER_BM)["chinh"]
        self.assertTrue(block["nhap_tai_duoc"])
        self.assertFalse(block["tai_duoc"], "nút PDF CHÍNH THỨC vẫn phải tắt")

    def test_chua_co_pdf_nhap_thi_khong_tai_duoc(self):
        si, fei = self._chain(CUSTOMER_BM, status="01 - Nháp", dinh_pdf=False)
        block = einvoice.block_for(si.name, CUSTOMER_BM)["chinh"]
        self.assertFalse(block["nhap_tai_duoc"])

    def test_05_van_la_dang_phat_hanh(self):
        si, fei = self._chain(CUSTOMER_BM, status="05 - Đang phát hành", dinh_pdf=False)
        block = einvoice.block_for(si.name, CUSTOMER_BM)["chinh"]
        self.assertEqual(block["trang_thai"], "dang_phat_hanh")

    def test_co_the_tai_van_chan_ban_nhap(self):
        """Chốt chống lỗi nghiêm trọng: nhóm `nhap` KHÔNG được mở đường tải
        PDF CHÍNH THỨC. `co_the_tai` phục vụ `portal_einvoice_download`."""
        for status in ("01 - Nháp", "02 - Đã xem nháp", "03 - Chờ khách duyệt", "04 - Khách đã duyệt"):
            with self.subTest(status=status):
                self.assertFalse(einvoice.co_the_tai(frappe._dict(status=status)))

    def test_khoi_json_khong_lo_duong_dan_draft_pdf(self):  # BR-E4
        import json

        si, fei = self._chain(CUSTOMER_BM, status="02 - Đã xem nháp", dinh_pdf=False)
        f = self._dinh_pdf_nhap(fei)
        block = einvoice.block_for(si.name, CUSTOMER_BM)
        self.assertNotIn(f.file_url, json.dumps(block, default=str))

    def test_canh_bao_phap_ly_do_server_tra(self):
        self.assertIn("KHÔNG có giá trị pháp lý", einvoice.CANH_BAO_NHAP)
        self.assertIn("chưa ký số", einvoice.CANH_BAO_NHAP)
