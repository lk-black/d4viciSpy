"""CLI de consulta dos dados coletados/pontuados pelo pipeline (SQLite).

Exemplos:
    # Top candidatos (100% dos campos scored, incluindo page_name do raw):
    .venv\\Scripts\\python.exe cli.py top --niche renda_extra --limit 20

    # Só os ambíguos (não descartados como marca grande), ou seja, os que
    # alimentariam a etapa de LLM:
    .venv\\Scripts\\python.exe cli.py top --ambigous-only

    # Dump da tabela bruta raw_ads:
    .venv\\Scripts\\python.exe cli.py raw --niche renda_extra

    # Estatísticas por nicho (contagem, score médio/máx, marcas descartadas):
    .venv\\Scripts\\python.exe cli.py stats
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from ad_pipeline.storage import Storage


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def cmd_top(args: argparse.Namespace, storage: Storage) -> None:
    rows = storage.top_scored(niche=args.niche, limit=args.limit)
    if args.ambigous_only:
        rows = [r for r in rows if r["is_likely_big_brand"] != 1]

    if not rows:
        print("Nenhum registro encontrado.")
        return

    cols = args.columns.split(",") if args.columns else (
        "niche", "page_name", "scale_score", "days_active", "impressions_lower",
        "is_likely_big_brand", "brand_reason", "ad_id",
    )
    header = "\t".join(cols)
    print(header)
    print("-" * max(len(header), 20))
    for r in rows:
        print("\t".join(str(r[c] if c in r.keys() else "") for c in cols))


def cmd_raw(args: argparse.Namespace, storage: Storage) -> None:
    with _connect(storage.db_path) as conn:
        q = "SELECT * FROM raw_ads"
        params: tuple = ()
        if args.niche:
            q += " WHERE niche = ?"
            params = (args.niche,)
        q += " ORDER BY impressions_lower DESC LIMIT ?"
        rows = conn.execute(q, params + (args.limit,)).fetchall()

    if not rows:
        print("Nenhum registro encontrado.")
        return

    if args.format == "json":
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
        return

    for r in rows:
        print(
            f"[{r['niche']}] {r['ad_id']}  impr={r['impressions_lower']}  "
            f"start={r['delivery_start']}  page={r['page_name']}"
        )


def cmd_stats(args: argparse.Namespace, storage: Storage) -> None:
    with _connect(storage.db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.niche,
                   COUNT(*)                     AS total,
                   ROUND(AVG(s.scale_score), 1) AS score_medio,
                   ROUND(MAX(s.scale_score), 1) AS score_max,
                   SUM(CASE WHEN s.is_likely_big_brand = 1 THEN 1 ELSE 0 END) AS marcas,
                   SUM(CASE WHEN s.is_likely_big_brand IS NULL THEN 1 ELSE 0 END) AS ambigous
            FROM scored_ads s
            GROUP BY s.niche
            ORDER BY score_max DESC
            """
        ).fetchall()

    if not rows:
        print("Nenhum registro encontrado.")
        return

    print("niche\t\ttotal\tscore_medio\tscore_max\tmarcas\tambigous")
    print("-" * 60)
    for r in rows:
        print(
            f"{r['niche']:<18}{r['total']}   {r['score_medio']:<12}"
            f"{r['score_max']:<11}{r['marcas']}   {r['ambigous']}"
        )


def main() -> None:
    default_db = str(Path("state/ads.db"))
    parser = argparse.ArgumentParser(
        prog="cli.py", description="Consulta os dados do pipeline (SQLite)."
    )
    parser.add_argument("--db", default=default_db, help=f"caminho do SQLite (default: {default_db})")
    sub = parser.add_subparsers(dest="command", required=True)

    p_top = sub.add_parser("top", help="Top anúncios pontuados (JOIN com raw).")
    p_top.add_argument("--niche", help="filtra por grupo/nicho")
    p_top.add_argument("--limit", type=int, default=30)
    p_top.add_argument("--ambigous-only", action="store_true",
                       help="só os não descartados (is_likely_big_brand != 1)")
    p_top.add_argument("--columns", help="colunas separadas por vírgula para exibir")
    p_top.set_defaults(func=cmd_top)

    p_raw = sub.add_parser("raw", help="Dump da tabela bruta raw_ads.")
    p_raw.add_argument("--niche")
    p_raw.add_argument("--limit", type=int, default=30)
    p_raw.add_argument("--format", choices=["table", "json"], default="table")
    p_raw.set_defaults(func=cmd_raw)

    p_stats = sub.add_parser("stats", help="Estatísticas agregadas por nicho.")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    storage = Storage(args.db)
    args.func(args, storage)


if __name__ == "__main__":
    main()
