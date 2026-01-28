# Recon for Cursor

Cursor-native subagents for codebase mapping. Same powerful analysis as the Claude Code plugin, built for Cursor's subagent system.

## Installation

### Step 1: Copy the subagent files

Copy the agent files to your project's `.cursor/agents/` directory:

```bash
# From your project root
mkdir -p .cursor/agents

# Download the agent files
curl -o .cursor/agents/recon.md https://raw.githubusercontent.com/EfrainTorres/recon/main/cursor/agents/recon.md
curl -o .cursor/agents/recon-analyzer.md https://raw.githubusercontent.com/EfrainTorres/recon/main/cursor/agents/recon-analyzer.md
```

Or manually copy from this repository:
- `cursor/agents/recon.md` → `.cursor/agents/recon.md`
- `cursor/agents/recon-analyzer.md` → `.cursor/agents/recon-analyzer.md`

### Step 2: Copy the scanner script

The scanner is a standalone Python script that gathers codebase metadata:

```bash
# From your project root
mkdir -p scripts

# Download the scanner
curl -o scripts/scan-codebase.py https://raw.githubusercontent.com/EfrainTorres/recon/main/plugins/recon/skills/recon/scripts/scan-codebase.py
chmod +x scripts/scan-codebase.py
```

Or manually copy:
- `plugins/recon/skills/recon/scripts/scan-codebase.py` → `scripts/scan-codebase.py`

### Step 3: Install dependencies

The scanner requires `tiktoken` for token counting:

```bash
# With UV (recommended - handles dependencies automatically)
# No manual install needed - uv run will install tiktoken

# Or with pip
pip install tiktoken
```

## Usage

In Cursor, invoke the recon subagent:

```
/recon
```

Or use natural language:
- "recon my project"
- "scan my project"
- "document the architecture"
- "understand this codebase"

For a full re-scan (ignoring existing map):
```
/recon --force
```

## What It Does

Recon orchestrates multiple analyzer subagents to map your codebase in parallel:

1. **Scans** - Runs the Python scanner for file tree, token counts, git stats, entrypoints
2. **Plans** - Splits work across subagents based on token budgets (~150k each)
3. **Analyzes** - Spawns `recon-analyzer` subagents in parallel to read code
4. **Synthesizes** - Combines reports into `docs/RECON_REPORT.md`

### Output

- `docs/RECON_REPORT.md` - Comprehensive codebase documentation:
  - Architecture diagram
  - Entrypoints and config surface
  - Module guide with file purposes
  - Health summary (hotspots, staleness, duplication, complexity)
  - Suggested first actions
- Updates `CLAUDE.md` or `AGENTS.md` with a summary

## How It Works with Cursor Subagents

Recon uses Cursor's subagent system for parallel analysis:

```
recon (orchestrator)
    │
    ├─→ recon-analyzer (module 1) ──→ analysis report
    ├─→ recon-analyzer (module 2) ──→ analysis report
    ├─→ recon-analyzer (module 3) ──→ analysis report
    └─→ recon-analyzer (module 4) ──→ analysis report
                                          │
                        synthesize ←──────┘
                            │
                            ▼
                   RECON_REPORT.md
```

The orchestrator (`recon.md`) uses the Task tool to spawn multiple `recon-analyzer` instances. Since custom subagents inherit the Task tool, this nested orchestration works natively in Cursor.

## Differences from Claude Code Version

| Aspect | Claude Code | Cursor |
|--------|-------------|--------|
| Installation | `/plugin install recon` | Copy files to `.cursor/agents/` |
| Invocation | Skill auto-triggered | `/recon` or natural language |
| Scanner path | `$CLAUDE_PLUGIN_ROOT/...` | `./scripts/scan-codebase.py` |
| Subagent model | `model: "sonnet"` | `model: inherit` |

The analysis logic, output format, and quality are identical.

## Troubleshooting

**Scanner not found:**
Ensure `scripts/scan-codebase.py` exists in your project root and is executable.

**tiktoken error:**
```bash
pip install tiktoken
# or
uv pip install tiktoken
```

**Subagents not spawning:**
Cursor's custom subagents inherit the Task tool. If subagents aren't being created, check that:
- Both `recon.md` and `recon-analyzer.md` are in `.cursor/agents/`
- You're using a Cursor version that supports subagents (2.4+)

**Large codebase timeout:**
- Increase token budget or reduce scope with scanner flags
- Use `--exclude` to skip test/vendor directories on first pass

## Known Issues

### Task Tool Bug (January 2026)

There is a [known bug](https://forum.cursor.com/t/task-tool-missing-for-custom-agents-in-cursor-agents-documentation-pages-return-errors/149771) in Cursor 2.4.x and 2.5 nightly where the Task tool is not available to custom subagents. This prevents the `recon` orchestrator from spawning `recon-analyzer` subagents.

**Status**: Cursor team has acknowledged the issue and is working on a fix. No timeline yet.

**Impact**: Until fixed, Recon's parallel analysis won't work. The orchestrator may fall back to single-agent mode (limited to smaller codebases that fit in one context window).

**Workaround**: Use the [Claude Code version](../README.md) which works fully today.

**Check for updates**: Once Cursor releases a fix, Recon should work automatically with no changes needed.

## Requirements

- Cursor 2.4+ (subagent support)
- Python 3.9+
- tiktoken (`pip install tiktoken` or use `uv run`)

## License

AGPL-3.0
