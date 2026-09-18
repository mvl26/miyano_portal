import frappe

from miyano_portal.setup.install_kho_print_formats import _STYLE

NAME = "Miyano - Xác nhận đơn hàng"

# Mẫu "PHIẾU ĐẶT HÀNG" của Miyano — dựng theo bản mẫu
# `docs/03_MVL_Phieu-dat-hang(SO).doc`. Tên bản ghi Print Format GIỮ NGUYÊN
# "Xác nhận đơn hàng": `api/portal.py` (nút "⬇ PDF đơn hàng"),
# `gan_mau_in_mac_dinh` và hai bộ test gọi thẳng tên này; chỉ tiêu đề trên
# tờ giấy đổi theo bản mẫu.
#
# Góc trên bên trái là đơn vị của KHÁCH chứ không phải Miyano (bản mẫu §2:
# "ghi rõ tên của đơn vị theo thông tin của Khách hàng") — người lập phiếu là
# khách, Miyano là bên nhận phiếu.
_DH_STYLE = """
<style>
  .phieu-kho p { margin: 3px 0; }
  .phieu-kho .ma-phieu { text-align: right; font-size: 12px; }
  .phieu-kho tr.ky-hieu th { font-weight: normal; font-style: italic; font-size: 11px; padding: 1px 6px; }
  .phieu-kho .ky i { display: block; font-style: normal; font-size: 12px; margin-top: 4px; }
  .phieu-kho table.chung-tu { table-layout: fixed; }
  .phieu-kho table.chung-tu td { font-size: 12px; }
  .phieu-kho td.x { text-align: center; }
</style>
"""

# `dong`: lọc dòng giữ chỗ `HANG-DAT-NGOAI` TRƯỚC vòng lặp (không lọc trong
# vòng lặp) để cột STT đánh số liền, không nhảy số ở chỗ dòng bị bỏ.
#
# `hop_dong`: hợp đồng khung của đơn — `custom_hdnt` ở đầu đơn, cộng các
# `blanket_order` khác nằm trên từng DÒNG (một đơn có thể gom dòng của nhiều
# hợp đồng, khi đó `custom_hdnt` để trống — xem `dat_hang._xay_don`). Số in ra
# là `order_no` (số hợp đồng hai bên ký); chưa khai thì in mã Blanket Order —
# đúng thứ cổng đang hiện cho khách dưới nhãn "HĐNT".
#
# `nguoi_dat`: `contact_person` là KHOÁ nội bộ dạng "<khách>-<khách>-11",
# không phải họ tên — phải tra `Contact.full_name`.
#
# `dia_chi`: cùng chuỗi xử lý với `_XUAT_SETUP` của mẫu 02-VT — Address
# Display là HTML nhiều dòng, có dòng rỗng.
_DH_SETUP = """
{%- set dong = [] -%}
{%- for i in doc.items -%}
  {%- if not la_dong_giu_cho(i.item_code) %}{% set _ = dong.append(i) %}{% endif -%}
{%- endfor -%}
{%- set ma_hd = [] -%}
{%- for m in [doc.custom_hdnt] + (doc.items | map(attribute="blanket_order") | list) -%}
  {%- if m and m not in ma_hd %}{% set _ = ma_hd.append(m) %}{% endif -%}
{%- endfor -%}
{%- set hop_dong = [] -%}
{%- for m in ma_hd -%}
  {%- set bo = frappe.db.get_value("Blanket Order", m, ["order_no", "order_date", "from_date"], as_dict=True) or {} -%}
  {%- set ngay = bo.order_date or bo.from_date -%}
  {%- set _ = hop_dong.append((bo.order_no or m) ~ (" ngày " ~ frappe.utils.formatdate(ngay, "dd/MM/yyyy") if ngay else "")) -%}
{%- endfor -%}
{%- set nguoi_dat = frappe.db.get_value("Contact", doc.contact_person, "full_name") if doc.contact_person else "" -%}
{%- set khoa = frappe.db.get_value("Customer Department", doc.custom_khoa_phong, "ten_khoa_phong") if doc.custom_khoa_phong else "" -%}
{%- set dia_chi = (frappe.utils.strip_html(doc.shipping_address or doc.address_display or "")
    .split("\n") | map("trim") | select | join(", ") | trim(", ")) -%}
"""

HTML = _STYLE + _DH_STYLE + _DH_SETUP + """
<div class="phieu-kho">
  <div class="hdr">
    <div>
      <b>{{ (doc.customer_name or doc.customer)|upper }}</b><br/>
      Bộ phận: {{ khoa or '.' * 40 }}
    </div>
    <div class="ma-phieu">
      Số phiếu: <b>{{ doc.name }}</b>
    </div>
  </div>

  <h2>PHIẾU ĐẶT HÀNG</h2>
  <div class="sub">
    <i>Ngày {{ frappe.utils.formatdate(doc.transaction_date, "dd") }}
    tháng {{ frappe.utils.formatdate(doc.transaction_date, "MM") }}
    năm {{ frappe.utils.formatdate(doc.transaction_date, "yyyy") }}</i>
  </div>

  <p>- Họ và tên người đặt hàng: <b>{{ nguoi_dat or '.' * 80 }}</b></p>
  <p>- Tên đơn vị đặt hàng: <b>{{ doc.customer_name or doc.customer }}</b>{% if khoa %} — {{ khoa }}{% endif %}</p>
  <p>- Theo Hợp đồng số: {{ hop_dong | join("; ") if hop_dong else '.' * 50 ~ ' ngày ...... tháng ...... năm ......' }}</p>
  {%- if doc.custom_so_po_khach %}
  <p>- Số dự trù/PO khách: {{ doc.custom_so_po_khach }}</p>
  {%- endif %}
  <p>- Địa điểm nhận hàng: {{ dia_chi or '.' * 90 }}</p>
  <p>- Ngày nhận hàng: {{ frappe.utils.formatdate(doc.delivery_date, "dd/MM/yyyy") if doc.delivery_date else '.' * 40 }}</p>

  <table class="chung-tu">
    <colgroup>
      <col style="width:5%"/><col style="width:31%"/><col style="width:15%"/><col style="width:8%"/>
      <col style="width:8%"/><col style="width:10%"/><col style="width:12%"/><col style="width:11%"/>
    </colgroup>
    <thead>
      <tr>
        <th>STT</th>
        <th>Tên, nhãn hiệu, quy cách, phẩm chất vật tư, dụng cụ sản phẩm, hàng hóa</th>
        <th>Mã số</th>
        <th>Đơn vị tính</th>
        <th>Số lượng</th>
        <th>Đơn giá</th>
        <th>Thành tiền</th>
        <th>Ghi chú</th>
      </tr>
      <!-- Ký hiệu cột chép nguyên văn từ bản mẫu 03_MVL. -->
      <tr class="ky-hieu">
        <th>A</th><th>B</th><th>C</th><th>D</th><th>1</th><th>2</th><th>3</th><th>4</th>
      </tr>
    </thead>
    <tbody>
    {%- for i in dong %}
      <tr>
        <td style="text-align:center">{{ loop.index }}</td>
        <td>{{ i.item_name or i.item_code }}</td>
        <td>{{ i.item_code }}</td>
        <td>{{ i.uom or '' }}</td>
        <td class="num">{{ "{:g}".format(i.qty or 0) }}</td>
        <td class="num">{{ "{:,.0f}".format(i.rate or 0).replace(",", ".") }}</td>
        <td class="num">{{ "{:,.0f}".format(i.amount or 0).replace(",", ".") }}</td>
        <td></td>
      </tr>
    {%- endfor %}
    </tbody>
    <tfoot>
      <tr>
        <td></td>
        <td style="text-align:center"><b>Cộng</b></td>
        <td class="x">x</td><td class="x">x</td><td class="x">x</td><td class="x">x</td>
        <td class="num"><b>{{ "{:,.0f}".format(doc.total or 0).replace(",", ".") }}</b></td>
        <td></td>
      </tr>
      {#- Đơn có thuế: dòng "Cộng" là tiền hàng, còn dòng "bằng chữ" là tổng
          thanh toán — thiếu dòng thuế thì hai con số lệch nhau mà không có
          gì giải thích trên tờ khách ký. #}
      {%- if doc.total_taxes_and_charges %}
      <tr>
        <td></td><td style="text-align:center">Thuế GTGT</td>
        <td class="x">x</td><td class="x">x</td><td class="x">x</td><td class="x">x</td>
        <td class="num">{{ "{:,.0f}".format(doc.total_taxes_and_charges).replace(",", ".") }}</td>
        <td></td>
      </tr>
      <tr>
        <td></td><td style="text-align:center"><b>Tổng cộng thanh toán</b></td>
        <td class="x">x</td><td class="x">x</td><td class="x">x</td><td class="x">x</td>
        <td class="num"><b>{{ "{:,.0f}".format(doc.grand_total or 0).replace(",", ".") }}</b></td>
        <td></td>
      </tr>
      {%- endif %}
    </tfoot>
  </table>

  <p style="margin-top:8px">- Tổng số tiền (viết bằng chữ): <i>{{ tien_bang_chu(doc.grand_total or doc.total or 0) }}</i></p>
  <p>- Lưu ý (nếu cần): {{ doc.custom_yeu_cau_khach or '.' * 80 }}</p>

  <div class="ky">
    <div></div>
    <div></div>
    <div>
      <b>Người lập phiếu/Đại diện Đơn vị mua<br/><i>(Ký, họ tên)</i></b>
      <i>{{ nguoi_dat or '' }}</i>
    </div>
  </div>
</div>
"""

NAME_DN = "Miyano - Phiếu giao hàng"
HTML_DN = """
<div class="print-heading"><h2>PHIẾU GIAO HÀNG / DELIVERY NOTE</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số phiếu / Delivery No:</b> {{ doc.name }}
   &nbsp; <b>Ngày / Date:</b> {{ frappe.utils.formatdate(doc.posting_date, "dd/mm/yyyy") }}</p>
<p><b>Đơn hàng / Sales Order:</b> {{ doc.items[0].against_sales_order if doc.items else "" }}</p>
<table class="table table-bordered">
  <thead><tr>
    <th>Mã / Code</th><th>Tên hàng / Item</th><th>SL / Qty</th>
    <th>Đơn giá / Rate</th><th>Thành tiền / Amount</th>
  </tr></thead>
  <tbody>
  {% for i in doc.items %}
    <tr>
      <td>{{ i.item_code }}</td><td>{{ i.item_name }}</td>
      <td class="text-right">{{ i.qty }}</td>
      <td class="text-right">{{ "{:,.0f}".format(i.rate) }} ₫</td>
      <td class="text-right">{{ "{:,.0f}".format(i.amount) }} ₫</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
<p class="text-right"><b>Tổng cộng / Total:</b> {{ "{:,.0f}".format(doc.grand_total) }} ₫</p>
"""

NAME_SI = "Miyano - Hoá đơn"
HTML_SI = """
<div class="print-heading"><h2>HOÁ ĐƠN BÁN HÀNG / SALES INVOICE</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số hoá đơn / Invoice No:</b> {{ doc.name }}
   &nbsp; <b>Ngày / Date:</b> {{ frappe.utils.formatdate(doc.posting_date, "dd/mm/yyyy") }}</p>
<p><b>Đơn hàng / Sales Order:</b> {{ doc.items[0].sales_order if doc.items else "" }}</p>
<table class="table table-bordered">
  <thead><tr>
    <th>Mã / Code</th><th>Tên hàng / Item</th><th>SL / Qty</th>
    <th>Đơn giá / Rate</th><th>Thành tiền / Amount</th>
  </tr></thead>
  <tbody>
  {% for i in doc.items %}
    <tr>
      <td>{{ i.item_code }}</td><td>{{ i.item_name }}</td>
      <td class="text-right">{{ i.qty }}</td>
      <td class="text-right">{{ "{:,.0f}".format(i.rate) }} ₫</td>
      <td class="text-right">{{ "{:,.0f}".format(i.amount) }} ₫</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
<p class="text-right"><b>Tổng cộng / Total:</b> {{ "{:,.0f}".format(doc.grand_total) }} ₫</p>
<p class="text-right"><b>Còn nợ / Outstanding:</b> {{ "{:,.0f}".format(doc.outstanding_amount) }} ₫</p>
"""

NAME_BG = "Miyano - Báo giá"
HTML_BG = """
<div class="print-heading"><h2>BÁO GIÁ / QUOTATION</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số đơn / Order No:</b> {{ doc.name }}
   &nbsp; <b>Ngày báo giá / Quotation Date:</b>
   {{ frappe.utils.formatdate(doc.custom_ngay_gui_khach_duyet or doc.transaction_date, "dd/mm/yyyy") }}</p>
<p><b>Hiệu lực đến / Valid Until:</b>
   {{ han_hieu_luc_bao_gia(doc).strftime('%d/%m/%Y') }}</p>
<table class="table table-bordered">
  <thead><tr>
    <th>Mã / Code</th><th>Tên hàng / Item</th><th>ĐVT / UoM</th><th>SL / Qty</th>
    <th>Đơn giá / Rate</th><th>Thành tiền / Amount</th>
  </tr></thead>
  <tbody>
  {% for i in doc.items %}
    {%- if not la_dong_giu_cho(i.item_code) %}
    <tr>
      <td>{{ i.item_code }}</td><td>{{ i.item_name }}</td><td>{{ i.uom }}</td>
      <td class="text-right">{{ i.qty }}</td>
      <td class="text-right">{{ "{:,.0f}".format(i.rate).replace(",", ".") }} ₫</td>
      <td class="text-right">{{ "{:,.0f}".format(i.amount).replace(",", ".") }} ₫</td>
    </tr>
    {%- endif %}
  {% endfor %}
  </tbody>
</table>
{% set cho_nguon = doc.get("custom_dat_ngoai") | selectattr("da_xu_ly", "equalto", 0) | list %}
{% if cho_nguon %}
<h4>Hàng đang tìm nguồn / Items being sourced</h4>
<!-- CR-03 — thêm Model/Hãng SX/Quy cách: TỜ GIẤY NÀY chính là thứ purchasing
     cầm đi hỏi nhà cung cấp (thiết kế §8), nên ba field khách đã khai trên
     màn Đặt hàng phải đi TIẾP xuống đây thay vì dừng lại ở màn hình Desk. -->
<table class="table table-bordered">
  <thead><tr>
    <th>Tên hàng / Item</th><th>ĐVT / UoM</th><th>SL / Qty</th>
    <th>Model</th><th>Hãng SX / Brand</th><th>Quy cách / Packing</th>
  </tr></thead>
  <tbody>
  {% for d in cho_nguon %}
    <tr><td>{{ d.ten_hang }}</td><td>{{ d.dvt }}</td>
        <td class="text-right">{{ d.so_luong }}</td>
        <td>{{ d.model_ma or "" }}</td>
        <td>{{ d.hang_san_xuat or "" }}</td>
        <td>{{ d.quy_cach or "" }}</td></tr>
  {% endfor %}
  </tbody>
</table>
<p class="text-muted">Các mặt hàng trên chưa có trong báo giá; Miyano sẽ báo giá bổ sung sau khi tìm được nguồn.</p>
{% endif %}
{# Lệch so với brief gốc — xem ghi chú trong nhomB-report.md §"chỗ lệch": #}
{# `item_khop` KHÔNG BAO GIỜ tự sinh một dòng "items" mới ở bất cứ đâu trong #}
{# codebase (đã kiểm `_xay_don_ban_le`/`dong_bo_da_xu_ly_dat_ngoai` — hàm sau #}
{# chỉ BẬT cờ `da_xu_ly`, không `so.append("items", ...)`) — nên một dòng đặt #}
{# ngoài ĐÃ khớp mã (`da_xu_ly=1`) không nằm trong `doc.items` VÀ bị lọc khỏi #}
{# bảng "chưa xử lý" ở trên: KHÔNG bảng nào in nó ra. Đúng lỗi mà docstring #}
{# test (`test_bao_gia_pdf.py`) đặt lên hàng đầu — "thiếu dòng đặt ngoài đã #}
{# khớp mã là khách nhận báo giá thiếu đúng món họ lo nhất". Thêm bảng riêng #}
{# cho nhóm ĐÃ khớp, ghi rõ mã Miyano đã gán — khách thấy yêu cầu của mình #}
{# được phục vụ bằng dòng hàng nào trong bảng trên, kể cả khi đó là một mã #}
{# đã có sẵn trong giỏ (không phải một dòng "items" riêng mới thêm). #}
{% set da_khop = doc.get("custom_dat_ngoai") | selectattr("da_xu_ly", "equalto", 1) | list %}
{% if da_khop %}
<h4>Hàng đặt ngoài đã khớp mã / Matched items</h4>
<table class="table table-bordered">
  <thead><tr>
    <th>Tên hàng khách yêu cầu / Requested</th>
    <th>Mã đã khớp / Matched code</th>
    <th>SL / Qty</th>
  </tr></thead>
  <tbody>
  {% for d in da_khop %}
    <tr><td>{{ d.ten_hang }}</td><td>{{ d.item_khop }}</td>
        <td class="text-right">{{ d.so_luong }}</td></tr>
  {% endfor %}
  </tbody>
</table>
<p class="text-muted">Các mặt hàng trên đã được Miyano khớp mã và tính vào bảng báo giá phía trên.</p>
{% endif %}
<p class="text-right"><b>Tổng cộng / Total:</b> {{ "{:,.0f}".format(doc.grand_total).replace(",", ".") }} ₫</p>
"""
# review Minor — mẫu Báo giá (`HTML_BG`) và mẫu Phiếu đặt hàng (`HTML`,
# dựng lại theo 03_MVL) dùng dấu chấm phân nhóm (`1.234.567`, đúng quy ước dự
# án). Hai mẫu CŨ còn lại (`HTML_DN`, `HTML_SI`) vẫn dùng `"{:,.0f}"` (dấu
# phẩy, sai quy ước) — đó là NỢ CŨ, cố ý chưa sửa để không lan phạm vi.

FORMATS = [
    (NAME, "Sales Order", HTML),
    (NAME_DN, "Delivery Note", HTML_DN),
    (NAME_SI, "Sales Invoice", HTML_SI),
    (NAME_BG, "Sales Order", HTML_BG),
]


def install_portal_print_formats():
    for name, doc_type, html in FORMATS:
        if frappe.db.exists("Print Format", name):
            continue
        frappe.get_doc({
            "doctype": "Print Format",
            "name": name,
            "doc_type": doc_type,
            "standard": "No",
            "custom_format": 1,
            "print_format_type": "Jinja",
            "html": html,
        }).insert(ignore_permissions=True)
