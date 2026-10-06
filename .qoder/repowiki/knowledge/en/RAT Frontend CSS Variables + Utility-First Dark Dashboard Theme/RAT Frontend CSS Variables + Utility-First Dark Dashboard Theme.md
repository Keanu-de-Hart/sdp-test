---
kind: frontend_style
name: 'RAT Frontend: CSS Variables + Utility-First Dark Dashboard Theme'
category: frontend_style
scope:
    - '**'
source_files:
    - frontend/src/theme.css
    - frontend/src/components/ui.tsx
    - frontend/package.json
---

## Approach

The RAT frontend is a Vite/React SPA with **no CSS framework** (no Tailwind, no Bootstrap, no CSS-in-JS library). Styling is centralized in a single stylesheet `frontend/src/theme.css` and consumed via plain class names. The design system is built on **CSS custom properties (variables)** defined under `:root`, giving the app a cohesive dark dashboard palette.

There are no preprocessors (no SCSS/Sass), no PostCSS plugins beyond what Vite provides, and no component-scoped stylesheets — all styles live in one file.

## Key Files

- `frontend/src/theme.css` — the entire visual system: design tokens, base resets, layout primitives, and every UI surface (navbar, cards, buttons, tables, badges, toasts, charts, dropzone).
- `frontend/src/components/ui.tsx` — tiny presentational React wrappers (`StatusBadge`, `Progress`, `Empty`, `ErrorNote`, `Loading`, `ChartState`) that compose the CSS classes from `theme.css`.
- `frontend/package.json` — confirms zero styling dependencies; only runtime deps are `react`, `react-dom`, `react-router-dom`, and `echarts` for chart rendering.
- `frontend/index.html` — entry point that imports `theme.css`.

## Design Tokens (from `:root`)

| Token group | Variables | Purpose |
|---|---|---|
| Backgrounds | `--bg`, `--bg-soft`, `--panel`, `--panel-2`, `--panel-3` | Layered dark surfaces used for body, panels, and hover states |
| Borders | `--border`, `--border-soft` | Subtle dividers |
| Text | `--text`, `--text-dim`, `--text-faint` | Three-tier text hierarchy |
| Accent / semantic | `--accent`, `--accent-hi`, `--accent-soft`, `--pos`, `--pos-soft`, `--neg`, `--neg-soft`, `--warn`, `--warn-soft` | Primary blue accent plus positive/negative/warning semantics |
| Typography | `--mono` | Monospace stack for code/sha values |
| Shape & depth | `--radius`, `--radius-sm`, `--shadow` | Rounded corners and card shadows |

Typography defaults: 14px/1.5 system font stack with `-webkit-font-smoothing: antialiased`. A `.mono` utility switches to the monospace stack at 0.92em.

## Architecture & Conventions

- **Single-file stylesheet**: All CSS lives in `theme.css`; there are no per-component stylesheets or CSS modules.
- **BEM-like flat class naming**: Classes are short, descriptive nouns (`card`, `card-header`, `card-body`, `btn`, `badge`, `pill`, `popover`, `filter-bar`, `stat-card`, `chart`, `toasts`, `toast`, `dropzone`, `repo-card`). No nesting convention is enforced by a tool — it's purely author discipline.
- **Utility-first helpers**: Small reusable classes (`row`, `col`, `grid`, `grid.cols-2/3/4`, `section-gap`, `muted`, `faint`, `small`, `ellipsis`, `nowrap`, `mono`) are mixed into components alongside semantic classes.
- **Responsive strategy**: Minimal — a single `@media (max-width: 1100px)` breakpoint collapses grid columns to a single column. There is no mobile-first media-query cascade; the layout targets desktop dashboards with a fixed `max-width: 1440px` container.
- **Component composition**: React components in `components/ui.tsx` map props to existing CSS classes rather than generating inline styles (except for dynamic widths like progress bars). This keeps the visual language centralized in CSS.
- **Semantic color usage**: Components pick variants by appending a modifier class (`badge.pos`, `badge.neg`, `badge.warn`, `toast.error`, `toast.success`, `btn.primary`, `btn.danger`, `btn.sm`, `btn.ghost`).
- **Charts**: Styled via ECharts configuration (in `lib/charts.ts` and `lib/useECharts.ts`) using the same token colors; the `.chart` and `.chart.tall` CSS classes control container sizing.

## Conventions Observed

- New UI surfaces should be added as new class selectors in `theme.css` following the existing naming style (flat, lowercase, hyphenated).
- Semantic meaning (positive/negative/warning) is expressed through modifier classes on top of base classes, not through separate files.
- Layout uses Flexbox and CSS Grid exclusively; no floats or positioning except for the sticky navbar and absolute-positioned popovers/toasts.
- Interactive elements use `transition` on background/border-color for hover states.
- Dark mode is the default and only mode; `color-scheme: dark` is set on native form controls.

## Rules Enforced by Tooling

- None specific to styling. The build script `vite build` runs `tsc --noEmit` before bundling, so TypeScript type errors block the build, but there is no CSS linter (no stylelint, no Prettier config for CSS) visible in `package.json`.
- The absence of any CSS-related devDependencies means adding a framework would require explicit package installation — the current setup effectively constrains the team to vanilla CSS.