---
name: seo
description: Audits web application codebases for SEO, GEO (AI visibility), and AEO (citation-readiness). Creates docs/SEO_REPORT.md with findings by severity. Use when user says "seo audit", "check seo", "/seo", "audit my site", "check structured data", "schema audit", or "check meta tags". Supports "--technical", "--schema", "--content" scan types (default runs all), "--force" for full re-audit, "--opus" for higher quality Opus subagents, "--opus Nk" for custom budget.
---

# SEO Audit

Audits web application source code for technical SEO, structured data (schema.org), and content optimization — covering traditional SEO, Generative Engine Optimization (GEO), and Answer Engine Optimization (AEO).

**CRITICAL: Orchestrator never reads codebase files directly.** Always delegate file reading to subagents — even for small codebases. The orchestrator plans the work, spawns subagents, verifies cross-references, and compiles the report.

## Quick Start

1. Run the scanner to get file tree and framework detection
2. Detect framework from config_surface
3. Identify SEO-relevant files per scan type
4. Spawn subagents in parallel with scan-type-specific checklists
5. Verify cross-references across subagent findings
6. Compile findings into `docs/SEO_REPORT.md`

## Workflow

### Step 1: Parse Flags and Check for Existing Report

Parse flags from the user's request:
- `--technical` → Crawlability, SSR, URL structure, AI discoverability
- `--schema` → Structured data, entity completeness, E-E-A-T signals
- `--content` → Meta tags, headings, images, GEO/AEO readiness
- `--force` → Full re-audit (ignore existing report)
- `--opus` → Use Opus model for subagents (higher quality analysis)
- `--opus Nk` → Opus with custom budget (e.g. `--opus 500k`)

**If no scan type flag is provided, run all three scan types.**

Flags are combinable: `/seo --technical --schema --force --opus`

**Budget parsing:** If a number like `500k` follows `--opus`, use that as the per-subagent token budget. Otherwise default to 750,000.

Then check if `docs/SEO_REPORT.md` already exists:

**If it exists (and not forced):**
1. Read the `last_audited` timestamp from the report frontmatter
2. Run `git log --oneline --since="<last_audited>"` if git available
3. If significant changes detected, proceed to re-audit
4. If no changes, inform user the audit is current

**If it does not exist (or forced):** Proceed to full audit.

### Step 2: Run the Scanner

Reuse the Recon scanner to get file tree and framework detection:

```bash
# Option 1: UV (preferred)
uv run ${CLAUDE_PLUGIN_ROOT}/skills/recon/scripts/scan-codebase.py . --format json

# Option 2: Direct execution
${CLAUDE_PLUGIN_ROOT}/skills/recon/scripts/scan-codebase.py . --format json

# Option 3: Explicit python3
python3 ${CLAUDE_PLUGIN_ROOT}/skills/recon/scripts/scan-codebase.py . --format json
```

The scanner provides:
- Complete file tree with paths
- Token counts per file
- `config_surface` — framework config files by category (used for framework detection)
- `entrypoints` — entry points (useful for understanding routing)

### Step 3: Detect Framework and Identify SEO-Relevant Files

**Framework detection** from `config_surface["build"]`:

| Config File | Framework |
|-------------|-----------|
| `next.config.*` | Next.js |
| `nuxt.config.*` | Nuxt |
| `astro.config.*` | Astro |
| `svelte.config.*` | SvelteKit |
| `gatsby-config.*` | Gatsby |
| `vite.config.*` (with no framework config) | Vite (generic SPA) |
| None of the above | Generic HTML/static |

**Identify SEO-relevant files** using framework-aware patterns. Build a file list for each enabled scan type from the scanner's file tree:

**Technical scan files:**
- `robots.txt`, `public/robots.txt`
- `sitemap.xml`, `sitemap*.xml`, `public/sitemap*.xml`
- `llms.txt`, `public/llms.txt`
- Framework config file (e.g. `next.config.js`, `nuxt.config.ts`)
- Routing files:
  - Next.js: `app/**/page.*`, `app/**/layout.*`, `pages/**/*`
  - Nuxt: `pages/**/*`, `server/middleware/**/*`
  - Astro: `src/pages/**/*`, `src/layouts/**/*`
  - SvelteKit: `src/routes/**/*`
  - Generic: `*.html`, `index.*`
- Root layout/document files:
  - Next.js: `app/layout.*`, `pages/_app.*`, `pages/_document.*`
  - Nuxt: `app.vue`, `layouts/default.*`
  - Astro: `src/layouts/**/*`
  - Generic: `index.html`
- Middleware/headers: `middleware.*`, `_headers`, `netlify.toml`, `vercel.json`, `.htaccess`
- 404 pages: `app/not-found.*`, `pages/404.*`, `src/pages/404.*`, `404.html`

**Schema scan files:**
- Root layouts (JSON-LD is typically injected here)
- Any file whose path contains `schema`, `jsonld`, `json-ld`, `structured-data`, or `seo`
- About/contact/author pages: files whose path contains `about`, `contact`, `author`, `team`
- Privacy/terms pages: files whose path contains `privacy`, `terms`, `legal`
- Component files with `schema`, `jsonld`, `seo`, or `metadata` in the name
- `package.json` (check for SEO-related dependencies like `next-seo`, `schema-dts`, `nuxt-schema-org`)

**Content scan files:**
- Page components/templates (same routing files as technical — these contain meta tags, headings, images, and content)
- Root layout/document files (same as technical — these contain shared meta tags, OG defaults)
- SEO utility files: files with `seo`, `meta`, `head`, or `metadata` in the filename
- Markdown/MDX content: `content/**/*`, `posts/**/*`, `blog/**/*`, `articles/**/*`
- **Note:** The subagent will find framework-specific patterns (`generateMetadata`, `useHead`, `useSeoMeta`, etc.) by reading the assigned files. The orchestrator only needs to identify files by path.

**Important:** Include ALL files that match these patterns, not just a sample. SEO audits must be exhaustive. If the total token count for a scan type exceeds the budget, split into multiple subagents grouped by directory.

### Step 4: Spawn Subagents in Parallel

Use the Task tool with `subagent_type: "Explore"` for each enabled scan type.

**Model selection:**
- Default: `model: "sonnet"`
- If `--opus` flag was provided: `model: "opus"`

**CRITICAL: Spawn all subagents in a SINGLE message with multiple Task tool calls.**

Each subagent receives its scan-type-specific prompt from the templates below.

---

## Subagent Prompt Templates

### Technical SEO Subagent Prompt

```
You are auditing a web application's source code for technical SEO issues.

## Framework
[framework name — e.g. "Next.js (App Router)", "Nuxt 3", "Astro", "Generic HTML"]

## Files to Analyze
[file list]

## Checklist

Read the assigned files and evaluate each check. For each check, report a finding.

**Status values:** pass | fail | warning | skip (if not applicable to this codebase)
**Severity (for fail/warning only):** critical | warning | info

---

### CRAWLABILITY

#### robots-txt-exists
- **Look for:** robots.txt in public root or project root
- **Pass:** File exists with valid content
- **Fail (critical):** File missing entirely
- **Note:** In Next.js/Nuxt, check if framework generates it automatically via config

#### robots-txt-valid
- **Look for:** Valid robots.txt syntax. Check User-agent and Disallow directives.
- **Pass:** Valid syntax, not blocking critical paths (/, /api is OK to block)
- **Fail (warning):** Blocking important content paths, or invalid syntax
- **Note:** Check for Disallow: / under User-agent: * which blocks everything

#### sitemap-exists
- **Look for:** sitemap.xml in public root, or sitemap generation config (next-sitemap, @nuxtjs/sitemap, astro-sitemap)
- **Pass:** Static sitemap exists OR sitemap generation is configured
- **Fail (critical):** No sitemap and no generation configured
- **Note:** Check package.json dependencies and framework config for sitemap plugins

#### sitemap-referenced
- **Look for:** Sitemap: directive in robots.txt pointing to sitemap URL
- **Pass:** robots.txt contains Sitemap: line
- **Fail (warning):** robots.txt exists but no Sitemap: directive

#### ssr-detection
- **Look for:** Whether pages render on the server or are client-only SPAs
- **Framework-specific patterns:**
  - Next.js App Router: Server Components are default (good). Check for `'use client'` on root page/layout (bad). Check for `getServerSideProps`/`getStaticProps` in pages dir (good).
  - Next.js with `output: 'export'` in config: static export only (acceptable for static sites)
  - Nuxt: SSR by default (good). Check for `ssr: false` in nuxt.config (bad).
  - Astro: Static by default (good). Check for `output: 'server'` for SSR pages.
  - Vite/CRA: Client-only by default (bad for SEO). Check for SSR plugins.
- **Pass:** Framework uses SSR/SSG by default and root pages are server-rendered
- **Fail (critical):** Pure client-side SPA with no SSR/SSG. Root pages with `'use client'` directive rendering all content client-side.
- **Warning:** Some content pages are client-only while layout is server-rendered
- **Note:** AI crawlers and Google cannot reliably execute client-side JavaScript. This is often the single highest-impact SEO issue.

#### noindex-check
- **Look for:** `<meta name="robots" content="noindex">` or equivalent in layouts, pages, or metadata config. Also check for `X-Robots-Tag: noindex` in middleware/headers config.
- **Framework-specific:** Next.js `robots` in metadata, Nuxt `useHead` robots, `_headers` files
- **Pass:** No unintentional noindex directives. Noindex on intentionally excluded pages (admin, staging) is fine.
- **Fail (critical):** Noindex on content pages, root layout, or blanket noindex in headers. This is the #1 most common accidental SEO disaster (often left from staging/development).
- **Note:** Check for environment-conditional noindex that might leak to production (e.g. `process.env.NODE_ENV !== 'production'` guards)

#### canonical-urls
- **Look for:** `<link rel="canonical">` in layouts or metadata config
- **Pass:** Canonical URLs implemented — either self-referencing (each page points to itself) or framework handles it automatically
- **Fail (warning):** No canonical URL implementation found — risks duplicate content from trailing slashes, www/non-www, query parameters
- **Note:** Self-referencing canonicals are the standard. Cross-domain canonicals are rare and intentional — don't flag those.

#### url-structure
- **Look for:** Route/page file naming patterns
- **Pass:** Clean slug-based URLs (e.g. /about, /blog/my-post)
- **Fail (info):** Routes rely heavily on query parameters or hash routing

#### trailing-slash
- **Look for:** Trailing slash configuration in framework config
- **Pass:** Explicit trailingSlash config set (true or false — consistency matters)
- **Fail (warning):** No trailing slash config (framework default may cause inconsistency)

#### viewport-meta
- **Look for:** <meta name="viewport"> in root layout/document
- **Pass:** Viewport meta tag present with width=device-width
- **Fail (critical):** Missing viewport meta tag (breaks mobile rendering and SEO)

#### 404-handling
- **Look for:** Custom 404/not-found page
- **Pass:** Custom 404 page exists (not-found.tsx, 404.tsx, 404.html, etc.)
- **Fail (warning):** No custom 404 page found

### PERFORMANCE SIGNALS

#### https-config
- **Look for:** HTTPS enforcement in server config, redirects, or hosting config
- **Pass:** HTTPS redirect configured, or hosting platform enforces it (Vercel, Netlify, etc.)
- **Fail (info):** No explicit HTTPS config found (may be handled at hosting level)

### AI DISCOVERABILITY

#### llms-txt
- **Look for:** llms.txt file in public root. Also check for RSL 1.0 (Really Simple Licensing) implementation — a machine-readable AI licensing standard (backed by Reddit, Yahoo, Medium, Quora, Cloudflare, Creative Commons as of December 2025).
- **Pass:** llms.txt exists with structured content about the site
- **Fail (info):** No llms.txt (community standard for AI crawler guidance, adoption growing). No RSL licensing terms.
- **Note:** llms.txt tells AI crawlers where your best content is (complementary to robots.txt which tells them where NOT to go). RSL defines licensing terms for AI use of your content.

#### ai-crawler-access
- **Look for:** In robots.txt, check rules for AI crawler user agents. Key distinction — **search crawlers** (blocking these hides you from AI search) vs **training crawlers** (blocking these is a content licensing choice):
  - **Search (blocking hurts AI visibility):** `OAI-SearchBot` (OpenAI search features), `PerplexityBot` (Perplexity search), `ClaudeBot` (Claude web features)
  - **Training (blocking is a business decision):** `GPTBot` (OpenAI model training), `Google-Extended` (Gemini training — does NOT affect Google Search or AI Overviews), `anthropic-ai` (Claude training), `CCBot` (Common Crawl), `Bytespider` (ByteDance/TikTok AI)
  - **User-initiated (NOT controlled by robots.txt):** `ChatGPT-User` — fires when a user asks ChatGPT to browse a URL. Cannot be blocked via robots.txt per OpenAI docs.
- **Pass:** Search crawlers not blocked. Training crawler policy is an intentional choice.
- **Fail (info):** Search crawlers blocked — this reduces AI search visibility
- **Warning:** Wildcard `Disallow: /` under `User-agent: *` blocks all automatic crawlers including AI search bots
- **Note:** Blocking `GPTBot` prevents training use but does NOT prevent ChatGPT from citing your content (that uses `ChatGPT-User`, which ignores robots.txt). Blocking `Google-Extended` does NOT affect Google Search or AI Overviews — those use `Googlebot`.

#### redirect-handling
- **Look for:** Redirect configuration (middleware, _redirects, netlify.toml, vercel.json, .htaccess)
- **Pass:** Redirects configured for common patterns (www/non-www, HTTP/HTTPS, old URLs)
- **Skip:** No redirect config found (may be handled at hosting level)

### INTERNATIONALIZATION (if detected)

#### i18n-urls
- **Look for:** i18n/locale configuration in framework config. If i18n is configured, check for locale-prefixed URL patterns.
- **Pass:** Locale-prefixed URLs (/en/about, /fr/about) or domain-based i18n
- **Fail (warning):** i18n configured but no locale-prefixed URLs
- **Skip:** No i18n configuration detected

#### hreflang
- **Look for:** hreflang tags in layouts/pages (if i18n detected)
- **Pass:** hreflang tags present linking language variants
- **Fail (warning):** i18n configured but no hreflang implementation
- **Skip:** No i18n configuration detected

#### www-redirect
- **Look for:** WWW/non-WWW redirect configuration
- **Pass:** Explicit redirect configured (either direction)
- **Fail (info):** No WWW redirect config (may be handled at DNS/hosting level)

---

## Output Format

Return ONLY a JSON block (no markdown wrapping, no explanation before or after):

{
  "scan_type": "technical",
  "framework": "[detected framework]",
  "findings": [
    {
      "check": "[check-id from checklist]",
      "status": "pass|fail|warning|skip",
      "severity": "critical|warning|info|null",
      "file": "path/to/file or null",
      "line": 42 or null,
      "detail": "What was found or what is missing",
      "context": "Relevant code snippet or explanation (optional)",
      "fix": "Suggested fix for this framework (only for fail/warning, else null)"
    }
  ]
}

**Rules:**
- Report ONE finding per check ID — do not duplicate
- Include ALL checks — use status "skip" for checks that don't apply
- Be specific in "detail" — cite exact file paths and line numbers
- Be actionable in "fix" — use framework-specific guidance
- "context" is optional — include a brief code snippet only when it helps explain the issue
```

### Schema/Structured Data Subagent Prompt

```
You are auditing a web application's source code for structured data (schema.org) and E-E-A-T signals.

## Framework
[framework name]

## Files to Analyze
[file list]

## Checklist

Read the assigned files and evaluate each check.

**Status values:** pass | fail | warning | skip
**Severity (for fail/warning only):** critical | warning | info

---

### JSON-LD PRESENCE AND VALIDITY

#### jsonld-present
- **Look for:** <script type="application/ld+json"> blocks, or JSON-LD objects passed via framework APIs (e.g. Next.js metadata.other, generateMetadata with jsonLd, Nuxt useSchemaOrg)
- **Pass:** At least one JSON-LD block found in layouts or pages
- **Fail (critical):** No JSON-LD structured data anywhere in the codebase
- **Note:** Also check for imports of schema libraries (schema-dts, next-seo, nuxt-schema-org) in package.json dependencies

#### jsonld-valid
- **Look for:** JSON-LD content is syntactically valid JSON with @context and @type
- **Pass:** All JSON-LD blocks parse correctly and have required @context/@type
- **Fail (critical):** JSON-LD has syntax errors, missing @context, or missing @type

### SCHEMA TYPE USAGE

#### schema-type-match
- **Look for:** Whether schema types match the page's purpose AND whether any deprecated/restricted types are used
- **Pass:** Schema types match content and none are deprecated
- **Fail (warning):** Schema type doesn't match content (e.g. Article schema on a product page)
- **Fail (warning):** Deprecated or restricted schema type in use (see list below)
- **Active types — recommend freely:** WebSite, Organization, LocalBusiness, Article, BlogPosting, NewsArticle, Product, ProductGroup, Offer, Service, BreadcrumbList, WebPage, Person, ProfilePage, ContactPage, VideoObject, ImageObject, Event, JobPosting, Course, Review, AggregateRating, SoftwareApplication
- **Restricted — flag if found:**
  - `FAQPage` — Google rich results restricted to government and healthcare sites only (August 2023). Still benefits AI/LLM citations on other sites, but note the restriction.
- **Deprecated — flag as warning if found:**
  - `HowTo` — Rich results removed September 2023
  - `SpecialAnnouncement` — Deprecated July 31, 2025
  - `CourseInfo`, `EstimatedSalary`, `LearningVideo` — Retired June 2025
  - `ClaimReview` — Retired from rich results June 2025
  - `VehicleListing` — Retired from rich results June 2025

#### required-props
- **Look for:** Required properties for each schema type used:
  - Article/BlogPosting: headline, author, datePublished
  - Organization: name, url
  - Product: name, description
  - FAQPage: mainEntity with Question/acceptedAnswer pairs
  - BreadcrumbList: itemListElement array
  - Person: name
- **Pass:** All required properties present for each schema type
- **Fail (warning):** Required properties missing

#### recommended-props
- **Look for:** Recommended properties that improve rich result eligibility:
  - Article: image, dateModified, publisher
  - Organization: logo, sameAs, contactPoint, address
  - Product: image, offers (with price, priceCurrency, availability)
  - Person: image, jobTitle, url, sameAs
- **Pass:** Most recommended properties present
- **Fail (info):** Several recommended properties missing

### ENTITY COMPLETENESS

#### org-complete
- **Look for:** Organization schema with: name, url, logo, sameAs (array of social/authority profile URLs)
- **Pass:** All four properties present
- **Fail (warning):** Organization schema exists but missing key properties
- **Skip:** No Organization schema found (flag this in detail)

#### person-complete
- **Look for:** Person schema with: name, url, and optionally jobTitle, sameAs, image
- **Pass:** Person schema has name, url, and at least one of jobTitle/sameAs
- **Fail (warning):** Person schema exists but is minimal (name only)
- **Skip:** No Person schema found (OK if not a personal site or no authored content)

#### sameas-present
- **Look for:** sameAs property linking to authoritative profiles (LinkedIn, Twitter/X, GitHub, Wikipedia, Wikidata, Crunchbase)
- **Pass:** sameAs links to 2+ authoritative profiles
- **Fail (info):** No sameAs or only 1 link
- **Note:** sameAs is the most powerful signal for Knowledge Graph inclusion

#### id-linking
- **Look for:** @id property used to create entity references across pages/blocks
- **Pass:** Entities use @id for cross-referencing (e.g. author @id in Article matches Person @id)
- **Fail (info):** No @id usage (entities are isolated, not linked)

### FRESHNESS SIGNALS

#### date-published
- **Look for:** datePublished property on Article, BlogPosting, or NewsArticle schema
- **Pass:** datePublished present in ISO 8601 format
- **Fail (warning):** Article/blog content exists but no datePublished in schema
- **Skip:** No article-type content detected

#### date-modified
- **Look for:** dateModified property on content schema
- **Pass:** dateModified present
- **Fail (info):** datePublished exists but no dateModified
- **Skip:** No article-type content detected

### AUTHORSHIP

#### author-schema
- **Look for:** author property on Article/BlogPosting linking to a Person entity (not just a string name)
- **Pass:** author is a Person object or @id reference with at minimum name and url
- **Fail (warning):** author is a plain string (e.g. "author": "John") or missing entirely on article content
- **Skip:** No article-type content detected

### SITE-LEVEL SCHEMA

#### website-schema
- **Look for:** WebSite schema on the homepage/root layout, ideally with SearchAction (enables Google sitelinks search box)
- **Pass:** WebSite schema present with at minimum name, url. SearchAction with a search URL template is a bonus.
- **Fail (warning):** No WebSite schema found — missing a basic site-level signal
- **Note:** WebSite schema is one of the most impactful yet frequently missing schema types

#### breadcrumb-schema
- **Look for:** BreadcrumbList schema in layouts or navigation components
- **Pass:** BreadcrumbList schema present with itemListElement array
- **Fail (info):** No BreadcrumbList schema (improves SERP appearance and helps crawlers understand site hierarchy)
- **Skip:** Single-page site or flat site structure

### ADVANCED

#### speakable
- **Look for:** SpeakableSpecification schema marking content suitable for voice/AI extraction
- **Pass:** SpeakableSpecification present with cssSelector or xpath pointing to key content
- **Fail (info):** No SpeakableSpecification (emerging standard, improves AI citation eligibility)

### TRUST PAGES

#### trust-pages
- **Look for:** Pages for About, Contact, and Privacy Policy (check route files and navigation)
- **Pass:** All three pages exist (about, contact, privacy/terms)
- **Fail (warning):** One or more trust pages missing
- **Note:** These pages are E-E-A-T trust signals. Record which exist and which are missing.

---

## Output Format

Return ONLY a JSON block:

{
  "scan_type": "schema",
  "framework": "[detected framework]",
  "findings": [
    {
      "check": "[check-id]",
      "status": "pass|fail|warning|skip",
      "severity": "critical|warning|info|null",
      "file": "path/to/file or null",
      "line": 42 or null,
      "detail": "What was found or what is missing",
      "context": "Relevant code or schema snippet (optional)",
      "fix": "Suggested fix (only for fail/warning, else null)"
    }
  ],
  "schema_blocks": [
    {
      "file": "path/to/file",
      "line": 10,
      "type": "Organization",
      "properties": ["name", "url", "logo", "sameAs"],
      "missing_required": [],
      "missing_recommended": ["contactPoint", "address"]
    }
  ],
  "entities": [
    {
      "type": "Organization",
      "id": "https://example.com/#organization",
      "name": "Example Corp",
      "sameas": ["https://linkedin.com/company/example", "https://twitter.com/example"],
      "file": "app/layout.tsx"
    }
  ]
}

**Rules:**
- Report ONE finding per check ID
- Include ALL checks — use "skip" for non-applicable checks
- Populate schema_blocks for EVERY JSON-LD block found (used for cross-reference verification)
- Populate entities for EVERY Person/Organization entity found (used for cross-reference verification)
- Be specific about which properties are present vs missing
```

### Content Optimization Subagent Prompt

```
You are auditing a web application's source code for content SEO, including meta tags, heading structure, image optimization, and AI citation readiness (GEO/AEO).

## Framework
[framework name]

## Files to Analyze
[file list]

## Checklist

Read the assigned files and evaluate each check.

**Status values:** pass | fail | warning | skip
**Severity (for fail/warning only):** critical | warning | info

---

### META TAGS

#### title-tag
- **Look for:** Page title implementation:
  - Next.js: title in metadata/generateMetadata, or <title> in layout
  - Nuxt: useHead({ title }), useSeoMeta({ title }), or definePageMeta
  - Astro: <title> in layout head, or Astro.props.title pattern
  - Generic: <title> tag in <head>
- **Pass:** Title set in root layout AND/OR per-page metadata
- **Fail (critical):** No title implementation found
- **Note:** Check for both static titles and dynamic title templates (e.g. "%s | Site Name")

#### title-length
- **Look for:** Title text length in metadata definitions
- **Pass:** Titles are in the 50-60 character range
- **Warning:** Titles consistently too short (<30 chars) or too long (>70 chars)
- **Note:** Dynamic titles with variables are hard to assess — note the template pattern and skip if uncertain

#### meta-description
- **Look for:** Meta description implementation (same framework patterns as title-tag)
- **Pass:** Description set in metadata
- **Fail (warning):** No meta description implementation found

#### meta-desc-length
- **Look for:** Description text length
- **Pass:** Descriptions are in the 150-160 character range
- **Fail (info):** Descriptions consistently too short or too long
- **Note:** Skip if descriptions are dynamic/variable-based

#### og-tags
- **Look for:** Open Graph meta tags: og:title, og:description, og:image, og:type, og:url
- **Pass:** At least og:title, og:description, and og:image present
- **Fail (warning):** Missing OG tags (impacts social sharing and some AI crawlers)
- **Note:** In Next.js, check openGraph in metadata. In Nuxt, check useSeoMeta.

#### twitter-card
- **Look for:** Twitter/X card meta tags: twitter:card, twitter:title, twitter:description, twitter:image
- **Pass:** Twitter card tags present (or explicitly inheriting from OG tags)
- **Fail (info):** No Twitter card implementation

### HEADING STRUCTURE

#### h1-present
- **Look for:** H1 tags in page components/templates
- **Pass:** Each page has exactly one H1 (in the page component, not the layout)
- **Fail (critical):** Pages with no H1, or multiple H1 tags per page
- **Warning:** H1 in the layout (means every page has the same H1)
- **Note:** Check both static <h1> tags and component-rendered headings

#### heading-hierarchy
- **Look for:** Heading levels (h1-h6) in page content
- **Pass:** Headings follow logical order (h1 → h2 → h3, no skipping levels)
- **Fail (warning):** Headings skip levels (h1 → h3) or are used for styling rather than structure

### IMAGE OPTIMIZATION

#### image-alt
- **Look for:** alt attributes on <img> tags and framework image components (next/image, nuxt-img, etc.)
- **Pass:** All or nearly all images have descriptive alt text
- **Fail (warning):** Multiple images missing alt attributes
- **Note:** Decorative images should have alt="" (empty, not missing). Flag images with alt text that is clearly keyword-stuffed.

### GEO / AEO READINESS

#### faq-patterns
- **Look for:** FAQ-structured content: question/answer pairs, definition lists (<dl>), accordion components with Q&A
- **Pass:** FAQ patterns found (especially if paired with FAQPage schema)
- **Fail (info):** No FAQ content patterns detected
- **Note:** FAQ content is highly citable by AI systems

#### citation-blocks
- **Look for:** Citation-ready content: self-contained answer passages (~134-167 words is the optimal length for AI citation), definition patterns ("X is..."), data tables, comparison tables, step-by-step lists, direct answers in the first 40-60 words of a section
- **Pass:** Content includes structured, extractable information blocks
- **Fail (info):** Content is purely narrative with no extractable blocks
- **Note:** AI systems are 28-40% more likely to cite content with clear, self-contained answers. Optimal cited passage length is ~134-167 words per industry research (analysis of 15,000+ AI Overview results). Content should also have a direct answer in the first 40-60 words of each section (the "hook").

#### internal-links
- **Look for:** Internal links between pages (<a href="/..."> or <Link> components)
- **Pass:** Pages link to related internal content
- **Fail (warning):** Pages appear isolated with few or no internal links

#### anchor-text
- **Look for:** Link text quality in internal links
- **Pass:** Link text is descriptive (e.g. "view our pricing plans")
- **Fail (info):** Links use generic text ("click here", "read more", "learn more")

#### thin-content
- **Look for:** Pages with very little substantive content (mostly UI chrome, very short text)
- **Pass:** Pages have meaningful content depth
- **Fail (warning):** Pages detected with very thin content that may be seen as low-quality by search engines
- **Note:** This is a judgment call — flag only obviously thin pages

### SEMANTIC HTML

#### semantic-html
- **Look for:** Use of semantic HTML elements: <article>, <nav>, <main>, <section>, <aside>, <header>, <footer>
- **Pass:** Semantic elements used appropriately to structure content
- **Fail (info):** Page structure relies primarily on <div> elements (div soup)
- **Note:** Semantic HTML helps both search engines and AI systems understand content structure

---

## Output Format

Return ONLY a JSON block:

{
  "scan_type": "content",
  "framework": "[detected framework]",
  "findings": [
    {
      "check": "[check-id]",
      "status": "pass|fail|warning|skip",
      "severity": "critical|warning|info|null",
      "file": "path/to/file or null",
      "line": 42 or null,
      "detail": "What was found or what is missing",
      "context": "Relevant code snippet (optional)",
      "fix": "Suggested fix (only for fail/warning, else null)"
    }
  ]
}

**Rules:**
- Report ONE finding per check ID
- Include ALL checks — use "skip" for non-applicable checks
- When a check applies to multiple files (e.g. image-alt across many files), summarize: "12/15 images have alt text, 3 missing in: file1.tsx:20, file2.tsx:45, file3.tsx:12"
- Be specific about file paths and line numbers
- Framework-specific fix guidance in the "fix" field
```

---

## Step 5: Verification (Cross-Reference)

After all subagents return their findings JSON, the orchestrator performs cross-reference verification. This uses ONLY the subagent findings data and the scanner file tree — no file reading.

**Only run cross-references when the relevant scan types were both executed.** For example, "FAQ schema → FAQ content" requires both schema and content scans. If the user ran `/seo --schema` only, skip cross-references that need content data.

**Cross-reference checks:**

1. **Schema entity → page exists:**
   For each entity in the schema subagent's `entities` array:
   - If an Organization entity references a URL path (e.g. `https://example.com/about`), check if an about page exists in the scanner file tree
   - If a Person entity has a `url` pointing to an author page, check if that route exists

2. **Trust pages → schema:**
   If the schema subagent found trust pages (about, contact, privacy), check if those pages also have appropriate schema (Organization on about, ContactPage on contact)

3. **FAQ schema → FAQ content:**
   If schema subagent found FAQPage schema, check if content subagent found `faq-patterns` as pass. If FAQPage schema exists but no FAQ content patterns, that's suspicious.

4. **Author schema → author pages:**
   If schema subagent found Person entities as article authors, check if corresponding author/about pages exist in the file tree

5. **Sitemap → routes:**
   If technical subagent found a static sitemap, check that listed paths correspond to actual route files. Skip this for dynamically generated sitemaps.

6. **Dynamic route awareness:**
   Skip cross-reference checks for dynamic routes (`[slug]`, `[...params]`, `:id`, `_slug.vue`). Note "dynamic route — cannot verify" instead of flagging as missing.

**For each cross-reference failure, add a finding:**
```json
{
  "check": "cross-ref-[description]",
  "status": "warning",
  "severity": "warning",
  "file": null,
  "line": null,
  "detail": "[What was referenced and what's missing]",
  "fix": "[What to create or fix]"
}
```

### Step 6: Write docs/SEO_REPORT.md

Compile findings into the report. **Only include actionable items** — do NOT list passed or skipped checks individually.

```markdown
---
last_audited: YYYY-MM-DDTHH:MM:SSZ
scanner_version: 2.0.1
framework: [detected framework]
scan_types: [list of scan types that were run]
findings_summary:
  critical: N
  warning: N
  info: N
  passed: N
---

# SEO Audit Report

> Auto-generated by Recon SEO. Last audited: [date]
> Framework: [framework name] | [N] checks passed, [N] need attention

## Issues

[List ALL critical and warning findings. Each as a concise action item with file:line and fix.]

### [Issue title — e.g. "No sitemap.xml"]
**Severity:** critical | **File:** `public/robots.txt`
[One-line explanation of the problem]
**Fix:** [Framework-specific fix — e.g. "Install next-sitemap: `npm i next-sitemap` and add next-sitemap.config.js"]

### [Next issue]
...

## Opportunities

[Info-level findings that aren't broken but could improve visibility. Keep brief — one line each with what and why.]

- **Add llms.txt** — Helps AI crawlers discover key content. Growing adoption in 2026.
- **Add SpeakableSpecification** — Marks content for voice/AI extraction. Improves citation eligibility.
- ...

## Schema Inventory

[Only if schema scan was run. Table of ALL JSON-LD blocks found — this is reference, not an issue list.]

| Type | File | Status | Notes |
|------|------|--------|-------|
| Organization | app/layout.tsx:15 | Complete | Has sameAs, logo, contactPoint |
| Article | app/blog/[slug]/page.tsx:8 | Missing dateModified | Add dateModified for freshness signal |

## Cross-Reference Issues

[Only if verification step found issues. Otherwise omit this section entirely.]

- Person schema references `/about/team` but no matching route file exists
- ...
```

**Formatting rules:**
- **Actionable items only.** Do NOT list passed checks. Do NOT list skipped checks. The reader should see only what needs attention.
- Keep the report as short as possible while being complete. Every line should be something the reader can act on or needs to know.
- Group critical and warning findings together under "Issues" — no need to separate by scan type. The reader cares about priority, not which checklist found it.
- "Opportunities" section is brief — one line per item, no multi-line explanations.
- "Schema Inventory" is a reference table, not a list of issues. Include it because structured data is hard to audit without seeing what exists.
- Omit sections entirely if they're empty (e.g. no cross-reference issues = no section).
- End with a line: `[N] of [N] checks passed. Run /seo --force to re-audit.`

### Step 7: Completion Message

After writing the report, display a summary:

```
SEO audit complete. Framework: [name]

Critical: N | Warnings: N | Info: N | Passed: N

Report: docs/SEO_REPORT.md

If recon helped you, consider starring: https://github.com/EfrainTorres/recon
```

## Update Mode

When updating an existing audit:

1. Check git for changes since `last_audited`
2. Re-run scanner to get current file tree
3. Re-run only scan types where relevant files changed
4. Merge new findings with existing report
5. Update `last_audited` timestamp
6. Preserve findings for unchanged sections

## Token Budget Reference

| Model | Context Window | Default Budget per Subagent | Custom Budget |
|-------|---------------|---------------------------|---------------|
| Sonnet | 1,000,000 | 750,000 | — |
| Opus | 1,000,000 | 750,000 | `--opus Nk` (e.g. `--opus 500k`) |
| Haiku | 200,000 | 100,000 | — |

SEO subagents typically need far less context than Recon subagents since SEO-relevant files are a small fraction of the total codebase. Most projects will use one subagent per scan type.

> **Note:** Haiku 4.5 retains a 200k context window. If subagents are overridden to Haiku (e.g. via `CLAUDE_CODE_SUBAGENT_MODEL`), the budget should be reduced to ~100k.

## Troubleshooting

**Scanner fails with tiktoken error:**
```bash
pip install tiktoken
# or with uv:
uv pip install tiktoken
```

**Python not found:**
Try `python3`, `python`, or use `uv run` which handles Python automatically.

**No framework detected:**
This is normal for static HTML sites or unconventional setups. The audit will use generic HTML patterns. All checks still apply — the "fix" suggestions will use plain HTML guidance instead of framework-specific APIs.

**Very few SEO-relevant files found:**
Some codebases (backends, CLIs, libraries) are not web applications. The audit will produce mostly "skip" results. This is expected — SEO audits are for web-facing applications.

**Scanner path not found:**
The scanner is shared with the Recon skill at `${CLAUDE_PLUGIN_ROOT}/skills/recon/scripts/scan-codebase.py`. If this path fails, the Recon plugin may not be installed correctly. Try reinstalling: `/plugin install recon`
