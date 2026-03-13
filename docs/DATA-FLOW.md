# ICast Computer Vision — Data Flow Reference

> Quick reference for how data moves through the CV pipeline, where it's stored, and how the two systems (BIMS V2 + CV API) connect.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MFG WORKSTATION                          │
│                                                                 │
│   ┌──────────┐    ┌─────────────────────────────────────────┐   │
│   │  Webcam   │───▶│  Chrome Browser                         │   │
│   │ (USB)    │    │                                         │   │
│   └──────────┘    │  ┌───────────────────────────────────┐  │   │
│                   │  │  BIMS V2 (SvelteKit)              │  │   │
│                   │  │  - getUserMedia() captures frame   │  │   │
│                   │  │  - Sends to CV API                 │  │   │
│                   │  │  - Displays pass/fail result       │  │   │
│                   │  └──────────────┬────────────────────┘  │   │
│                   └─────────────────┼───────────────────────┘   │
└─────────────────────────────────────┼───────────────────────────┘
                                      │ HTTP (REST)
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CV API SERVER (FastAPI)                      │
│                     Mac mini / Cloud / Docker                    │
│                                                                 │
│   ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│   │  API Routes  │  │  CV Worker   │  │  Image Storage        │ │
│   │  /api/v1/*   │  │  (polling)   │  │  Local disk or R2/S3  │ │
│   └──────┬──────┘  └──────┬───────┘  └───────────────────────┘ │
│          │                │                                     │
│          ▼                ▼                                     │
│   ┌─────────────────────────────┐  ┌──────────────────────────┐│
│   │  MongoDB Atlas              │  │  ONNX Model              ││
│   │  Database: icast_cv         │  │  (Anomalib PatchCore)    ││
│   │  - images collection        │  │  Trained on "good" parts ││
│   │  - inspections collection   │  └──────────────────────────┘│
│   │  - samples collection       │                               │
│   └──────────────┬──────────────┘                               │
└──────────────────┼──────────────────────────────────────────────┘
                   │
                   │  Same Atlas cluster
                   │
┌──────────────────┼──────────────────────────────────────────────┐
│  MongoDB Atlas   │                                              │
│  Database: bioscale                                             │
│  - cartridge_records  ◄── linked by cartridge _id               │
│  - lab_cartridges                                               │
│  - equipment, users, etc.                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Photo Journey (Step by Step)

### Step 1 — Capture

```
WHO:    Operator at MFG workstation
WHAT:   Scans cartridge barcode → webcam captures frame
HOW:    Browser getUserMedia() API → canvas → blob
WHERE:  Client-side only (no server yet)
```

### Step 2 — Upload to CV API

```
WHO:    BIMS V2 frontend (automatic after capture)
WHAT:   POST /api/v1/samples/{sample_id}/capture-and-inspect
BODY:   {
          cartridge_id: "cart_abc123",
          phase: "reagent_filled",
          tags: ["reagent_fill", "station_2"],
          image: <binary blob>
        }
WHERE:  BIMS → CV API over HTTP
```

### Step 3 — Image Storage

```
WHO:    CV API (storage_service)
WHAT:   Saves image file + generates thumbnail
WHERE:  Local disk: data/images/{sample_id}/{timestamp}_{uuid}.jpg
   OR:  Cloudflare R2: {bucket}/{sample_id}/{timestamp}_{uuid}.jpg
RESULT: Returns file_path + image_url
```

### Step 4 — Database Records Created

```
WHO:    CV API (capture-and-inspect endpoint)
WHAT:   Creates TWO documents in MongoDB:

IMAGE DOC (icast_cv.images):
{
  _id: "img_xyz789",
  sample_id: "smp_001",
  filename: "20260313T154500_a1b2c3.jpg",
  file_path: "smp_001/20260313T154500_a1b2c3.jpg",
  image_url: "https://r2.example.com/smp_001/20260313T154500_a1b2c3.jpg",
  thumbnail_path: "smp_001/thumbs/20260313T154500_a1b2c3.jpg",
  width: 1920,
  height: 1080,
  file_size_bytes: 245760,
  cartridge_record_id: "cart_abc123",    ← links to BIMS
  tags: ["reagent_fill", "station_2"],
  phase: "reagent_filled",
  camera_index: 0,
  captured_at: "2026-03-13T15:45:00Z"
}

INSPECTION DOC (icast_cv.inspections):
{
  _id: "insp_def456",
  sample_id: "smp_001",
  image_id: "img_xyz789",
  cartridge_record_id: "cart_abc123",    ← links to BIMS
  phase: "reagent_filled",
  inspection_type: "anomaly_detection",
  status: "pending",                     ← waiting for worker
  result: null,
  confidence_score: null,
  defects: [],
  model_version: null,
  processing_time_ms: null,
  created_at: "2026-03-13T15:45:00Z",
  completed_at: null
}

RETURNS: inspection _id to BIMS for polling
```

### Step 5 — Worker Picks Up Inspection

```
WHO:    CV inference worker (separate Python process)
WHAT:   Polls MongoDB for inspections where status = "pending"
HOW:    Every 2 seconds, queries inspections collection
WHEN:   Finds insp_def456 → sets status: "processing"
```

### Step 6 — Model Inference

```
WHO:    CV worker (model_loader + preprocessor)
WHAT:   
  1. Downloads image from R2/disk using image_url
  2. Resizes to 224x224 (MODEL_INPUT_SIZE)
  3. Normalizes pixel values
  4. Runs through ONNX model (Anomalib PatchCore)
  5. Gets anomaly score (0.0 = normal, 1.0 = defective)
  6. Compares against CONFIDENCE_THRESHOLD (default 0.5)
  7. score < threshold → PASS | score >= threshold → FAIL
TIME:   ~200-500ms per image
```

### Step 7 — Results Written

```
WHO:    CV worker
WHAT:   Updates inspection document:

{
  _id: "insp_def456",
  ...
  status: "complete",                    ← was "processing"
  result: "pass",                        ← or "fail"
  confidence_score: 0.12,               ← low = good (normal)
  defects: [],                          ← or [{type, location, severity}]
  model_version: "patchcore-v1",
  processing_time_ms: 340,
  completed_at: "2026-03-13T15:45:01Z"
}
```

### Step 8 — BIMS Displays Result

```
WHO:    BIMS V2 frontend
WHAT:   Polls GET /api/v1/inspections/{id} every 1-2 seconds
WHEN:   status changes from "pending" → "complete"
SHOWS:  ✅ PASS (97% confidence) or ❌ FAIL (score + defect details)
```

---

## Database Schema Reference

### icast_cv.images

| Field | Type | Description |
|-------|------|-------------|
| `_id` | string | Unique image ID |
| `sample_id` | string | Parent sample group |
| `filename` | string | File name on disk/R2 |
| `file_path` | string | Relative path or R2 key |
| `image_url` | string | Full URL to access image |
| `thumbnail_path` | string | Thumbnail relative path |
| `width` | int | Image width in pixels |
| `height` | int | Image height in pixels |
| `file_size_bytes` | int | File size |
| `cartridge_record_id` | string | Links to BIMS cartridge_records._id |
| `tags` | string[] | Labels: wax_fill, reagent_fill, top_seal, final_qc, defect_crack, defect_bubble, custom |
| `phase` | string | Manufacturing phase (matches cartridge currentPhase) |
| `camera_index` | int | Which camera captured this |
| `captured_at` | datetime | When photo was taken |

### icast_cv.inspections

| Field | Type | Description |
|-------|------|-------------|
| `_id` | string | Unique inspection ID |
| `sample_id` | string | Parent sample group |
| `image_id` | string | Links to images._id |
| `cartridge_record_id` | string | Links to BIMS cartridge_records._id |
| `phase` | string | Manufacturing phase |
| `inspection_type` | string | Model type used (e.g. "anomaly_detection") |
| `status` | string | pending → processing → complete / failed |
| `result` | string | "pass" or "fail" (null until complete) |
| `confidence_score` | float | 0.0 (normal) to 1.0 (anomalous) |
| `defects` | object[] | [{type, location, severity}] |
| `model_version` | string | Which model version scored this |
| `processing_time_ms` | int | How long inference took |
| `created_at` | datetime | When inspection was requested |
| `completed_at` | datetime | When result was written |

### bioscale.cartridge_records (BIMS V2 — reference)

| Field | Type | Description |
|-------|------|-------------|
| `_id` | string | Cartridge ID (used as foreign key in CV) |
| `currentPhase` | string | backing, wax_filled, wax_qc, wax_stored, reagent_filled, inspected, sealed, cured, stored, released, shipped, assay_loaded, testing, completed, voided |
| `backing` | object | Lot ID, oven entry time |
| `waxFilling` | object | Robot, deck, wax source, timing |
| `waxQc` | object | Accept/Reject, operator |
| `reagentFilling` | object | Robot, assay type, tube records |
| `reagentInspection` | object | Accept/Reject, operator |
| `topSeal` | object | Batch, lot, operator |
| `ovenCure` | object | Location, entry time |
| `storage` | object | Fridge, container, operator |
| `qaqcRelease` | object | Shipping lot, test result |
| `shipping` | object | Package, customer, tracking |
| `testExecution` | object | SPU, operator |
| `testResult` | object | Analyte, value, spectro readings |

---

## Cross-Database Linking

```
bioscale DB                          icast_cv DB
───────────                          ───────────

cartridge_records                    images
┌──────────────┐                     ┌──────────────────────┐
│ _id: "cart_1" │◄────────────────────│ cartridge_record_id  │
│ currentPhase  │                     │ tags, phase          │
│ backing {...}  │                     │ image_url            │
│ waxFilling {}  │                     └──────────────────────┘
│ ...           │
│               │                     inspections
│               │                     ┌──────────────────────┐
│               │◄────────────────────│ cartridge_record_id  │
└──────────────┘                     │ result, score        │
                                     │ status, defects      │
NO foreign keys.                     └──────────────────────┘
Just matching _id strings
across two databases.
```

---

## API Quick Reference

### Core Flow

| Step | Endpoint | Method | What It Does |
|------|----------|--------|-------------|
| Capture + inspect | `/api/v1/samples/{id}/capture-and-inspect` | POST | One call: save image + create pending inspection |
| Poll for result | `/api/v1/inspections/{id}` | GET | Check if result is ready |
| Long poll | `/api/v1/inspections/{id}/poll` | GET | Wait up to 30s for result |

### Image Management

| Endpoint | Method | What It Does |
|----------|--------|-------------|
| `/api/v1/images/upload` | POST | Upload image file |
| `/api/v1/images/{id}` | GET | Get image metadata |
| `/api/v1/images/{id}/tags` | POST | Add/update tags on image |
| `/api/v1/images?cartridge_id=X` | GET | List images for a cartridge |

### Inspection Queries

| Endpoint | Method | What It Does |
|----------|--------|-------------|
| `/api/v1/inspections` | GET | List all inspections |
| `/api/v1/inspections/{id}` | GET | Get single inspection |
| `/api/v1/inspections?sample_id=X` | GET | Filter by sample |
| `/api/v1/inspections/cartridge/{id}` | GET | All inspections for a cartridge |
| `/api/v1/inspections/cartridge/{id}/phase/{phase}` | GET | Filter by cartridge + phase |

### Model Training

| Endpoint | Method | What It Does |
|----------|--------|-------------|
| `/api/v1/training/upload` | POST | Upload training images (good/defect) |
| `/api/v1/training/train` | POST | Start model training |
| `/api/v1/training/status` | GET | Check training progress |
| `/api/v1/training/export` | POST | Export trained model to ONNX |

### Stats

| Endpoint | Method | What It Does |
|----------|--------|-------------|
| `/api/v1/dashboard/stats` | GET | Total counts, pass/fail rates |

---

## Environment Variables

### CV API (.env)

| Variable | Example | Description |
|----------|---------|-------------|
| `MONGODB_URI` | `mongodb+srv://...icast_cv` | Atlas connection (icast_cv database) |
| `MONGODB_DATABASE` | `icast_cv` | Database name |
| `IMAGE_STORAGE_PATH` | `data/images` | Local image storage directory |
| `R2_ACCOUNT_ID` | (Cloudflare ID) | R2 cloud storage account |
| `R2_ACCESS_KEY_ID` | (key) | R2 access key |
| `R2_SECRET_ACCESS_KEY` | (secret) | R2 secret key |
| `R2_BUCKET_NAME` | `icast-images` | R2 bucket name |
| `R2_PUBLIC_URL` | `https://images.example.com` | Public URL prefix for images |
| `MODEL_PATH` | `model.onnx` | Path to trained ONNX model |
| `MODEL_INPUT_SIZE` | `224` | Model input image size (pixels) |
| `CONFIDENCE_THRESHOLD` | `0.5` | Above = fail, below = pass |
| `API_KEY` | (optional) | API authentication key |

### BIMS V2 (.env)

| Variable | Example | Description |
|----------|---------|-------------|
| `CV_API_URL` | `http://localhost:8000` | Where the CV API is running |

---

## Status Flow Diagram

```
                    ┌─────────┐
  API creates ────▶ │ PENDING │
                    └────┬────┘
                         │ Worker picks up
                         ▼
                    ┌────────────┐
                    │ PROCESSING │
                    └────┬───────┘
                         │
                    ┌────┴────┐
                    │         │
                    ▼         ▼
              ┌──────────┐ ┌────────┐
              │ COMPLETE │ │ FAILED │
              └────┬─────┘ └────────┘
                   │
              ┌────┴────┐
              │         │
              ▼         ▼
           ┌──────┐ ┌──────┐
           │ PASS │ │ FAIL │
           └──────┘ └──────┘
```

---

*Last updated: March 13, 2026*
*Repo: avacoder3900/I_cast_computa_vision (branch: ralph/cv-pipeline)*
