# Photo upload: preview + crop/zoom before upload

Date: 2026-08-10

## Summary

Every photo upload point in the dashboard (project thumbnail, and every `input[name="avatar"]` field: profile, team member, club settings, admin club) currently uploads the raw file to the server the instant it's picked — no local preview, no resize, just client-side type/size validation. This adds a shared crop/zoom modal between "file picked" and "upload": the user sees the image immediately, drags to reposition and a slider to scale, confirms, and *that* cropped result is what gets uploaded.

## Current state (for reference)

Two call sites share one pattern and one backend code path:

- `handleThumbFileChange` (`static/js/dashboard.js:667-696`) — project thumbnail, wired to `#projectThumbFile`.
- The per-field handler built by `initAvatarUploads()` (`static/js/dashboard.js:698-765`) — dynamically attaches an "Upload photo" button + hidden file input next to every `input[name="avatar"]`.

Both: validate `ALLOWED_IMAGE_TYPES` (png/jpeg/webp/gif) and a 4MB size cap, `POST` a `FormData` to `/api/dashboard/projects/upload-image` or `/api/dashboard/upload-image`, both routed through `_handle_image_upload()` (`src/routes_api.py:673-708`) which re-validates server-side, sniffs the real content type, and stores to Vercel Blob. No Pillow/image-processing dependency exists server-side.

## Design

**One shared modal, parameterized.** A single `<div class="modal-backdrop" id="imageCropModal">` added once to `dashboard_layout.html` (available on every dashboard page, like the existing event/project/dispatch modals). It's opened by a new `openCropModal({ file, aspect, onCropped })` JS function instead of each call site uploading directly.

**Flow.**
1. File picked → same type/size validation as today (unchanged, runs first so a bad file never even opens the modal).
2. `URL.createObjectURL(file)` — no network request yet — sets the modal's working `<img>` source.
3. Modal shows the image inside a fixed-size frame: 1:1 (square) for avatar fields, 16:9 for the project thumbnail (`aspect` param). A range-input slider controls `scale` (1×–3×); dragging the image pans it within the frame. Both just update a CSS `transform: translate() scale()` on the image — no canvas work until confirm.
4. "Save" draws the current transform to an offscreen `<canvas>` sized to the frame's output resolution (e.g. 512×512 for avatars, 800×450 for thumbnails), reads it back via `canvas.toBlob(..., 'image/jpeg', 0.9)`, and calls `onCropped(blob)`. "Cancel" closes the modal and resets the file input — nothing is uploaded.
5. `onCropped(blob)` is exactly today's upload step, unchanged: build a `FormData`, `POST` to the same endpoint the call site already used, then set the hidden field + preview from the returned URL. The only change at each call site is *what* triggers this (the crop confirm instead of the raw `change` event) and *what* file is sent (the cropped blob instead of the original file).

**Why client-side canvas, not server-side Pillow.** No image-processing dependency exists in this codebase today (`_handle_image_upload` just sniffs bytes), and the crop/zoom interaction is inherently a client-side UX concern (the user needs to see and drag it live). Cropping in canvas before upload also means the uploaded file is already the target size — smaller than the original, so it helps the existing 4MB cap rather than fighting it. No backend changes needed at all beyond receiving a differently-shaped (but still valid PNG/JPEG) file, which `_handle_image_upload` already handles.

**Object URL cleanup.** `URL.revokeObjectURL()` is called when the modal closes (either Save or Cancel) to avoid leaking blob URLs across repeated opens.

## Components touched

- `templates/dashboard_layout.html` — one new modal markup block.
- `static/css/dashboard.css` — modal-specific styles: crop frame, drag cursor states, zoom slider row. Reuses existing `.modal-backdrop`/`.dashboard-modal` chrome.
- `static/js/dashboard.js` — new `openCropModal()` + drag/zoom/canvas-export logic; `handleThumbFileChange` and the `initAvatarUploads()` handler both call it instead of uploading directly.
- `templates/partials/icons.html` — none needed (slider/drag use native `<input type="range">`, no new icons).

## Testing

Client-only change; no backend logic changes (same endpoints, same validation, just different bytes in the request). No pytest coverage needed. Verified in-browser: pick an oversized image on the project thumbnail field, confirm the modal opens with a live preview, drag/zoom works, Save uploads and the resulting thumbnail shows correctly; repeat on one avatar field (profile) to confirm the shared modal works with the 1:1 frame; confirm Cancel leaves the original value untouched and doesn't upload anything; dark mode.
