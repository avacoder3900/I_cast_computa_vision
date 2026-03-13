"""ONNX model loader for CV inference."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_model(model_path: str | Path) -> Any:
    """Load an ONNX model from *model_path* and return an InferenceSession.

    Raises ``FileNotFoundError`` if the model file does not exist.
    """
    import onnxruntime as ort

    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"Model not found: {path}")
    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


def run_inference(session: Any, input_tensor: Any) -> tuple[float, bool]:
    """Run a forward pass and return ``(anomaly_score, is_anomaly)``.

    Expects the model to produce a single output whose first element is
    the anomaly / defect score (higher = more anomalous).  The boolean
    ``is_anomaly`` is ``True`` when the score exceeds 0.5 (the caller
    should use the configurable threshold instead of this default).
    """
    input_name: str = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: input_tensor})
    score: float = float(outputs[0].flat[0])
    return score, score > 0.5
