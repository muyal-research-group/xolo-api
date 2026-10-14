<script setup lang="ts">
const props = defineProps<{ accountId: string; canManage: boolean }>()
const { api, path, run, loading, errors } = useAuthorizationWorkspace(() => props.accountId)
const { requestConfirmation } = useConfirmationDialog()

const policies = ref<any[]>([])
const selected = ref<any>(null)
const page = ref(1)
const totalPages = ref(0)
const search = ref('')
const groups = ref<any[]>([])
const decision = ref<any>(null)
const deleteImpact = ref<any>(null)
const deleteDialog = ref(false)
const deleteConfirmation = ref('')
const grant = reactive({ principal_type: 'USER', principal_identifier: '', principal_id: '', permissions: ['read'] })
const inspector = reactive({ resource_id: '', username: '' })
const transfer = reactive({ principal_type: 'USER', owner_identifier: '', principal_id: '', keep_previous_permissions: [] as string[] })
const createForm = reactive({ resource_id: '', owner_type: 'USER', owner_identifier: '' })
const createDialog = ref(false)
const editGrantDialog = ref(false)
const editingGrant = ref<any>(null)
const editGrantPermissions = ref<string[]>([])
const permissionOptions = ['read', 'write', 'update', 'delete', 'sys:manage']

async function load() {
  const [inventory, references]: any[] = await Promise.all([
    run('resources', () => api(path(`acl/policies?search=${encodeURIComponent(search.value)}&page=${page.value}`))),
    run('groups', () => api(path('groups/references'))),
  ])
  if (inventory) {
    policies.value = inventory.items
    totalPages.value = inventory.total_pages
    if (selected.value) selected.value = policies.value.find(item => item.resource_id === selected.value.resource_id) || null
  }
  groups.value = references || []
}

function selectPolicy(policy: any) {
  selected.value = policy
  inspector.resource_id = policy.resource_id
  decision.value = null
}

async function addGrant() {
  if (!selected.value) return
  await run('grant', () => api(path('acl/grant'), {
    method: 'POST',
    body: {
      resource_id: selected.value.resource_id,
      principal_type: grant.principal_type,
      principal_identifier: grant.principal_type === 'USER' ? grant.principal_identifier : null,
      principal_id: grant.principal_type === 'GROUP' ? grant.principal_id : null,
      permissions: grant.permissions,
    },
  }))
  Object.assign(grant, { principal_type: 'USER', principal_identifier: '', principal_id: '', permissions: ['read'] })
  await load()
}

async function revoke(item: any) {
  if (!selected.value) return
  const confirmed = await requestConfirmation({
    title: 'Revoke ACL grant?',
    message: `Remove all access granted to ${item.principal_name || item.principal_id} for ${selected.value.resource_id}?`,
    confirmText: 'Revoke grant',
  })
  if (!confirmed) return
  await run(`revoke-${item.grant_id}`, () => api(path(`acl/resources/${encodeURIComponent(selected.value.resource_id)}/grants/${item.grant_id}`), {
    method: 'DELETE',
  }))
  await load()
}

function openGrantEdit(item: any) {
  editingGrant.value = item
  editGrantPermissions.value = [...item.permissions]
  editGrantDialog.value = true
}

async function saveGrant() {
  if (!selected.value || !editingGrant.value || !editGrantPermissions.value.length) return
  const updated = await run('update-grant', () => api(path(
    `acl/resources/${encodeURIComponent(selected.value.resource_id)}/grants/${encodeURIComponent(editingGrant.value.grant_id)}`
  ), { method: 'PATCH', body: { permissions: editGrantPermissions.value } }))
  if (updated) {
    editGrantDialog.value = false
    editingGrant.value = null
    editGrantPermissions.value = []
    await load()
  }
}

async function inspectAccess() {
  decision.value = null
  decision.value = await run('check', () => api(path(`acl/resources/${encodeURIComponent(inspector.resource_id)}/effective-access/${encodeURIComponent(inspector.username)}`)))
}

async function transferOwner() {
  if (!selected.value) return
  await run('transfer', () => api(path(`acl/resources/${encodeURIComponent(selected.value.resource_id)}/owner`), { method: 'POST', body: transfer }))
  Object.assign(transfer, { principal_type: 'USER', owner_identifier: '', principal_id: '', keep_previous_permissions: [] })
  await load()
}

async function createResource() {
  const created:any = await run('create-resource', () => api(path('acl/resources'), { method: 'POST', body: createForm }))
  if (created) { createDialog.value=false; Object.assign(createForm,{resource_id:'',owner_type:'USER',owner_identifier:''}); await load(); const policy=policies.value.find(item=>item.resource_id===created.resource_id); if(policy)selectPolicy(policy) }
}

async function previewDelete() {
  if (!selected.value) return
  deleteImpact.value = await run('impact', () => api(path(`acl/resources/${encodeURIComponent(selected.value.resource_id)}/deletion-impact`)))
  deleteConfirmation.value = ''
  deleteDialog.value = !!deleteImpact.value
}

async function deletePolicy() {
  if (!selected.value) return
  const id = selected.value.resource_id
  const response = await run('delete', () => api(path(`acl/resources/${encodeURIComponent(id)}/policy`), { method: 'DELETE', body: { confirm_resource_id: deleteConfirmation.value } }))
  if (response !== undefined) { selected.value = null; deleteDialog.value = false; await load() }
}

watch(() => props.accountId, () => {
  policies.value = []; selected.value = null; decision.value = null; deleteDialog.value = false
  Object.assign(inspector, { resource_id: '', username: '' }); createDialog.value=false; editGrantDialog.value=false; editingGrant.value=null; editGrantPermissions.value=[]; load()
}, { immediate: true })
watch(search, () => { page.value = 1; load() })
</script>

<template>
  <div class="pa-5 pa-md-7">
    <v-alert v-for="(message, key) in errors" v-show="message" :key="key" type="error" variant="tonal" class="mb-3" @click:close="errors[key] = ''">{{ message }}</v-alert>
    <div class="d-flex align-center mb-4"><div><h2 class="text-h5">Resource ACLs</h2><p class="text-medium-emphasis">Complete policy inventory, ownership, grants, and effective-access explanations.</p></div><v-spacer /><v-btn v-if="canManage" prepend-icon="mdi-plus" color="primary" variant="tonal" class="mr-2" @click="createDialog=true">Create resource</v-btn><v-btn icon="mdi-refresh" variant="text" :loading="loading.resources" aria-label="Refresh ACL resources" @click="load" /></div>
    <v-row>
      <v-col cols="12" lg="5"><v-card variant="outlined"><v-card-text><v-text-field v-model="search" label="Search resources" prepend-inner-icon="mdi-magnify" hide-details /></v-card-text><v-list v-if="policies.length"><v-list-item v-for="policy in policies" :key="policy.resource_id" :active="selected?.resource_id === policy.resource_id" :title="policy.resource_id" :subtitle="`${policy.grants.length} grants`" @click="selectPolicy(policy)" /></v-list><v-card-text v-else>No resource policies found.</v-card-text><v-pagination v-if="totalPages > 1" v-model="page" :length="totalPages" @update:model-value="load" /></v-card></v-col>
      <v-col cols="12" lg="7">
        <v-alert v-if="!selected" type="info" variant="tonal">Select a resource policy to manage it.</v-alert>
        <template v-else>
          <v-card variant="outlined" :title="selected.resource_id"><v-card-subtitle>Internal resource identifier</v-card-subtitle><v-list><v-list-item v-for="item in selected.grants" :key="item.grant_id" :title="item.principal_name || item.principal_id" :subtitle="`${item.principal_type} · ${item.principal_id}`"><template #prepend><v-icon :icon="item.is_owner ? 'mdi-crown-outline' : 'mdi-share-variant-outline'" :color="item.is_owner ? 'warning' : 'primary'" /></template><template #append><div class="d-flex align-center"><v-chip v-for="permission in item.permissions" :key="permission" size="small" class="ma-1">{{ permission }}</v-chip><v-btn v-if="canManage && !item.is_owner" icon="mdi-pencil-outline" size="small" variant="text" aria-label="Edit grant permissions" @click="openGrantEdit(item)" /><v-btn v-if="canManage && !item.is_owner" icon="mdi-delete-outline" size="small" variant="text" color="error" aria-label="Revoke grant" @click="revoke(item)" /></div></template></v-list-item></v-list></v-card>
          <v-row v-if="canManage" class="mt-2">
            <v-col cols="12" md="6"><v-card variant="outlined" title="Grant access"><v-card-text><v-select v-model="grant.principal_type" :items="['USER','GROUP']" label="Principal type" /><TenantUserAutocomplete v-if="grant.principal_type === 'USER'" v-model="grant.principal_identifier" :account-id="accountId" /><v-select v-else v-model="grant.principal_id" :items="groups" item-title="name" item-value="group_id" label="Shared group" /><v-select v-model="grant.permissions" :items="permissionOptions" multiple chips label="Permissions" /></v-card-text><v-card-actions><v-spacer /><v-btn color="primary" :loading="loading.grant" @click="addGrant">Grant</v-btn></v-card-actions></v-card></v-col>
            <v-col cols="12" md="6"><v-card variant="outlined" title="Transfer ownership"><v-card-text><v-select v-model="transfer.principal_type" :items="['USER','GROUP']" label="New owner type" /><TenantUserAutocomplete v-if="transfer.principal_type === 'USER'" v-model="transfer.owner_identifier" :account-id="accountId" /><v-select v-else v-model="transfer.principal_id" :items="groups" item-title="name" item-value="group_id" label="Shared group" /><v-select v-model="transfer.keep_previous_permissions" :items="permissionOptions.filter(item => item !== 'sys:manage')" multiple chips label="Previous owner retains" /></v-card-text><v-card-actions><v-btn color="error" variant="text" @click="previewDelete">Delete policy</v-btn><v-spacer /><v-btn color="primary" :loading="loading.transfer" @click="transferOwner">Transfer</v-btn></v-card-actions></v-card></v-col>
          </v-row>
        </template>
      </v-col>
    </v-row>
    <v-card variant="outlined" class="mt-5" title="Access inspector"><v-card-text><v-row><v-col cols="12" md="5"><v-text-field v-model="inspector.resource_id" label="Resource ID" /></v-col><v-col cols="12" md="5"><TenantUserAutocomplete v-model="inspector.username" :account-id="accountId" /></v-col><v-col cols="12" md="2"><v-btn block color="primary" class="mt-2" :loading="loading.check" @click="inspectAccess">Explain</v-btn></v-col></v-row><v-alert v-if="decision" :type="decision.allowed ? 'success' : 'error'" variant="tonal"><strong>{{ decision.allowed ? 'Has effective access' : 'No effective access' }}</strong><div v-if="decision.denial_reason">{{ decision.denial_reason }}</div><div class="mt-2">Direct: {{ [...decision.direct_permissions].join(', ') || 'none' }}</div><div v-for="(permissions, groupId) in decision.group_permissions" :key="groupId">Group {{ groupId }}: {{ [...permissions].join(', ') }}</div><div v-if="decision.ignored_disabled_groups.length">Ignored disabled groups: {{ decision.ignored_disabled_groups.join(', ') }}</div><div>Effective union: {{ [...decision.effective_permissions].join(', ') || 'none' }}</div></v-alert></v-card-text></v-card>
    <v-dialog v-model="createDialog" max-width="620"><v-card title="Create protected resource"><v-card-text><v-text-field v-model="createForm.resource_id" label="Resource ID"/><v-select v-model="createForm.owner_type" :items="['USER','GROUP']" label="Owner type"/><TenantUserAutocomplete v-if="createForm.owner_type==='USER'" v-model="createForm.owner_identifier" :account-id="accountId" label="Owner username"/><v-select v-else v-model="createForm.owner_identifier" :items="groups" item-title="name" item-value="group_id" label="Owner group"/><v-alert type="info" variant="tonal" density="compact">Creation atomically adds the protected sys:manage owner grant.</v-alert></v-card-text><v-card-actions><v-spacer/><v-btn @click="createDialog=false">Cancel</v-btn><v-btn color="primary" :disabled="!createForm.resource_id||!createForm.owner_identifier" :loading="loading['create-resource']" @click="createResource">Create</v-btn></v-card-actions></v-card></v-dialog>
    <v-dialog v-model="editGrantDialog" max-width="560"><v-card title="Edit ACL grant"><v-card-text><v-list density="compact"><v-list-item title="Principal" :subtitle="editingGrant?.principal_name || editingGrant?.principal_id"/><v-list-item title="Grant ID" :subtitle="editingGrant?.grant_id" class="xolo-mono"/></v-list><v-select v-model="editGrantPermissions" :items="permissionOptions" multiple chips label="Permissions" hint="At least one permission is required" persistent-hint/></v-card-text><v-card-actions><v-spacer/><v-btn @click="editGrantDialog=false">Cancel</v-btn><v-btn color="primary" :disabled="!editGrantPermissions.length" :loading="loading['update-grant']" @click="saveGrant">Save changes</v-btn></v-card-actions></v-card></v-dialog>
    <v-dialog v-model="deleteDialog" max-width="620"><v-card title="Delete resource policy?"><v-card-text><p>This removes {{ deleteImpact?.grant_count || 0 }} grants. This cannot be undone.</p><v-text-field v-model="deleteConfirmation" :label="`Type ${selected?.resource_id} to confirm`" autocomplete="off" /></v-card-text><v-card-actions><v-spacer /><v-btn @click="deleteDialog = false">Cancel</v-btn><v-btn color="error" :disabled="deleteConfirmation !== selected?.resource_id" :loading="loading.delete" @click="deletePolicy">Delete policy</v-btn></v-card-actions></v-card></v-dialog>
  </div>
</template>
