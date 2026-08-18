# Explore page design

## Goal

A signed-in-only gallery of shipped projects from every Hack Club on the
portal: `/dashboard/explore` (browse, search, filter, paginate) and
`/dashboard/explore/projects/<publicId>` (detail). Any Hack Clubber with a
session can browse; the general public cannot. Members opt a shipped project
in from the dashboard project form.

## Unchanged

- Dashboard routes, project form flow, admin review queue.
- Landing page showcase carousel (static, separate).
- Session/cookie backend stays a single-club demo with **no** cross-club
  data: Explore returns 503 with an unavailable state.
- Project draft/submit status machine (`Draft → Submitted → Shipped`).

## Changes

### 1. Project publication fields

Every project gains three fields (defaults for pre-existing rows):

| Key | Type | Default | Meaning |
|---|---|---|---|
| `publicId` | string | `showcase-<hex8>` | Stable public slug, generated at project creation |
| `isPublic` | bool | `false` | Owner opted the project into Explore |
| `category` | string | `''` | One of `Web`, `Game`, `Hardware`, `Mobile`, `Art & Design`, `Music`, `Other` |

Storage:
- Airtable: `Public ID` (single-line text), `Public` (checkbox), `Category`
  (single-select) via `PROJECT_FIELDS`; `isPublic` coerced like `rsvp`/`read`.
- Mongo: same keys on the `projects` collection; sparse unique index on
  `publicId` (documents without the field are skipped, so pre-existing
  projects keep saving), plus a read index on
  `(isPublic, status, category, date desc)`.
- Session: fields exist in demo state so dashboard JS renders them, but no
  public read path.

### 2. Publication rules (API)

On project update:
- `category` must be empty or one of the seven categories.
- Setting `isPublic: true` requires `status == 'Shipped'` and a non-empty
  valid `category`; otherwise 400 with a plain-language reason.
- Setting `isPublic: false` is always allowed.
- `publicId` is generated at creation (`_item_id('showcase')`) and never
  client-editable.

### 3. Storage contract: `list_public_projects()`

Both shared backends return a deliberately narrow, anonymous-safe projection:

```python
{
    'publicId', 'name', 'description', 'thumbnail',
    'demoUrl', 'repoUrl', 'ownerName', 'clubName', 'category', 'date',
}
```

Inclusion rules: project `Shipped`, `isPublic` true, `publicId` non-empty,
and owner club's `publicDirectory` true (Airtable) / `publicDirectory: true`
(Mongo). Sorted by `date` descending. **Never** include emails, addresses,
member data, or club-internal ids.

### 4. `/dashboard/explore`

Server-rendered (Flask), `@login_required`, inside the dashboard chrome
(sidebar, dashboard layout). Users without a club hit the normal membership
gate redirect:

- Filters: `q` (search across name, description, owner, club — casefold
  substring), `category` (exact match, validated against the seven
  categories), `page` (1-based, 12 per page, clamped).
- Template context: `projects`, `categories`, `query`, `selected_category`,
  `page`, `total_pages`, `total`, `unavailable`.
- Session backend: `unavailable=True`, HTTP 503, friendly state.
- Extends `dashboard_layout.html`; sidebar gains an Explore entry with a
  compass icon.

### 5. `/dashboard/explore/projects/<publicId>`

- `@login_required`, 404 via `flask.abort` when the id isn't in the shared
  list.
- Detail: thumbnail, name, category badge, club name, maker name, description,
  demo + repo buttons (omitted when absent), back-to-Explore link.
- Session backend: 503 unavailable, same as the grid.

### 6. Dashboard project form

- New `#projectPublication` fieldset (already in markup): category select +
  "Show this project publicly" toggle.
- Fieldset `disabled` unless the project's status is `Shipped`; the hint text
  explains why.
- `saveProjectFields` includes `category` and `isPublic` in POST/PATCH bodies.
- Edit flow pre-fills both; new-project flow resets them.

### 7. Navigation + sitemap

- "Explore" entry in the dashboard sidebar (between Projects and Levels),
  `side.explore` i18n key, compass icon added to `partials/icons.html`.
- `/dashboard/*` is already excluded from `sitemap.xml`/`robots.txt`, so the
  private Explore pages stay out of both.

### 8. i18n

New keys in `static/js/i18n-data.js` `en` block only; template English text is
the built-in fallback for other languages (existing i18n.js behaviour).
`side.explore` is translated in all 12 languages like every other sidebar key.

## Out of scope

- Explore search-as-you-type (client-side filter) — server round-trip is fine
  at this scale.
- Voting, comments, per-project analytics.
- Public (unauthenticated) access — the gallery is Hack Clubbers only.
- Session-mode cross-club data (impossible by design: no shared store).
