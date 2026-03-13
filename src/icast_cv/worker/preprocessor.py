"""Image preprocessing for CV inference."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    import numpy.typing as npt


def preprocess(
    image: Image.Image,
    input_size: tuple[int, int] = (224, 224),
) -> npt.NDArray[np.float32]:
    """Resize, normalize, and convert an image to a model-ready tensor.

    Returns an NCHW float32 array with shape ``(1, 3, H, W)``,
    pixel values normalized to ``[0, 1]``.
    """
    resized = image.resize(input_size, Image.Resampling.BILINEAR).convert("RGB")
    arr: npt.NDArray[np.float32] = np.asarray(resized, dtype=np.float32) / 255.0
    # HWC -> CHW -> NCHW
    arr = np.transpose(arr, (2, 0, 1))
    return np.expand_dims(arr, axis=0)
