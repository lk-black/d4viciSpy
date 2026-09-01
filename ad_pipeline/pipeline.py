"""Orquestrador principal. Junta collector + scorer + heuristic + storage num único fluxo.

Fluxo por anúncio coletado:
    1. Salva o dado bruto sempre (mesmo que já tenha sido processado antes).
    2. Se já foi processado num ciclo anterior, para aqui (evita reprocessar).
    3. Calcula o score de escala (dias ativo + impressões).
    4. Roda a heurística barata de marca grande.
    5. Salva o resultado processado.

A etapa de LLM (classificação fina de pessoa vs. empresa, análise de gancho/oferta)
ainda não está aqui — `top_candidates()` é o ponto de entrada pensado para
alimentar essa próxima etapa, retornando só os candidatos não descartados
pela heurística, ordenados por score.
"""
from __future__ import annotations

import json
import random
from typing import Any, Optional

from .collector import AdCollectorService
from .config import PipelineConfig, flatten_keywords, load_niche_groups
from .creative import CreativeExtractor
from .heuristics import BrandHeuristic, BrandHeuristicConfig
from .models import ScoredAd
from .scoring import ScaleScorer
from .storage import Storage


class Pipeline:
    def __init__(self, config: PipelineConfig, brand_config: Optional[BrandHeuristicConfig] = None):
        self.config = config
        self.storage = Storage(config.db_path)
        self.collector = AdCollectorService(config)
        self.scorer = ScaleScorer(config.scoring)
        self.heuristic = BrandHeuristic(brand_config or BrandHeuristicConfig())
        self.niche_groups = load_niche_groups(config.niches_file)

    def run_cycle(self) -> None:
        """Um ciclo completo: passa por todos os nichos do niches.yaml, em ordem embaralhada."""
        pairs = flatten_keywords(self.niche_groups)
        random.shuffle(pairs)

        for keyword, group_name in pairs:
            self.run_niche(keyword, group_name)
            self.collector.pause_between_niches()

    def run_niche(self, keyword: str, group_name: str) -> int:
        """Coleta + processa um único nicho/keyword. Retorna quantos anúncios foram vistos.

        Público de propósito: é o que permite testar rápido (`--niche`) sem
        esperar o ciclo completo com pausas entre 40+ nichos.
        """
        count = 0
        for ad in self.collector.collect_niche(keyword):
            self._process_ad(ad, niche=group_name)
            count += 1
        return count

    def _process_ad(self, ad: Any, niche: str) -> None:
        page = getattr(ad, "page", None)
        creative = CreativeExtractor.extract(ad)

        self.storage.save_raw(
            ad_id=ad.id,
            niche=niche,
            page_name=getattr(page, "name", None) if page else None,
            page_id=getattr(page, "id", None) if page else None,
            delivery_start=ad.delivery_start_time.isoformat() if ad.delivery_start_time else None,
            impressions_lower=self.scorer.impressions_lower(ad),
            raw_json=json.dumps(getattr(ad, "raw_data", None) or {}),
            creative_body=creative.body,
            creative_image_url=creative.image_url,
            creative_video_url=creative.video_url,
            snapshot_url=creative.snapshot_url,
        )

        if self.storage.already_processed(ad.id):
            return

        score = self.scorer.score(ad)
        days = self.scorer.days_active(ad)
        is_big_brand, reason = self.heuristic.classify(ad)

        scored = ScoredAd(
            ad_id=ad.id,
            page_name=getattr(page, "name", "") if page else "",
            page_id=getattr(page, "id", None) if page else None,
            niche=niche,
            delivery_start=ad.delivery_start_time,
            days_active=days,
            impressions_lower=self.scorer.impressions_lower(ad),
            scale_score=score,
            is_likely_big_brand=is_big_brand,
            brand_reason=reason,
            raw=ad,
        )
        self.storage.save_scored(scored)

    def top_candidates(self, niche: Optional[str] = None, limit: int = 30):
        """Melhores candidatos por score, excluindo os já marcados como marca grande.

        Este é o ponto de entrada pensado para alimentar a próxima etapa (LLM).
        """
        rows = self.storage.top_scored(niche=niche, limit=limit)
        return [row for row in rows if row["is_likely_big_brand"] != 1]
