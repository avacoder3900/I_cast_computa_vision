// Auto-generated from OpenAPI spec — do not edit manually
// Generated from: ICast Computer Vision API v0.1.0

export interface CaptureRequest {
  sample_id: string;
  camera_index?: number;
  metadata?: Record<string, unknown>;
}

export interface HTTPValidationError {
  detail?: Array<ValidationError>;
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
  captured_at: string;
}

export interface SampleCreate {
  name: string;
  description?: string;
  project?: string;
  tags?: Array<string>;
  metadata?: Record<string, unknown>;
}

export interface SampleResponse {
  id: string;
  name: string;
  description: string;
  project: string;
  tags: Array<string>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SampleUpdate {
  name?: string | null;
  description?: string | null;
  project?: string | null;
  tags?: Array<string> | null;
  metadata?: Record<string, unknown> | null;
}

export interface ValidationError {
  loc: Array<string | number>;
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

// API endpoint paths
export const API_PATHS = {
  health: '/health',
  samples: '/api/v1/samples',
  sample: (id: string) => `/api/v1/samples/${id}`,
  sampleImages: (id: string) => `/api/v1/samples/${id}/images`,
  images: '/api/v1/images',
  imageFile: (id: string) => `/api/v1/images/${id}/file`,
  imageThumbnail: (id: string) => `/api/v1/images/${id}/thumbnail`,
  capture: '/api/v1/capture',
  cameras: '/api/v1/cameras',
  cameraStatus: (index: number) => `/api/v1/cameras/${index}/status`,
} as const;
