# Program: magi_pact - web_runtime.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Validates modern CSS, accessible HTML and TypeScript samples with structural checks and no runtime dependencies.

"""Web & Modern Runtime Engineering Engine.

Validates and locks in:
- Modern CSS Layouts: Holy-grail named grid areas, fluid typography clamp(), @media print, and cascade specificity
- Accessible Semantic HTML: <dialog> modal workflows, form role="search" with input type="search", ARIA landmarks
- Modern TypeScript & Node 26: satisfies operator, discriminated unions, generic type constraints, native type stripping (--experimental-strip-types)

Provides structural validation with zero runtime dependencies.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

@dataclass
class WebComponentSpec:
    """Specification for one web-runtime validation case."""
    spec_id: str
    kind: str  # "css" | "html" | "typescript"
    title: str
    code_snippet: str
    validation_rules: List[str]
    description: str

WEB_SPECS: List[WebComponentSpec] = [
    WebComponentSpec(
        spec_id="CSS-HOLY-GRAIL-01",
        kind="css",
        title="Modern CSS Holy Grail Layout with Named Grid Areas and Responsive Sidebar",
        code_snippet=(
            ".holy-grail-layout {\n"
            "  display: grid;\n"
            "  grid-template-areas:\n"
            "    \"header header header\"\n"
            "    \"nav main aside\"\n"
            "    \"footer footer footer\";\n"
            "  grid-template-columns: minmax(200px, 260px) 1fr minmax(200px, 260px);\n"
            "  grid-template-rows: auto 1fr auto;\n"
            "  min-height: 100vh;\n"
            "  gap: 1rem;\n"
            "}\n\n"
            ".site-header { grid-area: header; }\n"
            ".site-nav    { grid-area: nav; }\n"
            ".site-main   { grid-area: main; }\n"
            ".site-aside  { grid-area: aside; }\n"
            ".site-footer { grid-area: footer; }\n\n"
            "@media (max-width: 768px) {\n"
            "  .holy-grail-layout {\n"
            "    grid-template-areas:\n"
            "      \"header\"\n"
            "      \"nav\"\n"
            "      \"main\"\n"
            "      \"aside\"\n"
            "      \"footer\";\n"
            "    grid-template-columns: 1fr;\n"
            "  }\n"
            "}\n"
        ),
        validation_rules=[
            "display: grid",
            "grid-template-areas",
            "nav main aside",
            "min-height: 100vh",
            "@media (max-width: 768px)"
        ],
        description="Responsive 3-column holy grail grid layout using named template areas and mobile stack collapse."
    ),
    WebComponentSpec(
        spec_id="CSS-FLUID-TYPE-01",
        kind="css",
        title="Fluid Typography with clamp() and Dynamic Viewport Scaling",
        code_snippet=(
            ":root {\n"
            "  --font-base: clamp(1rem, 0.75rem + 1.25vw, 1.25rem);\n"
            "  --font-h1: clamp(2rem, 1.5rem + 2.5vw, 3.5rem);\n"
            "  --font-h2: clamp(1.5rem, 1.25rem + 1.5vw, 2.25rem);\n"
            "  --space-unit: clamp(0.5rem, 0.25rem + 1vw, 1.5rem);\n"
            "}\n\n"
            "body {\n"
            "  font-size: var(--font-base);\n"
            "  line-height: 1.6;\n"
            "}\n\n"
            "h1 {\n"
            "  font-size: var(--font-h1);\n"
            "  line-height: 1.2;\n"
            "  letter-spacing: -0.02em;\n"
            "}\n\n"
            "h2 {\n"
            "  font-size: var(--font-h2);\n"
            "  line-height: 1.3;\n"
            "}\n"
        ),
        validation_rules=[
            "clamp(",
            "--font-base",
            "--font-h1",
            "--font-h2",
            "var(--font-base)"
        ],
        description="Dynamic fluid typography and spacing scale using CSS clamp functions across viewports."
    ),
    WebComponentSpec(
        spec_id="CSS-PRINT-MEDIA-01",
        kind="css",
        title="High-Contrast Print Stylesheet with Page Break and URL Disclosure Controls",
        code_snippet=(
            "@media print {\n"
            "  @page {\n"
            "    margin: 20mm;\n"
            "    size: auto;\n"
            "  }\n"
            "  *, *::before, *::after {\n"
            "    background: transparent !important;\n"
            "    color: #000 !important;\n"
            "    box-shadow: none !important;\n"
            "    text-shadow: none !important;\n"
            "  }\n"
            "  body {\n"
            "    font-size: 12pt;\n"
            "    line-height: 1.4;\n"
            "    color: #000;\n"
            "  }\n"
            "  nav, aside, .skip-link, button, form, .no-print {\n"
            "    display: none !important;\n"
            "  }\n"
            "  h1, h2, h3, h4, h5, h6 {\n"
            "    break-after: avoid;\n"
            "    page-break-after: avoid;\n"
            "  }\n"
            "  p, blockquote {\n"
            "    orphans: 3;\n"
            "    widows: 3;\n"
            "  }\n"
            "  pre, blockquote, table, img, figure {\n"
            "    break-inside: avoid;\n"
            "    page-break-inside: avoid;\n"
            "  }\n"
            "  a[href^=\"http\"]::after {\n"
            "    content: \" (\" attr(href) \")\";\n"
            "    font-size: 0.85em;\n"
            "    word-break: break-all;\n"
            "  }\n"
            "  .print-only {\n"
            "    display: block !important;\n"
            "  }\n"
            "}\n"
        ),
        validation_rules=[
            "@media print",
            "@page",
            "display: none !important",
            "break-inside: avoid",
            "attr(href)",
            "orphans: 3"
        ],
        description="Production print media stylesheet guaranteeing ink-conserving high contrast, link disclosure, and pagination."
    ),
    WebComponentSpec(
        spec_id="CSS-CASCADE-SPECIFICITY-01",
        kind="css",
        title="Modern Cascade Layers (@layer) and Specificity Isolation with :where() and :is()",
        code_snippet=(
            "@layer reset, base, layout, components, utilities;\n\n"
            "@layer reset {\n"
            "  *, *::before, *::after {\n"
            "    box-sizing: border-box;\n"
            "    margin: 0;\n"
            "    padding: 0;\n"
            "  }\n"
            "}\n\n"
            "@layer base {\n"
            "  body {\n"
            "    font-family: system-ui, -apple-system, sans-serif;\n"
            "    color: #1a1a1a;\n"
            "    background-color: #fafafa;\n"
            "  }\n"
            "}\n\n"
            "@layer components {\n"
            "  /* :where() gives 0-0-0 specificity: highly overridable defaults */\n"
            "  :where(.btn, .card, .badge) {\n"
            "    border-radius: 0.375rem;\n"
            "    transition: background-color 150ms ease;\n"
            "  }\n"
            "  /* :is() takes the specificity of its most specific argument */\n"
            "  :is(header, footer, main) > .content-wrapper {\n"
            "    max-width: 1200px;\n"
            "    margin-inline: auto;\n"
            "  }\n"
            "  .btn {\n"
            "    display: inline-flex;\n"
            "    padding: 0.5rem 1rem;\n"
            "    background: #2563eb;\n"
            "    color: #fff;\n"
            "  }\n"
            "}\n\n"
            "@layer utilities {\n"
            "  .u-hidden {\n"
            "    display: none;\n"
            "  }\n"
            "}\n"
        ),
        validation_rules=[
            "@layer reset, base, layout, components, utilities;",
            "@layer reset",
            "@layer components",
            ":where(",
            ":is("
        ],
        description="Cascade management using @layer definitions and specificity tuning with :where() and :is()."
    ),
    WebComponentSpec(
        spec_id="HTML-DIALOG-MODAL-01",
        kind="html",
        title="Native HTML5 <dialog> with Form Method Dialog and Accessible Focus Trapping",
        code_snippet=(
            "<dialog id=\"confirm-dialog\" aria-labelledby=\"dialog-title\" aria-describedby=\"dialog-desc\">\n"
            "  <form method=\"dialog\" class=\"dialog-form\">\n"
            "    <header class=\"dialog-header\">\n"
            "      <h2 id=\"dialog-title\">Confirm Deployment</h2>\n"
            "    </header>\n"
            "    <main class=\"dialog-body\">\n"
            "      <p id=\"dialog-desc\">Deploy model weights to production cluster?</p>\n"
            "    </main>\n"
            "    <footer class=\"dialog-footer\">\n"
            "      <button type=\"submit\" value=\"cancel\" formnovalidate class=\"btn btn-secondary\">Cancel</button>\n"
            "      <button type=\"submit\" value=\"confirm\" class=\"btn btn-primary\">Deploy</button>\n"
            "    </footer>\n"
            "  </form>\n"
            "</dialog>\n\n"
            "<script>\n"
            "  const dialog = document.getElementById('confirm-dialog');\n"
            "  dialog.addEventListener('click', (event) => {\n"
            "    const rect = dialog.getBoundingClientRect();\n"
            "    const isInDialog = (\n"
            "      rect.top <= event.clientY && event.clientY <= rect.top + rect.height &&\n"
            "      rect.left <= event.clientX && event.clientX <= rect.left + rect.width\n"
            "    );\n"
            "    if (!isInDialog) dialog.close('dismissed');\n"
            "  });\n"
            "</script>\n"
        ),
        validation_rules=[
            "<dialog",
            "method=\"dialog\"",
            "aria-labelledby",
            "aria-describedby",
            "formnovalidate"
        ],
        description="Accessible modal dialog using HTML5 native <dialog> element and form submission."
    ),
    WebComponentSpec(
        spec_id="HTML-SEARCH-FORM-01",
        kind="html",
        title="Accessible Semantic Search Form with role=\"search\" and input type=\"search\"",
        code_snippet=(
            "<form role=\"search\" action=\"/search\" method=\"get\" class=\"search-form\" aria-label=\"Documentation Search\">\n"
            "  <label for=\"site-search-input\" class=\"visually-hidden\">Search technical documentation</label>\n"
            "  <div class=\"search-input-wrapper\">\n"
            "    <svg class=\"search-icon\" aria-hidden=\"true\" viewBox=\"0 0 24 24\" width=\"20\" height=\"20\">\n"
            "      <circle cx=\"11\" cy=\"11\" r=\"8\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" />\n"
            "      <line x1=\"21\" y1=\"21\" x2=\"16.65\" y2=\"16.65\" stroke=\"currentColor\" stroke-width=\"2\" />\n"
            "    </svg>\n"
            "    <input\n"
            "      type=\"search\"\n"
            "      id=\"site-search-input\"\n"
            "      name=\"q\"\n"
            "      placeholder=\"Search specs, components, APIs...\"\n"
            "      autocomplete=\"off\"\n"
            "      spellcheck=\"false\"\n"
            "      enterkeyhint=\"search\"\n"
            "      required\n"
            "      minlength=\"2\"\n"
            "      aria-autocomplete=\"list\"\n"
            "    />\n"
            "    <button type=\"reset\" class=\"search-clear-btn\" aria-label=\"Clear search input\">\n"
            "      <span aria-hidden=\"true\">&times;</span>\n"
            "    </button>\n"
            "    <button type=\"submit\" class=\"search-submit-btn\">\n"
            "      <span>Search</span>\n"
            "    </button>\n"
            "  </div>\n"
            "</form>\n"
        ),
        validation_rules=[
            "<form role=\"search\"",
            "type=\"search\"",
            "enterkeyhint=\"search\"",
            "visually-hidden",
            "aria-autocomplete=\"list\""
        ],
        description="Semantic HTML5 search interface with landmark role, accessible labeling, and search input constraints."
    ),
    WebComponentSpec(
        spec_id="HTML-LANDMARK-NAV-01",
        kind="html",
        title="Complete HTML5 Semantic Landmark Navigation with Skip Links and Breadcrumbs",
        code_snippet=(
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>Pact Mesh Architecture - Technical Overview</title>\n"
            "  <style>\n"
            "    .skip-link {\n"
            "      position: absolute;\n"
            "      top: -40px;\n"
            "      left: 0;\n"
            "      background: #000;\n"
            "      color: #fff;\n"
            "      padding: 8px 16px;\n"
            "      z-index: 100;\n"
            "      transition: top 0.2s;\n"
            "    }\n"
            "    .skip-link:focus { top: 0; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <a href=\"#main-content\" class=\"skip-link\">Skip to main content</a>\n\n"
            "  <header role=\"banner\" class=\"site-header\">\n"
            "    <div class=\"brand-logo\">Magi Pact Mesh</div>\n"
            "    <nav aria-label=\"Primary navigation\" class=\"primary-nav\">\n"
            "      <ul>\n"
            "        <li><a href=\"/\" aria-current=\"page\">Home</a></li>\n"
            "        <li><a href=\"/specs\">Specs</a></li>\n"
            "        <li><a href=\"/status\">Mesh Status</a></li>\n"
            "      </ul>\n"
            "    </nav>\n"
            "  </header>\n\n"
            "  <nav aria-label=\"Breadcrumb\" class=\"breadcrumbs\">\n"
            "    <ol>\n"
            "      <li><a href=\"/\">Home</a></li>\n"
            "      <li><a href=\"/specs\">Specs</a></li>\n"
            "      <li aria-current=\"page\">Architecture</li>\n"
            "    </ol>\n"
            "  </nav>\n\n"
            "  <main id=\"main-content\" tabindex=\"-1\" class=\"site-main\">\n"
            "    <h1>Architecture Overview</h1>\n"
            "    <p>Federated 32-seat multi-agent mesh protocol documentation.</p>\n"
            "  </main>\n\n"
            "  <aside aria-label=\"Related specifications\" class=\"site-aside\">\n"
            "    <h2>Related Documents</h2>\n"
            "    <ul>\n"
            "      <li><a href=\"/specs/protocol\">Protocol v1.0.0</a></li>\n"
            "    </ul>\n"
            "  </aside>\n\n"
            "  <footer role=\"contentinfo\" class=\"site-footer\">\n"
            "    <p>&copy; 2026 Magi Pact Mesh. All rights reserved.</p>\n"
            "  </footer>\n"
            "</body>\n"
            "</html>\n"
        ),
        validation_rules=[
            "class=\"skip-link\"",
            "<header role=\"banner\"",
            "<nav aria-label=\"Primary navigation\"",
            "<main id=\"main-content\"",
            "<footer role=\"contentinfo\"",
            "aria-current=\"page\""
        ],
        description="Comprehensive accessible landmark skeleton featuring skip navigation, primary nav, breadcrumbs, and main."
    ),
    WebComponentSpec(
        spec_id="TS-SATISFIES-CONFIG-01",
        kind="typescript",
        title="TypeScript 5.x 'satisfies' Operator with Discriminated Unions and Exhaustive Matching",
        code_snippet=(
            "export interface AgentConfig {\n"
            "  readonly seatId: number;\n"
            "  readonly model: string;\n"
            "  readonly vramLimitMb: number;\n"
            "  readonly roles: readonly ('compiler' | 'systems' | 'web' | 'lora')[];\n"
            "}\n\n"
            "export const SEAT_SETTINGS = {\n"
            "  seatId: 3,\n"
            "  model: 'qwen3.5-9b-abli',\n"
            "  vramLimitMb: 7372,\n"
            "  roles: ['compiler', 'lora'] as const,\n"
            "} satisfies AgentConfig;\n\n"
            "export type MeshEvent =\n"
            "  | { kind: 'HEARTBEAT'; seat: number; timestamp: string }\n"
            "  | { kind: 'CLAIM'; seat: number; path: string; intent: string }\n"
            "  | { kind: 'RELEASE'; seat: number; path: string };\n\n"
            "export function formatEvent(event: MeshEvent): string {\n"
            "  switch (event.kind) {\n"
            "    case 'HEARTBEAT': return `[HB] Seat ${event.seat}`;\n"
            "    case 'CLAIM':     return `[LOCK] Seat ${event.seat} -> ${event.path}`;\n"
            "    case 'RELEASE':   return `[FREE] Seat ${event.seat} -> ${event.path}`;\n"
            "    default: {\n"
            "      const _exhaustive: never = event;\n"
            "      throw new Error(`Unhandled event: ${_exhaustive}`);\n"
            "    }\n"
            "  }\n"
            "}\n"
        ),
        validation_rules=[
            "satisfies AgentConfig",
            "as const",
            "const _exhaustive: never",
            "switch (event.kind)"
        ],
        description="Type-safe configuration with satisfies operator and exhaustive discriminated union matching."
    ),
    WebComponentSpec(
        spec_id="TS-DISCRIMINATED-UNION-01",
        kind="typescript",
        title="Discriminated Union Event Processing with Compile-Time Exhaustive Checks",
        code_snippet=(
            "export interface HeartbeatPayload {\n"
            "  readonly seatId: number;\n"
            "  readonly status: 'active' | 'stale';\n"
            "  readonly timestampEpoch: number;\n"
            "}\n\n"
            "export interface LockAcquiredPayload {\n"
            "  readonly seatId: number;\n"
            "  readonly resourcePath: string;\n"
            "  readonly leaseEpoch: number;\n"
            "}\n\n"
            "export interface TaskDispatchedPayload {\n"
            "  readonly taskId: string;\n"
            "  readonly seatId: number;\n"
            "  readonly payloadJson: string;\n"
            "}\n\n"
            "export type MeshProtocolEvent =\n"
            "  | { readonly kind: 'HEARTBEAT'; readonly data: HeartbeatPayload }\n"
            "  | { readonly kind: 'LOCK_ACQUIRED'; readonly data: LockAcquiredPayload }\n"
            "  | { readonly kind: 'TASK_DISPATCHED'; readonly data: TaskDispatchedPayload };\n\n"
            "export function assertNever(x: never, message?: string): never {\n"
            "  throw new Error(message ?? `Unexpected unreachable value: ${JSON.stringify(x)}`);\n"
            "}\n\n"
            "export function processMeshEvent(event: MeshProtocolEvent): string {\n"
            "  switch (event.kind) {\n"
            "    case 'HEARTBEAT':\n"
            "      return `[HB] Seat ${event.data.seatId} is ${event.data.status}`;\n"
            "    case 'LOCK_ACQUIRED':\n"
            "      return `[LOCK] Seat ${event.data.seatId} locked ${event.data.resourcePath}`;\n"
            "    case 'TASK_DISPATCHED':\n"
            "      return `[TASK] Task ${event.data.taskId} dispatched to Seat ${event.data.seatId}`;\n"
            "    default:\n"
            "      return assertNever(event);\n"
            "  }\n"
            "}\n"
        ),
        validation_rules=[
            "readonly kind:",
            "assertNever(x: never",
            "switch (event.kind)",
            "case 'HEARTBEAT':"
        ],
        description="Protocol event handling using discriminated unions and unreachable compile-time assertNever branch verification."
    ),
    WebComponentSpec(
        spec_id="TS-GENERIC-CONSTRAINTS-01",
        kind="typescript",
        title="Advanced Generic Type Constraints with 'extends', 'keyof', and Const Type Parameters",
        code_snippet=(
            "export type Primitive = string | number | boolean | bigint | symbol | null | undefined;\n\n"
            "export type DeepReadonly<T> = T extends Primitive\n"
            "  ? T\n"
            "  : T extends (...args: readonly any[]) => any\n"
            "  ? T\n"
            "  : { readonly [K in keyof T]: DeepReadonly<T[K]> };\n\n"
            "export function getNestedProperty<\n"
            "  TObject extends Record<string, any>,\n"
            "  TKey extends keyof TObject\n"
            ">(target: TObject, key: TKey): TObject[TKey] {\n"
            "  return target[key];\n"
            "}\n\n"
            "export function createRecordMap<\n"
            "  const TKeys extends readonly string[],\n"
            "  TValue\n"
            ">(keys: TKeys, initialValue: TValue): Record<TKeys[number], TValue> {\n"
            "  const result = {} as Record<TKeys[number], TValue>;\n"
            "  for (const key of keys) {\n"
            "    result[key as TKeys[number]] = initialValue;\n"
            "  }\n"
            "  return result;\n"
            "}\n\n"
            "export function mergeEntities<\n"
            "  TBase extends { readonly id: string | number },\n"
            "  TExtension extends Record<string, unknown>\n"
            ">(base: TBase, extension: TExtension): TBase & TExtension {\n"
            "  return Object.assign({}, base, extension);\n"
            "}\n"
        ),
        validation_rules=[
            "TObject extends Record<string, any>",
            "TKey extends keyof TObject",
            "DeepReadonly<T>",
            "const TKeys extends readonly string[]"
        ],
        description="Type constraints leveraging extends, keyof property indexing, and TypeScript 5.0 const type parameters."
    ),
    WebComponentSpec(
        spec_id="NODE-NATIVE-TYPE-STRIP-01",
        kind="typescript",
        title="Node.js v26 Native TypeScript Execution with Type Stripping and ESM Standards",
        code_snippet=(
            "// Node.js native type stripping (--experimental-strip-types / native TS runtime):\n"
            "// 1. Avoid TypeScript runtime 'enum' (use 'as const' objects)\n"
            "// 2. Avoid TypeScript 'namespace'\n"
            "// 3. Avoid constructor parameter properties\n"
            "// 4. Use explicit 'import type' for type-only imports\n\n"
            "import type { IncomingMessage, ServerResponse } from 'node:http';\n"
            "import { createServer } from 'node:http';\n\n"
            "export const LogSeverity = {\n"
            "  DEBUG: 'debug',\n"
            "  INFO: 'info',\n"
            "  WARN: 'warn',\n"
            "  ERROR: 'error',\n"
            "} as const;\n\n"
            "export type LogLevel = (typeof LogSeverity)[keyof typeof LogSeverity];\n\n"
            "export interface ServiceStatus {\n"
            "  readonly nodeVersion: string;\n"
            "  readonly uptimeSeconds: number;\n"
            "  readonly severity: LogLevel;\n"
            "}\n\n"
            "export function formatServiceStatus(status: ServiceStatus): string {\n"
            "  return `[NODE-${status.nodeVersion}] Status=${status.severity} Uptime=${status.uptimeSeconds}s`;\n"
            "}\n\n"
            "export const server = createServer((req: IncomingMessage, res: ServerResponse): void => {\n"
            "  const status: ServiceStatus = {\n"
            "    nodeVersion: process.version,\n"
            "    uptimeSeconds: Math.floor(process.uptime()),\n"
            "    severity: LogSeverity.INFO,\n"
            "  };\n"
            "  res.writeHead(200, { 'Content-Type': 'application/json' });\n"
            "  res.end(JSON.stringify(status));\n"
            "});\n"
        ),
        validation_rules=[
            "import type {",
            "as const",
            "export type LogLevel =",
            "node:http",
            "--experimental-strip-types"
        ],
        description="Node v26 native execution adhering strictly to type stripping syntax constraints without code emission."
    ),
    WebComponentSpec(
        spec_id="TS-FETCH-ABORT-STREAM-01",
        kind="typescript",
        title="Resilient Web API Client with AbortSignal.timeout and Discriminated Result",
        code_snippet=(
            "export type Result<T, E = Error> =\n"
            "  | { readonly ok: true; readonly value: T }\n"
            "  | { readonly ok: false; readonly error: E };\n\n"
            "export interface FetchOptions extends RequestInit {\n"
            "  readonly timeoutMs?: number;\n"
            "}\n\n"
            "export async function safeFetchJson<T>(\n"
            "  url: string,\n"
            "  options: FetchOptions = {}\n"
            "): Promise<Result<T, Error>> {\n"
            "  const { timeoutMs = 5000, ...init } = options;\n"
            "  const signal = options.signal ?? AbortSignal.timeout(timeoutMs);\n\n"
            "  try {\n"
            "    const response = await fetch(url, { ...init, signal });\n"
            "    if (!response.ok) {\n"
            "      return {\n"
            "        ok: false,\n"
            "        error: new Error(`HTTP Error ${response.status}: ${response.statusText}`),\n"
            "      };\n"
            "    }\n"
            "    const data = (await response.json()) as T;\n"
            "    return { ok: true, value: data };\n"
            "  } catch (err: unknown) {\n"
            "    if (err instanceof Error) {\n"
            "      return { ok: false, error: err };\n"
            "    }\n"
            "    return { ok: false, error: new Error(String(err)) };\n"
            "  }\n"
            "}\n"
        ),
        validation_rules=[
            "AbortSignal.timeout",
            "export type Result<T, E",
            "ok: true",
            "ok: false"
        ],
        description="Resilient modern Web API client with AbortSignal.timeout, strong error typing, and json parsing."
    )
]

# Trajectory definitions matching TrainingPair schema for golden master integration
WEB_TRAJECTORIES: List[Dict[str, Any]] = [
    {
        "id_suffix": "WEB_CSS_GRID_0001",
        "spec_id": "CSS-HOLY-GRAIL-01",
        "domain": "html_css",
        "prompt": "Implement a modern responsive Holy Grail layout using CSS Grid named template areas, fluid minmax tracks, and a clean mobile breakpoint collapse.",
        "chosen": WEB_SPECS[0].code_snippet,
        "rejected": (
            ".container { width: 100%; }\n"
            ".header { width: 100%; height: 60px; float: left; }\n"
            ".nav { width: 200px; float: left; }\n"
            ".main { width: 500px; float: left; }\n"
            ".aside { width: 200px; float: right; }\n"
            ".footer { clear: both; width: 100%; }\n"
            "/* Fragile float layout that breaks on varied viewport widths */"
        ),
        "capabilities": ["css_grid", "named_areas", "responsive", "holy_grail"],
        "title": WEB_SPECS[0].title,
        "validation_rules": WEB_SPECS[0].validation_rules,
        "description": WEB_SPECS[0].description
    },
    {
        "id_suffix": "WEB_CSS_FLUID_0002",
        "spec_id": "CSS-FLUID-TYPE-01",
        "domain": "html_css",
        "prompt": "Create a fluid typography and spacing scale in modern CSS using the clamp() function and root custom properties without media query breakpoints.",
        "chosen": WEB_SPECS[1].code_snippet,
        "rejected": (
            "body { font-size: 16px; }\n"
            "@media (max-width: 1200px) { body { font-size: 15px; } }\n"
            "@media (max-width: 992px) { body { font-size: 14px; } }\n"
            "@media (max-width: 768px) { body { font-size: 13px; } }\n"
            "@media (max-width: 576px) { body { font-size: 12px; } }\n"
            "/* Choppy step-wise font sizing causing layout jumping */"
        ),
        "capabilities": ["css_clamp", "fluid_typography", "custom_properties", "modular_scale"],
        "title": WEB_SPECS[1].title,
        "validation_rules": WEB_SPECS[1].validation_rules,
        "description": WEB_SPECS[1].description
    },
    {
        "id_suffix": "WEB_CSS_PRINT_0003",
        "spec_id": "CSS-PRINT-MEDIA-01",
        "domain": "html_css",
        "prompt": "Write a production-ready print media stylesheet in CSS ensuring high-contrast ink conservation, page break prevention on headings and tables, and URL disclosure.",
        "chosen": WEB_SPECS[2].code_snippet,
        "rejected": (
            "@media print {\n"
            "  body { font-size: 10px; }\n"
            "  /* Missing page break rules, keeps dark backgrounds, hides no navigation chrome */\n"
            "}"
        ),
        "capabilities": ["print_css", "media_queries", "page_breaks", "url_disclosure"],
        "title": WEB_SPECS[2].title,
        "validation_rules": WEB_SPECS[2].validation_rules,
        "description": WEB_SPECS[2].description
    },
    {
        "id_suffix": "WEB_CSS_CASCADE_0004",
        "spec_id": "CSS-CASCADE-SPECIFICITY-01",
        "domain": "html_css",
        "prompt": "Demonstrate modern CSS cascade layers (@layer) and pseudo-class specificity controls (:where() vs :is()) to manage stylesheet architecture cleanly without !important.",
        "chosen": WEB_SPECS[3].code_snippet,
        "rejected": (
            "#app .content-wrapper .main-container div.widget .btn {\n"
            "  background: #2563eb !important;\n"
            "  border-radius: 4px !important;\n"
            "}\n"
            "/* Deep selector chaining with !important escalation causing cascade lock-in */"
        ),
        "capabilities": ["cascade_layers", "css_specificity", "where_pseudo", "is_pseudo"],
        "title": WEB_SPECS[3].title,
        "validation_rules": WEB_SPECS[3].validation_rules,
        "description": WEB_SPECS[3].description
    },
    {
        "id_suffix": "WEB_HTML_DIALOG_0005",
        "spec_id": "HTML-DIALOG-MODAL-01",
        "domain": "html_css",
        "prompt": "Construct a fully accessible HTML5 <dialog> modal with accessible ARIA labeling, form method dialog integration, and backdrop dismissal.",
        "chosen": WEB_SPECS[4].code_snippet,
        "rejected": (
            "<div class=\"modal-overlay\" onclick=\"closeModal()\">\n"
            "  <div class=\"modal-box\">\n"
            "    <h3>Confirm</h3>\n"
            "    <p>Deploy?</p>\n"
            "    <a href=\"#\" onclick=\"confirm()\">Yes</a>\n"
            "  </div>\n"
            "</div>\n"
            "<!-- Inaccessible div modal with no ARIA roles, no keyboard trap, and no focus return -->"
        ),
        "capabilities": ["html5_dialog", "accessibility", "a11y", "form_dialog", "focus_trap"],
        "title": WEB_SPECS[4].title,
        "validation_rules": WEB_SPECS[4].validation_rules,
        "description": WEB_SPECS[4].description
    },
    {
        "id_suffix": "WEB_HTML_SEARCH_0006",
        "spec_id": "HTML-SEARCH-FORM-01",
        "domain": "html_css",
        "prompt": "Create an accessible, semantic search component using <form role=\"search\">, <input type=\"search\">, accessible hidden labels, and enterkeyhint.",
        "chosen": WEB_SPECS[5].code_snippet,
        "rejected": (
            "<div class=\"search-box\">\n"
            "  <input type=\"text\" placeholder=\"search...\">\n"
            "  <button onclick=\"search()\">Go</button>\n"
            "</div>\n"
            "<!-- Missing search landmark role, missing input type search, and missing accessible label -->"
        ),
        "capabilities": ["semantic_html", "role_search", "search_input", "a11y", "screen_readers"],
        "title": WEB_SPECS[5].title,
        "validation_rules": WEB_SPECS[5].validation_rules,
        "description": WEB_SPECS[5].description
    },
    {
        "id_suffix": "WEB_HTML_LANDMARK_0007",
        "spec_id": "HTML-LANDMARK-NAV-01",
        "domain": "html_css",
        "prompt": "Implement a semantic HTML5 document skeleton featuring complete ARIA landmarks, a skip-to-main-content link, accessible primary and breadcrumb navigation, and proper heading hierarchy.",
        "chosen": WEB_SPECS[6].code_snippet,
        "rejected": (
            "<div id=\"header\"><div id=\"nav\">...</div></div>\n"
            "<div id=\"content\">\n"
            "  <div>Welcome</div>\n"
            "</div>\n"
            "<div id=\"footer\">&copy; 2026</div>\n"
            "<!-- Non-semantic div-soup with zero landmarks, no skip links, and no accessibility tree -->"
        ),
        "capabilities": ["aria_landmarks", "skip_links", "breadcrumbs", "semantic_html", "a11y"],
        "title": WEB_SPECS[6].title,
        "validation_rules": WEB_SPECS[6].validation_rules,
        "description": WEB_SPECS[6].description
    },
    {
        "id_suffix": "WEB_TS_SATISFIES_0008",
        "spec_id": "TS-SATISFIES-CONFIG-01",
        "domain": "typescript",
        "prompt": "Demonstrate TypeScript 5.x 'satisfies' operator for strictly type-checking configuration objects while preserving literal inference and tuple types without widening.",
        "chosen": WEB_SPECS[7].code_snippet,
        "rejected": (
            "export interface AgentConfig {\n"
            "  seatId: number;\n"
            "  model: string;\n"
            "  roles: string[];\n"
            "}\n"
            "export const SEAT_SETTINGS: AgentConfig = {\n"
            "  seatId: 3,\n"
            "  model: 'qwen3.5-9b-abli',\n"
            "  roles: ['compiler', 'lora'],\n"
            "};\n"
            "// Widens roles to mutable string[] and loses literal tracking"
        ),
        "capabilities": ["typescript5", "satisfies_operator", "literal_types", "discriminated_unions"],
        "title": WEB_SPECS[7].title,
        "validation_rules": WEB_SPECS[7].validation_rules,
        "description": WEB_SPECS[7].description
    },
    {
        "id_suffix": "WEB_TS_DISCRIMINATED_0009",
        "spec_id": "TS-DISCRIMINATED-UNION-01",
        "domain": "typescript",
        "prompt": "Implement a robust discriminated union event processing pipeline in TypeScript 5.x with compile-time exhaustive match verification using the 'never' type.",
        "chosen": WEB_SPECS[8].code_snippet,
        "rejected": (
            "export function processMeshEvent(event: any): string {\n"
            "  if (event.kind === 'HEARTBEAT') {\n"
            "    return 'HB ' + event.data.seatId;\n"
            "  }\n"
            "  return 'UNKNOWN';\n"
            "}\n"
            "// Untyped any handling without compile-time discriminant safety or exhaustiveness checks"
        ),
        "capabilities": ["typescript5", "discriminated_unions", "exhaustive_matching", "never_type"],
        "title": WEB_SPECS[8].title,
        "validation_rules": WEB_SPECS[8].validation_rules,
        "description": WEB_SPECS[8].description
    },
    {
        "id_suffix": "WEB_TS_GENERICS_0010",
        "spec_id": "TS-GENERIC-CONSTRAINTS-01",
        "domain": "typescript",
        "prompt": "Construct advanced generic TypeScript 5.x utility functions leveraging 'extends' constraints, keyof indexing, mapped types, and const type parameter constraints.",
        "chosen": WEB_SPECS[9].code_snippet,
        "rejected": (
            "export function getNestedProperty(target: any, key: any): any {\n"
            "  return target[key];\n"
            "}\n"
            "export function createRecordMap(keys: any[], value: any): any {\n"
            "  const res: any = {};\n"
            "  for (const k of keys) res[k] = value;\n"
            "  return res;\n"
            "}\n"
            "// Discards all generic constraints, return type inference, and keyof type safety"
        ),
        "capabilities": ["typescript5", "generics", "type_constraints", "mapped_types", "const_generics"],
        "title": WEB_SPECS[9].title,
        "validation_rules": WEB_SPECS[9].validation_rules,
        "description": WEB_SPECS[9].description
    },
    {
        "id_suffix": "WEB_NODE_STRIP_0011",
        "spec_id": "NODE-NATIVE-TYPE-STRIP-01",
        "domain": "typescript",
        "prompt": "Develop a high-performance Node.js v26 modern service using native type stripping (--experimental-strip-types), ESM syntax, import type, and object union const assertions instead of runtime enums.",
        "chosen": WEB_SPECS[10].code_snippet,
        "rejected": (
            "const http = require('http');\n"
            "enum LogSeverity { DEBUG = 0, INFO = 1 }\n"
            "class Server {\n"
            "  constructor(public port: number) {}\n"
            "}\n"
            "// Fails under Node native type stripping due to runtime TypeScript enum and parameter properties"
        ),
        "capabilities": ["node26", "strip_types", "esm", "as_const", "native_typescript"],
        "title": WEB_SPECS[10].title,
        "validation_rules": WEB_SPECS[10].validation_rules,
        "description": WEB_SPECS[10].description
    },
    {
        "id_suffix": "WEB_TS_FETCH_0012",
        "spec_id": "TS-FETCH-ABORT-STREAM-01",
        "domain": "typescript",
        "prompt": "Implement a resilient modern Web API HTTP client in TypeScript featuring AbortSignal.timeout(), discriminated Result<T, E> error handling, and response validation.",
        "chosen": WEB_SPECS[11].code_snippet,
        "rejected": (
            "export async function fetchJson(url: string) {\n"
            "  const res = await fetch(url);\n"
            "  return await res.json();\n"
            "}\n"
            "// Missing timeout signals, no error boundary, returns untyped any, risks unhandled rejections"
        ),
        "capabilities": ["fetch_api", "abort_signal", "result_type", "type_safe_api", "async_await"],
        "title": WEB_SPECS[11].title,
        "validation_rules": WEB_SPECS[11].validation_rules,
        "description": WEB_SPECS[11].description
    }
]

def validate_web_spec(spec: WebComponentSpec) -> bool:
    """Validates that a web component spec adheres to all stated rules."""
    for rule in spec.validation_rules:
        if rule not in spec.code_snippet:
            return False
    return True

def generate_web_corpus_records(created_at: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generates unified records compliant with both TrainingPair and WebComponentSpec schemas."""
    ts = created_at or "2026-11-16T21:16:00.000000+00:00"
    records = []
    for item in WEB_TRAJECTORIES:
        record = {
            "id": f"TWU_GOLD_{item['id_suffix']}",
            "domain": item["domain"],
            "kind": "dpo",
            "prompt": item["prompt"],
            "chosen": item["chosen"],
            "rejected": item["rejected"],
            "quality": "gold_certified",
            "capabilities": item["capabilities"],
            "created_at": ts,
            "spec_id": item["spec_id"],
            "title": item["title"],
            "code_snippet": item["chosen"],
            "validation_rules": item["validation_rules"],
            "description": item["description"],
        }
        records.append(record)
    return records

def export_web_specs(dest_path: Optional[Path] = None) -> Tuple[int, str]:
    """Exports web specs to JSONL and returns row count and sha256."""
    target = dest_path or (Path(__file__).resolve().parent.parent / "exchange" / "web_specs.jsonl")
    target.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for spec in WEB_SPECS:
        assert validate_web_spec(spec), f"Spec validation failed for {spec.spec_id}"
        lines.append(json.dumps(asdict(spec), sort_keys=True))

    content = "\n".join(lines) + "\n"
    target.write_text(content, encoding="utf-8")
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return len(WEB_SPECS), sha

def export_web_corpus(dest_path: Optional[Path] = None) -> Tuple[int, str]:
    """Exports web corpus trajectories to JSONL and returns row count and sha256."""
    target = dest_path or (Path(__file__).resolve().parent.parent / "data" / "corpus" / "web" / "web_corpus.jsonl")
    target.parent.mkdir(parents=True, exist_ok=True)

    records = generate_web_corpus_records()
    lines = []
    for r in records:
        lines.append(json.dumps(r, sort_keys=True))

    content = "\n".join(lines) + "\n"
    target.write_text(content, encoding="utf-8")
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return len(records), sha
