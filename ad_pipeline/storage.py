"""Camada de persistência (SQLite). Separa dado bruto coletado de dado já processado/pontuado.

Ter as duas tabelas separadas resolve dois problemas do pipeline original:
  1. Nunca perdemos o dado bruto, mesmo que a lógica de score/heurística mude depois.
  2. `already_processed` evita reprocessar (e regastar chamada de LLM) um anúncio
     que já vimos em um ciclo anterior.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from .models import ScoredAd

# colunas adicionadas depois da v1 — migradas via ALTER TABLE se o banco já existir
_RAW_ADS_EXTRA_COLUMNS = {
    "creative_body": "TEXT",
    "creative_image_url": "TEXT",
    "creative_video_url": "TEXT",
    "snapshot_url": "TEXT",
}


class Storage:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_schema()
        self._migrate()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_ads (
                    ad_id TEXT PRIMARY KEY,
                    niche TEXT,
                    page_name TEXT,
                    page_id TEXT,
                    delivery_start TEXT,
                    impressions_lower INTEGER,
                    raw_json TEXT,
                    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scored_ads (
                    ad_id TEXT PRIMARY KEY,
                    niche TEXT,
                    days_active INTEGER,
                    scale_score REAL,
                    is_likely_big_brand INTEGER,
                    brand_reason TEXT,
                    llm_classification TEXT,
                    processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ad_id) REFERENCES raw_ads (ad_id)
                )
                """
            )

    def _migrate(self) -> None:
        """Adiciona colunas novas (criativo) a bancos criados antes delas existirem.

        Idempotente: PRAGMA table_info diz quais colunas já existem, só
        adiciona as que faltam. Seguro rodar toda vez que Storage é criado.
        """
        with self._connect() as conn:
            existing = {row["name"] for row in conn.execute("PRAGMA table_info(raw_ads)")}
            for column, coltype in _RAW_ADS_EXTRA_COLUMNS.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE raw_ads ADD COLUMN {column} {coltype}")

    def save_raw(
        self,
        ad_id: str,
        niche: str,
        page_name: Optional[str],
        page_id: Optional[str],
        delivery_start: Optional[str],
        impressions_lower: int,
        raw_json: str,
        creative_body: str = "",
        creative_image_url: Optional[str] = None,
        creative_video_url: Optional[str] = None,
        snapshot_url: Optional[str] = None,
    ) -> None:
        """Persiste o dado bruto. Se o ad já existir, atualiza tudo (UPSERT).

        IMPORTANTE: usamos `ON CONFLICT ... DO UPDATE` (e não INSERT OR IGNORE)
        para que linhas coletadas numa versão antiga do pipeline — antes de
        extrair criativos — sejam preenchidas quando o mesmo anúncio for
        coletado de novo. Com INSERT OR IGNORE, os campos de criativo ficavam
        NULL para sempre.
        """
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO raw_ads
                   (ad_id, niche, page_name, page_id, delivery_start, impressions_lower,
                    raw_json, creative_body, creative_image_url, creative_video_url, snapshot_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ad_id) DO UPDATE SET
                     niche = excluded.niche,
                     page_name = excluded.page_name,
                     page_id = excluded.page_id,
                     delivery_start = excluded.delivery_start,
                     impressions_lower = excluded.impressions_lower,
                     raw_json = excluded.raw_json,
                     creative_body = excluded.creative_body,
                     creative_image_url = excluded.creative_image_url,
                     creative_video_url = excluded.creative_video_url,
                     snapshot_url = excluded.snapshot_url
                   """,
                (
                    ad_id, niche, page_name, page_id, delivery_start, impressions_lower,
                    raw_json, creative_body, creative_image_url, creative_video_url, snapshot_url,
                ),
            )

    def backfill_creatives(self) -> int:
        """Reextrai os criativos (vídeo/imagem/body/snapshot) a partir do raw_json.

        Corrige linhas coletadas antes da extração de criativo existir: o
        raw_json guarda o payload completo da Ad Library, então conseguimos
        reprocessá-lo agora e gravar as URLs na tabela sem re-coletar.
        Retorna quantas linhas foram atualizadas.
        """
        from .creative import CreativeExtractor
        from meta_ads_collector.models import Ad

        updated = 0
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ad_id, raw_json FROM raw_ads"
            ).fetchall()
            for row in rows:
                try:
                    ad = Ad.from_graphql_response(json.loads(row["raw_json"]))
                    info = CreativeExtractor.extract(ad)
                except Exception:
                    continue
                cur = conn.execute(
                    """UPDATE raw_ads SET
                         creative_body = ?,
                         creative_image_url = ?,
                         creative_video_url = ?,
                         snapshot_url = ?
                       WHERE ad_id = ?""",
                    (
                        info.body,
                        info.image_url,
                        info.video_url,
                        info.snapshot_url,
                        row["ad_id"],
                    ),
                )
                updated += cur.rowcount
        return updated

    def save_scored(self, scored: ScoredAd) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO scored_ads
                   (ad_id, niche, days_active, scale_score, is_likely_big_brand,
                    brand_reason, llm_classification)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    scored.ad_id,
                    scored.niche,
                    scored.days_active,
                    scored.scale_score,
                    None if scored.is_likely_big_brand is None else int(scored.is_likely_big_brand),
                    scored.brand_reason,
                    scored.llm_classification,
                ),
            )

    def already_processed(self, ad_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM scored_ads WHERE ad_id = ?", (ad_id,)).fetchone()
            return row is not None

    def top_scored(self, niche: Optional[str] = None, limit: int = 30) -> list[sqlite3.Row]:
        """Retorna os anúncios com maior scale_score, opcionalmente filtrados por nicho.

        Faz JOIN com raw_ads para trazer page_name + dados de criativo junto —
        scored_ads não duplica isso, já existe na tabela raw.
        """
        base_query = """
            SELECT s.*,
                   r.page_name AS page_name,
                   r.creative_body AS creative_body,
                   r.creative_image_url AS creative_image_url,
                   r.creative_video_url AS creative_video_url,
                   r.snapshot_url AS snapshot_url
            FROM scored_ads s
            JOIN raw_ads r ON r.ad_id = s.ad_id
        """
        with self._connect() as conn:
            if niche:
                cur = conn.execute(
                    base_query + " WHERE s.niche = ? ORDER BY s.scale_score DESC LIMIT ?",
                    (niche, limit),
                )
            else:
                cur = conn.execute(
                    base_query + " ORDER BY s.scale_score DESC LIMIT ?", (limit,)
                )
            return cur.fetchall()
