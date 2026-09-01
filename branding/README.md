# QUEDERA Brand Kit

Single source of truth for QUEDERA product suite colours and design tokens.
Every QUEDERA scaffold (Sentinel, Pulse, Atlas, Beacon, Duet) reads from here.

## Rule

**Palette codes only.** No off-palette colours anywhere in QUEDERA work. If a UI
needs a shade that isn't in the palette, pick the closest palette token and use
an opacity modifier — do **not** introduce a new hex.

Locked by MacWood, 2026-08-26 21:10 BST in `#branding`.

## Files

| File | What it is | Consumers |
|---|---|---|
| `quedera-palette.json` | Canonical metadata + per-product mapping + tokens | Humans / docs |
| `quedera-tokens.css` | CSS variables (RGB channels) for runtime consumption | `globals.css`, any consumer |
| `quedera-tailwind-preset.cjs` | Tailwind theme preset with `<alpha-value>` opacity support | `tailwind.config.*` |

Source assets (kept for stable reference):

| File | Source |
|---|---|
| `quedera-color-palette.png` | MacWood's palette drop, 2026-08-26 21:08 BST |
| `quedera-product-suite-logos.jpg` | MacWood's logo lineup drop, 2026-08-26 21:05 BST |

## Palette

| Token | Hex | Role |
|---|---|---|
| `quedera-navy` | `#0D182A` | QUEDERA master wordmark |
| `quedera-deep-blue` | `#1E3A8A` | ATLAS product brand |
| `quedera-cyan` | `#06B6D4` | PULSE product brand |
| `quedera-violet` | `#7C3AED` | DUET product brand |
| `quedera-amber` | `#F59E0B` | BEACON product brand |
| `quedera-emerald` | `#10B981` | SENTINEL product brand |
| `quedera-surface` | `#F2F4F7` | Universal surface / background |

Five of seven are Tailwind defaults (`blue-900`, `cyan-500`, `violet-600`,
`amber-500`, `emerald-500`); only the two neutrals (`#0D182A`, `#F2F4F7`) are
registered as custom tokens under the `quedera-` prefix.

## Wiring a new product scaffold

1. **CSS variables.** At the top of `app/globals.css`:

   ```css
   @import "../../branding/quedera-tokens.css";
   ```

   (or copy the contents inline if the project can't resolve cross-folder
   `@import`s — see `sentinel/app/globals.css` for either pattern.)

2. **Tailwind preset.** In `tailwind.config.ts`:

   ```ts
   import type { Config } from "tailwindcss";
   import quederaPreset from "../branding/quedera-tailwind-preset.cjs";

   const config: Config = {
     content: [/* ... */],
     theme: { extend: { ...quederaPreset.theme.extend } },
     plugins: [],
   };

   export default config;
   ```

3. **Use palette tokens only.** No `bg-white`, `text-gray-500`,
   `border-blue-300`, etc. Translate them to the closest palette token with an
   opacity if needed (e.g. `bg-quedera-surface`, `text-quedera-navy/70`,
   `border-quedera-navy/30`).

## Opacity modifiers

The Tailwind preset uses the `rgb(var(--token) / <alpha-value>)` pattern, so
opacity modifiers compose natively:

- `bg-quedera-emerald/10` — faint emerald background
- `text-quedera-navy/60` — muted navy text
- `border-quedera-navy/30` — subtle navy outline

## Pre-ship checklist

Before any QUEDERA UI lands:

- [ ] Grep the diff for `(bg|text|border|ring|stroke|fill)-(white|black|slate|gray|zinc|red|orange|yellow|green|emerald|blue|indigo|violet|cyan|sky|amber)` — should be zero.
- [ ] Grep for `#X{3,6}` hex codes — only the seven canonical hex values should appear.
- [ ] Build clean (`npm run build` for Next.js scaffolds).
