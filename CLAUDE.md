# CLAUDE.md

## Codebase Overview

Recon is a multi-platform codebase mapping tool that runs a Python scanner to collect metadata, spawns parallel AI subagents to analyze file groups, and synthesizes results into a persistent map.

**Stack**: Python (scanner), Markdown (documentation/prompts), JSON (configs)
**Structure**: `plugins/recon/` (Claude Code plugin), `cursor/` (Cursor support), root (shared docs)
**Health**: Documentation duplication between platforms (SKILL.md and cursor/agents/recon.md are 80%+ identical). Scanner has complexity issues (250-line `scan_directory()` function).

For detailed architecture and health analysis, see [docs/RECON_REPORT.md](docs/RECON_REPORT.md).

## Key Files

- `plugins/recon/skills/recon/scripts/scan-codebase.py` — Core scanner (9.8k tokens)
- `plugins/recon/skills/recon/SKILL.md` — Orchestrator instructions
- `cursor/agents/recon.md` — Cursor orchestrator agent
