# DIAGNOSTICS.md
# Project Diagnostic & Repair Skill — Master Checklist

Version: 1.0
Author: [Skaldcraft]
Last updated: [Date]

---

## HOW TO USE THIS FILE

1. Drop this file into the root of any project.
2. At the start of each diagnostic session, duplicate `DIAGNOSTIC_REPORT.md` and rename it
   with the date: e.g. `DIAGNOSTIC_REPORT_2026-03-27.md`
3. Work through the relevant sections below. For each item:
   - Note findings in the report using the severity codes defined below.
   - Do NOT modify config files unless the issue is flagged as CRITICAL and you are certain
     of the fix. All config files are treat-as-read-only by default.
4. At the end of the session, fill in the Summary and Suggested Actions in the report.
5. Present findings to the owner and wait for approval before taking any action.

---

## SEVERITY LEVELS

  [C] CRITICAL   — Broken functionality, security risk, data exposure, build failure.
                   Requires immediate attention before any deployment.
  [W] WARNING    — Suboptimal, inconsistent, or potentially problematic. Not urgent
                   but should be resolved before launch or next milestone.
  [S] SUGGESTION — Optimization, cleanup, or best practice. Low risk. Apply when convenient.
  [OK] CONFIRMED — Verified working. No action needed. Worth noting for confidence.

---

## SECTION 0 — STACK DETECTION

Before running any checks, identify the stack and mark which conditional sections apply.

  [ ] Runtime / Language
      - [ ] Node.js / JavaScript / TypeScript
      - [ ] PHP
      - [ ] Python
      - [ ] Other: ___________

  [ ] Framework
      - [ ] Next.js (App Router / Pages Router)
      - [ ] React (CRA, Vite, etc.)
      - [ ] WordPress (theme / plugin / full site)
      - [ ] Express / bare Node
      - [ ] Laravel
      - [ ] Other: ___________

  [ ] Database
      - [ ] None
      - [ ] SQLite
      - [ ] MySQL / MariaDB
      - [ ] PostgreSQL (incl. Supabase)
      - [ ] MongoDB
      - [ ] Other: ___________

  [ ] ORM / Query layer
      - [ ] Prisma
      - [ ] Drizzle
      - [ ] Raw SQL
      - [ ] wpdb (WordPress)
      - [ ] None / other: ___________

  [ ] Hosting / Deployment target
      - [ ] Hostinger (shared / VPS)
      - [ ] Vercel
      - [ ] Netlify
      - [ ] VPS (manual / PM2)
      - [ ] Other: ___________

  [ ] Version control
      - [ ] Git + GitHub
      - [ ] Other: ___________

  [ ] CI/CD
      - [ ] GitHub Actions
      - [ ] Manual deploy
      - [ ] Other: ___________

---

## SECTION 1 — PROJECT STRUCTURE & FILES

  1.1  Root directory is clean — no stray files, temp exports, or test scripts at root level.
  1.2  Folder structure follows the conventions of the identified framework.
  1.3  No duplicate folders or files with redundant purposes.
  1.4  All referenced paths in config files actually exist.
  1.5  `.gitignore` is present and correctly excludes:
       - node_modules / vendor
       - .env and all .env.* variants
       - build/dist output folders
       - OS/editor artifacts (.DS_Store, Thumbs.db, .vscode/settings if sensitive)
  1.6  No sensitive files are committed to the repo (.env, credentials, API keys in code).
  1.7  README.md exists and is not empty or placeholder-only.
  1.8  LICENSE file present (if applicable).
  1.9  No large binary files committed unnecessarily (images, zips, exports).

---

## SECTION 2 — DEPENDENCIES & PACKAGES

  2.1  package.json / composer.json / requirements.txt is present and well-formed.
  2.2  Lock file is present (package-lock.json / yarn.lock / composer.lock).
  2.3  Lock file is committed to the repo.
  2.4  No packages listed in dependencies that should be in devDependencies.
  2.5  No obviously unused top-level packages (check against actual imports in code).
  2.6  No packages with known critical vulnerabilities (run: npm audit / composer audit).
  2.7  No conflicting peer dependency warnings that affect runtime behavior.
  2.8  Scripts in package.json are complete: dev, build, start, lint (at minimum).
  2.9  Node.js / PHP / Python version is specified (engines field, .nvmrc, .tool-versions).

  >> IF WordPress:
  2.W1 All active plugins are up to date (or intentionally pinned with a reason noted).
  2.W2 No inactive/deactivated plugins left installed unnecessarily.
  2.W3 Theme has no pending updates (or is a custom theme under version control).
  2.W4 No Hello Dolly or other default placeholder plugins present.

---

## SECTION 3 — ENVIRONMENT & CONFIGURATION

  NOTE: All .env and config files are READ-ONLY during diagnostics unless flagged [C].

  3.1  .env.example (or .env.sample) exists and lists all required variables (no values).
  3.2  Actual .env file is NOT committed to the repo.
  3.3  All variables referenced in code are present in .env.
  3.4  No hardcoded secrets, tokens, or credentials anywhere in source code.
  3.5  NODE_ENV (or equivalent) is set appropriately for the current environment.
  3.6  No debug flags, verbose logging, or test modes left active for production.
  3.7  API base URLs, database URLs, and external service endpoints are env-driven,
       not hardcoded.
  3.8  Timeout and retry values for external services are explicitly configured.

  >> IF Next.js:
  3.N1 next.config.js / next.config.ts is present and valid.
  3.N2 NEXT_PUBLIC_ prefix used correctly for client-exposed vars only.
  3.N3 No server-only secrets exposed via NEXT_PUBLIC_.
  3.N4 Image domains / remotePatterns configured for all external image sources.
  3.N5 No experimental flags enabled that are not required.

  >> IF WordPress:
  3.W1 wp-config.php has WP_DEBUG set to false (or is env-driven).
  3.W2 Database credentials are not hardcoded in any non-standard location.
  3.W3 ABSPATH and other core constants are defined correctly.
  3.W4 wp-config.php is outside webroot if possible, or protected via .htaccess.
  3.W5 wp-content is in expected location or custom path is correctly configured.

  >> IF Prisma:
  3.P1 schema.prisma is present and well-formed.
  3.P2 DATABASE_URL is in .env and not hardcoded in schema.
  3.P3 No pending migrations (run: npx prisma migrate status).
  3.P4 Prisma client is generated (npx prisma generate has been run).

---

## SECTION 4 — CODE QUALITY & CLEANUP

  4.1  No console.log / var_dump / print_r / dd() statements left in production code paths.
  4.2  No commented-out blocks of significant length left in source files.
  4.3  No TODO / FIXME / HACK comments left unresolved that affect functionality.
  4.4  No dead functions, unused imports, or unreachable code blocks.
  4.5  Consistent naming conventions across files (camelCase, kebab-case, etc.).
  4.6  No test files, mock data, or seed scripts committed in production paths.
  4.7  No placeholder or Lorem Ipsum content left in UI.
  4.8  Error handling is present on all async operations and external calls.
  4.9  No empty catch blocks that silently swallow errors.
  4.10 TypeScript strict mode or equivalent linting is configured (if TS project).
  4.11 Linter config (ESLint, Prettier, PHPCS) is present and consistent.
  4.12 No linter errors or warnings that indicate real code issues (ignoring style-only).

---

## SECTION 5 — DATABASE

  5.1  Database connection is tested and confirmed working.
  5.2  Schema matches the current state of the application (no missing tables/columns).
  5.3  No tables or collections that are never referenced in application code.
  5.4  No columns that are defined but never written to or read from.
  5.5  Indexes exist on all foreign keys and frequently queried columns.
  5.6  No N+1 query patterns visible in main data-fetching code paths.
  5.7  Sensitive data fields (passwords, tokens) are hashed/encrypted, never plain text.
  5.8  Database credentials in production are different from development credentials.
  5.9  Backup strategy is defined (even if manual).

  >> IF Supabase:
  5.S1 Row Level Security (RLS) is enabled on all tables containing user data.
  5.S2 RLS policies are defined — no tables left with RLS enabled but no policies.
  5.S3 Anon key is not used for operations that require authentication.
  5.S4 Service role key is never exposed to the frontend.

  >> IF MySQL / MariaDB (Hostinger):
  5.M1 Remote access is disabled for the database user in production.
  5.M2 User has minimal required privileges (not root).

---

## SECTION 6 — SECURITY

  6.1  Authentication is required on all routes/pages that contain user-specific data.
  6.2  Authorization checks are present (user can only access their own data).
  6.3  Input validation is present on all form fields and API endpoints.
  6.4  No SQL injection vectors (parameterized queries or ORM used throughout).
  6.5  No XSS vectors (user input is sanitized before rendering).
  6.6  CORS is configured and not set to wildcard (*) in production.
  6.7  Rate limiting is present on authentication and public API endpoints.
  6.8  HTTP security headers are configured (X-Frame-Options, CSP, HSTS, etc.).
  6.9  Dependencies have no known critical CVEs (cross-check with Section 2.6).
  6.10 File upload endpoints (if any) validate type, size, and destination.
  6.11 Admin or dashboard routes are protected and not guessable.

  >> IF WordPress:
  6.W1 Default admin username "admin" is not in use.
  6.W2 Login URL is protected or obscured (e.g. WPS Hide Login or equivalent).
  6.W3 XML-RPC is disabled if not needed.
  6.W4 Directory listing is disabled in .htaccess.
  6.W5 wp-config.php and .htaccess are not publicly accessible.

---

## SECTION 7 — PERFORMANCE & OPTIMIZATION

  7.1  Images are optimized (compressed, correct format: WebP preferred).
  7.2  No unused CSS or JS bundles being loaded on every page.
  7.3  Static assets are cached with appropriate cache headers.
  7.4  Fonts are loaded efficiently (preconnect, font-display: swap).
  7.5  No render-blocking resources in the critical path.
  7.6  API responses for list endpoints are paginated, not returning full datasets.
  7.7  Heavy computations or third-party calls are not blocking page render.
  7.8  Build output size is within reasonable bounds (check with build analyzer if needed).

  >> IF Next.js:
  7.N1 Static generation (SSG/ISR) is used where appropriate instead of SSR.
  7.N2 Dynamic imports used for heavy client-side components.
  7.N3 next/image used for all <img> tags to enable automatic optimization.
  7.N4 No unnecessary use of 'use client' directives — server components used by default.
  7.N5 Build output analyzed for unexpected bundle size increases.

  >> IF WordPress:
  7.W1 Caching plugin is active and configured (e.g., LiteSpeed Cache, W3 Total Cache).
  7.W2 Database queries are not running on every page load without caching.
  7.W3 Unnecessary plugins that affect frontend load are deactivated.
  7.W4 CDN is configured for static assets if applicable.

---

## SECTION 8 — UI/UX & FRONTEND

  8.1  All internal links resolve (no 404s on navigation).
  8.2  All external links open in a new tab with rel="noopener noreferrer".
  8.3  All forms submit correctly and show appropriate feedback (success / error states).
  8.4  Loading states are present for async operations visible to the user.
  8.5  Empty states are handled (lists with 0 items show a meaningful message, not blank).
  8.6  Error states are handled and shown to the user in a readable format.
  8.7  Favicon is set and not the framework/tool default.
  8.8  Page title tags are set correctly on all pages (not generic or duplicate).
  8.9  Meta description is present on at least the homepage and key landing pages.
  8.10 404 page is custom and useful (not a raw server error page).
  8.11 Mobile responsiveness is confirmed on at least one narrow breakpoint.
  8.12 No layout overflow or horizontal scroll on mobile viewports.
  8.13 Focus styles are visible for keyboard navigation (basic accessibility).
  8.14 Color contrast meets minimum readability standards (not AA-strict, just readable).
  8.15 No placeholder text like "Your Name Here" or "Insert content" visible in UI.

---

## SECTION 9 — API & INTEGRATIONS

  9.1  All third-party API keys are stored in environment variables.
  9.2  All external integrations have been tested end-to-end in the current environment.
  9.3  Webhook endpoints (if any) validate the source of the request.
  9.4  API error responses are handled gracefully in the frontend.
  9.5  No test/sandbox keys are present in production configuration.
  9.6  Rate limits of third-party services are accounted for in implementation.
  9.7  Payment integrations (if any) are tested with sandbox, not live keys, until launch.

  >> IF OpenAI / DeepSeek or other AI APIs:
  9.A1 API key is in .env and never in frontend code.
  9.A2 Token limits and cost guardrails are implemented (max_tokens set).
  9.A3 User input to prompts is sanitized (no prompt injection vectors).
  9.A4 Streaming responses handled with proper error recovery.
  9.A5 Fallback behavior defined for API downtime or quota exceeded.

---

## SECTION 10 — SEO & DISCOVERABILITY

  10.1 robots.txt is present and correctly configured for the environment
       (noindex in dev/staging, appropriate rules in production).
  10.2 sitemap.xml exists (or is auto-generated) and is linked in robots.txt.
  10.3 Canonical URLs are set on key pages.
  10.4 Open Graph tags (og:title, og:description, og:image) present on key pages.
  10.5 Twitter/X card meta tags present if social sharing is a goal.
  10.6 No duplicate content issues from www vs non-www or http vs https.
  10.7 All pages have unique, descriptive <title> tags.

---

## SECTION 11 — LAUNCH READINESS

  This section is only relevant for pre-launch / production deployment.

  11.1  All items in Sections 1–10 reviewed and no [C] items unresolved.
  11.2  NODE_ENV=production (or equivalent) confirmed for production environment.
  11.3  All debug modes, verbose logging