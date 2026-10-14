<script setup lang="ts">
const props = withDefaults(defineProps<{
  accountId: string
  modelValue: string | string[] | null
  label?: string
  multiple?: boolean
  limit?: number
  clearable?: boolean
}>(), { label: 'Tenant username', multiple: false, limit: 3, clearable: true })
const emit = defineEmits<{ 'update:modelValue': [string | string[] | null] }>()
const { api } = useXoloApi()

interface TenantUserReference {
  user_id: string
  username: string
  match_type: string
}

const query = ref('')
const items = ref<TenantUserReference[]>([])
const loading = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
let controller: AbortController | undefined

function reset() { if (timer) clearTimeout(timer); controller?.abort(); query.value = ''; items.value = []; loading.value = false }
watch(() => props.accountId, () => {
  reset()
  emit('update:modelValue', props.multiple ? [] : null)
})
watch(query, value => {
  if (timer) clearTimeout(timer)
  controller?.abort()
  if (!value?.trim()) { items.value = []; loading.value = false; return }
  timer = setTimeout(async () => {
    const requestController = new AbortController()
    controller = requestController
    loading.value = true
    try {
      const result = await api(`/accounts/${encodeURIComponent(props.accountId)}/users/references?search=${encodeURIComponent(value.trim())}&limit=${Math.max(1, Math.min(20, props.limit))}`, { signal: requestController.signal }) as TenantUserReference[]
      if (controller === requestController && !requestController.signal.aborted) items.value = result
    } catch (cause: any) {
      if (controller === requestController && cause?.name !== 'AbortError') items.value = []
    } finally {
      if (controller === requestController) loading.value = false
    }
  }, 250)
})
onBeforeUnmount(reset)
</script>

<template>
  <v-autocomplete :model-value="modelValue" v-model:search="query" :items="items" item-title="username" item-value="username"
    :label="label" :multiple="multiple" :chips="multiple" :closable-chips="multiple" :loading="loading" :clearable="clearable"
    no-filter autocomplete="off" @update:model-value="value => emit('update:modelValue', value)">
    <template #item="{ props: itemProps, item }"><v-list-item v-bind="itemProps" :subtitle="`${item.match_type} · ${item.user_id}`" /></template>
    <template #no-data><v-list-item :title="query.trim() ? 'No matching users' : 'Type at least one character'" /></template>
  </v-autocomplete>
</template>
