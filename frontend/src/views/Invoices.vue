<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { store } from '../store'
import { showToast } from '../toast'
import HoaDonNhap from '../components/HoaDonNhap.vue'
import { fmtVND, fmtDate, invoiceBadge, daysUntil } from '../format'
import { useIsMobile } from '../useMobile'
import PhanTrang from '../components/PhanTrang.vue'
import Icon from '../components/Icon.vue'

const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const invoices = ref([])
const outstanding = ref(0)
// Brief 2026-08-15 (phân trang) — server-side, thay cho limit:100 cố định.
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)
// Tên hoá đơn đang xổ khối HĐĐT (F-08) — CHỈ MỘT dòng mở tại một thời điểm,
// đúng hành vi `toggleEinv()` của bản mẫu. Dữ liệu khối đã có sẵn trong
// `inv.einvoice` từ `portal_invoices` (Câu 1), bấm dòng KHÔNG gọi thêm API.
const einvOpen = ref(null)
const hoTroDangGui = ref(null)

// Chủ đầu tư chốt 05/09/2026 — mở thẳng MỘT hoá đơn từ màn chi tiết đơn
// hàng (`/invoices?hoa-don=ACC-SINV-…`). Không dựng màn chi tiết hoá đơn
// riêng: dòng xổ ở đây đã có đủ trạng thái HĐĐT, bản chính, mọi bản điều
// chỉnh/thay thế và nút yêu cầu hỗ trợ.
//
// LỌC Ở SERVER (`portal_invoices({ ten })`), không lọc trên trang đang tải:
// một bệnh viện giao dịch nhiều năm có hàng trăm hoá đơn, và một liên kết
// chỉ mở được khi hoá đơn tình cờ nằm ở trang đầu là thứ chạy lúc được lúc
// không — tệ hơn không có liên kết.
const route = useRoute()
const router = useRouter()
const locHoaDon = ref(route.query['hoa-don'] || '')

function xemTatCa() {
  locHoaDon.value = ''
  einvOpen.value = null
  trang.value = 1
  router.replace({ name: 'invoices' })
}

function toggleEinv(name) {
  einvOpen.value = einvOpen.value === name ? null : name
}

async function copyMaTraCuu(ma) {
  try {
    await navigator.clipboard.writeText(ma)
    showToast('Đã sao chép mã tra cứu.')
  } catch {
    showToast('Không sao chép được — hãy bôi đen và Ctrl+C.', 'error')
  }
}

// Một hoá đơn có thể khớp NHIỀU chứng từ HĐĐT (gốc + điều chỉnh/thay thế/lập
// lại — review round 1 C-1): `chinh` là bản hiện hành cho badge thu gọn,
// `khac` là MỌI bản còn lại — không được rơi mất một bản nào (NL-12.2).
function dsHddt(inv) {
  return [inv.einvoice.chinh, ...(inv.einvoice.khac || [])]
}

// M-7 (review round 1) — chú thích "PDF là bản thể hiện, không phải bản gốc
// XML" chỉ có Ý NGHĨA khi có một chứng từ HĐĐT THẬT (đã bắt đầu quy trình,
// không còn ở 01-05/"Đang phát hành HĐĐT") — hiện nó cho một hoá đơn còn ở
// dạng nháp là nói về "bản gốc XML" của một thứ CHƯA TỒN TẠI.
function coHddtThat(inv) {
  return dsHddt(inv).some((m) => m.trang_thai !== 'dang_phat_hanh')
}

const taiDangXuLy = ref(null)

// I-3 (review round 1) — tải qua fetch()/Blob thay vì `<a href>` GET: một
// hoá đơn thuế bị từ chối tải (hết hạn, file lỗi, đổi trạng thái giữa lúc
// khách mở tab và lúc bấm) không được mở ra một TAB JSON LỖI TRẦN — phải là
// một toast tiếng Việt, cùng cách `yeuCauHoTro` bên dưới đã làm đúng.
async function taiPdfHddt(invName, feiName) {
  const khoa = invName + '|' + (feiName || '')
  if (taiDangXuLy.value) return
  taiDangXuLy.value = khoa
  const url =
    '/api/method/miyano_portal.api.portal.portal_einvoice_download?invoice=' +
    encodeURIComponent(invName) +
    '&loai=pdf' +
    (feiName ? '&fei=' + encodeURIComponent(feiName) : '')
  try {
    await api.downloadFile(url, invName + '.pdf')
  } catch (e) {
    showToast(e.message || 'Không tải được file PDF.', 'error')
  } finally {
    taiDangXuLy.value = null
  }
}

// E7b — URL bản in thử PDF do Fast dựng, neo theo Sales Invoice. Chuỗi rỗng
// khi chứng từ chưa có file (trạng thái 01: kế toán chưa bấm "Xem bản nháp"),
// khi đó component tự rơi về bảng dòng hàng dự phòng.
function urlPdfNhap(invName, muc) {
  if (!muc || !muc.nhap_tai_duoc) return ''
  return (
    '/api/method/miyano_portal.api.portal.portal_einvoice_download?invoice=' +
    encodeURIComponent(invName) +
    '&loai=nhap&fei=' +
    encodeURIComponent(muc.fei)
  )
}

async function yeuCauHoTro(invName, feiName) {
  if (hoTroDangGui.value) return
  hoTroDangGui.value = invName
  try {
    await api.call('portal_einvoice_ho_tro', { invoice: invName, fei: feiName || undefined })
    showToast('Đã gửi yêu cầu hỗ trợ — Miyano sẽ liên hệ lại.')
  } catch (e) {
    showToast(e.message || 'Không gửi được yêu cầu hỗ trợ.', 'error')
  } finally {
    hoTroDangGui.value = null
  }
}

// Brief 2026-08-15 (phân trang) — hai con số này giờ TÍNH Ở SERVER trên
// TOÀN BỘ hoá đơn còn nợ (`portal_invoices` trả kèm `qua_han_thanh_toan`/
// `sap_den_han_so_luong`), không còn tính từ `invoices.value` (chỉ MỘT
// trang) — bản trước tính client-side trên tối đa 100 dòng đã là gần
// đúng; tính trên một trang 10-50 dòng sẽ sai hẳn theo từng lần lật trang,
// đúng kiểu hồi quy im lặng brief cảnh báo.
const overdueTotal = ref(0)
const dueSoonCount = ref(0)

function pdfUrl(name) {
  return (
    '/api/method/miyano_portal.api.portal.portal_document_download?doctype=' +
    encodeURIComponent('Sales Invoice') +
    '&name=' +
    encodeURIComponent(name)
  )
}

async function loadInvoices() {
  try {
    const res = await api.call('portal_invoices', {
      start: (trang.value - 1) * soDong.value,
      limit: soDong.value,
      ten: locHoaDon.value || undefined,
    })
    invoices.value = res?.rows || []
    // Đang lọc về một hoá đơn thì xổ sẵn khối HĐĐT của nó — khách bấm từ
    // màn đơn hàng sang là để XEM hoá đơn đó, không phải để bấm thêm lần
    // nữa. Không tìm thấy (hoá đơn đã huỷ, link cũ) thì để nguyên trạng
    // thái đóng; khối cảnh báo trên đầu danh sách nói rõ đang lọc gì.
    if (locHoaDon.value) {
      einvOpen.value = invoices.value.some((r) => r.name === locHoaDon.value)
        ? locHoaDon.value
        : null
    }
    tong.value = res?.tong || 0
    overdueTotal.value = res?.qua_han_thanh_toan || 0
    dueSoonCount.value = res?.sap_den_han_so_luong || 0
  } catch (e) {
    error.value = e.message || 'Không tải được hoá đơn.'
  }
}

watch([trang, soDong, locHoaDon], loadInvoices)

onMounted(async () => {
  try {
    const [me] = await Promise.all([
      store.me ? Promise.resolve(store.me) : api.call('portal_me'),
      loadInvoices(),
    ])
    store.setMe(me)
    outstanding.value = me.outstanding
  } catch (e) {
    error.value = e.message || 'Không tải được hoá đơn.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Hoá đơn &amp; công nợ</h2>
        <div class="sub">{{ store.me?.customer_name || '' }}</div>
      </div>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <template v-else>
      <!-- Đang lọc về một hoá đơn (đến từ liên kết trên màn chi tiết đơn) —
           NÓI RÕ đang xem gì và cho đường quay lại. Không có dải này thì
           khách thấy một danh sách một dòng và tưởng mình mất hết hoá đơn
           cũ. Hai thẻ KPI phía dưới CỐ Ý vẫn là tổng công nợ TOÀN đơn vị,
           không phải của riêng dòng này. -->
      <div v-if="locHoaDon" class="note note-b note-ic loc-hd">
        <Icon name="filter" :size="18" />
        <div class="grow">
          <div class="row wrap gap8">
            <span class="grow">Đang xem hoá đơn <b class="mono">{{ locHoaDon }}</b></span>
            <button class="btn-o btn-sm" @click="xemTatCa">
              Xem tất cả hoá đơn
            </button>
          </div>
          <div v-if="!invoices.length" class="tag mt6">
            Không tìm thấy hoá đơn này — có thể nó đã bị huỷ, hoặc liên kết đã cũ.
          </div>
        </div>
      </div>

      <div class="kpis kpis-hd">
        <div class="card kpi kpi-debt">
          <span class="kpi-ic t-red"><Icon name="wallet" :size="19" /></span>
          <span class="kpi-lb t">Tổng công nợ hiện tại</span>
          <span class="n">{{ fmtVND(outstanding) }}</span>
        </div>
        <div class="card kpi kpi-qua-han">
          <span class="kpi-ic t-orange"><Icon name="alert-triangle" :size="19" /></span>
          <span class="kpi-lb t">Quá hạn thanh toán</span>
          <span class="n text-orange">{{ fmtVND(overdueTotal) }}</span>
        </div>
        <div class="card kpi">
          <span class="kpi-ic t-navy"><Icon name="calendar" :size="19" /></span>
          <span class="kpi-lb t">Hoá đơn đến hạn trong 7 ngày</span>
          <span class="n">{{ dueSoonCount }}</span>
        </div>
      </div>

      <div v-if="!invoices.length" class="empty">Chưa có hoá đơn nào.</div>

      <!-- DESKTOP: bảng -->
      <div v-else-if="!isMobile" class="card card-flush">
        <div class="tbl-scroll">
        <table>
          <thead>
            <tr>
              <th class="cot-mo"><span class="sr-only">Mở rộng</span></th><th>Số hoá đơn</th><th>Ngày</th><th class="right">Giá trị</th>
              <th class="right">Còn phải trả</th><th>Hạn TT</th><th>Trạng thái</th>
              <th>HĐĐT</th><th></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="inv in invoices" :key="inv.name">
              <tr class="clickable" :class="{ 'dong-mo': einvOpen === inv.name }" @click="toggleEinv(inv.name)">
                <td class="cot-mo"><Icon :name="einvOpen === inv.name ? 'chevron-down' : 'chevron-right'" :size="16" /></td>
                <td class="cell-code">{{ inv.name }}</td>
                <td>{{ fmtDate(inv.posting_date) }}</td>
                <td class="right">{{ fmtVND(inv.grand_total) }}</td>
                <td class="right fw600">{{ fmtVND(inv.outstanding_amount) }}</td>
                <td>{{ fmtDate(inv.due_date) }}</td>
                <td><span class="badge" :class="invoiceBadge(inv.status_vi)">{{ inv.status_vi }}</span></td>
                <td><span class="badge" :class="inv.einvoice.chinh.badge">{{ inv.einvoice.chinh.nhan }}</span></td>
                <!-- Bản in nội bộ ERPNext (KHÔNG phải chứng từ HĐĐT có giá trị pháp
                     lý) — đổi nhãn để khách không lưu nhầm bản này làm hoá đơn thuế
                     (review round 1, M-5); bản THẬT nằm trong khối xổ dòng dưới. -->
                <td class="right" @click.stop><a :href="pdfUrl(inv.name)" target="_blank" rel="noopener" class="btn-o btn-sm nowrap"><Icon name="download" :size="16" />Bản in</a></td>
              </tr>
              <tr v-if="einvOpen === inv.name" class="dong-hddt">
                <td colspan="9" @click.stop>
                  <template v-if="inv.einvoice.chinh.fei">
                    <div v-for="muc in dsHddt(inv)" :key="muc.fei" class="flex hddt-muc">
                      <div class="hddt-o">
                        <span class="tag">Số – ký hiệu</span>
                        <b class="mono">{{ muc.so || '—' }}{{ muc.mau_so ? ' · Mẫu ' + muc.mau_so : '' }}{{ muc.ky_hieu ? ' · ' + muc.ky_hieu : '' }}</b>
                      </div>
                      <div class="hddt-o">
                        <span class="tag">Trạng thái</span>
                        <span><span class="badge" :class="muc.badge">{{ muc.nhan }}</span></span>
                      </div>
                      <div class="hddt-o">
                        <span class="tag">Ngày phát hành</span>
                        <b>{{ muc.ngay_phat_hanh ? fmtDate(muc.ngay_phat_hanh) : '—' }}</b>
                      </div>
                      <div v-if="muc.ma_tra_cuu" class="hddt-o">
                        <span class="tag">Mã tra cứu CQT</span>
                        <span class="row gap6">
                          <b class="mono">{{ muc.ma_tra_cuu }}</b>
                          <button class="btn-o btn-sm nut-chep" aria-label="Sao chép mã tra cứu" title="Sao chép mã tra cứu" @click="copyMaTraCuu(muc.ma_tra_cuu)"><Icon name="copy" :size="15" /></button>
                        </span>
                      </div>
                      <div v-if="muc.ly_do_huy" class="hddt-o">
                        <span class="tag">Lý do huỷ</span>
                        <b>{{ muc.ly_do_huy }}</b>
                      </div>
                      <div v-if="muc.hoa_don_goc" class="hddt-o">
                        <span class="tag">Hoá đơn gốc</span>
                        <span class="row gap6">
                          <b class="mono">{{ muc.hoa_don_goc.so || muc.hoa_don_goc.fei }}</b>
                          <span class="badge" :class="muc.hoa_don_goc.badge">{{ muc.hoa_don_goc.nhan }}</span>
                        </span>
                      </div>
                      <div v-if="muc.hoa_don_moi" class="hddt-o">
                        <span class="tag">Hoá đơn điều chỉnh/thay thế</span>
                        <span class="row gap6">
                          <b class="mono">{{ muc.hoa_don_moi.so || muc.hoa_don_moi.fei }}</b>
                          <span class="badge" :class="muc.hoa_don_moi.badge">{{ muc.hoa_don_moi.nhan }}</span>
                        </span>
                      </div>
                      <div v-if="muc.trang_thai === 'nhap'" class="hddt-nhap">
                        <HoaDonNhap
                          :du-lieu="{ canh_bao: inv.einvoice.canh_bao }"
                          :url-pdf="urlPdfNhap(inv.name, muc)"
                        />
                      </div>
                      <div class="row gap8 ai-start ml-auto">
                        <button v-if="muc.tai_duoc" class="btn-o btn-sm" :disabled="taiDangXuLy === inv.name + '|' + muc.fei" @click="taiPdfHddt(inv.name, muc.fei)">
                          <template v-if="taiDangXuLy === inv.name + '|' + muc.fei">Đang tải…</template>
                          <template v-else><Icon name="download" :size="16" />PDF HĐĐT</template>
                        </button>
                        <button v-if="muc.ho_tro" class="btn-o btn-sm" :disabled="hoTroDangGui === inv.name" @click="yeuCauHoTro(inv.name, muc.fei)">
                          <template v-if="hoTroDangGui === inv.name">Đang gửi…</template>
                          <template v-else><Icon name="mail" :size="16" />Yêu cầu hỗ trợ</template>
                        </button>
                      </div>
                    </div>
                    <!-- Không lấy được XML gốc từ module HĐĐT (không field nào lưu XML) —
                         PDF ở đây là bản THỂ HIỆN, KHÔNG phải bản gốc pháp lý; không lặp
                         lại câu chú thích cố định của bản mẫu vì sẽ nói sai giá trị pháp
                         lý của file khách vừa tải. -->
                    <p v-if="coHddtThat(inv)" class="tag hddt-chu row-top gap6">
                      <Icon name="info" :size="15" class="shrink0" />
                      <span>PDF là bản thể hiện hoá đơn điện tử, không phải bản gốc XML. Cần bản
                      gốc XML có giá trị pháp lý theo NĐ 123/2020, TT 78/2021 — vui lòng
                      liên hệ kế toán Miyano.</span>
                    </p>
                  </template>
                  <p v-else class="tag hddt-chu">{{ inv.einvoice.chinh.nhan }} — hệ thống HĐĐT của Miyano đang xử lý, công nợ vẫn ghi nhận bình thường.</p>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
        </div>
      </div>

      <!-- MOBILE: thẻ -->
      <template v-else>
        <div v-for="inv in invoices" :key="inv.name" class="card mb10 inv-m">
          <div class="sb pointer" @click="toggleEinv(inv.name)">
            <span class="cell-code">{{ inv.name }}</span><span class="badge" :class="invoiceBadge(inv.status_vi)">{{ inv.status_vi }}</span>
          </div>
          <p class="tag mt4">
            {{ fmtDate(inv.posting_date) }} · Hạn TT {{ fmtDate(inv.due_date) }}
            <template v-if="Number(inv.outstanding_amount) > 0"> · Còn {{ fmtVND(inv.outstanding_amount) }}</template>
          </p>
          <div class="sb mt8">
            <b class="fs16 tnum text-navy">{{ fmtVND(inv.grand_total) }}</b>
            <!-- Bản in nội bộ ERPNext, không phải chứng từ HĐĐT (M-5). -->
            <a :href="pdfUrl(inv.name)" target="_blank" rel="noopener" class="btn-o btn-sm"><Icon name="download" :size="16" />Bản in</a>
          </div>
          <button type="button" class="inv-m-hddt" :aria-expanded="einvOpen === inv.name" @click="toggleEinv(inv.name)">
            <span class="tag grow">HĐĐT</span>
            <span class="badge" :class="inv.einvoice.chinh.badge">{{ inv.einvoice.chinh.nhan }}</span>
            <Icon :name="einvOpen === inv.name ? 'chevron-up' : 'chevron-down'" :size="16" class="muted" />
          </button>
          <div v-if="einvOpen === inv.name" class="inv-m-mo">
            <template v-if="inv.einvoice.chinh.fei">
              <div v-for="muc in dsHddt(inv)" :key="muc.fei" class="inv-m-muc">
                <p class="inv-m-dong">
                  <span class="badge" :class="muc.badge">{{ muc.nhan }}</span><br>
                  Số – ký hiệu: <b class="mono">{{ muc.so || '—' }}{{ muc.mau_so ? ' · Mẫu ' + muc.mau_so : '' }}{{ muc.ky_hieu ? ' · ' + muc.ky_hieu : '' }}</b><br>
                  Ngày phát hành: <b>{{ muc.ngay_phat_hanh ? fmtDate(muc.ngay_phat_hanh) : '—' }}</b>
                </p>
                <p v-if="muc.ma_tra_cuu" class="inv-m-dong row gap6 wrap">
                  <span>Mã tra cứu CQT: <b class="mono">{{ muc.ma_tra_cuu }}</b></span>
                  <button class="btn-o btn-sm nut-chep" aria-label="Sao chép mã tra cứu" title="Sao chép mã tra cứu" @click="copyMaTraCuu(muc.ma_tra_cuu)"><Icon name="copy" :size="15" /></button>
                </p>
                <p v-if="muc.ly_do_huy" class="inv-m-dong">Lý do huỷ: <b>{{ muc.ly_do_huy }}</b></p>
                <p v-if="muc.hoa_don_goc" class="inv-m-dong">
                  Hoá đơn gốc: <b class="mono">{{ muc.hoa_don_goc.so || muc.hoa_don_goc.fei }}</b>
                  <span class="badge" :class="muc.hoa_don_goc.badge">{{ muc.hoa_don_goc.nhan }}</span>
                </p>
                <p v-if="muc.hoa_don_moi" class="inv-m-dong">
                  Hoá đơn điều chỉnh/thay thế: <b class="mono">{{ muc.hoa_don_moi.so || muc.hoa_don_moi.fei }}</b>
                  <span class="badge" :class="muc.hoa_don_moi.badge">{{ muc.hoa_don_moi.nhan }}</span>
                </p>
                <div class="row wrap gap8">
                  <button v-if="muc.tai_duoc" class="btn-o btn-sm" :disabled="taiDangXuLy === inv.name + '|' + muc.fei" @click="taiPdfHddt(inv.name, muc.fei)">
                    <template v-if="taiDangXuLy === inv.name + '|' + muc.fei">Đang tải…</template>
                    <template v-else><Icon name="download" :size="16" />PDF HĐĐT</template>
                  </button>
                  <button v-if="muc.ho_tro" class="btn-o btn-sm" :disabled="hoTroDangGui === inv.name" @click="yeuCauHoTro(inv.name, muc.fei)">
                    <template v-if="hoTroDangGui === inv.name">Đang gửi…</template>
                    <template v-else><Icon name="mail" :size="16" />Yêu cầu hỗ trợ</template>
                  </button>
                </div>
              </div>
              <p v-if="coHddtThat(inv)" class="tag mt6">
                PDF là bản thể hiện, không phải bản gốc XML. Cần bản gốc XML có giá trị
                pháp lý (NĐ 123/2020, TT 78/2021) — liên hệ kế toán Miyano.
              </p>
            </template>
            <p v-else class="tag mb0">{{ inv.einvoice.chinh.nhan }} — hệ thống HĐĐT đang xử lý.</p>
          </div>
        </div>
      </template>

      <PhanTrang v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
    </template>
  </div>
</template>

<style scoped>
.loc-hd { margin-bottom: 14px; }
.kpis-hd { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.kpis-hd .kpi-lb { color: var(--text-2); }
.cot-mo { width: 36px; padding-right: 0; color: var(--text-3); }
tr.dong-mo td { background: var(--accent-soft); }
tr.dong-mo .cot-mo { color: var(--accent); }
tr.dong-hddt > td { background: var(--surface-2); padding: 4px 20px 8px; }
tr.dong-hddt:hover > td { background: var(--surface-2); }
.hddt-muc {
  display: flex; flex-wrap: wrap; gap: 14px 24px; align-items: flex-start;
  padding: 12px 0; border-bottom: 1px solid var(--line);
}
.hddt-o { display: flex; flex-direction: column; gap: 4px; }
.hddt-nhap { flex-basis: 100%; }
.hddt-chu { margin: 0; padding: 10px 0 4px; }
.nut-chep { padding: 0; width: 32px; justify-content: center; }
.inv-m-hddt {
  width: 100%; display: flex; align-items: center; gap: 8px;
  margin-top: 10px; padding: 8px 0 0; min-height: 44px;
  background: none; border: none; border-top: 1px solid var(--line); color: inherit; text-align: left;
}
.inv-m-mo { margin-top: 6px; padding-top: 8px; border-top: 1px solid var(--line); }
.inv-m-muc { margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px dashed var(--line); }
.inv-m-dong { font-size: 13px; margin: 0 0 6px; line-height: 1.6; }
@media (max-width: 900px) {
  .kpis-hd { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .kpis-hd .kpi-debt, .kpis-hd .kpi-qua-han { grid-column: 1 / -1; }
  .kpis-hd .kpi .n { font-size: 20px; overflow-wrap: anywhere; }
  .nut-chep { width: 40px; }
}
</style>
