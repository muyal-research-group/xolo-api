<script setup lang="ts">
import type { Account } from '~/types/platform'

const props = defineProps<{ selected: string | null; canManage: boolean }>()
const emit = defineEmits<{ select: [accountId: string]; changed: [] }>()
const { api } = useXoloApi()
const accounts = ref<Account[]>([])
const loading = ref(false)
const error = ref('')
const dialog = ref(false)
const form = reactive({ account_id: '', name: '' })

async function load() {
  loading.value = true
  error.value = ''
  try { accounts.value = await api<Account[]>('/accounts') }
  catch (cause: any) { error.value = cause?.data?.detail?.message || cause?.data?.detail || cause.message }
  finally { loading.value = false }
}

async function create() {
  await api('/accounts', { method: 'POST', body: form })
  dialog.value = false
  form.account_id = ''; form.name = ''
  await load(); emit('changed')
}

async function remove(account: Account) {
  if (!confirm(`Delete account ${account.account_id}?`)) return
  await api(`/accounts/${encodeURIComponent(account.account_id)}`, { method: 'DELETE' })
  await load(); emit('changed')
}

onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex align-center mb-5">
      <div><h1 class="text-h4 xolo-title">Accounts</h1><p class="text-medium-emphasis">Choose the tenant you want to manage.</p></div>
      <v-spacer /><v-btn v-if="canManage" color="primary" prepend-icon="mdi-plus" @click="dialog = true">New account</v-btn>
    </div>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
    <v-row><v-col v-for="account in accounts" :key="account.account_id" cols="12" md="6" lg="4">
      <v-card class="xolo-card" :color="selected === account.account_id ? 'primary' : undefined" :variant="selected === account.account_id ? 'tonal' : 'flat'">
        <v-card-title>{{ account.name }}</v-card-title><v-card-subtitle class="xolo-mono">{{ account.account_id }}</v-card-subtitle>
        <v-card-actions><v-btn variant="text" @click="emit('select', account.account_id)">Manage</v-btn><v-spacer /><v-btn v-if="canManage" color="error" icon="mdi-delete-outline" variant="text" @click="remove(account)" /></v-card-actions>
      </v-card>
    </v-col></v-row>
    <v-progress-linear v-if="loading" indeterminate color="primary" />
    <v-dialog v-model="dialog" max-width="520"><v-card title="Create account"><v-card-text><v-text-field v-model="form.account_id" label="Account ID" /><v-text-field v-model="form.name" label="Name" /></v-card-text><v-card-actions><v-spacer /><v-btn @click="dialog = false">Cancel</v-btn><v-btn color="primary" :disabled="form.account_id.length < 3 || !form.name" @click="create">Create</v-btn></v-card-actions></v-card></v-dialog>
  </div>
</template>
