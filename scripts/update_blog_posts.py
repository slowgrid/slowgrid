#!/usr/bin/env python3
"""Render Tistory posts as gapless editorial SVG cards in a GitHub profile README.

The updater keeps every post independently clickable, but emits all card images inside
one raw HTML container. This avoids GitHub wrapping each card in a paragraph and adding
visible space between adjacent SVGs.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

try:
    from render_profile import (
        ASSETS,
        ROOT,
        esc,
        palette,
        safe_url,
        stacked_linked_pictures,
        svg_document,
        visual_wrap,
        visual_width,
        write_themed_asset,
    )
except ModuleNotFoundError:  # Supports importing as scripts.update_blog_posts in tests.
    from scripts.render_profile import (  # type: ignore[no-redef]
        ASSETS,
        ROOT,
        esc,
        palette,
        safe_url,
        stacked_linked_pictures,
        svg_document,
        visual_wrap,
        visual_width,
        write_themed_asset,
    )

START_MARKER = "<!-- BLOG-POSTS:START -->"
END_MARKER = "<!-- BLOG-POSTS:END -->"
FEATURED_MARKER_PREFIX = "<!-- BLOG-FEATURED:"
USER_AGENT = "slowgrid-profile-readme/2.0 (+https://github.com/slowgrid/slowgrid)"
TIMEOUT_SECONDS = 15
BLOG_RENDERER_VERSION = "editorial-writing-1"
DEFAULT_RSS_URL = "https://slowgrid.tistory.com/rss"


@dataclass
class Post:
    title: str
    url: str
    published: Optional[datetime] = None
    description: str = ""
    thumbnail: str = ""


class PageMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.og_image = ""
        self.og_title = ""
        self.og_description = ""
        self.published_time = ""
        self.canonical = ""
        self.first_image = ""
        self._inside_title = False
        self._title_parts: list[str] = []

    @property
    def title(self) -> str:
        return "".join(self._title_parts).strip()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        data = {key.lower(): (value or "") for key, value in attrs}
        tag = tag.lower()
        if tag == "meta":
            key = (data.get("property") or data.get("name") or "").lower()
            content = data.get("content", "").strip()
            if key == "og:image" and content and not self.og_image:
                self.og_image = content
            elif key == "og:title" and content and not self.og_title:
                self.og_title = content
            elif key in {"og:description", "description"} and content and not self.og_description:
                self.og_description = content
            elif key in {"article:published_time", "date", "datepublished"} and content and not self.published_time:
                self.published_time = content
        elif tag == "link" and data.get("rel", "").lower() == "canonical":
            self.canonical = data.get("href", "").strip()
        elif tag == "img" and not self.first_image:
            source = data.get("src", "").strip() or data.get("data-src", "").strip()
            if source:
                self.first_image = source
        elif tag == "title":
            self._inside_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._title_parts.append(data)


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def normalize_url(url: str) -> str:
    """Normalize only enough for duplicate detection; preserve the real link."""
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def parse_date(value: str) -> Optional[datetime]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        pass

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def first_image_from_html(fragment: str, base_url: str = "") -> str:
    if not fragment:
        return ""
    parser = PageMetadataParser()
    try:
        parser.feed(html.unescape(fragment))
    except Exception:
        return ""
    return urljoin(base_url, parser.first_image) if parser.first_image else ""


def parse_rss(xml_text: str) -> list[Post]:
    root = ET.fromstring(xml_text)
    posts: list[Post] = []
    for item in root.findall(".//item"):
        title = html.unescape((item.findtext("title") or "").strip())
        url = (item.findtext("link") or "").strip()
        description = item.findtext("description") or ""
        published = parse_date(item.findtext("pubDate") or "")
        if not title or not url:
            continue
        posts.append(
            Post(
                title=title,
                url=url,
                published=published,
                description=description,
                thumbnail=first_image_from_html(description, url),
            )
        )

    posts.sort(
        key=lambda post: post.published.timestamp() if post.published else float("-inf"),
        reverse=True,
    )
    return posts


def fetch_page_metadata(post: Post) -> Post:
    try:
        page = fetch_text(post.url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"warning: could not fetch {post.url}: {exc}", file=sys.stderr)
        return post

    parser = PageMetadataParser()
    try:
        parser.feed(page)
    except Exception as exc:
        print(f"warning: could not parse {post.url}: {exc}", file=sys.stderr)

    if parser.og_image or parser.first_image:
        post.thumbnail = urljoin(post.url, parser.og_image or parser.first_image)
    if not post.title:
        post.title = html.unescape(parser.og_title or parser.title).strip()
    if not post.published and parser.published_time:
        post.published = parse_date(parser.published_time)
    if parser.og_description:
        post.description = html.unescape(parser.og_description).strip()
    if parser.canonical:
        post.url = urljoin(post.url, parser.canonical)
    return post


def resolve_featured(url: str, rss_posts: list[Post]) -> Optional[Post]:
    if not url.strip():
        return None

    target = normalize_url(url)
    for post in rss_posts:
        if normalize_url(post.url) == target:
            return Post(post.title, post.url, post.published, post.description, post.thumbnail)

    return fetch_page_metadata(Post(title="Featured post", url=url.strip()))


def copy_post(post: Post) -> Post:
    return Post(post.title, post.url, post.published, post.description, post.thumbnail)


def _extract_marked_content(readme: str) -> str:
    match = re.search(
        re.escape(START_MARKER) + r"(.*?)" + re.escape(END_MARKER),
        readme,
        flags=re.DOTALL,
    )
    return match.group(1) if match else ""


def discover_existing_featured_url(readme: str) -> str:
    section = _extract_marked_content(readme)
    if not section:
        return ""

    metadata = re.search(r"<!--\s*BLOG-FEATURED:(.*?)-->", section, flags=re.IGNORECASE)
    if metadata:
        candidate = html.unescape(metadata.group(1)).strip()
        if normalize_url(candidate):
            return candidate

    # Backward compatibility with the previous "### Featured post" table layout.
    featured_heading = re.search(r"###\s+Featured post(.*?)(?:###\s+Latest posts|$)", section, flags=re.DOTALL | re.IGNORECASE)
    haystack = featured_heading.group(1) if featured_heading else ""
    first_link = re.search(r'href=["\']([^"\']+)["\']', haystack, flags=re.IGNORECASE)
    return html.unescape(first_link.group(1)).strip() if first_link else ""


def blog_asset_version(posts: list[tuple[Post, str]], accent: str) -> str:
    payload = {
        "renderer": BLOG_RENDERER_VERSION,
        "accent": accent,
        "posts": [
            {
                "title": post.title,
                "url": normalize_url(post.url),
                "published": post.published.isoformat() if post.published else "",
                "kind": kind,
            }
            for post, kind in posts
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]


def post_title_layout(title: str) -> tuple[list[str], int]:
    for font_size, max_units in ((37, 39), (34, 43), (31, 48), (29, 52)):
        lines = visual_wrap(title, max_units)
        if len(lines) <= 2:
            return lines, font_size
    return visual_wrap(title, 52, max_lines=2), 29


def _short_host(url: str) -> str:
    host = (urlsplit(url).netloc or "slowgrid.tistory.com").lower()
    return re.sub(r"^www\.", "", host)


def render_post_asset(
    post: Post, position: int, total: int, kind: str, accent: str
) -> str:
    asset_name = f"writing-{position:02d}"
    title_lines, title_font_size = post_title_layout(post.title)
    date = post.published.strftime("%Y.%m.%d") if post.published else "UNDATED"
    host = _short_host(post.url)
    card_kind = kind.strip().upper()

    def build(theme: str) -> str:
        p = palette(theme, accent)
        inverse = position % 2 == 0
        bg = p["inverse_bg"] if inverse else p["bg"]
        ink = p["inverse_ink"] if inverse else p["ink"]
        muted = p["inverse_muted"] if inverse else p["muted"]
        rule = p["inverse_rule"] if inverse else p["rule"]

        title_y = 127 if len(title_lines) == 1 else 108
        line_height = int(title_font_size * 1.22)
        title_markup = "".join(
            f'<text x="306" y="{title_y + row * line_height}" class="sans" fill="{ink}" font-size="{title_font_size}" font-weight="720" letter-spacing="-1.05px">{esc(line)}</text>'
            for row, line in enumerate(title_lines)
        )
        body = f'''
  <rect width="1400" height="238" fill="{bg}"/>
  <rect width="4" height="238" fill="{accent}"/>
  <text x="64" y="46" class="sans label" fill="{muted}">WRITING {position:02d}  /  {esc(card_kind)}</text>
  <text x="1336" y="46" text-anchor="end" class="sans label" fill="{muted}">{total:02d} / NOTES</text>
  <line x1="64" y1="66" x2="1336" y2="66" stroke="{rule}"/>

  <text x="64" y="174" class="serif" fill="{muted}" font-size="90" letter-spacing="-4px">{position:02d}</text>
  <line x1="270" y1="88" x2="270" y2="198" stroke="{rule}"/>
  {title_markup}
  <text x="306" y="205" class="sans label" fill="{muted}">{esc(date)}  /  {esc(host.upper())}</text>

  <line x1="1080" y1="88" x2="1080" y2="198" stroke="{rule}"/>
  <text x="1120" y="118" class="sans label" fill="{muted}">{esc(card_kind)}</text>
  <text x="1120" y="151" class="sans small" fill="{muted}">{esc(host)}</text>
  <text x="1218" y="205" class="sans label" fill="{ink}">READ</text>
  <path d="M1274 200 H1334 M1326 192 L1334 200 L1326 208" fill="none" stroke="{ink}" stroke-width="1.5"/>
'''
        return svg_document(
            1400,
            238,
            f"{card_kind}: {post.title}",
            f"{post.title}, published {date} on {host}.",
            body,
        )

    write_themed_asset(asset_name, build("light"), build("dark"))
    return asset_name


def cleanup_stale_assets(active_names: set[str]) -> None:
    for path in ASSETS.glob("writing-*.svg"):
        stem = path.stem
        base = re.sub(r"-(?:light|dark)$", "", stem)
        if base not in active_names:
            path.unlink(missing_ok=True)


def render_section(featured: Optional[Post], latest: list[Post], accent: str) -> str:
    ordered: list[tuple[Post, str]] = []
    if featured:
        ordered.append((featured, "Featured post"))
    ordered.extend((post, "Latest post") for post in latest)

    if not ordered:
        cleanup_stale_assets(set())
        return "_No posts found._"

    version = blog_asset_version(ordered, accent)
    cards: list[tuple[str, str, str]] = []
    active_names: set[str] = set()
    for position, (post, kind) in enumerate(ordered, start=1):
        asset_name = render_post_asset(post, position, len(ordered), kind, accent)
        active_names.add(asset_name)
        cards.append((asset_name, post.title, post.url))

    cleanup_stale_assets(active_names)
    featured_url = featured.url if featured else ""
    metadata = f"<!-- BLOG-FEATURED:{esc(featured_url)} -->"
    return metadata + "\n" + stacked_linked_pictures(cards, version)


def replace_marked_section(readme: str, rendered: str) -> str:
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        flags=re.DOTALL,
    )
    replacement = f"{START_MARKER}\n{rendered}\n{END_MARKER}"
    updated, count = pattern.subn(lambda _: replacement, readme, count=1)
    if count != 1:
        raise RuntimeError(
            f"README must contain exactly one marker pair: {START_MARKER} ... {END_MARKER}"
        )
    return updated


def load_profile(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Could not read {path}: {exc}") from exc
    return data if isinstance(data, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readme", default=str(ROOT / "README.md"))
    parser.add_argument("--profile", default=str(ROOT / "profile.json"))
    parser.add_argument("--rss-url", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--featured-url", default=None)
    parser.add_argument(
        "--no-auto-featured",
        action="store_true",
        help="Do not use the newest RSS item as featured when no pinned URL exists.",
    )
    args = parser.parse_args()

    profile = load_profile(Path(args.profile))
    blog_config = profile.get("blog", {}) if isinstance(profile.get("blog", {}), dict) else {}
    accent = str(profile.get("accent", "#7c3aed"))
    rss_url = str(args.rss_url or blog_config.get("rss_url") or DEFAULT_RSS_URL)
    limit = args.limit if args.limit is not None else int(blog_config.get("limit", 3))
    if limit < 1:
        parser.error("--limit must be at least 1")

    readme_path = Path(args.readme)
    original = readme_path.read_text(encoding="utf-8")

    configured_featured = args.featured_url
    if configured_featured is None:
        configured_featured = str(blog_config.get("featured_url", "")).strip()
    featured_url = configured_featured or discover_existing_featured_url(original)

    try:
        rss_text = fetch_text(rss_url)
        rss_posts = parse_rss(rss_text)
    except (urllib.error.URLError, TimeoutError, OSError, ET.ParseError) as exc:
        print(f"warning: blog update skipped because the RSS feed could not be read: {exc}", file=sys.stderr)
        return 0

    featured = resolve_featured(featured_url, rss_posts) if featured_url else None
    if featured is None and rss_posts and not args.no_auto_featured:
        featured = copy_post(rss_posts[0])

    featured_key = normalize_url(featured.url) if featured else ""
    latest: list[Post] = []
    for post in rss_posts:
        if featured_key and normalize_url(post.url) == featured_key:
            continue
        latest.append(copy_post(post))
        if len(latest) >= limit:
            break

    rendered = render_section(featured, latest, accent)
    updated = replace_marked_section(original, rendered)

    if updated != original:
        readme_path.write_text(updated, encoding="utf-8")
        print(
            f"updated {readme_path} with {1 if featured else 0} featured and "
            f"{len(latest)} latest post(s)"
        )
    else:
        print(f"no changes in {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
