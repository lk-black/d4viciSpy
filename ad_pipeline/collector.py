"""Camada de coleta: encapsula a MetaAdsCollector com nossos defaults de pacing/dedup.

Mantida separada do resto do pipeline para que, se um dia trocarmos a lib de
coleta, só esse módulo precise mudar.
"""
from __future__ import annotations

import random
import time
from typing import Any, Iterator

from meta_ads_collector import DeduplicationTracker, FilterConfig, MetaAdsCollector

from .config import PipelineConfig


class AdCollectorService:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._tracker = DeduplicationTracker(mode="persistent", db_path=config.dedup_db_path)
        self._filters = FilterConfig(min_impressions=config.min_impressions)

    def collect_niche(self, keyword: str) -> Iterator[Any]:
        """Coleta anúncios ativos para uma keyword, ordenados por impressões (maiores primeiro).

        Note: não filtramos por data de início aqui de propósito — isso é
        decidido depois, via ScaleScorer, para não descartar ofertas novas
        que já estão validando rápido.
        """
        with MetaAdsCollector(
            rate_limit_delay=self.config.rate_limit_delay,
            jitter=self.config.jitter,
        ) as collector:
            yield from collector.search(
                query=keyword,
                country=self.config.country,
                status="ACTIVE",
                ad_type="ALL",
                sort_by="SORT_BY_TOTAL_IMPRESSIONS",
                filter_config=self._filters,
                dedup_tracker=self._tracker,
                max_results=self.config.max_results_per_niche,
            )

    def pause_between_niches(self) -> None:
        """Pausa aleatória entre nichos, para não bater tudo em rajada única."""
        low, high = self.config.pause_between_niches_range
        time.sleep(random.uniform(low, high))
