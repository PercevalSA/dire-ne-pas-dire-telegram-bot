from __future__ import annotations

from dataclasses import dataclass
from html import escape as html_escape
from urllib.parse import urlparse
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


BASE = "https://www.academie-francaise.fr"
INDEX = "https://www.academie-francaise.fr/dire-ne-pas-dire"
DICO_BASE = "https://www.dictionnaire-academie.fr"


@dataclass(frozen=True)
class Article:
    title: str
    url: str


@dataclass(frozen=True)
class ArticleContent:
    title: str
    url: str
    body_html: str


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

    # The "Dire, ne pas dire" landing page is a feed of blog nodes.
    # Each node title links to the actual article at root (e.g. /le-cuirasse...),
    # while the category link is under /dire-ne-pas-dire/<category>.
    for node in soup.select("div.node.node-blog"):
        h = node.select_one("h2 a[href]")
        if not h:
            continue
        href = (h.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:")):
            continue
        url = urljoin(BASE, href).split("#", 1)[0]
        if url in seen:
            continue
        seen.add(url)
        title = " ".join(h.get_text(" ", strip=True).split()) or url.rsplit("/", 1)[-1].replace(
            "-", " "
        )
        out.append(Article(title=title, url=url))
        if len(out) >= limit:
            break

    return out


def _render_inline_to_tg_html(node: Tag | NavigableString, *, base_url: str) -> str:
    """
    Convert a BeautifulSoup node to a Telegram-HTML-safe string.

    We keep a small, safe subset of tags and escape everything else.
    """
    if isinstance(node, NavigableString):
        return html_escape(str(node))
    if not isinstance(node, Tag):
        return ""

    name = (node.name or "").lower()

    if name == "br":
        return "\n"

    # Recurse through children first for most elements
    inner = "".join(_render_inline_to_tg_html(c, base_url=base_url) for c in node.children)

    if name in {"strong", "b"}:
        return f"<b>{inner}</b>"
    if name in {"em", "i"}:
        return f"<i>{inner}</i>"
    if name in {"u", "ins"}:
        return f"<u>{inner}</u>"
    if name in {"s", "strike", "del"}:
        return f"<s>{inner}</s>"
    if name == "code":
        return f"<code>{inner}</code>"
    if name == "a":
        href = (node.get("href") or "").strip()
        if not href:
            return inner
        url = urljoin(base_url, href)
        # Telegram HTML requires a quoted href.
        return f'<a href="{html_escape(url, quote=True)}">{inner}</a>'
    if name in {"span"}:
        # Keep spoiler if present, otherwise just inline text.
        cls = " ".join(node.get("class") or [])
        if "tg-spoiler" in cls:
            return f'<span class="tg-spoiler">{inner}</span>'
        return inner

    # Drop unsupported tags but keep their text.
    return inner


def _extract_article_body_html_academie(soup: BeautifulSoup, *, base_url: str) -> str:
    root = soup.select_one("div.node.node-blog") or soup
    content = root.select_one("div.content") or root

    blocks: list[str] = []

    # Preserve a readable structure: headings/paragraphs/lists.
    for el in content.find_all(
        ["h2", "h3", "p", "ul", "ol", "blockquote", "pre"],
        recursive=True,
    ):
        name = (el.name or "").lower()

        if name in {"h2", "h3"}:
            txt = "".join(_render_inline_to_tg_html(c, base_url=base_url) for c in el.children).strip()
            if txt:
                blocks.append(f"<b>{txt}</b>")
            continue

        if name == "p":
            txt = "".join(_render_inline_to_tg_html(c, base_url=base_url) for c in el.children).strip()
            if txt:
                blocks.append(txt)
            continue

        if name in {"ul", "ol"}:
            items: list[str] = []
            for li in el.find_all("li", recursive=False):
                li_txt = "".join(_render_inline_to_tg_html(c, base_url=base_url) for c in li.children).strip()
                if li_txt:
                    items.append(f"• {li_txt}")
            if items:
                blocks.append("\n".join(items))
            continue

        if name == "blockquote":
            txt = "".join(_render_inline_to_tg_html(c, base_url=base_url) for c in el.children).strip()
            if txt:
                blocks.append(f"<i>{txt}</i>")
            continue

        if name == "pre":
            # Telegram supports <pre> with optional <code>.
            code_txt = el.get_text("\n", strip=True)
            if code_txt:
                blocks.append(f"<pre>{html_escape(code_txt)}</pre>")
            continue

    body_html = "\n\n".join(b for b in blocks if b).strip()
    return body_html


def _extract_article_body_html_dico(soup: BeautifulSoup, *, base_url: str) -> tuple[str, str | None]:
    """
    Dictionnaire site structure (ex: /article/DNP0585):
    - div.s_Notice contains the entry
    - title: h2.s_Entree
    - rubric line: div.s_rubn (often italic + section)
    - paragraphs: div.s_DivPar
    - quotations: blockquote.s_cit
    - references: div.s_ZoneRenv (often contains ■ markers)
    """
    notice = soup.select_one("div.s_Notice")
    if not notice:
        return "", None

    rubric_el = notice.select_one("div.s_rubn")
    rubric = None
    if rubric_el:
        rubric = " ".join(rubric_el.get_text(" ", strip=True).split()) or None

    blocks: list[str] = []
    for el in notice.find_all(["div", "blockquote"], recursive=False):
        cls = " ".join(el.get("class") or [])

        if isinstance(el, Tag) and el.name == "blockquote":
            txt = "".join(_render_inline_to_tg_html(c, base_url=base_url) for c in el.children).strip()
            if txt:
                blocks.append(f"<i>{txt}</i>")
            continue

        if not isinstance(el, Tag) or el.name != "div":
            continue

        if "s_EnTete" in cls or "s_rubn" in cls:
            continue

        if "s_DivPar" in cls:
            txt = "".join(_render_inline_to_tg_html(c, base_url=base_url) for c in el.children).strip()
            if txt:
                blocks.append(txt)
            continue

        if "s_ZoneRenv" in cls:
            txt = " ".join(el.get_text(" ", strip=True).split())
            if txt:
                # Keep the "■" sections readable; Telegram HTML doesn't do small-caps, etc.
                blocks.append(txt)
            continue

    return "\n\n".join(b for b in blocks if b).strip(), rubric


def fetch_article_content(article: Article, timeout_s: int = 20) -> ArticleContent:
    r = requests.get(
        article.url,
        timeout=timeout_s,
        headers={
            "User-Agent": "academie-fr-dnpd-tgbot/1.0 (+https://t.me/)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    parsed = urlparse(article.url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    if parsed.netloc.endswith("dictionnaire-academie.fr"):
        body_html, rubric = _extract_article_body_html_dico(soup, base_url=base_url)
        title_el = soup.select_one("div.s_Notice h2.s_Entree") or soup.select_one("h2.s_Entree")
        title = (
            " ".join(title_el.get_text(" ", strip=True).split())
            if title_el
            else article.title
        )
        if rubric:
            body_html = f"<i>{html_escape(rubric)}</i>\n\n{body_html}" if body_html else f"<i>{html_escape(rubric)}</i>"
        return ArticleContent(title=title, url=article.url, body_html=body_html)

    title_el = soup.select_one("h1")
    title = (
        " ".join(title_el.get_text(" ", strip=True).split())
        if title_el
        else article.title
    )

    body_html = _extract_article_body_html_academie(soup, base_url=base_url)
    return ArticleContent(title=title, url=article.url, body_html=body_html)


def format_article_html(article: ArticleContent) -> str:
    # Telegram HTML parse mode; keep it simple and robust.
    title = html_escape(article.title)
    body = article.body_html
    # Keep source link, but the message is primarily the content.
    return f"📌 <b>Dire, ne pas dire</b>\n\n<b>{title}</b>\n\n{body}\n\n<i>Source :</i> {html_escape(article.url)}"


def split_telegram_text(text: str, max_len: int = 3900) -> list[str]:
    # Conservative split to stay below Telegram 4096 chars.
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for para in text.split("\n\n"):
        piece = (para + "\n\n")
        if cur_len + len(piece) > max_len and cur:
            chunks.append("".join(cur).rstrip())
            cur = []
            cur_len = 0
        if len(piece) > max_len:
            # Hard split very long paragraph.
            s = para
            while s:
                take = s[:max_len]
                chunks.append(take)
                s = s[max_len:]
            continue
        cur.append(piece)
        cur_len += len(piece)
    if cur:
        chunks.append("".join(cur).rstrip())
    return chunks
