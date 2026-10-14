<script setup lang="ts">
const { snackbars, dismiss } = useNotificationCenter()
function open(item: any) {
  if (item.linkTarget && import.meta.client) window.dispatchEvent(new CustomEvent('xolo:notification-link', { detail: item.linkTarget }))
  dismiss(item.id)
}
</script>

<template>
  <div class="xolo-snackbar-stack" aria-live="polite">
    <TransitionGroup name="snackbar">
      <v-alert v-for="item in snackbars" :key="item.id" :type="item.severity" elevation="8" closable
        class="xolo-snackbar" @click="open(item)" @click:close.stop="dismiss(item.id)">{{ item.message }}</v-alert>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.xolo-snackbar-stack{position:fixed;right:20px;bottom:20px;z-index:3000;display:flex;flex-direction:column-reverse;gap:10px;width:min(420px,calc(100vw - 32px));pointer-events:none}.xolo-snackbar{pointer-events:auto;cursor:pointer}.snackbar-enter-active,.snackbar-leave-active{transition:all .2s ease}.snackbar-enter-from,.snackbar-leave-to{opacity:0;transform:translateY(12px)}
</style>
