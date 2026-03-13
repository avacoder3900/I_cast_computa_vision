"""Tests for CV inference worker components."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from icast_cv.worker.preprocessor import preprocess


def test_preprocess_output_shape() -> None:
    """preprocess returns NCHW tensor with correct shape."""
    img = Image.fromarray(np.zeros((100, 150, 3), dtype=np.uint8))
    tensor = preprocess(img, input_size=(224, 224))
    assert tensor.shape == (1, 3, 224, 224)
    assert tensor.dtype == np.float32


def test_preprocess_normalizes() -> None:
    """preprocess normalizes pixel values to [0, 1]."""
    img = Image.fromarray(np.full((50, 50, 3), 255, dtype=np.uint8))
    tensor = preprocess(img, input_size=(32, 32))
    assert tensor.max() <= 1.0
    assert tensor.min() >= 0.0


def test_model_loader_missing_file() -> None:
    """load_model raises FileNotFoundError for missing model."""
    from icast_cv.worker.model_loader import load_model

    with pytest.raises(FileNotFoundError, match="Model not found"):
        load_model("/nonexistent/model.onnx")


def test_run_inference_mock() -> None:
    """run_inference returns score and boolean from mocked session."""
    from icast_cv.worker.model_loader import run_inference

    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "input"
    mock_session.get_inputs.return_value = [mock_input]
    mock_session.run.return_value = [np.array([0.75])]

    score, is_anomaly = run_inference(mock_session, np.zeros((1, 3, 224, 224)))
    assert score == pytest.approx(0.75)
    assert is_anomaly is True


def test_run_inference_below_threshold() -> None:
    """run_inference returns is_anomaly=False for low score."""
    from icast_cv.worker.model_loader import run_inference

    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "input"
    mock_session.get_inputs.return_value = [mock_input]
    mock_session.run.return_value = [np.array([0.3])]

    score, is_anomaly = run_inference(mock_session, np.zeros((1, 3, 224, 224)))
    assert score == pytest.approx(0.3)
    assert is_anomaly is False
