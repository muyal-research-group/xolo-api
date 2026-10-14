<script setup lang="ts">
import type { Account, PlatformOptions, PlatformRole, PlatformUser } from '~/types/platform'

defineProps<{ canManage: boolean }>()
const { api } = useXoloApi()
const { requestConfirmation } = useConfirmationDialog()
const users = ref<PlatformUser[]>([])
const accounts = ref<Account[]>([])
const options = ref<PlatformOptions>({ roles: ['admin', 'user', 'guest'], permissions: [] })
const dialog = ref(false)
const editing = ref<PlatformUser | null>(null)
const error = ref('')
const form = reactive({ username: '', password: '', role: 'user' as PlatformRole, permissions: [] as string[], allowed_account_ids: [] as string[] })

async function load() {
  error.value = ''
  try {
    [users.value, options.value, accounts.value] = await Promise.all([
      api<PlatformUser[]>('/platform/users'), api<PlatformOptions>('/platform/options'), api<Account[]>('/accounts')
    ])
  } catch (cause: any) { error.value = cause?.data?.detail?.message || cause?.data?.detail || cause.message }
}
function openCreate() {
  editing.value = null
  form.username = ''; form.password = ''; form.role = 'user'; form.permissions = []; form.allowed_account_ids = []
  dialog.value = true
}
function openEdit(user: PlatformUser) {
  editing.value = user
  form.username = user.username; form.password = ''; form.role = user.role
  form.permissions = [...user.permissions]; form.allowed_account_ids = [...user.allowed_account_ids]
  dialog.value = true
}
async function save() {
  if (editing.value) {
    await api(`/platform/users/${editing.value.user_id}`, {
      method: 'PATCH',
      body: { role: form.role, permissions: form.permissions, allowed_account_ids: form.allowed_account_ids }
    })
  } else {
    await api('/platform/users', { method: 'POST', body: { ...form, must_change_password: true } })
  }
  dialog.value = false; form.username = ''; form.password = ''; form.permissions = []; form.allowed_account_ids = []
  await load()
}
async function toggle(user: PlatformUser) {
  await api(`/platform/users/${user.user_id}`, { method: 'PATCH', body: { is_active: !user.is_active } }); await load()
}
async function remove(user: PlatformUser) {
  const confirmed = await requestConfirmation({
    title: 'Delete platform user?',
    message: `Permanently delete ${user.username} and remove their console access?`,
    confirmText: 'Delete user',
  })
  if (!confirmed) return
  await api(`/platform/users/${user.user_id}`, { method: 'DELETE' }); await load()
}
watch(() => form.role, role => { if (role === 'guest') form.permissions = form.permissions.filter(p => p.endsWith('.read')) })
onMounted(load)
</script>

<template>
  <div><div class="d-flex align-center mb-5"><div><h1 class="text-h4 xolo-title">Platform users</h1><p class="text-medium-emphasis">Console access is separate from tenant identities and API keys.</p></div><v-spacer /><v-btn v-if="canManage" color="primary" prepend-icon="mdi-account-plus" @click="openCreate">Add user</v-btn></div>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4" @click:close="error = ''">{{ error }}</v-alert>
    <v-card class="xolo-card"><v-table><thead><tr><th>User</th><th>Role</th><th>Accounts</th><th>Permissions</th><th>Status</th><th /></tr></thead><tbody><tr v-for="user in users" :key="user.user_id"><td><strong>{{ user.username }}</strong><div v-if="user.must_change_password" class="text-caption text-warning">Password change required</div></td><td><v-chip size="small">{{ user.role }}</v-chip></td><td>{{ user.role === 'admin' ? 'All' : user.allowed_account_ids.join(', ') || 'None' }}</td><td>{{ user.role === 'admin' ? 'All' : `${user.permissions.length} assigned` }}</td><td><v-chip size="small" :color="user.is_active ? 'success' : 'error'">{{ user.is_active ? 'Active' : 'Disabled' }}</v-chip></td><td class="text-right"><v-btn v-if="canManage" icon="mdi-pencil-outline" size="small" variant="text" @click="openEdit(user)" /><v-btn v-if="canManage" size="small" variant="text" @click="toggle(user)">{{ user.is_active ? 'Disable' : 'Enable' }}</v-btn><v-btn v-if="canManage" icon="mdi-delete-outline" color="error" variant="text" size="small" @click="remove(user)" /></td></tr></tbody></v-table></v-card>
    <v-dialog v-model="dialog" max-width="680"><v-card :title="editing ? `Edit ${editing.username}` : 'Add platform user'"><v-card-text><v-row><v-col cols="12" md="6"><v-text-field v-model="form.username" label="Username" :disabled="!!editing" /></v-col><v-col v-if="!editing" cols="12" md="6"><v-text-field v-model="form.password" label="Temporary password" type="password" hint="At least 12 characters" /></v-col><v-col cols="12"><v-select v-model="form.role" :items="options.roles" label="Role" /></v-col><v-col v-if="form.role !== 'admin'" cols="12"><v-select v-model="form.allowed_account_ids" :items="accounts" item-title="name" item-value="account_id" multiple chips label="Allowed accounts" /><v-select v-model="form.permissions" :items="options.permissions.filter(p => form.role !== 'guest' || p.endsWith('.read'))" multiple chips label="Permissions" /></v-col></v-row></v-card-text><v-card-actions><v-spacer /><v-btn @click="dialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!form.username || (!editing && form.password.length < 12)" @click="save">{{ editing ? 'Save' : 'Create' }}</v-btn></v-card-actions></v-card></v-dialog>
  </div>
</template>
