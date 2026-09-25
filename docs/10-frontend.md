# 10 · Frontend

React 19 single-page app built with Vite ([`frontend/`](../frontend)). There's no UI
framework: the design system is hand-written CSS ([`styles/tokens.css`](../frontend/src/styles/tokens.css),
[`styles/global.css`](../frontend/src/styles/global.css)), with fonts bundled locally
(Rozha One, Hind, IBM Plex Mono) so the strict CSP needs no external hosts.

**Design idea: the steel thali.** A plan is drawn as an Indian steel plate. Each katori
(bowl) is a meal, sized by its share of the day's calories, arranged in day order and
labelled with its kcal. Colours come from the kitchen: leaf green, turmeric, chilli and curry.

## Pages

| Route | Page | What it shows | Screenshot |
|---|---|---|---|
| `/` | Landing | What the app does, a sample thali, how it works, the cloud architecture as a pipeline | [01](../screenshots/01-landing.png), [12](../screenshots/12-architecture.png) |
| `/register` | Register | Name, email, password with inline validation; then goes straight to the profile | [02](../screenshots/02-register.png) |
| `/login` | Login | Email and password; returns you to the page you were trying to open | – |
| `/profile` | User profile | Demo fields with ranges; allergy chips; saves with feedback | [04](../screenshots/04-profile.png) |
| `/generate` | Generate plan | Diet, goal, allergies and cuisine for this plan only; AI toggle when configured; calculated targets preview | [05](../screenshots/05-generate-plan.png) |
| `/plans/:id` | Plan result | Thali, calorie total, macro meters vs targets, hydration, meal cards with "why", tips, engine badge, export and save to cloud | [06](../screenshots/06-plan-result.png), [07](../screenshots/07-plan-meals.png) |
| `/plans` | Saved plans | Table of plans (newest first), open or delete | [08](../screenshots/08-saved-plans.png) |
| `/files` | Cloud files | Drag-and-drop upload, previews of images, download, delete, quota usage | [09](../screenshots/09-cloud-files.png) |
| `/dashboard` | Dashboard | Welcome, current goal and diet, latest plan, previous plans, generate button, uploaded files, cloud status, logout | [03](../screenshots/03-dashboard.png), [10 (mobile)](../screenshots/10-mobile-dashboard.png) |
| `*` | 404 | Friendly not-found page | – |

## Code structure

```text
src/
├── main.jsx, App.jsx         router, AuthProvider, layout
├── pages/                    one component per route (above)
├── components/               Navbar, Footer, AppLayout, RouteGuards, Thali, MealCard, MacroMeters,
│                             SourceBadge, UploadDropzone, FileTile, CloudStatusPanel, Disclaimer,
│                             FormControls, Alert, Loader, EmptyState, PageHeader, Icon
├── context/AuthContext.jsx   current user, login/register/logout, 401 handling
├── services/                 apiClient.js (fetch wrapper) + one module per API area
├── hooks/                    useDocumentTitle, useFilePreview (authenticated image previews)
├── utils/                    format.js, options.js (labels), thaliLayout.js (geometry), download.js
└── styles/                   tokens.css (colours, type, spacing), global.css
```

## How the frontend talks to the cloud

- [`apiClient.js`](../frontend/src/services/apiClient.js) is the only place that calls
  `fetch`. It:
  - adds `Authorization: Bearer <token>`;
  - turns error bodies into `ApiError(code, message, status, requestId)`;
  - reports a 401 on a signed-in request so the app logs out cleanly;
  - handles downloads.
- **Base URL:** empty in development (Vite proxies `/api` to port 8000) and when the API
  serves the app; `VITE_API_BASE_URL` when the API is on another domain.
- **Images** are private, so `<img src="/api/files/…">` can't send the token. Instead
  `useFilePreview` fetches the bytes with the token and shows them via a temporary `blob:`
  URL, which is released on unmount.
- **The cloud status panel** reads `/api/health/ready` and `/api/system/status` to show which
  database, storage and AI provider the deployment is using.

## Quality

- **Responsive**: grids collapse at set breakpoints, container queries handle the thali
  legend, and every page was checked at 375 px and 1366 px.
- **Accessible**: labelled form controls, visible focus, alerts announced to screen readers
  (`role="alert"` / `role="status"`), sufficient
  contrast, reduced-motion support, and a text legend for the thali.
- **Tests**: 31 Vitest tests for the API client (errors, tokens, downloads), formatting and
  thali geometry. `npm test` runs them.
- **Build**: `npm run build` produces fingerprinted assets in `frontend/dist`. CI builds on
  every push.

## Run

```bash
npm --prefix frontend ci
npm --prefix frontend run dev      # http://localhost:5173
npm --prefix frontend test
npm --prefix frontend run build
```
