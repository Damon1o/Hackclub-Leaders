## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- Only use graphify when the user explicitly types `/graphify` or asks you to use it.
- For all codebase questions, use grep, glob, and read tools directly instead of graphify.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
