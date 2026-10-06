export async function copyText(text: string): Promise<void> {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch { /* Try the legacy browser path below. */ }
  }

  const focusedElement = document.activeElement as HTMLElement | null
  const activeElement = focusedElement && typeof focusedElement.focus === 'function' ? focusedElement : null
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('aria-hidden', 'true')
  Object.assign(textarea.style, { position: 'fixed', opacity: '0', left: '-9999px', top: '0' })
  document.body.appendChild(textarea)
  try {
    textarea.focus()
    textarea.select()
    if (!document.execCommand('copy')) throw new Error('Copy command failed')
  } finally {
    textarea.remove()
    activeElement?.focus()
  }
}
