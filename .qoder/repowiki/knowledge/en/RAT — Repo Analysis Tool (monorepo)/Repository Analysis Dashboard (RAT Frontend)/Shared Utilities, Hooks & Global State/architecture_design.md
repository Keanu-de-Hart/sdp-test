Two sibling sub-trees with a clear dependency direction: `state/` depends on `lib/`, never the reverse.

- `lib/` is a flat collection of framework-agnostic utilities and React hooks:
  - Pure helpers: `format.ts` (number/date formatters), `time.ts` (UTC day-bucketing, granularity conversion), `csv.ts` (Blob-based CSV download), `charts.ts` (ECharts palette, axis/tooltip base styles, diverging color).
  - Data-fetching hooks in `hooks.ts`: `useRepo` (polls repo status while active), `useMetrics` (SWR-style cached fetch with debounced filter key via `useDebouncedValue`), `useAuthors`, plus `useClickOutside` for dropdown panels.
  - UI hooks: `useECharts.ts` wraps ECharts with lazy init, ResizeObserver-driven resize, event forwarding, and disposal; `useDebounced.ts` provides a generic debounced value hook.
- `state/` exposes two React Context providers consumed app-wide:
  - `FiltersContext.tsx` — centralizes dashboard filters (`start`, `end`, `commits`, `authors`, `path`, `type`, `gran`) backed by `react-router-dom`'s `useSearchParams`; serializes/deserializes to URL query params and derives backend-facing `MetricsFilters` (`apiFilters`).
  - `ToastContext.tsx` — lightweight success/error/info notification system with auto-dismiss after 5.2s.

External dependencies flow inward only: `lib/hooks.ts` calls `../api` and types from `../types`; `state/FiltersContext.tsx` imports `../lib/time` and `../types`. No component code lives here — it is purely reusable primitives.