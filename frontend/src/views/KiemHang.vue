<script setup>
// Màn "Kiểm hàng" — khách đối chiếu đợt giao, báo phần thiếu và phần hỏng
// cần trả lại. Thiết kế:
// docs/superpowers/specs/2026-08-16-kiem-hang-tra-hang-hong-design.md
//
// CỐ Ý không nằm dưới /kho: màn này chạy cho MỌI khách, kể cả khách chưa mở
// kho (16/21 khách trên site). Gắn nó vào cụm /kho sẽ ngầm gợi ý điều ngược
// lại và sớm muộn có người thêm một guard "phải có kho" vào đây.
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtDate } from '../format'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

// Khớp EPS phía server (PortalDeliveryInspection.EPS). Chỉ để báo lỗi SỚM ở
// client cho đúng cùng ngưỡng — chốt chặn thật vẫn ở server.
const EPS = 0.000001

const loading = ref(true)
const error = ref('')
const saving = ref(false)
const sending = ref(false)

const dn = ref('')
const ngayGiao = ref(null)
const bienBan = ref(null)
const dongGoc = ref([])
const rows = ref([])
const ghiChu = ref('')

// Miyano từ chối → khách được gõ lại. Không có chế độ này, màn khoá cứng ở
// "đã gửi" (bản bị từ chối vẫn là docstatus=1) và khách hết đường đi.
const guiLaiMode = ref(false)
const coTheGuiLai = computed(
  () => !!(bienBan.value && bienBan.value.co_the_gui_lai) && !guiLaiMode.value
)

const daGui = computed(
  () => !!(bienBan.value && bienBan.value.da_gui) && !guiLaiMode.value
)
const trangThai = computed(() => (bienBan.value ? bienBan.value.trang_thai : 'Nháp'))

const BADGE = {
  'Nháp': 'b-gray',
  'Chờ xử lý': 'b-orange',
  'Đã xác nhận': 'b-green',
  'Đã duyệt trả': 'b-blue',
  'Đã thu hồi': 'b-green',
  'Đã xử lý': 'b-green',
  'Từ chối': 'b-red',
}
const badgeClass = computed(() => BADGE[trangThai.value] || 'b-gray')

function thieu(r) {
  const v = num(r.sl_giao) - num(r.sl_nhan) - num(r.sl_tra)
  return v > EPS ? v : 0
}
function num(v) {
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : 0
}

// Lỗi TỪNG DÒNG, hiện ngay tại dòng — không dồn thành một chuỗi rồi đổ vào
// một toast, vì khách cần biết dòng nào sai chứ không phải "có gì đó sai".
function loiDong(r) {
  const giao = num(r.sl_giao)
  const nhan = num(r.sl_nhan)
  const tra = num(r.sl_tra)
  if (nhan < 0 || tra < 0) return 'Số lượng không được âm.'
  if (nhan + tra > giao + EPS) return `Nhận tốt + trả lại không được vượt ${giao}.`
  const lech = Math.abs(nhan + tra - giao) > EPS
  if ((tra > EPS || lech) && !(r.ly_do || '').trim()) return 'Nhập lý do để tiếp tục.'
  return ''
}

const coLoi = computed(() => rows.value.some((r) => loiDong(r)))
const coVanDe = computed(() =>
  rows.value.some((r) => num(r.sl_tra) > EPS || thieu(r) > EPS)
)
const coHangHong = computed(() => rows.value.some((r) => num(r.sl_tra) > EPS))

function apDung(bb) {
  bienBan.value = bb
  ghiChu.value = bb.ghi_chu || ''
  rows.value = (bb.items || []).map((i) => ({ ...i }))
}

// Gõ lại từ ĐẦU (dòng dựng từ chính phiếu giao), không chép lại các con số đã
// bị từ chối: giữ chúng lại là mời khách gửi y nguyên thứ vừa bị bác.
function batDauGuiLai() {
  guiLaiMode.value = true
  rows.value = dongGoc.value.map((i) => ({ ...i }))
  ghiChu.value = ''
}

async function nap() {
  loading.value = true
  error.value = ''
  try {
    const d = await api.call('portal_kiem_hang_get', { delivery_note: route.params.dn })
    dn.value = d.delivery_note
    ngayGiao.value = d.ngay_giao
    dongGoc.value = d.dong_goc || []
    guiLaiMode.value = false
    apDung(d.bien_ban)
  } catch (e) {
    error.value = e.message || 'Không mở được màn kiểm hàng.'
  } finally {
    loading.value = false
  }
}

function payload() {
  return rows.value.map((r) => ({
    item_code: r.item_code,
    sl_nhan: num(r.sl_nhan),
    sl_tra: num(r.sl_tra),
    ly_do: (r.ly_do || '').trim(),
  }))
}

async function luuNhap() {
  saving.value = true
  try {
    await api.call('portal_kiem_hang_luu', {
      delivery_note: dn.value, dong: payload(), ghi_chu: ghiChu.value,
    })
    showToast('Đã lưu nháp. Bạn có thể quay lại hoàn tất sau.')
    await nap()
  } catch (e) {
    showToast(e.message || 'Lưu nháp thất bại.', 'error')
  } finally {
    saving.value = false
  }
}

const xacNhanMo = ref(false)

function moXacNhan() {
  if (coLoi.value) {
    showToast('Còn dòng chưa hợp lệ — xem thông báo đỏ ở từng dòng.', 'error')
    return
  }
  xacNhanMo.value = true
}

async function gui() {
  sending.value = true
  try {
    const kq = await api.call('portal_kiem_hang_gui', {
      delivery_note: dn.value, dong: payload(), ghi_chu: ghiChu.value,
    })
    xacNhanMo.value = false
    showToast(
      kq.co_hang_hong
        ? 'Đã gửi. Miyano sẽ phản hồi về phần hàng hỏng.'
        : 'Đã gửi biên bản kiểm hàng.'
    )
    await nap()
  } catch (e) {
    showToast(e.message || 'Gửi biên bản thất bại.', 'error')
  } finally {
    sending.value = false
  }
}

onMounted(nap)
</script>

<template>
  <div>
    <p class="tag" style="margin-bottom: 8px">
      <a href="#" @click.prevent="router.back()">← Quay lại</a>
    </p>

    <h2 style="margin: 0 0 4px">Kiểm hàng</h2>
    <p class="tag" style="margin-bottom: 14px">
      Phiếu giao <b>{{ dn }}</b>
      <template v-if="ngayGiao"> · giao ngày {{ fmtDate(ngayGiao) }}</template>
      <span class="badge" :class="badgeClass" style="margin-left: 8px">{{ trangThai }}</span>
    </p>

    <p v-if="loading" class="tag">Đang tải…</p>
    <p v-else-if="error" class="tag" style="color: var(--red)">{{ error }}</p>

    <template v-else>
      <!-- Phản hồi của Miyano, đặt TRÊN bảng: khi đã có kết quả thì đó là
           thứ khách vào đây để đọc, không phải các con số họ đã gõ. -->
      <div v-if="bienBan.ly_do_tu_choi" class="card" style="border-color: var(--red)">
        <div class="h3" style="color: var(--red)">Miyano chưa chấp nhận</div>
        <p>{{ bienBan.ly_do_tu_choi }}</p>
        <button v-if="coTheGuiLai" class="btn btn-sm" style="margin-top: 8px" @click="batDauGuiLai">
          Kiểm lại và gửi biên bản mới
        </button>
      </div>
      <div v-else-if="bienBan.phieu_tra_hang" class="card">
        <div class="h3">Miyano đã duyệt trả hàng</div>
        <p class="tag">
          Phiếu trả hàng: <b>{{ bienBan.phieu_tra_hang }}</b>.
          <template v-if="trangThai === 'Đã thu hồi'"> Hàng đã được thu hồi.</template>
          <template v-else> Bộ phận giao nhận sẽ liên hệ để thu hồi phần hàng hỏng.</template>
        </p>
      </div>

      <!-- Trả lời của Miyano về phần hàng THIẾU. `v-if` ĐỘC LẬP, cố ý đứng
           NGOÀI chuỗi v-if/v-else-if của khối hàng hỏng ngay trên: một biên
           bản có thể vừa có hàng hỏng vừa thiếu hàng, và hai việc đó được
           trả lời độc lập — nhét vào chuỗi else sẽ giấu mất một trong hai. -->
      <div v-if="bienBan.xu_ly_thieu" class="card">
        <div class="h3">Hàng thiếu — Miyano đã trả lời</div>
        <p style="margin: 0 0 4px">
          <span class="badge b-orange">{{ bienBan.xu_ly_thieu }}</span>
          <b v-if="bienBan.ngay_hen_giao" style="margin-left: 8px">
            Dự kiến giao {{ fmtDate(bienBan.ngay_hen_giao) }}
          </b>
        </p>
        <p v-if="bienBan.ghi_chu_xu_ly" class="tag" style="margin: 0">
          {{ bienBan.ghi_chu_xu_ly }}
        </p>
      </div>

      <div class="card">
        <div class="h3">Đối chiếu từng mặt hàng</div>
        <p v-if="!daGui" class="tag" style="margin-bottom: 10px">
          Mặc định là <b>nhận đủ</b>. Chỉ sửa những dòng có vấn đề: ghi số nhận
          tốt, số hỏng cần trả lại, và lý do. Phần chênh còn lại được tính là
          <b>thiếu</b>.
        </p>

        <div style="overflow-x: auto">
          <table style="min-width: 640px">
            <thead>
              <tr>
                <th>Mặt hàng</th>
                <th style="text-align: right">SL giao</th>
                <th style="text-align: right">Nhận tốt</th>
                <th style="text-align: right">Hỏng, trả lại</th>
                <th style="text-align: right">Thiếu</th>
                <th>Lý do</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in rows" :key="r.item_code">
                <td>
                  <b>{{ r.item_name || r.item_code }}</b><br />
                  <span class="tag">{{ r.item_code }} · {{ r.uom }}</span>
                  <p v-if="!daGui && loiDong(r)" class="tag" style="color: var(--red); margin: 4px 0 0">
                    {{ loiDong(r) }}
                  </p>
                </td>
                <td style="text-align: right">{{ r.sl_giao }}</td>
                <td style="text-align: right">
                  <input
                    v-if="!daGui" v-model="r.sl_nhan" type="number" min="0" step="any"
                    style="width: 84px; text-align: right"
                  />
                  <span v-else>{{ r.sl_nhan }}</span>
                </td>
                <td style="text-align: right">
                  <input
                    v-if="!daGui" v-model="r.sl_tra" type="number" min="0" step="any"
                    style="width: 84px; text-align: right"
                  />
                  <span v-else>{{ r.sl_tra }}</span>
                </td>
                <td style="text-align: right">
                  <span :style="thieu(r) > 0 ? 'color: var(--red); font-weight: 600' : ''">
                    {{ thieu(r) || '' }}
                  </span>
                </td>
                <td>
                  <input
                    v-if="!daGui" v-model="r.ly_do" type="text" maxlength="140"
                    placeholder="vd. vỡ khi vận chuyển"
                    :style="isMobile ? 'width: 100%' : 'width: 200px'"
                  />
                  <span v-else>{{ r.ly_do }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div style="margin-top: 12px">
          <label class="tag">Ghi chú</label><br />
          <textarea
            v-if="!daGui" v-model="ghiChu" rows="2" maxlength="500"
            style="width: 100%" placeholder="Ghi chú thêm cho Miyano (không bắt buộc)"
          ></textarea>
          <p v-else-if="ghiChu" class="tag">{{ ghiChu }}</p>
        </div>

        <div v-if="!daGui" style="margin-top: 14px">
          <button class="btn-o btn-sm" :disabled="saving || sending" @click="luuNhap">
            {{ saving ? 'Đang lưu…' : 'Lưu nháp' }}
          </button>
          <button
            class="btn btn-sm" style="margin-left: 8px"
            :disabled="saving || sending || coLoi" @click="moXacNhan"
          >
            Gửi biên bản
          </button>
        </div>
        <p v-else class="tag" style="margin-top: 14px">
          Biên bản đã gửi ngày {{ fmtDate(bienBan.ngay_kiem) }} — không sửa được nữa.
        </p>
      </div>
    </template>

    <!-- Xác nhận trước khi gửi: gửi xong là khoá, khách không tự sửa lại
         được (phải chờ Miyano từ chối). Một hành động không lùi được thì
         phải hỏi lại. Dùng modal của app, KHÔNG window.confirm (treo tab). -->
    <div v-if="xacNhanMo" class="modal" @click.self="xacNhanMo = false">
      <div class="card">
        <div class="h3">Gửi biên bản kiểm hàng?</div>
        <p v-if="coHangHong">
          Bạn báo có <b>hàng hỏng cần trả lại</b>. Miyano sẽ xem xét và phản hồi.
        </p>
        <p v-else-if="coVanDe">
          Bạn báo <b>thiếu hàng</b> so với phiếu giao. Miyano sẽ xem xét và phản hồi.
        </p>
        <p v-else>Bạn xác nhận đã <b>nhận đủ</b> hàng của đợt giao này.</p>
        <p class="tag">Sau khi gửi, biên bản sẽ khoá lại và không tự sửa được.</p>
        <div style="margin-top: 14px; text-align: right">
          <button class="btn-o btn-sm" :disabled="sending" @click="xacNhanMo = false">
            Để sau
          </button>
          <button class="btn btn-sm" style="margin-left: 8px" :disabled="sending" @click="gui">
            {{ sending ? 'Đang gửi…' : 'Gửi biên bản' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
