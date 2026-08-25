"""Mẫu in theo chế độ kế toán cho Biên bản kiểm hàng và Phiếu giao hàng.

Yêu cầu chủ đầu tư 2026-08-16: *"những phiếu in, biên bản, pdf đều phải đúng
định dạng thông tư chứ không lấy print có sẵn của ERP"*.

Hai lỗ hổng bản này bịt:

1. `Portal Delivery Inspection` **chưa có mẫu in nào** — bấm In là rơi vào mẫu
   Standard của ERPNext. Đúng ra nó là **Mẫu số 03-VT "Biên bản kiểm nghiệm
   vật tư, công cụ, sản phẩm, hàng hoá"**.
2. `Delivery Note` in bằng mẫu thương mại của Miyano, không phải **Mẫu số
   02-VT "Phiếu xuất kho"**.

Dùng lại `_STYLE` của `install_kho_print_formats` — một bảng CSS cho mọi chứng
từ, để hai mẫu mới không trôi dần khỏi bốn mẫu cũ.

**Ràng buộc bối cảnh Jinja** (đọc docstring `install_kho_print_formats` trước
khi sửa): template chỉ được dựa vào `{"doc", "frappe"}`. Mọi thứ khác phải tự
tra bằng `frappe.db.get_value` NGAY TRONG template.

**Về số hiệu mẫu dưới TT107**: bộ mẫu kho sẵn có giữ nguyên số hiệu VT và chỉ
đổi thông tư trích dẫn (xem `HTML_NHAP_TT107`: "Mẫu số 01 - VT ... Thông tư
107/2017"). Hai mẫu ở đây theo ĐÚNG quy ước đó để không có hai cách đánh số
song song trong cùng một app. Nếu kế toán của khách yêu cầu số hiệu khác dưới
TT107, sửa ở đây là đủ — không chỗ nào khác hardcode số hiệu.

**Phiếu xuất kho 02-VT chỉ có MỘT bản**: `Delivery Note` là chứng từ của
CHÍNH Miyano (doanh nghiệp), không phải của khách hàng đơn vị sự nghiệp. TT107
áp cho chứng từ trong kho của khách (`Customer Stock *`), nơi đã có sẵn hai
biến thể.

**Cập nhật 25/08/2026 — 02-VT chuyển sang TT 99/2025/TT-BTC.** Chủ đầu tư giao
bản mẫu `docs/04_MVL_PhieuXuatKho_GiaoHang(DN).docx`; mẫu đó trích
*"Kèm theo Thông tư số 99/2025/TT-BTC ngày 27 tháng 10 năm 2025"* thay cho
TT 200/2014, và đổi tên chứng từ thành **"PHIẾU XUẤT KHO KIÊM BIÊN BẢN BÀN
GIAO"**. Đây là quyết định của chủ đầu tư ghi trong chính bản mẫu, không phải
suy diễn ở đây — thông tư trích dẫn trên một chứng từ kế toán là thứ chỉ chủ
đầu tư/kế toán được chốt.

Bốn thay đổi thực chất so với bản TT200 (không chỉ đổi dòng trích dẫn):
  * thêm hai cột **Số lô / Hạn dùng** — xem `lo_han_cho_in`, hàng dược phẩm
    bàn giao mà không ghi lô/hạn thì biên bản ký xong không truy hồi được;
  * thêm ô **Số đơn hàng (SO/PO)**, **Địa chỉ giao hàng**, **Ngày giờ bàn
    giao**, **Điều kiện bảo quản/Nhiệt độ**;
  * thêm **đoạn cam kết bàn giao** — đây là thứ biến một phiếu xuất kho thành
    một biên bản có giá trị đối chứng;
  * khối ký đổi từ 5 ô (có Kế toán trưởng, Giám đốc) sang đúng **4 ô** của
    bản mẫu: Người lập phiếu / Thủ kho / Người giao hàng / Người nhận hàng.

Bản mẫu docx là NGUỒN, giữ nguyên trong `docs/`. Sửa mẫu in thì mở lại nó,
đừng sửa theo trí nhớ.
"""

import frappe

from miyano_portal.setup.install_kho_print_formats import _STYLE

NAME_BIEN_BAN_TT107 = "Miyano - Biên bản kiểm nghiệm (TT107)"
NAME_BIEN_BAN_TT200 = "Miyano - Biên bản kiểm nghiệm (TT200)"
NAME_PHIEU_XUAT_02VT = "Miyano - Phiếu xuất kho (02-VT)"

# Khách hàng của Miyano phần lớn là bệnh viện công — đơn vị hành chính sự
# nghiệp, tức TT107. Cùng lựa chọn mặc định với bốn mẫu kho sẵn có.
DEFAULT_BIEN_BAN = NAME_BIEN_BAN_TT107

# Biên bản kiểm nghiệm KHÔNG có bộ chọn mẫu theo khách như phiếu kho.
# `Customer Warehouse.mau_phieu_nhap/xuat` không dùng được ở đây: biên bản
# kiểm hàng CỐ Ý chạy cho cả khách chưa mở kho (16/21 khách trên site), nên
# không có bản ghi kho nào để treo lựa chọn. Cài cả hai mẫu, mặc định TT107,
# nhân viên đổi trong dropdown khi khách là doanh nghiệp.

_BB_SETUP = (
	'{% set kh = frappe.db.get_value("Customer", doc.customer, '
	'["customer_name", "tax_id"], as_dict=True) or {} %}'
	'{% set dn = frappe.db.get_value("Delivery Note", doc.delivery_note, '
	'["posting_date", "company"], as_dict=True) or {} %}'
)

# Cột "Kết quả kiểm nghiệm" của 03-VT tách làm hai: ĐÚNG quy cách phẩm chất
# (`sl_nhan`) và KHÔNG đúng quy cách phẩm chất (`sl_tra`). Phần chênh còn lại
# là hàng KHÔNG TỚI NƠI — không thuộc cột nào trong hai cột đó, nên ghi vào
# cột Ghi chú thay vì nhét bừa vào "không đúng quy cách": thiếu hàng và hàng
# hỏng là hai sự việc khác nhau, và biên bản này là chứng từ pháp lý.
_BB_ROWS = """
    {% for i in doc.items %}
    {% set thieu = (i.sl_giao or 0) - (i.sl_nhan or 0) - (i.sl_tra or 0) %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ i.item_name or i.item_code }}</td>
      <td>{{ i.item_code }}</td>
      <td>Kiểm đếm, quan sát bằng mắt</td>
      <td>{{ i.uom or '' }}</td>
      <td class="num">{{ "{:g}".format(i.sl_giao or 0) }}</td>
      <td class="num">{{ "{:g}".format(i.sl_nhan or 0) }}</td>
      <td class="num">{{ "{:g}".format(i.sl_tra or 0) }}</td>
      <td>
        {%- if thieu > 0 %}Thiếu {{ "{:g}".format(thieu) }} {{ i.uom or '' }}. {% endif -%}
        {{ i.ly_do or '' }}
      </td>
    </tr>
    {% endfor %}
"""


def _html_bien_ban(so_thong_tu: str, ngay_thong_tu: str) -> str:
	"""Mẫu 03-VT. Chỉ khác nhau ở dòng trích dẫn thông tư."""
	return _STYLE + _BB_SETUP + """
<div class="phieu-kho">
  <div class="hdr">
    <div>
      <b>Đơn vị:</b> {{ kh.customer_name or doc.customer }}<br/>
      <b>Bộ phận:</b> ......................................
    </div>
    <div class="mau">
      Mẫu số 03 - VT<br/>
      (Ban hành theo Thông tư số """ + so_thong_tu + """<br/>
      ngày """ + ngay_thong_tu + """ của Bộ Tài chính)
    </div>
  </div>
  <h2>BIÊN BẢN KIỂM NGHIỆM</h2>
  <div class="sub">
    (Vật tư, công cụ, sản phẩm, hàng hoá)<br/>
    Ngày {{ frappe.utils.formatdate(doc.ngay_kiem, "dd") }}
    tháng {{ frappe.utils.formatdate(doc.ngay_kiem, "mm") }}
    năm {{ frappe.utils.formatdate(doc.ngay_kiem, "yyyy") }}
    &nbsp;&nbsp; Số: {{ doc.name }}
  </div>

  <p>- Căn cứ Phiếu giao hàng số <b>{{ doc.delivery_note or '' }}</b>
     {% if dn.posting_date %}ngày {{ frappe.utils.formatdate(dn.posting_date, "dd/MM/yyyy") }}{% endif %}
     {% if doc.sales_order %}(theo đơn hàng {{ doc.sales_order }}){% endif %}.</p>

  <p>- Ban kiểm nghiệm gồm:</p>
  <p style="margin-left:24px">
    Ông/Bà ................................................... Chức vụ ............................ Trưởng ban<br/>
    Ông/Bà ................................................... Chức vụ ............................ Uỷ viên<br/>
    Ông/Bà ................................................... Chức vụ ............................ Uỷ viên
  </p>

  <p>- Đã kiểm nghiệm các loại:</p>
  <table class="chung-tu">
    <thead>
      <tr>
        <th rowspan="2">STT</th>
        <th rowspan="2">Tên, nhãn hiệu, quy cách vật tư, công cụ, sản phẩm, hàng hoá</th>
        <th rowspan="2">Mã số</th>
        <th rowspan="2">Phương thức kiểm nghiệm</th>
        <th rowspan="2">Đơn vị tính</th>
        <th rowspan="2">Số lượng theo chứng từ</th>
        <th colspan="2">Kết quả kiểm nghiệm</th>
        <th rowspan="2">Ghi chú</th>
      </tr>
      <tr>
        <th>Số lượng đúng quy cách, phẩm chất</th>
        <th>Số lượng không đúng quy cách, phẩm chất</th>
      </tr>
    </thead>
    <tbody>""" + _BB_ROWS + """</tbody>
  </table>

  <p style="margin-top:12px"><b>Ý kiến của Ban kiểm nghiệm:</b></p>
  <p style="margin-left:24px">
    {%- if doc.ghi_chu %}{{ doc.ghi_chu }}{% else %}
    ...........................................................................................................................
    {% endif -%}
  </p>

  <div class="ky">
    <div><b>Đại diện kỹ thuật</b>(Ký, họ tên)</div>
    <div><b>Thủ kho</b>(Ký, họ tên)</div>
    <div><b>Trưởng ban</b>(Ký, họ tên)</div>
  </div>
</div>
"""


# CSS RIÊNG của 02-VT bản TT 99/2025. Không nhét vào `_STYLE` dùng chung: sáu
# mẫu kho khác đang chia nhau bảng đó, và bốn khối dưới đây (bảng meta 2 cột,
# hàng ký hiệu cột, đoạn cam kết, chân trang) chỉ mẫu này có.
_XUAT_STYLE = """
<style>
  .phieu-kho table.meta { width: 100%; border-collapse: collapse; margin: 8px 0 10px; table-layout: fixed; }
  .phieu-kho table.meta td { border: 0; padding: 2px 0; font-size: 13px; }
  .phieu-kho p { margin: 3px 0; }
  /* Hàng ký hiệu cột của Bộ Tài chính — chữ nhỏ, nhạt, không cạnh tranh với
     tên cột thật ngay trên nó. */
  .phieu-kho tr.ky-hieu th { font-weight: normal; font-style: italic; font-size: 11px; padding: 1px 6px; }
  .phieu-kho .cam-ket { margin-top: 10px; text-align: justify; }
  /* `.ky b` của `_STYLE` chừa sẵn 50px khoảng trống để ký; dòng "Họ tên"
     phải nằm DƯỚI khoảng trống đó, nên là một khối riêng chứ không phải
     text chảy tiếp sau `b`. */
  .phieu-kho .ky i { display: block; font-style: normal; font-size: 12px; margin-top: 4px; }
  .phieu-kho .chan-trang { margin-top: 26px; text-align: center; font-size: 11px; font-style: italic; }
</style>
"""

# `so_don`: mẫu mới có ô "Số đơn hàng (SO/PO)" mà mẫu cũ không có. Lấy từ
# CHÍNH các dòng phiếu (`against_sales_order`) chứ không từ `doc.po_no` —
# `po_no` là số PO của KHÁCH, một ô khác trên cùng mẫu ("Số chứng từ gốc kèm
# theo"). Gộp trùng và giữ thứ tự: một phiếu giao gộp nhiều đơn là chuyện
# thường ở đây (giao gộp nhiều đợt).
#
# `dia_chi`: `shipping_address` là HTML nhiều dòng (Address Display). Ép về
# một dòng bằng `strip_html` — chuỗi thô có `<br>` sẽ bị Jinja escape và in
# ra nguyên văn thẻ trên chứng từ.
_XUAT_SETUP = (
	'{% set cty = frappe.db.get_value("Company", doc.company, '
	'["company_name", "tax_id"], as_dict=True) or {} %}'
	'{% set so_don = (doc.items | map(attribute="against_sales_order") '
	'| select | unique | list | join(", ")) %}'
	# Tách dòng → bỏ dòng RỖNG → ghép: `Address Display` của ERPNext luôn
	# kèm vài dòng trống (address_line2/county không khai), nên phép ghép
	# ngây thơ in ra "..., Hà Nội, Vietnam, ," trên chứng từ có chữ ký.
	'{% set dia_chi = (frappe.utils.strip_html(doc.shipping_address or "")'
	'.split("\n") | map("trim") | select | join(", ") | trim(", ")) %}'
)

_XUAT_ROWS = """
    {% for i in doc.items %}
    {% set lo = lo_han_cho_in(i) %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ i.item_code }}</td>
      <td>{{ i.item_name or i.item_code }}</td>
      <td>{{ i.uom or '' }}</td>
      <td class="num">{{ "{:g}".format(i.qty or 0) }}</td>
      <td class="num">{{ "{:g}".format(i.qty or 0) }}</td>
      <td>{{ lo.so_lo }}</td>
      <td>{{ lo.han_dung }}</td>
      <td class="num">{{ "{:,.0f}".format(i.rate or 0) }}</td>
      <td class="num">{{ "{:,.0f}".format(i.amount or 0) }}</td>
    </tr>
    {% endfor %}
"""

HTML_PHIEU_XUAT_02VT = _STYLE + _XUAT_STYLE + _XUAT_SETUP + """
<div class="phieu-kho">
  <div class="hdr">
    <div>
      <b>{{ (cty.company_name or doc.company)|upper }}</b><br/>
      Bộ phận: .............................................
    </div>
    <div class="mau">
      Mẫu số: 02 - VT<br/>
      (Kèm theo Thông tư số 99/2025/TT-BTC<br/>
      ngày 27 tháng 10 năm 2025 của Bộ trưởng Bộ Tài chính)
    </div>
  </div>

  <h2>PHIẾU XUẤT KHO KIÊM BIÊN BẢN BÀN GIAO</h2>

  <table class="meta">
    <tr>
      <td>Mã phiếu: <b>{{ doc.name }}</b></td>
      <td>Số đơn hàng (SO/PO): {{ so_don or '.' * 24 }}</td>
    </tr>
    <tr>
      <td>Ngày lập:
        {{ frappe.utils.formatdate(doc.posting_date, "dd") }} /
        {{ frappe.utils.formatdate(doc.posting_date, "MM") }} /
        {{ frappe.utils.formatdate(doc.posting_date, "yyyy") }}</td>
      <!-- Ngày GIỜ bàn giao để trống có chủ đích: mốc pháp lý của biên bản
           này là thời điểm hai bên ĐẶT BÚT KÝ tại kho khách, không phải
           `posting_date` của chứng từ trong ERP (thường ghi trước đó). Điền
           hộ bằng dữ liệu ERP là khai khống một mốc thời gian có chữ ký. -->
      <td>Ngày, giờ bàn giao: ......giờ......, ngày......./......./..........</td>
    </tr>
    <tr>
      <td>Nợ: ....................</td>
      <td>Có: ....................</td>
    </tr>
  </table>

  <p>- Họ và tên người nhận hàng: ..................................................
     Bộ phận/Đơn vị: <b>{{ doc.customer_name or doc.customer }}</b></p>
  <p>- Địa chỉ giao hàng: {{ dia_chi or '.' * 90 }}</p>
  <p>- Lý do xuất kho: Giao hàng cho <b>{{ doc.customer_name or doc.customer }}</b>
     {% if doc.is_return %}<b>(PHIẾU TRẢ HÀNG — hàng nhận lại từ khách)</b>{% endif %}</p>
  <p>- Xuất tại kho (ngăn lô): <b>{{ doc.set_warehouse or (doc.items[0].warehouse if doc.items else '') }}</b>
     &nbsp; Địa điểm: ........................................</p>

  <table class="chung-tu">
    <thead>
      <tr>
        <th>STT</th>
        <th>Mã vật tư</th>
        <th>Tên, nhãn hiệu, quy cách hàng hóa</th>
        <th>ĐVT</th>
        <th>SL yêu cầu</th>
        <th>SL thực xuất</th>
        <th>Số lô</th>
        <th>Hạn dùng</th>
        <th>Đơn giá</th>
        <th>Thành tiền</th>
      </tr>
      <!-- Hàng ký hiệu cột của mẫu in Bộ Tài chính. Thứ tự A,C,B,D,1,2,E,F,3,4
           CỐ Ý không theo alphabet — nó là ký hiệu gắn với Ý NGHĨA cột trong
           chế độ kế toán, chép nguyên văn từ mẫu, không "sửa cho thẳng". -->
      <tr class="ky-hieu">
        <th>A</th><th>C</th><th>B</th><th>D</th><th>1</th>
        <th>2</th><th>E</th><th>F</th><th>3</th><th>4</th>
      </tr>
    </thead>
    <tbody>""" + _XUAT_ROWS + """</tbody>
    <tfoot>
      <tr>
        <td colspan="3" style="text-align:right"><b>Cộng</b></td>
        <td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td>
        <td class="num"><b>{{ "{:,.0f}".format(doc.total or 0) }}</b></td>
      </tr>
    </tfoot>
  </table>

  <p>- Tổng số tiền (viết bằng chữ): {{ tien_bang_chu(doc.grand_total or doc.total or 0) }}</p>
  <p>- Số chứng từ gốc kèm theo: {{ doc.po_no or '.' * 60 }}</p>
  <p>- Điều kiện bảo quản/vận chuyển: ..................................................
     Nhiệt độ: .........................</p>

  <!-- Thông tin vận chuyển KHÔNG nằm trong mẫu 02-VT, nhưng giao nhận đang
       dùng nó hằng ngày. Đặt DƯỚI khối chuẩn, tách bằng nhãn riêng — thêm
       thông tin bên dưới không làm sai mẫu, còn bỏ đi thì mất dữ liệu thật. -->
  {% if doc.transporter_name or doc.lr_no %}
  <p style="font-style:italic">
    Vận chuyển: {{ doc.transporter_name or '' }}{% if doc.lr_no %} — Vận đơn số {{ doc.lr_no }}{% endif %}
  </p>
  {% endif %}

  <p class="cam-ket">Hai bên đã kiểm tra và xác nhận: hàng hóa được bàn giao đầy đủ
  về số lượng, đúng chủng loại, quy cách, số lô, hạn dùng nêu trên; bao bì nguyên vẹn
  tại thời điểm bàn giao. Kể từ thời điểm ký nhận, bên nhận chịu trách nhiệm quản lý,
  bảo quản hàng hóa theo đúng điều kiện của nhà sản xuất.</p>

  <div class="ky">
    <div><b>Người lập phiếu</b>(Ký, họ tên)<i>Họ tên: ..................</i></div>
    <div><b>Thủ kho</b>(Ký, họ tên)<i>Họ tên: ..................</i></div>
    <div><b>Người giao hàng</b>(Ký, họ tên)<i>Họ tên: ..................</i></div>
    <div><b>Người nhận hàng</b>(Ký, họ tên)<i>Họ tên: ..................</i></div>
  </div>

  <p class="chan-trang">Liên hệ: 0988.806.848 &nbsp;|&nbsp; Email: info@miyano.com.vn
  &nbsp;|&nbsp; Website: https://miyano.com.vn/</p>
</div>
"""


FORMATS = [
	(NAME_BIEN_BAN_TT107, "Portal Delivery Inspection",
	 _html_bien_ban("107/2017/TT-BTC", "10/10/2017")),
	(NAME_BIEN_BAN_TT200, "Portal Delivery Inspection",
	 _html_bien_ban("200/2014/TT-BTC", "22/12/2014")),
	(NAME_PHIEU_XUAT_02VT, "Delivery Note", HTML_PHIEU_XUAT_02VT),
]


def install_bien_ban_print_formats() -> list[str]:
	"""Idempotent theo kiểu "bỏ qua nếu đã có" — cùng khuôn hai installer sẵn
	có. Trả danh sách mẫu VỪA tạo, để patch/test nhìn được chuyện gì đã xảy ra
	thay vì phải đoán."""
	moi = []
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
		moi.append(name)
	return moi
