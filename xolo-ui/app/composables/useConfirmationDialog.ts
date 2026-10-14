interface ConfirmationOptions {
  title: string
  message: string
  confirmText?: string
  cancelText?: string
}

const confirmation = reactive({
  open: false,
  title: 'Confirm action',
  message: '',
  confirmText: 'Confirm',
  cancelText: 'Cancel',
})

let pendingResolve: ((confirmed: boolean) => void) | null = null

export function useConfirmationDialog() {
  function resolveConfirmation(confirmed: boolean) {
    const resolve = pendingResolve
    pendingResolve = null
    confirmation.open = false
    resolve?.(confirmed)
  }

  function requestConfirmation(options: ConfirmationOptions): Promise<boolean> {
    if (pendingResolve) resolveConfirmation(false)
    Object.assign(confirmation, {
      open: true,
      title: options.title,
      message: options.message,
      confirmText: options.confirmText || 'Confirm',
      cancelText: options.cancelText || 'Cancel',
    })
    return new Promise<boolean>(resolve => { pendingResolve = resolve })
  }

  return { confirmation, requestConfirmation, resolveConfirmation }
}
