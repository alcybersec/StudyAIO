# Rules for services/ui/

## General
- React 18 with functional components only — no class components
- TypeScript for all new files (.tsx/.ts)
- Tailwind CSS for styling — no CSS modules, no styled-components
- React Query (TanStack Query) for all server state — no useEffect for data fetching
- React Router for navigation

## File Organization
- `src/pages/` — one file per route (Dashboard, CoursePage, WeekView, etc.)
- `src/components/` — reusable UI components (Card, Badge, FileUpload, etc.)
- `src/components/layout/` — layout components (Sidebar, Header, MobileNav)
- `src/hooks/` — custom hooks (useUpload, usePipeline, useReviewItems)
- `src/api/` — API client functions (typed, using fetch or axios)
- `src/types/` — shared TypeScript interfaces and types

## Component Rules
- One component per file
- Named exports (not default) for components
- Props interface defined above the component
- Destructure props in the function signature
- Keep components under 150 lines — extract sub-components if larger
- Use `React.memo` only when there's a measured performance problem, not preemptively

## State Management
- Server state: React Query (queries + mutations)
- Local UI state: useState
- Complex local state: useReducer
- No Redux, no Zustand, no global state libraries in v1
- Share state via React Query cache — if two components need the same data, use the same query key

## API Client
- All API calls in `src/api/` with typed request/response
- Use React Query's `useQuery` and `useMutation` hooks
- Handle loading, error, and empty states in every component that fetches data
- Never swallow errors — show user-friendly error messages

## Responsive Design
- Mobile-first Tailwind classes (base = mobile, `md:` = tablet, `lg:` = desktop)
- Test at 375px (phone), 768px (tablet), 1280px (desktop)
- Touch targets minimum 44x44px on mobile
- No horizontal scrolling on any screen size

## Accessibility Basics
- Semantic HTML elements (button, nav, main, article, etc.)
- Alt text on all images
- Keyboard navigable interactive elements
- Visible focus indicators
