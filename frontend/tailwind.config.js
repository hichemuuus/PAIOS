/** @type {import('tailwindcss').Config} */
//
// PAIOS — Atelier design system.
// A warm, premium "intelligent companion" aesthetic: paper canvas, white cards
// with soft shadows, a terracotta-clay primary accent, and editorial display
// type (Fraunces) paired with Inter for UI and JetBrains Mono for data.
//
// Token names are preserved from the previous dark theme (ink / sig / ok / warn
// / bad / violet) so semantic utility classes keep working across the app; only
// their underlying values change. The `ink` neutral ramp now runs light→dark in
// the standard Tailwind direction (50 = lightest, 950 = darkest).
//
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Warm-stone neutral ramp. 50 = cream paper, 950 = near-black ink.
        // Border/surface utilities below were tuned for calm legibility.
        ink: {
          50: '#FBF8F3',
          100: '#F4EEE3',
          200: '#E9DFCE',
          300: '#D8C9B2',
          400: '#B7A489',
          500: '#95815F',
          600: '#6E5C41',
          700: '#504230',
          800: '#332921',
          900: '#221A14',
          950: '#14100B',
        },
        // Page surfaces.
        paper: '#FAF7F2', // primary app background — warm paper.
        cream: '#F3EDE3', // inset / secondary surface.
        // Primary signal — clay / terracotta. Warm, human, memorable.
        sig: {
          50: '#FBF1ED',
          100: '#F6E0D6',
          200: '#ECC2B0',
          300: '#E0A187',
          400: '#D17E58',
          500: '#C75D3A', // base accent
          600: '#A94A2D',
          700: '#883A24',
          800: '#6A2E1E',
          900: '#4F2317',
          950: '#2E150E',
        },
        // Status tones — softened, warm-leaning (calm, not alarmist).
        ok: { 400: '#5B9E7A', 500: '#3F8765', 600: '#2F6B4F' }, // sage
        warn: { 400: '#D6A24A', 500: '#C2882E', 600: '#9F6E20' }, // amber
        bad: { 400: '#D06B6B', 500: '#BE4D4D', 600: '#9E3838' }, // rose
        violet: { 400: '#8E7BB8', 500: '#715FA0' }, // muted plum
      },
      fontFamily: {
        // Editorial display serif for headings + wordmark; Inter for UI;
        // JetBrains Mono for data / code / micro-labels.
        display: ['Fraunces', 'Georgia', '"Times New Roman"', 'serif'],
        sans: ['Inter', 'system-ui', '"Segoe UI"', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SF Mono"', 'Menlo', 'Consolas', 'monospace'],
      },
      fontSize: {
        // Display sizes for expressive headings.
        'display-sm': ['1.625rem', { lineHeight: '1.15', letterSpacing: '-0.01em' }],
        'display': ['2rem', { lineHeight: '1.1', letterSpacing: '-0.015em' }],
        'display-lg': ['2.75rem', { lineHeight: '1.05', letterSpacing: '-0.02em' }],
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.25rem',
      },
      boxShadow: {
        // Soft, layered, warm — the signature elevation language.
        card: '0 1px 2px rgba(40,28,18,0.04), 0 4px 12px -4px rgba(40,28,18,0.06)',
        'card-lg': '0 2px 4px rgba(40,28,18,0.04), 0 12px 32px -10px rgba(40,28,18,0.10)',
        soft: '0 1px 2px rgba(40,28,18,0.05)',
        ring: '0 0 0 3px rgba(199,93,58,0.15)',
        // Kept for legacy "glow" usages — now a gentle warm halo, not neon.
        glow: '0 0 0 1px rgba(199,93,58,0.18), 0 6px 20px -10px rgba(199,93,58,0.30)',
        'glow-ok': '0 0 0 1px rgba(63,135,101,0.20), 0 6px 18px -10px rgba(63,135,101,0.30)',
        'glow-bad': '0 0 0 1px rgba(190,77,77,0.20), 0 6px 18px -10px rgba(190,77,77,0.30)',
      },
      keyframes: {
        pulseDot: {
          '0%,100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.45', transform: 'scale(0.82)' },
        },
        sweep: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(400%)' },
        },
        riseIn: {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        spinSlow: { to: { transform: 'rotate(360deg)' } },
        // Atelier additions.
        fadeUp: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        breathe: {
          '0%,100%': { transform: 'scale(1)', opacity: '0.85' },
          '50%': { transform: 'scale(1.06)', opacity: '1' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        pulseDot: 'pulseDot 1.4s ease-in-out infinite',
        sweep: 'sweep 1.6s ease-in-out infinite',
        riseIn: 'riseIn 0.28s ease-out both',
        spinSlow: 'spinSlow 2.4s linear infinite',
        fadeUp: 'fadeUp 0.4s ease-out both',
        breathe: 'breathe 4s ease-in-out infinite',
        shimmer: 'shimmer 2s linear infinite',
      },
    },
  },
  plugins: [],
}
