<script setup lang="ts">
const props = defineProps<{ accountId: string; canManage: boolean }>()
const { api, path, run, loading, errors } = useAuthorizationWorkspace(() => props.accountId)
const { requestConfirmation } = useConfirmationDialog()

const groups = ref<any[]>([])
const selected = ref<any>(null)
const members = ref<any[]>([])
const usage = ref<any>({ acl_grants: [], rbac_assignments: [] })
const search = ref('')
const memberSearch = ref('')
const page = ref(1)
const memberPage = ref(1)
const totalPages = ref(0)
const memberTotalPages = ref(0)
const section = ref('overview')
const deleteDialog = ref(false)
const statusDialog = ref(false)
const deleteConfirmation = ref('')
const pendingStatus = ref(true)
const usernames = ref('')
const selectedUsernames = ref<string[]>([])
const createForm = reactive({ name: '', description: '', owner_username: '' })
const editForm = reactive({ name: '', description: '' })
const ownerUsername = ref('')
const usernameList = computed(() => [...new Set([...selectedUsernames.value, ...usernames.value.split(/[\s,]+/).map(value => value.trim()).filter(Boolean)])])
const usageCount = computed(() => usage.value.acl_grants.length + usage.value.rbac_assignments.length)

async function load() {
  const data: any = await run('list', () => api(path(`groups?search=${encodeURIComponent(search.value)}&page=${page.value}`)))
  if (data) { groups.value = data.items; totalPages.value = data.total_pages }
}

async function open(group: any) {
  selected.value = group
  section.value = 'overview'
  Object.assign(editForm, { name: group.name, description: group.description || '' })
  ownerUsername.value = ''
  memberSearch.value = ''
  memberPage.value = 1
  await Promise.all([loadMembers(), loadUsage()])
}

async function loadMembers() {
  if (!selected.value) return
  const data: any = await run('members', () => api(path(`groups/${selected.value.group_id}/members?search=${encodeURIComponent(memberSearch.value)}&page=${memberPage.value}`)))
  members.value = data?.items || []
  memberTotalPages.value = data?.total_pages || 0
}

async function loadUsage() {
  if (!selected.value) return
  usage.value = await run('usage', () => api(path(`groups/${selected.value.group_id}/usage`))) || { acl_grants: [], rbac_assignments: [] }
}

async function create() {
  const created: any = await run('create', () => api(path('groups'), { method: 'POST', body: createForm }))
  if (created) { Object.assign(createForm, { name: '', description: '', owner_username: '' }); await load(); await open(created) }
}

async function updateMetadata() {
  if (!selected.value) return
  const updated: any = await run('metadata', () => api(path(`groups/${selected.value.group_id}`), { method: 'PATCH', body: editForm }))
  if (updated) { selected.value = updated; await load() }
}

async function transferOwner() {
  if (!selected.value || !ownerUsername.value) return
  const response = await run('owner', () => api(path(`groups/${selected.value.group_id}/owner`), { method: 'POST', body: { owner_username: ownerUsername.value } }))
  if (response !== undefined) { ownerUsername.value = ''; const refreshed: any = await run('detail', () => api(path(`groups/${selected.value.group_id}`))); if (refreshed) selected.value = refreshed; await load() }
}

async function changeMembers(method: 'POST' | 'DELETE') {
  if (!selected.value || !usernameList.value.length) return
  if (method === 'DELETE') {
    const confirmed = await requestConfirmation({
      title: 'Remove group members?',
      message: `Remove ${usernameList.value.length} selected user${usernameList.value.length === 1 ? '' : 's'} from ${selected.value.name}?`,
      confirmText: 'Remove members',
    })
    if (!confirmed) return
  }
  const response = await run('membership', () => api(path(`groups/${selected.value.group_id}/members`), { method, body: { usernames: usernameList.value } }))
  if (response !== undefined) { usernames.value = ''; selectedUsernames.value = []; await loadMembers(); await load() }
}

async function leave() {
  if (!selected.value) return
  const confirmed = await requestConfirmation({
    title: 'Leave group?',
    message: `Remove your membership from ${selected.value.name}? Any access inherited from this group will be lost.`,
    confirmText: 'Leave group',
  })
  if (!confirmed) return
  const response = await run('leave', () => api(path(`groups/${selected.value.group_id}/members/me`), { method: 'DELETE' }))
  if (response !== undefined) { await loadMembers(); await load() }
}

function requestStatus() {
  pendingStatus.value = !selected.value.is_active
  statusDialog.value = true
}

async function setStatus() {
  if (!selected.value) return
  const updated: any = await run('status', () => api(path(`groups/${selected.value.group_id}/status`), { method: 'POST', body: { is_active: pendingStatus.value } }))
  if (updated) { selected.value = updated; statusDialog.value = false; await load() }
}

async function remove() {
  if (!selected.value) return
  const response = await run('delete', () => api(path(`groups/${selected.value.group_id}`), { method: 'DELETE' }))
  if (response !== undefined) { deleteDialog.value = false; selected.value = null; deleteConfirmation.value = ''; await load() }
}

watch(() => props.accountId, () => {
  groups.value = []; selected.value = null; members.value = []; usage.value = { acl_grants: [], rbac_assignments: [] }
  usernames.value = ''; selectedUsernames.value = []; search.value = ''; memberSearch.value = ''; deleteDialog.value = false; statusDialog.value = false
  load()
}, { immediate: true })
watch(search, () => { page.value = 1; load() })
watch(memberSearch, () => { memberPage.value = 1; loadMembers() })
</script>

<template>
  <div class="pa-5 pa-md-7">
    <v-alert v-for="(message, key) in errors" v-show="message" :key="key" type="error" variant="tonal" class="mb-3" @click:close="errors[key] = ''">{{ message }}</v-alert>
    <div class="d-flex align-center mb-5"><div><h2 class="text-h5">Shared groups</h2><p class="text-medium-emphasis">Ownership is administrative; access comes only from explicit ACL grants and RBAC assignments.</p></div><v-spacer /><v-btn icon="mdi-refresh" variant="text" :loading="loading.list" aria-label="Refresh groups" @click="load" /></div>
    <v-row>
      <v-col cols="12" lg="4">
        <v-card variant="outlined" class="mb-4"><v-card-text><v-text-field v-model="search" label="Search groups" prepend-inner-icon="mdi-magnify" hide-details /></v-card-text><v-list v-if="groups.length"><v-list-item v-for="group in groups" :key="group.group_id" :active="selected?.group_id === group.group_id" :title="group.name" :subtitle="`${group.member_count} members · ${group.acl_usage_count} ACL · ${group.rbac_usage_count} RBAC`" @click="open(group)"><template #prepend><v-icon :color="group.is_active ? 'success' : 'grey'" :icon="group.is_active ? 'mdi-check-circle' : 'mdi-pause-circle'" /></template></v-list-item></v-list><v-card-text v-else>No groups found.</v-card-text><v-pagination v-if="totalPages > 1" v-model="page" :length="totalPages" @update:model-value="load" /></v-card>
        <v-card v-if="canManage" variant="outlined"><v-card-title>Create group</v-card-title><v-card-text><v-text-field v-model="createForm.name" label="Name" /><TenantUserAutocomplete v-model="createForm.owner_username" :account-id="accountId" label="Owner username" /><v-textarea v-model="createForm.description" label="Description" rows="2" /><v-alert type="info" density="compact" variant="tonal">The owner is not added as a member.</v-alert></v-card-text><v-card-actions><v-spacer /><v-btn color="primary" :loading="loading.create" :disabled="!createForm.name || !createForm.owner_username" @click="create">Create</v-btn></v-card-actions></v-card>
      </v-col>
      <v-col cols="12" lg="8">
        <v-alert v-if="!selected" type="info" variant="tonal">Select a group to inspect it.</v-alert>
        <v-card v-else variant="outlined"><v-card-title class="d-flex align-center"><span>{{ selected.name }}</span><v-chip class="ml-3" size="small" :color="selected.is_active ? 'success' : 'warning'" variant="tonal">{{ selected.is_active ? 'Active' : 'Disabled' }}</v-chip><v-spacer /><v-btn v-if="canManage" variant="tonal" @click="requestStatus">{{ selected.is_active ? 'Disable' : 'Reactivate' }}</v-btn></v-card-title><v-card-subtitle class="xolo-mono">{{ selected.group_id }}</v-card-subtitle><v-tabs v-model="section"><v-tab value="overview">Overview</v-tab><v-tab value="members">Members</v-tab><v-tab value="usage">Usage</v-tab><v-tab value="activity">Activity</v-tab></v-tabs><v-divider />
          <v-window v-model="section">
            <v-window-item value="overview"><v-card-text><v-row><v-col cols="12" md="6"><v-text-field v-model="editForm.name" label="Name" :readonly="!canManage" /><v-textarea v-model="editForm.description" label="Description" rows="3" :readonly="!canManage" /><v-btn v-if="canManage" color="primary" :loading="loading.metadata" @click="updateMetadata">Save metadata</v-btn></v-col><v-col cols="12" md="6"><v-list bg-color="transparent"><v-list-item title="Owner" :subtitle="selected.owner_username || selected.owner_id" /><v-list-item title="Group ID" :subtitle="selected.group_id" /><v-list-item title="Created" :subtitle="new Date(selected.created_at).toLocaleString()" /><v-list-item title="Updated" :subtitle="new Date(selected.updated_at).toLocaleString()" /></v-list><template v-if="canManage"><TenantUserAutocomplete v-model="ownerUsername" :account-id="accountId" label="New owner username" /><v-btn variant="tonal" :loading="loading.owner" :disabled="!ownerUsername" @click="transferOwner">Transfer ownership</v-btn></template></v-col></v-row><v-alert v-if="!selected.is_active" type="warning" variant="tonal" class="mt-3">Relationships and members are retained but contribute no ACL or RBAC access. Reactivation restores them.</v-alert><v-btn v-if="canManage" color="error" variant="text" class="mt-3" :disabled="usageCount > 0" @click="deleteDialog = true">Delete group</v-btn></v-card-text></v-window-item>
            <v-window-item value="members"><v-card-text><v-text-field v-model="memberSearch" label="Filter current members" prepend-inner-icon="mdi-magnify" /><div v-if="canManage" class="d-flex ga-2 flex-wrap"><div class="flex-grow-1"><TenantUserAutocomplete v-model="selectedUsernames" :account-id="accountId" multiple :limit="20" label="Add tenant users"/><v-textarea v-model="usernames" label="Or paste batch usernames" rows="2" hint="Separate with spaces, commas, or new lines" /></div><div><v-btn color="primary" block class="mb-2" :disabled="!usernameList.length" @click="changeMembers('POST')">Add batch</v-btn><v-btn color="error" variant="outlined" block :disabled="!usernameList.length" @click="changeMembers('DELETE')">Remove batch</v-btn></div></div><v-table><thead><tr><th>Username</th><th>Joined</th></tr></thead><tbody><tr v-for="member in members" :key="member.user_id"><td>{{ member.username }}<div class="text-caption xolo-mono">{{ member.user_id }}</div></td><td>{{ new Date(member.joined_at).toLocaleString() }}</td></tr></tbody></v-table><v-pagination v-if="memberTotalPages > 1" v-model="memberPage" :length="memberTotalPages" @update:model-value="loadMembers" /><v-btn variant="text" color="warning" prepend-icon="mdi-exit-to-app" @click="leave">Leave this group</v-btn></v-card-text></v-window-item>
            <v-window-item value="usage"><v-card-text><v-alert v-if="!usageCount" type="success" variant="tonal">Unused — this group may be deleted.</v-alert><h3 class="text-subtitle-1 mt-3">ACL grants</h3><v-chip v-for="item in usage.acl_grants" :key="item.grant_id" class="ma-1" color="primary" variant="tonal">{{ item.resource_id }}</v-chip><h3 class="text-subtitle-1 mt-4">RBAC assignments</h3><v-chip v-for="item in usage.rbac_assignments" :key="item.assignment_id" class="ma-1" color="secondary" variant="tonal">{{ item.role_id }}</v-chip></v-card-text></v-window-item>
            <v-window-item value="activity"><AuthorizationAuditWorkspace :account-id="accountId" :target="selected.group_id" compact /></v-window-item>
          </v-window>
        </v-card>
      </v-col>
    </v-row>
    <v-dialog v-model="statusDialog" max-width="620"><v-card :title="pendingStatus ? 'Reactivate group?' : 'Disable group?'"><v-card-text><template v-if="pendingStatus">All retained ACL grants and RBAC assignments will contribute access again.</template><template v-else>This immediately suspends access from {{ usage.acl_grants.length }} ACL grants and {{ usage.rbac_assignments.length }} RBAC assignments. Members and relationships remain stored.</template></v-card-text><v-card-actions><v-spacer /><v-btn @click="statusDialog = false">Cancel</v-btn><v-btn :color="pendingStatus ? 'primary' : 'warning'" :loading="loading.status" @click="setStatus">{{ pendingStatus ? 'Reactivate' : 'Disable' }}</v-btn></v-card-actions></v-card></v-dialog>
    <v-dialog v-model="deleteDialog" max-width="560"><v-card title="Delete unused group?"><v-card-text><p class="mb-3">Deletion is permanent. The group ID cannot be recovered.</p><v-text-field v-model="deleteConfirmation" :label="`Type ${selected?.name} to confirm`" autocomplete="off" /></v-card-text><v-card-actions><v-spacer /><v-btn @click="deleteDialog = false">Cancel</v-btn><v-btn color="error" :disabled="deleteConfirmation !== selected?.name || usageCount > 0" :loading="loading.delete" @click="remove">Delete</v-btn></v-card-actions></v-card></v-dialog>
  </div>
</template>
