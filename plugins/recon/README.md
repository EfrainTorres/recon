# Recon

A Claude Code plugin that maps and documents codebases of any size using parallel AI subagents. Now with **codebase health intelligence**: hotspot detection, unused code candidates, duplication analysis, and actionable recommendations.

## What it does

Recon orchestrates multiple Sonnet subagents to analyze your entire codebase in parallel, then synthesizes their findings with scanner metadata into comprehensive documentation:

- `docs/RECON_REPORT.md` - Architecture map with:
  - File purposes, dependencies, data flows
  - **Entrypoints** and **config surface**
  - **Health summary**: hotspots, staleness, duplication, cleanup candidates
  - **Suggested first actions** (top 5 priorities)
- Updates `CLAUDE.md` with a summary pointing to the map

## Installation

### Via Claude Code Plugin Marketplace

```
/plugin marketplace add EfrainTorres/recon
/plugin install recon
```

### Manual Installation (Development)

Clone the repo and load with `--plugin-dir`:

```bash
git clone https://github.com/EfrainTorres/recon.git ~/recon
claude --plugin-dir ~/recon/plugins/recon
```

### Dependencies

The scanner script uses tiktoken. With UV (recommended), dependencies are auto-installed:

```bash
# UV handles dependencies automatically
uv run scan-codebase.py .
```

Or install manually:

```bash
pip install tiktoken
```

## Usage

Simply invoke the skill:

```
/recon
```

Or say:
- "recon my project"
- "scan my project"
- "document the architecture"
- "understand this codebase"

### Force Full Re-scan

To force a complete re-analysis (ignoring existing map):

```
/recon --force
```

Or say: "remap everything", "full recon scan"

### Update Mode

If `docs/RECON_REPORT.md` already exists, Recon will:

1. Check git history for changes since last mapping
2. Only re-analyze changed modules
3. Refresh health metrics (git stats can change without file changes)
4. Merge updates with existing documentation

Just run `/recon` again to update.

## How it Works

```
/recon invoked
        |
        v
+---------------------------------------+
|  1. Run scanner (v2)                  |
|     - File tree with token counts     |
|     - Entrypoint detection            |
|     - Config surface listing          |
|     - Git intelligence (churn,        |
|       staleness, co-change)           |
|     - Duplicate detection (hashing)   |
|     - Generated code detection        |
|     - TODO/FIXME counting             |
+---------------------------------------+
        |
        v
+---------------------------------------+
|  2. Plan subagent assignments         |
|     - Group files by module           |
|     - Balance token budgets (~150k)   |
|     - Prioritize hotspots             |
|     - Exclude generated files         |
+---------------------------------------+
        |
        v
+---------------------------------------+
|  3. Spawn Sonnet subagents PARALLEL   |
|     - Standard analysis (purpose,     |
|       exports, patterns, gotchas)     |
|     - Health observations:            |
|       * Unused code candidates        |
|       * Complexity hotspots           |
|       * Duplication patterns          |
|       * Coupling concerns             |
+---------------------------------------+
        |
        v
+---------------------------------------+
|  4. Synthesize all reports            |
|     - Merge subagent outputs          |
|     - Combine with scanner metadata   |
|     - Build architecture diagram      |
|     - Generate health summary         |
|     - Create suggested actions        |
+---------------------------------------+
        |
        v
+---------------------------------------+
|  5. Write docs/RECON_REPORT.md        |
|     Update CLAUDE.md with summary     |
+---------------------------------------+
```

## Output Structure

The generated `docs/RECON_REPORT.md` includes:

### Structural Documentation
- **System Overview** - Mermaid architecture diagram
- **Entrypoints** - Where execution begins (from configs and conventions)
- **Config Surface** - Configuration files by category
- **Directory Structure** - Annotated file tree (source vs generated)
- **Module Guide** - Per-module documentation with exports, dependencies
- **Data Flow** - Sequence diagrams for key flows
- **Conventions** - Naming, patterns, style
- **Gotchas** - Non-obvious behaviors and warnings
- **Navigation Guide** - How to add features, modify systems

### Health Intelligence (New in v2)
- **Hotspots** - High-churn files + complexity observations
- **Staleness** - Files/directories not touched in 6+ months
- **Knowledge Risk** - Single-author files in critical paths
- **Coupled Files** - Files that always change together (co-change analysis)
- **Duplication** - Exact duplicates (hash) + semantic duplicates (subagent)
- **Cleanup Candidates** - Unused files/exports with confidence levels
- **Complexity** - Large files, nested logic, TODO/FIXME density
- **Suggested First Actions** - Top 5 prioritized recommendations

## Scanner CLI Options

The v2 scanner supports filtering:

```bash
# Show top 20 files by token count
uv run scan-codebase.py . --top 20

# Sort by git churn instead of tokens
uv run scan-codebase.py . --sort churn

# Filter by extension
uv run scan-codebase.py . --ext .ts,.tsx

# Include/exclude patterns
uv run scan-codebase.py . --include "src/**" --exclude "test/**"

# Output formats
uv run scan-codebase.py . --format json   # Full metadata (default)
uv run scan-codebase.py . --format tree   # Visual tree
uv run scan-codebase.py . --format compact # Sorted list
```

## Token Budgets

| Model | Context Window | Budget per Subagent |
|-------|---------------|---------------------|
| Sonnet | 200,000 | 150,000 |
| Opus | 200,000 | 100,000 |
| Haiku | 200,000 | 100,000 |

Recon uses Sonnet subagents by default for best capability/cost balance.

## Configuration

The scanner respects `.gitignore` (including nested files and negation patterns) and has sensible defaults for:
- Ignoring `node_modules`, `dist`, `build`, `vendor`, etc.
- Skipping binary files
- Skipping files over 1MB or 50k tokens
- Detecting generated code (by path and header markers)

## Philosophy

**Heuristics with honesty beat precision with complexity.**

- Scanner gathers deterministic metadata (fast, cheap)
- Subagents make intelligent judgments (contextual, language-aware)
- Output is curated prose, not data dumps
- Works on any language, any stack, any size
- Single markdown file = predictable token cost for AI agents

## License

AGPL-3.0
