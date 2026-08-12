# Claude Code Configuration

## User

- The user's name is Damon. Refer to them as Damon.
- Start every conversation by greeting Damon by name.

## Rules

- NEVER create files unless absolutely necessary — prefer editing existing files
- NEVER create documentation files unless explicitly requested
- NEVER save working files or tests to root — use `/src`, `/tests`, `/docs`, `/config`, `/scripts`
- NEVER commit secrets, credentials, or .env files
- NEVER add `Co-Authored-By` trailers to commits
- Keep files under 500 lines
- ALWAYS use Rust Token Killer (`rtk`) for codebase searches and grep — never fall back to plain `grep`/`Select-String` when `rtk` is available
