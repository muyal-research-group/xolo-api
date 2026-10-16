<script setup lang="ts">
const props = defineProps<{ accountId: string; permissions: string[]; admin: boolean }>()
const tab = ref('rbac')
const can = (model: string, action: 'read' | 'manage') => props.admin || props.permissions.includes(`${model}.${action}`)
const sections = computed(() => [
  { value: 'rbac', label: 'RBAC', icon: 'mdi-account-badge-outline', area: 'rbac' },
  { value: 'acl', label: 'ACL', icon: 'mdi-format-list-checks', area: 'acl' },
  { value: 'abac', label: 'ABAC', icon: 'mdi-tune-variant', area: 'abac' },
  { value: 'ngac', label: 'NGAC', icon: 'mdi-graph-outline', area: 'ngac' },
  { value: 'audit', label: 'Audit', icon: 'mdi-history', area: 'audit' }
].filter(item => can(item.area, 'read')))
watch(() => props.accountId, () => { tab.value = sections.value[0]?.value || 'rbac' })
watch(sections, items => { if (!items.some(item => item.value === tab.value)) tab.value = items[0]?.value || 'rbac' }, { immediate: true })
</script>

<template>
  <div :key="accountId">
    <div class="d-flex flex-wrap align-end justify-space-between ga-4 mb-6">
      <div><div class="text-overline text-primary">Policy studio</div><h1 class="text-h4 xolo-title">Authorization</h1><p class="text-medium-emphasis mb-0">Policy models and immutable activity.</p></div>
      <v-chip prepend-icon="mdi-domain" color="primary" variant="tonal">{{ accountId }}</v-chip>
    </div>
    <v-card class="xolo-card auth-shell">
      <v-tabs v-model="tab" color="primary" show-arrows><v-tab v-for="section in sections" :key="section.value" :value="section.value" :prepend-icon="section.icon">{{ section.label }}</v-tab></v-tabs>
      <v-divider />
      <v-window v-model="tab">
        <v-window-item value="rbac"><AuthorizationRbacWorkspace :account-id="accountId" :can-manage="can('rbac','manage')" /></v-window-item>
        <v-window-item value="acl"><AuthorizationAclWorkspace :account-id="accountId" :can-manage="can('acl','manage')" /></v-window-item>
        <v-window-item value="abac"><AuthorizationAbacWorkspace :account-id="accountId" :can-manage="can('abac','manage')" /></v-window-item>
        <v-window-item value="ngac"><AuthorizationNgacWorkspace :account-id="accountId" :can-manage="can('ngac','manage')" /></v-window-item>
        <v-window-item value="audit"><AuthorizationAuditWorkspace :account-id="accountId" /></v-window-item>
      </v-window>
    </v-card>
    <v-alert v-if="!sections.length" type="info" variant="tonal">You do not have read access to an authorization workspace.</v-alert>
  </div>
</template>
