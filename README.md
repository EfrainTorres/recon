# Recon

AI-powered codebase mapping with parallel subagents. Produces architecture documentation, health analysis, and actionable recommendations.

## Platforms

| Platform | Status | Installation |
|----------|--------|--------------|
| **Claude Code** | ✅ Stable | [Get Started](#claude-code) |
| **Cursor** | ⚠️ Beta | [Get Started](#cursor) |
| **Codex** | 🔜 Coming Soon | — |

---

## Claude Code

**Install:**
```
/plugin marketplace add EfrainTorres/recon
/plugin install recon
```

**Use:**
```
/recon
```

Or say "recon my project" — it triggers automatically.

For a full re-scan: `/recon --force`

**Requirements:** tiktoken (auto-installed with `uv run`, or `pip install tiktoken`)

📖 [Full Claude Code documentation](plugins/recon/README.md)

---

## Cursor

**Install:**
```bash
# Copy agents to your project
mkdir -p .cursor/agents
curl -o .cursor/agents/recon.md https://raw.githubusercontent.com/EfrainTorres/recon/main/cursor/agents/recon.md
curl -o .cursor/agents/recon-analyzer.md https://raw.githubusercontent.com/EfrainTorres/recon/main/cursor/agents/recon-analyzer.md

# Copy scanner
mkdir -p scripts
curl -o scripts/scan-codebase.py https://raw.githubusercontent.com/EfrainTorres/recon/main/plugins/recon/skills/recon/scripts/scan-codebase.py
chmod +x scripts/scan-codebase.py
```

**Use:**
```
/recon
```

Or say "recon my project".

**Requirements:** Cursor 2.4+, Python 3.9+, tiktoken

> ⚠️ **Known Issue:** Cursor 2.4.x/2.5 has a [bug](https://forum.cursor.com/t/task-tool-missing-for-custom-agents-in-cursor-agents-documentation-pages-return-errors/149771) preventing subagent spawning. Parallel analysis won't work until Cursor releases a fix. Use Claude Code for full functionality.

📖 [Full Cursor documentation](cursor/README.md)

---

## What it Does

Recon orchestrates multiple subagents to analyze your codebase in parallel, then synthesizes their findings into:

- **`docs/RECON_REPORT.md`** — Comprehensive codebase documentation:
  - Architecture map with file purposes, dependencies, data flows
  - Entrypoints — where execution begins
  - Config surface — all configuration files by category
  - Health summary — hotspots, staleness, duplication, complexity
  - Suggested first actions — top 5 priorities for improvement
- Updates `CLAUDE.md` with a summary pointing to the map

## How it Works

1. **Scan** — Runs v2 scanner for file tree, token counts, git stats, entrypoints, duplicates
2. **Plan** — Splits work across subagents based on token budgets (~150k each)
3. **Analyze** — Spawns subagents in parallel with enhanced observation prompts
4. **Synthesize** — Combines subagent reports + scanner metadata into documentation

## Features (v2)

**Scanner Intelligence:**
- Git-powered analysis: churn hotspots, staleness detection, co-change coupling
- Entrypoint detection (package.json, pyproject.toml, Cargo.toml, Dockerfile)
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
