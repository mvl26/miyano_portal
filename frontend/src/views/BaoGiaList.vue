<script setup>
// Tab "Yêu cầu báo giá" (spec 2026-10-12 §6.2). Lọc nhóm và khoa ở SERVER,
// cắt trang ở SERVER — cùng lý do đã ghi ở YeuCauList.vue.
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'
import PhanTrang from '../components/PhanTrang.vue'
import TabDonBaoGia from '../components/TabDonBaoGia.vue'
import Icon from '../components/Icon.vue'
import {
  NHOM_BAO_GIA, nhanNhomBaoGia, khoaNhomBaoGia, dichDongBaoGia,
  nhanDongBaoGia, badgeDongBaoGia,
} from '../bao-gia'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const rows = ref([])
const nhom = ref(khoaNhomBaoGia(route.query.nhom))
const khoaFilter = ref(String(route.query.khoa || ''))
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)
const khoaPhongList = ref([])

const NHOM = ['', ...NHOM_BAO_GIA]

// Cùng endpoint và cùng cách dựng ô lọc khoa với YeuCauList.vue.
function tenKhoa(ma) {
  if (!ma) return ''
  const k = khoaPhongList.value.find((x) => x.name === ma)
  return k ? k.ten_khoa_phong : ma
}
const khoaOptions = computed(() =>
  khoaPhongList.value
    .map((k) => ({ ma: k.name, ten: k.ten_khoa_phong || k.name }))
    .sort((a, b) => a.ten.localeCompare(b.ten, 'vi'))
)

// Lời gọi sau cùng mới được ghi kết quả: đổi nhóm rồi đổi trang liền nhau thì
// trả lời của lời gọi cũ không được đè lên danh sách của bộ lọc mới.
let lanTai = 0
async function load() {
  const lan = ++lanTai
  loading.value = true
  error.value = ''
  try {
    const res = await api.call('portal_bao_gia_danh_sach', {
      start: (trang.value - 1) * soDong.value,
      limit: soDong.value,
      nhom: nhom.value || undefined,
      khoa_phong: khoaFilter.value || undefined,
    })
    if (lan !== lanTai) return
    rows.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    if (lan !== lanTai) return
    error.value = e.message || 'Không tải được danh sách yêu cầu báo giá.'
  } finally {
    if (lan === lanTai) loading.value = false
  }
}

watch([nhom, khoaFilter], () => {
  trang.value = 1
  router.replace({
    name: 'bao-gia',
    query: {
      ...(nhom.value ? { nhom: nhom.value } : {}),
      ...(khoaFilter.value ? { khoa: khoaFilter.value } : {}),
    },
  })
})
watch([trang, soDong, nhom, khoaFilter], load)
watch(() => route.query.nhom, (moi) => {
  if (route.name !== 'bao-gia') return
  const k = khoaNhomBaoGia(moi)
  if (k !== nhom.value) nhom.value = k
})

function mo(r) { router.push(dichDongBaoGia(r)) }

onMounted(async () => {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list_khach', { ca_inactive: 1 })
  } catch (e) {
    // Thiếu danh sách khoa thì cột khoa hiện mã thay cho tên; danh sách vẫn dùng được.
    console.warn('[BaoGiaList] không tải được danh mục khoa phòng:', e)
  }
  if (!store.me) {
    try {
      store.setMe(await api.call('portal_me'))
    } catch (e) {
      // App.vue xử lý phiên hỏng; ở đây chỉ mất ô lọc khoa của quản lý.
      console.warn('[BaoGiaList] không tải được thông tin người dùng:', e)
    }
  }
  load()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div class="grow">
        <h2>Danh sách đơn hàng</h2>
        <div class="sub">Hàng chưa có giá hoặc chưa có mã — Miyano báo giá, quý vị đồng ý rồi mới thành đơn hàng</div>
      </div>
      <router-link :to="{ name: 'dat-hang' }" class="btn"><Icon name="plus" :size="18" />Đặt hàng</router-link>
    </div>
    <div v-else class="mb10">
      <router-link :to="{ name: 'dat-hang' }" class="btn btn-sm"><Icon name="plus" :size="16" />Đặt hàng</router-link>
    </div>

    <TabDonBaoGia dang="bao-gia" />

    <div v-if="store.me?.la_quan_ly && khoaOptions.length" class="card mb10">
      <div class="field mb0 loc-khoa">
        <label>Khoa phòng</label>
        <select v-model="khoaFilter">
          <option value="">— Tất cả các khoa —</option>
          <option v-for="k in khoaOptions" :key="k.ma" :value="k.ma">{{ k.ten }}</option>
        </select>
      </div>
    </div>

    <div class="chips">
      <button v-for="n in NHOM" :key="n" class="chip" :class="{ on: nhom === n }" @click="nhom = n">
        {{ n ? nhanNhomBaoGia(n) : 'Tất cả' }}
      </button>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="empty">Chưa có yêu cầu báo giá nào ở nhóm này.</div>

    <div v-else-if="!isMobile" class="card card-flush">
      <div class="tbl-scroll">
      <table>
        <thead>
          <tr>
            <th>Mã yêu cầu</th><th>Khoa phòng</th><th>Ngày gửi</th>
            <th class="right">Giá trị báo giá</th><th>Hiệu lực đến</th><th>Tình trạng</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.de_xuat || r.bao_gia" class="clickable" @click="mo(r)">
            <td class="cot-ma-yc">
              <b v-if="r.ma" class="cell-code">{{ r.ma }}</b>
              <span v-else class="tag">(chưa gửi duyệt)</span>
              <div v-if="r.ten_don_hang" class="ten-don">{{ r.ten_don_hang }}</div>
            </td>
            <td>{{ tenKhoa(r.khoa_phong) }}</td>
            <td>{{ fmtDate(r.thoi_diem) }}</td>
            <!-- `null` = server không cho người này xem giá (hoặc chưa có báo
                 giá): "—", không phải một số 0 đọc như giá thật. -->
            <td class="right">{{ r.grand_total == null ? '—' : fmtVND(r.grand_total) }}</td>
            <td>{{ r.han_hieu_luc ? fmtDate(r.han_hieu_luc) : '—' }}</td>
            <td>
              <!-- Dòng chưa có báo giá (nhóm `nhap`): huy hiệu là trạng thái
                   phiếu, dòng phụ là tên nhóm. Dòng đã có báo giá: ngược lại. -->
              <span class="badge" :class="badgeDongBaoGia(r)">{{ nhanDongBaoGia(r) }}</span>
              <div class="tag trang-thai-phu">{{ r.trang_thai_bao_gia || nhanNhomBaoGia(r.nhom) }}</div>
            </td>
          </tr>
        </tbody>
      </table>
      </div>
    </div>

    <template v-else>
      <div v-for="r in rows" :key="r.de_xuat || r.bao_gia" class="card mb10 clickable" @click="mo(r)">
        <div class="sb">
          <b v-if="r.ma" class="cell-code">{{ r.ma }}</b>
          <span v-else class="tag">(chưa gửi duyệt)</span>
          <span class="badge" :class="badgeDongBaoGia(r)">{{ nhanDongBaoGia(r) }}</span>
        </div>
        <div v-if="r.ten_don_hang" class="ten-don">{{ r.ten_don_hang }}</div>
        <p class="tag mt4">
          {{ tenKhoa(r.khoa_phong) }} · {{ fmtDate(r.thoi_diem) }}
          <template v-if="r.grand_total != null"> · {{ fmtVND(r.grand_total) }}</template>
          <template v-if="r.han_hieu_luc"> · hiệu lực đến {{ fmtDate(r.han_hieu_luc) }}</template>
        </p>
      </div>
    </template>

    <PhanTrang v-if="!loading && !error" v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
  </div>
</template>

<style scoped>
.loc-khoa { max-width: 320px; }
.cot-ma-yc { min-width: 14rem; }
.trang-thai-phu { margin-top: 2px; }
/* Cùng dáng với tên đơn hàng ở YeuCauList.vue: nhãn của dòng, không cắt bớt. */
.ten-don {
  margin-top: 0.125rem;
  font-size: 0.8125rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
</style>
