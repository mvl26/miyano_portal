"""Cách ly dữ liệu kho — HỢP ĐỒNG HIỆN HÀNH (vòng 4).

Hợp đồng cũ (vòng 1-3) là: "khách A gọi get_list thấy đúng các dòng của A".
Hợp đồng MỚI mạnh hơn hẳn: tài khoản portal KHÔNG đọc được doctype kho nào qua
bất kỳ đường trực tiếp nào — get_list, REST v1/v2, /printview, download_pdf,
frappe.client.* đều ném PermissionError, KỂ CẢ cho dữ liệu của chính họ. Lý do:
role `Customer` không còn DocPerm nào trên doctype kho cha, nên không còn grant
nền để bất kỳ đường nào tụt về. Cổng duy nhất là API whitelist
miyano_portal/api/kho.py, nơi kho được suy từ phiên và lọc tường minh.

Vì mọi assertion phủ định ở đây giờ đều pass dưới một lỗi "cấm tiệt tất cả",
mỗi nhóm test phủ định BẮT BUỘC đi kèm positive control tương ứng:
  * TestKhoApiDoorStillOpen — API kho vẫn trả đúng dữ liệu của người gọi;
  * TestKhoStaffDeskAccess  — System Manager vẫn có toàn quyền desk;
  * các test `..._staff_...` rải trong TestKhoPortalDoorClosed.
Xoá một trong các positive control đó là biến cả file này thành vô nghĩa.
"""

import frappe
from frappe import client as frappe_client
from frappe.model.base_document import get_controller
from frappe.model.document import Document
from frappe.tests.utils import FrappeTestCase
from frappe.www import printview
from miyano_portal.api import kho as kho_api
from miyano_portal.kho import permissions as kho_perms
from miyano_portal.kho.voucher_item import VoucherItemBase
from miyano_portal.portal_context import (
	get_allowed_khos, get_portal_customer, get_portal_kho,
)
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"
CUSTOMER_BM = "Bệnh viện Bạch Mai"
CUSTOMER_PXN = "PXN ABC"

# Ba role nhân viên Miyano PHẢI giữ nguyên quyền desk. Assert sự có mặt của
# chúng để một bản vá "xoá sạch mảng permissions" không lọt qua bộ test này.
STAFF_ROLES = ["System Manager", "Sales Manager", "Sales User"]

# Module chứa toàn bộ doctype của app. Hai tiền tố dưới đây là quy ước đặt tên
# của MỘT HỌ chứng từ/danh mục kho nhiều-doctype — mọi doctype kho thuộc họ
# đó, hiện tại và tương lai, đều bắt đầu bằng một trong hai.
KHO_MODULE = "Miyano Portal"
KHO_PREFIXES = ("Customer Warehouse", "Customer Stock")

# Doctype kho nhưng KHÔNG chia sẻ tiền tố với "anh em" nào — mỗi tên ở đây là
# một danh mục riêng, độc lập của kho (NCC, khoa phòng...), không phải một họ
# nhiều-doctype kiểu "Customer Stock *". Khai báo TƯỜNG MINH từng TÊN ĐẦY ĐỦ,
# so bằng SO KHỚP CHÍNH XÁC (==), khác hẳn cơ chế startswith() của
# KHO_PREFIXES.
#
# M-8 (review E4 phần A): bản trước nhét thẳng "Customer Supplier" vào
# KHO_PREFIXES. Nhìn giống gọn nhưng SAI VỀ CHẤT: KHO_PREFIXES so bằng
# startswith(), nên một chuỗi ĐẦY ĐỦ nằm trong đó biến _nap_doctype_kho()
# thành một allowlist thủ công cho ĐÚNG MỘT tên — bất kỳ doctype tương lai
# nào tình cờ bắt đầu bằng "Customer Supplier..." (ví dụ "Customer Supplier
# Contact") sẽ lọt qua vô hình, đúng kiểu lưới an toàn mà _nap_doctype_kho()
# sinh ra để chặn. "Customer Department" (E8) sẽ gặp đúng ngã ba này — thêm
# nó vào ĐÂY, không phải vào KHO_PREFIXES.
# E6: `Portal Item Request` mang dữ liệu của khách (mỗi yêu cầu thuộc một
# khách qua field `customer`) — KHÔNG được nhét vào KHONG_PHAI_DOCTYPE_KHO.
# Về HÌNH DẠNG nó gần Sales Order/Delivery Note (permissions.py, lọc theo
# `customer` trực tiếp) hơn là các doctype "kho" khác trong danh sách này
# (lọc theo `kho`) — nhưng Sales Order không thuộc module "Miyano Portal" nên
# không bị _nap_doctype_kho() quét tới; "Portal Item Request" THÌ có, và phải
# được phân loại vào một trong ba nhóm. Đứng tên ở đây (không chia sẻ tiền tố
# với ai) vì nó là một danh mục độc lập, giống "Customer Supplier".
KHO_DOCTYPES_KHAC: tuple[str, ...] = (
    "Customer Supplier", "Portal Item Request", "Customer Department",
)

# Doctype thuộc module `Miyano Portal` nhưng CỐ Ý không phải doctype kho. Danh
# sách này tồn tại để việc thêm một doctype không-kho vào module trở thành một
# quyết định TƯỜNG MINH: _nap_doctype_kho() ném lỗi khi gặp một cái tên nó
# không phân loại được, thay vì âm thầm bỏ qua. Bỏ qua âm thầm chính là cách
# một doctype kho đặt tên lệch quy ước sẽ ship ra với zero độ phủ cách ly.
#
# `Miyano Portal Settings` (P0, 2026-08-12) là mục đầu tiên: Single doctype
# chứa tham số vận hành cổng (ngưỡng duyệt, kỳ ADU, SLA...). Không phải kho,
# không mang dữ liệu của khách hàng nào, và chỉ `System Manager` có DocPerm —
# nên nó nằm ngoài mọi vòng kiểm cách ly theo khách bên dưới. Cơ chế lưới an
# toàn này đã hoạt động đúng như thiết kế: 30 test đỏ ngay khi doctype mới
# xuất hiện mà chưa được phân loại.
KHONG_PHAI_DOCTYPE_KHO: tuple[str, ...] = ("Miyano Portal Settings",)

# --------------------------------------------------------------------- AN-1
# AN-1 (báo cáo kiểm thử hệ thống 2026-08-14, mục 4 / P1 #5): `_nap_doctype_
# kho()` phía trên chỉ quét `module="Miyano Portal"` — `Fast EInvoice
# Document` thuộc module `Einvoice` của app `erpnext` (tích hợp hoá đơn điện
# tử "Fast") nằm NGOÀI lưới quét đó, nên độ phủ cách ly của nó hoàn toàn dựa
# vào test viết tay, không có gì buộc một doctype thứ hai của module này
# (bảng log, đối soát...) phải được phân loại. Mở MỘT LƯỚI RIÊNG cho module
# này — KHÔNG gộp vào kho_doctypes()/kho_parent_doctypes(): rất nhiều test
# lặp qua hai hàm đó để SEED một bản ghi có field `kho`/`customer` (hình dạng
# "kho khách hàng"); `Fast EInvoice *` có hình dạng hoàn toàn khác (buyer_*,
# fei_document, lines...), gộp vào sẽ làm vỡ hàng loạt test đó mà không tăng
# thêm gì cho an ninh.
EINVOICE_MODULE = "Einvoice"

# Doctype MANG dữ liệu khách (customer/buyer_* trực tiếp, hoặc link/child về
# một doctype có customer/buyer_*) — phải nằm trong diện phủ cách ly.
#
#   * "Fast EInvoice Document" — có field `customer` (Link Customer) trực
#     tiếp. Doctype CHA duy nhất trong module này ĐÃ được nối dây cả hai hook
#     permission_query_conditions/has_permission (hooks.py:144-148/184) —
#     xem test_fast_einvoice_document_co_lop_phong_thu_thu_hai bên dưới.
#   * "Fast EInvoice Line" — istable=1, bảng con `lines` của Document (dòng
#     hàng hoá đơn: item_code/qty/price...). Cùng nguyên tắc với
#     kho_child_doctypes(): Frappe route has_child_permission() thẳng về
#     PARENT trước khi has_permission của CHÍNH bảng con có cơ hội chạy, nên
#     không cần (và không được) đăng ký riêng.
#   * "Fast EInvoice Log" — KHÔNG phải bảng con (istable=0, đứng độc lập),
#     chỉ LIÊN KẾT tới Document qua field `fei_document`; `request_json`/
#     `response_raw` là payload gửi/nhận API Fast, có thể chứa buyer_name/
#     customer_tax_code. KHÁC với Document, nó KHÔNG có wiring hook riêng
#     nào — an toàn của nó hôm nay dựa 100% vào lớp phòng thủ CHÍNH (zero
#     DocPerm cho role Customer, xem
#     test_customer_role_khong_co_docperm_tren_doctype_einvoice_nao). Đã
#     `grep` toàn bộ `miyano_portal/` — không endpoint whitelist nào của app
#     này trả dữ liệu Log, nên đây là một lớp phòng thủ thứ hai còn THIẾU,
#     không phải một lỗ hổng đang khai thác được; liệt kê tường minh ở đây để
#     quyết định đó hiện ra trên giấy thay vì chìm trong im lặng.
EINVOICE_DOCTYPES_MANG_DU_LIEU_KHACH: tuple[str, ...] = (
    "Fast EInvoice Document", "Fast EInvoice Line", "Fast EInvoice Log",
)

# Miễn trừ tường minh — cấu hình vận hành module Fast, không gắn danh tính
# khách hàng nào (khuôn giống KHONG_PHAI_DOCTYPE_KHO/"Miyano Portal
# Settings" phía trên).
#   * "Fast EInvoice Settings" — Single, tham số kết nối API Fast (api_url,
#     token, template email...).
#   * "Fast EInvoice Notify User" — istable=1, bảng con multiselect của
#     Settings (`notify_on_error`): danh sách USER NỘI BỘ Miyano nhận cảnh
#     báo lỗi, không phải dữ liệu của khách hàng nào.
EINVOICE_DOCTYPES_KHONG_MANG_DU_LIEU_KHACH: tuple[str, ...] = (
    "Fast EInvoice Settings", "Fast EInvoice Notify User",
)


def _nap_doctype_einvoice() -> dict[str, list[str]]:
    """Liệt kê doctype của module `Einvoice` từ DATABASE lúc chạy test, cùng
    nguyên tắc "ném lỗi khi gặp tên lạ" như `_nap_doctype_kho()` — xem AN-1 ở
    trên. KHÔNG lọc theo tiền tố/tên ở tầng SQL, lấy TOÀN BỘ rồi mới phân
    loại trong Python, để một doctype lệch cả hai danh sách buộc phải hiện ra
    thay vì biến mất khỏi kết quả truy vấn."""
    rows = frappe.get_all(
        "DocType",
        filters={"module": EINVOICE_MODULE},
        fields=["name", "istable"],
        order_by="name asc",
    )
    if not rows:
        frappe.throw(
            f"Không tìm thấy doctype nào trong module {EINVOICE_MODULE} — "
            "danh sách rỗng sẽ khiến mọi vòng lặp test bên dưới pass vô "
            "nghĩa. Kiểm tra lại tên module (module HĐĐT có thể đã đổi tên)."
        )
    la = [
        r.name for r in rows
        if r.name not in EINVOICE_DOCTYPES_MANG_DU_LIEU_KHACH
        and r.name not in EINVOICE_DOCTYPES_KHONG_MANG_DU_LIEU_KHACH
    ]
    if la:
        frappe.throw(
            f"Doctype {la} thuộc module {EINVOICE_MODULE} chưa được phân "
            "loại. Khai tên ĐẦY ĐỦ vào EINVOICE_DOCTYPES_MANG_DU_LIEU_KHACH "
            "(nếu nó mang dữ liệu khách — kể cả gián tiếp qua link/child) "
            "hoặc EINVOICE_DOCTYPES_KHONG_MANG_DU_LIEU_KHACH (nếu không), "
            "trong test_kho_isolation.py — xem AN-1."
        )
    return {
        "all": [r.name for r in rows],
        "mang_du_lieu_khach": [
            r.name for r in rows if r.name in EINVOICE_DOCTYPES_MANG_DU_LIEU_KHACH
        ],
    }


def _nap_doctype_kho() -> dict[str, list[str]]:
    """Liệt kê doctype kho từ DATABASE lúc chạy test, không hardcode.

    FINDING I2 (review cuối). Bản trước giữ hai hằng số viết tay
    (`SIX_PARENT_DOCTYPES`, `ALL_EIGHT_DOCTYPES`). Không có gì buộc chúng phải
    theo kịp code: thêm một doctype kho thứ bảy — cụ thể là loại chứng từ thứ
    ba, đúng kịch bản mà `kho/permissions.py` tự dự báo trong comment của nó —
    sẽ ship ra với ZERO độ phủ cách ly, và bảng item con của nó không nằm
    trong hook dict nào, trong khi cả bộ test vẫn xanh.

    Suy động từ `tabDocType` khiến điều đó không thể xảy ra: doctype kho mới
    tự động lọt vào mọi vòng lặp bên dưới, và bộ test ĐỎ cho tới khi nó được
    nối dây vào tầng cách ly (hook `permission_query_conditions`, và
    `has_permission` nếu là doctype cha).

    Truy vấn LẤY VỀ TOÀN BỘ doctype của module rồi mới phân loại trong Python
    — KHÔNG lọc theo tiền tố ở tầng SQL. Đó là điều kiện để phát hiện được
    một doctype lệch quy ước đặt tên: nếu lọc bằng `or_filters` thì những cái
    tên không khớp bị loại ngay ở SQL, tức vô hình, và lưới an toàn dưới đây
    không bao giờ có gì để bắt.

    Phân loại cha/con bằng `istable` chứ không bằng tên: đó chính là thuộc
    tính mà `frappe.permissions.has_child_permission()` rẽ nhánh theo, nên nó
    là tiêu chí đúng về mặt cơ chế.

    Đọc lười (không phải ở mức module) để việc import file test không cần sẵn
    kết nối site. Cố ý KHÔNG cache: vài dòng, truy vấn gần như miễn phí, còn
    một cache cũ là đúng kiểu hỏng âm thầm mà cả hàm này sinh ra để chống.
    """
    rows = frappe.get_all(
        "DocType",
        filters={"module": KHO_MODULE},
        fields=["name", "istable"],
        order_by="name asc",
    )
    def _la_doctype_kho(ten: str) -> bool:
        return ten.startswith(KHO_PREFIXES) or ten in KHO_DOCTYPES_KHAC

    kho_rows = [r for r in rows if _la_doctype_kho(r.name)]
    la = [
        r.name for r in rows
        if not _la_doctype_kho(r.name)
        and r.name not in KHONG_PHAI_DOCTYPE_KHO
    ]
    if la:
        frappe.throw(
            f"Doctype {la} thuộc module {KHO_MODULE} nhưng không khớp tiền tố "
            f"kho nào ({', '.join(KHO_PREFIXES)}), không nằm trong "
            f"KHO_DOCTYPES_KHAC ({', '.join(KHO_DOCTYPES_KHAC)}), và cũng "
            "không nằm trong KHONG_PHAI_DOCTYPE_KHO. Suy động chỉ đúng bằng "
            "đúng quy ước đặt tên của nó, nên trường hợp này phải ĐỎ chứ "
            "không được bỏ qua: đổi tên doctype cho đúng tiền tố (nếu nó "
            "thuộc một họ chứng từ/danh mục kho nhiều-doctype), khai báo tên "
            "đầy đủ vào KHO_DOCTYPES_KHAC (nếu là doctype kho độc lập, không "
            "chia sẻ tiền tố với ai), hoặc khai báo vào KHONG_PHAI_DOCTYPE_KHO "
            "(nếu không phải doctype kho)."
        )
    if not kho_rows:
        frappe.throw(
            f"Không tìm thấy doctype kho nào trong module {KHO_MODULE} — "
            "danh sách rỗng sẽ khiến mọi vòng lặp test bên dưới pass vô "
            "nghĩa. Kiểm tra lại tên module hoặc quy ước tiền tố."
        )
    return {
        "all": [r.name for r in kho_rows],
        "parent": [r.name for r in kho_rows if not r.istable],
        "child": [r.name for r in kho_rows if r.istable],
    }


def kho_doctypes() -> list[str]:
    """Mọi doctype kho — tất cả PHẢI có mặt trong permission_query_conditions."""
    return _nap_doctype_kho()["all"]


def kho_parent_doctypes() -> list[str]:
    """Doctype kho KHÔNG phải bảng con.

    Đây chính là danh sách phải KHÔNG có DocPerm nào cho role `Customer` (xem
    TestKhoDocPermConfig) và là danh sách duy nhất được đăng ký trong hook
    `has_permission`.
    """
    return _nap_doctype_kho()["parent"]


def kho_child_doctypes() -> list[str]:
    """Bảng con (istable=1) của các chứng từ kho.

    Chúng CỐ Ý vắng mặt trong hook `has_permission` (vòng review 2, Finding 5):
    `frappe.permissions.has_child_permission()` rẽ nhánh sang kiểm PARENT
    trước khi bất kỳ hook has_permission nào đăng ký cho CHÍNH doctype con có
    cơ hội chạy — một entry ở đó sẽ không bao giờ được gọi, bất kể cấu hình
    DocPerm thế nào, tức là một decoy. ĐỪNG thêm lại chúng chỉ để "cho khớp"
    với danh sách đầy đủ ở permission_query_conditions. Sự bất đối xứng đó
    được CHỐT bằng assertion ngược trong
    test_hooks_registered_for_every_kho_doctype, không chỉ bằng comment này.

    LƯU Ý (sửa lại ở vòng 4): bản trước của comment này viết tiếp rằng "cơ chế
    THẬT SỰ là has_permission() ghi đè trên class controller". Câu đó KHÔNG CÒN
    ĐÚNG. Kể từ vòng 4, cơ chế thật sự là role `Customer` không còn DocPerm nào
    trên các doctype cha (xem docstring đầu file và TestKhoDocPermConfig);
    override trên controller tụt xuống thành lớp phòng thủ thứ hai, và chính nó
    cũng không đóng nổi đường module-level `frappe.has_permission()` mà
    /printview dùng — đó là lý do vòng 4 phải sửa ở tầng cấu hình quyền.
    """
    return _nap_doctype_kho()["child"]


def _assert_fixture_phu_het(case, mapping, mong_doi, nhan):
    """Chốt rằng một fixture viết tay phủ ĐÚNG danh sách doctype suy động.

    FINDING I2. Vài fixture bên dưới buộc phải viết tay vì mỗi doctype cần một
    BẢN GHI THẬT được seed (không suy ra từ tabDocType được). Nếu chỉ suy động
    ở mấy test cấu hình hook mà để các fixture này tự do, doctype kho thứ chín
    vẫn ship ra với zero độ phủ ở chính những test đo hành vi. Assertion này
    làm chúng ĐỎ ngay khi hai bên lệch nhau.
    """
    case.assertEqual(
        set(mapping), set(mong_doi),
        f"{nhan}: fixture phải phủ đúng danh sách doctype kho suy động từ "
        "tabDocType. Lệch nghĩa là có doctype kho mới chưa được nối vào bộ "
        "test cách ly này (hoặc một doctype đã bị gỡ) — xem FINDING I2 và "
        "_nap_doctype_kho() ở đầu file.",
    )


def _make_receipt(kho, vat_tu, so_lo):
    doc = frappe.get_doc({
        "doctype": "Customer Stock Receipt",
        "kho": kho,
        "ngay": "2026-02-01",
        "loai_nhap": "Nhập khác",
        "nguoi_giao": "Trần Văn Giao",
        "items": [{
            "vat_tu": vat_tu,
            "so_lo": so_lo,
            "han_su_dung": "2027-01-01",
            "so_luong": 50,
            "don_gia": 20000,
        }],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc


def _make_issue(kho, vat_tu, so_lo):
    doc = frappe.get_doc({
        "doctype": "Customer Stock Issue",
        "kho": kho,
        "ngay": "2026-03-01",
        "loai_xuat": "Xuất sử dụng",
        "noi_nhan": "Khoa test",
        "nguoi_nhan": "Nhân viên test",
        "items": [{
            "vat_tu": vat_tu,
            "so_lo": so_lo,
            "so_luong": 5,
        }],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc


def _make_ncc(kho, ten):
    """Idempotent, giống _ensure_kho/_ensure_vat_tu trong seed_kho_demo.py:
    FrappeTestCase chỉ rollback một lần mỗi CLASS (không phải mỗi test), nên
    setUp chạy lại nhiều lần trong cùng một class với cùng tên `ten` — tạo vô
    điều kiện sẽ tự đụng chốt chặn trùng tên (BR-N3) của chính doctype này ở
    lần setUp thứ hai."""
    existing = frappe.db.get_value("Customer Supplier", {"kho": kho, "ten_ncc": ten}, "name")
    if existing:
        return frappe.get_doc("Customer Supplier", existing)
    doc = frappe.get_doc({
        "doctype": "Customer Supplier",
        "kho": kho,
        "ten_ncc": ten,
    })
    doc.insert(ignore_permissions=True)
    return doc


def _make_khoa_phong(kho, ten):
    """E8 — idempotent, cùng lý do với `_make_ncc`: setUp chạy lại nhiều lần
    trong cùng một class với cùng `ten` — tạo vô điều kiện sẽ tự đụng chốt
    chặn trùng tên (BR-CP1) của chính doctype này ở lần setUp thứ hai."""
    existing = frappe.db.get_value(
        "Customer Department", {"kho": kho, "ten_khoa_phong": ten}, "name"
    )
    if existing:
        return frappe.get_doc("Customer Department", existing)
    doc = frappe.get_doc({
        "doctype": "Customer Department",
        "kho": kho,
        "ten_khoa_phong": ten,
    })
    doc.insert(ignore_permissions=True)
    return doc


def _make_yeu_cau(customer, ten_hang):
    """E6 — idempotent, cùng lý do với `_make_ncc`: setUp chạy lại nhiều lần
    trong cùng một class. `Portal Item Request` mang `customer` trực tiếp
    (không phải `kho`), nên đây là fixture riêng, không dùng chung với
    `_make_ncc`/`_make_receipt`."""
    existing = frappe.db.get_value(
        "Portal Item Request", {"customer": customer, "ten_hang": ten_hang}, "name"
    )
    if existing:
        return frappe.get_doc("Portal Item Request", existing)
    doc = frappe.get_doc({
        "doctype": "Portal Item Request",
        "customer": customer,
        "nguoi_yeu_cau": "test@demo.miyano",
        "loai": "Tìm nguồn hàng mới",
        "ten_hang": ten_hang,
        "dvt": "Hộp",
        "so_luong_du_kien": 10,
    })
    doc.insert(ignore_permissions=True)
    return doc


def _ensure_staff_user():
    """Nhân viên Miyano ngồi desk: System User + role System Manager,
    KHÔNG phải Website User và KHÔNG có role Customer."""
    u = "staff@demo.miyano"
    if not frappe.db.exists("User", u):
        frappe.get_doc({
            "doctype": "User",
            "email": u,
            "first_name": "Staff",
            "user_type": "System User",
            "send_welcome_email": 0,
            "roles": [{"role": "System Manager"}],
        }).insert(ignore_permissions=True)
    return u


def _ensure_orphan_user():
    """Website User có role Customer, đúng hình dạng một tài khoản portal
    thật, nhưng Contact không link tới Customer nào — đúng kịch bản review đã
    khai thác (tài khoản này từng render được /printview chứng từ của MỌI
    khách hàng).

    Vai trò Customer được giữ nguyên sau vòng 4 dù nó không còn cấp quyền gì
    trên doctype kho nào: mục đích là mô phỏng đúng tài khoản portal xấu nhất
    có thể tồn tại trên site, chứ không phải để vượt qua vòng kiểm role. Với
    các test unit gọi thẳng _kho_condition/_child_condition, role không ảnh
    hưởng: chúng vẫn phải render "1=0" vì get_allowed_khos() trả về []."""
    u = "orphan@demo.miyano"
    if not frappe.db.exists("User", u):
        frappe.get_doc({
            "doctype": "User", "email": u, "first_name": "Orphan",
            "user_type": "Website User", "send_welcome_email": 0,
            "roles": [{"role": "Customer"}],
        }).insert(ignore_permissions=True)
    else:
        usr = frappe.get_doc("User", u)
        if not any(r.role == "Customer" for r in usr.roles):
            usr.append("roles", {"role": "Customer"})
            usr.save(ignore_permissions=True)
    return u


class TestKhoIsolation(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_get_portal_kho_resolves_own_warehouse(self):
        frappe.set_user(BM_USER)
        self.assertEqual(get_portal_kho(), self.kho["kho_bm"])

    def test_get_portal_kho_blocks_user_without_warehouse(self):
        # NOTE (deviation from brief's literal fixture): the brief's snippet
        # reused the fully-orphan "orphan@demo.miyano" user (no Contact, no
        # Customer at all) here. With get_portal_kho() as specified, that
        # user always hits the FIRST guard ("chưa gắn với khách hàng nào"),
        # never the second ("chưa được mở kho") — the two are genuinely
        # different failure modes. This test's name says "without_warehouse",
        # so the fixture must give the user a real Customer that simply has
        # no Customer Warehouse yet, distinct from
        # test_user_without_customer_sees_nothing below (which correctly
        # keeps using the fully-orphan user).
        cust = "Himedic Chưa Mở Kho"
        if not frappe.db.exists("Customer", cust):
            frappe.get_doc({
                "doctype": "Customer", "customer_name": cust,
                "customer_type": "Company", "customer_group": "All Customer Groups",
                "territory": "All Territories",
            }).insert(ignore_permissions=True)
        u = "chua_mo_kho@demo.miyano"
        if not frappe.db.exists("User", u):
            frappe.get_doc({
                "doctype": "User", "email": u, "first_name": "Chua Mo Kho",
                "user_type": "Website User", "send_welcome_email": 0,
            }).insert(ignore_permissions=True)
        contact_name = f"{cust}-portal"
        if not frappe.db.exists("Contact", contact_name):
            ct = frappe.new_doc("Contact")
            ct.first_name = cust
            ct.user = u
            ct.append("email_ids", {"email_id": u, "is_primary": 1})
            ct.append("links", {"link_doctype": "Customer", "link_name": cust})
            ct.name = contact_name
            ct.insert(ignore_permissions=True, set_name=contact_name)
        frappe.set_user(u)
        with self.assertRaises(frappe.PermissionError) as ctx:
            get_portal_kho()
        self.assertIn("chưa được mở kho", str(ctx.exception))

    def test_warehouse_query_scopes_to_own_customer(self):
        cond = kho_perms.kho_query(BM_USER)
        self.assertIn("Bệnh viện Bạch Mai", cond)
        self.assertNotIn("PXN ABC", cond)

    def test_child_queries_scope_to_own_warehouse(self):
        for fn, table in [
            (kho_perms.vat_tu_query, "Customer Warehouse Item"),
            (kho_perms.receipt_query, "Customer Stock Receipt"),
            (kho_perms.issue_query, "Customer Stock Issue"),
            (kho_perms.sle_query, "Customer Stock Ledger Entry"),
            (kho_perms.lot_query, "Customer Stock Lot Balance"),
        ]:
            cond = fn(BM_USER)
            self.assertIn(f"`tab{table}`.`kho`", cond)
            self.assertIn(self.kho["kho_bm"], cond)
            self.assertNotIn(self.kho["kho_pxn"], cond)

    def test_grandchild_item_queries_scope_to_own_warehouse_via_parent(self):
        """Customer Stock Receipt Item / Issue Item không có field `kho`
        riêng — điều kiện lọc phải đi qua subquery trên bảng cha."""
        for fn, table, parent_table in [
            (kho_perms.receipt_item_query, "Customer Stock Receipt Item",
             "Customer Stock Receipt"),
            (kho_perms.issue_item_query, "Customer Stock Issue Item",
             "Customer Stock Issue"),
        ]:
            cond = fn(BM_USER)
            self.assertIn(f"`tab{table}`.`parent`", cond)
            self.assertIn(f"`tab{parent_table}`", cond)
            self.assertIn(self.kho["kho_bm"], cond)
            self.assertNotIn(self.kho["kho_pxn"], cond)

    def test_system_user_unrestricted(self):
        for fn in [
            kho_perms.kho_query, kho_perms.vat_tu_query,
            kho_perms.receipt_query, kho_perms.issue_query,
            kho_perms.sle_query, kho_perms.lot_query, kho_perms.ncc_query,
            kho_perms.receipt_item_query, kho_perms.issue_item_query,
        ]:
            with self.subTest(fn=fn.__name__):
                self.assertEqual(fn("Administrator"), "")

    def test_user_without_customer_sees_nothing(self):
        # NOTE (deviation from brief): the brief's snippet referenced
        # "orphan@demo.miyano" without creating it, implicitly depending on
        # test_get_portal_kho_blocks_user_without_warehouse (run earlier by
        # alphabetical order) to have created it as a side effect. That's a
        # hidden ordering dependency, and it broke once that other test's
        # fixture was fixed (see NOTE above) to use a differently-named user.
        # Made self-sufficient here via the module-level _ensure_orphan_user().
        u = _ensure_orphan_user()
        self.assertIn("1=0", kho_perms.kho_query(u))
        self.assertIn("1=0", kho_perms.vat_tu_query(u))
        self.assertIn("1=0", kho_perms.receipt_item_query(u))
        self.assertIn("1=0", kho_perms.issue_item_query(u))

    def test_deactivated_warehouse_leaves_permission_layer_without_leaking(self):
        """FINDING N3 (review cuối): `get_portal_kho` lọc `active: 1` còn
        `get_allowed_khos` thì không, nên một kho đã tắt vẫn hiện với tầng
        phân quyền trong khi API từ chối nó.

        Sau khi sửa, hàm này chốt cả hai nửa của hợp đồng:
          * kho đã tắt rời khỏi danh sách của CHÍNH chủ (portal bị cắt thật),
          * và nó KHÔNG vì thế mà rơi sang khách khác — điều kiện lọc của BM
            vẫn không chứa kho PXN, đúng như trước khi tắt. Lịch sử của một
            kho đã tắt vẫn là của khách đó, chỉ là không ai ở phía portal đọc
            được nữa.
          * Positive control BẮT BUỘC: nhân viên desk vẫn thấy kho đã tắt.
            Thiếu nó thì một bản vá "tắt kho là xoá sổ dữ liệu" cũng pass.

        FrappeTestCase chỉ rollback ở cuối class, nên bọc trong savepoint và
        clear cache doc — cùng khuôn mẫu với test_kho_api.py.
        """
        kho_pxn = self.kho["kho_pxn"]
        sp = "test_kho_tat_active_sp"
        frappe.db.savepoint(sp)
        try:
            frappe.db.set_value("Customer Warehouse", kho_pxn, "active", 0)

            # 1. Chủ sở hữu mất kho đã tắt khỏi mọi danh sách phân quyền.
            self.assertNotIn(kho_pxn, get_allowed_khos(PXN_USER))
            for fn in (kho_perms.receipt_query, kho_perms.lot_query,
                       kho_perms.sle_query, kho_perms.receipt_item_query):
                with self.subTest(fn=fn.__name__, user="PXN"):
                    self.assertIn("1=0", fn(PXN_USER))
            frappe.set_user(PXN_USER)
            with self.assertRaises(frappe.PermissionError) as ctx:
                get_portal_kho()
            self.assertIn("chưa được mở kho", str(ctx.exception))
            frappe.set_user("Administrator")

            # 2. ...và KHÔNG rơi sang khách khác: điều kiện của BM y như cũ.
            for fn in (kho_perms.receipt_query, kho_perms.lot_query,
                       kho_perms.sle_query):
                with self.subTest(fn=fn.__name__, user="BM"):
                    cond = fn(BM_USER)
                    self.assertIn(self.kho["kho_bm"], cond)
                    self.assertNotIn(kho_pxn, cond)
            self.assertEqual(get_allowed_khos(BM_USER), [self.kho["kho_bm"]])
            lo_pxn = frappe.get_doc("Customer Warehouse Item", self.kho["vt_pxn"])
            self.assertFalse(kho_perms.kho_child_has_permission(lo_pxn, user=BM_USER))

            # 3. Positive control: desk Miyano vẫn đọc được kho đã tắt.
            staff = _ensure_staff_user()
            self.assertEqual(kho_perms.kho_query(staff), "")
            self.assertEqual(kho_perms.receipt_query(staff), "")
            frappe.set_user(staff)
            self.assertIn(
                kho_pxn,
                frappe.get_list("Customer Warehouse", pluck="name",
                                limit_page_length=0),
            )
            frappe.get_doc("Customer Warehouse", kho_pxn).check_permission("read")
        finally:
            frappe.set_user("Administrator")
            frappe.db.rollback(save_point=sp)
            frappe.clear_document_cache("Customer Warehouse", kho_pxn)

    def test_has_permission_blocks_other_customers_warehouse(self):
        kho_pxn = frappe.get_doc("Customer Warehouse", self.kho["kho_pxn"])
        self.assertFalse(kho_perms.kho_has_permission(kho_pxn, user=BM_USER))
        kho_bm = frappe.get_doc("Customer Warehouse", self.kho["kho_bm"])
        self.assertTrue(kho_perms.kho_has_permission(kho_bm, user=BM_USER))

    def test_has_permission_blocks_other_customers_item(self):
        vt_pxn = frappe.get_doc("Customer Warehouse Item", self.kho["vt_pxn"])
        self.assertFalse(kho_perms.kho_child_has_permission(vt_pxn, user=BM_USER))
        vt_bm = frappe.get_doc("Customer Warehouse Item", self.kho["vt_bm"])
        self.assertTrue(kho_perms.kho_child_has_permission(vt_bm, user=BM_USER))

    def test_check_permission_raises_for_other_customer(self):
        """doc.check_permission() phải chặn. (Trước vòng 4 đây là đường mà
        hook kho_child_has_permission gánh; từ vòng 4 lỗi đến sớm hơn, ở vòng
        kiểm role — hợp đồng không đổi, cơ chế thì đổi.)"""
        frappe.set_user(BM_USER)
        doc = frappe.get_doc("Customer Warehouse Item", self.kho["vt_pxn"])
        with self.assertRaises(frappe.PermissionError):
            doc.check_permission("read")

    def test_child_item_controllers_use_shared_has_permission(self):
        """FINDING N4: hai bảng dòng chứng từ dùng CHUNG một has_permission().

        Vì sao phải chốt bằng test riêng: kể từ vòng 4 mọi test phủ định về
        dòng con pass nhờ role `Customer` không còn DocPerm trên chứng từ cha,
        KHÔNG nhờ override này. Nếu Frappe thôi nhận diện được controller (đổi
        tên class, gộp lớp cơ sở sai, MRO hỏng) thì lớp phòng thủ thứ hai chết
        âm thầm và cả suite vẫn xanh — đúng kiểu "control chết" mà dự án này
        đã gặp hai lần (xem progress.md, hook has_permission cho istable).

        Assert cả ba mắt xích: Frappe resolve đúng class, class đó kế thừa lớp
        cơ sở dùng chung, và has_permission nó dùng CHÍNH LÀ bản của lớp cơ sở
        (không phải Document.has_permission mặc định, cũng không phải một bản
        chép tay khác).
        """
        for dt in kho_child_doctypes():
            with self.subTest(doctype=dt):
                cls = get_controller(dt)
                self.assertTrue(
                    issubclass(cls, VoucherItemBase),
                    f"{dt}: controller {cls!r} không kế thừa VoucherItemBase",
                )
                self.assertIs(
                    cls.has_permission, VoucherItemBase.has_permission,
                    f"{dt}: has_permission không phải bản dùng chung",
                )
                self.assertIsNot(
                    cls.has_permission, Document.has_permission,
                    f"{dt}: has_permission tụt về mặc định của Frappe",
                )

    def test_hooks_registered_for_every_kho_doctype(self):
        # FINDING 2 (review round 1): kiểm tra membership trong dict LITERAL
        # của module hooks.py đã import không chứng minh gì về hook THẬT SỰ
        # được Frappe dùng lúc chạy — nó pass ngay cả khi cache hook cũ (đã
        # bị clear-cache quên chạy) hoặc app chưa cài. Phải hỏi thẳng
        # frappe.get_hooks(), nguồn mà framework thực sự đọc.
        #
        # FINDING 5 (review round 2): has_permission chỉ đăng ký cho doctype
        # CHA — hai bảng item con (istable=1) KHÔNG được đăng ký, xem
        # kho_child_doctypes() ở đầu file để biết lý do. Assert NGƯỢC LẠI
        # (rằng chúng KHÔNG có mặt) để không ai "sửa" sự bất đối xứng này
        # bằng cách thêm lại những dòng chết đó.
        #
        # FINDING I2 (review cuối): danh sách suy động từ tabDocType, nên một
        # doctype kho thứ chín chưa nối dây sẽ làm test này ĐỎ ngay.
        pqc = frappe.get_hooks("permission_query_conditions")
        hp = frappe.get_hooks("has_permission")
        for dt in kho_doctypes():
            self.assertIn(dt, pqc, dt)
        for dt in kho_parent_doctypes():
            self.assertIn(dt, hp, dt)
        for dt in kho_child_doctypes():
            self.assertNotIn(dt, hp, dt)


# ---------------------------------------------------------------------------
# Phần dưới đây vượt ra ngoài yêu cầu tối thiểu của brief. Lỗ hổng mà một bộ
# test "trông có vẻ đủ" hay bỏ sót:
#
#   1. check_permission() phải chặn cho MỌI doctype kho cha, không chỉ Customer
#      Warehouse Item như test_check_permission_raises_for_other_customer ở
#      trên. permission_query_conditions và has_permission được nối dây riêng
#      cho từng doctype trong hooks.py — thiếu một dòng ở đâu đó vẫn để lọt.
#   2. frappe.get_list() — con đường list-view thật sự đi qua — không được rò
#      rỉ bản ghi của khách khác, cho MỌI doctype kho cha. Đây là cơ chế khác
#      hẳn has_permission (permission_query_conditions), nên phải kiểm riêng.
#   3. Nhân viên Miyano (System Manager, không phải Website User) vẫn phải
#      thấy toàn bộ dữ liệu của mọi khách hàng — cách ly không được lỡ tay
#      chặn luôn cả desk.
#
# Và sau vòng review — MÔ TẢ LỖ HỔNG NHƯ NÓ TỪNG LÀ (trước vòng 4), giữ lại
# để giải thích vì sao các test dưới đây tồn tại: Customer Stock Receipt Item /
# Customer Stock Issue Item là istable=1, permissions=[] trong JSON, KHÔNG có
# field `kho` riêng, và KHÔNG nằm trong hai hook dict ở bản Task 6 đầu tiên —
# has_permission chỉ được hỏi ở cấp PARENT (khi đó role Customer read=1 là đủ
# để qua), còn db_query lọc CHILD table lại không có điều kiện gì.
# frappe.client.get_list được whitelist cho Website User đọc thẳng bảng con
# theo parent/parenttype, không đi qua get_doc(parent) nào cả — rò rỉ đơn giá,
# số lô, số lượng của MỌI khách hàng cho bất kỳ ai có role Customer, kể cả user
# không gắn khách hàng nào.
#
# HIỆN TRẠNG (vòng 4): điều kiện "role Customer read=1 trên PARENT" không còn,
# nên bước tụt-về đó không xảy ra nữa và frappe.client.get_list ném
# PermissionError. Các assertion dưới đây đã được viết lại theo hợp đồng mới —
# xem docstring đầu file. Điểm 2 ở trên ("frappe.get_list là con đường list-view
# thật sự đi qua") vẫn đúng như một mô tả về đường code, chỉ là kết quả mong đợi
# đã đổi từ "danh sách đã lọc" thành "PermissionError".
# ---------------------------------------------------------------------------


class TestKhoIsolationDeep(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        # Dọn sổ của cả hai kho để đếm/lọc đúng trong phạm vi test này, giống
        # cách test_kho_receipt.py / test_kho_issue.py đã làm.
        frappe.db.delete(
            "Customer Stock Ledger Entry",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )
        frappe.db.delete(
            "Customer Stock Lot Balance",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )

        self.receipt_bm = _make_receipt(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.receipt_pxn = _make_receipt(self.kho["kho_pxn"], self.kho["vt_pxn"], "LO-PXN-A")
        self.issue_bm = _make_issue(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.issue_pxn = _make_issue(self.kho["kho_pxn"], self.kho["vt_pxn"], "LO-PXN-A")

        self.sle_pxn = frappe.db.get_value(
            "Customer Stock Ledger Entry", {"kho": self.kho["kho_pxn"]}, "name"
        )
        self.lot_pxn = frappe.db.get_value(
            "Customer Stock Lot Balance", {"kho": self.kho["kho_pxn"]}, "name"
        )

        self.sle_bm = frappe.db.get_value(
            "Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}, "name"
        )
        self.lot_bm = frappe.db.get_value(
            "Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]}, "name"
        )

        # E4: NCC của kho — doctype kho cha thứ bảy, mang field `kho` riêng.
        self.ncc_bm = _make_ncc(self.kho["kho_bm"], "NCC BM Test")
        self.ncc_pxn = _make_ncc(self.kho["kho_pxn"], "NCC PXN Test")

        # E6: Portal Item Request — doctype kho cha thứ tám, mang `customer`
        # trực tiếp (không phải `kho`) — xem _pxn_filter/_bm_filter bên dưới.
        self.yeu_cau_bm = _make_yeu_cau(CUSTOMER_BM, "Yêu cầu test BM")
        self.yeu_cau_pxn = _make_yeu_cau(CUSTOMER_PXN, "Yêu cầu test PXN")

        # E8: Customer Department — doctype kho cha thứ chín, mang field
        # `kho` riêng, cùng hình dạng Customer Supplier.
        self.khoa_bm = _make_khoa_phong(self.kho["kho_bm"], "Khoa BM Test")
        self.khoa_pxn = _make_khoa_phong(self.kho["kho_pxn"], "Khoa PXN Test")

        # Một bản ghi của PXN (khách B) cho từng doctype kho cha.
        self.pxn_records = {
            "Customer Warehouse": self.kho["kho_pxn"],
            "Customer Warehouse Item": self.kho["vt_pxn"],
            "Customer Stock Receipt": self.receipt_pxn.name,
            "Customer Stock Issue": self.issue_pxn.name,
            "Customer Stock Ledger Entry": self.sle_pxn,
            "Customer Stock Lot Balance": self.lot_pxn,
            "Customer Supplier": self.ncc_pxn.name,
            "Portal Item Request": self.yeu_cau_pxn.name,
            "Customer Department": self.khoa_pxn.name,
        }
        # Cùng danh sách đó, nhưng bản ghi của chính BM (khách A) — dùng để
        # chứng minh cách ly không lỡ tay chặn luôn dữ liệu CỦA CHÍNH khách
        # đang đăng nhập. Một hook trả "1=0" vô điều kiện sẽ pass hết mọi
        # test "PXN không lộ" ở trên nhưng phá luôn portal của BM.
        self.bm_records = {
            "Customer Warehouse": self.kho["kho_bm"],
            "Customer Warehouse Item": self.kho["vt_bm"],
            "Customer Stock Receipt": self.receipt_bm.name,
            "Customer Stock Issue": self.issue_bm.name,
            "Customer Stock Ledger Entry": self.sle_bm,
            "Customer Stock Lot Balance": self.lot_bm,
            "Customer Supplier": self.ncc_bm.name,
            "Portal Item Request": self.yeu_cau_bm.name,
            "Customer Department": self.khoa_bm.name,
        }
        for nhan, m in (("pxn_records", self.pxn_records),
                        ("bm_records", self.bm_records)):
            _assert_fixture_phu_het(self, m, kho_parent_doctypes(), nhan)

    def tearDown(self):
        frappe.set_user("Administrator")

    def _ensure_staff_user(self):
        return _ensure_staff_user()

    def _pxn_filter(self, doctype):
        if doctype in ("Customer Warehouse", "Portal Item Request"):
            return {"customer": CUSTOMER_PXN}
        return {"kho": self.kho["kho_pxn"]}

    def _bm_filter(self, doctype):
        if doctype in ("Customer Warehouse", "Portal Item Request"):
            return {"customer": CUSTOMER_BM}
        return {"kho": self.kho["kho_bm"]}

    # -- 1. check_permission() phải chặn cho MỌI doctype kho cha -------------
    #
    # Vẫn pass sau vòng 4, nhưng CƠ CHẾ đã đổi: trước đây lỗi đến từ hook
    # kho_has_permission/kho_child_has_permission (đã qua vòng kiểm role nhờ
    # DocPerm read=1 của `Customer`); giờ lỗi đến sớm hơn, ngay ở vòng kiểm
    # role, vì `Customer` không còn DocPerm nào. Giữ nguyên test vì hợp đồng
    # "khách A không đọc được bản ghi của khách B" không đổi — chỉ mạnh thêm.

    def test_check_permission_blocks_other_customer_for_every_parent_doctype(self):
        frappe.set_user(BM_USER)
        for dt, name in self.pxn_records.items():
            with self.subTest(doctype=dt):
                doc = frappe.get_doc(dt, name)
                with self.assertRaises(frappe.PermissionError):
                    doc.check_permission("read")

    # -- 2. frappe.get_list() — HỢP ĐỒNG MỚI (vòng 4) -------------------------
    #
    # Bản cũ assert `get_list(... filters=PXN ...) == []`, tức "khách A gọi
    # get_list thì lọc mất dòng của B". Hợp đồng đó KHÔNG CÒN ĐÚNG và cũng
    # không còn là thứ ta muốn: role `Customer` không còn DocPerm nào trên các
    # doctype kho, nên get_list ném PermissionError trước khi tới bước lọc. Đây là
    # cách ly MẠNH HƠN, không phải regression — một danh sách rỗng vẫn xác
    # nhận doctype tồn tại và truy vấn được; một PermissionError thì không.
    #
    # Assert luôn cả hai chiều bộ lọc (của PXN và của chính BM) vì hợp đồng
    # mới nói "portal không có cửa trực tiếp nào hết", chứ không phải "cửa
    # trực tiếp có nhưng đã lọc". Nếu chỉ assert chiều PXN, một ngày nào đó ai
    # đó cấp lại DocPerm cho `Customer` thì test vẫn pass (nhờ
    # permission_query_conditions còn nguyên) và ta mất cảnh báo về việc mô
    # hình bảo vệ đã âm thầm tụt về mô hình cũ vốn để hở /printview.
    #
    # Rủi ro "test thoái hoá thành pass dưới lỗi cấm tiệt": xem
    # TestKhoApiDoorStillOpen + TestKhoStaffDeskAccess, và test 2b ngay dưới.

    def test_get_list_denied_for_portal_user_for_every_parent_doctype(self):
        frappe.set_user(BM_USER)
        for dt in self.pxn_records:
            for label, flt in (
                ("dữ liệu khách khác", self._pxn_filter(dt)),
                ("dữ liệu của chính mình", self._bm_filter(dt)),
            ):
                with self.subTest(doctype=dt, filters=label):
                    with self.assertRaises(frappe.PermissionError):
                        frappe.get_list(dt, filters=flt, pluck="name")

    # -- 2b. Chiều ngược lại: BM vẫn phải LẤY ĐƯỢC dữ liệu của chính mình -----
    #
    # Không còn qua get_list, mà qua ĐÚNG khuôn mẫu mà api/kho.py dùng: suy
    # kho từ phiên bằng get_portal_kho(), rồi lọc tường minh theo kho đó bằng
    # frappe.get_all (bỏ qua phân quyền — an toàn nhờ cấu trúc truy vấn).
    #
    # GIỚI HẠN, nói thẳng: đây là PATTERN CONTROL, KHÔNG phải endpoint
    # coverage. api/kho.py hiện chỉ có kho_me/kho_ton/kho_lo, phủ ba doctype
    # (Customer Warehouse, Customer Warehouse Item, Customer Stock Lot
    # Balance) — xem TestKhoApiDoorStillOpen cho phần endpoint thật. Ba
    # doctype còn lại (Stock Receipt / Stock Issue / Stock Ledger Entry) CHƯA
    # có endpoint portal nào, đúng theo thiết kế Phase 1. Với chúng, test này
    # chứng minh khuôn mẫu sẽ dùng khi có endpoint vẫn chạy được và vẫn đúng
    # kho; positive control thật của chúng là TestKhoStaffDeskAccess (desk đọc
    # được) và test_kho_ledger/receipt/issue (engine ghi/đọc được).
    #
    # Test này là cái bắt lỗi "cấm tiệt": nếu get_portal_kho()/get_allowed_khos
    # hỏng hoặc trả rỗng, nó fail ngay, trong khi mọi assertRaises ở trên vẫn
    # pass.

    def test_own_data_reachable_via_sanctioned_pattern_for_every_parent_doctype(self):
        frappe.set_user(BM_USER)
        kho = get_portal_kho()
        self.assertEqual(kho, self.kho["kho_bm"])
        # E6: khuôn mẫu sanctioned của Portal Item Request là
        # get_portal_customer() + lọc theo `customer` (portal_yeu_cau_list),
        # KHÔNG phải get_portal_kho() + lọc theo `kho` — nó không có field đó.
        customer = get_portal_customer()
        self.assertEqual(customer, CUSTOMER_BM)
        for dt, name in self.bm_records.items():
            with self.subTest(doctype=dt):
                if dt == "Customer Warehouse":
                    rows = frappe.get_all(dt, filters={"name": kho}, pluck="name")
                elif dt == "Portal Item Request":
                    rows = frappe.get_all(dt, filters={"customer": customer}, pluck="name")
                else:
                    rows = frappe.get_all(dt, filters={"kho": kho}, pluck="name")
                self.assertIn(name, rows)
                # ...và khuôn mẫu đó không kéo theo dòng nào của khách khác.
                self.assertNotIn(self.pxn_records[dt], rows)

    # -- 3. Nhân viên Miyano (System Manager) vẫn thấy toàn bộ ----------------

    def test_staff_user_sees_all_customers(self):
        staff = self._ensure_staff_user()
        frappe.set_user(staff)
        # FINDING I1 (review cuối): tên nói "all customers" nên phải chạy CẢ
        # HAI khách, không chỉ PXN. Bản trước chỉ lặp pxn_records — một lỗi
        # chặn riêng dữ liệu của BM ở phía desk sẽ lọt qua.
        for label, records, flt in (
            ("PXN", self.pxn_records, self._pxn_filter),
            ("BM", self.bm_records, self._bm_filter),
        ):
            for dt, name in records.items():
                with self.subTest(customer=label, doctype=dt):
                    # assertIn, not assertEqual: Customer Stock Ledger Entry
                    # gets one row from the receipt and another from the issue
                    # in this same setUp, so "exactly one row" is not the
                    # invariant — "the row is visible to staff" is.
                    rows = frappe.get_list(dt, filters=flt(dt), pluck="name")
                    self.assertIn(name, rows)
                    doc = frappe.get_doc(dt, name)
                    doc.check_permission("read")  # không được ném lỗi


# ---------------------------------------------------------------------------
# FINDING 1 (CRITICAL, từ vòng review): Customer Stock Receipt Item / Customer
# Stock Issue Item — hai bảng item con của Receipt/Issue — hoàn toàn không có
# cách ly cho tới bản vá này. Bài test dưới đây bám sát đúng năm điểm review
# yêu cầu, cho CẢ HAI bảng item con.
# ---------------------------------------------------------------------------


class TestKhoIsolationChildItems(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete(
            "Customer Stock Ledger Entry",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )
        frappe.db.delete(
            "Customer Stock Lot Balance",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )

        self.receipt_bm = _make_receipt(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.receipt_pxn = _make_receipt(self.kho["kho_pxn"], self.kho["vt_pxn"], "ZZLO-PXN")
        self.issue_bm = _make_issue(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.issue_pxn = _make_issue(self.kho["kho_pxn"], self.kho["vt_pxn"], "ZZLO-PXN")

        # doctype của bảng con -> (tên doctype cha, tên dòng con của PXN,
        # tên dòng con của BM). Đây chính là bốn giá trị các test dưới đây
        # xoay quanh.
        self.child_map = {
            "Customer Stock Receipt Item": {
                "parent_doctype": "Customer Stock Receipt",
                "pxn_parent": self.receipt_pxn.name,
                "bm_parent": self.receipt_bm.name,
                "pxn_row": self.receipt_pxn.items[0].name,
                "bm_row": self.receipt_bm.items[0].name,
            },
            "Customer Stock Issue Item": {
                "parent_doctype": "Customer Stock Issue",
                "pxn_parent": self.issue_pxn.name,
                "bm_parent": self.issue_bm.name,
                "pxn_row": self.issue_pxn.items[0].name,
                "bm_row": self.issue_bm.items[0].name,
            },
        }
        _assert_fixture_phu_het(self, self.child_map, kho_child_doctypes(),
                                "child_map")

        # Phiếu NHÁP (docstatus=0) của BM, dùng riêng cho các test write-side
        # (FINDING 6) — save() ghi đè trực tiếp một dòng con chỉ có ý nghĩa
        # kiểm tra khi phiếu còn ở trạng thái có thể sửa; phiếu đã submit thì
        # dùng cho test xoá (delete_doc bỏ qua docstatus hoàn toàn, đúng như
        # lỗ hổng đã khai thác).
        self.draft_receipt_bm = self._draft_receipt(
            self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A"
        )
        self.draft_issue_bm = self._draft_issue(
            self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A"
        )
        self.draft_map = {
            "Customer Stock Receipt Item": self.draft_receipt_bm.items[0].name,
            "Customer Stock Issue Item": self.draft_issue_bm.items[0].name,
        }

    def tearDown(self):
        frappe.set_user("Administrator")

    def _draft_receipt(self, kho, vat_tu, so_lo):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": kho,
            "ngay": "2026-02-01",
            "loai_nhap": "Nhập khác",
            "nguoi_giao": "Trần Văn Giao",
            "items": [{
                "vat_tu": vat_tu,
                "so_lo": so_lo,
                "han_su_dung": "2027-01-01",
                "so_luong": 10,
                "don_gia": 20000,
            }],
        })
        doc.insert(ignore_permissions=True)  # KHÔNG submit — ở lại docstatus=0
        return doc

    def _draft_issue(self, kho, vat_tu, so_lo):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Issue",
            "kho": kho,
            "ngay": "2026-03-01",
            "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Khoa test",
            "nguoi_nhan": "Nhân viên test",
            "items": [{"vat_tu": vat_tu, "so_lo": so_lo, "so_luong": 5}],
        })
        doc.insert(ignore_permissions=True)  # KHÔNG submit
        return doc

    def _rows(self, dt, parent_doctype):
        return frappe.get_list(
            dt,
            parent_doctype=parent_doctype,
            fields=["name", "parent", "vat_tu", "so_lo", "don_gia"],
            limit_page_length=0,
        )

    # -- 1. Khách A không đọc được bảng con qua get_list ---------------------
    #
    # Bản cũ assert "danh sách trả về không chứa parent của PXN" — tức bảng
    # con VẪN liệt kê được, chỉ đã lọc. Hợp đồng vòng 4: get_list trên bảng
    # con kiểm quyền ở doctype CHA (has_child_permission), và `Customer` không
    # còn DocPerm nào trên cha, nên nó ném PermissionError — không danh sách
    # nào để mà lọc. Mạnh hơn: bản cũ chỉ chứng minh "không thấy dòng của B",
    # bản mới chứng minh "không mở được bảng".
    #
    # Đây chính là lỗ /printview được đóng tận gốc: cùng một vòng kiểm role
    # trên doctype cha mà cả get_list lẫn frappe.has_permission module-level
    # đều quy về.

    def test_get_list_denied_for_portal_user_child_rows(self):
        frappe.set_user(BM_USER)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt):
                with self.assertRaises(frappe.PermissionError):
                    self._rows(dt, info["parent_doctype"])

    # -- 2. User không gắn khách hàng nào cũng bị chặn hẳn -------------------
    #
    # Bản cũ assert `== []`. Danh sách rỗng và PermissionError khác nhau về
    # chất: rỗng nghĩa là "bạn được phép hỏi, chỉ là không có gì", và nó
    # KHÔNG phân biệt được "hook lọc đúng" với "hook chưa chạy nhưng chưa có
    # dữ liệu". PermissionError thì không mơ hồ.

    def test_orphan_user_denied_child_rows(self):
        u = _ensure_orphan_user()
        frappe.set_user(u)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt):
                with self.assertRaises(frappe.PermissionError):
                    self._rows(dt, info["parent_doctype"])

    # -- 3. check_permission() phải ném lỗi cho dòng con của khách khác ------
    #
    # `frappe.permissions.has_child_permission()` chỉ suy ra parent đúng khi
    # dòng con có `parent_doc` gắn sẵn (tức lấy từ `.items` của parent doc đã
    # load) — một dòng LOAD ĐỘC LẬP qua frappe.get_doc(child_dt, name) (đúng
    # như /api/resource/<dt>/<name>/ và /api/v2/document/<dt>/<name>/ đều
    # làm) có `parent_doc` resolve về None và TỤT VỀ kiểm role thuần, bỏ qua
    # hoàn toàn `kho`. Vì vậy has_permission() được ghi đè thẳng trên
    # CustomerStockReceiptItem/CustomerStockIssueItem (xem hai file
    # customer_stock_*_item.py) thay vì đăng ký hook has_permission trong
    # hooks.py — một entry ở đó sẽ KHÔNG BAO GIỜ được framework gọi tới cho
    # doctype istable=1 (cố tình không đăng ký, xem comment trong hooks.py).
    #
    # SỬA LẠI Ở VÒNG 4: bản trước của comment này kết luận "ghi đè ở đây mới
    # là cơ chế THẬT SỰ chặn". Không còn đúng. Kể từ vòng 4, cái chặn là việc
    # role `Customer` không còn DocPerm nào trên chứng từ cha; override chỉ là
    # lớp phòng thủ thứ hai, và bản thân nó KHÔNG chặn được đường module-level
    # `frappe.has_permission()` mà /printview dùng (xem
    # TestKhoPortalDoorClosed). Test này vì thế giờ pass nhờ vòng kiểm role,
    # không phải nhờ override. Vẫn kiểm cả hai hình thức load (độc lập VÀ đính
    # kèm qua parent doc) vì cả hai đều phải bị chặn, bất kể đường vào.

    def test_check_permission_raises_for_other_customers_child_row(self):
        frappe.set_user(BM_USER)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt, form="standalone"):
                doc = frappe.get_doc(dt, info["pxn_row"])
                self.assertIsNone(doc.parent_doc)
                with self.assertRaises(frappe.PermissionError):
                    doc.check_permission("read")
            with self.subTest(doctype=dt, form="attached"):
                parent = frappe.get_doc(info["parent_doctype"], info["pxn_parent"])
                self.assertIsNotNone(parent.items[0].parent_doc)
                with self.assertRaises(frappe.PermissionError):
                    parent.items[0].check_permission("read")

    # -- 4. Vòng 4: dòng con CỦA CHÍNH MÌNH cũng không đọc trực tiếp được ----
    #
    # Bản cũ là positive control ("BM vẫn đọc được dòng của BM"), và nó ĐÚNG
    # dưới mô hình cũ. Dưới mô hình mới nó sai theo đúng chủ đích: portal
    # không có cửa trực tiếp nào vào bảng con, kể cả cửa của chính mình.
    # Đảo chiều assertion, và ghi rõ vì sao đây không phải regression: dữ liệu
    # tồn kho mà portal cần vẫn tới được qua api/kho.py (xem
    # TestKhoApiDoorStillOpen); còn dòng chi tiết chứng từ thì Phase 1 chưa
    # phát hành ra portal, đúng thiết kế đã duyệt.
    #
    # Positive control cho nhóm này chuyển hẳn sang
    # test_staff_user_sees_all_customers_child_rows và
    # test_staff_can_still_delete_and_write_child_rows bên dưới — không được
    # xoá cả hai, nếu không cả class này pass dưới lỗi "cấm tiệt tất cả".

    def test_own_child_rows_also_denied_directly(self):
        frappe.set_user(BM_USER)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt, form="standalone"):
                doc = frappe.get_doc(dt, info["bm_row"])
                self.assertFalse(doc.has_permission("read"))
                with self.assertRaises(frappe.PermissionError):
                    doc.check_permission("read")
            with self.subTest(doctype=dt, form="attached"):
                parent = frappe.get_doc(info["parent_doctype"], info["bm_parent"])
                with self.assertRaises(frappe.PermissionError):
                    parent.items[0].check_permission("read")

    # -- 4b. "print" cũng đóng, cho cả hai khách ----------------------------
    #
    # Vòng 3 phát hiện role Customer có print=1 trên chứng từ cha giống hệt
    # read=1, nên `doc.check_permission("print")` (đường
    # frappe.utils.weasyprint.get_html) từng trả True cho dòng của khách
    # khác; bản vá khi đó là thu hẹp "print" trong override controller. Vòng 4
    # gỡ luôn cả entry DocPerm `Customer` (cả read lẫn print), nên print đóng
    # ở tầng sâu hơn và đóng cho CẢ dòng của chính mình.
    #
    # Assertion vì thế đổi: bản cũ khẳng định `own_doc.has_permission("print")`
    # là True — điều đó giờ sai. Positive control tương ứng chuyển sang nhân
    # viên desk (dưới đây), nơi print PHẢI vẫn chạy được; thiếu nó thì test
    # này pass cả dưới lỗi tắt print của toàn hệ thống.

    def test_print_permission_denied_for_portal_user_both_customers(self):
        frappe.set_user(BM_USER)
        for dt, info in self.child_map.items():
            for label, row in (("khách khác", info["pxn_row"]),
                               ("của chính mình", info["bm_row"])):
                with self.subTest(doctype=dt, row=label):
                    doc = frappe.get_doc(dt, row)
                    self.assertFalse(doc.has_permission("print"))
                    self.assertFalse(
                        frappe.has_permission(dt, "print", doc)
                    )
                    with self.assertRaises(frappe.PermissionError):
                        doc.check_permission("print")

    def test_staff_can_still_print_child_rows(self):
        staff = _ensure_staff_user()
        frappe.set_user(staff)
        for dt, info in self.child_map.items():
            for label, row in (("PXN", info["pxn_row"]), ("BM", info["bm_row"])):
                with self.subTest(doctype=dt, row=label):
                    doc = frappe.get_doc(dt, row)
                    self.assertTrue(doc.has_permission("print"))
                    doc.check_permission("print")  # không được ném lỗi

    # -- 5. Nhân viên Miyano (System Manager) vẫn thấy dòng con của mọi khách -

    def test_staff_user_sees_all_customers_child_rows(self):
        staff = _ensure_staff_user()
        frappe.set_user(staff)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt):
                rows = self._rows(dt, info["parent_doctype"])
                parents = {r.parent for r in rows}
                self.assertIn(info["pxn_parent"], parents)
                self.assertIn(info["bm_parent"], parents)
                frappe.get_doc(dt, info["pxn_row"]).check_permission("read")
                frappe.get_doc(dt, info["bm_row"]).check_permission("read")

    # -- 6. FINDING 4 (vòng review 2, CRITICAL): write-side, KHÔNG ĐƯỢC xoá/
    #    sửa dòng con dù đó là dòng CỦA CHÍNH MÌNH -----------------------
    #
    # Bối cảnh dưới đây là tình trạng TRƯỚC VÒNG 4 (khi role Customer còn
    # DocPerm trên chứng từ cha); giữ lại vì nó giải thích vì sao override
    # phải thu hẹp theo permtype, và sẽ đúng trở lại ngay nếu grant quay lại.
    #
    # Bản has_permission() ghi đè đầu tiên trả kết quả kho-check cho MỌI
    # permtype như nhau, nên vô tình CẤP quyền xoá/sửa cho role Customer (khi
    # đó chỉ có read=1 trên chứng từ cha — customer_stock_receipt.json /
    # customer_stock_issue.json: write=0, delete=0, submit=0, cancel=0). Xác
    # nhận thực nghiệm bởi review: frappe.delete_doc() xoá được một dòng trên
    # phiếu ĐÃ SUBMIT, và doc.save() ghi đè được đơn giá trên dòng nháp — cả
    # hai đều làm sổ (Customer Stock Ledger Entry, append-only) lệch khỏi
    # phiếu, vì sửa/xoá thẳng dòng con hoàn toàn bỏ qua on_submit/on_cancel
    # của phiếu cha.
    #
    # Đây KHÔNG phải test rò rỉ giữa hai khách — nạn nhân là chính chủ sở hữu
    # hợp pháp của dòng đó (BM), chỉ là họ không có quyền GHI/XOÁ nó theo
    # đúng vai trò Customer. Vì vậy chỉ dùng dữ liệu của BM ở đây.

    def test_delete_own_submitted_child_row_blocked(self):
        frappe.set_user(BM_USER)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt):
                with self.assertRaises(frappe.PermissionError):
                    frappe.delete_doc(dt, info["bm_row"])
                # Không bị xoá nửa chừng trước khi exception được ném ra.
                self.assertTrue(frappe.db.exists(dt, info["bm_row"]))

    def test_write_own_draft_child_row_blocked(self):
        frappe.set_user(BM_USER)
        for dt, row_name in self.draft_map.items():
            with self.subTest(doctype=dt):
                doc = frappe.get_doc(dt, row_name)
                doc.don_gia = 1
                with self.assertRaises(frappe.PermissionError):
                    doc.save()
                # Không bị ghi đè nửa chừng trước khi exception được ném ra.
                self.assertEqual(
                    frappe.db.get_value(dt, row_name, "don_gia"), 20000
                )

    # -- Positive control: System Manager vẫn xoá/sửa được, chứng minh bản vá
    #    THU HẸP chứ không cấm tiệt — nếu không có test này, một
    #    has_permission() luôn trả False cho ptype != "read" (thay vì giao
    #    lại cho super()) sẽ làm hai test ở trên PASS trong khi khoá luôn cả
    #    quyền sửa/xoá hợp pháp của nhân viên desk.

    def test_staff_can_still_delete_and_write_child_rows(self):
        staff = _ensure_staff_user()
        frappe.set_user(staff)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt, op="delete"):
                frappe.delete_doc(dt, info["bm_row"])
                self.assertFalse(frappe.db.exists(dt, info["bm_row"]))
        for dt, row_name in self.draft_map.items():
            with self.subTest(doctype=dt, op="write"):
                doc = frappe.get_doc(dt, row_name)
                doc.don_gia = 1
                doc.save()
                self.assertEqual(frappe.db.get_value(dt, row_name, "don_gia"), 1)


# ---------------------------------------------------------------------------
# VÒNG 4 — cơ chế bảo vệ MỚI và các đường thoát mà ba vòng trước không đóng
# nổi ở tầng class/hook.
#
# Bối cảnh (đo được ở vòng 3, trước thay đổi này):
#     doc.has_permission("read")                      -> False  (override chạy)
#     frappe.has_permission(doc.doctype, "read", doc) -> True   (override bị bỏ qua)
# và /printview render ra số lô, số lượng, đơn giá của khách khác cho một
# Website User. Nguyên nhân: với doctype istable=1, hàm module-level
# frappe.has_permission() rẽ vào has_child_permission(), hàm này quy về kiểm
# ROLE THUẦN trên doctype CHA và không bao giờ chạm tới controller của con.
#
# Vòng 4 đóng ở đúng chỗ mà mọi đường đó quy về: gỡ hết DocPerm của role
# `Customer` trên các doctype kho cha. Các test dưới đây bám đúng những route đã
# từng hở.
# ---------------------------------------------------------------------------


class TestKhoDocPermConfig(FrappeTestCase):
    """Cơ chế bảo vệ chính giờ là CẤU HÌNH QUYỀN, nên nó phải được test như
    một hợp đồng, không phải như một chi tiết cài đặt."""

    def test_customer_role_has_no_docperm_on_any_kho_doctype(self):
        # Kiểm CẢ tabDocPerm (từ JSON doctype) LẪN tabCustom DocPerm (từ Role
        # Permission Manager). Custom DocPerm che hoàn toàn DocPerm khi tồn
        # tại, nên chỉ kiểm một bảng là để hở đúng đường mà một lần chỉnh tay
        # trên desk có thể mở lại.
        for table in ("DocPerm", "Custom DocPerm"):
            rows = frappe.get_all(
                table,
                filters={"parent": ["in", kho_doctypes()], "role": "Customer"},
                fields=["parent", "role"],
            )
            self.assertEqual(
                rows, [],
                f"{table}: role Customer không được có quyền trên doctype kho — "
                "đây là cơ chế cách ly chính của vòng 4, xem hooks.py",
            )

    def test_staff_roles_keep_desk_permissions(self):
        """Guard chống bản vá 'xoá sạch mảng permissions'. Nếu chỉ assert
        Customer vắng mặt, một commit xoá luôn System Manager/Sales Manager/
        Sales User vẫn pass — và desk Miyano sẽ chết."""
        for dt in kho_parent_doctypes():
            roles = {
                r.role for r in frappe.get_all(
                    "DocPerm", filters={"parent": dt}, fields=["role"]
                )
            }
            with self.subTest(doctype=dt):
                for role in STAFF_ROLES:
                    self.assertIn(role, roles, f"{dt} phải giữ quyền desk cho {role}")

    def test_portal_user_has_no_doctype_level_read(self):
        """Mức doctype (không kèm doc cụ thể) — đây chính là vòng kiểm mà
        has_child_permission() quy về cho hai bảng con istable=1, và cũng là
        vòng kiểm mà validate_print_permission() đi qua."""
        for user in (BM_USER, PXN_USER):
            for dt in kho_parent_doctypes():
                with self.subTest(user=user, doctype=dt):
                    self.assertFalse(
                        frappe.has_permission(dt, "read", user=user),
                        f"{user} không được có quyền đọc mức doctype trên {dt}",
                    )


class TestEinvoiceModuleLuoiQuetDong(FrappeTestCase):
    """AN-1: mở lưới quét động sang module `Einvoice` (app `erpnext`, tích
    hợp hoá đơn điện tử "Fast") — xem khối hằng số/`_nap_doctype_einvoice()`
    ở đầu file. KHÔNG sửa `apps/erpnext`, chỉ mở rộng phạm vi quét của test
    này."""

    def test_moi_doctype_einvoice_deu_duoc_phan_loai(self):
        """Bản thân lệnh gọi không ném lỗi ĐÃ LÀ bài kiểm chính: một doctype
        Einvoice mới (log, đối soát...) chưa được xếp vào một trong hai danh
        sách ở đầu file sẽ làm test này đỏ ngay — đúng cơ chế đã cứu dự án
        nhiều lần với _nap_doctype_kho()."""
        info = _nap_doctype_einvoice()
        self.assertIn("Fast EInvoice Document", info["all"])
        self.assertIn("Fast EInvoice Document", info["mang_du_lieu_khach"])
        self.assertIn("Fast EInvoice Log", info["mang_du_lieu_khach"])

    def test_customer_role_khong_co_docperm_tren_doctype_einvoice_nao(self):
        """Lớp phòng thủ CHÍNH (vòng 4, cùng khuôn
        test_customer_role_has_no_docperm_on_any_kho_doctype) — zero DocPerm
        VÀ Custom DocPerm cho role Customer, trên MỌI doctype của module
        Einvoice, không chỉ những cái đã nối hook. `Fast EInvoice Log` không
        có wiring permission_query_conditions/has_permission riêng (xem
        comment EINVOICE_DOCTYPES_MANG_DU_LIEU_KHACH) — assertion NÀY là lớp
        phòng thủ DUY NHẤT của nó; xoá là tắt hẳn cách ly của Log."""
        doctypes = _nap_doctype_einvoice()["all"]
        for table in ("DocPerm", "Custom DocPerm"):
            rows = frappe.get_all(
                table,
                filters={"parent": ["in", doctypes], "role": "Customer"},
                fields=["parent", "role"],
            )
            self.assertEqual(
                rows, [],
                f"{table}: role Customer không được có quyền trên doctype "
                f"module {EINVOICE_MODULE}",
            )

    def test_fast_einvoice_document_co_lop_phong_thu_thu_hai(self):
        """Doctype DUY NHẤT của module này có wiring hook riêng
        (hooks.py:144-148/184) — chốt nó không bị gỡ nhầm khi dọn hooks.py.
        Hỏi thẳng `frappe.get_hooks()` (nguồn framework thật sự đọc), không
        import tĩnh dict trong module hooks — cùng lý do FINDING 2 ở
        test_hooks_registered_for_every_kho_doctype."""
        pqc = frappe.get_hooks("permission_query_conditions")
        hp = frappe.get_hooks("has_permission")
        self.assertIn("Fast EInvoice Document", pqc)
        self.assertIn("Fast EInvoice Document", hp)


class _KhoVoucherFixture(FrappeTestCase):
    """setUp dùng chung: một Receipt + một Issue đã submit cho mỗi kho, và
    tên dòng con tương ứng."""

    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete(
            "Customer Stock Ledger Entry",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )
        frappe.db.delete(
            "Customer Stock Lot Balance",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )
        self.receipt_bm = _make_receipt(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.receipt_pxn = _make_receipt(self.kho["kho_pxn"], self.kho["vt_pxn"], "LO-PXN-A")
        self.issue_bm = _make_issue(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.issue_pxn = _make_issue(self.kho["kho_pxn"], self.kho["vt_pxn"], "LO-PXN-A")
        self.ncc_bm = _make_ncc(self.kho["kho_bm"], "NCC BM Test")
        self.ncc_pxn = _make_ncc(self.kho["kho_pxn"], "NCC PXN Test")
        # E6: bản ghi tối thiểu cho mỗi khách, cùng lý do với ncc_bm/ncc_pxn ở
        # trên — không nằm trong child_rows (istable), nhưng cần tồn tại để
        # các test "staff đọc được mọi doctype kho cha" ở dưới có dữ liệu.
        self.yeu_cau_bm = _make_yeu_cau(CUSTOMER_BM, "Yêu cầu test BM")
        self.yeu_cau_pxn = _make_yeu_cau(CUSTOMER_PXN, "Yêu cầu test PXN")
        # E8: cùng lý do — bản ghi tối thiểu cho mỗi khách.
        self.khoa_bm = _make_khoa_phong(self.kho["kho_bm"], "Khoa BM Test")
        self.khoa_pxn = _make_khoa_phong(self.kho["kho_pxn"], "Khoa PXN Test")

        self.child_rows = {
            "Customer Stock Receipt Item": {
                "pxn": self.receipt_pxn.items[0].name,
                "bm": self.receipt_bm.items[0].name,
            },
            "Customer Stock Issue Item": {
                "pxn": self.issue_pxn.items[0].name,
                "bm": self.issue_bm.items[0].name,
            },
        }
        _assert_fixture_phu_het(self, self.child_rows, kho_child_doctypes(),
                                "child_rows")

    def tearDown(self):
        frappe.set_user("Administrator")


class TestKhoPortalDoorClosed(_KhoVoucherFixture):
    def setUp(self):
        super().setUp()
        # printview chỉ kiểm quyền khi cờ này falsy. Nếu một test khác trong
        # cùng process để sót cờ bật, mọi assertRaises dưới đây sẽ fail-open
        # (pass vì lý do sai). Kiểm rồi ép về trạng thái sạch.
        self._orig_ignore_print = frappe.flags.ignore_print_permissions
        self.assertFalse(
            self._orig_ignore_print,
            "frappe.flags.ignore_print_permissions bị để sót — test printview "
            "sẽ vô nghĩa",
        )
        frappe.flags.ignore_print_permissions = False
        self._orig_form_dict = frappe.local.form_dict

    def tearDown(self):
        # form_dict và disable_traceback nằm trên frappe.local / frappe.flags,
        # KHÔNG được rollback giữa các test method của suite này (xem
        # task-6-report.md, "Deviations" #2). Trả nguyên trạng bằng tay.
        frappe.local.form_dict = self._orig_form_dict
        frappe.flags.ignore_print_permissions = self._orig_ignore_print
        frappe.flags.disable_traceback = False
        super().tearDown()

    def _printview(self, doctype, name):
        """Gọi đúng frappe/www/printview.py:get_context — route /printview."""
        frappe.local.form_dict = frappe._dict({"doctype": doctype, "name": name})
        try:
            return printview.get_context({})
        finally:
            frappe.local.form_dict = self._orig_form_dict

    # -- A. /printview: lỗ đã đo được ở vòng 3, giờ phải đóng ---------------
    #
    # Bằng chứng "trước" (vòng 3, cùng dòng dữ liệu, cùng user): get_context
    # trả về body chứa "Số lô: MANUAL-PXN ... Số lượng: 50 ... Đơn giá:
    # VND 20.000,00" cho bvbm@demo.miyano. Xem task-6-report.md addendum
    # vòng 4 để có bản in nguyên văn.

    def test_printview_denied_for_portal_user_on_other_customers_child_row(self):
        frappe.set_user(BM_USER)
        for dt, rows in self.child_rows.items():
            with self.subTest(doctype=dt):
                with self.assertRaises(frappe.PermissionError):
                    self._printview(dt, rows["pxn"])

    def test_printview_denied_for_orphan_website_user(self):
        """Website User có role Customer nhưng Contact không link tới khách
        hàng nào — tài khoản này từng render được chứng từ của MỌI khách."""
        u = _ensure_orphan_user()
        frappe.set_user(u)
        for dt, rows in self.child_rows.items():
            for label, row in (("PXN", rows["pxn"]), ("BM", rows["bm"])):
                with self.subTest(doctype=dt, row=label):
                    with self.assertRaises(frappe.PermissionError):
                        self._printview(dt, row)

    def test_printview_denied_for_portal_user_on_parent_vouchers_too(self):
        """Không chỉ bảng con: chính chứng từ cha cũng không in được từ
        portal nữa (role Customer từng có print=1 trên cả hai)."""
        frappe.set_user(BM_USER)
        for dt, name in (
            ("Customer Stock Receipt", self.receipt_pxn.name),
            ("Customer Stock Issue", self.issue_pxn.name),
            ("Customer Stock Receipt", self.receipt_bm.name),
            ("Customer Stock Issue", self.issue_bm.name),
        ):
            with self.subTest(doctype=dt, name=name):
                with self.assertRaises(frappe.PermissionError):
                    self._printview(dt, name)

    def test_printview_still_renders_for_staff(self):
        """Positive control bắt buộc: nếu thiếu, mọi test printview ở trên
        pass ngay cả khi /printview bị hỏng hoàn toàn cho tất cả mọi người."""
        staff = _ensure_staff_user()
        frappe.set_user(staff)
        for dt, rows in self.child_rows.items():
            with self.subTest(doctype=dt):
                ctx = self._printview(dt, rows["pxn"])
                self.assertTrue(ctx.get("body"), "staff phải render được body")

    # -- B. frappe.has_permission() MODULE-LEVEL ----------------------------
    #
    # Đây đúng là API mà has_permission() override trên controller KHÔNG BAO
    # GIỜ với tới (frappe/permissions.py: `if frappe.is_table(doctype): return
    # has_child_permission(...)`, ngay đầu hàm). Vòng 3 đo được True; phải là
    # False.

    def test_module_level_has_permission_false_on_other_customers_child_row(self):
        frappe.set_user(BM_USER)
        for dt, rows in self.child_rows.items():
            with self.subTest(doctype=dt, form="doc"):
                doc = frappe.get_doc(dt, rows["pxn"])
                self.assertFalse(frappe.has_permission(dt, "read", doc))
            with self.subTest(doctype=dt, form="docname"):
                # Dạng chuỗi docname — đường mà frappe.client.has_permission
                # dùng; vòng 3 cũng đo được True ở đây.
                self.assertFalse(frappe.has_permission(dt, "read", rows["pxn"]))

    def test_module_level_has_permission_true_for_staff(self):
        staff = _ensure_staff_user()
        frappe.set_user(staff)
        for dt, rows in self.child_rows.items():
            with self.subTest(doctype=dt):
                doc = frappe.get_doc(dt, rows["pxn"])
                self.assertTrue(frappe.has_permission(dt, "read", doc))
                self.assertTrue(frappe.has_permission(dt, "read", rows["pxn"]))

    # -- C. frappe.client.has_permission — oracle "dòng này có phải của tôi" -

    def test_client_has_permission_false_for_portal_user(self):
        frappe.set_user(BM_USER)
        for dt, rows in self.child_rows.items():
            for label, row in (("PXN", rows["pxn"]), ("BM", rows["bm"])):
                with self.subTest(doctype=dt, row=label):
                    self.assertEqual(
                        frappe_client.has_permission(dt, row, "read"),
                        {"has_permission": False},
                    )

    # -- D. frappe.client.get_list trên mọi doctype kho cha -----------------

    def test_client_get_list_raises_for_portal_user_on_every_parent_doctype(self):
        for user in (BM_USER, PXN_USER):
            frappe.set_user(user)
            for dt in kho_parent_doctypes():
                with self.subTest(user=user, doctype=dt):
                    with self.assertRaises(frappe.PermissionError):
                        frappe_client.get_list(dt, limit_page_length=0)

    def test_client_get_list_still_works_for_staff_on_every_parent_doctype(self):
        staff = _ensure_staff_user()
        frappe.set_user(staff)
        for dt in kho_parent_doctypes():
            with self.subTest(doctype=dt):
                rows = frappe_client.get_list(dt, limit_page_length=0)
                self.assertTrue(rows, f"staff phải đọc được {dt}")


class TestKhoApiDoorStillOpen(FrappeTestCase):
    """POSITIVE CONTROL TRUNG TÂM của vòng 4.

    Sau khi gỡ hết DocPerm của `Customer`, cổng duy nhất còn lại là
    miyano_portal/api/kho.py. Nếu class này fail thì thay đổi đã đóng luôn cả
    cửa hợp lệ — và mọi assertRaises ở các class khác trở thành bằng chứng
    của một lỗi, chứ không phải của cách ly.

    Phủ ĐỦ ba endpoint hiện có, cho CẢ HAI khách hàng (không chỉ BM): một lỗi
    "luôn trả kho của khách đầu tiên" sẽ lọt nếu chỉ test một phía.
    """

    def setUp(self):
        self.kho = seed_kho_demo()
        for k in (self.kho["kho_bm"], self.kho["kho_pxn"]):
            frappe.db.delete("Customer Stock Ledger Entry", {"kho": k})
            frappe.db.delete("Customer Stock Lot Balance", {"kho": k})
        _make_receipt(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        _make_receipt(self.kho["kho_pxn"], self.kho["vt_pxn"], "LO-PXN-A")

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_kho_me_returns_callers_own_warehouse(self):
        for user, kho_key, customer in (
            (BM_USER, "kho_bm", "Bệnh viện Bạch Mai"),
            (PXN_USER, "kho_pxn", "PXN ABC"),
        ):
            with self.subTest(user=user):
                frappe.set_user(user)
                out = kho_api.kho_me()
                self.assertEqual(out["kho"], self.kho[kho_key])
                self.assertEqual(out["customer"], customer)

    def test_kho_ton_returns_own_stock_and_only_own(self):
        for user, own_vt, other_vt in (
            (BM_USER, "vt_bm", "vt_pxn"),
            (PXN_USER, "vt_pxn", "vt_bm"),
        ):
            with self.subTest(user=user):
                frappe.set_user(user)
                rows = kho_api.kho_ton()
                vat_tus = {r["vat_tu"] for r in rows}
                self.assertIn(self.kho[own_vt], vat_tus)
                self.assertNotIn(self.kho[other_vt], vat_tus)

    def test_kho_lo_returns_own_lots_and_rejects_other_customers_item(self):
        for user, own_vt, other_vt, own_lot in (
            (BM_USER, "vt_bm", "vt_pxn", "LO-BM-A"),
            (PXN_USER, "vt_pxn", "vt_bm", "LO-PXN-A"),
        ):
            with self.subTest(user=user):
                frappe.set_user(user)
                lots = kho_api.kho_lo(self.kho[own_vt])
                self.assertIn(own_lot, [l["so_lo"] for l in lots])
                with self.assertRaises(frappe.PermissionError) as cm:
                    kho_api.kho_lo(self.kho[other_vt])
                # Lỗi tiếng Việt, không lộ tên doctype tiếng Anh, không traceback.
                msg = str(cm.exception)
                self.assertIn("không thuộc kho", msg)
                self.assertNotIn("Customer Warehouse", msg)
                self.assertNotIn("Traceback", msg)


class TestKhoStaffDeskAccess(_KhoVoucherFixture):
    """Positive control cho phía nhân viên: gỡ quyền của `Customer` không
    được đụng tới desk Miyano. Dùng một System Manager THẬT (không phải
    Administrator — Administrator bỏ qua mọi kiểm tra nên sẽ không chứng minh
    được gì)."""

    def test_system_manager_has_full_read_on_every_parent_doctype(self):
        staff = _ensure_staff_user()
        frappe.set_user(staff)
        records = {
            "Customer Warehouse": (self.kho["kho_bm"], self.kho["kho_pxn"]),
            "Customer Warehouse Item": (self.kho["vt_bm"], self.kho["vt_pxn"]),
            "Customer Stock Receipt": (self.receipt_bm.name, self.receipt_pxn.name),
            "Customer Stock Issue": (self.issue_bm.name, self.issue_pxn.name),
            "Customer Stock Ledger Entry": (
                frappe.db.get_value("Customer Stock Ledger Entry",
                                    {"kho": self.kho["kho_bm"]}, "name"),
                frappe.db.get_value("Customer Stock Ledger Entry",
                                    {"kho": self.kho["kho_pxn"]}, "name"),
            ),
            "Customer Stock Lot Balance": (
                frappe.db.get_value("Customer Stock Lot Balance",
                                    {"kho": self.kho["kho_bm"]}, "name"),
                frappe.db.get_value("Customer Stock Lot Balance",
                                    {"kho": self.kho["kho_pxn"]}, "name"),
            ),
            "Customer Supplier": (self.ncc_bm.name, self.ncc_pxn.name),
            "Portal Item Request": (self.yeu_cau_bm.name, self.yeu_cau_pxn.name),
            "Customer Department": (self.khoa_bm.name, self.khoa_pxn.name),
        }
        _assert_fixture_phu_het(self, records, kho_parent_doctypes(), "records")
        for dt, (bm_name, pxn_name) in records.items():
            with self.subTest(doctype=dt):
                self.assertTrue(frappe.has_permission(dt, "read"))
                rows = frappe.get_list(dt, pluck="name", limit_page_length=0)
                self.assertIn(bm_name, rows)
                self.assertIn(pxn_name, rows, "desk phải thấy CẢ hai khách hàng")
                frappe.get_doc(dt, bm_name).check_permission("read")
                frappe.get_doc(dt, pxn_name).check_permission("read")

    def test_system_manager_can_still_write_and_submit_vouchers(self):
        """Không chỉ đọc: gỡ DocPerm không được làm hỏng luồng nghiệp vụ desk."""
        staff = _ensure_staff_user()
        frappe.set_user(staff)
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"], "ngay": "2026-04-01",
            "loai_nhap": "Nhập khác", "nguoi_giao": "Nhân viên desk",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-DESK",
                       "han_su_dung": "2027-06-01", "so_luong": 7,
                       "don_gia": 15000}],
        })
        doc.insert()           # không ignore_permissions — phải qua quyền thật
        doc.submit()
        self.assertEqual(doc.docstatus, 1)
        self.assertTrue(frappe.db.exists(
            "Customer Stock Ledger Entry",
            {"chung_tu": doc.name, "so_lo": "LO-DESK"},
        ))
