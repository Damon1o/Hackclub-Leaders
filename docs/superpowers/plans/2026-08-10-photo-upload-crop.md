# Photo Upload Preview + Crop Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every photo upload point (project thumbnail, every avatar field) opens a shared crop/zoom modal showing a live local preview before uploading, instead of uploading the raw file immediately on pick.

**Architecture:** One shared modal (markup added once to `dashboard_layout.html`), driven by a single `openCropModal({file, aspect, onCropped})` JS entry point built on `<canvas>` for the crop/scale math and the existing `openModal`/`closeModal` helpers for show/hide. Both existing upload call sites are changed to call it instead of uploading directly; the actual upload (`FormData` → existing endpoints) is unchanged.

**Tech Stack:** Vanilla JS, `<canvas>` 2D context, native `<input type="range">`. No new dependencies, no backend changes.

## Global Constraints

- No backend/route changes — `/api/dashboard/projects/upload-image` and `/api/dashboard/upload-image` keep their exact contract (`multipart/form-data`, field name `image`, JSON `{url}` response) per `src/routes_api.py:673-708`.
- Existing client-side type/size validation (`ALLOWED_IMAGE_TYPES`, 4MB cap) runs before the modal opens, unchanged.
- `URL.revokeObjectURL()` must be called on every modal close (Save or Cancel) — no leaked blob URLs.

---

### Task 1: Shared crop/zoom modal (markup, CSS, core JS)

**Files:**
- Modify: `templates/dashboard_layout.html` (add modal markup once, near the other modals — after the `toast-region` div, before the closing `</body>` scripts, `~260`)
- Modify: `static/css/dashboard.css` (new rules, append near `.thumb-preview` at `~2628-2641`)
- Modify: `static/js/dashboard.js` (new `openCropModal` + supporting functions)

**Interfaces:**
- Produces: `openCropModal({file: File, aspect: number, onCropped: (blob: Blob) => void})` — called by Task 2 and Task 3. `aspect` is width/height (e.g. `1` for square, `16/9` for project thumbnails).

- [ ] **Step 1: Add the modal markup**

In `templates/dashboard_layout.html`, add after the `toast-region` div (currently line 260, right before the `<script id="dashboard-state">` line):

```html
    <div class="modal-backdrop" id="imageCropModal" aria-hidden="true">
        <section class="dashboard-modal" role="dialog" aria-modal="true" aria-labelledby="imageCropModalTitle">
            <header class="modal-header">
                <h2 id="imageCropModalTitle" data-i18n="upload.cropTitle">Adjust image</h2>
                <button class="icon-button" type="button" data-modal-close aria-label="Close" data-i18n-attr="aria-label:common.close"><span aria-hidden="true" data-i18n="common.closeX">×</span></button>
            </header>
            <div class="crop-frame-wrap">
                <div class="crop-frame" id="cropFrame">
                    <img id="cropImage" alt="" draggable="false">
                </div>
            </div>
            <label class="form-group crop-zoom-row">
                <span class="form-label" data-i18n="upload.zoom">Zoom</span>
                <input type="range" id="cropZoomSlider" min="1" max="3" step="0.01" value="1">
            </label>
            <p class="form-error" id="cropModalError" hidden></p>
            <div class="modal-actions">
                <button class="btn-secondary" type="button" data-modal-close data-i18n="upload.cancel">Cancel</button>
                <button class="btn-primary" type="button" id="cropSaveButton" data-i18n="upload.save">Save</button>
            </div>
        </section>
    </div>
```

- [ ] **Step 2: CSS for the crop frame**

In `static/css/dashboard.css`, append after the `.thumb-preview` rules (ends line 2641):

```css
.crop-frame-wrap {
    display: flex;
    justify-content: center;
    padding: 12px 0;
}

.crop-frame {
    position: relative;
    width: 280px;
    overflow: hidden;
    border-radius: 12px;
    border: 1px solid var(--dash-border);
    background: var(--dash-fill);
    cursor: grab;
    touch-action: none;
}

.crop-frame.is-dragging {
    cursor: grabbing;
}

.crop-frame img {
    position: absolute;
    top: 50%;
    left: 50%;
    max-width: none;
    max-height: none;
    transform-origin: center;
    user-select: none;
    pointer-events: none;
}

.crop-zoom-row {
    display: flex;
    align-items: center;
    gap: 12px;
}

.crop-zoom-row input[type="range"] {
    flex: 1;
}
```

- [ ] **Step 3: Implement `openCropModal` and its drag/zoom/export logic**

In `static/js/dashboard.js`, add near `updateThumbPreview`/`ALLOWED_IMAGE_TYPES` (before `uploadProjectImage`, `~line 648`):

```javascript
    // Shared crop/zoom step between "file picked" and "upload". `aspect` is
    // width/height for the crop frame (1 = square, 16/9 = project thumbnail).
    // `onCropped` receives the exported Blob; nothing is uploaded here.
    let cropState = null;

    function openCropModal({ file, aspect, onCropped }) {
        const frame = $('#cropFrame');
        const img = $('#cropImage');
        const slider = $('#cropZoomSlider');
        if (!frame || !img || !slider) return;

        const frameWidth = 280;
        const frameHeight = Math.round(frameWidth / aspect);
        frame.style.height = `${frameHeight}px`;

        const objectUrl = URL.createObjectURL(file);
        cropState = {
            objectUrl, aspect, onCropped,
            naturalWidth: 0, naturalHeight: 0,
            scale: 1, minScale: 1,
            offsetX: 0, offsetY: 0,
            dragging: false, dragStartX: 0, dragStartY: 0, dragOffsetX: 0, dragOffsetY: 0,
        };

        img.onload = function () {
            cropState.naturalWidth = img.naturalWidth;
            cropState.naturalHeight = img.naturalHeight;
            // The smallest scale that still fully covers the frame in both dimensions.
            cropState.minScale = Math.max(frameWidth / img.naturalWidth, frameHeight / img.naturalHeight);
            cropState.scale = cropState.minScale;
            cropState.offsetX = 0;
            cropState.offsetY = 0;
            slider.min = String(cropState.minScale);
            slider.max = String(cropState.minScale * 3);
            slider.step = String(cropState.minScale / 100);
            slider.value = String(cropState.minScale);
            applyCropTransform();
        };
        img.src = objectUrl;

        setFormError('cropModalError', '');
        openModal('imageCropModal');
    }

    function applyCropTransform() {
        const img = $('#cropImage');
        if (!img || !cropState) return;
        const w = cropState.naturalWidth * cropState.scale;
        const h = cropState.naturalHeight * cropState.scale;
        img.style.width = `${w}px`;
        img.style.height = `${h}px`;
        img.style.transform =
            `translate(-50%, -50%) translate(${cropState.offsetX}px, ${cropState.offsetY}px)`;
    }

    function clampCropOffsets() {
        if (!cropState) return;
        const frame = $('#cropFrame');
        if (!frame) return;
        const frameWidth = frame.clientWidth;
        const frameHeight = frame.clientHeight;
        const w = cropState.naturalWidth * cropState.scale;
        const h = cropState.naturalHeight * cropState.scale;
        const maxX = Math.max(0, (w - frameWidth) / 2);
        const maxY = Math.max(0, (h - frameHeight) / 2);
        cropState.offsetX = Math.min(maxX, Math.max(-maxX, cropState.offsetX));
        cropState.offsetY = Math.min(maxY, Math.max(-maxY, cropState.offsetY));
    }

    function exportCroppedBlob() {
        return new Promise((resolve, reject) => {
            const frame = $('#cropFrame');
            if (!cropState || !frame) return reject(new Error('Nothing to crop.'));
            const frameWidth = frame.clientWidth;
            const frameHeight = frame.clientHeight;
            const outputWidth = cropState.aspect === 1 ? 512 : 800;
            const outputHeight = Math.round(outputWidth / cropState.aspect);

            const canvas = document.createElement('canvas');
            canvas.width = outputWidth;
            canvas.height = outputHeight;
            const ctx = canvas.getContext('2d');

            // Map frame-space (what's visible) to the source image's natural pixels.
            const visibleLeft = (cropState.naturalWidth * cropState.scale - frameWidth) / 2 - cropState.offsetX;
            const visibleTop = (cropState.naturalHeight * cropState.scale - frameHeight) / 2 - cropState.offsetY;
            const sx = visibleLeft / cropState.scale;
            const sy = visibleTop / cropState.scale;
            const sw = frameWidth / cropState.scale;
            const sh = frameHeight / cropState.scale;

            const img = $('#cropImage');
            ctx.drawImage(img, sx, sy, sw, sh, 0, 0, outputWidth, outputHeight);
            canvas.toBlob((blob) => {
                if (!blob) return reject(new Error('Could not export image.'));
                resolve(blob);
            }, 'image/jpeg', 0.9);
        });
    }

    function closeCropModal() {
        if (cropState) {
            URL.revokeObjectURL(cropState.objectUrl);
            cropState = null;
        }
        closeModal('imageCropModal');
    }

    function initCropModal() {
        const frame = $('#cropFrame');
        const slider = $('#cropZoomSlider');
        const saveButton = $('#cropSaveButton');
        const modal = $('#imageCropModal');
        if (!frame || !slider || !saveButton || !modal) return;

        frame.addEventListener('pointerdown', (event) => {
            if (!cropState) return;
            cropState.dragging = true;
            frame.classList.add('is-dragging');
            frame.setPointerCapture(event.pointerId);
            cropState.dragStartX = event.clientX;
            cropState.dragStartY = event.clientY;
            cropState.dragOffsetX = cropState.offsetX;
            cropState.dragOffsetY = cropState.offsetY;
        });
        frame.addEventListener('pointermove', (event) => {
            if (!cropState || !cropState.dragging) return;
            cropState.offsetX = cropState.dragOffsetX + (event.clientX - cropState.dragStartX);
            cropState.offsetY = cropState.dragOffsetY + (event.clientY - cropState.dragStartY);
            clampCropOffsets();
            applyCropTransform();
        });
        frame.addEventListener('pointerup', () => {
            if (!cropState) return;
            cropState.dragging = false;
            frame.classList.remove('is-dragging');
        });

        slider.addEventListener('input', () => {
            if (!cropState) return;
            cropState.scale = Number(slider.value);
            clampCropOffsets();
            applyCropTransform();
        });

        saveButton.addEventListener('click', async () => {
            if (!cropState) return;
            const onCropped = cropState.onCropped;
            try {
                const blob = await exportCroppedBlob();
                closeCropModal();
                onCropped(blob);
            } catch (error) {
                setFormError('cropModalError', error.message);
            }
        });

        // The modal's own [data-modal-close]/backdrop-click handlers are wired
        // generically in setupGlobalEvents() via [data-modal-close]; hook the
        // object-URL cleanup onto that same generic path.
        modal.addEventListener('click', (event) => {
            if (event.target === modal || event.target.closest('[data-modal-close]')) {
                closeCropModal();
            }
        });
    }
```

- [ ] **Step 4: Call `initCropModal()` on page init**

In `static/js/dashboard.js`, in `function init()` (starts `~3005`), add `initCropModal();` alongside the other `init*()` calls (e.g. right after `initBackground();`).

- [ ] **Step 5: Verify in browser**

Add a temporary call in the browser console on any dashboard page: pick a file via a throwaway `<input type=file>`, call `openCropModal({file: thatFile, aspect: 1, onCropped: (blob) => console.log('cropped', blob)})`. Confirm the modal opens with a live preview, dragging pans the image, the zoom slider scales it, Save logs a `Blob`, and Cancel closes without logging anything. Confirm no lingering blob URLs (`chrome://blob-internals` or just trust `revokeObjectURL` — no automated check needed).

- [ ] **Step 6: Commit**

```bash
git add templates/dashboard_layout.html static/css/dashboard.css static/js/dashboard.js
git commit -m "feat: add shared crop/zoom modal for photo uploads"
```

---

### Task 2: Wire project thumbnail upload through the crop modal

**Files:**
- Modify: `static/js/dashboard.js` (`handleThumbFileChange`, `~667-696`)

**Interfaces:**
- Consumes: `openCropModal` from Task 1, `uploadProjectImage(file)` (existing, `~652-665`, unchanged).

- [ ] **Step 1: Replace the direct-upload handler**

Replace `handleThumbFileChange` (lines 667-696) with:

```javascript
    async function handleThumbFileChange(event) {
        const input = event.target;
        const file = input.files && input.files[0];
        if (!file) return;
        setFormError('projectThumbError', '');
        if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
            setFormError('projectThumbError', 'Only PNG, JPEG, WebP, or GIF images are allowed.');
            input.value = '';
            return;
        }
        if (file.size > 4 * 1024 * 1024) {
            setFormError('projectThumbError', 'Image must be 4 MB or smaller.');
            input.value = '';
            return;
        }
        input.value = '';  // let the same file be re-picked later regardless of outcome

        openCropModal({
            file,
            aspect: 16 / 9,
            onCropped: async (blob) => {
                const cta = $('#projectThumbUpload .image-upload-cta');
                if (cta) cta.textContent = 'Uploading…';
                const form = $('#projectForm');
                try {
                    const url = await uploadProjectImage(blob);
                    if (form) form.elements.thumbnail.value = url;
                    updateThumbPreview(url);
                    refreshProjectRequirements();
                } catch (error) {
                    setFormError('projectThumbError', error.message);
                    updateThumbPreview(form ? form.elements.thumbnail.value : '');
                }
            },
        });
    }
```

`uploadProjectImage` already accepts any `Blob` via `body.append('image', file)` (a cropped `Blob` works identically to a `File` there — `FormData.append` doesn't require a `File`), so it needs no change.

- [ ] **Step 2: Verify in browser**

On `/dashboard/projects`, open "New project", choose an image for the thumbnail. Confirm the crop modal opens (16:9 frame) instead of an immediate upload, and Save uploads the cropped result — the thumbnail preview shows the cropped image, not the original.

- [ ] **Step 3: Commit**

```bash
git add static/js/dashboard.js
git commit -m "feat: project thumbnail upload goes through the crop modal"
```

---

### Task 3: Wire avatar uploads through the crop modal

**Files:**
- Modify: `static/js/dashboard.js` (`initAvatarUploads`, `~698-765`)

**Interfaces:**
- Consumes: `openCropModal` from Task 1.

- [ ] **Step 1: Replace the avatar file-input `change` handler**

Inside `initAvatarUploads()`, replace the `fileInput.addEventListener('change', async function () { ... });` block (lines 722-758) with:

```javascript
            fileInput.addEventListener('change', function () {
                const file = fileInput.files && fileInput.files[0];
                fileInput.value = '';
                if (!file) return;
                if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
                    statusText.textContent = 'Only PNG, JPEG, WebP, or GIF.';
                    return;
                }
                if (file.size > 4 * 1024 * 1024) {
                    statusText.textContent = 'Max 4 MB.';
                    return;
                }

                openCropModal({
                    file,
                    aspect: 1,
                    onCropped: async (blob) => {
                        uploadBtn.disabled = true;
                        statusText.textContent = 'Uploading...';
                        try {
                            const body = new FormData();
                            body.append('image', blob);
                            const response = await fetch('/api/dashboard/upload-image', {
                                method: 'POST',
                                headers: { Accept: 'application/json', 'X-CSRF-Token': csrfToken },
                                credentials: 'same-origin',
                                body,
                            });
                            const payload = await response.json().catch(() => ({}));
                            if (!response.ok) throw new Error(payload.error || 'Upload failed.');
                            input.value = payload.url;
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                            statusText.textContent = 'Uploaded.';
                            updateNearbyAvatarPreview(input);
                        } catch (error) {
                            statusText.textContent = error.message;
                        } finally {
                            uploadBtn.disabled = false;
                        }
                    },
                });
            });
```

- [ ] **Step 2: Verify in browser**

On `/dashboard/profile` (or `/dashboard/settings` for the club avatar), click "Upload photo", choose an image. Confirm the crop modal opens with a square (1:1) frame, and Save uploads the cropped square — the avatar preview (`#profilePreviewAvatar` / `.club-preview-avatar`) shows the cropped result.

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest -q`
Expected: no new failures (this task is client-only; unaffected backend tests keep whatever pass/fail state they had before this plan).

- [ ] **Step 4: Commit**

```bash
git add static/js/dashboard.js
git commit -m "feat: avatar photo uploads go through the crop modal"
```
