"""Heurística de triagem: 'isso parece marca grande, ou vale mandar pro LLM?'

Não tenta ser perfeita — o objetivo é eliminar os casos óbvios (selo verificado,
seguidores muito acima do normal para pessoa física, funding_entity batendo com
uma blacklist conhecida) de graça, sem gastar chamada de modelo. Tudo que não
bate com nenhuma regra clara volta como ambíguo (None) para a próxima etapa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple


@dataclass
class BrandHeuristicConfig:
    max_followers_individual: int = 200_000
    # nomes/trechos de razão social conhecidos — preencha com sua blacklist
    known_big_brands: set[str] = field(default_factory=set)


class BrandHeuristic:
    def __init__(self, config: BrandHeuristicConfig):
        self.config = config

    def classify(self, ad: Any) -> Tuple[Optional[bool], str]:
        """Retorna (is_provavel_marca_grande, motivo).

        is_provavel_marca_grande:
            True  -> provavelmente marca grande, pode ser descartado sem LLM
            None  -> ambíguo, mandar para o LLM decidir
        (nunca retornamos False aqui de propósito — "provavelmente pessoa" é uma
        decisão que preferimos deixar para o LLM, que olha o conteúdo do anúncio)
        """
        page = getattr(ad, "page", None)
        funding_entity = (getattr(ad, "funding_entity", "") or "").strip().lower()

        if funding_entity and any(
            brand in funding_entity for brand in self.config.known_big_brands
        ):
            return True, f"funding_entity bate com blacklist: '{funding_entity}'"

        if page is not None:
            if getattr(page, "verified", False):
                return True, "página com selo verificado"

            likes = getattr(page, "likes", None)
            if likes is not None and likes > self.config.max_followers_individual:
                return True, f"seguidores acima do limite ({likes} > {self.config.max_followers_individual})"

        return None, "sinais insuficientes — ambíguo, mandar para LLM"
