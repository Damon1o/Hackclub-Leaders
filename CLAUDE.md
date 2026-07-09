# Ruflo — Claude Code Configuration

## User

- The user's name is Damon. Refer to them as Damon.
- Start every conversation by greeting Damon by name.

## Rules

- Do what has been asked; nothing more, nothing less
- NEVER create files unless absolutely necessary — prefer editing existing files
- NEVER create documentation files unless explicitly requested
- NEVER save working files or tests to root — use `/src`, `/tests`, `/docs`, `/config`, `/scripts`
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files
- NEVER add `Co-Authored-By` trailers to commits
- Keep files under 500 lines
- Validate input at system boundaries

## Agent Comms (SendMessage-First Coordination)

Named agents coordinate via `SendMessage`, not polling or shared state.

```
Lead ←→ architect ←→ developer ←→ tester ←→ reviewer
```

Spawn ALL agents in ONE message with `run_in_background: true`, each knowing who to message next. Kick off the pipeline with `SendMessage` to the first agent.

### Patterns

| Pattern | Flow | Use When |
|---------|------|----------|
| Pipeline | A → B → C → D | Sequential dependencies |
| Fan-out | Lead → A, B, C → Lead | Independent parallel work |
| Supervisor | Lead ↔ workers | Ongoing coordination |

### Rules

- ALWAYS name agents — `name: "role"` makes them addressable
- ALWAYS include comms instructions in prompts
- Spawn ALL agents in ONE message with `run_in_background: true`
- After spawning: STOP, tell user what's running, wait for results
- NEVER poll status — agents message back or complete automatically

## Swarm & Routing

### Agent Routing

| Task | Agents |
|------|--------|
| Bug Fix | researcher, coder, tester |
| Feature | architect, coder, tester, reviewer |
| Refactor | architect, coder, reviewer |
| Performance | perf-engineer, coder |
| Security | security-architect, auditor |

### When to Swarm

- YES: 3+ files, new features, cross-module refactoring, API changes, security, performance
- NO: single file edits, 1-2 line fixes, docs updates, config changes, questions

## MCP Tools

Use `ToolSearch("keyword")` to discover tools. Key categories: Memory, Swarm, Agents, Hooks, Security.

## Agents

Core: coder, reviewer, tester, planner, researcher. Architecture: system-architect, backend-dev. Security: security-architect, security-auditor. Performance: performance-engineer. Coordination: hierarchical-coordinator, mesh-coordinator, adaptive-coordinator. Any string works as a custom type.

## Build & Test

- ALWAYS run tests after code changes
- ALWAYS verify build succeeds before committing

```bash
pytest tests/ -v
```

## Setup

```bash
claude mcp add claude-flow -- npx -y ruflo@latest mcp start
npx ruflo@latest doctor --fix
```

Agent tool handles execution. MCP tools handle coordination. CLI is the same via Bash.
