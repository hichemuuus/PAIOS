import { useAppStore } from '../../stores/appStore'

/** Live WebSocket connection indicator for the header. */
export function ConnectionIndicator() {
  const connected = useAppStore((s) => s.connected)
  return (
    <div
      className={`flex items-center gap-2 rounded-full border px-2.5 py-1 transition-colors ${
        connected
          ? 'border-ok-500/30 bg-ok-500/10'
          : 'border-bad-500/30 bg-bad-500/10'
      }`}
    >
      <span
        className={`h-2 w-2 rounded-full ${
          connected ? 'bg-ok-500 animate-pulseDot' : 'bg-bad-500'
        }`}
      />
      <span className="hud-label text-ink-600">
        {connected ? 'Connected' : 'Offline'}
      </span>
    </div>
  )
}
