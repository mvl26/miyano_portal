"""Chặn REST resource/document cho doctype con — NG-37c (2026-08-12, ngoài BA
v2 gốc — xem `.superpowers/sdd/2026-08-12-dot-1-chan-mau-P0/task-1c-brief.md`).

**Vì sao NG-37b (`search_guard.client_get_list`/`client_get`,
`override_whitelisted_methods` ở `hooks.py`) không đóng được lỗ này.**
`override_whitelisted_methods` chỉ chặn được lời gọi mà `execute_cmd()`
(`handler.py:65-86`) resolve **theo tên chuỗi** — tra `method` trong dict
này rồi `get_attr()` tới hàm thay thế. Route REST của Frappe không đi qua
đường đó:

- `frappe/api/v1.py::document_list()` và `frappe/api/v2.py::document_list()`
  (phục vụ `/api/resource/<doctype>`, `/api/v1/resource/<doctype>`,
  `/api/v2/document/<doctype>` — dạng list/`?filters=`) gọi
  `frappe.call(frappe.client.get_list, doctype, **frappe.form_dict)` — TRUYỀN
  THẲNG THAM CHIẾU HÀM `frappe.client.get_list` (đối tượng function, đã bind
  sẵn, KHÔNG phải chuỗi `"frappe.client.get_list"`). `override_whitelisted_
  methods` không bao giờ được hỏi tới, vì không có bước tra tên nào xảy ra.
- Dạng đơn lẻ `/<doctype>/<name>` còn lệch hẳn cơ chế: nó không gọi
  `frappe.client.get` chút nào — nó gọi thẳng `frappe.get_doc()` rồi
  `doc.has_permission()`/`doc.check_permission()`. Với doctype con, đường
  này rơi vào `frappe.permissions.has_child_permission()`, hàm này rẽ nhánh
  sang kiểm quyền CHA (`has_permission(parent_doctype, ...)`) TRƯỚC KHI bất
  kỳ `has_permission` hook đăng ký riêng cho doctype con có cơ hội chạy —
  cùng cơ chế đã ghi lại cho tám doctype kho ở khối `has_permission` trong
  `hooks.py` (xem comment ở đó). Đây là lý do brief cấm đăng ký
  `has_permission` cho các doctype con ở đây: nó là một chốt chặn giả, không
  bao giờ được gọi tới.

Nói ngắn: đây không phải lỗi cấu hình (thiếu một entry trong dict) mà là
**giới hạn theo thiết kế** của cơ chế `override_whitelisted_method` — nó chỉ
phủ được request định tuyến bằng tên, không phủ được request định tuyến
bằng tham chiếu hàm Python trực tiếp. Thêm khoá vào dict là vô ích. Cách duy
nhất chặn được cả hai phiên bản API bằng MỘT chỗ là chặn sớm hơn, ở tầng
định tuyến HTTP — tức `before_request`.

**Vì sao chặn ở `before_request`, không ở tầng permission.**
`frappe/app.py::init_request()` gọi các hook `before_request` SAU KHI
`HTTPRequest()` đã resume session từ cookie (`set_session()` ->
`LoginManager()`), nên `frappe.session.user` ở thời điểm hook này chạy đã là
user thật đã đăng nhập (không phải "Guest" mặc định của `frappe.init()`), và
TRƯỚC KHI request được dispatch tới route handler
(`frappe.api.handle()` -> `document_list()`/`read_doc()`). Đó là cửa sổ duy
nhất nhìn thấy được cả path HTTP thật lẫn user đã xác thực, TRƯỚC khi hai
đường lỗ khác hẳn nhau (list qua `frappe.client.get_list` bằng tham chiếu
hàm, đơn lẻ qua `has_child_permission()`) kịp phân nhánh — chặn ở đây đóng
được cả hai bằng một hook, thay vì phải vá riêng từng route/hàm.

Khuôn mẫu port từ `supplycore/supplycore/utils/permissions.py::
portal_block_rest_child` (đã qua review, đang chạy trên bench này) + đăng ký
ở `supplycore/supplycore/hooks.py:177-186`. Giữ nguyên cấu trúc return-sớm
và `unquote()` — CHỈ đổi ba thứ:

1. Phân loại user: `search_guard._la_khach_cong()` (app này dùng
   `user_type == "Website User"`, không dùng tên role như supplycore dùng
   `PORTAL_ROLE in frappe.get_roles(user)`) — TÁI SỬ DỤNG, không viết bản
   phân loại thứ ba.
2. Điều kiện chặn theo doctype — supplycore dùng một tuple bốn tên
   (`_PORTAL_BLOCKED_REST_CHILDREN`). **KHÔNG port phần đó.** Task 1b đã vấp
   đúng lỗi này (Critical C1, review round 1) và bị trả về: chặn theo tên
   liệt kê là allow-by-omission trên TRỤC DOCTYPE — `Payment Schedule`
   (mang `outstanding`), `Sales Taxes and Charges` (mang `rate`,
   `tax_amount`, `total`), và bất kỳ doctype con nào khác của các doctype
   cha đã có `permission_query_conditions` đều lọt nguyên. Lý do cấu trúc:
   `check_parent_permission()` (`db_query.py:1305-1317`, đường mà
   `document_list()` dạng list rơi vào qua `frappe.client.get_list`) chỉ
   kiểm `has_permission(parent)` Ở MỨC DOCTYPE cho BẤT KỲ doctype con nào —
   không riêng bốn/ba tên nào đó. Role `Customer` có read trên Sales Order/
   Delivery Note/Sales Invoice/Blanket Order (xem `permission_query_
   conditions` ở `hooks.py`), nên MỌI bảng con của các doctype cha này đều
   với tới được qua đường đó — liệt kê tên là trò đuổi bắt không bao giờ
   xong (ERPNext/Custom Field có thể thêm bảng con mới bất kỳ lúc nào).
   Gate đúng, đồng nhất với `search_guard.client_get_list`/`client_get`
   (NG-37b) và với chính cách `frappe/client.py:50,99` tự hỏi "đây có phải
   bảng con không": `frappe.is_table(doctype)`. Website User không có nhu
   cầu chính đáng nào đọc BẤT KỲ bảng con nào qua REST — SPA dùng endpoint
   riêng (`miyano_portal/api/portal.py`, `miyano_portal/api/kho.py`; đã
   grep `frontend/src/` xác nhận: mọi lời gọi từ SPA đều qua
   `/api/method/miyano_portal.api.*`, không có chỗ nào dùng `/api/resource`
   hay `/api/v2/document`). Một doctype con mới thêm sau này mặc định BỊ
   CHẶN, không phải mặc định mở — fail-closed theo thuộc tính.
3. Thông điệp lỗi: tiếng Việt.

KHÔNG đụng REST của doctype CHA: `frappe.is_table()` đã tự phân biệt hai
loại này (doctype cha có `istable=0`), và doctype cha đã được
`permission_query_conditions` lọc đúng theo hàng từ trước (Task 1) — chặn
thêm ở đây sẽ chặn NHẦM khách đọc đơn của chính họ qua
`/api/resource/Sales Order`.

**Giới hạn đã biết, CHƯA đóng (NG-37g, xem `docs/CHANGELOG-khac-phuc-BA-v2.md`):**
`frappe/app.py::application()` gọi `init_request(request)` (vòng lặp `before_request`
nằm TRONG hàm đó) RỒI MỚI gọi `validate_auth()` — hàm phân giải header
`Authorization: token <api_key>:<api_secret>`. Với request xác thực bằng API key
(không có cookie `sid`), tại thời điểm hook này chạy, `frappe.session.user` vẫn là
`"Guest"` (chưa được `validate_auth()` gán) → nhánh return-sớm `user == "Guest"`
bên dưới tự thoát, KHÔNG chặn. Đã xác nhận bằng probe HTTP thật (cấp API key cho
`bvbm@demo.miyano` bằng quyền Administrator, gọi REST child doctype kèm header
`Authorization` thay vì cookie → lộ nguyên vẹn). Rủi ro hiện TIỀM ẨN, không phải
đang bị khai thác: SPA chỉ dùng cookie, và không portal Website User nào trên
`erptest.local` có API key trước khi probe (cấp API key đòi `frappe.only_for(
"System Manager")`, khách cổng không tự cấp được). Kế thừa từ mẫu supplycore
(`portal_block_rest_child`, docstring gốc không nhắc `validate_auth()`), không
phải lỗi riêng của lần port này — KHÔNG tự sửa ở đây, đổi thứ tự
`init_request()`/`validate_auth()` là thay đổi hành vi framework, ngoài phạm vi
NG-37c.

`before_request` chạy trên MỌI request Frappe xử lý, kể cả file tĩnh (CSS,
JS, ảnh, trang HTML của SPA) và trang đăng nhập — PHẢI rẻ và an toàn: return
sớm ở MỌI bước trước khi chạm `frappe.is_table()` (thiếu request, path
không chứa "/api/", prefix không khớp một trong ba dạng REST, thiếu
session/user, user là Guest, user không phải khách cổng). `frappe.is_table()`
đọc từ meta cache nên bản thân nó rẻ, nhưng vẫn đặt SAU cùng để request tĩnh
(chiếm đa số lưu lượng) không bao giờ phải chạm meta cache của bất kỳ
doctype nào. Chỉ `frappe.throw()` ở nhánh cuối cùng, sau khi mọi điều kiện
trên đã khớp.
"""

from urllib.parse import unquote

import frappe
from frappe import _

from miyano_portal.search_guard import _la_khach_cong

# Ba prefix REST phải phủ — v1 có hai submount cùng url_rules
# (`frappe/api/__init__.py`): mount gốc "/api" và mount con "/api/v1" trỏ
# cùng danh sách route, nên cả hai dạng đường dẫn đều phải bắt.
# Thứ tự không quan trọng — kiểm từng prefix, dùng prefix khớp đầu tiên để
# tách tên doctype (segment ngay sau prefix, trước dấu "/" kế tiếp nếu có
# <name> đi kèm).
_REST_CHILD_PREFIXES = (
    "/api/resource/",  # v1, submount "/api"
    "/api/v1/resource/",  # v1, submount "/api/v1"
    "/api/v2/document/",  # v2, submount "/api/v2"
)


def chan_rest_doctype_con():
    """`before_request` hook (đăng ký ở `hooks.py`) — chặn khách cổng
    (`_la_khach_cong()`) truy cập REST resource/document endpoint cho BẤT KỲ
    doctype con nào (`frappe.is_table(doctype)`), bất kể có `<name>` hay
    không, bất kể `parent=`/`filters=` client gửi là gì.

    Đọc docstring module ở đầu file này trước khi sửa — đặc biệt phần giải
    thích vì sao gate KHÔNG được liệt kê tên doctype.
    """
    req = getattr(frappe.local, "request", None)
    if not req:
        return

    path = getattr(req, "path", None)
    if not path or "/api/" not in path:
        return

    # Tên doctype có dấu cách (`Sales Order Item`) nên URL thật mang `%20`
    # (hoặc `+` tuỳ client) — so chuỗi trên path thô sẽ trượt prefix lẫn
    # tách tên doctype sai. unquote() TRƯỚC khi so, không phải sau.
    decoded = unquote(path)
    matched_prefix = next(
        (p for p in _REST_CHILD_PREFIXES if decoded.startswith(p)), None
    )
    if not matched_prefix:
        return

    # `parent=`/`filters=` do client gửi KHÔNG được tin để quyết định block
    # hay không — gate chỉ nhìn tên doctype rút từ chính path, đúng segment
    # framework tự dùng để định tuyến.
    doctype = decoded[len(matched_prefix):].split("/", 1)[0]
    if not doctype:
        return

    session = getattr(frappe.local, "session", None)
    user = getattr(session, "user", None) if session else None
    if not user or user == "Guest":
        return

    if not _la_khach_cong(user):
        return

    # `frappe.is_table()` đọc từ meta cache — rẻ, nhưng vẫn đặt sau MỌI
    # bước return-sớm ở trên để request tĩnh/không phải khách cổng không
    # bao giờ phải chạm tới nó.
    if not frappe.is_table(doctype):
        return

    frappe.throw(
        _("Không có quyền truy cập dữ liệu này"), frappe.PermissionError
    )
