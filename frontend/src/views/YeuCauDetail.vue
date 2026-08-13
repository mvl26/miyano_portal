<script setup>
// E6/F-23 [MỚI] — Chi tiết Yêu cầu hàng hoá + comment 2 chiều (pg-ycdetail).
//
// GHI CHÚ VỀ "Timeline trạng thái" của FormSpec F-23: prototype vẽ mỗi mốc
// kèm timestamp riêng ("Mới — 08/08 14:02", "Đang tìm nguồn — 08/08 16:40"…).
// `portal_yeu_cau_detail` KHÔNG trả lịch sử chuyển trạng thái (không có
// endpoint đọc Version/Comment theo mốc trạng thái) — chỉ có trạng thái
// HIỆN TẠI + ngày gửi + hạn SLA. Dựng một timeline nhiều mốc kèm timestamp
// giả định sẽ bịa dữ liệu (một yêu cầu có thể nhảy thẳng Mới → Khách huỷ,
// không nhất thiết đi qua "Đang tìm nguồn"). Thay vào đó hiển thị trạng thái
// hiện tại + ngày gửi thật, kèm một sơ đồ luồng tổng quát (không phải lịch
// sử của riêng yêu cầu này) để định hướng. Xem báo cáo bàn giao — đây là một
// trong các khoảng lệch bản mẫu/endpoint cần xác nhận lại với BA nếu muốn
// timeline có timestamp thật (đòi hỏi endpoint mới đọc Version).
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtDate, fmtDateTime, yeuCauBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { showToast } from '../toast'
import YeuCauModal from '../components/YeuCauModal.vue'
import ReasonModal from '../components/ReasonModal.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const data = ref(null)
const name = computed(() => route.params.name)

const hanHieuLucBaoGia = ref('')
const editOpen = ref(false)
const cancelOpen = ref(false)
const cancelling = ref(false)
const replyText = ref('')
const sendingReply = ref(false)

const TRANG_THAI_KET_THUC = new Set(['Đã chuyển thành đơn', 'Không đáp ứng được', 'Khách huỷ', 'Hết hạn'])
const daKetThuc = computed(() => data.value && TRANG_THAI_KET_THUC.has(data.value.trang_thai))
const suaDuoc = computed(() => data.value && data.value.trang_thai === 'Mới')

// Câu hỏi gần nhất của Miyano khi yêu cầu đang "Cần thêm thông tin"
// (NL-11.3) — bình luận không mang tiền tố "[Khách hàng]"/"[Portal]" là của
// nhân viên Miyano (xem quy ước ở fromKhach() bên dưới).
const cauHoiMiyano = computed(() => {
  if (!data.value || data.value.trang_thai !== 'Cần thêm thông tin') return ''
  const list = data.value.binh_luan || []
  for (let i = list.length - 1; i >= 0; i--) {
    if (!fromKhach(list[i])) return stripPrefix(list[i])
  }
  return ''
})

function fromKhach(c) {
  return /^\[Khách hàng\]|^\[Portal\]/.test(c.content || '')
}
function stripPrefix(c) {
  return (c.content || '').replace(/^\[Khách hàng\]\s*|^\[Portal\][^:]*:\s*/, '')
}

function fileUrl(fileName) {
  return (
    '/api/method/miyano_portal.api.portal.portal_yeu_cau_file?name=' +
    encodeURIComponent(name.value) +
    '&file_name=' +
    encodeURIComponent(fileName)
  )
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api.call('portal_yeu_cau_detail', { name: name.value })
    hanHieuLucBaoGia.value = ''
    if (data.value.trang_thai === 'Đã báo giá' && data.value.don_lien_ket) {
      try {
        const track = await api.call('portal_order_track', { order: data.value.don_lien_ket })
        hanHieuLucBaoGia.value = track?.chap_nhan?.han_hieu_luc || ''
      } catch (e) {
        /* không chặn hiển thị chi tiết yêu cầu nếu đơn liên kết không đọc được */
      }
    }
  } catch (e) {
    error.value = e.message || 'Không tải được chi tiết yêu cầu.'
  } finally {
    loading.value = false
  }
}

function onEdited(res) {
  editOpen.value = false
  showToast(`Đã lưu ${res.name}.`)
  load()
}

async function sendReply() {
  const noi_dung = replyText.value.trim()
  if (!noi_dung || sendingReply.value) return
  sendingReply.value = true
  try {
    await api.call('portal_yeu_cau_tra_loi', { name: name.value, noi_dung })
    replyText.value = ''
    load()
  } catch (e) {
    showToast(e.message || 'Không gửi được trả lời.', 'error')
  } finally {
    sendingReply.value = false
  }
}

async function onCancel(reason) {
  cancelling.value = true
  try {
    await api.call('portal_yeu_cau_cancel', { name: name.value, ly_do: reason })
    cancelOpen.value = false
    showToast('Đã huỷ yêu cầu.')
    load()
  } catch (e) {
    showToast(e.message || 'Không huỷ được yêu cầu.', 'error')
  } finally {
    cancelling.value = false
  }
}

// "Đã có hàng" → F-03/F-21 với filter mặt hàng (best-effort: prefill ô tìm
// kiếm bằng mã item_lien_ket; Catalog.vue tự đọc query "search").
function datNgay() {
  router.push({ path: '/catalog', query: { search: data.value.item_lien_ket } })
}
const guiLaiOpen = ref(false)
function onGuiLaiSaved(res) {
  guiLaiOpen.value = false
  showToast(`Đã gửi ${res.name} — Miyano phản hồi trong 48h làm việc.`)
  router.push({ name: 'yeu-cau-detail', params: { name: res.name } })
}

onMounted(load)
</script>

<template>
  <div>
    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <template v-else-if="data">
      <div class="topbar">
        <div>
          <h2 class="mono" style="font-size: 18px">
            {{ data.name }} <span class="badge" :class="yeuCauBadge(data.trang_thai)">{{ data.trang_thai }}</span>
          </h2>
          <div class="sub">
            {{ data.loai }}
            <template v-if="data.trang_thai === 'Mới' && data.sla_den_han">
              · hạn phản hồi {{ fmtDateTime(data.sla_den_han) }}
            </template>
          </div>
          <!-- `portal_yeu_cau_detail` không trả ngày gửi/người gửi (chỉ
               `portal_yeu_cau_list` có `creation`) — không hiển thị để tránh
               một dòng trống; xem báo cáo bàn giao. -->
        </div>
        <div class="flex">
          <button v-if="!daKetThuc" class="btn-o btn-sm" style="color: var(--red); border-color: var(--red)" @click="cancelOpen = true">
            Huỷ yêu cầu…
          </button>
          <button class="btn-o btn-sm" @click="router.push('/yeu-cau')">← Danh sách</button>
        </div>
      </div>

      <div class="grid2">
        <div>
          <!-- Nội dung yêu cầu -->
          <div class="card mb10" style="margin-bottom: 14px">
            <div class="sb">
              <div class="h3">Nội dung yêu cầu</div>
              <button v-if="suaDuoc" class="btn-o btn-sm" @click="editOpen = true">Sửa</button>
            </div>
            <table>
              <tbody>
                <tr><td class="tag" style="width: 140px">Tên hàng</td><td><b>{{ data.ten_hang }}</b></td></tr>
                <tr v-if="data.quy_cach"><td class="tag">Quy cách / ĐVT</td><td>{{ data.quy_cach }} · {{ data.dvt }}</td></tr>
                <tr v-else><td class="tag">ĐVT</td><td>{{ data.dvt }}</td></tr>
                <tr>
                  <td class="tag">SL dự kiến · tần suất</td>
                  <td>{{ data.so_luong_du_kien }} · {{ data.tan_suat }}<template v-if="data.chu_ky_thang"> ({{ data.chu_ky_thang }} tháng/lần)</template></td>
                </tr>
                <tr v-if="data.ngay_can"><td class="tag">Ngày cần hàng</td><td>{{ fmtDate(data.ngay_can) }}</td></tr>
                <tr v-if="data.hang_xuat_xu"><td class="tag">Hãng mong muốn</td><td>{{ data.hang_xuat_xu }}</td></tr>
                <tr v-if="data.ghi_chu"><td class="tag">Ghi chú</td><td>{{ data.ghi_chu }}</td></tr>
                <tr v-if="data.dinh_kem && data.dinh_kem.length">
                  <td class="tag">Đính kèm</td>
                  <td>
                    <a v-for="f in data.dinh_kem" :key="f.name" :href="fileUrl(f.name)" target="_blank" rel="noopener" style="margin-right: 10px; text-decoration: underline">
                      📎 {{ f.file_name }}
                    </a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Trao đổi -->
          <div class="card">
            <div class="h3">Trao đổi</div>
            <div v-if="cauHoiMiyano" class="note note-b">💬 Miyano hỏi: {{ cauHoiMiyano }} — vui lòng trả lời bên dưới.</div>
            <div v-if="!(data.binh_luan || []).length" class="tag" style="padding: 6px 0">Chưa có trao đổi nào.</div>
            <p v-for="(c, i) in data.binh_luan" :key="i" style="font-size: 13px; margin-bottom: 8px">
              <b>{{ fromKhach(c) ? 'Bạn' : `Miyano (${c.comment_by || c.owner})` }}:</b>
              {{ stripPrefix(c) }}
              <span class="tag">{{ fmtDate(c.creation) }}</span>
            </p>
            <div v-if="!daKetThuc" class="flex" style="margin-top: 8px">
              <input v-model="replyText" placeholder="Nhập trả lời..." @keyup.enter="sendReply" />
              <button class="btn btn-sm" :disabled="sendingReply || !replyText.trim()" @click="sendReply">Gửi</button>
            </div>
          </div>
        </div>

        <div>
          <!-- Trạng thái hiện tại (xem ghi chú đầu file về giới hạn timeline) -->
          <div class="card mb10" style="margin-bottom: 14px">
            <div class="h3">Trạng thái</div>
            <p style="font-size: 13px">
              Hiện tại: <span class="badge" :class="yeuCauBadge(data.trang_thai)">{{ data.trang_thai }}</span>
            </p>
            <p class="tag" style="margin-top: 8px">
              Luồng xử lý: Mới → Đang tìm nguồn → (Cần thêm thông tin, nếu cần bổ sung) →
              Đã báo giá / Đã có hàng / Không đáp ứng được → Kết thúc.
            </p>
          </div>

          <!-- Đã báo giá -->
          <div v-if="data.trang_thai === 'Đã báo giá'" class="card" style="background: #f5f3ff; border-color: #ddd6fe">
            <div class="h3">Báo giá của Miyano</div>
            <p style="font-size: 13px">
              Giá: <b>{{ data.gia_bao ? Number(data.gia_bao).toLocaleString('vi-VN') + ' ₫' : '—' }}</b>
              <template v-if="data.dvt">/{{ data.dvt }}</template>
              <template v-if="data.lead_time_ngay"> · lead time <b>{{ data.lead_time_ngay }} ngày</b></template>
              <br />
              <template v-if="data.don_lien_ket">Đơn: <router-link :to="`/orders/${data.don_lien_ket}`" class="mono" style="text-decoration: underline">{{ data.don_lien_ket }}</router-link></template>
            </p>
            <router-link v-if="data.don_lien_ket" :to="`/orders/${data.don_lien_ket}`">
              <button class="btn" style="width: 100%; margin-top: 10px; background: var(--purple)">Xem &amp; đồng ý đơn →</button>
            </router-link>
            <p v-if="hanHieuLucBaoGia" class="tag" style="margin-top: 6px">Hiệu lực đến {{ fmtDate(hanHieuLucBaoGia) }}</p>
          </div>

          <!-- Đã có hàng -->
          <div v-else-if="data.trang_thai === 'Đã có hàng'" class="card" style="background: #f0fdf4; border-color: #bbf7d0">
            <div class="h3">Đã có hàng</div>
            <p style="font-size: 13px">Mặt hàng đã mở bán<template v-if="data.item_lien_ket">: <b class="mono">{{ data.item_lien_ket }}</b></template>.</p>
            <button class="btn" style="width: 100%; margin-top: 10px" @click="datNgay">Đặt ngay →</button>
          </div>

          <!-- Không đáp ứng được -->
          <div v-else-if="data.trang_thai === 'Không đáp ứng được'" class="card" style="background: #fef2f2; border-color: #fecaca">
            <div class="h3">Không đáp ứng được</div>
            <p style="font-size: 13px">{{ data.ly_do_khong_dap_ung || 'Miyano không thể đáp ứng yêu cầu này.' }}</p>
            <button class="btn-o" style="width: 100%; margin-top: 10px" @click="guiLaiOpen = true">Gửi yêu cầu khác</button>
          </div>
        </div>
      </div>
    </template>

    <YeuCauModal
      :open="editOpen"
      mode="sua"
      :initial="data ? { name: data.name, loai: data.loai, ten_hang: data.ten_hang, quy_cach: data.quy_cach, dvt: data.dvt, so_luong_du_kien: data.so_luong_du_kien, tan_suat: data.tan_suat, chu_ky_thang: data.chu_ky_thang, ngay_can: data.ngay_can, hang_xuat_xu: data.hang_xuat_xu, ghi_chu: data.ghi_chu } : {}"
      :existing-attachments="data ? data.dinh_kem : []"
      @close="editOpen = false"
      @saved="onEdited"
    />
    <YeuCauModal
      :open="guiLaiOpen"
      mode="tao"
      :initial="data ? { loai: 'Tìm nguồn hàng mới', ten_hang: data.ten_hang, quy_cach: data.quy_cach, dvt: data.dvt, so_luong_du_kien: data.so_luong_du_kien } : {}"
      @close="guiLaiOpen = false"
      @saved="onGuiLaiSaved"
    />
    <ReasonModal
      :open="cancelOpen"
      title="Huỷ yêu cầu"
      placeholder="VD: Không còn cần hàng này nữa..."
      :submitting="cancelling"
      submit-label="Huỷ yêu cầu"
      @close="cancelOpen = false"
      @submit="onCancel"
    />
  </div>
</template>
