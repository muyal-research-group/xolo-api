<script setup lang="ts">
const props = defineProps<{ accountId: string; permissions: string[]; admin: boolean }>()
const { api } = useXoloApi()

type Area = 'rbac' | 'acl' | 'abac' | 'ngac'

const tab = ref<Area>('rbac')
const items = ref<any[]>([])
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const checkResult = ref<boolean | null>(null)
const editDialog = ref(false)
const editing = ref<any>(null)
const principals = ref<any[]>([])
const groups = ref<any[]>([])
const grants = ref<any[]>([])
const groupMembers = ref<any[]>([])
const selectedResource = ref('')
const selectedGroup = ref('')
const aclView = ref<'resources' | 'groups'>('resources')
const validationResult = ref<any>(null)

const roleForm = reactive({ name: '', description: '', permissions: '' })
const abacForm = reactive({ name: '', effect: 'ALLOW', subject: '*', resource: '*', action: 'read' })
const ngacForm = reactive({ name: '', node_type: 'user_attribute', properties: '{}' })
const aclForm = reactive({ resource_id: '', principal: '', permissions: ['read'] as string[] })
const checkForm = reactive({ resource_id: '', principal: '', permissions: ['read'] as string[] })
const groupForm = reactive({ name: '', description: '' })
const memberForm = reactive({ username: '' })
const rbacCheck = reactive({ subject_id: '', permission: 'read' })
const abacCheck = reactive({ subject: '', resource: '', action: 'read' })
const ngacCheck = reactive({ user_id: '', object_id: '', operation: 'read' })
const editForm = reactive({ name: '', description: '', permissions: '', effect: 'ALLOW', subject: '*', resource: '*', action: 'read', properties: '{}' })

const permissionChoices = ['read', 'write', 'update', 'delete', 'sys:manage']
const nodeTypes = [
  { title: 'User', value: 'user' },
  { title: 'User attribute', value: 'user_attribute' },
  { title: 'Object', value: 'object' },
  { title: 'Object attribute', value: 'object_attribute' },
  { title: 'Policy class', value: 'policy_class' }
]
const paths: Record<Area, string> = {
  rbac: '/rbac/roles',
  acl: '/acl/resources',
  abac: '/abac/policies',
  ngac: '/ngac/nodes'
}
const guides: Record<Area, { icon: string; title: string; summary: string; use: string }> = {
  rbac: { icon: 'mdi-account-badge-outline', title: 'Role-based access', summary: 'Bundle permissions into roles, then assign roles to users or groups.', use: 'Best when people with the same job need the same access.' },
  acl: { icon: 'mdi-format-list-checks', title: 'Access-control lists', summary: 'Claim a resource and grant explicit permissions to a user or group.', use: 'Best for sharing one specific resource with named principals.' },
  abac: { icon: 'mdi-tune-variant', title: 'Attribute-based access', summary: 'Allow or deny an action when subject, resource, location, and time attributes match.', use: 'Best for contextual rules such as “edit invoices during office hours”.' },
  ngac: { icon: 'mdi-graph-outline', title: 'Graph-based access', summary: 'Model users, objects, attributes, and policy classes as a relationship graph.', use: 'Best for deep hierarchies and policies inherited through relationships.' }
}

const can = (area: Area, action: 'read' | 'manage') => props.admin || props.permissions.includes(`${area}.${action}`)
const base = computed(() => `/accounts/${encodeURIComponent(props.accountId)}`)
const principalItems = computed(() => principals.value.map(item => ({
  title: `${item.type === 'USER' ? 'User' : 'Group'} · ${item.label || item.name}`,
  value: `${item.type}:${item.type === 'USER' ? item.name : item.id}`,
  raw: item
})))
const userItems = computed(() => principals.value.filter(item => item.type === 'USER').map(item => ({ title: item.label || item.name, value: item.name })))
const rbacUserItems = computed(() => principals.value.filter(item => item.type === 'USER').map(item => ({ title: item.label || item.name, value: item.id })))
const ngacUsers = computed(() => items.value.filter(item => item.node_type === 'user').map(item => ({ title: item.name, value: item.node_id })))
const ngacObjects = computed(() => items.value.filter(item => item.node_type === 'object').map(item => ({ title: item.name, value: item.node_id })))
const selectedGroupOwner = computed(() => groups.value.find(group => group.id === selectedGroup.value)?.owner_id || '')

function messageFrom(cause: any) {
  const detail = cause?.data?.detail
  return detail?.message || detail?.raw_detail || (typeof detail === 'string' ? detail : '') || cause?.message || 'The request failed.'
}

function permissionsFrom(value: string) {
  return [...new Set(value.split(',').map(item => item.trim()).filter(Boolean))]
}

function parseProperties(value: string) {
  const parsed = JSON.parse(value || '{}')
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('Properties must be a JSON object.')
  return parsed
}

function abacEventPayload(event: any, overrides: Record<string, string> = {}) {
  const center = event?.location?.center
  return {
    subject: overrides.subject ?? event?.subject?.value ?? '*',
    resource: overrides.resource ?? event?.resource?.value ?? '*',
    action: overrides.action ?? event?.action?.value ?? '*',
    location: center ? { lat: center.lat, lng: center.lng, radius_km: event.location.radius_km } : null,
    time_mode: event?.time?.mode || 'wildcard',
    time_start: event?.time?.start || null,
    time_end: event?.time?.end || null
  }
}

async function run(action: () => Promise<void>, success: string) {
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    await action()
    notice.value = success
    await load()
  } catch (cause: any) {
    error.value = messageFrom(cause)
  } finally {
    busy.value = false
  }
}

function selectedPrincipal(value: string) {
  const separator = value.indexOf(':')
  return separator < 0 ? null : { type: value.slice(0, separator), value: value.slice(separator + 1) }
}

function memberTitle(member: any) {
  if (member.user_id === selectedGroupOwner.value && member.username === member.user_id) return 'Platform administrator'
  return member.username
}

async function loadAclSupport() {
  const [principalResponse, groupResponse] = await Promise.all([
    api<any[]>(base.value + '/acl/principals/list'),
    api<any[]>(base.value + '/acl/groups/list')
  ])
  principals.value = principalResponse
  groups.value = groupResponse
}

async function load() {
  error.value = ''
  items.value = []
  if (!can(tab.value, 'read')) return
  loading.value = true
  try {
    const response: any = await api(base.value + paths[tab.value])
    items.value = Array.isArray(response)
      ? response
      : [
          ...(response.owned_resources?.items || []).map((item: any) => ({ ...item, ownership: 'Owned' })),
          ...(response.shared_resources?.items || []).map((item: any) => ({ ...item, ownership: 'Shared' }))
        ]
    if (tab.value === 'acl') await loadAclSupport()
    if (tab.value === 'rbac' && (props.admin || props.permissions.includes('users.read'))) {
      const users = await api<any[]>(base.value + '/users/list')
      principals.value = users.map(user => ({ id: user.key, name: user.username, type: 'USER', label: `${user.username} (${user.first_name} ${user.last_name})` }))
    }
  } catch (cause: any) {
    error.value = messageFrom(cause)
  } finally {
    loading.value = false
  }
}

async function createRole() {
  await run(async () => {
    await api(base.value + '/rbac/roles', {
      method: 'POST',
      body: { name: roleForm.name.trim(), description: roleForm.description.trim() || null, permissions: permissionsFrom(roleForm.permissions) }
    })
    Object.assign(roleForm, { name: '', description: '', permissions: '' })
  }, 'Role created.')
}

async function createAbacPolicy() {
  await run(async () => {
    await api(base.value + '/abac/policies', {
      method: 'POST',
      body: {
        name: abacForm.name.trim(), effect: abacForm.effect,
        events: [{ subject: abacForm.subject || '*', resource: abacForm.resource || '*', action: abacForm.action || '*', time_mode: 'wildcard' }]
      }
    })
    Object.assign(abacForm, { name: '', effect: 'ALLOW', subject: '*', resource: '*', action: 'read' })
  }, 'ABAC policy created.')
}

async function createNgacNode() {
  await run(async () => {
    await api(base.value + '/ngac/nodes', {
      method: 'POST',
      body: { name: ngacForm.name.trim(), node_type: ngacForm.node_type, properties: parseProperties(ngacForm.properties) }
    })
    Object.assign(ngacForm, { name: '', node_type: 'user_attribute', properties: '{}' })
  }, 'NGAC node created.')
}

async function claimResource() {
  await run(async () => {
    await api(base.value + '/acl/claim', { method: 'POST', body: { resource_id: aclForm.resource_id.trim() } })
  }, 'Resource claimed. You are now its owner.')
}

async function changeGrant(mode: 'grant' | 'revoke') {
  const principal = selectedPrincipal(aclForm.principal)
  if (!principal) return
  await run(async () => {
    await api(base.value + `/acl/${mode}`, {
      method: mode === 'grant' ? 'POST' : 'DELETE',
      body: {
        resource_id: aclForm.resource_id.trim(),
        principal_id: principal.type === 'GROUP' ? principal.value : null,
        principal_username: principal.type === 'USER' ? principal.value : null,
        principal_type: principal.type,
        permissions: aclForm.permissions
      }
    })
  }, mode === 'grant' ? 'Access granted.' : 'Access revoked.')
  await loadGrants(aclForm.resource_id)
}

async function checkAccess() {
  error.value = ''
  checkResult.value = null
  busy.value = true
  try {
    const principal = selectedPrincipal(checkForm.principal)
    const response: any = await api(base.value + '/acl/check', {
      method: 'POST',
      body: {
        resource_id: checkForm.resource_id.trim(),
        principal_id: principal?.type === 'GROUP' ? principal.value : null,
        principal_username: principal?.type === 'USER' ? principal.value : null,
        principal_type: principal?.type || null,
        permissions: checkForm.permissions
      }
    })
    checkResult.value = Boolean(response.has_permission)
  } catch (cause: any) {
    error.value = messageFrom(cause)
  } finally {
    busy.value = false
  }
}

async function loadGrants(resourceId: string) {
  selectedResource.value = resourceId
  aclForm.resource_id = resourceId
  grants.value = []
  try {
    const response: any = await api(base.value + `/acl/resources/${encodeURIComponent(resourceId)}/grants`)
    grants.value = response.grants || []
  } catch (cause: any) {
    error.value = messageFrom(cause)
  }
}

async function revokeGrant(grant: any) {
  await run(async () => {
    await api(base.value + '/acl/revoke', {
      method: 'DELETE',
      body: {
        resource_id: selectedResource.value,
        principal_id: grant.principal_id,
        principal_type: grant.principal_type,
        permissions: grant.permissions
      }
    })
  }, `Access revoked from ${grant.principal_name}.`)
  await loadGrants(selectedResource.value)
}

async function createGroup() {
  await run(async () => {
    await api(base.value + '/acl/groups', { method: 'POST', body: { name: groupForm.name.trim(), description: groupForm.description.trim() } })
    Object.assign(groupForm, { name: '', description: '' })
  }, 'Group created.')
}

async function removeGroup(group: any) {
  if (!window.confirm(`Delete group “${group.name}”?`)) return
  await run(async () => {
    await api(base.value + `/acl/groups/${encodeURIComponent(group.id)}`, { method: 'DELETE' })
    if (selectedGroup.value === group.id) { selectedGroup.value = ''; groupMembers.value = [] }
  }, 'Group deleted.')
}

async function loadMembers(groupId: string) {
  selectedGroup.value = groupId
  try {
    groupMembers.value = await api<any[]>(base.value + `/acl/groups/${encodeURIComponent(groupId)}/members`)
  } catch (cause: any) {
    error.value = messageFrom(cause)
  }
}

async function changeMember(mode: 'add' | 'remove', username = memberForm.username) {
  if (!selectedGroup.value || !username) return
  await run(async () => {
    await api(base.value + `/acl/groups/${encodeURIComponent(selectedGroup.value)}/members`, {
      method: mode === 'add' ? 'POST' : 'DELETE',
      body: { usernames: [username] }
    })
    memberForm.username = ''
  }, mode === 'add' ? 'Member added.' : 'Member removed.')
  await loadMembers(selectedGroup.value)
}

async function validatePermission() {
  error.value = ''
  validationResult.value = null
  busy.value = true
  try {
    if (tab.value === 'rbac') {
      validationResult.value = await api(base.value + '/rbac/check', { method: 'POST', body: rbacCheck })
    } else if (tab.value === 'abac') {
      validationResult.value = await api(base.value + '/abac/evaluate', { method: 'POST', body: abacCheck })
    } else if (tab.value === 'ngac') {
      validationResult.value = await api(base.value + '/ngac/check', { method: 'POST', body: ngacCheck })
    }
  } catch (cause: any) {
    error.value = messageFrom(cause)
  } finally {
    busy.value = false
  }
}

function validationAllowed() {
  return Boolean(validationResult.value?.has_access ?? validationResult.value?.allowed)
}

function openEdit(item: any) {
  editing.value = item
  const event = item.events?.[0]
  Object.assign(editForm, {
    name: item.name || '',
    description: item.description || '',
    permissions: (item.permissions || []).join(', '),
    effect: item.effect || 'ALLOW',
    subject: event?.subject?.value || '*',
    resource: event?.resource?.value || '*',
    action: event?.action?.value || 'read',
    properties: JSON.stringify(item.properties || {}, null, 2)
  })
  editDialog.value = true
}

async function saveEdit() {
  const item = editing.value
  if (!item) return
  await run(async () => {
    if (tab.value === 'rbac') {
      await api(base.value + `/rbac/roles/${encodeURIComponent(item.role_id)}`, {
        method: 'PATCH', body: { name: editForm.name.trim(), description: editForm.description.trim() || null }
      })
      const before = new Set<string>(item.permissions || [])
      const after = new Set<string>(permissionsFrom(editForm.permissions))
      for (const permission of after) {
        if (!before.has(permission)) await api(base.value + `/rbac/roles/${encodeURIComponent(item.role_id)}/permissions`, { method: 'POST', body: { permission } })
      }
      for (const permission of before) {
        if (!after.has(permission)) await api(base.value + `/rbac/roles/${encodeURIComponent(item.role_id)}/permissions`, { method: 'DELETE', body: { permission } })
      }
    } else if (tab.value === 'abac') {
      const existingEvents = item.events || []
      const events = existingEvents.length
        ? existingEvents.map((event: any, index: number) => abacEventPayload(event, index === 0 ? {
            subject: editForm.subject || '*',
            resource: editForm.resource || '*',
            action: editForm.action || '*'
          } : {}))
        : [{ subject: editForm.subject || '*', resource: editForm.resource || '*', action: editForm.action || '*', time_mode: 'wildcard' }]
      await api(base.value + `/abac/policies/${encodeURIComponent(item.policy_id)}`, {
        method: 'PUT',
        body: { name: editForm.name.trim(), effect: editForm.effect, events }
      })
    } else if (tab.value === 'ngac') {
      await api(base.value + `/ngac/nodes/${encodeURIComponent(item.node_id)}`, {
        method: 'PATCH', body: { name: editForm.name.trim(), properties: parseProperties(editForm.properties) }
      })
    }
    editDialog.value = false
  }, `${guides[tab.value].title} item updated.`)
}

async function removeItem(item: any) {
  const id = item.role_id || item.policy_id || item.node_id
  const label = item.name || id
  if (!window.confirm(`Delete “${label}”? This cannot be undone.`)) return
  const resource = tab.value === 'rbac' ? 'roles' : tab.value === 'abac' ? 'policies' : 'nodes'
  await run(async () => {
    await api(base.value + `/${tab.value}/${resource}/${encodeURIComponent(id)}`, { method: 'DELETE' })
  }, `${label} deleted.`)
}

function subtitle(item: any) {
  if (tab.value === 'rbac') return item.description || 'No description'
  if (tab.value === 'abac') {
    const event = item.events?.[0]
    return `${event?.subject?.value || '*'} → ${event?.action?.value || '*'} → ${event?.resource?.value || '*'}`
  }
  if (tab.value === 'ngac') return item.node_type?.replaceAll('_', ' ')
  return `${item.ownership || item.access_source} · ${item.access_source}`
}

watch(tab, () => { notice.value = ''; checkResult.value = null; validationResult.value = null; load() })
watch(() => props.accountId, load)
onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-end justify-space-between ga-4 mb-6">
      <div>
        <div class="text-overline text-primary">Policy studio</div>
        <h1 class="text-h4 xolo-title">Authorization</h1>
        <p class="text-medium-emphasis mb-0">Choose a model, create its rules, and maintain them in one place.</p>
      </div>
      <v-chip prepend-icon="mdi-domain" color="primary" variant="tonal">{{ accountId }}</v-chip>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" closable class="mb-4" @click:close="error = ''">{{ error }}</v-alert>
    <v-alert v-if="notice" type="success" variant="tonal" closable class="mb-4" @click:close="notice = ''">{{ notice }}</v-alert>

    <v-card class="xolo-card auth-shell">
      <v-tabs v-model="tab" color="primary" grow show-arrows>
        <v-tab value="rbac" prepend-icon="mdi-account-badge-outline">RBAC</v-tab>
        <v-tab value="acl" prepend-icon="mdi-format-list-checks">ACL</v-tab>
        <v-tab value="abac" prepend-icon="mdi-tune-variant">ABAC</v-tab>
        <v-tab value="ngac" prepend-icon="mdi-graph-outline">NGAC</v-tab>
      </v-tabs>
      <v-divider />

      <v-card-text class="pa-5 pa-md-7">
        <v-sheet class="auth-guide pa-5 mb-6" rounded="lg">
          <div class="d-flex ga-4 align-start">
            <v-avatar color="primary" variant="tonal" rounded="lg"><v-icon :icon="guides[tab].icon" /></v-avatar>
            <div>
              <div class="text-h6">{{ guides[tab].title }}</div>
              <div class="text-body-2 text-medium-emphasis">{{ guides[tab].summary }}</div>
              <div class="text-caption text-primary mt-2"><strong>Use it when:</strong> {{ guides[tab].use }}</div>
            </div>
          </div>
        </v-sheet>

        <v-alert v-if="!can(tab, 'read')" type="info" variant="tonal">You do not have read permission for this authorization model.</v-alert>

        <template v-else-if="tab === 'acl'">
          <div class="d-flex justify-center mb-6">
            <v-btn-toggle v-model="aclView" color="primary" mandatory rounded="lg" variant="outlined">
              <v-btn value="resources" prepend-icon="mdi-cube-outline">Resources</v-btn>
              <v-btn value="groups" prepend-icon="mdi-account-multiple-outline">Groups</v-btn>
            </v-btn-toggle>
          </div>

          <template v-if="aclView === 'resources'">
            <v-row>
              <v-col cols="12" lg="7">
                <v-card variant="outlined" class="h-100">
                  <v-card-title>Manage resource access</v-card-title>
                  <v-card-subtitle>Select people by username or choose an existing group.</v-card-subtitle>
                  <v-card-text>
                    <v-text-field v-model="aclForm.resource_id" label="Resource ID" placeholder="invoice:2026-0042" prepend-inner-icon="mdi-cube-outline" />
                    <v-autocomplete v-model="aclForm.principal" :items="principalItems" label="User or group" prepend-inner-icon="mdi-account-key-outline" clearable />
                    <v-select v-model="aclForm.permissions" :items="permissionChoices" label="Permissions" multiple chips closable-chips />
                  </v-card-text>
                  <v-card-actions class="px-4 pb-4 ga-2 flex-wrap">
                    <v-btn variant="tonal" :disabled="!can('acl', 'manage') || !aclForm.resource_id" :loading="busy" @click="claimResource">Claim resource</v-btn>
                    <v-spacer />
                    <v-btn variant="outlined" color="error" :disabled="!can('acl', 'manage') || !aclForm.resource_id || !aclForm.principal || !aclForm.permissions.length" :loading="busy" @click="changeGrant('revoke')">Revoke</v-btn>
                    <v-btn color="primary" :disabled="!can('acl', 'manage') || !aclForm.resource_id || !aclForm.principal || !aclForm.permissions.length" :loading="busy" @click="changeGrant('grant')">Grant access</v-btn>
                  </v-card-actions>
                </v-card>
              </v-col>
              <v-col cols="12" lg="5">
                <v-card variant="outlined" class="h-100">
                  <v-card-title>Validate access</v-card-title>
                  <v-card-subtitle>Select a principal or leave blank to check yourself.</v-card-subtitle>
                  <v-card-text>
                    <v-text-field v-model="checkForm.resource_id" label="Resource ID" />
                    <v-autocomplete v-model="checkForm.principal" :items="principalItems" label="User or group (optional)" clearable />
                    <v-select v-model="checkForm.permissions" :items="permissionChoices" label="Required permissions" multiple chips />
                    <v-alert v-if="checkResult !== null" :type="checkResult ? 'success' : 'error'" variant="tonal" class="mt-2">{{ checkResult ? 'Allowed — every requested permission is present.' : 'Denied — one or more permissions are missing.' }}</v-alert>
                  </v-card-text>
                  <v-card-actions class="px-4 pb-4"><v-spacer /><v-btn color="primary" variant="tonal" :loading="busy" :disabled="!checkForm.resource_id || !checkForm.permissions.length" @click="checkAccess">Validate</v-btn></v-card-actions>
                </v-card>
              </v-col>
            </v-row>

            <div class="d-flex align-center mt-8 mb-3"><div class="text-h6">Resources and grants</div><v-spacer /><v-btn icon="mdi-refresh" variant="text" :loading="loading" @click="load" /></div>
            <v-table v-if="items.length" hover>
              <thead><tr><th>Resource</th><th>Relationship</th><th>My permissions</th><th /></tr></thead>
              <tbody><tr v-for="item in items" :key="item.resource_id"><td class="xolo-mono">{{ item.resource_id }}</td><td>{{ item.ownership }} · {{ item.access_source }}</td><td><v-chip v-for="permission in item.permissions" :key="permission" size="small" color="primary" variant="tonal" class="mr-1">{{ permission }}</v-chip></td><td class="text-right"><v-btn size="small" variant="text" prepend-icon="mdi-account-key-outline" @click="loadGrants(item.resource_id)">View grants</v-btn></td></tr></tbody>
            </v-table>
            <v-alert v-else-if="!loading" type="info" variant="tonal">No ACL resources are visible yet. Claim one above to begin.</v-alert>

            <v-card v-if="selectedResource" variant="outlined" class="mt-5">
              <v-card-title class="d-flex align-center"><span>Grants for <span class="xolo-mono">{{ selectedResource }}</span></span><v-spacer /><v-btn icon="mdi-close" variant="text" size="small" @click="selectedResource = ''; grants = []" /></v-card-title>
              <v-list v-if="grants.length" class="bg-transparent">
                <v-list-item v-for="grant in grants" :key="grant.grant_id" :title="grant.principal_name" :subtitle="`${grant.principal_type} · ${grant.principal_id}`" prepend-icon="mdi-account-key-outline">
                  <template #append><div class="d-flex align-center ga-2"><v-chip v-if="grant.is_owner" size="small" color="warning" variant="tonal">Owner</v-chip><v-chip v-for="permission in grant.permissions" :key="permission" size="small" color="primary" variant="tonal">{{ permission }}</v-chip><v-btn v-if="can('acl','manage') && !grant.is_owner" icon="mdi-delete-outline" color="error" variant="text" size="small" @click="revokeGrant(grant)" /></div></template>
                </v-list-item>
              </v-list>
              <v-card-text v-else class="text-medium-emphasis">No grants found.</v-card-text>
            </v-card>
          </template>

          <template v-else>
            <v-row>
              <v-col cols="12" lg="5">
                <v-card v-if="can('acl','manage')" variant="outlined" class="mb-5">
                  <v-card-title>Create a group</v-card-title>
                  <v-card-subtitle>Grant once, then manage membership separately.</v-card-subtitle>
                  <v-card-text><v-text-field v-model="groupForm.name" label="Group name" /><v-textarea v-model="groupForm.description" label="Description" rows="2" /></v-card-text>
                  <v-card-actions class="px-4 pb-4"><v-spacer /><v-btn color="primary" :loading="busy" :disabled="!groupForm.name.trim()" @click="createGroup">Create group</v-btn></v-card-actions>
                </v-card>
                <v-card variant="outlined"><v-card-title>Groups</v-card-title><v-list v-if="groups.length" class="bg-transparent"><v-list-item v-for="group in groups" :key="group.id" :active="selectedGroup === group.id" :title="group.name" :subtitle="group.description || group.id" prepend-icon="mdi-account-multiple-outline" @click="loadMembers(group.id)"><template #append><v-btn v-if="can('acl','manage')" icon="mdi-delete-outline" color="error" size="small" variant="text" @click.stop="removeGroup(group)" /></template></v-list-item></v-list><v-card-text v-else class="text-medium-emphasis">No groups yet.</v-card-text></v-card>
              </v-col>
              <v-col cols="12" lg="7">
                <v-card variant="outlined" class="h-100">
                  <v-card-title>Members</v-card-title>
                  <v-card-subtitle>{{ selectedGroup ? 'Add members using their username.' : 'Choose a group to manage its members.' }}</v-card-subtitle>
                  <v-card-text>
                    <div v-if="selectedGroup && can('acl','manage')" class="d-flex ga-2 align-start mb-4"><v-autocomplete v-model="memberForm.username" :items="userItems" label="Tenant username" class="flex-grow-1" clearable /><v-btn color="primary" class="mt-1" :disabled="!memberForm.username" :loading="busy" @click="changeMember('add')">Add</v-btn></div>
                    <v-list v-if="groupMembers.length" class="bg-transparent"><v-list-item v-for="member in groupMembers" :key="member.user_id" :title="memberTitle(member)" :subtitle="member.user_id" prepend-icon="mdi-account-outline"><template #append><div class="d-flex align-center ga-2"><v-chip v-if="member.user_id === selectedGroupOwner" size="small" color="warning" variant="tonal">Owner</v-chip><v-btn v-if="can('acl','manage') && member.user_id !== selectedGroupOwner" icon="mdi-account-minus-outline" color="error" variant="text" @click="changeMember('remove', member.username)" /></div></template></v-list-item></v-list>
                    <v-alert v-else-if="selectedGroup" type="info" variant="tonal">This group has no members.</v-alert>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>
          </template>
        </template>

        <template v-else>
          <v-card v-if="can(tab, 'manage')" variant="outlined" class="mb-7">
            <v-card-title>Create {{ tab === 'rbac' ? 'a role' : tab === 'abac' ? 'a policy' : 'a node' }}</v-card-title>
            <v-card-text v-if="tab === 'rbac'">
              <v-row><v-col cols="12" md="4"><v-text-field v-model="roleForm.name" label="Role name" /></v-col><v-col cols="12" md="8"><v-text-field v-model="roleForm.description" label="Description" /></v-col></v-row>
              <v-text-field v-model="roleForm.permissions" label="Permissions" hint="Comma separated, for example: documents.read, documents.write" persistent-hint />
            </v-card-text>
            <v-card-text v-else-if="tab === 'abac'">
              <v-row><v-col cols="12" md="8"><v-text-field v-model="abacForm.name" label="Policy name" /></v-col><v-col cols="12" md="4"><v-select v-model="abacForm.effect" :items="['ALLOW', 'DENY']" label="Effect" /></v-col></v-row>
              <v-row><v-col cols="12" md="4"><v-text-field v-model="abacForm.subject" label="Subject pattern" /></v-col><v-col cols="12" md="4"><v-text-field v-model="abacForm.action" label="Action" /></v-col><v-col cols="12" md="4"><v-text-field v-model="abacForm.resource" label="Resource pattern" /></v-col></v-row>
            </v-card-text>
            <v-card-text v-else>
              <v-row><v-col cols="12" md="5"><v-text-field v-model="ngacForm.name" label="Node name" /></v-col><v-col cols="12" md="7"><v-select v-model="ngacForm.node_type" :items="nodeTypes" label="Node type" /></v-col></v-row>
              <v-textarea v-model="ngacForm.properties" label="Properties (JSON)" rows="3" class="xolo-mono" />
            </v-card-text>
            <v-card-actions class="px-4 pb-4"><v-spacer /><v-btn v-if="tab === 'rbac'" color="primary" :loading="busy" :disabled="!roleForm.name.trim()" @click="createRole">Create role</v-btn><v-btn v-else-if="tab === 'abac'" color="primary" :loading="busy" :disabled="!abacForm.name.trim()" @click="createAbacPolicy">Create policy</v-btn><v-btn v-else color="primary" :loading="busy" :disabled="!ngacForm.name.trim()" @click="createNgacNode">Create node</v-btn></v-card-actions>
          </v-card>

          <v-card variant="outlined" class="mb-7 auth-validator">
            <v-card-title>Validate permission</v-card-title>
            <v-card-subtitle>Run the current {{ tab.toUpperCase() }} policy engine and inspect its decision.</v-card-subtitle>
            <v-card-text>
              <v-row v-if="tab === 'rbac'">
                <v-col cols="12" md="7"><v-combobox v-model="rbacCheck.subject_id" :items="rbacUserItems" label="Tenant user" hint="Choose a username or enter a subject ID" persistent-hint /></v-col>
                <v-col cols="12" md="5"><v-text-field v-model="rbacCheck.permission" label="Permission" placeholder="documents.read" /></v-col>
              </v-row>
              <v-row v-else-if="tab === 'abac'">
                <v-col cols="12" md="4"><v-text-field v-model="abacCheck.subject" label="Subject" placeholder="Teacher" /></v-col>
                <v-col cols="12" md="4"><v-text-field v-model="abacCheck.action" label="Action" placeholder="read" /></v-col>
                <v-col cols="12" md="4"><v-text-field v-model="abacCheck.resource" label="Resource" placeholder="Grades" /></v-col>
              </v-row>
              <v-row v-else>
                <v-col cols="12" md="4"><v-select v-model="ngacCheck.user_id" :items="ngacUsers" label="User node" no-data-text="Create a user node first" /></v-col>
                <v-col cols="12" md="4"><v-text-field v-model="ngacCheck.operation" label="Operation" placeholder="read" /></v-col>
                <v-col cols="12" md="4"><v-select v-model="ngacCheck.object_id" :items="ngacObjects" label="Object node" no-data-text="Create an object node first" /></v-col>
              </v-row>
              <v-alert v-if="validationResult" :type="validationAllowed() ? 'success' : 'error'" variant="tonal" class="mt-2">
                <strong>{{ validationAllowed() ? 'Allowed' : 'Denied' }}</strong>
                <span v-if="validationResult.reason"> — {{ validationResult.reason }}</span>
                <span v-else-if="validationResult.matched_policy"> — matched policy {{ validationResult.matched_policy }}</span>
              </v-alert>
            </v-card-text>
            <v-card-actions class="px-4 pb-4"><v-spacer /><v-btn color="primary" variant="tonal" :loading="busy" :disabled="tab === 'rbac' ? (!rbacCheck.subject_id || !rbacCheck.permission) : tab === 'abac' ? (!abacCheck.subject || !abacCheck.resource || !abacCheck.action) : (!ngacCheck.user_id || !ngacCheck.object_id || !ngacCheck.operation)" @click="validatePermission">Validate</v-btn></v-card-actions>
          </v-card>

          <div class="d-flex align-center mb-3"><div class="text-h6">Existing {{ tab === 'rbac' ? 'roles' : tab === 'abac' ? 'policies' : 'nodes' }}</div><v-spacer /><v-btn icon="mdi-refresh" variant="text" :loading="loading" @click="load" /></div>
          <v-list v-if="items.length" class="auth-list" lines="two">
            <v-list-item v-for="item in items" :key="item.role_id || item.policy_id || item.node_id" :prepend-icon="guides[tab].icon" :title="item.name" :subtitle="subtitle(item)">
              <template #append>
                <div class="d-none d-sm-flex align-center ga-1 mr-3">
                  <v-chip v-if="tab === 'abac'" size="small" :color="item.effect === 'ALLOW' ? 'success' : 'error'" variant="tonal">{{ item.effect }}</v-chip>
                  <v-chip v-for="permission in tab === 'rbac' ? item.permissions : []" :key="permission" size="small" color="primary" variant="tonal">{{ permission }}</v-chip>
                </div>
                <v-btn v-if="can(tab, 'manage')" icon="mdi-pencil-outline" size="small" variant="text" aria-label="Edit" @click="openEdit(item)" />
                <v-btn v-if="can(tab, 'manage')" icon="mdi-delete-outline" size="small" variant="text" color="error" aria-label="Delete" @click="removeItem(item)" />
              </template>
            </v-list-item>
          </v-list>
          <v-alert v-else-if="!loading" type="info" variant="tonal">Nothing here yet. Create the first item above.</v-alert>
          <div v-if="loading" class="d-flex justify-center pa-8"><v-progress-circular indeterminate color="primary" /></div>
        </template>
      </v-card-text>
    </v-card>

    <v-dialog v-model="editDialog" max-width="680">
      <v-card>
        <v-card-title>Edit {{ tab === 'rbac' ? 'role' : tab === 'abac' ? 'policy' : 'node' }}</v-card-title>
        <v-card-text>
          <v-text-field v-model="editForm.name" label="Name" />
          <template v-if="tab === 'rbac'"><v-text-field v-model="editForm.description" label="Description" /><v-text-field v-model="editForm.permissions" label="Permissions (comma separated)" /></template>
          <template v-else-if="tab === 'abac'"><v-select v-model="editForm.effect" :items="['ALLOW', 'DENY']" label="Effect" /><v-row><v-col cols="12" md="4"><v-text-field v-model="editForm.subject" label="Subject" /></v-col><v-col cols="12" md="4"><v-text-field v-model="editForm.action" label="Action" /></v-col><v-col cols="12" md="4"><v-text-field v-model="editForm.resource" label="Resource" /></v-col></v-row></template>
          <v-textarea v-else v-model="editForm.properties" label="Properties (JSON)" rows="5" class="xolo-mono" />
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn variant="text" @click="editDialog = false">Cancel</v-btn><v-btn color="primary" :loading="busy" :disabled="!editForm.name.trim()" @click="saveEdit">Save changes</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>
