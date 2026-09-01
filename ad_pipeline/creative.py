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
        """Extrai o melhor criativo disponível do anúncio.

        Um Ad pode ter vários testes de criativo (carrossel etc.). Escolhemos o
        primeiro que tiver mídia (vídeo ou imagem); se nenhum tiver, usamos o
        primeiro da lista mesmo, para ao menos capturar o texto do body.
        """
        creatives = getattr(ad, "creatives", None) or []
        first = creatives[0] if creatives else None

        if creatives:
            best = next(
                (c for c in creatives if getattr(c, "video_url", None)),
                None,
            ) or next(
                (c for c in creatives if getattr(c, "image_url", None)),
                None,
            ) or first
        else:
            best = None

        snapshot_url = (
            getattr(ad, "ad_snapshot_url", None)
            or getattr(ad, "snapshot_url", None)
        )
        if not snapshot_url and getattr(ad, "id", None):
            # A API da Ad Library não manda o snapshot_url; ele segue esse padrão
            # fixo a partir do ad_id.
            snapshot_url = f"https://www.facebook.com/ads/library/?id={ad.id}"

        return CreativeInfo(
            body=(getattr(best, "body", "") or "") if best else "",
            image_url=getattr(best, "image_url", None) if best else None,
            video_url=getattr(best, "video_url", None) if best else None,
            snapshot_url=snapshot_url,
        )
