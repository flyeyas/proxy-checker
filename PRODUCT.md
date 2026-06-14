# Product

## Register

product

## Users

Users batch-check free proxy lists for general HTTPS access and AI service reachability. They work with large pasted lists, repeated detection runs, saved repositories, cloud sync, and public deployments, so the interface must stay dense, predictable, protected, and fast to operate.

## Product Purpose

Proxy Checker v6.0 is a self-hosted-first proxy checking and repository automation tool. It verifies HTTP, HTTPS, SOCKS4, SOCKS5, and SOCKS5H proxies against a generic target plus optional OpenAI, Grok, Gemini, and Claude profiles. It reports stability, service reachability, API-domain reachability, exit IP, country, IP type, recommended use, and helps users save, re-check, export, sync, schedule, and share usable proxies.

Detection results are deployment-relative. The recommended deployment target is the same server that will actually use the proxies, because a proxy that is reachable from one server may be unreachable from another. The product should explain this clearly instead of implying globally valid proxy quality.

Account registration should not be inferred from a registration-page HTTP probe. Signup success depends on platform risk controls, phone/email inputs, browser state, account history, and timing, so the product should avoid presenting "registration ready" as a proxy quality dimension.

## Brand Personality

Technical, direct, utilitarian. The product should feel like a reliable operations tool, not a landing page or decorative demo.

## Anti-references

Avoid marketing-page composition, decorative cards, oversized hero sections, hidden primary actions, and server-specific defaults that would leak a private deployment into the public GitHub version.

## Design Principles

- Keep repeated workflows one click away.
- Make status and failure reasons visible without extra ceremony.
- Preserve standard controls and predictable button placement.
- Prefer public, portable defaults over private deployment assumptions.
- Keep the UI compact enough for large proxy batches.
- Treat registration-page reachability as out of scope; show network usefulness instead of signup promises.
- Protect operational actions with a configurable login password while keeping generated repository links usable by other programs.
- Keep auto mode backend-driven on self-hosted Python deployments; browser timers must not be the source of truth for scheduled checks.
- Show scheduled times in one explicit plan timezone, never by mixing server-local text with browser-local timestamp formatting.
- Keep run history visible through a product-level log view, not only process logs.
- Make serverless deployments degrade clearly when background scheduling is unavailable.
- On same-origin self-hosted deployments, unauthenticated users should receive only the login page, not the main app shell.
- Treat `config.local.json`, environment variables, logs, repository data, and checked history as deployment-local state.
- Remind users that the meaningful path is their own server to proxy IP to target service.

## Accessibility & Inclusion

Prefer complete, low-friction workflows that do not require manual stitching. Keep actions explicit, labels plain, and controls reachable without relying on hover-only discovery.

## Release Context

v6.0 is the public GitHub release line. It builds on the v5 general-purpose proxy checker by adding backend auto mode, per-token scheduled task persistence, automatic repository maintenance, run logs, global settings, timezone-aware scheduling, serverless degradation messaging, stronger smoke coverage, and clearer release documentation. v5 replaced the old ChatGPT-specific positioning with a general-purpose proxy checking workflow, AI service profiles, dynamic proxy source aggregation, repository filters, refresh-safe detection UI, configurable concurrency, password-protected operations, and usefulness labels instead of registration-page checks.
