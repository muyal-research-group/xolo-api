<script setup lang="ts">
const { confirmation, resolveConfirmation } = useConfirmationDialog()
</script>

<template>
  <v-dialog :model-value="confirmation.open" max-width="520" persistent>
    <v-card :title="confirmation.title">
      <v-card-text>{{ confirmation.message }}</v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="resolveConfirmation(false)">{{ confirmation.cancelText }}</v-btn>
        <v-btn color="error" @click="resolveConfirmation(true)">{{ confirmation.confirmText }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
