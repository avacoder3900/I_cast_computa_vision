# BIMS UI Integration — Computer Vision Pipeline

> **Audience:** AI agent building the SvelteKit frontend in `Bioscale_Operations_System_V2`.
> This document specifies every API endpoint, data model, page, component,
> and data-flow needed to integrate the ICast Computer Vision API into the
> BIMS UI.  Follow this PRD exactly — it contains everything required to
> build the full CV UI without asking questions.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    BIMS V2 (SvelteKit)                  │
│  Vercel / Node                                          │
│                                                         │
│  /cv/dashboard          CV Dashboard page               │
│  /cv/cartridge/[id]     Cartridge Inspection Gallery     │
│  /cv/capture            Live Capture + Inspect           │
│  /cv/training           Training Data Manager            │
│                                                         │
│  lib/api/cv.ts          Fetch wrapper for CV API         │
│  lib/stores/cv.ts       Svelte stores for CV state       │
└───────────┬─────────────────────────────────────────────┘
            │  REST / JSON (X-API-Key auth)
            ▼
┌─────────────────────────────────────────────────────────┐
│               ICast CV API (FastAPI)                     │
│  Deployed on Railway / Fly.io / Docker                  │
│                                                         │
│  /health                Public health check              │
│  /api/v1/samples        Sample CRUD                      │
│  /api/v1/images         Image query + cartridge tags     │
│  /api/v1/capture        Image capture                    │
│  /api/v1/cameras        Camera status                    │
│  /api/inspections       Inspection CRUD + results        │
│                                                         │
│  Worker (separate process) — polls pending inspections   │
│  and runs ONNX inference                                │
└───────────┬─────────────┬───────────────────────────────┘
            │             │
     MongoDB              Cloudflare R2
     (Motor)              (S3-compatible)
```

---

## 2. Connecting BIMS to the CV API

### 2.1 Environment Variables

In the BIMS V2 SvelteKit project:

```env
# .env or Vercel environment variables
NEXT_PUBLIC_CV_API_URL=https://icast-cv-api.your-domain.com
CV_API_KEY=your-secret-api-key
```

- `NEXT_PUBLIC_CV_API_URL` — **public** (used client-side for image URLs)
- `CV_API_KEY` — **private / server-side only** (never expose to browser)

### 2.2 Fetch Wrapper (`lib/api/cv.ts`)

All CV API calls go through a single typed wrapper.  Server-side calls
attach the API key; client-side calls for image/thumbnail URLs use the
public base URL directly (images are served without auth via R2 public
URLs or can be proxied).

```typescript
// lib/api/cv.ts

const CV_BASE = import.meta.env.NEXT_PUBLIC_CV_API_URL;
const CV_KEY  = import.meta.env.CV_API_KEY; // server-side only

interface FetchOptions {
  method?: string;
  body?: unknown;
  params?: Record<string, string>;
}

export async function cvFetch<T>(
  path: string,
  opts: FetchOptions = {},
): Promise<T> {
  const url = new URL(path, CV_BASE);
  if (opts.params) {
    for (const [k, v] of Object.entries(opts.params)) {
      url.searchParams.set(k, v);
    }
  }

  const res = await fetch(url.toString(), {
    method: opts.method ?? 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': CV_KEY,
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `CV API ${res.status}`);
  }

  return res.json() as Promise<T>;
}

/** Build a public image URL (for <img src=...>) */
export function cvImageUrl(imageId: string): string {
  return `${CV_BASE}/api/v1/images/${imageId}/file`;
}

/** Build a public thumbnail URL */
export function cvThumbUrl(imageId: string): string {
  return `${CV_BASE}/api/v1/images/${imageId}/thumbnail`;
}
```

---

## 3. Complete API Endpoint Reference

All endpoints require `X-API-Key` header unless noted.  Pagination uses
`skip` (default 0) and `limit` (default 50, max 200) query params.

### 3.1 Health (public — no auth)

| Method | Path      | Response |
|--------|-----------|----------|
| GET    | `/health` | `{ status, service, version, database }` |

---

### 3.2 Samples (`/api/v1/samples`)

| Method | Path                        | Body / Params | Response | Status |
|--------|-----------------------------|---------------|----------|--------|
| POST   | `/api/v1/samples`           | `SampleCreate` | `SampleResponse` | 201 |
| GET    | `/api/v1/samples`           | `?skip=&limit=` | `SampleResponse[]` | 200 |
| GET    | `/api/v1/samples/{id}`      | — | `SampleResponse` | 200 / 404 |
| PATCH  | `/api/v1/samples/{id}`      | `SampleUpdate` | `SampleResponse` | 200 / 404 |
| DELETE | `/api/v1/samples/{id}`      | — | — | 204 / 404 |

**SampleCreate:**
```json
{
  "name": "string (1-255 chars, required)",
  "description": "string (default '')",
  "project": "string (default '')",
  "tags": ["string"],
  "metadata": {}
}
```

**SampleResponse:**
```json
{
  "id": "string (MongoDB ObjectId as string)",
  "name": "string",
  "description": "string",
  "project": "string",
  "tags": ["string"],
  "metadata": {},
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

---

### 3.3 Images (`/api/v1/images`)

| Method | Path | Body / Params | Response | Status |
|--------|------|---------------|----------|--------|
| GET | `/api/v1/images` | `?sample_id=&cartridge_id=&skip=&limit=` | `ImageResponse[]` | 200 |
| GET | `/api/v1/samples/{sample_id}/images` | `?skip=&limit=` | `ImageResponse[]` | 200 |
| POST | `/api/v1/images/{id}/tags` | `CartridgeTag` | `ImageResponse` | 200 / 404 |
| GET | `/api/v1/images/{id}/file` | — | JPEG binary | 200 / 404 |
| GET | `/api/v1/images/{id}/thumbnail` | — | JPEG binary (256px max) | 200 / 404 |

**CartridgeTag (request body for POST .../tags):**
```json
{
  "cartridge_record_id": "string (required — the BIMS cartridge _id)",
  "phase": "string (required — e.g. 'backing', 'wax_filled', 'reagent_filled', 'inspected', 'sealed')",
  "labels": ["string (e.g. 'wax_fill', 'top_view', 'defect_crack')"],
  "notes": "string (optional free-text)"
}
```

**ImageResponse:**
```json
{
  "id": "string",
  "sample_id": "string",
  "filename": "string",
  "file_path": "string (relative path)",
  "thumbnail_path": "string (relative path)",
  "width": 640,
  "height": 480,
  "file_size_bytes": 104857,
  "camera_index": 0,
  "metadata": {},
  "captured_at": "ISO 8601 datetime",
  "image_url": "string (full R2 public URL, or '' if local-only)",
  "cartridge_tag": {
    "cartridge_record_id": "string",
    "phase": "string",
    "labels": ["string"],
    "notes": "string"
  }
}
```
> `cartridge_tag` is `null` until a tag is applied via `POST .../tags`.

---

### 3.4 Capture (`/api/v1/capture`)

| Method | Path | Body | Response | Status |
|--------|------|------|----------|--------|
| POST | `/api/v1/capture` | `CaptureRequest` | `ImageResponse` | 201 / 404 / 502 |
| POST | `/api/v1/samples/{id}/capture-and-inspect` | `CaptureAndInspectRequest` | `CaptureAndInspectResponse` | 201 / 404 / 502 |

**CaptureRequest:**
```json
{
  "sample_id": "string (required)",
  "camera_index": 0,
  "metadata": {}
}
```

**CaptureAndInspectRequest:**
```json
{
  "camera_index": 0,
  "inspection_type": "anomaly_detection",
  "metadata": {}
}
```

**CaptureAndInspectResponse:**
```json
{
  "image": { ... ImageResponse },
  "inspection": { ... InspectionResponse }
}
```

Error codes: **404** sample not found, **502** camera unavailable, **500** storage failure.

---

### 3.5 Cameras (`/api/v1/cameras`)

| Method | Path | Response | Status |
|--------|------|----------|--------|
| GET | `/api/v1/cameras` | `CameraInfo[]` | 200 |
| GET | `/api/v1/cameras/{index}/status` | `CameraInfo` | 200 / 404 |

**CameraInfo:**
```json
{
  "index": 0,
  "name": "Camera 0",
  "is_open": true,
  "width": 1920,
  "height": 1080
}
```

---

### 3.6 Inspections (`/api/inspections`)

| Method | Path | Body / Params | Response | Status |
|--------|------|---------------|----------|--------|
| POST | `/api/inspections` | `InspectionCreate` | `InspectionResponse` | 201 |
| GET | `/api/inspections/{id}` | — | `InspectionResponse` | 200 / 404 |
| GET | `/api/inspections` | `?sample_id= (required)` | `InspectionResponse[]` | 200 / 400 |
| GET | `/api/inspections/{id}/poll` | — | `InspectionResponse` | 200 / 404 |
| POST | `/api/inspections/{id}/result` | `InspectionResult` | `InspectionResponse` | 200 / 404 |

**InspectionCreate:**
```json
{
  "sample_id": "string (required)",
  "image_id": "string (required)",
  "inspection_type": "string (required, e.g. 'anomaly_detection')",
  "cartridge_record_id": "string | null (optional — BIMS cartridge _id)",
  "phase": "string | null (optional — manufacturing phase)"
}
```

**InspectionResult (webhook body from CV worker):**
```json
{
  "result": "pass | fail",
  "confidence_score": 0.95,
  "defects": [
    { "type": "scratch", "location": "top-left", "severity": "medium" }
  ],
  "model_version": "patchcore-v1",
  "processing_time_ms": 320
}
```

**InspectionResponse:**
```json
{
  "id": "string",
  "sample_id": "string",
  "image_id": "string",
  "inspection_type": "string",
  "status": "pending | processing | complete | failed",
  "result": "pass | fail | null",
  "confidence_score": 0.95,
  "defects": [
    { "type": "string", "location": "string", "severity": "string" }
  ],
  "model_version": "string",
  "processing_time_ms": 320,
  "created_at": "ISO 8601",
  "completed_at": "ISO 8601 | null",
  "cartridge_record_id": "string | null",
  "phase": "string | null"
}
```

---

## 4. Cartridge Photo Tagging Data Model

The BIMS `cartridge_records` collection uses this schema (simplified for
CV integration context):

```
cartridge_records
├── _id                    ObjectId (string in API)
├── cartridgeId            string (human-readable serial, e.g. "CART-2026-0042")
├── currentPhase           enum string — one of:
│                            backing
│                            wax_filled
│                            reagent_filled
│                            inspected
│                            sealed
│                            oven_cured
│                            qaqc_released
│                            shipped
│                            testing
│                            completed
├── backing                { status, operator, startedAt, completedAt, notes }
├── waxFilling             { status, operator, temperature, volume, ... }
├── reagentFilling         { status, operator, reagentLot, volume, ... }
├── topSeal                { status, operator, sealType, ... }
├── ovenCure               { status, temperature, duration, ... }
├── qaqcRelease            { status, inspector, passedAt, ... }
├── storage                { location, temperature, ... }
├── shipping               { trackingNumber, shippedAt, ... }
├── testExecution          { protocol, operator, startedAt, ... }
├── testResult             { passed, data, completedAt, ... }
├── createdAt              datetime
└── updatedAt              datetime
```

### How tagging works

1. **Image level** — When an image is captured during a cartridge's
   manufacturing phase, call `POST /api/v1/images/{id}/tags` with:
   ```json
   {
     "cartridge_record_id": "<cartridge _id>",
     "phase": "wax_filled",
     "labels": ["wax_fill", "top_view"],
     "notes": "Optional operator note"
   }
   ```

2. **Inspection level** — When creating an inspection (or using
   capture-and-inspect), pass the cartridge context:
   ```json
   {
     "sample_id": "...",
     "image_id": "...",
     "inspection_type": "anomaly_detection",
     "cartridge_record_id": "<cartridge _id>",
     "phase": "reagent_filled"
   }
   ```

3. **Query all photos for a cartridge:**
   ```
   GET /api/v1/images?cartridge_id=<cartridge_record_id>
   ```
   Returns all images tagged with that cartridge, across all phases.

4. **Query inspections for a sample:**
   ```
   GET /api/inspections?sample_id=<sample_id>
   ```
   Filter client-side by `cartridge_record_id` and `phase` if needed.

### Label conventions

| Label | Meaning |
|-------|---------|
| `wax_fill` | Photo taken during wax filling |
| `reagent_fill` | Photo taken during reagent filling |
| `top_seal` | Photo of top seal application |
| `top_view` | Top-down camera angle |
| `side_view` | Side camera angle |
| `defect_crack` | Visible crack defect |
| `defect_bubble` | Visible bubble defect |
| `defect_overflow` | Material overflow |
| `final_qc` | Final QA/QC inspection photo |
| `reference` | Reference/baseline image |

---

## 5. Inspection Status Flow

```
┌─────────┐   POST /api/inspections   ┌────────────┐
│  (none)  │ ─────────────────────────>│   pending   │
└─────────┘                            └──────┬─────┘
                                              │
                              Worker picks up  │
                                              ▼
                                       ┌────────────┐
                                       │ processing  │
                                       └──────┬─────┘
                                              │
                              ┌───────────────┼───────────────┐
                              │               │               │
                        Inference OK    Inference OK      Exception
                        score < thresh  score >= thresh
                              │               │               │
                              ▼               ▼               ▼
                        ┌──────────┐   ┌──────────┐   ┌──────────┐
                        │ complete │   │ complete │   │  failed   │
                        │  PASS    │   │  FAIL    │   │          │
                        └──────────┘   └──────────┘   └──────────┘
```

**Polling strategy for the UI:**

```typescript
async function pollInspection(id: string, intervalMs = 2000, maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    const insp = await cvFetch<InspectionResponse>(`/api/inspections/${id}/poll`);
    if (insp.status === 'complete' || insp.status === 'failed') {
      return insp;
    }
    await new Promise(r => setTimeout(r, intervalMs));
  }
  throw new Error('Inspection timed out');
}
```

---

## 6. Proposed BIMS Pages

### 6.1 CV Dashboard (`/cv/dashboard`)

**Purpose:** Overview of all recent inspections, pass/fail rates, and
quick access to capture.

**Data sources:**
- `GET /api/v1/samples?limit=20` — recent samples
- `GET /api/inspections?sample_id=X` — inspections per sample
- `GET /api/v1/cameras` — camera availability

**Component breakdown:**

```
CVDashboard.svelte
├── InspectionStatsBar.svelte
│   ├── StatCard (total inspections today)
│   ├── StatCard (pass rate %)
│   ├── StatCard (fail rate %)
│   └── StatCard (pending count)
│
├── RecentInspectionsTable.svelte
│   └── InspectionRow.svelte (one per inspection)
│       ├── StatusBadge.svelte (pending=yellow, processing=blue, pass=green, fail=red, failed=gray)
│       ├── ConfidenceBar.svelte (horizontal bar 0-100%)
│       ├── Thumbnail (<img> via cvThumbUrl)
│       └── CartridgeLink (link to /cv/cartridge/[id] if cartridge_record_id set)
│
├── CameraStatusPanel.svelte
│   └── CameraCard.svelte (per camera — index, resolution, is_open indicator)
│
└── QuickCaptureButton.svelte
    └── Navigates to /cv/capture
```

**Layout:** Stats bar across top. Left 2/3 is RecentInspectionsTable
(sorted by created_at descending). Right 1/3 is CameraStatusPanel +
QuickCaptureButton.

---

### 6.2 Cartridge Inspection Gallery (`/cv/cartridge/[cartridgeId]`)

**Purpose:** Show all inspection photos for a single cartridge record,
organized by manufacturing phase.  This is the primary view operators
use to review a cartridge's visual history.

**Data sources:**
- `GET /api/v1/images?cartridge_id={cartridgeId}` — all images for cartridge
- `GET /api/inspections?sample_id=X` — inspection results for related samples
- BIMS MongoDB: `cartridge_records.findOne({ _id: cartridgeId })` — cartridge metadata

**Component breakdown:**

```
CartridgeGallery.svelte
├── CartridgeHeader.svelte
│   ├── Cartridge ID + serial number
│   ├── Current phase badge
│   └── Phase progress bar (backing → ... → completed)
│
├── PhaseFilterTabs.svelte
│   └── Tab per phase (All | backing | wax_filled | reagent_filled | inspected | sealed | ...)
│       Active tab filters the gallery below
│
├── ImageGrid.svelte
│   └── ImageCard.svelte (one per image)
│       ├── Thumbnail (<img> via cvThumbUrl, click to expand)
│       ├── PhaseBadge.svelte (from cartridge_tag.phase)
│       ├── TagChips.svelte (from cartridge_tag.labels)
│       ├── InspectionOverlay.svelte (if inspection exists for this image)
│       │   ├── PassFailBadge.svelte
│       │   ├── ConfidenceBar.svelte
│       │   └── DefectList.svelte (if defects present)
│       └── NotesPopover.svelte (cartridge_tag.notes)
│
├── ImageLightbox.svelte
│   └── Full-resolution image viewer (loads from cvImageUrl)
│       ├── Image with zoom/pan
│       ├── Inspection result overlay
│       ├── Defect annotations (type, location, severity)
│       └── Navigation arrows (prev/next in gallery)
│
└── TagEditor.svelte
    └── Modal for editing cartridge_tag on an image
        ├── Phase dropdown (enum values)
        ├── Label chips input (autocomplete from conventions)
        ├── Notes textarea
        └── Save button → POST /api/v1/images/{id}/tags
```

**Data flow:**
```
Page load
  → fetch images by cartridge_id
  → fetch cartridge record from BIMS MongoDB
  → group images by phase
  → for each image with an inspection, show result overlay

Phase tab click
  → filter displayed images client-side (already loaded)

Tag edit
  → POST /api/v1/images/{id}/tags
  → update local store
  → re-render ImageCard
```

---

### 6.3 Live Capture + Inspect (`/cv/capture`)

**Purpose:** Operator captures a photo from the connected USB camera
and immediately kicks off a CV inspection.  Used during manufacturing
for real-time quality checks.

**Data sources:**
- `GET /api/v1/cameras` — available cameras
- `GET /api/v1/samples?limit=50` — samples to associate with
- `POST /api/v1/samples/{id}/capture-and-inspect` — capture + inspect
- `GET /api/inspections/{id}/poll` — poll for result
- `POST /api/v1/images/{id}/tags` — tag with cartridge after capture

**Component breakdown:**

```
LiveCapturePage.svelte
├── CaptureSetupPanel.svelte
│   ├── CameraSelector.svelte (dropdown from GET /cameras)
│   ├── SampleSelector.svelte (dropdown/search from GET /samples)
│   ├── InspectionTypeSelector.svelte (dropdown: anomaly_detection, visual, ...)
│   ├── CartridgeIdInput.svelte (optional — text input or BIMS cartridge picker)
│   ├── PhaseSelector.svelte (optional — dropdown of phase enum values)
│   └── CaptureButton.svelte (big, prominent — triggers capture flow)
│
├── CaptureResultPanel.svelte (shown after capture)
│   ├── CapturedImagePreview.svelte
│   │   └── Full image from cvImageUrl
│   │
│   ├── InspectionStatusTracker.svelte
│   │   ├── Step: "Captured" ✓
│   │   ├── Step: "Uploading to R2" ✓
│   │   ├── Step: "Inspection pending..." (spinner)
│   │   ├── Step: "Processing..." (spinner, shown during 'processing')
│   │   └── Step: "Complete" (shown with result)
│   │
│   ├── InspectionResultCard.svelte (shown when status=complete)
│   │   ├── PassFailBadge.svelte (large)
│   │   ├── ConfidenceScoreBar.svelte
│   │   ├── DefectAnnotations.svelte
│   │   ├── ProcessingTime.svelte ("320ms")
│   │   └── ModelVersion.svelte ("patchcore-v1")
│   │
│   └── PostCaptureTagging.svelte
│       ├── CartridgeIdInput (pre-filled if set before capture)
│       ├── PhaseSelector
│       ├── LabelChips input
│       ├── Notes textarea
│       └── SaveTagButton → POST /api/v1/images/{id}/tags
│
└── CaptureHistory.svelte
    └── Recent captures in this session (list of ImageCard + result)
```

**Capture flow (data):**
```
1. User selects camera, sample, inspection type
2. User clicks "Capture & Inspect"
3. POST /api/v1/samples/{sampleId}/capture-and-inspect
   Body: { camera_index, inspection_type, metadata }
   Response: { image: ImageResponse, inspection: InspectionResponse }
4. Show CapturedImagePreview with image data
5. Start polling: GET /api/inspections/{inspection.id}/poll
   Poll every 2 seconds
6. When status changes to "processing" → update status tracker
7. When status = "complete" or "failed" → stop polling, show result
8. If cartridge context was set:
   POST /api/v1/images/{image.id}/tags with CartridgeTag
```

---

### 6.4 Training Data Manager (`/cv/training`)

**Purpose:** Browse and curate captured images for model training.
Operators sort images into "good" and "defect" categories to build
the training dataset.

**Data sources:**
- `GET /api/v1/images?skip=&limit=` — browse all images
- `GET /api/v1/images?sample_id=X` — filter by sample
- `GET /api/v1/images?cartridge_id=X` — filter by cartridge
- `GET /api/inspections?sample_id=X` — get inspection results as labeling hints

**Component breakdown:**

```
TrainingDataManager.svelte
├── FilterBar.svelte
│   ├── SampleFilter (dropdown)
│   ├── CartridgeFilter (text input)
│   ├── DateRangeFilter
│   ├── InspectionResultFilter (all | pass | fail | uninspected)
│   └── PhaseFilter (dropdown of phases)
│
├── ImageBrowser.svelte
│   └── Paginated grid of ImageCard.svelte
│       ├── Thumbnail
│       ├── Inspection result badge (if exists)
│       ├── SelectionCheckbox
│       └── ClassificationBadge (good / defect / unclassified)
│
├── ClassificationPanel.svelte (sidebar)
│   ├── Selected count display
│   ├── "Mark as Good" button
│   ├── "Mark as Defect" button
│   ├── "Clear Classification" button
│   └── Classification stats (N good, N defect, N unclassified)
│
├── ExportPanel.svelte
│   ├── Export format info (folder structure)
│   ├── "Download Good Set" button
│   ├── "Download Defect Set" button
│   └── Export instructions text
│       "Download images and place in training/data/good/
│        and training/data/defect/ respectively."
│
└── Pagination.svelte
    └── Page controls (skip/limit based)
```

> **Note:** Image classification (good/defect) for training is stored
> client-side or in BIMS MongoDB — the CV API does not have a
> "training classification" field.  You can use `metadata` on the
> image or a separate BIMS collection like `cv_training_labels`.

---

## 7. Result Display Components

These shared components are used across multiple pages.

### 7.1 PassFailBadge

```svelte
<!-- PassFailBadge.svelte -->
<script lang="ts">
  export let result: 'pass' | 'fail' | null;
  export let status: string;
  export let size: 'sm' | 'md' | 'lg' = 'md';
</script>

<!--
  Renders a colored badge:
  - status = "pending"    → yellow badge, text "Pending"
  - status = "processing" → blue badge with pulse animation, text "Processing"
  - status = "failed"     → gray badge, text "Error"
  - result = "pass"       → green badge, text "PASS"
  - result = "fail"       → red badge, text "FAIL"

  Size variants: sm (inline in tables), md (cards), lg (result page hero)
-->
```

### 7.2 ConfidenceScoreBar

```svelte
<!-- ConfidenceScoreBar.svelte -->
<script lang="ts">
  export let score: number | null;   // 0.0 to 1.0
  export let threshold: number = 0.5; // pass/fail threshold
</script>

<!--
  Horizontal bar visualization:
  - Bar fill = score * 100%
  - Color gradient: green (0) → yellow (0.3) → orange (0.5) → red (1.0)
  - Vertical marker at threshold position
  - Text label: "95.0%" or "—" if null
  - Tooltip: "Anomaly score: 0.95 (threshold: 0.50)"
-->
```

### 7.3 DefectAnnotations

```svelte
<!-- DefectAnnotations.svelte -->
<script lang="ts">
  interface Defect {
    type: string;
    location: string;
    severity: string;
  }
  export let defects: Defect[];
</script>

<!--
  If defects is empty: show nothing or "No defects detected"
  If defects present: render a list:
    - Each row: [severity icon] [type] — [location]
    - severity "high" → red icon
    - severity "medium" → orange icon
    - severity "low" / "auto" → yellow icon

  Example output:
    🔴 scratch — top-left
    🟡 anomaly — global
-->
```

### 7.4 StatusBadge

Maps the four-state inspection status to visual indicators:

| Status | Color | Icon | Animation |
|--------|-------|------|-----------|
| `pending` | Yellow/amber | Clock | None |
| `processing` | Blue | Spinner | Pulse |
| `complete` | Green or Red (based on result) | Check or X | None |
| `failed` | Gray | Alert triangle | None |

---

## 8. TypeScript Types

Use these types throughout the BIMS frontend.  They mirror the CV API
response models exactly.

```typescript
// lib/types/cv.ts

export interface CartridgeTag {
  cartridge_record_id: string;
  phase: string;
  labels: string[];
  notes: string;
}

export interface ImageResponse {
  id: string;
  sample_id: string;
  filename: string;
  file_path: string;
  thumbnail_path: string;
  width: number;
  height: number;
  file_size_bytes: number;
  camera_index: number;
  metadata: Record<string, unknown>;
  captured_at: string;       // ISO 8601
  image_url: string;         // R2 public URL or ""
  cartridge_tag: CartridgeTag | null;
}

export interface SampleResponse {
  id: string;
  name: string;
  description: string;
  project: string;
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Defect {
  type: string;
  location: string;
  severity: string;
}

export interface InspectionResponse {
  id: string;
  sample_id: string;
  image_id: string;
  inspection_type: string;
  status: 'pending' | 'processing' | 'complete' | 'failed';
  result: 'pass' | 'fail' | null;
  confidence_score: number | null;
  defects: Defect[];
  model_version: string;
  processing_time_ms: number | null;
  created_at: string;
  completed_at: string | null;
  cartridge_record_id: string | null;
  phase: string | null;
}

export interface CaptureAndInspectRequest {
  camera_index?: number;
  inspection_type?: string;
  metadata?: Record<string, unknown>;
}

export interface CaptureAndInspectResponse {
  image: ImageResponse;
  inspection: InspectionResponse;
}

export interface CameraInfo {
  index: number;
  name: string;
  is_open: boolean;
  width: number;
  height: number;
}

export type InspectionStatus = InspectionResponse['status'];
export type InspectionResult = InspectionResponse['result'];

export const CARTRIDGE_PHASES = [
  'backing',
  'wax_filled',
  'reagent_filled',
  'inspected',
  'sealed',
  'oven_cured',
  'qaqc_released',
  'shipped',
  'testing',
  'completed',
] as const;

export type CartridgePhase = typeof CARTRIDGE_PHASES[number];

export const IMAGE_TAG_LABELS = [
  'wax_fill',
  'reagent_fill',
  'top_seal',
  'top_view',
  'side_view',
  'defect_crack',
  'defect_bubble',
  'defect_overflow',
  'final_qc',
  'reference',
] as const;
```

---

## 9. SvelteKit Route Structure

```
src/routes/
├── cv/
│   ├── +layout.svelte              CV section layout (sidebar nav)
│   ├── +layout.server.ts           Load camera status for sidebar
│   ├── dashboard/
│   │   ├── +page.svelte            CV Dashboard
│   │   └── +page.server.ts         Load samples + recent inspections
│   ├── cartridge/
│   │   └── [cartridgeId]/
│   │       ├── +page.svelte        Cartridge Inspection Gallery
│   │       └── +page.server.ts     Load images + cartridge record
│   ├── capture/
│   │   ├── +page.svelte            Live Capture + Inspect
│   │   └── +page.server.ts         Load cameras + samples list
│   └── training/
│       ├── +page.svelte            Training Data Manager
│       └── +page.server.ts         Load images with pagination
```

**Server-side data loading** (`+page.server.ts`): All CV API calls
should be made server-side to keep the `CV_API_KEY` secret.  Pass the
data to the page via `load()` return values.  Client-side polling
(for inspection status) can call a SvelteKit API route that proxies
to the CV API.

```
src/routes/api/cv/
├── inspections/
│   └── [id]/
│       └── poll/
│           └── +server.ts          Proxy: GET /api/inspections/{id}/poll
├── capture/
│   └── +server.ts                  Proxy: POST capture-and-inspect
└── images/
    └── [id]/
        └── tags/
            └── +server.ts          Proxy: POST /api/v1/images/{id}/tags
```

---

## 10. Svelte Stores

```typescript
// lib/stores/cv.ts
import { writable, derived } from 'svelte/store';
import type { InspectionResponse, ImageResponse, CameraInfo } from '$lib/types/cv';

// Currently active inspection being polled
export const activeInspection = writable<InspectionResponse | null>(null);

// Recent captures in current session
export const sessionCaptures = writable<Array<{
  image: ImageResponse;
  inspection: InspectionResponse;
}>>([]);

// Camera list (refreshed periodically)
export const cameras = writable<CameraInfo[]>([]);

// Derived: is any inspection currently being processed?
export const isProcessing = derived(
  activeInspection,
  ($insp) => $insp?.status === 'pending' || $insp?.status === 'processing'
);
```

---

## 11. Error Handling

| CV API Status | Meaning | UI Behavior |
|---------------|---------|-------------|
| 200/201 | Success | Show data |
| 400 | Bad request (missing sample_id) | Show validation error toast |
| 404 | Resource not found | Show "not found" message |
| 502 | Camera unavailable | Show "Camera not connected" error with retry button |
| 500 | Storage / server error | Show "Server error" toast with retry |

Always wrap `cvFetch` calls in try/catch and show user-friendly toast
notifications for errors.  For camera errors (502), offer a "Check
Camera" button that calls `GET /api/v1/cameras` to refresh status.

---

## 12. Quick Reference — API Calls per Page

| Page | On Load | On User Action |
|------|---------|----------------|
| CV Dashboard | `GET /samples`, `GET /inspections?sample_id=X` (per sample), `GET /cameras` | Click row → navigate to gallery |
| Cartridge Gallery | `GET /images?cartridge_id=X`, BIMS cartridge record | Edit tag → `POST /images/{id}/tags`, click image → lightbox |
| Live Capture | `GET /cameras`, `GET /samples` | Capture → `POST /samples/{id}/capture-and-inspect`, poll → `GET /inspections/{id}/poll`, tag → `POST /images/{id}/tags` |
| Training Manager | `GET /images?skip=&limit=` | Filter → re-fetch with params, classify → store in BIMS DB |
