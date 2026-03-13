# Anomalib Model Training

Train anomaly detection models for the ICast CV inspection pipeline.

## Prerequisites

```bash
pip install -r requirements.txt
```

## Data Structure

```
training/data/
├── good/          # Normal / passing samples (required)
│   ├── img001.jpg
│   └── ...
└── defect/        # Defective / failing samples (optional for anomaly detection)
    ├── img001.jpg
    └── ...
```

- **good/**: Place all known-good sample images here. These are used as the
  reference distribution for anomaly detection.
- **defect/**: Optionally place defective sample images here. PatchCore can
  train with only good samples (unsupervised), but defect images improve
  evaluation metrics.

## Collecting Training Data

1. Use the ICast CV API to capture images of samples via
   `POST /api/v1/capture`.
2. Download images from R2 or copy from `data/images/` on the server.
3. Sort images into `training/data/good/` and `training/data/defect/`.
4. Aim for **50+ good images** minimum; more is better.

## Training

```bash
cd training
python train.py
```

This runs Anomalib's PatchCore model with settings from `config.yaml`.
The trained model checkpoint is saved to `training/results/`.

## Export to ONNX

After training, export the model for the inference worker:

```bash
python export_onnx.py
```

This produces `model.onnx` in the repo root (or the path configured in
`config.yaml`). Copy the ONNX file to where the worker can access it
(set `MODEL_PATH` env var).

## Configuration

Edit `config.yaml` to adjust:

- **model**: PatchCore backbone, layer selection, coreset sampling ratio
- **dataset**: Image size, train/test split
- **export**: ONNX output path
