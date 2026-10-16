<script setup lang="ts">
const props = defineProps<{ accountId: string; permissions: string[]; admin: boolean }>()
const { api } = useXoloApi()
const { requestConfirmation } = useConfirmationDialog()
const tab = ref('users')
const data = reactive<Record<string, any[]>>({ users: [], keys: [], scopes: [], licenses: [] })
const error = ref('')
const busy = ref(false)
const secret = ref('')
const keyCopyState = ref<'idle' | 'copied' | 'failed'>('idle')
const dialogs = reactive({ user: false, key: false, scope: false, license: false })
const userForm = reactive({ username: '', first_name: '', last_name: '', email: '', password: '', profile_photo: '' })
const keyForm = reactive({ name: '', scopes: ['users'] as string[] })
const scopeForm = reactive({ name: '' })
const licenseForm = reactive({ username: '', scope: '', expires_in: '36500d', force: true })
const keyScopes = ref<string[]>([])

const can = (area: string, action: 'read' | 'manage') => props.admin || props.permissions.includes(`${area}.${action}`)
const base = computed(() => `/accounts/${encodeURIComponent(props.accountId)}`)

async function load(area = tab.value) {
  const paths: Record<string, string> = { users: '/users/all', keys: '/apikeys', scopes: '/scopes', licenses: '/licenses' }
  const permissionArea = area === 'keys' ? 'api_keys' : area
  if (!paths[area] || !can(permissionArea, 'read')) return
  busy.value = true; error.value = ''
  try { data[area] = await api<any[]>(base.value + paths[area]) }
  catch (cause: any) { error.value = cause?.data?.detail?.message || cause?.data?.detail || cause.message }
  finally { busy.value = false }
}

async function loadKeyScopes() {
  if (!can('api_keys', 'manage')) return
  try { keyScopes.value = await api<string[]>(base.value + '/apikeys/scopes') }
  catch (cause: any) { error.value = cause?.data?.detail?.message || cause?.data?.detail || cause.message }
}

async function createUser() { await api(base.value + '/users', { method: 'POST', body: userForm }); dialogs.user = false; await load('users') }
async function createKey() {
  const result = await api<any>(base.value + '/apikeys', { method: 'POST', body: keyForm })
  secret.value = result.key; keyCopyState.value = 'idle'; dialogs.key = false; await load('keys')
}
async function copyKey() {
  if (!secret.value) return
  try {
    await navigator.clipboard.writeText(secret.value)
    keyCopyState.value = 'copied'
  } catch {
    keyCopyState.value = 'failed'
  }
}
async function createScope() { await api(base.value + '/scopes', { method: 'POST', body: scopeForm }); dialogs.scope = false; scopeForm.name = ''; await load('scopes') }
async function createLicense() { await api(base.value + '/licenses', { method: 'POST', body: licenseForm }); dialogs.license = false; await load('licenses') }
async function removeUser(username: string) { const confirmed=await requestConfirmation({title:'Delete tenant user?',message:`Permanently delete ${username} and clean up their authorization data?`,confirmText:'Delete user'});if(!confirmed)return;await api(base.value + `/users/${encodeURIComponent(username)}`, { method: 'DELETE' });await load('users') }
async function toggleUser(username: string, disabled: boolean) { await api(base.value + `/users/${encodeURIComponent(username)}/${disabled ? 'unblock' : 'block'}`, { method: 'POST' }); await load('users') }
async function revokeKey(item: any) { const confirmed=await requestConfirmation({title:'Revoke API key?',message:`Permanently revoke ${item.name || item.key_prefix}? Existing clients using this key will lose access.`,confirmText:'Revoke key'});if(!confirmed)return;await api(base.value + `/apikeys/${item.key_id}`, { method: 'DELETE' });await load('keys') }
async function deleteKey(item: any) { const confirmed=await requestConfirmation({title:'Delete API key permanently?',message:`Permanently delete ${item.name || item.key_prefix} and its metadata? This also invalidates an active key and cannot be undone.`,confirmText:'Delete key'});if(!confirmed)return;await api(base.value + `/apikeys/${encodeURIComponent(item.key_id)}/permanent`, { method: 'DELETE' });await load('keys') }
async function rotateKey(id: string) { const result = await api<any>(base.value + `/apikeys/${id}/rotate`, { method: 'POST' }); secret.value = result.key; keyCopyState.value = 'idle'; await load('keys') }
async function removeScope(name: string) { const confirmed=await requestConfirmation({title:'Delete scope?',message:`Permanently delete the ${name} scope?`,confirmText:'Delete scope'});if(!confirmed)return;await api(base.value + '/scopes', { method: 'DELETE', body: { name } });await load('scopes') }

watch(tab, area => { load(area); if (area === 'keys') loadKeyScopes() })
watch(() => props.accountId, () => { keyScopes.value = []; secret.value = ''; keyCopyState.value = 'idle'; dialogs.key = false; load(tab.value); loadKeyScopes() })
onMounted(() => { load(); loadKeyScopes() })
</script>

<template>
  <div><div class="mb-5"><h1 class="text-h4 xolo-title">Tenant workspace</h1><p class="text-medium-emphasis">Account <span class="xolo-mono">{{ accountId }}</span></p></div>
    <v-alert v-if="secret" type="warning" variant="tonal" closable class="mb-4" @click:close="secret = ''"><strong>Copy this key now. It is shown once.</strong><div class="xolo-mono xolo-wrap mt-2">{{ secret }}</div><v-btn class="mt-3" size="small" variant="outlined" :prepend-icon="keyCopyState === 'copied' ? 'mdi-check' : 'mdi-content-copy'" @click="copyKey">{{ keyCopyState === 'copied' ? 'Copied' : 'Copy key' }}</v-btn><div v-if="keyCopyState === 'failed'" class="mt-2">Could not copy automatically. Select and copy the key above.</div></v-alert>
    <v-alert v-if="error" type="error" variant="tonal" closable class="mb-4" @click:close="error = ''">{{ error }}</v-alert>
    <v-card class="xolo-card"><v-tabs v-model="tab" color="primary"><v-tab value="users">Users</v-tab><v-tab value="keys">API keys</v-tab><v-tab value="scopes">Scopes</v-tab><v-tab value="licenses">Licenses</v-tab></v-tabs>
      <v-divider /><v-window v-model="tab"><v-window-item value="users"><v-card-text><div class="d-flex mb-3"><v-spacer /><v-btn v-if="can('users','manage')" color="primary" size="small" prepend-icon="mdi-plus" @click="dialogs.user = true">Add user</v-btn></div><v-table><thead><tr><th>User</th><th>Name</th><th>Email</th><th>Status</th><th /></tr></thead><tbody><tr v-for="item in data.users" :key="item.key"><td>{{ item.username }}</td><td>{{ item.first_name }} {{ item.last_name }}</td><td>{{ item.email }}</td><td><v-chip size="small" :color="item.disabled ? 'error' : 'success'">{{ item.disabled ? 'Blocked' : 'Active' }}</v-chip></td><td class="text-right"><template v-if="can('users','manage')"><v-btn size="small" variant="text" @click="toggleUser(item.username,item.disabled)">{{ item.disabled ? 'Unblock' : 'Block' }}</v-btn><v-btn icon="mdi-delete-outline" color="error" size="small" variant="text" @click="removeUser(item.username)" /></template></td></tr></tbody></v-table></v-card-text></v-window-item>
        <v-window-item value="keys"><v-card-text><div class="d-flex mb-3"><v-spacer /><v-btn v-if="can('api_keys','manage')" color="primary" size="small" prepend-icon="mdi-key-plus" @click="dialogs.key = true">Create key</v-btn></div><v-table><thead><tr><th>Name</th><th>Prefix</th><th>Scopes</th><th>Status</th><th /></tr></thead><tbody><tr v-for="item in data.keys" :key="item.key_id"><td>{{ item.name }}</td><td class="xolo-mono">{{ item.key_prefix }}</td><td>{{ item.scopes.join(', ') }}</td><td>{{ item.is_active ? 'Active' : 'Revoked' }}</td><td class="text-right"><template v-if="can('api_keys','manage')"><v-btn v-if="item.is_active" size="small" variant="text" @click="rotateKey(item.key_id)">Rotate</v-btn><v-btn v-if="item.is_active" size="small" color="error" variant="text" @click="revokeKey(item)">Revoke</v-btn><v-btn size="small" color="error" variant="text" @click="deleteKey(item)">Delete</v-btn></template></td></tr></tbody></v-table></v-card-text></v-window-item>
        <v-window-item value="scopes"><v-card-text><div class="d-flex mb-3"><v-spacer /><v-btn v-if="can('scopes','manage')" color="primary" size="small" prepend-icon="mdi-plus" @click="dialogs.scope = true">Add scope</v-btn></div><v-list><v-list-item v-for="item in data.scopes" :key="item.name" :title="item.name"><template #append><v-btn v-if="can('scopes','manage')" icon="mdi-delete-outline" color="error" variant="text" @click="removeScope(item.name)" /></template></v-list-item></v-list></v-card-text></v-window-item>
        <v-window-item value="licenses"><v-card-text><div class="d-flex mb-3"><v-spacer /><v-btn v-if="can('licenses','manage')" color="primary" size="small" prepend-icon="mdi-plus" @click="dialogs.license = true">Assign license</v-btn></div><v-table><thead><tr><th>User</th><th>Scope</th><th>Expires</th></tr></thead><tbody><tr v-for="(item,index) in data.licenses" :key="index"><td>{{ item.username }}</td><td>{{ item.scope }}</td><td>{{ item.expires_at }}</td></tr></tbody></v-table></v-card-text></v-window-item></v-window>
      <v-progress-linear v-if="busy" indeterminate color="primary" />
    </v-card>

    <v-dialog v-model="dialogs.user" max-width="650"><v-card title="Create tenant user"><v-card-text><v-row><v-col cols="12" md="6"><v-text-field v-model="userForm.username" label="Username" /></v-col><v-col cols="12" md="6"><v-text-field v-model="userForm.email" label="Email" /></v-col><v-col cols="12" md="6"><v-text-field v-model="userForm.first_name" label="First name" /></v-col><v-col cols="12" md="6"><v-text-field v-model="userForm.last_name" label="Last name" /></v-col><v-col cols="12"><v-text-field v-model="userForm.password" type="password" label="Password" /></v-col></v-row></v-card-text><v-card-actions><v-spacer /><v-btn @click="dialogs.user=false">Cancel</v-btn><v-btn color="primary" @click="createUser">Create</v-btn></v-card-actions></v-card></v-dialog>
    <v-dialog v-model="dialogs.key" max-width="560"><v-card title="Create API key"><v-card-text><v-text-field v-model="keyForm.name" label="Name" /><v-select v-model="keyForm.scopes" :items="keyScopes" multiple chips label="Scopes" hint="Service operations require service plus their feature scope; all does not include service." persistent-hint /></v-card-text><v-card-actions><v-spacer /><v-btn @click="dialogs.key=false">Cancel</v-btn><v-btn color="primary" :disabled="!keyForm.name.trim() || !keyForm.scopes.length || !keyScopes.length" @click="createKey">Create</v-btn></v-card-actions></v-card></v-dialog>
    <v-dialog v-model="dialogs.scope" max-width="480"><v-card title="Create scope"><v-card-text><v-text-field v-model="scopeForm.name" label="Scope name" /></v-card-text><v-card-actions><v-spacer /><v-btn @click="dialogs.scope=false">Cancel</v-btn><v-btn color="primary" @click="createScope">Create</v-btn></v-card-actions></v-card></v-dialog>
    <v-dialog v-model="dialogs.license" max-width="560"><v-card title="Assign license"><v-card-text><v-text-field v-model="licenseForm.username" label="Username" /><v-text-field v-model="licenseForm.scope" label="Scope" /><v-text-field v-model="licenseForm.expires_in" label="Expires in" hint="Example: 36500d" /></v-card-text><v-card-actions><v-spacer /><v-btn @click="dialogs.license=false">Cancel</v-btn><v-btn color="primary" @click="createLicense">Assign</v-btn></v-card-actions></v-card></v-dialog>
  </div>
</template>
