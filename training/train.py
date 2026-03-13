#!/usr/bin/env python3
"""Train an Anomalib PatchCore model for defect detection."""

from __future__ import annotations

from pathlib import Path

import yaml
from anomalib.data import Folder
from anomalib.engine import Engine
from anomalib.models import Patchcore


def main(config_path: str = "config.yaml") -> None:
    cfg = yaml.safe_load(Path(config_path).read_text())

    model_cfg = cfg["model"]
    dataset_cfg = cfg["dataset"]
    trainer_cfg = cfg["trainer"]

    # Build datamodule
    datamodule = Folder(
        name="icast_cv",
        root=dataset_cfg["root"],
        normal_dir=dataset_cfg["normal_dir"],
        abnormal_dir=dataset_cfg.get("abnormal_dir", "defect"),
        image_size=dataset_cfg["image_size"],
        train_batch_size=dataset_cfg["train_batch_size"],
        eval_batch_size=dataset_cfg["test_batch_size"],
        num_workers=dataset_cfg["num_workers"],
    )

    # Build model
    model = Patchcore(
        backbone=model_cfg["backbone"],
        layers=model_cfg["layers"],
        coreset_sampling_ratio=model_cfg["coreset_sampling_ratio"],
        num_neighbors=model_cfg["num_neighbors"],
    )

    # Train
    engine = Engine(
        max_epochs=trainer_cfg["max_epochs"],
        accelerator=trainer_cfg["accelerator"],
        devices=trainer_cfg["devices"],
        default_root_dir="./results",
    )
    engine.fit(model=model, datamodule=datamodule)

    print(f"\nTraining complete. Results saved to ./results/")
    print("Run `python export_onnx.py` to export to ONNX format.")


if __name__ == "__main__":
    main()
