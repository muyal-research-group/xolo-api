export type LocalOperationNotification = {
  notification_id: string
  category: 'operation'
  severity: 'success' | 'error'
  account_id: string
  action: string
  target: string
  safe_detail: { message: string }
  link_target?: string | null
  timestamp: string
  is_read: boolean
  local: true
}

export type SnackbarMessage = {
  id: string
  notificationId?: string
  accountId?: string
  message: string
  severity: 'success' | 'error' | 'info' | 'warning'
  linkTarget?: string | null
}

export function useNotificationCenter() {
  const userId = useState<string>('notification-user-id', () => '')
  const localItems = useState<LocalOperationNotification[]>('local-operation-notifications', () => [])
  const snackbars = useState<SnackbarMessage[]>('authorization-snackbars', () => [])

  function storageKey() { return `xolo.operations.${userId.value || 'anonymous'}` }

  function configure(nextUserId: string) {
    userId.value = nextUserId
    if (!import.meta.client) return
    try { localItems.value = JSON.parse(localStorage.getItem(storageKey()) || '[]').slice(0, 100) }
    catch { localItems.value = [] }
  }

  function persist() {
    if (!import.meta.client) return
    if (localItems.value.length) localStorage.setItem(storageKey(), JSON.stringify(localItems.value.slice(0, 100)))
    else localStorage.removeItem(storageKey())
  }

  function dismiss(id: string) { snackbars.value = snackbars.value.filter(item => item.id !== id) }

  function pushSnackbar(
    message: string,
    severity: SnackbarMessage['severity'],
    linkTarget?: string | null,
    notificationId?: string,
    accountId?: string,
  ) {
    const id = crypto.randomUUID()
    snackbars.value = [...snackbars.value.slice(-2), { id, notificationId, accountId, message, severity, linkTarget }]
    if (import.meta.client) window.setTimeout(() => dismiss(id), 3000)
  }

  function record(accountId: string, action: string, message: string, success: boolean, linkTarget?: string | null) {
    const item: LocalOperationNotification = {
      notification_id: `local-${crypto.randomUUID()}`,
      category: 'operation', severity: success ? 'success' : 'error', account_id: accountId,
      action, target: action, safe_detail: { message }, link_target: linkTarget,
      timestamp: new Date().toISOString(), is_read: false, local: true,
    }
    localItems.value = [item, ...localItems.value].slice(0, 100)
    persist()
    pushSnackbar(message, item.severity, linkTarget, item.notification_id, accountId)
  }

  function markLocalRead(id: string) {
    const item = localItems.value.find(entry => entry.notification_id === id)
    if (item) item.is_read = true
    persist()
  }

  function markAllLocalRead() { localItems.value.forEach(item => { item.is_read = true }); persist() }
  function clearLocal(accountId?: string) {
    const removedIds = new Set(
      localItems.value
        .filter(item => !accountId || item.account_id === accountId)
        .map(item => item.notification_id),
    )
    localItems.value = accountId
      ? localItems.value.filter(item => item.account_id !== accountId)
      : []
    snackbars.value = snackbars.value.filter(item => (
      !removedIds.has(item.notificationId || '') && (!accountId || item.accountId !== accountId)
    ))
    persist()
  }

  return { userId, localItems, snackbars, configure, record, dismiss, markLocalRead, markAllLocalRead, clearLocal }
}
