"""Modelos de domínio internos do pipeline (não confundir com o Ad da lib meta_ads_collector)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class ScoredAd:
    """Um anúncio depois de passar por score de escala + heurística de marca.

    `raw` guarda o objeto Ad original da lib, útil se for preciso reenriquecer
    ou baixar mídia depois sem re-coletar.
    """
    ad_id: str
    page_name: str
    page_id: Optional[str]
    niche: str
    delivery_start: Optional[datetime]
    days_active: int
    impressions_lower: int
    scale_score: float
    is_likely_big_brand: Optional[bool] = None  # None = ambíguo, ainda não decidido
    brand_reason: str = ""
    llm_classification: Optional[str] = None
    raw: Any = None
