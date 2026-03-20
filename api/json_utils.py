"""JSON helpers safe for numpy/pandas values (NaN, inf)."""

from __future__ import annotations

import json
import logging
import math
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def sanitize_for_json(obj: Any) -> Any:
    """
    Рекурсивно очищает объект от значений, которые не поддерживаются JSON.
    NaN, Infinity, -Infinity заменяются на None.
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="ignore")

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    if isinstance(obj, (np.floating, np.integer)):
        if isinstance(obj, np.floating):
            val = float(obj)
            if math.isnan(val) or math.isinf(val):
                return None
            return val
        return int(obj)

    if isinstance(obj, np.ndarray):
        return [sanitize_for_json(item) for item in obj.tolist()]

    if isinstance(obj, pd.Series):
        return [sanitize_for_json(item) for item in obj.tolist()]

    if isinstance(obj, pd.DataFrame):
        return obj.replace({np.nan: None, pd.NA: None}).to_dict(orient="records")

    try:
        if not isinstance(obj, (list, tuple, dict, np.ndarray, pd.Series, pd.DataFrame)):
            if pd.isna(obj):
                return None
    except (TypeError, ValueError):
        pass

    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]

    try:
        return str(obj)
    except Exception:
        logger.debug("sanitize_for_json: could not stringify %r", type(obj))
        return None


def safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """Безопасная JSON сериализация с обработкой NaN/Infinity."""
    default_kwargs = {
        "ensure_ascii": False,
        "separators": (",", ":"),
        "check_circular": False,
    }
    default_kwargs.update(kwargs)
    return json.dumps(sanitize_for_json(obj), **default_kwargs)


# Backwards compatibility for older imports
_sanitize_for_json = sanitize_for_json
_safe_json_dumps = safe_json_dumps
