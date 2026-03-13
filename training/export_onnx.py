#!/usr/bin/env python3
"""Export a trained Anomalib model to ONNX format."""

from __future__ import annotations

import glob
from pathlib import Path

import yaml
from anomalib.deploy import ExportMode
from anomalib.engine import Engine
from anomalib.models import Patchcore


def find_best_checkpoint(results_dir: str = "./results") -> Path:
    """Find the best model checkpoint in the results directory."""
    patterns = [
        f"{results_dir}/**/best*.ckpt",
        f"{results_dir}/**/*.ckpt",
    ]
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return Path(matches[0])
    raise FileNotFoundError(
        f"No checkpoint found in {results_dir}. Run train.py first."
    )


def main(config_path: str = "config.yaml") -> None:
    cfg = yaml.safe_load(Path(config_path).read_text())
    export_cfg = cfg.get("export", {})
    onnx_path = Path(export_cfg.get("onnx_path", "../model.onnx"))

    checkpoint = find_best_checkpoint()
    print(f"Loading checkpoint: {checkpoint}")

    model = Patchcore.load_from_checkpoint(str(checkpoint))
    engine = Engine()
    engine.export(
        model=model,
        export_mode=ExportMode.ONNX,
        export_root=str(onnx_path.parent),
    )

    print(f"\nONNX model exported to: {onnx_path}")
    print(f"Set MODEL_PATH={onnx_path.resolve()} in your .env")


if __name__ == "__main__":
    main()
