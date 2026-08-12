# Graph Report - Hackclub Leaders  (2026-08-12)

## Corpus Check
- 65 files · ~93,381 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 862 nodes · 1646 edges · 51 communities (42 shown, 9 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 46 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c6da7df9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 8
- Community 9
- Community 10
- Community 11
- test_coins.py
- test_workshops.py
- test_admin_shop.py
- test_pagination.py
- test_notifications.py
- Brag Plan: Hack Club Leaders
- Task 4 Implementation Report: Link preview fetcher with SSRF guards
- Task 1: Feature Flag Helper — Implementation Report
- Task 2: Storage — Metadata JSON field, attachment loading, Airtable schema — Report
- File Structure
- Task 3 Report: `AirtableStorage.upload_attachment`
- Sections
- Task 5 Report: Wire link previews into message posting
- Coins Spine: Ledger, Dollar Removal, Shop Conversion
- Workshops: Propose, Apply-to-Run, Schedule, Track
- Global Constraints
- Hyperframes Composition Brief: Hack Club Leaders
- Chat Sprint 1: Uploads, Link Previews, Markdown + Feature Flags
- Global Constraints
- Global Constraints
- ideas.md
- scripts
- Global Constraints
- split_i18n_data.py
- paths
- Global Constraints
- Photo upload: preview + crop/zoom before upload
- Global Constraints
- Sidebar redesign + notifications-into-newsletters
- setup_chat_tables.py
- progress.md
- task-1-brief.md
- task-2-brief.md
- task-3-brief.md
- task-4-brief.md
- task-5-brief.md

## God Nodes (most connected - your core abstractions)
1. `_seed()` - 45 edges
2. `StorageError` - 43 edges
3. `AirtableStorage` - 39 edges
4. `SessionStorage` - 36 edges
5. `MongoStorage` - 33 edges
6. `register()` - 30 edges
7. `get_dashboard_state()` - 25 edges
8. `_seed_message()` - 24 edges
9. `_msg()` - 24 edges
10. `_seed()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `test_default_dashboard_state_seeds_a_starter_grant()` --calls--> `default_dashboard_state()`  [EXTRACTED]
  tests/test_coins.py → src/helpers.py
- `test_default_dashboard_state_seeds_empty_workshops()` --calls--> `default_dashboard_state()`  [EXTRACTED]
  tests/test_workshops.py → src/helpers.py
- `test_error_handlers()` --calls--> `StateTooLarge`  [EXTRACTED]
  tests/test_api.py → src/helpers.py
- `test_add_in_app_notification_with_explicit_state_caps_at_100()` --calls--> `add_in_app_notification()`  [EXTRACTED]
  tests/test_notifications.py → src/notifications.py
- `test_add_in_app_notification_with_explicit_state_skips_ambient_lookup()` --calls--> `add_in_app_notification()`  [EXTRACTED]
  tests/test_notifications.py → src/notifications.py

## Import Cycles
- None detected.

## Communities (51 total, 9 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (33): MongoClient, _as_bool(), _as_int(), _item_from_row(), load_states(), main(), Import club data from Airtable CSV exports into MongoDB.  Fallback for scripts/s, Mirror AirtableStorage.load() output for every club, built from CSVs. (+25 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (21): main(), Delete test records from the live Airtable base.  During development, sign-in, AirtableStorage, make_storage(), Any, Storage backends for the dashboard state.  The app talks to one of three backe, State shared across the club via an Airtable base.      Loads/saves are whole-, All records in `table` where {field} = value, following pagination.          ` (+13 more)

### Community 2 - "Community 2"
Cohesion: 0.10
Nodes (53): reset_rate_limits(), _iso(), _make_channel(), _msg(), Chat (channels + messages) API coverage.  These exercise *successful* authenti, Append a pre-built message onto the seeded dashboard state., _reset_rate_limit(), _seed() (+45 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (102): inject_user(), _payload_too_large(), _html_to_text(), Email notification system for the Hack Club Leaders Portal., Render the email sent to a member once a leader schedules them to run a workshop, Send email in background thread., Render project submission notification email., Render the email sent to a member when their shipped project is approved. (+94 more)

### Community 4 - "Community 4"
Cohesion: 0.21
Nodes (5): _save_settings(), test_default_state_has_language(), test_error_handlers(), test_settings_persists_supported_language(), test_settings_rejects_unsupported_language()

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (4): _i18n_translations(), test_i18n_all_languages_cover_public_page_keys(), test_storage_error_on_dashboard_redirects_once_not_forever(), test_storage_error_on_index_degrades_instead_of_looping()

### Community 6 - "Community 6"
Cohesion: 0.50
Nodes (4): convert_to_webp(), main(), Convert heavyweight raster images to WebP and rewrite local references.  Targets, Convert source_path to a sibling .webp. Returns the .webp path if     converted,

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (27): _embedded_state(), _messages(), mongo_client(), MongoStorage backend coverage, against an in-memory Mongo (mongomock).  These lo, A signed-in test client served by the Mongo backend., _state(), storage(), test_chat_page_embeds_chat_sections() (+19 more)

### Community 9 - "Community 9"
Cohesion: 0.67
Nodes (3): fail(), main(), Airtable readiness check.  Run this after creating your base and setting AIRTA

### Community 13 - "test_coins.py"
Cohesion: 0.07
Nodes (64): Exception, F, add_shop_item(), admin_required(), award_coins(), Channel, ClubState, ClubStateLite (+56 more)

### Community 14 - "test_workshops.py"
Cohesion: 0.17
Nodes (24): workshop_from_payload(), _base_workshop(), _seed_workshop_club(), test_apply_does_not_require_leader_role(), test_apply_rejected_once_workshop_is_scheduled(), test_apply_to_missing_workshop_404s(), test_apply_to_workshop_adds_viewer_to_applicants(), test_default_dashboard_state_seeds_empty_workshops() (+16 more)

### Community 15 - "test_admin_shop.py"
Cohesion: 0.11
Nodes (16): Point the shop writer at a throwaway catalog so tests never touch the     real, _read(), _seed(), _seed_project(), shop_file(), test_add_shop_item_appends_and_prices(), test_add_shop_item_route(), test_add_shop_item_route_rejects_bad_image() (+8 more)

### Community 16 - "test_pagination.py"
Cohesion: 0.16
Nodes (23): _messages(), Pagination and section-scoped loading across the API.  These run on the session, _seed(), test_chat_bad_limit_falls_back_to_default(), test_chat_before_cursor_reports_start_of_history(), test_chat_before_cursor_walks_backwards(), test_chat_limit_is_capped(), test_chat_limit_is_honoured() (+15 more)

### Community 17 - "test_notifications.py"
Cohesion: 0.12
Nodes (18): Notification centre API coverage.  The bell menu in dashboard_layout.html called, The literal path must not be matched as a notification id., _seed(), test_add_in_app_notification_with_explicit_state_caps_at_100(), test_add_in_app_notification_with_explicit_state_skips_ambient_lookup(), test_delete_notification(), test_delete_unknown_notification_is_404(), test_list_paginates() (+10 more)

### Community 18 - "Brag Plan: Hack Club Leaders"
Cohesion: 0.10
Nodes (19): Audio direction, Brag Plan: Hack Club Leaders, Duration: ~19s, Format: landscape — 1920x1080, Hook (first 2-3 seconds), Key moments (the middle), Outro / punchline, Scene 1 — Hook: "Where leaders build the future!" — 3s (+11 more)

### Community 19 - "Task 4 Implementation Report: Link preview fetcher with SSRF guards"
Cohesion: 0.11
Nodes (18): Code Quality ✅, Commit, Completeness ✅, Discipline ✅, Files Changed, Full Suite Results, GREEN Phase (after implementation), Module Additions to `src/routes_chat.py` (+10 more)

### Community 20 - "Task 1: Feature Flag Helper — Implementation Report"
Cohesion: 0.11
Nodes (17): Code Added, Code Quality, Commit, Concerns, Correctness, Files Changed, Full Test Suite Verification, GREEN Phase: Tests Pass (After Implementation) (+9 more)

### Community 21 - "Task 2: Storage — Metadata JSON field, attachment loading, Airtable schema — Report"
Cohesion: 0.12
Nodes (15): Code Quality, Commit Created, Completeness, Files Changed, Full Suite Verification, GREEN Phase, Implementation Details, Key Features (+7 more)

### Community 22 - "File Structure"
Cohesion: 0.13
Nodes (14): File Structure, Global Constraints, Post-plan cleanup (housekeeping, not a task), Self-Review Notes, Settings Page Redesign (Round 1) Implementation Plan, Task 1: Club profile data model — structured address + derived `location`, Task 2: Settings shell — scrollspy layout + sidebar nav, Task 3: Club profile section (fully built) (+6 more)

### Community 23 - "Task 3 Report: `AirtableStorage.upload_attachment`"
Cohesion: 0.13
Nodes (14): 1. **Added `import base64`** (Line 41), 2. **Added `supports_uploads` class attributes**, 3. **Implemented `AirtableStorage.upload_attachment()` method** (Lines 481-526), Commit, Files Changed, Fix Report (post-review), Full Suite Test Results, Implementation Summary (+6 more)

### Community 24 - "Sections"
Cohesion: 0.14
Nodes (13): 1. Club profile (fully built), 2. Members (real content, partial), 3. Your account (new section, stubbed data), 4. Appearance (real content), 5. Explore & privacy (real content), 6. Notifications (real content), 7. Danger zone (real content, gated by backend), Context (+5 more)

### Community 25 - "Task 5 Report: Wire link previews into message posting"
Cohesion: 0.14
Nodes (13): Code Quality Review, Commits, Completeness, Concerns, Discipline, Files Changed, Implementation Summary, Pattern Compliance (+5 more)

### Community 26 - "Coins Spine: Ledger, Dollar Removal, Shop Conversion"
Cohesion: 0.15
Nodes (12): 1. Ledger data model, 2. Where the ledger lives (the always-loaded problem), 3. Removing dollars, 4. Pricing the existing catalog, 5. UI: coin glyph, balance, cart subtotal, 6. Checkout becomes a real debit, 7. Open questions, Coins Spine: Ledger, Dollar Removal, Shop Conversion (+4 more)

### Community 27 - "Workshops: Propose, Apply-to-Run, Schedule, Track"
Cohesion: 0.15
Nodes (12): 1. Data model, 2. Storage registration (the five-place pattern, plus the two `PAGE_SECTIONS` mirrors), 3. Endpoints, 4. Notifications, 5. UI, 6. Home page stat tile, 7. i18n, Context (+4 more)

### Community 28 - "Global Constraints"
Cohesion: 0.17
Nodes (11): Chat Sprint 1 Implementation Plan, Global Constraints, Task 1: Feature flag helper, Task 2: Storage — Metadata JSON field, attachment loading, Airtable schema, Task 3: `AirtableStorage.upload_attachment`, Task 4: Link preview fetcher with SSRF guards, Task 5: Wire link previews into message posting, Task 6: Multipart file uploads on the message endpoint (+3 more)

### Community 29 - "Hyperframes Composition Brief: Hack Club Leaders"
Cohesion: 0.18
Nodes (10): Audio, Creative Direction, Hyperframes Composition Brief: Hack Club Leaders, Hyperframes Instructions, Known blocker (for delivery), Objective, Output, Source Material (+2 more)

### Community 30 - "Chat Sprint 1: Uploads, Link Previews, Markdown + Feature Flags"
Cohesion: 0.18
Nodes (10): 1. Feature flags, 2. Data model, 3. File uploads, 4. Link previews, 5. Markdown rendering (client-side), 6. UI, 7. Testing, Chat Sprint 1: Uploads, Link Previews, Markdown + Feature Flags (+2 more)

### Community 31 - "Global Constraints"
Cohesion: 0.20
Nodes (9): Coins Spine Implementation Plan, Global Constraints, Task 1: Ledger data model and pure functions, Task 2: Register `ledger` across all three storage backends, Task 3: Convert the shop from dollars to coins — types, parser, and catalog, Task 4: Cart snapshot and checkout debit, Task 5: Coin glyph, balance chip, and shop pricing UI, Task 6: i18n keys for the coin UI (+1 more)

### Community 32 - "Global Constraints"
Cohesion: 0.20
Nodes (9): Global Constraints, Task 1: Workshop data model and payload validator, Task 2: Register `workshops` across all three storage backends, Task 3: Propose and apply/withdraw endpoints, Task 4: Schedule, mark run, delete, and the scheduling notification, Task 5: UI — nav, page, modals, and the home stat tile, Task 6: i18n keys for the workshops UI, Task 7: Final verification gate (+1 more)

### Community 33 - "ideas.md"
Cohesion: 0.20
Nodes (9): Idea	Why	How, Idea	Why	How, Idea	Why	How, Idea	Why	How, Idea	Why	How, Idea	Why	How, Idea	Why	How, Idea	Why	How (+1 more)

### Community 34 - "scripts"
Cohesion: 0.22
Nodes (8): name, private, scripts, check, dev, publish, render, type

### Community 35 - "Global Constraints"
Cohesion: 0.25
Nodes (7): Global Constraints, Sidebar Hover-Expand + Notifications-into-Newsletters Implementation Plan, Task 1: Sidebar hover-expand — panel wrapper + page labels, Task 2: Sidebar profile card (coin balance + sign-out) + remove header coin chip, Task 3: Rename Newsletters page to Notification (route, template, i18n key), Task 4: Merge notifications into the Notification page feed + unread nav badge, Task 5: Remove the header notification bell and popover

### Community 36 - "split_i18n_data.py"
Cohesion: 0.36
Nodes (7): language_blocks(), language_list(), main(), Split static/js/i18n-data.js into one file per language.  i18n-data.js ships all, The declared language codes, plus the verbatim `const LANGUAGES = [...]`     blo, {code: "<the object literal body, without the trailing comma>"}., read_source()

### Community 37 - "paths"
Cohesion: 0.29
Nodes (6): paths, assets, blocks, components, registry, $schema

### Community 38 - "Global Constraints"
Cohesion: 0.29
Nodes (6): Global Constraints, Ship Review Coin Award Implementation Plan, Task 1: `add_in_app_notification` accepts an explicit `state`, Task 2: Owner review notification + email templates, Task 3: Wire coin award + notification into the review endpoint, Task 4: Frontend — surface the coin award

### Community 39 - "Photo upload: preview + crop/zoom before upload"
Cohesion: 0.29
Nodes (6): Components touched, Current state (for reference), Design, Photo upload: preview + crop/zoom before upload, Summary, Testing

### Community 40 - "Global Constraints"
Cohesion: 0.33
Nodes (5): Global Constraints, Photo Upload Preview + Crop Modal Implementation Plan, Task 1: Shared crop/zoom modal (markup, CSS, core JS), Task 2: Wire project thumbnail upload through the crop modal, Task 3: Wire avatar uploads through the crop modal

### Community 41 - "Sidebar redesign + notifications-into-newsletters"
Cohesion: 0.33
Nodes (5): 1. Sidebar hover-expand, 2. Notifications fold into a renamed "Notification" page, Sidebar redesign + notifications-into-newsletters, Summary, Testing

## Knowledge Gaps
- **208 isolated node(s):** `$schema`, `registry`, `blocks`, `components`, `assets` (+203 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `StorageError` connect `test_coins.py` to `Community 0`, `Community 1`, `Community 3`, `Community 5`, `Community 8`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Why does `reset_rate_limits()` connect `Community 2` to `Community 3`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Why does `AirtableStorage` connect `Community 1` to `Community 0`, `Community 5`, `test_coins.py`, `test_workshops.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `StorageError` (e.g. with `Channel` and `ClubState`) actually correct?**
  _`StorageError` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `AirtableStorage` (e.g. with `MongoStorage` and `test_storage_error_on_dashboard_redirects_once_not_forever()`) actually correct?**
  _`AirtableStorage` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `SessionStorage` (e.g. with `Channel` and `ClubState`) actually correct?**
  _`SessionStorage` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `MongoStorage` (e.g. with `AirtableStorage` and `StorageError`) actually correct?**
  _`MongoStorage` has 3 INFERRED edges - model-reasoned connections that need verification._