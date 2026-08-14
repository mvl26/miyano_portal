<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
import { store } from '../store'
import { showToast } from '../toast'
import HoaDonNhap from '../components/HoaDonNhap.vue'
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
                <td><span class="badge" :class="inv.einvoice.chinh.badge">{{ inv.einvoice.chinh.nhan }}</span></td>
                <!-- Bản in nội bộ ERPNext (KHÔNG phải chứng từ HĐĐT có giá trị pháp
                     lý) — đổi nhãn để khách không lưu nhầm bản này làm hoá đơn thuế
                     (review round 1, M-5); bản THẬT nằm trong khối xổ dòng dưới. -->
                <td @click.stop><a :href="pdfUrl(inv.name)" target="_blank" rel="noopener"><button class="btn-o btn-sm">⬇ Bản in</button></a></td>
              </tr>
              <tr v-if="einvOpen === inv.name">
                <td colspan="9" style="background: #f8fafc" @click.stop>
                  <template v-if="inv.einvoice.chinh.fei">
                    <div v-for="muc in dsHddt(inv)" :key="muc.fei" class="flex" style="flex-wrap: wrap; gap: 18px; padding: 8px; border-bottom: 1px solid var(--line)">
                      <div>
                        <span class="tag">Số – ký hiệu</span><br>
                        <b class="mono">{{ muc.so || '—' }}{{ muc.mau_so ? ' · Mẫu ' + muc.mau_so : '' }}{{ muc.ky_hieu ? ' · ' + muc.ky_hieu : '' }}</b>
                      </div>
                      <div>
                        <span class="tag">Trạng thái</span><br>
                        <span class="badge" :class="muc.badge">{{ muc.nhan }}</span>
                      </div>
                      <div>
                        <span class="tag">Ngày phát hành</span><br>
                        <b>{{ muc.ngay_phat_hanh ? fmtDate(muc.ngay_phat_hanh) : '—' }}</b>
                      </div>
                      <div v-if="muc.ma_tra_cuu">
                        <span class="tag">Mã tra cứu CQT</span><br>
                        <b class="mono">{{ muc.ma_tra_cuu }}</b>
                        <button class="btn-o btn-sm" @click="copyMaTraCuu(muc.ma_tra_cuu)">📋</button>
                      </div>
                      <div v-if="muc.ly_do_huy">
                        <span class="tag">Lý do huỷ</span><br>
                        <b>{{ muc.ly_do_huy }}</b>
                      </div>
                      <div v-if="muc.hoa_don_goc">
                        <span class="tag">Hoá đơn gốc</span><br>
                        <b class="mono">{{ muc.hoa_don_goc.so || muc.hoa_don_goc.fei }}</b>
                        <span class="badge" :class="muc.hoa_don_goc.badge">{{ muc.hoa_don_goc.nhan }}</span>
                      </div>
                      <div v-if="muc.hoa_don_moi">
                        <span class="tag">Hoá đơn điều chỉnh/thay thế</span><br>
                        <b class="mono">{{ muc.hoa_don_moi.so || muc.hoa_don_moi.fei }}</b>
                        <span class="badge" :class="muc.hoa_don_moi.badge">{{ muc.hoa_don_moi.nhan }}</span>
                      </div>
                      <div v-if="muc.trang_thai === 'nhap'" style="flex-basis: 100%">
                        <HoaDonNhap
                          :du-lieu="{ canh_bao: inv.einvoice.canh_bao }"
                          :url-pdf="urlPdfNhap(inv.name, muc)"
                        />
                      </div>
                      <div class="flex" style="margin-left: auto; align-items: flex-start">
                        <button v-if="muc.tai_duoc" class="btn-o btn-sm" :disabled="taiDangXuLy === inv.name + '|' + muc.fei" @click="taiPdfHddt(inv.name, muc.fei)">
                          {{ taiDangXuLy === inv.name + '|' + muc.fei ? 'Đang tải…' : '⬇ PDF HĐĐT' }}
                        </button>
                        <button v-if="muc.ho_tro" class="btn-o btn-sm" :disabled="hoTroDangGui === inv.name" @click="yeuCauHoTro(inv.name, muc.fei)">
                          {{ hoTroDangGui === inv.name ? 'Đang gửi…' : '✉ Yêu cầu hỗ trợ' }}
                        </button>
                      </div>
                    </div>
                    <!-- Không lấy được XML gốc từ module HĐĐT (không field nào lưu XML) —
                         PDF ở đây là bản THỂ HIỆN, KHÔNG phải bản gốc pháp lý; không lặp
                         lại câu chú thích cố định của bản mẫu vì sẽ nói sai giá trị pháp
                         lý của file khách vừa tải. -->
                    <p v-if="coHddtThat(inv)" class="tag" style="padding: 8px">
                      PDF là bản thể hiện hoá đơn điện tử, không phải bản gốc XML. Cần bản
                      gốc XML có giá trị pháp lý theo NĐ 123/2020, TT 78/2021 — vui lòng
                      liên hệ kế toán Miyano.
                    </p>
                  </template>
                  <p v-else class="tag" style="margin: 0; padding: 8px">{{ inv.einvoice.chinh.nhan }} — hệ thống HĐĐT của Miyano đang xử lý, công nợ vẫn ghi nhận bình thường.</p>
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
            <!-- Bản in nội bộ ERPNext, không phải chứng từ HĐĐT (M-5). -->
            <a :href="pdfUrl(inv.name)" target="_blank" rel="noopener"><button class="btn-o btn-sm">⬇ Bản in</button></a>
          </div>
          <div class="sb" style="margin-top: 6px; cursor: pointer" @click="toggleEinv(inv.name)">
            <span class="tag">HĐĐT</span>
            <span class="badge" :class="inv.einvoice.chinh.badge">{{ inv.einvoice.chinh.nhan }}</span>
          </div>
          <div v-if="einvOpen === inv.name" style="margin-top: 6px; border-top: 1px solid var(--line); padding-top: 6px">
            <template v-if="inv.einvoice.chinh.fei">
              <div v-for="muc in dsHddt(inv)" :key="muc.fei" style="margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px dashed var(--line)">
                <p style="font-size: 13px; margin: 0 0 4px">
                  <span class="badge" :class="muc.badge">{{ muc.nhan }}</span><br>
                  Số – ký hiệu: <b class="mono">{{ muc.so || '—' }}{{ muc.mau_so ? ' · Mẫu ' + muc.mau_so : '' }}{{ muc.ky_hieu ? ' · ' + muc.ky_hieu : '' }}</b><br>
                  Ngày phát hành: <b>{{ muc.ngay_phat_hanh ? fmtDate(muc.ngay_phat_hanh) : '—' }}</b>
                </p>
                <p v-if="muc.ma_tra_cuu" style="font-size: 13px; margin: 0 0 4px">
                  Mã tra cứu CQT: <b class="mono">{{ muc.ma_tra_cuu }}</b>
                  <button class="btn-o btn-sm" @click="copyMaTraCuu(muc.ma_tra_cuu)">📋</button>
                </p>
                <p v-if="muc.ly_do_huy" style="font-size: 13px; margin: 0 0 4px">Lý do huỷ: <b>{{ muc.ly_do_huy }}</b></p>
                <p v-if="muc.hoa_don_goc" style="font-size: 13px; margin: 0 0 4px">
                  Hoá đơn gốc: <b class="mono">{{ muc.hoa_don_goc.so || muc.hoa_don_goc.fei }}</b>
                  <span class="badge" :class="muc.hoa_don_goc.badge">{{ muc.hoa_don_goc.nhan }}</span>
                </p>
                <p v-if="muc.hoa_don_moi" style="font-size: 13px; margin: 0 0 4px">
                  Hoá đơn điều chỉnh/thay thế: <b class="mono">{{ muc.hoa_don_moi.so || muc.hoa_don_moi.fei }}</b>
                  <span class="badge" :class="muc.hoa_don_moi.badge">{{ muc.hoa_don_moi.nhan }}</span>
                </p>
                <div class="flex">
                  <button v-if="muc.tai_duoc" class="btn-o btn-sm" :disabled="taiDangXuLy === inv.name + '|' + muc.fei" @click="taiPdfHddt(inv.name, muc.fei)">
                    {{ taiDangXuLy === inv.name + '|' + muc.fei ? 'Đang tải…' : '⬇ PDF HĐĐT' }}
                  </button>
                  <button v-if="muc.ho_tro" class="btn-o btn-sm" :disabled="hoTroDangGui === inv.name" @click="yeuCauHoTro(inv.name, muc.fei)">
                    {{ hoTroDangGui === inv.name ? 'Đang gửi…' : '✉ Yêu cầu hỗ trợ' }}
                  </button>
                </div>
              </div>
              <p v-if="coHddtThat(inv)" class="tag" style="margin-top: 6px">
                PDF là bản thể hiện, không phải bản gốc XML. Cần bản gốc XML có giá trị
                pháp lý (NĐ 123/2020, TT 78/2021) — liên hệ kế toán Miyano.
              </p>
            </template>
            <p v-else class="tag" style="margin: 0">{{ inv.einvoice.chinh.nhan }} — hệ thống HĐĐT đang xử lý.</p>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>
