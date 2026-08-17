# Graph Report - Hackclub Leaders  (2026-08-17)

## Corpus Check
- 81 files · ~123,756 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1086 nodes · 1992 edges · 73 communities (66 shown, 7 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 53 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a3fa1896`
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
- Chat typing indicators + presence
- Chat Visual Redesign — Design Spec
- _add_member
- Global Constraints
- Global Constraints
- Global Constraints
- Server-synced chat read receipts
- Chat threads / replies
- Dashboard home page redesign
- Global Constraints
- Global Constraints
- Global Constraints
- _airtable
- _FakePreviewResponse
- feature_enabled
- reset_rate_limits
- reset_typing_presence
- _i18n_translations
- app.py
- Changes
- Motion polish implementation plan
- Design Context

## God Nodes (most connected - your core abstractions)
1. `_seed()` - 84 edges
2. `_make_channel()` - 35 edges
3. `MongoStorage` - 33 edges
4. `get_dashboard_state()` - 30 edges
5. `AirtableStorage` - 30 edges
6. `SessionStorage` - 25 edges
7. `StateTooLarge` - 24 edges
8. `_seed_message()` - 24 edges
9. `_msg()` - 24 edges
10. `save_dashboard_state()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `test_save_user_record_raises_when_table_missing()` --indirect_call--> `StorageError`  [INFERRED]
  tests/test_storage_airtable.py → src/storage_airtable.py
- `test_storage_error_on_dashboard_redirects_once_not_forever()` --indirect_call--> `AirtableStorage`  [INFERRED]
  tests/test_public.py → src/storage_airtable.py
- `test_storage_error_on_index_degrades_instead_of_looping()` --indirect_call--> `AirtableStorage`  [INFERRED]
  tests/test_public.py → src/storage_airtable.py
- `_payload_too_large()` --calls--> `json_error()`  [INFERRED]
  app.py → src/helpers_validation.py
- `inject_user()` --calls--> `get_sticker_files()`  [INFERRED]
  app.py → src/helpers_shop.py

## Import Cycles
- None detected.

## Communities (73 total, 7 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (39): Exception, MongoClient, _as_bool(), _as_int(), _item_from_row(), load_states(), main(), Import club data from Airtable CSV exports into MongoDB.  Fallback for scripts/s (+31 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (18): main(), Delete test records from the live Airtable base.  During development, sign-in, register(), AirtableStorage, Airtable column mappings for the Hack Club Leaders Portal storage layer., Any, Airtable storage backend for Hack Club Leaders Portal., Cross-club session-invalidation counter for `email`.          Degrades to `{'s (+10 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (57): _make_channel(), Chat (channels + messages) API coverage.  These exercise *successful* authenti, _seed(), test_blank_channel_name_rejected(), test_channel_list_unread_flag(), test_channel_patch_sets_topic(), test_channel_requires_csrf(), test_channel_topic_cleared_by_empty_string() (+49 more)

### Community 3 - "Community 3"
Cohesion: 0.10
Nodes (35): _html_to_text(), Email notification system for the Hack Club Leaders Portal., Render the email sent to a member once a leader schedules them to run a workshop, Send email in background thread., Render project submission notification email., Render the email sent to a member when their shipped project is approved., Send email using a template. Runs in background thread., Render the email sent to a member when their submitted project is sent back to D (+27 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (10): _save_settings(), _save_settings_v2(), test_default_state_has_language(), test_error_handlers(), test_settings_derives_empty_location_when_no_address(), test_settings_derives_location_from_city_state(), test_settings_derives_location_with_only_city(), test_settings_persists_supported_language() (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.50
Nodes (4): convert_to_webp(), main(), Convert heavyweight raster images to WebP and rewrite local references.  Targets, Convert source_path to a sibling .webp. Returns the .webp path if     converted,

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (29): _embedded_state(), _messages(), mongo_client(), MongoStorage backend coverage, against an in-memory Mongo (mongomock).  These, A signed-in test client served by the Mongo backend., _state(), storage(), test_chat_page_embeds_chat_sections() (+21 more)

### Community 9 - "Community 9"
Cohesion: 0.67
Nodes (3): fail(), main(), Airtable readiness check.  Run this after creating your base and setting AIRTA

### Community 13 - "test_coins.py"
Cohesion: 0.13
Nodes (17): coins_spent(), _seed_cart_club(), test_award_coins_appends_transaction_and_reconciles(), test_award_coins_creates_ledger_key_if_absent(), test_award_coins_negative_delta_updates_spent_cache(), test_cart_add_rejects_unpriced_item(), test_cart_add_snapshots_coin_cost(), test_checkout_debits_ledger_on_success() (+9 more)

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
Cohesion: 0.08
Nodes (65): default_dashboard_state(), default_dashboard_state(), generate_join_code(), playtest_state(), Demo and default initial state builders for Hack Club Leaders Portal., generate_join_code(), playtest_state(), The sections the given endpoint needs, or None for "everything". (+57 more)

### Community 20 - "Task 1: Feature Flag Helper — Implementation Report"
Cohesion: 0.25
Nodes (4): HTMLParser, fetch_link_preview(), _host_is_public(), _OgParser

### Community 21 - "Task 2: Storage — Metadata JSON field, attachment loading, Airtable schema — Report"
Cohesion: 0.25
Nodes (16): F, admin_required(), _club_key(), get_dashboard_state(), leader_required(), login_required(), parse_language(), Return a supported language code, defaulting to English for anything else. (+8 more)

### Community 22 - "File Structure"
Cohesion: 0.13
Nodes (14): File Structure, Global Constraints, Post-plan cleanup (housekeeping, not a task), Self-Review Notes, Settings Page Redesign (Round 1) Implementation Plan, Task 1: Club profile data model — structured address + derived `location`, Task 2: Settings shell — scrollspy layout + sidebar nav, Task 3: Club profile section (fully built) (+6 more)

### Community 23 - "Task 3 Report: `AirtableStorage.upload_attachment`"
Cohesion: 0.29
Nodes (11): _join_missing(), _owned_project_or_error(), Any, require_admin_api(), require_dashboard_csrf(), _slugify(), _viewer_email(), register() (+3 more)

### Community 24 - "Sections"
Cohesion: 0.14
Nodes (13): 1. Club profile (fully built), 2. Members (real content, partial), 3. Your account (new section, stubbed data), 4. Appearance (real content), 5. Explore & privacy (real content), 6. Notifications (real content), 7. Danger zone (real content, gated by backend), Context (+5 more)

### Community 25 - "Task 5 Report: Wire link previews into message posting"
Cohesion: 0.15
Nodes (26): _iso(), _msg(), Append a pre-built message onto the seeded dashboard state., _seed_message(), test_add_reaction(), test_author_deletes_own_recent_message(), test_author_edits_own_recent_message(), test_cannot_edit_deleted_message() (+18 more)

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

### Community 44 - "progress.md"
Cohesion: 0.14
Nodes (13): _chat_reads(), _find_chat_read(), _find_message(), _messages(), _page_limit(), _rate_limit_retry_after(), Club chat: channels + messages.  All members can read and post; only leaders/m, A sane page size from an untrusted ?limit= value. (+5 more)

### Community 45 - "task-1-brief.md"
Cohesion: 0.23
Nodes (15): award_coins(), coin_balance(), _item_id(), UTC timestamp, ISO-8601 with a 'Z' suffix (e.g. 2026-07-10T22:59:00.123456Z)., Recompute the cached balance/spent totals in `settings` from the     ledger. Ca, Append a ledger transaction and refresh the balance/spent cache.      The only, reconcile_coins(), require_leader_api() (+7 more)

### Community 46 - "task-2-brief.md"
Cohesion: 0.18
Nodes (10): Architecture, Data flow, Error handling, Goal, New `data-tour` markup needed, Out of scope, Per-page step content, Scope: pages (+2 more)

### Community 47 - "task-3-brief.md"
Cohesion: 0.18
Nodes (11): Resolve @-mentions in `body` against the club's member list.      Returns (sor, resolve_mentions(), test_resolve_mentions_duplicate_names_both_notified(), test_resolve_mentions_everyone_by_leader(), test_resolve_mentions_everyone_by_non_leader_ignored(), test_resolve_mentions_excludes_self(), test_resolve_mentions_false_positive_inside_email_avoided(), test_resolve_mentions_longest_name_wins() (+3 more)

### Community 48 - "task-4-brief.md"
Cohesion: 0.20
Nodes (9): Chat Visual Redesign Implementation Plan, Global Constraints, Task 1: Channel rail restyle, Task 2: Grouped message spacing + hover timestamp, Task 3: Mention pills + own-mention row highlight, Task 4: Seen-by overflow cap + animated typing dots, Task 5: Thread panel slide-in + nested styling, Task 6: Composer redesign — icon send button + mention menu polish (+1 more)

### Community 49 - "task-5-brief.md"
Cohesion: 0.20
Nodes (9): Chat @mentions + notification, Data model, Detection algorithm, Error handling / edge cases, Frontend (`static/js/dashboard-chat.js`, `templates/dashboard/chat.html`), Notification delivery, Scope, Summary (+1 more)

### Community 51 - "Chat typing indicators + presence"
Cohesion: 0.20
Nodes (9): Chat typing indicators + presence, Data model, Endpoints (`src/routes_chat.py`), Error handling / edge cases, Frontend (`static/js/dashboard-chat.js`), Scope, Summary, Testing (+1 more)

### Community 52 - "Chat Visual Redesign — Design Spec"
Cohesion: 0.20
Nodes (9): Chat Visual Redesign — Design Spec, Composer, Empty / loading states, Feature-specific treatment, Goal, Layout, Motion, Out of scope (+1 more)

### Community 53 - "_add_member"
Cohesion: 0.24
Nodes (10): _add_member(), _notifications(), _switch_user(), test_everyone_mention_by_leader_notifies_all_other_members(), test_everyone_mention_by_member_not_honored(), test_mentions_persist_on_message_listing(), test_message_self_mention_not_notified(), test_message_with_mention_notifies_recipient() (+2 more)

### Community 54 - "Global Constraints"
Cohesion: 0.22
Nodes (8): Chat Read Receipts Implementation Plan, Global Constraints, Self-Review Notes, Task 1: `chatReads` upsert endpoint, Task 2: `GET .../reads` + `unread` on channel list, Task 3: Drop `chatReads` rows on channel delete, Task 4: Mongo collection + index, Task 5: Client — server-synced unread dot + "seen by" row

### Community 55 - "Global Constraints"
Cohesion: 0.22
Nodes (8): Chat Threads / Replies Implementation Plan, Global Constraints, Self-Review Notes, Task 1: Reply validation + parent bookkeeping on message send, Task 2: Filter replies out of the top-level channel view; `?parentId=` scopes to a thread, Task 3: `page_messages()` gains a `parent_id` parameter; new Mongo index, Task 4: Frontend — reply affordance, thread panel, scoped polling, reply composer, Task 5: Extend channel-delete test coverage to replies

### Community 56 - "Global Constraints"
Cohesion: 0.22
Nodes (8): Chat Typing Indicators + Presence Implementation Plan, Global Constraints, Self-Review Notes, Task 1: Module-level state + `POST .../typing` endpoint, Task 2: `typing` array on `GET .../messages`, Task 3: `onlineMembers` array + presence heartbeat on `GET .../channels`, Task 4: Client — typing indicator under the compose box, Task 5: Client — presence dot on message-author avatars

### Community 57 - "Server-synced chat read receipts"
Cohesion: 0.22
Nodes (8): Data model, Endpoints (`src/routes_chat.py`), Error handling / edge cases, Frontend (`static/js/dashboard-chat.js`), Scope, Server-synced chat read receipts, Summary, Testing

### Community 58 - "Chat threads / replies"
Cohesion: 0.22
Nodes (8): Backend changes (`src/routes_chat.py`), Chat threads / replies, Data model, Error handling / edge cases, Frontend (`static/js/dashboard-chat.js`), Scope, Summary, Testing

### Community 59 - "Dashboard home page redesign"
Cohesion: 0.22
Nodes (8): Dashboard home page redesign, Data plumbing, Goal, Layout order (top → bottom), New: coins widget, Out of scope, Shrink existing widgets, Unchanged

### Community 60 - "Global Constraints"
Cohesion: 0.29
Nodes (6): Chat @mentions Implementation Plan, Global Constraints, Self-Review Notes, Task 1: Mention-resolution helper (pure function), Task 2: Persist mentions on message send + notify, Task 3: Client `@` autocomplete + mention highlighting

### Community 61 - "Global Constraints"
Cohesion: 0.29
Nodes (6): Global Constraints, Site-Wide Guided Tour Implementation Plan, Task 1: Shared tour engine, CSS, layout wiring, and Tools page migration, Task 2: Tour steps for Home, Team, Workshops, Events, Shop, Task 3: Tour steps for Levels, Map, Projects, Ships, Chat, Task 4: Tour steps for Notifications, Settings, Profile, Admin, Admin Club

### Community 62 - "Global Constraints"
Cohesion: 0.33
Nodes (5): Dashboard Home Redesign Implementation Plan, Global Constraints, Task 1: Load the coin ledger on the home page, Task 2: Shrink the team, checklist, and events widgets, Task 3: Add the coins-earned widget

### Community 63 - "_airtable"
Cohesion: 0.40
Nodes (6): _airtable(), _save_messages_and_capture(), test_item_fields_no_preview_writes_blank(), test_item_fields_serializes_link_preview(), test_load_message_without_extras(), test_load_parses_message_metadata_and_attachments()

### Community 64 - "_FakePreviewResponse"
Cohesion: 0.33
Nodes (4): _FakePreviewResponse, test_preview_happy_path(), test_preview_non_html_skipped(), test_preview_title_fallback()

### Community 65 - "feature_enabled"
Cohesion: 0.40
Nodes (5): feature_enabled(), Env-driven feature flag: on unless the env var is set to false/0/off/no., test_feature_flags_default_on(), test_feature_flags_disabled_values(), test_feature_flags_true_value()

### Community 69 - "app.py"
Cohesion: 0.25
Nodes (13): handle_state_too_large(), handle_storage_error(), inject_user(), _payload_too_large(), Any, Exception, Response, get_csrf_token() (+5 more)

### Community 70 - "Changes"
Cohesion: 0.17
Nodes (11): 1. Press feedback, 2. Modal exit, 3. Nav dropdown, 4. Toast enter, 5. Touch gating, 6. Notification badge pop, Changes, Goal (+3 more)

### Community 71 - "Motion polish implementation plan"
Cohesion: 0.20
Nodes (9): Motion polish implementation plan, Step 1 — dashboard.css: press feedback, Step 2 — dashboard.js: modal exit sequence, Step 3 — dashboard.css: modal exit styles, Step 4 — navigation.css: dropdown transition, Step 5 — dashboard.js + dashboard.css: toast enter, Step 6 — dashboard.css: hover gating, Step 7 — dashboard.css: badge pop (+1 more)

### Community 72 - "Design Context"
Cohesion: 0.33
Nodes (5): Aesthetic Direction, Brand Personality, Design Context, Design Principles, Users

## Knowledge Gaps
- **255 isolated node(s):** `$schema`, `registry`, `blocks`, `components`, `assets` (+250 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AirtableStorage` connect `Community 1` to `Community 0`, `Community 5`, `_airtable`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Why does `SessionStorage` connect `Community 1` to `Community 0`, `Task 4 Implementation Report: Link preview fetcher with SSRF guards`, `Task 2: Storage — Metadata JSON field, attachment loading, Airtable schema — Report`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `MongoStorage` connect `Community 0` to `Community 8`, `Community 1`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `get_dashboard_state()` (e.g. with `ShopItem` and `SessionStorage`) actually correct?**
  _`get_dashboard_state()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `AirtableStorage` (e.g. with `main()` and `SessionStorage`) actually correct?**
  _`AirtableStorage` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `registry`, `blocks` to the rest of the system?**
  _341 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06912442396313365 - nodes in this community are weakly interconnected._