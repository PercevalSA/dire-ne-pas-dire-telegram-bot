from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE = "https://www.academie-francaise.fr"
INDEX = "https://www.academie-francaise.fr/dire-ne-pas-dire"


@dataclass(frozen=True)
class Article:
    title: str
    url: str


def _is_article_href(href: str) -> bool:
    # Articles are typically under /dire-ne-pas-dire/<slug>
    if not href:
        return False
    if href.startswith("mailto:") or href.startswith("tel:"):
        return False
    return "/dire-ne-pas-dire/" in href and href.rstrip("/").count("/") >= 2


def fetch_latest_articles(limit: int = 30, timeout_s: int = 20) -> list[Article]:
    """
    Returns a list of recent articles from the 'Dire, ne pas dire' index page.
    Best-effort parsing: we keep unique links in first-seen order.
    """
    r = requests.get(
        INDEX,
        timeout=timeout_s,
        headers={
            "User-Agent": "academie-fr-dnpd-tgbot/1.0 (+https://t.me/)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    seen: set[str] = set()
    out: list[Article] = []

    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not _is_article_href(href):
            continue
        url = urljoin(BASE, href)
        url = url.split("#", 1)[0]
        if url in seen:
            continue
        seen.add(url)
        title = " ".join(a.get_text(" ", strip=True).split())
        if not title:
            # fallback title if link has no text
            title = url.rsplit("/", 1)[-1].replace("-", " ")
        out.append(Article(title=title, url=url))
        if len(out) >= limit:
            break

    return out


def format_message(article: Article) -> str:
    return f"📌 *Dire, ne pas dire*\n\n*{article.title}*\n{article.url}"
