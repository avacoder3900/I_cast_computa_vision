# ICast Computer Vision API — Integration Guide

## What This Is

This is a **separate backend API** (not part of your Next.js app). It runs on its own server and your Vercel site calls it over HTTP. Think of it like calling any third-party API — Stripe, Twilio, etc — except this one is yours.

```
[Vercel / Next.js Frontend]  ---HTTP--->  [ICast CV API]  --->  [MongoDB]
     your website                         separate server        shared DB
```

**You do NOT merge this repo into your website repo.** They stay separate.

---

## API Base URL

Once deployed, the API lives at a URL like:
```
https://icast-cv-production.up.railway.app
```

During development, if running locally:
```
http://localhost:8000
```

---

## Authentication

Every request to `/api/v1/*` requires an `X-API-Key` header:

```ts
headers: { "X-API-Key": process.env.ICAST_API_KEY }
```

The `/health` and `/docs` endpoints are public (no key needed).

---

## Environment Variables to Set in Vercel

```
NEXT_PUBLIC_ICAST_API_URL=https://your-icast-api-url.com
ICAST_API_KEY=PgJXWr3i6r5p2nBPh0SLn2GNNyu9i0XO128ZL0THn98
```

`NEXT_PUBLIC_` prefix makes the URL available client-side. The API key should **NOT** have the `NEXT_PUBLIC_` prefix — keep it server-side only.

---

## How to Call the API from Next.js

### Option A: Server-side API route (recommended — hides API key from browser)

Create a Next.js API route that proxies requests:

```ts
// app/api/samples/route.ts
import { NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_ICAST_API_URL;
const API_KEY = process.env.ICAST_API_KEY;

export async function GET() {
  const res = await fetch(`${API_URL}/api/v1/samples`, {
    headers: { "X-API-Key": API_KEY ?? "" },
  });
  const data = await res.json();
  return NextResponse.json(data);
}

export async function POST(request: Request) {
  const body = await request.json();
  const res = await fetch(`${API_URL}/api/v1/samples`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY ?? "",
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
```

Then from your React components, call your own API route:
```ts
const res = await fetch("/api/samples");
const samples = await res.json();
```

### Option B: Direct client-side fetch (simpler, but exposes API URL)

```ts
const API_URL = process.env.NEXT_PUBLIC_ICAST_API_URL;

const res = await fetch(`${API_URL}/api/v1/samples`, {
  headers: { "X-API-Key": "your-key-here" },
});
```

**Option A is recommended** because it keeps your API key on the server.

---

## Available Endpoints

### Samples (lab samples)

| Method | Path | Description | Request Body |
|--------|------|-------------|-------------|
| `POST` | `/api/v1/samples` | Create a sample | `{ "name": "Sample ABC", "description": "...", "project": "...", "tags": ["tag1"] }` |
| `GET` | `/api/v1/samples` | List samples | Query: `?skip=0&limit=50` |
| `GET` | `/api/v1/samples/{id}` | Get one sample | — |
| `PATCH` | `/api/v1/samples/{id}` | Update a sample | `{ "name": "New Name" }` (any fields) |
| `DELETE` | `/api/v1/samples/{id}` | Delete a sample | — |

### Image Capture

| Method | Path | Description | Request Body |
|--------|------|-------------|-------------|
| `POST` | `/api/v1/capture` | Capture photo from camera | `{ "sample_id": "abc123", "camera_index": 0 }` |

### Images

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/images` | List all images (query: `?sample_id=...&skip=0&limit=50`) |
| `GET` | `/api/v1/samples/{id}/images` | Images for a specific sample |
| `GET` | `/api/v1/images/{id}/file` | Download full image |
| `GET` | `/api/v1/images/{id}/thumbnail` | Download thumbnail |

### Cameras

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/cameras` | List connected cameras |
| `GET` | `/api/v1/cameras/{index}/status` | Camera details |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service + DB status (no auth needed) |

---

## TypeScript Types

Copy `generated/icast-cv-api.ts` from this repo into your frontend project. It gives you:

```ts
import type { SampleResponse, SampleCreate, ImageResponse, CaptureRequest } from "@/types/icast-cv-api";
import { API_PATHS } from "@/types/icast-cv-api";

// Type-safe API calls
const res = await fetch(`${API_URL}${API_PATHS.samples}`);
const samples: SampleResponse[] = await res.json();

// Create a sample
const newSample: SampleCreate = { name: "My Sample", tags: ["urgent"] };
await fetch(`${API_URL}${API_PATHS.samples}`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": key },
  body: JSON.stringify(newSample),
});

// Get images for a sample
const imgRes = await fetch(`${API_URL}${API_PATHS.sampleImages(sampleId)}`);
const images: ImageResponse[] = await imgRes.json();
```

---

## Example: Full Workflow

```ts
// 1. Create a sample
const sampleRes = await fetch(`${API_URL}/api/v1/samples`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": key },
  body: JSON.stringify({ name: "Protein Assay Batch 7", project: "Experiment-42", tags: ["protein", "batch-7"] }),
});
const sample = await sampleRes.json();
// sample.id = "507f1f77bcf86cd799439011"

// 2. Capture an image for that sample
const captureRes = await fetch(`${API_URL}/api/v1/capture`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": key },
  body: JSON.stringify({ sample_id: sample.id, camera_index: 0 }),
});
const image = await captureRes.json();
// image.id, image.filename, image.width, image.height

// 3. Display the thumbnail
const thumbnailUrl = `${API_URL}/api/v1/images/${image.id}/thumbnail`;
// Use in an <img> tag: <img src={thumbnailUrl} />

// 4. Display the full image
const fullUrl = `${API_URL}/api/v1/images/${image.id}/file`;
```

---

## Response Shapes

### SampleResponse
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "Sample ABC-123",
  "description": "Protein assay sample batch 7",
  "project": "Experiment-42",
  "tags": ["batch-7", "protein"],
  "metadata": {},
  "created_at": "2026-03-03T10:30:00Z",
  "updated_at": "2026-03-03T10:30:00Z"
}
```

### ImageResponse
```json
{
  "id": "507f1f77bcf86cd799439012",
  "sample_id": "507f1f77bcf86cd799439011",
  "filename": "20260303T103000_a1b2c3.jpg",
  "file_path": "507f1f77bcf86cd799439011/20260303T103000_a1b2c3.jpg",
  "thumbnail_path": "507f1f77bcf86cd799439011/thumbs/20260303T103000_a1b2c3.jpg",
  "width": 1920,
  "height": 1080,
  "file_size_bytes": 245760,
  "camera_index": 0,
  "metadata": {},
  "captured_at": "2026-03-03T10:30:00Z"
}
```

---

## Deploying the API

The API repo is at: `https://github.com/avacoder3900/I_cast_computa_vision`

**Railway (recommended):**
1. Go to [railway.app](https://railway.app), sign in with GitHub
2. New Project → Deploy from GitHub Repo → select `I_cast_computa_vision`
3. Railway detects the Dockerfile and deploys automatically
4. Add environment variables in Railway dashboard:
   - `MONGODB_URI` = your MongoDB Atlas connection string
   - `MONGODB_DATABASE` = `icast_cv`
   - `API_KEY` = `PgJXWr3i6r5p2nBPh0SLn2GNNyu9i0XO128ZL0THn98`
   - `CORS_ORIGINS` = `https://bioscale-operations-system-mongodb.vercel.app`
   - `IMAGE_STORAGE_PATH` = `data/images`
5. Railway gives you a public URL — use that as `NEXT_PUBLIC_ICAST_API_URL` in Vercel

---

## Error Handling

All errors return JSON:
```json
{ "detail": "Sample 507f1f77bcf86cd799439011 not found" }
```

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 201 | Created (POST) |
| 204 | Deleted (DELETE) |
| 401 | Bad or missing API key |
| 404 | Resource not found |
| 422 | Validation error (bad request body) |
| 502 | Camera error (hardware issue) |
