<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
import { store } from '../store'
import { showToast } from '../toast'
import { fmtVND, fmtDate, invoiceBadge, daysUntil } from '../format'
import { useIsMobile } from '../useMobile'

const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const invoices = ref([])
const outstanding = ref(0)
// Tên hoá đơn đang xổ khối HĐĐT (F-08) — CHỈ MỘT dòng mở tại một thời điểm,
// đúng hành vi `toggleEinv()` của bản mẫu. Dữ liệu khối đã có sẵn trong
// `inv.einvoice` từ `portal_invoices` (Câu 1), bấm dòng KHÔNG gọi thêm API.
const einvOpen = ref(null)
const hoTroDangGui = ref(null)

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

function einvoicePdfUrl(invName) {
  return (
    '/api/method/miyano_portal.api.portal.portal_einvoice_download?invoice=' +
    encodeURIComponent(invName) +
    '&loai=pdf'
  )
}

async function yeuCauHoTro(invName) {
  if (hoTroDangGui.value) return
  hoTroDangGui.value = invName
  try {
    await api.call('portal_einvoice_ho_tro', { invoice: invName })
    showToast('Đã gửi yêu cầu hỗ trợ — Miyano sẽ liên hệ lại.')
  } catch (e) {
    showToast(e.message || 'Không gửi được yêu cầu hỗ trợ.', 'error')
  } finally {
    hoTroDangGui.value = null
  }
}

const overdueTotal = computed(() =>
  invoices.value.reduce((a, inv) => {
    const d = daysUntil(inv.due_date)
    return a + (d !== null && d < 0 ? Number(inv.outstanding_amount || 0) : 0)
  }, 0)
)
const dueSoonCount = computed(() =>
  invoices.value.filter((inv) => {
    const d = daysUntil(inv.due_date)
    return d !== null && d >= 0 && d <= 7 && Number(inv.outstanding_amount || 0) > 0
  }).length
)

function pdfUrl(name) {
  return (
    '/api/method/miyano_portal.api.portal.portal_document_download?doctype=' +
    encodeURIComponent('Sales Invoice') +
    '&name=' +
    encodeURIComponent(name)
  )
}

onMounted(async () => {
  try {
    const [me, invs] = await Promise.all([
      store.me ? Promise.resolve(store.me) : api.call('portal_me'),
      api.call('portal_invoices', { limit: 100 }),
    ])
    store.setMe(me)
    outstanding.value = me.outstanding
    invoices.value = invs || []
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
      <div class="kpis">
        <div class="card kpi"><div class="n" style="color: var(--red)">{{ fmtVND(outstanding) }}</div><div class="t">Tổng công nợ hiện tại</div></div>
        <div class="card kpi"><div class="n" style="color: var(--orange)">{{ fmtVND(overdueTotal) }}</div><div class="t">Quá hạn thanh toán</div></div>
        <div class="card kpi"><div class="n">{{ dueSoonCount }}</div><div class="t">Hoá đơn đến hạn trong 7 ngày</div></div>
      </div>

      <div v-if="!invoices.length" class="empty">Chưa có hoá đơn nào.</div>

      <!-- DESKTOP: bảng -->
      <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th></th><th>Số hoá đơn</th><th>Ngày</th><th class="right">Giá trị</th>
              <th class="right">Còn phải trả</th><th>Hạn TT</th><th>Trạng thái</th>
              <th>HĐĐT</th><th></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="inv in invoices" :key="inv.name">
              <tr style="cursor: pointer" @click="toggleEinv(inv.name)">
                <td>{{ einvOpen === inv.name ? '▾' : '▸' }}</td>
                <td><b>{{ inv.name }}</b></td>
                <td>{{ fmtDate(inv.posting_date) }}</td>
                <td class="right">{{ fmtVND(inv.grand_total) }}</td>
                <td class="right">{{ fmtVND(inv.outstanding_amount) }}</td>
                <td>{{ fmtDate(inv.due_date) }}</td>
                <td><span class="badge" :class="invoiceBadge(inv.status_vi)">{{ inv.status_vi }}</span></td>
                <td><span class="badge" :class="inv.einvoice.badge">{{ inv.einvoice.nhan }}</span></td>
                <td @click.stop><a :href="pdfUrl(inv.name)" target="_blank" rel="noopener"><button class="btn-o btn-sm">⬇ PDF</button></a></td>
              </tr>
              <tr v-if="einvOpen === inv.name">
                <td colspan="9" style="background: #f8fafc" @click.stop>
                  <div class="flex" style="flex-wrap: wrap; gap: 18px; padding: 8px">
                    <template v-if="inv.einvoice.fei">
                      <div>
                        <span class="tag">Số – ký hiệu</span><br>
                        <b class="mono">{{ inv.einvoice.so || '—' }}{{ inv.einvoice.ky_hieu ? ' · ' + inv.einvoice.ky_hieu : '' }}</b>
                      </div>
                      <div>
                        <span class="tag">Ngày phát hành</span><br>
                        <b>{{ inv.einvoice.ngay_phat_hanh ? fmtDate(inv.einvoice.ngay_phat_hanh) : '—' }}</b>
                      </div>
                      <div v-if="inv.einvoice.ma_tra_cuu">
                        <span class="tag">Mã tra cứu CQT</span><br>
                        <b class="mono">{{ inv.einvoice.ma_tra_cuu }}</b>
                        <button class="btn-o btn-sm" @click="copyMaTraCuu(inv.einvoice.ma_tra_cuu)">📋</button>
                      </div>
                      <div v-if="inv.einvoice.hoa_don_goc">
                        <span class="tag">Hoá đơn gốc</span><br>
                        <b class="mono">{{ inv.einvoice.hoa_don_goc.so || inv.einvoice.hoa_don_goc.fei }}</b>
                        <span class="badge" :class="inv.einvoice.hoa_don_goc.badge">{{ inv.einvoice.hoa_don_goc.nhan }}</span>
                      </div>
                      <div v-if="inv.einvoice.hoa_don_moi">
                        <span class="tag">Hoá đơn điều chỉnh/thay thế</span><br>
                        <b class="mono">{{ inv.einvoice.hoa_don_moi.so || inv.einvoice.hoa_don_moi.fei }}</b>
                        <span class="badge" :class="inv.einvoice.hoa_don_moi.badge">{{ inv.einvoice.hoa_don_moi.nhan }}</span>
                      </div>
                      <div class="flex" style="margin-left: auto; align-items: flex-start">
                        <a v-if="inv.einvoice.tai_duoc" :href="einvoicePdfUrl(inv.name)" target="_blank" rel="noopener">
                          <button class="btn-o btn-sm">⬇ PDF HĐĐT</button>
                        </a>
                        <button v-if="inv.einvoice.ho_tro" class="btn-o btn-sm" :disabled="hoTroDangGui === inv.name" @click="yeuCauHoTro(inv.name)">
                          {{ hoTroDangGui === inv.name ? 'Đang gửi…' : '✉ Yêu cầu hỗ trợ' }}
                        </button>
                      </div>
                    </template>
                    <p v-else class="tag" style="margin: 0">{{ inv.einvoice.nhan }} — hệ thống HĐĐT của Miyano đang xử lý, công nợ vẫn ghi nhận bình thường.</p>
                  </div>
                  <!-- Không lấy được XML gốc từ module HĐĐT (không field nào lưu XML) —
                       PDF ở đây là bản THỂ HIỆN, KHÔNG phải bản gốc pháp lý; không lặp
                       lại câu chú thích cố định của bản mẫu vì sẽ nói sai giá trị pháp
                       lý của file khách vừa tải. -->
                  <p v-if="inv.einvoice.fei" class="tag" style="padding: 0 8px 8px">
                    PDF là bản thể hiện hoá đơn điện tử, không phải bản gốc XML. Cần bản
                    gốc XML có giá trị pháp lý theo NĐ 123/2020, TT 78/2021 — vui lòng
                    liên hệ kế toán Miyano.
                  </p>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- MOBILE: thẻ -->
      <template v-else>
        <div v-for="inv in invoices" :key="inv.name" class="card mb10">
          <div class="sb" style="cursor: pointer" @click="toggleEinv(inv.name)">
            <b>{{ inv.name }}</b><span class="badge" :class="invoiceBadge(inv.status_vi)">{{ inv.status_vi }}</span>
          </div>
          <p class="tag" style="margin-top: 4px">
            {{ fmtDate(inv.posting_date) }} · Hạn TT {{ fmtDate(inv.due_date) }}
            <template v-if="Number(inv.outstanding_amount) > 0"> · Còn {{ fmtVND(inv.outstanding_amount) }}</template>
          </p>
          <div class="sb" style="margin-top: 6px">
            <b style="font-size: 15px">{{ fmtVND(inv.grand_total) }}</b>
            <a :href="pdfUrl(inv.name)" target="_blank" rel="noopener"><button class="btn-o btn-sm">⬇ PDF</button></a>
          </div>
          <div class="sb" style="margin-top: 6px; cursor: pointer" @click="toggleEinv(inv.name)">
            <span class="tag">HĐĐT</span>
            <span class="badge" :class="inv.einvoice.badge">{{ inv.einvoice.nhan }}</span>
          </div>
          <div v-if="einvOpen === inv.name" style="margin-top: 6px; border-top: 1px solid var(--line); padding-top: 6px">
            <template v-if="inv.einvoice.fei">
              <p style="font-size: 13px; margin: 0 0 4px">
                Số – ký hiệu: <b class="mono">{{ inv.einvoice.so || '—' }}{{ inv.einvoice.ky_hieu ? ' · ' + inv.einvoice.ky_hieu : '' }}</b><br>
                Ngày phát hành: <b>{{ inv.einvoice.ngay_phat_hanh ? fmtDate(inv.einvoice.ngay_phat_hanh) : '—' }}</b>
              </p>
              <p v-if="inv.einvoice.ma_tra_cuu" style="font-size: 13px; margin: 0 0 4px">
                Mã tra cứu CQT: <b class="mono">{{ inv.einvoice.ma_tra_cuu }}</b>
                <button class="btn-o btn-sm" @click="copyMaTraCuu(inv.einvoice.ma_tra_cuu)">📋</button>
              </p>
              <p v-if="inv.einvoice.hoa_don_goc" style="font-size: 13px; margin: 0 0 4px">
                Hoá đơn gốc: <b class="mono">{{ inv.einvoice.hoa_don_goc.so || inv.einvoice.hoa_don_goc.fei }}</b>
                <span class="badge" :class="inv.einvoice.hoa_don_goc.badge">{{ inv.einvoice.hoa_don_goc.nhan }}</span>
              </p>
              <p v-if="inv.einvoice.hoa_don_moi" style="font-size: 13px; margin: 0 0 4px">
                Hoá đơn điều chỉnh/thay thế: <b class="mono">{{ inv.einvoice.hoa_don_moi.so || inv.einvoice.hoa_don_moi.fei }}</b>
                <span class="badge" :class="inv.einvoice.hoa_don_moi.badge">{{ inv.einvoice.hoa_don_moi.nhan }}</span>
              </p>
              <div class="flex">
                <a v-if="inv.einvoice.tai_duoc" :href="einvoicePdfUrl(inv.name)" target="_blank" rel="noopener">
                  <button class="btn-o btn-sm">⬇ PDF HĐĐT</button>
                </a>
                <button v-if="inv.einvoice.ho_tro" class="btn-o btn-sm" :disabled="hoTroDangGui === inv.name" @click="yeuCauHoTro(inv.name)">
                  {{ hoTroDangGui === inv.name ? 'Đang gửi…' : '✉ Yêu cầu hỗ trợ' }}
                </button>
              </div>
              <p class="tag" style="margin-top: 6px">
                PDF là bản thể hiện, không phải bản gốc XML. Cần bản gốc XML có giá trị
                pháp lý (NĐ 123/2020, TT 78/2021) — liên hệ kế toán Miyano.
              </p>
            </template>
            <p v-else class="tag" style="margin: 0">{{ inv.einvoice.nhan }} — hệ thống HĐĐT đang xử lý.</p>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>
