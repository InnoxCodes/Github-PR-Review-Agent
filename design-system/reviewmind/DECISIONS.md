# ReviewMind, design decisions on top of MASTER.md

`MASTER.md` was generated with the ui-ux-pro-max skill
(`"developer tool AI code review dashboard dark" --design-system --variance 6 --motion 6 --density 7`).
It is the source of truth; this file records where ReviewMind deliberately departs from it, and why.

## Adopted as generated
- **Style:** Dark Mode (OLED), dark is the default; high contrast, visible focus, minimal glow.
- **Palette core:** accent `#22C55E` with `#0F172A` on-accent text (7.8:1), muted foreground `#94A3B8`,
  destructive red, card `#1B2336` (used as the *raised* surface), muted `#272F42`.
- **Typography:** JetBrains Mono (headings, code, diff) + IBM Plex Sans (UI text).
- **Motion:** staggered list entrances, spring-based, `prefers-reduced-motion` respected.

## Overrides
| Area | MASTER | ReviewMind | Why |
|---|---|---|---|
| Page pattern | FAQ / documentation landing | Single-action tool entry (paste a PR) + recent reviews | The search matched "tool" to documentation; ReviewMind's landing is the product's primary action, not support content. |
| Light mode | "Not recommended" | Supported via toggle, dark default | Required by the product spec. Light tokens were contrast-checked separately (all text ≥ 4.5:1). |
| Page background | `#0F172A` | `#0A0F1C`, cards `#121A2B` | One step deeper so cards separate from the page without heavy borders. |
| Border | `#475569` | `rgb(148 163 184 / 0.13)` hairline, `0.26` strong | `#475569` is too loud for a dense diff/issue UI; hairlines keep the code as the loudest element. |
| Fonts | Google Fonts CDN | Self-hosted via @fontsource | Works offline and avoids a third-party request. |
| Motion easing | `back.out(1.4)` | Critically-damped springs, no overshoot on data | MASTER itself warns against back.out on informational UI. |

## Charts (dataviz skill)
- Categorical series use the reference palette slots 1–6 (blue, orange, aqua, yellow, magenta, green) in
  fixed order, mapped to issue categories. Validated with `validate_palette.js`:
  dark on `#121A2B`, all checks pass (worst adjacent CVD ΔE 8.4, normal-vision 19.3);
  light on `#FFFFFF`, passes, with aqua/yellow/magenta below 3:1 contrast, so every categorical chart
  ships a legend and a table view (the required relief channel).
- Severity and health grade use the reserved status steps (good `#0CA30C`, warning `#FAB219`,
  critical `#D03B3B`) and always appear with an icon and a text label, never colour alone.
- Nominal single-series bars (findings by category) use one hue; the health trend is a single 2px line.
