<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtDateTime, deXuatBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'
import { napHangChoDuyet, GIOI_HAN_CHO_DUYET } from '../cho-duyet'

const isMobile = useIsMobile()
const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref('')
const rows = ref([])
// Việc (e) — danh sách chạm trần `limit`. Phải NÓI RA: một quản lý lọc khoa
// "Huyết học" trên một danh sách đã bị cắt ngầm sẽ thấy 3 phiếu và tin rằng
// khoa đó chỉ có 3.
const biCat = ref(false)

// Task 5 — "quản lý sẽ filter theo khoa … cốt lõi là để quản lý biết được
// khoa nào đang mua cái gì mà để duyệt" (yêu cầu gốc chủ đầu tư). Dropdown
// lấy giá trị từ CHÍNH các phiếu đang hiện — không gọi thêm endpoint nào
// (không có endpoint danh mục khoa "đang có phiếu chờ").
const khoaFilter = ref('') // '' = Tất cả các khoa

// Khoa phòng chỉ có MÃ (`KP-00001`) trong payload danh sách — cùng khuôn
// YeuCauList.vue/DeXuatDetail.vue: nạp danh mục khoa phòng của kho rồi tự
// map mã -> tên. Best-effort: lỗi ở đây chỉ làm dropdown hiện mã thô, không
// chặn cả hàng chờ duyệt.
const khoaPhongList = ref([])
async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Im lặng — xem giải thích ở trên.
  }
}
function tenKhoa(ma) {
  if (!ma) return ''
  const k = khoaPhongList.value.find((x) => x.name === ma)
  return k ? k.ten_khoa_phong : ma
}

// Danh sách khoa để đổ vào dropdown — CHỈ những khoa THẬT SỰ có phiếu đang
// chờ (không phải toàn bộ danh mục khoa phòng của viện): một khoa không có
// gì để duyệt thì không cần xuất hiện trong ô lọc của màn hàng chờ.
const khoaOptions = computed(() => {
  const ma = [...new Set(rows.value.map((r) => r.khoa_phong).filter(Boolean))]
  return ma
    .map((m) => ({ ma: m, ten: tenKhoa(m) }))
    .sort((a, b) => a.ten.localeCompare(b.ten, 'vi'))
})

const filteredRows = computed(() => {
  if (!khoaFilter.value) return rows.value
  return rows.value.filter((r) => r.khoa_phong === khoaFilter.value)
})

// C3 — giữ bộ lọc trong URL. `replace` (không `push`) để mỗi lần đổi khoa
// KHÔNG sinh một bước lịch sử: nếu không, quản lý bấm Quay lại từ phiếu sẽ
// lùi qua từng lần đổi dropdown trước đó.
watch(khoaFilter, (ma) => {
  router.replace({ name: 'duyet', query: ma ? { khoa: ma } : {} })
})

// C3 — mang NƠI ĐÃ TỚI (`tu=duyet`) và bộ lọc đang mở sang màn chi tiết.
// Màn đó dùng đúng hai thứ này để dựng lại nút "Quay lại" (và App.vue dùng
// `tu` để sáng đúng mục nav — việc (c)).
function moPhieu(r) {
  router.push({
    name: 'de-xuat-detail',
    params: { ten: r.name },
    query: { tu: 'duyet', ...(khoaFilter.value ? { khoa: khoaFilter.value } : {}) },
  })
}

// Hai lời gọi ("Chờ duyệt" + "Chờ duyệt sửa") và luật phát hiện bị cắt nằm
// ở `cho-duyet.js` — dùng chung với badge nav ở App.vue và màn chi tiết, để
// bảng và badge không nói hai con số khác nhau.
async function load() {
  loading.value = true
  error.value = ''
  try {
    const kq = await napHangChoDuyet()
    rows.value = kq.rows
    biCat.value = kq.biCat
    // Bảng và badge nav là CÙNG một tập dữ liệu — đồng bộ luôn, thay vì để
    // badge giữ con số từ lúc mount shell.
    store.setChoDuyetCount(kq.rows.length, kq.biCat)
  } catch (e) {
    error.value = e.message || 'Không tải được hàng chờ duyệt.'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  loadKhoaPhongList()
  // C3 — quản lý quay lại từ màn chi tiết phải rơi đúng vào bộ lọc khoa đã
  // chọn. Bộ lọc sống trong URL (`?khoa=`), không trong bộ nhớ component:
  // component bị huỷ khi rời trang, URL thì không.
  if (route.query.khoa) khoaFilter.value = String(route.query.khoa)
  if (!store.me) {
    try {
      store.setMe(await api.call('portal_me'))
    } catch (e) {
      // Subtitle phạm vi chỉ là gợi ý phụ — im lặng bỏ qua.
    }
  }
  load()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Duyệt</h2>
        <div class="sub">Phiếu đề xuất mua đang chờ bạn duyệt — cả gửi mới và xin sửa số lượng</div>
      </div>
    </div>

    <div class="card mb10">
      <div class="field" style="margin-bottom: 0; max-width: 320px">
        <label>Khoa phòng</label>
        <select v-model="khoaFilter">
          <option value="">— Tất cả các khoa —</option>
          <option v-for="k in khoaOptions" :key="k.ma" :value="k.ma">{{ k.ten }}</option>
        </select>
      </div>
    </div>

    <!-- Việc (e) — danh sách chạm trần thì NÓI RA, không cắt im lặng. Đứng
         NGOÀI chuỗi v-if/v-else-if bên dưới: nó là lời cảnh báo ĐI KÈM bảng,
         không phải một nhánh thay thế bảng. -->
    <div v-if="!loading && !error && biCat" class="card mb10" style="border-color: var(--red)">
      <p class="tag" style="color: var(--red)">
        Danh sách đang bị giới hạn ở {{ GIOI_HAN_CHO_DUYET }} phiếu mỗi loại — có thể còn phiếu
        chưa hiện ở đây. Hãy duyệt bớt hàng chờ, hoặc báo Miyano nếu con số này không giảm.
      </p>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!filteredRows.length" class="empty">Không có phiếu nào chờ duyệt.</div>

    <!-- DESKTOP: bảng -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã phiếu</th><th>Khoa phòng</th><th>Trạng thái</th><th>Thời điểm gửi</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in filteredRows"
            :key="r.name"
            style="cursor: pointer"
            @click="moPhieu(r)"
          >
            <td>
              <b v-if="r.ma_de_xuat">{{ r.ma_de_xuat }}</b>
              <span v-else class="tag">(chưa gửi duyệt)</span>
            </td>
            <td>{{ tenKhoa(r.khoa_phong) }}</td>
            <td><span class="badge" :class="deXuatBadge(r.trang_thai)">{{ r.trang_thai }}</span></td>
            <td>{{ r.thoi_diem_gui ? fmtDateTime(r.thoi_diem_gui) : '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- MOBILE: thẻ -->
    <template v-else>
      <div
        v-for="r in filteredRows"
        :key="r.name"
        class="card mb10"
        style="cursor: pointer"
        @click="moPhieu(r)"
      >
        <div class="sb">
          <b v-if="r.ma_de_xuat">{{ r.ma_de_xuat }}</b>
          <span v-else class="tag">(chưa gửi duyệt)</span>
          <span class="badge" :class="deXuatBadge(r.trang_thai)">{{ r.trang_thai }}</span>
        </div>
        <p class="tag" style="margin-top: 4px">
          {{ tenKhoa(r.khoa_phong) }}
          <template v-if="r.thoi_diem_gui"> · Gửi {{ fmtDateTime(r.thoi_diem_gui) }}</template>
        </p>
      </div>
    </template>
  </div>
</template>
