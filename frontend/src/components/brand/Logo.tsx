/** Veyron wordmark + geometric V-mark. */

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <div className="flex items-center gap-2.5">
      <Mark size={size} />
      <div className="leading-none">
        <div className="text-[1.15rem] font-medium tracking-[-0.01em] text-ink-900">
          Veyron
        </div>
      </div>
    </div>
  )
}

export function Mark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <defs>
        <linearGradient id="v-gold" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#e8c878" />
          <stop offset="100%" stopColor="#d4a84b" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="#12121c" />
      <path
        d="M7.5 10 L10.5 8.5 L16 21.5 L21.5 8.5 L24.5 10 L17 24 Z"
        fill="url(#v-gold)"
      />
    </svg>
  )
}
