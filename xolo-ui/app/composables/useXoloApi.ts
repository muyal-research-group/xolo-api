import type { FetchOptions } from 'ofetch'

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1'])

export function resolveApiBase(configuredBase: string, browserHostname?: string): string {
  if (!browserHostname || !LOOPBACK_HOSTS.has(browserHostname)) return configuredBase

  try {
    const url = new URL(configuredBase)
    if (!LOOPBACK_HOSTS.has(url.hostname)) return configuredBase
    url.hostname = browserHostname
    return url.toString().replace(/\/$/, '')
  } catch {
    return configuredBase
  }
}

export function useXoloApi() {
  const config = useRuntimeConfig()
  const csrf = useCookie<string | null>('xolo_platform_csrf')

  async function api<T>(path: string, options: FetchOptions<'json'> = {}): Promise<T> {
    const method = String(options.method || 'GET').toUpperCase()
    const headers = new Headers(options.headers as HeadersInit | undefined)
    const baseURL = resolveApiBase(
      config.public.apiBase,
      import.meta.client ? window.location.hostname : undefined
    )
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrf.value) {
      headers.set('X-CSRF-Token', csrf.value)
    }
    return await $fetch<T>(path, {
      baseURL,
      credentials: 'include',
      ...options,
      headers
    })
  }

  return { api, csrf }
}
