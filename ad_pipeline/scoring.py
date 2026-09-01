"""Score de escala. Combina tempo de vida do anúncio + volume de impressões.

Propositalmente NÃO filtra por dias ativos (isso eliminaria ofertas novas que
validam rápido com spend alto desde o dia 1) — só usa como critério de
priorização/ordenação para decidir o que entra na fila do LLM primeiro.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import ScoringWeights


class ScaleScorer:
    def __init__(self, weights: ScoringWeights):
        self.weights = weights

    @staticmethod
    def days_active(ad: Any) -> int:
        start = getattr(ad, "delivery_start_time", None)
        if not start:
            return 0
        now = datetime.now(start.tzinfo) if start.tzinfo else datetime.now()
        return max((now - start).days, 0)

    @staticmethod
    def impressions_lower(ad: Any) -> int:
        impressions = getattr(ad, "impressions", None)
        lower = getattr(impressions, "lower_bound", None) if impressions else None
        return lower or 0

    def score(self, ad: Any) -> float:
        days = self.days_active(ad)
        impressions = self.impressions_lower(ad)
        return (days * self.weights.days_active) + (
            impressions / self.weights.impressions_scale * self.weights.impressions
        )
