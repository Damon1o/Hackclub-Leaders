# Graph Report - .  (2026-07-07)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 159 nodes · 346 edges · 13 communities (11 shown, 2 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 5 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `01981829`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 6
- Community 8
- Community 9
- Community 10
- Community 11

## God Nodes (most connected - your core abstractions)
1. `AirtableStorage` - 24 edges
2. `register()` - 19 edges
3. `SessionStorage` - 18 edges
4. `register()` - 14 edges
5. `_storage()` - 13 edges
6. `json_error()` - 13 edges
7. `register()` - 13 edges
8. `save_dashboard_state()` - 12 edges
9. `clean_text()` - 12 edges
10. `get_dashboard_state()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `_payload_too_large()` --calls--> `json_error()`  [EXTRACTED]
  app.py → helpers.py
- `get_dashboard_state()` --indirect_call--> `SessionStorage`  [INFERRED]
  helpers.py → storage.py
- `StateTooLarge` --uses--> `SessionStorage`  [INFERRED]
  helpers.py → storage.py
- `save_dashboard_state()` --indirect_call--> `SessionStorage`  [INFERRED]
  helpers.py → storage.py
- `_persist_club()` --indirect_call--> `SessionStorage`  [INFERRED]
  helpers.py → storage.py

## Import Cycles
- None detected.

## Communities (13 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.21
Nodes (28): admin_required(), clean_text(), event_from_payload(), find_by_id(), _find_club_by_project(), generate_join_code(), _item_id(), _join_missing() (+20 more)

### Community 1 - "Community 1"
Cohesion: 0.10
Nodes (12): main(), Delete test records from the live Airtable base.  During development, sign-in te, AirtableStorage, State shared across the club via an Airtable base.      Loads/saves are whole-cl, All records in `table` where {field} = value, following pagination., Every record in `table`, following pagination., Create/update/delete records in Airtable's 10-per-request batches., Members belong to the club whose roster lists their email;         everyone else (+4 more)

### Community 2 - "Community 2"
Cohesion: 0.13
Nodes (6): make_storage(), Storage backends for the dashboard state.  The app talks to one of two backends,, Summary of every club, for the admin overview. Three full-table         scans (c, Build the backend named by STORAGE_BACKEND (default: session)., Today's behavior: the whole state rides in the session cookie., SessionStorage

### Community 3 - "Community 3"
Cohesion: 0.20
Nodes (6): inject_user(), _payload_too_large(), get_csrf_token(), is_admin(), viewer_is_leader(), viewer_role()

### Community 4 - "Community 4"
Cohesion: 0.18
Nodes (5): Exception, StateTooLarge, Raised when the configured backend cannot read or write state., StorageError, test_error_handlers()

### Community 6 - "Community 6"
Cohesion: 0.42
Nodes (10): _club_key(), default_dashboard_state(), get_dashboard_state(), leader_required(), save_dashboard_state(), _state_cookie_size(), _storage(), viewer_club_lite() (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.22
Nodes (8): CLAUDE_FLOW_HOOKS_ENABLED, CLAUDE_FLOW_MAX_AGENTS, CLAUDE_FLOW_MEMORY_BACKEND, CLAUDE_FLOW_MODE, CLAUDE_FLOW_TOPOLOGY, npm_config_update_notifier, cmd, claude-flow

### Community 9 - "Community 9"
Cohesion: 0.67
Nodes (3): fail(), main(), Airtable readiness check.  Run this after creating your base and setting AIRTABL

## Knowledge Gaps
- **10 isolated node(s):** `cmd`, `npm_config_update_notifier`, `CLAUDE_FLOW_MODE`, `CLAUDE_FLOW_HOOKS_ENABLED`, `CLAUDE_FLOW_TOPOLOGY` (+5 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AirtableStorage` connect `Community 1` to `Community 2`, `Community 4`?**
  _High betweenness centrality (0.202) - this node is a cross-community bridge._
- **Why does `SessionStorage` connect `Community 2` to `Community 0`, `Community 1`, `Community 4`, `Community 6`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `StateTooLarge` connect `Community 4` to `Community 0`, `Community 2`, `Community 3`, `Community 6`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `SessionStorage` (e.g. with `get_dashboard_state()` and `_persist_club()`) actually correct?**
  _`SessionStorage` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `cmd`, `npm_config_update_notifier`, `CLAUDE_FLOW_MODE` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.0967741935483871 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._