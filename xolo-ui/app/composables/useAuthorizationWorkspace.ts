export function useAuthorizationWorkspace(accountId: () => string) {
  const { api } = useXoloApi()
  const loading = reactive<Record<string, boolean>>({})
  const errors = reactive<Record<string, string>>({})
  const notifications = useNotificationCenter()
  const path = (suffix: string) => `/accounts/${encodeURIComponent(accountId())}/${suffix}`
  const message = (cause: any) => cause?.data?.detail?.message || cause?.data?.detail || cause?.message || 'Request failed'
  const mutationOperations = new Set([
    'create', 'save', 'assign', 'delete', 'remove', 'status', 'owner',
    'membership', 'metadata', 'grant', 'transfer', 'upgrade', 'associate',
    'revoke', 'update',
  ])
  async function run<T>(operation: string, request: () => Promise<T>): Promise<T | undefined> {
    loading[operation] = true; delete errors[operation]
    try {
      const result = await request()
      const operationTokens = operation.toLowerCase().split(/[-_:]/).filter(Boolean)
      if (operationTokens.some(token => mutationOperations.has(token))) {
        notifications.record(accountId(), operation, 'Operation completed successfully', true)
      }
      return result
    } catch (cause: any) {
      errors[operation] = message(cause)
      notifications.record(accountId(), operation, errors[operation], false)
    }
    finally { loading[operation] = false }
  }
  function reset() { for (const key of Object.keys(loading)) delete loading[key]; for (const key of Object.keys(errors)) delete errors[key] }
  watch(accountId, reset)
  return { api, path, run, loading, errors, reset }
}
