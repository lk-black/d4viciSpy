"""Gera um relatório HTML estático a partir dos anúncios processados no storage.

Não sobe servidor nem depende de framework web — gera um arquivo .html que
você abre direto no navegador. Um card por anúncio, com o criativo (vídeo ou
imagem) embutido, score de escala, dias ativo, e link pro anúncio original.

Esta é a camada "View" do pipeline original (Scrapy -> Process -> View).
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Optional

from .storage import Storage

_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Ad Pipeline — Relatório</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
    background: #0f0f11; color: #eee; margin: 0; padding: 28px;
  }}
  h1 {{ font-weight: 600; margin: 0 0 4px; }}
  .meta {{ color: #999; margin-bottom: 24px; font-size: 14px; }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 18px;
  }}
  .card {{
    background: #1a1a1d; border-radius: 14px; overflow: hidden;
    border: 1px solid #2a2a2e; display: flex; flex-direction: column;
  }}
  .media {{ background: #000; aspect-ratio: 4 / 3; }}
  .media video, .media img {{
    width: 100%; height: 100%; display: block; object-fit: contain; background: #000;
  }}
  .no-media {{
    height: 100%; display: flex; align-items: center; justify-content: center;
    color: #555; font-size: 13px;
  }}
  .info {{ padding: 14px 16px; flex: 1; display: flex; flex-direction: column; }}
  .niche {{
    font-size: 11px; text-transform: uppercase; color: #7aa2f7;
    letter-spacing: 0.06em; font-weight: 600;
  }}
  .page {{ font-weight: 600; margin: 4px 0 8px; font-size: 15px; }}
  .stats {{ font-size: 13px; color: #9a9aa0; margin-bottom: 10px; display: flex; gap: 10px; }}
  .stats b {{ color: #eee; }}
  .badge {{
    display: inline-block; padding: 2px 8px; border-radius: 999px;
    font-size: 11px; background: #22331f; color: #8bd17c;
  }}
  .body {{ font-size: 13px; color: #ccc; line-height: 1.45; margin-bottom: 12px; flex: 1; }}
  .link {{
    font-size: 13px; color: #7aa2f7; text-decoration: none; margin-top: auto;
  }}
  .link:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
  <h1>Ad Pipeline</h1>
  <div class="meta">{count} anúncios · nicho: {niche} · ordenado por score de escala</div>
  <div class="grid">
    {cards}
  </div>
</body>
</html>"""

_CARD_TEMPLATE = """
    <div class="card">
      <div class="media">{media}</div>
      <div class="info">
        <div class="niche">{niche}</div>
        <div class="page">{page_name}</div>
        <div class="stats"><span class="badge">score {score:.1f}</span> <span>{days} dias ativo</span></div>
        <div class="body">{body}</div>
        <a class="link" href="{snapshot_url}" target="_blank" rel="noopener">Ver na Ad Library ↗</a>
      </div>
    </div>
"""


class HtmlReportGenerator:
    def __init__(self, storage: Storage):
        self.storage = storage

    def build(
        self,
        niche: Optional[str] = None,
        limit: int = 50,
        output_path: str = "report.html",
    ) -> str:
        # Garante que criativos existam antes de gerar o relatório —
        # reextrai do raw_json se necessário.
        self.storage.backfill_creatives()
        rows = self.storage.top_scored(niche=niche, limit=limit)
        cards_html = "\n".join(self._render_card(row) for row in rows)
        html = _TEMPLATE.format(cards=cards_html, count=len(rows), niche=escape(niche or "todos"))
        Path(output_path).write_text(html, encoding="utf-8")
        return output_path

    @staticmethod
    def _render_card(row) -> str:
        page_name = escape(row["page_name"] or "—")
        niche = escape(row["niche"] or "")
        body = escape((row["creative_body"] or "sem texto capturado")[:220])
        snapshot_url = escape(row["snapshot_url"] or "#")
        video_url = row["creative_video_url"]
        image_url = row["creative_image_url"]

        if video_url:
            poster = escape(image_url) if image_url else ""
            poster_attr = f' poster="{poster}"' if poster else ""
            media = (
                f'<video controls preload="metadata" {poster_attr}'
                f' onerror="this.outerHTML=\'<div class=no-media>vídeo indisponível</div>\'">'
                f'<source src="{escape(video_url)}"></video>'
            )
        elif image_url:
            media = (
                f'<img src="{escape(image_url)}" alt="criativo do anúncio" loading="lazy" '
                f'onerror="this.outerHTML=\'<div class=no-media>imagem indisponível</div>\'">'
            )
        else:
            media = '<div class="no-media">sem criativo capturado</div>'

        return _CARD_TEMPLATE.format(
            media=media,
            niche=niche,
            page_name=page_name,
            score=row["scale_score"],
            days=row["days_active"],
            body=body,
            snapshot_url=snapshot_url,
        )
