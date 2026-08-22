#!/usr/bin/env python3
"""Update a GitHub profile README with Tistory blog cards and thumbnails.

The updater reads the Tistory RSS feed, fetches each post page, prefers the
page's og:image, and falls back to the first image in the RSS description.
A featured post can optionally be pinned above the latest posts.

Only the content between BLOG-POSTS markers is replaced.
"""

from __future__ import annotations

import argparse
import html
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

START_MARKER = "<!-- BLOG-POSTS:START -->"
END_MARKER = "<!-- BLOG-POSTS:END -->"
USER_AGENT = "slowgrid-profile-readme/1.0 (+https://github.com/slowgrid/slowgrid)"
TIMEOUT_SECONDS = 15


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
        self.published_time = ""
        self.canonical = ""
        self.first_image = ""
        self._inside_title = False
        self._title_parts: list[str] = []

    @property
    def title(self) -> str:
        return "".join(self._title_parts).strip()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        data = {k.lower(): (v or "") for k, v in attrs}
        tag = tag.lower()

        if tag == "meta":
            key = (data.get("property") or data.get("name") or "").lower()
            content = data.get("content", "").strip()
            if key == "og:image" and content and not self.og_image:
                self.og_image = content
            elif key == "og:title" and content and not self.og_title:
                self.og_title = content
            elif key in {"article:published_time", "date", "datepublished"} and content and not self.published_time:
                self.published_time = content
        elif tag == "link" and data.get("rel", "").lower() == "canonical":
            self.canonical = data.get("href", "").strip()
        elif tag == "img" and not self.first_image:
            src = data.get("src", "").strip() or data.get("data-src", "").strip()
            if src:
                self.first_image = src
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
    """Normalize only enough for duplicate detection; preserve the real URL for links."""
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

    iso_value = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_value)
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
    image = parser.first_image
    return urljoin(base_url, image) if image else ""


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
        posts.append(Post(title=title, url=url, published=published, description=description))

    # RSS is normally newest-first, but sorting makes the behavior explicit.
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
        post.thumbnail = first_image_from_html(post.description, post.url)
        return post

    parser = PageMetadataParser()
    try:
        parser.feed(page)
    except Exception as exc:
        print(f"warning: could not parse {post.url}: {exc}", file=sys.stderr)

    thumbnail = parser.og_image or first_image_from_html(post.description, post.url) or parser.first_image
    if thumbnail:
        post.thumbnail = urljoin(post.url, thumbnail)

    if not post.title:
        post.title = html.unescape(parser.og_title or parser.title).strip()
    if not post.published and parser.published_time:
        post.published = parse_date(parser.published_time)

    return post


def resolve_featured(url: str, rss_posts: list[Post]) -> Optional[Post]:
    if not url.strip():
        return None

    target = normalize_url(url)
    for post in rss_posts:
        if normalize_url(post.url) == target:
            # copy so latest-post mutation does not affect the featured card
            return Post(post.title, post.url, post.published, post.description, post.thumbnail)

    # Older post not present in the RSS window: discover title/image from the page itself.
    post = Post(title="Featured post", url=url.strip())
    try:
        page = fetch_text(post.url)
        parser = PageMetadataParser()
        parser.feed(page)
        post.title = html.unescape(parser.og_title or parser.title or post.title).strip()
        if parser.og_image or parser.first_image:
            post.thumbnail = urljoin(post.url, parser.og_image or parser.first_image)
        post.published = parse_date(parser.published_time)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"warning: could not fetch featured post {post.url}: {exc}", file=sys.stderr)
    return post


def render_card(post: Post) -> str:
    title = html.escape(post.title, quote=True)
    url = html.escape(post.url, quote=True)
    date = post.published.strftime("%Y.%m.%d") if post.published else ""
    host = html.escape(urlsplit(post.url).netloc or "slowgrid.tistory.com")

    meta_parts = [part for part in (date, host) if part]
    meta = " &middot; ".join(meta_parts)
    meta_html = f"<br/><sub>{meta}</sub>" if meta else ""

    if post.thumbnail:
        thumb = html.escape(post.thumbnail, quote=True)
        return (
            '<table width="100%"><tr>'
            f'<td width="190" valign="top"><a href="{url}">'
            f'<img src="{thumb}" width="180" alt="{title} thumbnail"/></a></td>'
            f'<td valign="middle"><a href="{url}"><strong>{title}</strong></a>{meta_html}</td>'
            "</tr></table>"
        )

    return (
        '<table width="100%"><tr>'
        f'<td valign="middle"><a href="{url}"><strong>{title}</strong></a>{meta_html}</td>'
        "</tr></table>"
    )


def render_section(featured: Optional[Post], latest: list[Post]) -> str:
    chunks: list[str] = []
    if featured:
        chunks.append("### Featured post\n\n" + render_card(featured))

    if latest:
        chunks.append("### Latest posts\n\n" + "\n".join(render_card(post) for post in latest))
    else:
        chunks.append("### Latest posts\n\n_No posts found._")

    return "\n\n".join(chunks).strip()


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readme", default="README.md")
    parser.add_argument("--rss-url", default="https://slowgrid.tistory.com/rss")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--featured-url", default="")
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    rss_text = fetch_text(args.rss_url)
    rss_posts = parse_rss(rss_text)

    featured = resolve_featured(args.featured_url, rss_posts)
    if featured:
        featured = fetch_page_metadata(featured)

    featured_key = normalize_url(featured.url) if featured else ""
    latest: list[Post] = []
    for post in rss_posts:
        if featured_key and normalize_url(post.url) == featured_key:
            continue
        latest.append(fetch_page_metadata(post))
        if len(latest) >= args.limit:
            break

    rendered = render_section(featured, latest)
    readme_path = Path(args.readme)
    original = readme_path.read_text(encoding="utf-8")
    updated = replace_marked_section(original, rendered)

    if updated != original:
        readme_path.write_text(updated, encoding="utf-8")
        print(f"updated {readme_path} with {len(latest)} latest post(s)")
    else:
        print(f"no changes in {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
