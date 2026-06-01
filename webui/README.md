# webui — React + Vite + Tailwind + shadcn/ui

Frontend rewrite of the trending-scraper UI. Replaces the previous vanilla
single-file `static/index.html`.

## Stack

- **Vite** — build + dev server
- **React 18** + **TypeScript** (strict mode)
- **Tailwind CSS** with design tokens (HSL variables in `src/index.css`)
- **shadcn/ui** components (Radix-based, source in `src/components/ui/`)
- **lucide-react** for icons
- **sonner** for toasts

No global state library, no router — region is URL-synced, view is in
localStorage. State is lifted to `App.tsx`.

## Development

```bash
# 1. Make sure the FastAPI backend is running
trending123   # or: uvicorn main:app --port 11001

# 2. In another terminal, start Vite dev server
cd webui
npm run dev
# → http://localhost:5173 with HMR
```

Vite proxies `/api/*` to `http://localhost:11001`, so the dev server
behaves like the production backend for fetch calls.

## Production build

```bash
cd webui
npm run build
```

Outputs to `../static/`:
- `static/index.html`
- `static/assets/index.<hash>.js`
- `static/assets/index.<hash>.css`

FastAPI's `app.mount("/static", ...)` serves the assets and `GET /`
returns the HTML. **Restart the FastAPI server is NOT required** — Python
isn't watching the static dir, but `FileResponse(STATIC_DIR / "index.html")`
re-reads from disk each request.

## Project structure

```
webui/
├── src/
│   ├── main.tsx             # React entry
│   ├── App.tsx              # Top-level layout + state
│   ├── index.css            # Tailwind directives + design tokens
│   ├── vite-env.d.ts        # Vite + CSS module declarations
│   ├── components/
│   │   ├── ui/              # shadcn-style primitives
│   │   │   ├── button.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── card.tsx
│   │   │   ├── toggle-group.tsx
│   │   │   ├── select.tsx
│   │   │   ├── skeleton.tsx
│   │   │   └── source-chip.tsx
│   │   ├── header.tsx
│   │   ├── big-story.tsx
│   │   ├── threads-section.tsx
│   │   ├── platform-grid.tsx
│   │   ├── platform-card.tsx
│   │   ├── timeline-view.tsx
│   │   ├── footer.tsx
│   │   └── empty-state.tsx
│   ├── hooks/
│   │   ├── use-region.ts        # URL search-param sync
│   │   ├── use-view.ts          # localStorage view preference
│   │   ├── use-keyboard.ts      # single-key shortcuts
│   │   └── use-trending-data.ts # platforms + per-platform + aggregate
│   ├── lib/
│   │   ├── api.ts           # typed fetch wrapper
│   │   ├── types.ts         # Backend response contracts
│   │   └── utils.ts         # cn() helper + todayISO()
│   └── data/
│       └── platforms.ts     # platform emoji map
├── index.html               # HTML shell (Vite injects scripts/styles here)
├── vite.config.ts           # base, alias, proxy, build output
├── tailwind.config.ts       # token wiring
├── postcss.config.js
├── tsconfig.json / .app.json / .node.json
└── package.json
```

## Design tokens

All tokens are CSS variables in `src/index.css` (HSL triplets, used with
`hsl(var(--...))` so Tailwind opacity modifiers like `bg-primary/20` work).

Tailwind config maps them to utility classes:

| Surfaces | Text | Brand | Semantic |
|---|---|---|---|
| `bg-bg`, `bg-bg-2`, `bg-panel`, `bg-panel-2`, `bg-panel-3`, `border-border`, `border-border-strong` | `text-fg`, `text-fg-strong`, `text-muted`, `text-muted-2` | `text-primary`, `text-primary-strong`, `bg-primary-soft`, `text-accent2` | `success` / `warning` / `danger` / `hot` (each with `-soft` variant) |

Type scale: `text-xs` 11 / `text-sm` 13 / `text-base` 14 / `text-md` 15 / `text-lg` 17 / `text-xl` 20 / `text-2xl` 26 / `text-3xl` 32.

## When to update what

- **Change UI text / copy** → component file
- **Change colors / spacing globally** → `src/index.css` (token values)
- **Change spacing/font sizes** → `tailwind.config.ts`
- **Add a Radix primitive** → `src/components/ui/<name>.tsx`
- **Change API response shape** → `src/lib/types.ts` + `src/lib/api.ts`
- **Add a new component using shadcn pattern** → see `src/components/ui/button.tsx` for the CVA + forwardRef pattern

## Why no shadcn CLI?

We could install the official shadcn CLI to add components, but the project
is small and the components we use are stable. Inlining keeps things simple
and avoids the CLI's components.json overhead.
