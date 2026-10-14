<script setup lang="ts">
const props = defineProps<{ accountId: string }>()
const { api } = useXoloApi()
const { localItems, markLocalRead, markAllLocalRead, clearLocal } = useNotificationCenter()
const open = ref(false), serverItems = ref<any[]>([]), unreadCount = ref(0), unreadOnly = ref(false), category = ref('all')
const categories = ['all', 'membership', 'access', 'policy', 'security', 'operation']
let poller: ReturnType<typeof setInterval> | undefined
const accountLocalCount = computed(() => localItems.value.filter(item => item.account_id === props.accountId).length)
const visibleLocal = computed(() => localItems.value.filter(item => item.account_id === props.accountId && (category.value === 'all' || category.value === 'operation') && (!unreadOnly.value || !item.is_read)))
const merged = computed(() => [...serverItems.value, ...visibleLocal.value].sort((a,b) => Date.parse(b.timestamp)-Date.parse(a.timestamp)))
const totalUnread = computed(() => unreadCount.value + localItems.value.filter(item => item.account_id === props.accountId && !item.is_read).length)

async function load() {
  if (!props.accountId || (import.meta.client && document.hidden)) return
  const params = new URLSearchParams(); if (category.value !== 'all' && category.value !== 'operation') params.append('category', category.value); if (unreadOnly.value) params.set('unread_only', 'true')
  try {
    const [page, count]: any[] = await Promise.all([
      category.value === 'operation' ? Promise.resolve({ items: [] }) : api(`/accounts/${encodeURIComponent(props.accountId)}/notifications?${params}`),
      api(`/accounts/${encodeURIComponent(props.accountId)}/notifications/unread-count`),
    ])
    serverItems.value = page.items || []; unreadCount.value = count.count || 0
  } catch { serverItems.value = [] }
}
async function mark(item: any) {
  if (item.local) markLocalRead(item.notification_id)
  else if (!item.is_read) { await api(`/accounts/${encodeURIComponent(props.accountId)}/notifications/${item.notification_id}/read`, { method: 'POST' }); item.is_read = true; unreadCount.value = Math.max(0, unreadCount.value - 1) }
  if (item.link_target && import.meta.client) window.dispatchEvent(new CustomEvent('xolo:notification-link', { detail: item.link_target }))
}
async function markAll() { await api(`/accounts/${encodeURIComponent(props.accountId)}/notifications/read-all`, { method: 'POST' }); markAllLocalRead(); await load() }
function clearLocalHistory() { clearLocal(props.accountId) }
function clearPoller() { if (poller) clearInterval(poller); poller = undefined }
function schedule() {
  clearPoller()
  if (!props.accountId || document.hidden) return
  load()
  poller = setInterval(load, 20000)
}
function focus() { if (!document.hidden) load() }
function visibility() { schedule() }
function start() {
  stop()
  if (!import.meta.client) return
  window.addEventListener('focus', focus)
  document.addEventListener('visibilitychange', visibility)
  schedule()
}
function stop() {
  clearPoller()
  if (import.meta.client) {
    window.removeEventListener('focus', focus)
    document.removeEventListener('visibilitychange', visibility)
  }
}
watch(() => props.accountId, start)
watch([category, unreadOnly], load)
onMounted(start); onBeforeUnmount(stop)
</script>

<template>
  <v-menu v-model="open" :close-on-content-click="false" location="bottom end">
    <template #activator="{ props: menuProps }"><v-btn v-bind="menuProps" icon aria-label="Notifications"><v-badge :model-value="totalUnread > 0" :content="totalUnread" color="error" floating><v-icon icon="mdi-bell-outline" /></v-badge></v-btn></template>
    <v-card width="440" max-width="calc(100vw - 24px)"><v-card-title class="d-flex align-center">Notifications<v-spacer/><v-btn size="small" variant="text" @click="markAll">Mark all read</v-btn></v-card-title><v-card-text class="pb-2"><div class="d-flex ga-2"><v-select v-model="category" :items="categories" density="compact" hide-details label="Category"/><v-switch v-model="unreadOnly" density="compact" hide-details label="Unread"/></div></v-card-text><v-divider/><v-list max-height="520" class="overflow-y-auto"><v-list-item v-for="item in merged" :key="item.notification_id" :title="item.safe_detail?.message || item.action" :subtitle="new Date(item.timestamp).toLocaleString()" :class="{ 'font-weight-bold': !item.is_read }" @click="mark(item)"><template #prepend><v-icon :color="item.severity === 'error' ? 'error' : item.severity === 'warning' ? 'warning' : 'primary'" :icon="item.local ? 'mdi-console' : 'mdi-shield-outline'"/></template></v-list-item><v-list-item v-if="!merged.length" title="No notifications"/></v-list><v-divider/><v-card-actions><v-btn variant="text" size="small" :disabled="accountLocalCount === 0" @click="clearLocalHistory">Clear local history</v-btn><v-spacer/><v-btn variant="text" @click="open=false">Close</v-btn></v-card-actions></v-card>
  </v-menu>
</template>
