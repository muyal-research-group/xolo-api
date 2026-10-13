<script setup lang="ts">
import type { PlatformUser } from '~/types/platform'

const { api } = useXoloApi()
const config = useRuntimeConfig()
const current = ref<PlatformUser | null>(null)
const loading = ref(true)
const loginError = ref('')
const login = reactive({ username: '', password: '' })
const password = reactive({ current_password: '', new_password: '', confirm: '' })
const view = ref('overview')
const selectedAccount = ref<string | null>(null)
const drawer = ref(true)

const isAdmin = computed(() => current.value?.role === 'admin')
const permissions = computed(() => current.value?.permissions || [])
const can = (permission: string) => isAdmin.value || permissions.value.includes(permission)
const accountIds = computed(() => current.value?.allowed_account_ids || [])
const nav = computed(() => [
  { value: 'overview', title: 'Overview', icon: 'mdi-view-dashboard-outline', show: true },
  { value: 'accounts', title: 'Accounts', icon: 'mdi-domain', show: can('accounts.read') },
  { value: 'tenant', title: 'Tenant workspace', icon: 'mdi-account-group-outline', show: !!selectedAccount.value && ['users','api_keys','scopes','licenses'].some(x => can(`${x}.read`)) },
  { value: 'authorization', title: 'Authorization', icon: 'mdi-shield-key-outline', show: !!selectedAccount.value && ['acl','rbac','abac','ngac'].some(x => can(`${x}.read`)) },
  { value: 'platform-users', title: 'Platform users', icon: 'mdi-account-cog-outline', show: can('platform_users.read') }
].filter(item => item.show))

async function restore() {
  try {
    current.value = await api<PlatformUser>('/platform/session')
    const saved = localStorage.getItem('xolo.account')
    selectedAccount.value = saved || accountIds.value[0] || null
  } catch { current.value = null }
  finally { loading.value = false }
}
async function signIn() {
  loginError.value = ''
  try {
    const response = await api<{ user: PlatformUser; csrf_token: string }>('/platform/session', { method: 'POST', body: login })
    current.value = response.user
    selectedAccount.value = response.user.allowed_account_ids[0] || null
    login.password = ''
  } catch (cause: any) { loginError.value = cause?.data?.detail?.message || cause?.data?.detail || 'Sign in failed' }
}
async function changePassword() {
  if (password.new_password !== password.confirm) { loginError.value = 'New passwords do not match'; return }
  try {
    await api('/platform/password', { method: 'PUT', body: { current_password: password.current_password, new_password: password.new_password } })
    current.value = null; password.current_password=''; password.new_password=''; password.confirm=''
    loginError.value = 'Password changed. Sign in again.'
  } catch (cause: any) { loginError.value = cause?.data?.detail?.message || cause?.data?.detail || cause.message }
}
async function signOut() {
  try { await api('/platform/session', { method: 'DELETE' }) } finally { current.value = null; view.value = 'overview' }
}
function selectAccount(accountId: string) { selectedAccount.value = accountId; localStorage.setItem('xolo.account', accountId); view.value = 'tenant' }
function allowed(accountId: string) { return isAdmin.value || accountIds.value.includes(accountId) }

onMounted(restore)
</script>

<template>
  <v-app>
    <div v-if="loading" class="d-flex align-center justify-center" style="min-height:100vh"><v-progress-circular indeterminate color="primary" /></div>
    <div v-else-if="!current" class="xolo-login-shell d-flex align-center justify-center pa-6">
      <v-card width="440" class="xolo-card pa-3" elevation="8"><v-card-text><div class="d-flex align-center mb-8"><v-avatar color="primary" rounded="lg" size="52"><v-icon icon="mdi-shield-key" size="30" /></v-avatar><div class="ml-4"><div class="text-h4 xolo-title">Xolo</div><div class="text-medium-emphasis">Platform console</div></div></div>
        <v-alert v-if="loginError" :type="loginError.startsWith('Password changed') ? 'success' : 'error'" variant="tonal" class="mb-5">{{ loginError }}</v-alert>
        <v-form @submit.prevent="signIn"><v-text-field v-model="login.username" label="Username" autocomplete="username" prepend-inner-icon="mdi-account-outline" /><v-text-field v-model="login.password" label="Password" type="password" autocomplete="current-password" prepend-inner-icon="mdi-lock-outline" /><v-btn type="submit" color="primary" block size="large" class="mt-3">Sign in</v-btn></v-form>
      </v-card-text><v-card-subtitle class="text-center pb-4">Local administration · {{ config.public.version }}</v-card-subtitle></v-card>
    </div>
    <template v-else>
      <v-navigation-drawer v-model="drawer" width="270"><div class="pa-5 d-flex align-center"><v-avatar color="primary" rounded="lg"><v-icon icon="mdi-shield-key" /></v-avatar><div class="ml-3"><div class="text-h5 xolo-title">Xolo</div><div class="text-caption text-medium-emphasis">{{ current.role }} console</div></div></div><v-divider />
        <v-list nav class="pa-3"><v-list-item v-for="item in nav" :key="item.value" :active="view === item.value" :prepend-icon="item.icon" :title="item.title" rounded="lg" @click="view = item.value" /></v-list>
        <template #append><v-divider /><div class="pa-3"><v-list-item :title="current.username" :subtitle="selectedAccount || 'No account selected'" prepend-icon="mdi-account-circle-outline" /><v-btn variant="text" block prepend-icon="mdi-logout" @click="signOut">Sign out</v-btn></div></template>
      </v-navigation-drawer>
      <v-app-bar flat color="surface" border><v-app-bar-nav-icon @click="drawer=!drawer" /><v-app-bar-title class="text-subtitle-1">{{ selectedAccount || 'Platform' }}</v-app-bar-title><v-chip class="mr-5" color="primary" variant="tonal">{{ config.public.version }}</v-chip></v-app-bar>
      <v-main><v-container fluid class="pa-5 pa-md-8" style="max-width:1500px">
        <v-alert v-if="current.must_change_password" type="warning" variant="tonal" prominent class="mb-6" title="Change the bootstrap password">You must choose a new password before using the console.</v-alert>
        <template v-if="current.must_change_password"><v-card max-width="620" class="xolo-card"><v-card-title>Set a new password</v-card-title><v-card-text><v-alert v-if="loginError" type="error" variant="tonal" class="mb-4">{{ loginError }}</v-alert><v-text-field v-model="password.current_password" label="Current password" type="password" /><v-text-field v-model="password.new_password" label="New password" type="password" hint="At least 12 characters" /><v-text-field v-model="password.confirm" label="Confirm new password" type="password" /></v-card-text><v-card-actions><v-spacer /><v-btn color="primary" :disabled="password.new_password.length < 12" @click="changePassword">Change password</v-btn></v-card-actions></v-card></template>
        <template v-else>
          <div v-if="view === 'overview'"><h1 class="text-h4 xolo-title mb-1">Welcome, {{ current.username }}</h1><p class="text-medium-emphasis mb-7">A focused view of the Xolo platform.</p><v-row><v-col cols="12" md="4"><v-card class="xolo-card" title="Role"><v-card-text><div class="text-h5 text-capitalize">{{ current.role }}</div><div class="text-medium-emphasis">{{ isAdmin ? 'Full platform control' : `${permissions.length} permissions` }}</div></v-card-text></v-card></v-col><v-col cols="12" md="4"><v-card class="xolo-card" title="Accounts"><v-card-text><div class="text-h5">{{ isAdmin ? 'All' : accountIds.length }}</div><div class="text-medium-emphasis">{{ selectedAccount || 'Select an account' }}</div></v-card-text></v-card></v-col><v-col cols="12" md="4"><v-card class="xolo-card" title="Security"><v-card-text><div class="text-h5">Session protected</div><div class="text-medium-emphasis">HttpOnly cookie + CSRF token</div></v-card-text></v-card></v-col></v-row></div>
          <AccountsPanel v-else-if="view === 'accounts'" :selected="selectedAccount" :can-manage="can('accounts.manage')" @select="selectAccount" />
          <TenantResourcesPanel v-else-if="view === 'tenant' && selectedAccount && allowed(selectedAccount)" :account-id="selectedAccount" :permissions="permissions" :admin="isAdmin" />
          <AuthorizationPanel v-else-if="view === 'authorization' && selectedAccount && allowed(selectedAccount)" :account-id="selectedAccount" :permissions="permissions" :admin="isAdmin" />
          <PlatformUsersPanel v-else-if="view === 'platform-users'" :can-manage="can('platform_users.manage')" />
          <v-alert v-else type="info" variant="tonal">Select an allowed account first.</v-alert>
        </template>
      </v-container></v-main>
    </template>
  </v-app>
</template>
