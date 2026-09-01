"""Configuração do pipeline: nichos, pesos de score, parâmetros de coleta."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

import yaml


@dataclass
class NicheGroup:
    """Uma categoria de nichos, ex.: 'ia_generativa', 'espiritualidade'."""
    name: str
    keywords: list[str]


@dataclass
class ScoringWeights:
    """Pesos usados pelo ScaleScorer para combinar sinais em um único score.

    days_active e impressions são combinados como:
        score = (dias_ativo * days_active) + (impressoes / impressions_scale * impressions)
    """
    days_active: float = 0.6
    impressions: float = 0.4
    impressions_scale: float = 10_000.0  # divisor para normalizar impressões


@dataclass
class PipelineConfig:
    country: str = "BR"
    min_impressions: int = 10_000
    max_results_per_niche: int = 100
    top_n_per_niche_for_llm: int = 30
    rate_limit_delay: float = 3.0
    jitter: float = 1.5
    pause_between_niches_range: Tuple[float, float] = (20.0, 45.0)
    db_path: str = "state/ads.db"
    dedup_db_path: str = "state/dedup.db"
    niches_file: str = "niches.yaml"
    scoring: ScoringWeights = field(default_factory=ScoringWeights)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PipelineConfig":
        """Carrega config a partir de um YAML. Campos ausentes usam o default da dataclass."""
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        scoring_data = data.pop("scoring", {})
        return cls(scoring=ScoringWeights(**scoring_data), **data)


def load_niche_groups(path: str | Path) -> list[NicheGroup]:
    """Carrega os grupos de nicho + keywords a partir de um arquivo YAML."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    groups = data.get("niche_groups", {})
    return [NicheGroup(name=name, keywords=keywords) for name, keywords in groups.items()]


def flatten_keywords(groups: list[NicheGroup]) -> list[Tuple[str, str]]:
    """Retorna pares (keyword, nome_do_grupo), achatados através de todos os grupos.

    Mantemos o nome do grupo junto da keyword para já taggear a origem do anúncio
    no momento da coleta, sem precisar reclassificar o nicho depois.
    """
    pairs: list[Tuple[str, str]] = []
    for group in groups:
        for kw in group.keywords:
            pairs.append((kw, group.name))
    return pairs
