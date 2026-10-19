<script setup>
import { toasts } from './toast'
import Icon from './components/Icon.vue'
</script>

<template>
  <div class="toast-host" role="status" aria-live="polite">
    <transition-group name="toast">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="'toast-' + t.type">
        <span class="toast-ic">
          <Icon :name="t.type === 'error' ? 'alert-circle' : 'check-circle'" :size="18" />
        </span>
        <span class="toast-msg">{{ t.message }}</span>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
/* Desktop: góc dưới-phải. Mobile (<900px): giữa dưới, phía trên bottom-nav.
   Nền navy (lỗi: đỏ sẫm), icon SVG — không dùng emoji. */
.toast-host {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-end;
  pointer-events: none;
}
.toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: 380px;
  padding: 12px 16px 12px 14px;
  border-radius: 12px;
  background: var(--navy);
  color: #fff;
  font-size: 13.5px;
  font-weight: 500;
  line-height: 1.45;
  box-shadow: 0 10px 30px rgba(0, 31, 61, 0.28);
  pointer-events: auto;
}
.toast-error { background: #8f1414; }
.toast-ic {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  margin-top: 1px;
}
.toast-success .toast-ic { color: #7dd3a3; }
.toast-error .toast-ic { color: #ffc9c9; }

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s var(--ease);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

@media (max-width: 900px) {
  .toast-host {
    right: 12px;
    left: 12px;
    bottom: calc(84px + env(safe-area-inset-bottom));
    align-items: center;
  }
  .toast {
    max-width: 100%;
    width: fit-content;
  }
}
</style>
