<script setup>
import { toasts } from './toast'
</script>

<template>
  <div class="toast-host">
    <transition-group name="toast">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="'toast-' + t.type">
        <span class="toast-ic">{{ t.type === 'error' ? '⚠' : '✓' }}</span>
        <span>{{ t.message }}</span>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
/* Desktop: góc dưới-phải. Mobile (<900px): giữa dưới, phía trên bottom-nav. */
.toast-host {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-end;
  pointer-events: none;
}
.toast {
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 340px;
  padding: 12px 16px;
  border-radius: 10px;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.35;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.28);
  pointer-events: auto;
}
.toast-success { background: var(--green); }
.toast-error { background: var(--red); }
.toast-ic {
  font-weight: 800;
  font-size: 14px;
  flex-shrink: 0;
}

/* Enter/leave animation */
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
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
    /* bottom-nav cao ~66px → đẩy toast lên trên để không che */
    bottom: 78px;
    align-items: center;
  }
  .toast {
    max-width: 100%;
    width: fit-content;
  }
}
</style>
