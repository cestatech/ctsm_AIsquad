# Dependency Cleanup Report

**Date:** 2026-06-12  
**Scope:** Frontend (`frontend/package.json`) and Backend (`backend/requirements.txt`)

---

## Frontend Dependencies

### Removed (unused — zero imports in `frontend/src/`)

| Package | Version | Reason |
|---------|---------|--------|
| `clsx` | ^2.1.1 | Never imported |
| `tailwind-merge` | ^2.5.3 | Never imported |
| `react-hook-form` | ^7.53.0 | Never imported |
| `zod` | ^3.23.8 | Never imported |
| `@hookform/resolvers` | ^3.9.0 | Depends on unused form stack |
| `@tanstack/react-query-devtools` | ^5.59.0 | Not wired in `QueryProvider.tsx` |
| `@testing-library/react` | ^16.0.1 | No RTL component tests |
| `@testing-library/user-event` | ^14.5.2 | No RTL component tests |

**Estimated bundle/install reduction:** ~8 packages removed from dependency tree.

### Retained (actively used)

| Package | Usage |
|---------|-------|
| `@tanstack/react-query` | All data-fetching pages |
| `date-fns` | `GraphNodeDetailPanel.tsx` |
| `lucide-react` | Submission and select pages |
| `next`, `react`, `react-dom` | Framework |
| `reactflow` | Context graph canvas |
| `zustand` | Auth and intelligence study stores |

### Dev dependencies retained

| Package | Usage |
|---------|-------|
| `@playwright/test` | E2E tests in `frontend/e2e/` |
| `vitest` | Unit tests (`*.test.ts`) |
| `typescript`, `eslint`, `tailwindcss`, etc. | Build toolchain |

### Recommendations (not implemented)

| Action | Rationale |
|--------|-----------|
| Wire React Query Devtools behind `NODE_ENV === 'development'` | Useful for debugging if re-added |
| Add `react-hook-form` + `zod` when forms are refactored | Currently all forms use controlled state |
| Consider replacing `date-fns` with `Intl.RelativeTimeFormat` | Used in only one file |

### Lockfile

Run `pnpm install` in `frontend/` to update `pnpm-lock.yaml` after package removals.

---

## Backend Dependencies

### Audit Results

All packages in `backend/requirements.txt` are actively used:

| Package | Used By |
|---------|---------|
| `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings` | Core framework |
| `sqlalchemy`, `asyncpg`, `alembic` | Database |
| `python-jose`, `bcrypt`, `passlib` | Auth |
| `httpx`, `anyio` | HTTP client / async |
| `redis` | Caching (configured) |
| `jsonpatch` | Artifact versioning diffs |
| `anthropic` | AI generation and intake |
| `fastapi-mail`, `Jinja2` | Email templates |
| `python-multipart` | File uploads |
| `python-dateutil` | Date parsing |
| `pytest*` , `factory-boy` | Testing |
| `openpyxl` | XLSX upload parsing |
| `python-docx`, `reportlab` | Document export |
| `pandas`, `pyreadstat` | XPT/CDISC export |

### Issues Found

| Issue | Severity | Action |
|-------|----------|--------|
| `httpx==0.27.2` listed twice | Low | Remove duplicate line in future edit |
| No `ruff` in requirements | Low | Lint run via system or CI, not venv |

### Duplicate Packages

| Duplicate | Status |
|-----------|--------|
| `httpx` (lines 18 and 43) | **Documented** — same version, harmless |

### Abandoned Packages

None identified. All pinned versions are current and maintained.

### Recommendations (not implemented)

| Action | Rationale |
|--------|-----------|
| Add `ruff` to dev requirements | Consistent local linting |
| Pin `openpyxl` exact version | Currently `>=3.1.0` — consider `==3.1.5` |
| Evaluate `passlib` necessity | `bcrypt` used directly in security module |

---

## Summary

| Area | Before | After | Removed |
|------|--------|-------|---------|
| Frontend production deps | 14 | 8 | 6 |
| Frontend dev deps | 11 | 9 | 2 |
| Backend deps | 24 lines | 24 lines | 0 |

No backend packages were removed — all are in active use.
