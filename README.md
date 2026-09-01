# ad_pipeline

Pipeline pessoal de coleta e triagem de anúncios da Meta Ad Library, focado em
identificar ofertas de pessoas físicas (não marcas grandes) com sinais de escala.

## Instalação

```bash
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

Isso roda um ciclo completo:

```
niches.yaml (wordlist por categoria)
    -> AdCollectorService.collect_niche()   # coleta via meta-ads-collector
    -> Storage.save_raw()                   # persiste sempre, mesmo sem processar
    -> ScaleScorer.score()                  # dias ativo + impressões -> score
    -> BrandHeuristic.classify()            # True = descarta / None = ambíguo
    -> Storage.save_scored()                # grava resultado processado
    -> Pipeline.top_candidates()            # melhores candidatos, marcas já fora
```

## Estrutura

| Módulo | Responsabilidade |
|---|---|
| `config.py` | `PipelineConfig`, pesos de score, carregamento do `niches.yaml` |
| `collector.py` | Wrapper sobre `meta_ads_collector`, dedup e pacing entre nichos |
| `scoring.py` | `ScaleScorer` — combina dias ativo + impressões num score |
| `heuristics.py` | `BrandHeuristic` — triagem barata de marca grande vs. ambíguo |
| `storage.py` | `Storage` — SQLite (tabelas `raw_ads` e `scored_ads`) |
| `models.py` | `ScoredAd` — objeto de domínio interno |
| `pipeline.py` | `Pipeline` — orquestra tudo acima |

## Próximos passos (não implementados ainda)

- Etapa de LLM sobre `pipeline.top_candidates()`: decidir os casos ambíguos
  (`is_likely_big_brand is None`) e extrair gancho/ângulo/oferta de cada anúncio.
- Preencher `BrandHeuristicConfig.known_big_brands` com uma blacklist real.
- Camada de "View" (dashboard ou export) sobre a tabela `scored_ads`.

## Configuração

Edite `niches.yaml` para adicionar/remover nichos sem tocar no código. Ajuste
pesos de score e parâmetros de coleta via `PipelineConfig` (ou crie um
`config.yaml` e use `PipelineConfig.from_yaml(...)`).
