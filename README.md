# Recon

A Claude Code plugin that maps and documents codebases of any size using parallel AI subagents. **Now with codebase health intelligence.**

## Installation

**Step 1:** Add the marketplace to Claude Code:

```
/plugin marketplace add EfrainTorres/recon
```

**Step 2:** Install the plugin:

```
/plugin install recon
```

**Step 3:** Restart Claude Code (may be required for the skill to load)

**Step 4:** Use it:

```
/recon
```

Or just say "map this codebase" and it will trigger automatically.

For a full re-scan: `/recon --force`

## What it Does

Recon orchestrates multiple Sonnet subagents to analyze your entire codebase in parallel, then synthesizes their findings with scanner metadata into:

- `docs/CODEBASE_MAP.md` - Comprehensive codebase documentation:
  - Architecture map with file purposes, dependencies, data flows
  - **Entrypoints** - Where execution begins
  - **Config surface** - All configuration files by category
  - **Health summary** - Hotspots, staleness, duplication, complexity
  - **Suggested first actions** - Top 5 priorities for improvement
- Updates `CLAUDE.md` with a summary pointing to the map

## What's New in v2

**Scanner Intelligence:**
- Git-powered analysis: churn hotspots, staleness detection, co-change coupling
- Entrypoint detection (package.json, pyproject.toml, Cargo.toml, Dockerfile, conventions)
- Config surface listing by category
- Exact duplicate detection via content hashing
- Generated code detection (excluded from health signals)
- TODO/FIXME counting and distribution

**Health Observations:**
- Subagents actively look for unused code, complexity issues, duplication patterns
- Evidence-based confidence levels for cleanup recommendations
- Coverage tracking (what was actually analyzed)

**Actionable Output:**
- Health Summary section with prioritized findings
- Suggested First Actions (top 5 things to address)
- Knowledge risk identification (single-author critical files)

## How it Works

1. **Scan** - Runs v2 scanner for file tree, token counts, git stats, entrypoints, duplicates
2. **Plan** - Splits work across subagents based on token budgets (~150k each)
3. **Analyze** - Spawns Sonnet subagents in parallel with enhanced observation prompts
4. **Synthesize** - Combines subagent reports + scanner metadata into documentation

## Update Mode

If `docs/CODEBASE_MAP.md` already exists, Recon will:

1. Check git history for changes since last mapping
2. Only re-analyze changed modules
3. Refresh health metrics (git stats change even without file changes)
4. Merge updates with existing documentation

Just run `/recon` again to update.

## Token Usage

This skill spawns Sonnet subagents for accurate, reliable analysis. Token usage depends on codebase size. Each subagent analyzes ~150k tokens of code.

You can ask Claude to use Haiku subagents instead for a cheaper run, but accuracy may suffer on complex codebases.

## Requirements

- tiktoken (for token counting)

With UV (recommended - auto-installs dependencies):
```bash
uv run scan-codebase.py .
```

Or install manually:
```bash
pip install tiktoken
```

## Full Documentation

See [plugins/recon/README.md](plugins/recon/README.md) for detailed documentation including scanner CLI options.

## Philosophy

> Heuristics with honesty beat precision with complexity.

- Language-agnostic: works on any language, any stack, any size
- Scanner measures, LLMs judge
- Output is curated prose, not data dumps
- Single markdown file = predictable token cost

## Acknowledgments

Recon is based on [Cartographer](https://github.com/kingbootoshi/cartographer) by [@kingbootoshi](https://github.com/kingbootoshi). The v2 scanner and health intelligence features build on his original vision for AI-powered codebase mapping.

## License

MIT
