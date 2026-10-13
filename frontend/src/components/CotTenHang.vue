<script setup>
// Ba ô Mã → Tên mặt hàng → Tên thường gọi của MỘT dòng hàng — dùng chung cho
// mọi bảng mặt hàng của cổng (quy tắc ở `ten-hang.js`, chủ đầu tư 13/10/2026).
// Đặt `head` để ra ba ô tiêu đề tương ứng, cho thead và tbody không lệch nhau.
//
// Component trả về ba <td>/<th> liền nhau (fragment), nên phải đặt TRỰC TIẾP
// trong một <tr>.
//
//   <tr><CotTenHang head /> <th>ĐVT</th> …</tr>
//   <tr><CotTenHang :ma="r.item_code" :ten="r.item_name" /> <td>…</td></tr>
//
// `tenGoi` truyền vào thì dùng luôn (màn Chọn hàng đã có sẵn trong payload);
// bỏ trống thì component tự tra kho tên theo mã. Slot mặc định nằm dưới tên
// mặt hàng — chỗ của nhãn và ghi chú riêng từng bảng.
import { computed, watchEffect } from 'vue'
import { TIEU_DE_COT, ghepTenThuongGoi, tenMatHang } from '../ten-hang'
import { napTenHang, tenTrongKho } from '../useTenHang'

const props = defineProps({
  head: { type: Boolean, default: false },
  ma: { type: String, default: '' },
  ten: { type: String, default: '' },
  tenGoi: { type: Array, default: null },
})

watchEffect(() => {
  if (!props.head && props.ma && (props.tenGoi === null || !props.ten)) napTenHang([props.ma])
})

const trongKho = computed(() => (props.ma ? tenTrongKho(props.ma) : null))
const tenHien = computed(() => tenMatHang(props.ten, trongKho.value?.item_name))
const tenGoiHien = computed(() =>
  ghepTenThuongGoi(props.tenGoi !== null ? props.tenGoi : trongKho.value?.ten_thuong_goi)
)
</script>

<template>
  <template v-if="head">
    <th class="cot-ma">{{ TIEU_DE_COT.ma }}</th>
    <th class="cot-ten">{{ TIEU_DE_COT.ten }}</th>
    <th class="cot-ten-goi">{{ TIEU_DE_COT.tenGoi }}</th>
  </template>
  <template v-else>
    <td class="cot-ma"><b>{{ ma || '—' }}</b></td>
    <td class="cot-ten">
      {{ tenHien }}
      <slot />
    </td>
    <td class="cot-ten-goi">{{ tenGoiHien }}</td>
  </template>
</template>
