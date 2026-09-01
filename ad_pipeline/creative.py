"""Extração dos dados de criativo do Ad bruto — separado do resto porque é a
parte mais acoplada ao formato específico da lib meta_ads_collector. Se o
formato do objeto Ad mudar numa versão futura da lib, só este módulo muda.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CreativeInfo:
    body: str = ""
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    snapshot_url: Optional[str] = None


class CreativeExtractor:
    @staticmethod
    def extract(ad: Any) -> CreativeInfo:
        """Usa o primeiro criativo do anúncio (um Ad pode ter mais de um teste
        de criativo — para exibição inicial, o primeiro já basta)."""
        creatives = getattr(ad, "creatives", None) or []
        first = creatives[0] if creatives else None

        return CreativeInfo(
            body=(getattr(first, "body", "") or "") if first else "",
            image_url=getattr(first, "image_url", None) if first else None,
            video_url=getattr(first, "video_url", None) if first else None,
            snapshot_url=getattr(ad, "ad_snapshot_url", None) or getattr(ad, "snapshot_url", None),
        )
