# Computer Vision Inspection System — Complete Overview

> Brevitest In-Process Quality Inspection via Computer Vision
> Last Updated: March 15, 2026

---

## Table of Contents

1. [System Location](#1-system-location)
2. [User Workflow](#2-user-workflow)
3. [Data Flow Process](#3-data-flow-process)
4. [Model Validation](#4-model-validation)
5. [BIMS Connection](#5-bims-connection)
6. [Database Schemas](#6-database-schemas)
7. [API Reference](#7-api-reference)
8. [Environment Configuration](#8-environment-configuration)
9. [Project Status](#9-project-status)
10. [Next Steps](#10-next-steps)

---

## 1. System Location

| Component | Location | Repo / Path |
|-----------|----------|-------------|
| CV API + Inference Worker | Mac mini (or any server with Python 3.11+) | `avacoder3900/I_cast_computa_vision` — branch `ralph/cv-pipeline` |
| Admin Dashboard | Served by CV API at `/ui/` | Same repo — `src/icast_cv/static/` + `templates/` |
| BIMS V2 Frontend (CV pages) | Vercel or local dev | `Bioscale_Operations_System_V2` — branch `cv` |
| Image Storage | Local disk (default) or Cloudflare R2 | `data/images/` or R2 bucket |
| Database — CV data | MongoDB Atlas | Database: `icast_cv` (images, inspections, samples) |
| Database — BIMS data | MongoDB Atlas (same cluster) | Database: `bioscale` (cartridge_records, equipment, users) |
| Trained Model | CV API server filesystem | `model.onnx` (generated after training) |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MFG WORKSTATION                                  │
│                                                                     │
│   ┌──────────┐    ┌───────────────────────────────────────────┐     │
│   │  Webcam   │───▶│  Chrome Browser                           │     │
│   │  (USB)   │    │                                           │     │
│   └──────────┘    │  ┌─────────────────────────────────────┐  │     │
│                   │  │  BIMS V2 (SvelteKit on Vercel)      │  │     │
│                   │  │                                     │  │     │
│                   │  │  • getUserMedia() captures frame    │  │     │
│                   │  │  • Sends image to CV API            │  │     │
│                   │  │  • Polls for result                 │  │     │
│                   │  │  • Displays pass/fail to operator   │  │     │
│                   │  └──────────────┬──────────────────────┘  │     │
│                   └─────────────────┼─────────────────────────┘     │
└─────────────────────────────────────┼───────────────────────────────┘
                                      │ HTTP (REST API)
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  CV API SERVER (FastAPI on Mac mini)                 │
│                                                                     │
│  ┌──────────────┐   ┌───────────────┐   ┌────────────────────────┐ │
│  │  API Routes   │   │  CV Worker    │   │  Image Storage         │ │
│  │  /api/v1/*    │   │  (background  │   │                        │ │
│  │               │   │   process,    │   │  Local: data/images/   │ │
│  │  Receives     │   │   polls for   │   │    OR                  │ │
│  │  images,      │   │   pending     │   │  Cloud: Cloudflare R2  │ │
│  │  creates      │   │   jobs)       │   │                        │ │
│  │  inspections  │   │               │   └────────────────────────┘ │
│  └──────┬───────┘   └──────┬────────┘                               │
│         │                  │                                         │
│         ▼                  ▼                                         │
│  ┌──────────────────────────────┐   ┌───────────────────────────┐   │
│  │  MongoDB Atlas               │   │  ONNX Model               │   │
│  │  Database: icast_cv          │   │  (Anomalib PatchCore)     │   │
│  │                              │   │                           │   │
│  │  Collections:                │   │  Trained on "good" parts  │   │
│  │  • images                    │   │  Flags anomalies          │   │
│  │  • inspections               │   │  Returns 0.0–1.0 score   │   │
│  │  • samples                   │   └───────────────────────────┘   │
│  └──────────────┬───────────────┘                                    │
└──────────────────┼──────────────────────────────────────────────────┘
                   │
                   │ Same Atlas cluster, different database
                   │
┌──────────────────┼──────────────────────────────────────────────────┐
│  MongoDB Atlas   │                                                  │
│  Database: bioscale                                                 │
│                                                                     │
│  • cartridge_records  ◄── linked by cartridge _id string            │
│  • lab_cartridges                                                   │
│  • equipment                                                        │
│  • users                                                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. User Workflow

### What the Operator Does (Step by Step)

```
STEP 1 — IDENTIFY CARTRIDGE
   Operator scans cartridge barcode at workstation
   → BIMS pulls up the cartridge record
   → Shows current manufacturing phase

STEP 2 — SELECT PHASE
   Operator confirms or selects the current phase
   → e.g. "Wax Fill", "Reagent Fill", "Top Seal", "Final QC"

STEP 3 — CAMERA PREVIEW
   Webcam shows live preview on the BIMS page
   → Browser accesses USB camera via getUserMedia()
   → Operator positions cartridge under camera

STEP 4 — CAPTURE
   Operator clicks "Capture & Inspect"
   → Photo is taken automatically
   → Image sent to CV API in background
   → Loading indicator shows "Analyzing..."

STEP 5 — VIEW RESULT (1-3 seconds)
   Result appears on screen:
   ┌──────────────────────────────────┐
   │  ✅ PASS                         │
   │  Confidence: 97%                │
   │  Phase: Reagent Fill            │
   │  Time: 340ms                    │
   │                                  │
   │  [Retake]  [Continue to Next]   │
   └──────────────────────────────────┘

   OR

   ┌──────────────────────────────────┐
   │  ❌ FAIL                         │
   │  Confidence: 34%                │
   │  Defects: bubble detected       │
   │  Phase: Wax Fill                │
   │                                  │
   │  [Retake]  [Override]  [Reject] │
   └──────────────────────────────────┘

STEP 6 — ACTION ON FAIL
   If FAIL, operator can:
   → Retake photo (maybe misaligned)
   → Override with reason + supervisor approval
   → Reject / quarantine the cartridge

The operator NEVER leaves BIMS.
The operator NEVER opens another app.
```

---

## 3. Data Flow Process

### The Journey of a Photo

```
STAGE 1: CAPTURE
─────────────────
WHO:    Operator at MFG workstation
WHAT:   Webcam captures a frame of the cartridge
HOW:    Browser getUserMedia() API → canvas → image blob
WHERE:  Client-side only (nothing saved yet)


STAGE 2: UPLOAD
─────────────────
WHO:    BIMS V2 frontend (automatic after capture)
WHAT:   Sends image + metadata to CV API
HOW:    POST /api/v1/samples/{sample_id}/capture-and-inspect
BODY:   {
          cartridge_id: "cart_abc123",
          phase: "reagent_filled",
          tags: ["reagent_fill", "station_2"],
          image: <binary blob>
        }
WHERE:  BIMS (Vercel) → CV API (Mac mini) over HTTPS


STAGE 3: STORAGE
─────────────────
WHO:    CV API storage service
WHAT:   Saves full image + generates thumbnail
WHERE:  Option A — Local disk:
          data/images/{sample_id}/{timestamp}_{uuid}.jpg
          data/images/{sample_id}/thumbs/{timestamp}_{uuid}.jpg
        Option B — Cloudflare R2:
          {bucket}/{sample_id}/{timestamp}_{uuid}.jpg
RESULT: Returns file_path + image_url


STAGE 4: DATABASE RECORDS
─────────────────────────
WHO:    CV API (capture-and-inspect endpoint)
WHAT:   Creates TWO documents in MongoDB (icast_cv database):

        IMAGE DOC:
        {
          _id: "img_xyz789",
          sample_id: "smp_001",
          filename: "20260313T154500_a1b2c3.jpg",
          image_url: "https://r2.example.com/...",
          cartridge_record_id: "cart_abc123",
          tags: ["reagent_fill"],
          phase: "reagent_filled",
          width: 1920, height: 1080,
          captured_at: "2026-03-13T15:45:00Z"
        }

        INSPECTION DOC:
        {
          _id: "insp_def456",
          image_id: "img_xyz789",
          cartridge_record_id: "cart_abc123",
          phase: "reagent_filled",
          status: "pending",        ← waiting for worker
          result: null,
          confidence_score: null,
          created_at: "2026-03-13T15:45:00Z"
        }

RETURNS: inspection_id to BIMS for polling


STAGE 5: INFERENCE
─────────────────
WHO:    CV inference worker (separate background process)
WHAT:   1. Polls MongoDB every 2 seconds for status: "pending"
        2. Finds inspection → sets status: "processing"
        3. Downloads image from R2/disk
        4. Resizes to 224×224 pixels
        5. Normalizes pixel values
        6. Runs through ONNX model (Anomalib PatchCore)
        7. Gets anomaly score: 0.0 (normal) → 1.0 (defective)
        8. Compares against CONFIDENCE_THRESHOLD (default 0.5)
        9. score < threshold → PASS
           score >= threshold → FAIL
TIME:   ~200–500ms per image


STAGE 6: RESULT WRITTEN
────────────────────────
WHO:    CV worker updates MongoDB
WHAT:   {
          status: "complete",
          result: "pass",
          confidence_score: 0.12,
          defects: [],
          model_version: "patchcore-v1",
          processing_time_ms: 340,
          completed_at: "2026-03-13T15:45:01Z"
        }


STAGE 7: DISPLAY
─────────────────
WHO:    BIMS V2 frontend
WHAT:   Polls GET /api/v1/inspections/{id} every 1-2 seconds
WHEN:   status changes "pending" → "complete"
SHOWS:  ✅ PASS (97% confidence) or ❌ FAIL (score + defect list)
```

---

## 4. Model Validation

### Phase 1 — Collect Training Data

```
GOAL:   Teach the model what a "good" cartridge looks like
HOW:    Mount webcam → open admin UI → photograph parts
COUNT:  Minimum 50 good images per phase (more = better)

Steps:
1. Mount webcam at the workstation
2. Open admin dashboard → /ui/training
3. Select category: "good"
4. Photograph 50–100 GOOD cartridges
   → Drag-and-drop or click to upload
   → Cover different angles, lighting conditions
5. (Optional) Photograph KNOWN DEFECTS
   → Upload to "defect" category
   → Helps model evaluation but not required for training
```

### Phase 2 — Train the Model

```
GOAL:   Build the ONNX model file
HOW:    Click a button in admin UI
TIME:   5–30 minutes depending on dataset size

Steps:
1. Admin UI → /ui/training
2. Verify training data counts (good: 50+, defect: optional)
3. Click "Train Model"
4. Wait for training to complete (progress shown on screen)
5. Click "Export to ONNX"
6. model.onnx is generated and ready for the worker

WHAT HAPPENS UNDER THE HOOD:
  → Anomalib PatchCore algorithm
  → Extracts feature embeddings from good images
  → Builds a "coreset" — a compact representation of normal
  → Any new image compared against this coreset
  → Distance from normal = anomaly score
```

### Phase 3 — Validate Performance

```
GOAL:   Prove the model works before going live
METHOD: Test with known good AND known bad samples

Steps:
1. Prepare a VALIDATION SET (separate from training data):
   → 20+ known GOOD samples (confirmed by human)
   → 20+ known BAD samples (real defects or simulated)
   → Label each with expected result

2. Run all through the system
   → Upload each image
   → Record: expected result vs actual result

3. Calculate metrics:
   ┌────────────────────┬─────────────────────────────────────┐
   │ Metric             │ What It Means                       │
   ├────────────────────┼─────────────────────────────────────┤
   │ Sensitivity (TPR)  │ % of real defects caught            │
   │ Specificity (TNR)  │ % of good parts correctly passed    │
   │ Accuracy           │ Overall % correct                   │
   │ False Positive Rate│ Good parts wrongly flagged as bad   │
   │ False Negative Rate│ Bad parts wrongly passed as good    │
   └────────────────────┴─────────────────────────────────────┘

4. Tune CONFIDENCE_THRESHOLD:
   → Lower (e.g. 0.3) = stricter, catches more, more false alarms
   → Higher (e.g. 0.7) = looser, fewer false alarms, might miss defects
   → Target: sensitivity > 95%, specificity > 90%

5. Document everything for QMS records
   → ISO 13485 §7.5.6 (validation of production processes)
   → Include: dataset size, metrics, threshold chosen, date, reviewer
```

### Phase 4 — Ongoing Monitoring

```
GOAL:   Keep the model accurate over time

• Track pass/fail rates on the dashboard
  → Sudden spike in failures? Check camera, lighting, or model drift
• Retrain periodically (monthly or after process changes)
  → Add new images to training set
  → Re-run training + validation
• Keep validation records for audits
• Log any operator overrides (supervisor-approved FAIL→PASS)
```

---

## 5. BIMS Connection

### How the Two Systems Communicate

```
BIMS V2 (SvelteKit)                        CV API (FastAPI)
Deployed on Vercel                          Running on Mac mini / server
Database: bioscale                          Database: icast_cv
────────────────────                        ─────────────────────

Env var: CV_API_URL                         Env var: MONGODB_URI
= http://server:8000                        = mongodb+srv://...icast_cv

┌─ /cv/inspect ──────────────┐              ┌─ /api/v1/ ──────────────┐
│                             │    POST      │                          │
│  Camera preview             │─────────────▶│  capture-and-inspect     │
│  Capture button             │              │  → saves image to R2     │
│                             │              │  → creates image doc     │
│                             │              │  → creates inspection    │
│                             │    GET       │    (status: pending)     │
│  Poll for result            │◀─────────────│                          │
│  GET /inspections/{id}      │              │  Worker runs model...    │
│                             │              │  → updates result        │
│  Show ✅ PASS or ❌ FAIL    │    GET       │                          │
│  with confidence score      │◀─────────────│  Returns complete doc    │
│                             │              │                          │
└─────────────────────────────┘              └──────────────────────────┘
```

### Cross-Database Linking

```
bioscale DB                              icast_cv DB
───────────                              ───────────

cartridge_records                        images
┌──────────────────┐                     ┌──────────────────────┐
│ _id: "cart_abc"   │◄────────────────────│ cartridge_record_id  │
│ currentPhase      │                     │ tags, phase          │
│ backing {...}     │                     │ image_url            │
│ waxFilling {...}  │                     └──────────────────────┘
│ reagentFilling {} │
│ topSeal {...}     │                     inspections
│ qaqcRelease {...} │                     ┌──────────────────────┐
│ ...               │◄────────────────────│ cartridge_record_id  │
└──────────────────┘                     │ result, score        │
                                         │ phase, status        │
  No foreign keys.                       └──────────────────────┘
  Just matching _id strings.
```

### BIMS Pages (SvelteKit Routes)

| Route | Page | What It Shows |
|-------|------|---------------|
| `/cv` | Dashboard | Total inspections, pass/fail rates, recent activity |
| `/cv/inspect` | Capture & Inspect | Live webcam, capture button, result display |
| `/cv/history` | Inspection History | Filterable list of all inspections |
| `/cv/cartridge/[id]` | Cartridge Timeline | All inspections for one cartridge, grouped by phase |

---

## 6. Database Schemas

### icast_cv.images

| Field | Type | Description |
|-------|------|-------------|
| `_id` | string | Unique image ID |
| `sample_id` | string | Parent sample group |
| `filename` | string | Filename on disk/R2 |
| `file_path` | string | Relative path or R2 key |
| `image_url` | string | Full URL to access image |
| `thumbnail_path` | string | Thumbnail path |
| `width` | int | Pixels |
| `height` | int | Pixels |
| `file_size_bytes` | int | File size |
| `cartridge_record_id` | string | → bioscale.cartridge_records._id |
| `tags` | string[] | wax_fill, reagent_fill, top_seal, final_qc, defect_crack, defect_bubble |
| `phase` | string | Matches cartridge currentPhase |
| `camera_index` | int | Which camera |
| `captured_at` | datetime | When taken |

### icast_cv.inspections

| Field | Type | Description |
|-------|------|-------------|
| `_id` | string | Unique inspection ID |
| `sample_id` | string | Parent sample |
| `image_id` | string | → images._id |
| `cartridge_record_id` | string | → bioscale.cartridge_records._id |
| `phase` | string | Manufacturing phase |
| `inspection_type` | string | e.g. "anomaly_detection" |
| `status` | string | pending → processing → complete / failed |
| `result` | string | "pass" or "fail" (null until complete) |
| `confidence_score` | float | 0.0 (normal) to 1.0 (anomalous) |
| `defects` | object[] | [{type, location, severity}] |
| `model_version` | string | Which model scored this |
| `processing_time_ms` | int | Inference duration |
| `created_at` | datetime | When requested |
| `completed_at` | datetime | When scored |

### bioscale.cartridge_records (Reference)

| Field | Type | Description |
|-------|------|-------------|
| `_id` | string | Cartridge ID (used as link in CV system) |
| `currentPhase` | enum | backing, wax_filled, wax_qc, wax_stored, reagent_filled, inspected, sealed, cured, stored, released, shipped, assay_loaded, testing, completed, voided |
| `backing` | object | Lot ID, oven entry time |
| `waxFilling` | object | Robot, deck, wax source, timing |
| `waxQc` | object | Accept/Reject status, operator |
| `reagentFilling` | object | Robot, assay type, tube records |
| `reagentInspection` | object | Accept/Reject status, operator |
| `topSeal` | object | Batch, lot, operator |
| `ovenCure` | object | Location, entry time |
| `storage` | object | Fridge, container, operator |
| `qaqcRelease` | object | Shipping lot, test result (pass/fail/pending) |
| `shipping` | object | Package, customer, tracking |
| `testExecution` | object | SPU details, operator |
| `testResult` | object | Analyte, value, spectro readings, status |

### Inspection Status Flow

```
                    ┌─────────┐
  Created ────────▶ │ PENDING │
                    └────┬────┘
                         │ Worker picks up
                         ▼
                    ┌────────────┐
                    │ PROCESSING │
                    └─────┬──────┘
                          │
                    ┌─────┴─────┐
                    │           │
                    ▼           ▼
              ┌──────────┐ ┌────────┐
              │ COMPLETE │ │ FAILED │
              └────┬─────┘ └────────┘
                   │         (error)
              ┌────┴────┐
              │         │
              ▼         ▼
           ┌──────┐ ┌──────┐
           │ PASS │ │ FAIL │
           └──────┘ └──────┘
```

---

## 7. API Reference

### Core Inspection Flow

| Action | Method | Endpoint |
|--------|--------|----------|
| Capture + auto-inspect | POST | `/api/v1/samples/{sample_id}/capture-and-inspect` |
| Poll for result | GET | `/api/v1/inspections/{id}` |
| Long poll (waits 30s) | GET | `/api/v1/inspections/{id}/poll` |

### Image Management

| Action | Method | Endpoint |
|--------|--------|----------|
| Upload image | POST | `/api/v1/images/upload` |
| Get image info | GET | `/api/v1/images/{id}` |
| Add/update tags | POST | `/api/v1/images/{id}/tags` |
| List by cartridge | GET | `/api/v1/images?cartridge_id={id}` |

### Inspection Queries

| Action | Method | Endpoint |
|--------|--------|----------|
| List all | GET | `/api/v1/inspections` |
| Get one | GET | `/api/v1/inspections/{id}` |
| By sample | GET | `/api/v1/inspections?sample_id={id}` |
| By cartridge | GET | `/api/v1/inspections/cartridge/{cartridge_id}` |
| By cartridge + phase | GET | `/api/v1/inspections/cartridge/{cartridge_id}/phase/{phase}` |

### Model Training & Management

| Action | Method | Endpoint |
|--------|--------|----------|
| Upload training images | POST | `/api/v1/training/upload` |
| Start training | POST | `/api/v1/training/train` |
| Check training status | GET | `/api/v1/training/status` |
| Export model to ONNX | POST | `/api/v1/training/export` |

### Dashboard

| Action | Method | Endpoint |
|--------|--------|----------|
| Get stats | GET | `/api/v1/dashboard/stats` |

---

## 8. Environment Configuration

### CV API Server (.env)

```bash
# MongoDB — same Atlas cluster, separate database
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/icast_cv
MONGODB_DATABASE=icast_cv

# Image storage — local path
IMAGE_STORAGE_PATH=data/images

# Cloudflare R2 (optional — leave blank for local storage)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_URL=

# Camera
DEFAULT_CAMERA_INDEX=0

# Server
HOST=0.0.0.0
PORT=8000

# CORS — add BIMS domain
CORS_ORIGINS=http://localhost:3000,https://your-bims.vercel.app

# API key (empty = no auth, dev only)
API_KEY=

# Model
MODEL_PATH=model.onnx
MODEL_INPUT_SIZE=224
CONFIDENCE_THRESHOLD=0.5
```

### BIMS V2 (.env)

```bash
# Add this to existing BIMS .env
CV_API_URL=http://localhost:8000
```

---

## 9. Project Status

| Component | Status | Notes |
|-----------|--------|-------|
| CV API backend | ✅ Complete | FastAPI, all endpoints, 52 tests passing |
| Cloud storage (R2/S3) | ✅ Complete | With local fallback |
| Inspection data model | ✅ Complete | Full CRUD + cartridge linking |
| Inference worker | ✅ Complete | ONNX model runner, polling loop |
| Training scaffold | ✅ Complete | Anomalib PatchCore, train + export scripts |
| Cartridge photo tagging | ✅ Complete | Tags, phases, cartridge ID linking |
| Admin dashboard UI | ✅ Complete | 5 pages, dark theme, vanilla JS |
| Data flow documentation | ✅ Complete | DATA-FLOW.md + this document |
| BIMS UI integration doc | ✅ Complete | BIMS-UI-INTEGRATION.md (1000 lines) |
| BIMS V2 CV pages | ⚠️ In Progress | Branch `cv` created, pages need building |
| Webcam hardware | ❌ Not Started | Need USB webcam mounted at workstation |
| Training data | ❌ Not Started | Need 50+ good photos per phase |
| Model training | ❌ Not Started | Blocked by training data |
| Validation testing | ❌ Not Started | Blocked by trained model |
| Cloudflare R2 setup | ❌ Not Started | Optional — local storage works for now |

---

## 10. Next Steps

### To Get Running (Minimum Viable)

```
1. Mount webcam at MFG workstation
2. Take 50+ photos of good cartridges (per phase you want to inspect)
3. Upload to admin UI → train model → export ONNX
4. Finish BIMS V2 CV pages (branch: cv)
5. Test end-to-end with a few cartridges
6. Tune confidence threshold based on results
```

### To Go Production

```
1. Set up Cloudflare R2 bucket (free 10GB, zero egress)
2. Run validation testing (20+ good, 20+ bad, document results)
3. Document for ISO 13485 §7.5.6 (process validation)
4. Add operator override workflow (supervisor approval for FAIL→PASS)
5. Set up monitoring dashboard alerts (fail rate spikes)
6. Schedule periodic retraining (monthly or after process changes)
```

---

## Quick Links

| Resource | Location |
|----------|----------|
| CV API repo | `github.com/avacoder3900/I_cast_computa_vision` (branch: `ralph/cv-pipeline`) |
| BIMS V2 repo | `github.com/aiagentcode001/Bioscale_Operations_System_V2` (branch: `cv`) |
| Admin dashboard | `http://[server]:8000/ui/` |
| API docs (Swagger) | `http://[server]:8000/docs` |
| Data flow reference | `docs/DATA-FLOW.md` in CV repo |
| BIMS integration PRD | `docs/BIMS-UI-INTEGRATION.md` in CV repo |

---

*Document Version: 1.0*
*Created: March 15, 2026*
*Author: Agent001 (Brevitest AI)*
*For: Alejandro Valdez — Operations Manager*
