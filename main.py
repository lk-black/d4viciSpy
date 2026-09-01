"""Ponto de entrada. Roda o pipeline e mostra os resultados na CLI e/ou como
relatório HTML (com os criativos — vídeo/imagem — embutidos).

Exemplos:
    # teste rápido, um nicho só, sem esperar pausas entre nichos
    python main.py --niche "renda extra em casa" --group renda_extra

    # ciclo completo (todos os nichos do niches.yaml, com pausas entre eles)
    python main.py --full

    # gera relatório HTML visual em vez de (ou além de) mostrar tabela na CLI
    python main.py --niche "tarot online" --group espiritualidade --report --open

    # relatório do que já está no banco, sem coletar de novo
    python main.py --report-only --report --open --top 30
"""
from __future__ import annotations

import argparse
import logging
import webbrowser
from pathlib import Path

from ad_pipeline import HtmlReportGenerator, Pipeline, PipelineConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ad Pipeline - coleta e triagem de anúncios da Meta Ad Library")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--niche", metavar="KEYWORD",
        help="Teste rápido: roda só essa keyword, sem pausas entre nichos.",
    )
    mode.add_argument(
        "--full", action="store_true",
        help="Roda o ciclo completo: todos os nichos do niches.yaml, com pausas entre eles.",
    )
    mode.add_argument(
        "--report-only", action="store_true",
        help="Não coleta nada novo — só gera a visualização do que já está no banco.",
    )

    parser.add_argument("--group", default="teste", help="Nome do grupo/nicho para taggear os anúncios coletados com --niche.")
    parser.add_argument("--max-results", type=int, default=None, help="Sobrescreve max_results_per_niche.")
    parser.add_argument("--top", type=int, default=20, help="Quantos anúncios mostrar/incluir no relatório.")
    parser.add_argument("--show-niche", default=None, help="Filtra a listagem/relatório por um nicho específico.")
    parser.add_argument("--verbose", action="store_true", help="Log em nível DEBUG.")

    parser.add_argument("--report", action="store_true", help="Gera relatório HTML com os criativos (vídeo/imagem).")
    parser.add_argument("--report-path", default="report.html", help="Caminho do arquivo HTML gerado (default: report.html).")
    parser.add_argument("--open", action="store_true", help="Abre o relatório no navegador automaticamente após gerar.")
    parser.add_argument("--no-table", action="store_true", help="Não imprime a tabela na CLI (útil junto com --report).")

    return parser.parse_args()


def print_candidates(rows, title: str) -> None:
    print(f"\n--- {title} ---")
    if not rows:
        print("(nenhum candidato ainda — rode uma coleta primeiro)")
        return
    print(f"{'NICHO':<18} {'SCORE':>8} {'DIAS':>6}  {'PÁGINA':<28} AD_ID")
    print("-" * 90)
    for row in rows:
        print(
            f"{row['niche']:<18} {row['scale_score']:>8.1f} {row['days_active']:>6}  "
            f"{(row['page_name'] or '')[:28]:<28} {row['ad_id']}"
        )


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    config = PipelineConfig()
    if args.max_results:
        config.max_results_per_niche = args.max_results

    pipeline = Pipeline(config)

    if args.niche:
        print(f"Rodando teste rápido para: '{args.niche}' (grupo: {args.group})")
        count = pipeline.run_niche(args.niche, args.group)
        print(f"{count} anúncios coletados/atualizados.")
    elif args.full:
        print("Rodando ciclo completo (todos os nichos do niches.yaml)...")
        pipeline.run_cycle()
    else:
        print("Gerando visualização do que já está no banco (sem coletar nada novo)...")

    if not args.no_table:
        candidatos = pipeline.top_candidates(niche=args.show_niche, limit=args.top)
        print_candidates(candidatos, "Top candidatos (marcas grandes já excluídas pela heurística)")

    if args.report:
        generator = HtmlReportGenerator(pipeline.storage)
        path = generator.build(niche=args.show_niche, limit=args.top, output_path=args.report_path)
        full_path = Path(path).resolve()
        print(f"\nRelatório gerado em: {full_path}")
        if args.open:
            webbrowser.open(f"file://{full_path}")


if __name__ == "__main__":
    main()
