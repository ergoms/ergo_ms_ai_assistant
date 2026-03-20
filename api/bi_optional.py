"""
Опциональные модели BI. Модуль Chart удалён из bi_charts (миграция 0004_delete_chart);
оставляем попытку импорта на случай возврата модели в будущем.
"""

from __future__ import annotations

try:
    from modules.bi_analysis_modern.api.bi_datasets.models import FileUpload
except ImportError:
    FileUpload = None

Chart = None
try:
    from modules.bi_analysis_modern.api.bi_charts import models as _bi_charts_models  # type: ignore

    Chart = getattr(_bi_charts_models, "Chart", None)
except ImportError:
    pass

_BI_AVAILABLE = FileUpload is not None
