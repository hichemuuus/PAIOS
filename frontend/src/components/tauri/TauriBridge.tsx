import { useEffect } from 'react'
import { listen } from '@tauri-apps/api/event'

export function TauriBridge() {
  useEffect(() => {
    const isTauri = typeof window !== 'undefined' && '__TAURI__' in window
    if (!isTauri) return

    let unlistenBackend: (() => void) | undefined
    let unlistenUpdate: (() => void) | undefined
    let unlistenCommand: (() => void) | undefined

    async function setup() {
      unlistenBackend = await listen<string>('backend-status', (event) => {
        const status = event.payload
        if (status === 'running') {
          console.log('[Veyron Desktop] Backend is running')
        } else if (status === 'error') {
          console.error('[Veyron Desktop] Backend failed to start')
        } else if (status === 'unhealthy') {
          console.warn('[Veyron Desktop] Backend is unhealthy')
        }
      })

      unlistenUpdate = await listen<string>('update-available', (event) => {
        console.log(`[Veyron Desktop] Update available: v${event.payload}`)
      })

      unlistenCommand = await listen<string>('engine-command', (event) => {
        const cmd = event.payload
        if (cmd === 'restart') {
          console.log('[Veyron Desktop] Restarting AI engine...')
          window.location.reload()
        }
      })
    }

    setup()

    return () => {
      unlistenBackend?.()
      unlistenUpdate?.()
      unlistenCommand?.()
    }
  }, [])

  return null
}
