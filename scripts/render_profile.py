#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

RENDERER_VERSION = "editorial-complete-4"
BLOG_START_MARKER = "<!-- BLOG-POSTS:START -->"
BLOG_END_MARKER = "<!-- BLOG-POSTS:END -->"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def safe_url(url: object) -> str:
    value = str(url or "").strip()
    if re.match(r"^(https://|mailto:)", value, flags=re.IGNORECASE):
        return value
    return "#"


def display_url(value: str, username: str) -> str:
    value = re.sub(r"^https?://", "", str(value).strip(), flags=re.IGNORECASE)
    value = re.sub(r"^www\.", "", value, flags=re.IGNORECASE).rstrip("/")
    return value or f"github.com/{username}"


def visual_width(value: object) -> int:
    """Approximate rendered width, counting wide East Asian glyphs as two units."""
    total = 0
    for char in str(value):
        total += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return total


def _split_long_token(token: str, max_units: int) -> list[str]:
    if visual_width(token) <= max_units:
        return [token]

    parts: list[str] = []
    current = ""
    for char in token:
        candidate = current + char
        if current and visual_width(candidate) > max_units:
            parts.append(current)
            current = char
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _truncate_to_units(value: str, max_units: int, placeholder: str = "…") -> str:
    value = value.rstrip()
    if visual_width(value) <= max_units:
        return value

    target = max(0, max_units - visual_width(placeholder))
    result = ""
    for char in value:
        if visual_width(result + char) > target:
            break
        result += char
    return result.rstrip() + placeholder


def visual_wrap(value: object, max_units: int, max_lines: int | None = None) -> list[str]:
    """Wrap Latin and Korean text without relying on a server-side font renderer."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return [""]

    raw_tokens = text.split(" ")
    tokens: list[str] = []
    for token in raw_tokens:
        tokens.extend(_split_long_token(token, max_units))

    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = token if not current else f"{current} {token}"
        if visual_width(candidate) <= max_units:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = token
    if current:
        lines.append(current)

    if max_lines is not None and len(lines) > max_lines:
        kept = lines[:max_lines]
        overflow = " ".join(lines[max_lines - 1 :])
        kept[-1] = _truncate_to_units(overflow, max_units)
        return kept
    return lines or [""]


def wrap_project_title(value: object, max_units: int) -> list[str]:
    """Wrap repo-style names after spaces, slashes, and hyphens where possible."""
    title = str(value or "").strip()
    if not title:
        return [""]

    tokens = [token for token in re.split(r"(?<=[-/])|\s+", title) if token]
    expanded: list[str] = []
    for token in tokens:
        expanded.extend(_split_long_token(token, max_units))

    lines: list[str] = []
    current = ""
    for token in expanded:
        joiner = "" if not current or current.endswith(("-", "/")) else " "
        candidate = f"{current}{joiner}{token}" if current else token
        if visual_width(candidate) <= max_units:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = token
    if current:
        lines.append(current)
    return lines or [""]


def project_title_layout(value: object) -> tuple[list[str], int]:
    for font_size, max_units in ((42, 20), (39, 23), (36, 26), (33, 29), (30, 32)):
        lines = wrap_project_title(value, max_units)
        if len(lines) <= 2:
            return lines, font_size

    lines = wrap_project_title(value, 32)
    if len(lines) > 2:
        lines = [lines[0], _truncate_to_units(" ".join(lines[1:]), 32)]
    return lines[:2], 30


def asset_version(cfg: dict) -> str:
    raw = json.dumps(cfg, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    payload = f"{RENDERER_VERSION}:{raw}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:10]


def palette(theme: str, accent: str) -> dict[str, str]:
    if theme == "dark":
        return {
            "bg": "#151515",
            "ink": "#f4f1e9",
            "muted": "#9f9c94",
            "rule": "#3a3936",
            "soft": "#1e1e1c",
            "inverse_bg": "#ece9e1",
            "inverse_ink": "#171717",
            "inverse_muted": "#716e67",
            "inverse_rule": "#c8c4ba",
            "accent": accent,
        }
    return {
        "bg": "#f2f0e9",
        "ink": "#171717",
        "muted": "#6f6c66",
        "rule": "#c9c5bb",
        "soft": "#e8e4da",
        "inverse_bg": "#171717",
        "inverse_ink": "#f4f1e9",
        "inverse_muted": "#a6a299",
        "inverse_rule": "#403f3c",
        "accent": accent,
    }


def svg_document(
    width: int,
    height: int,
    title: str,
    description: str,
    body: str,
) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{esc(title)}</title>
  <desc id="desc">{esc(description)}</desc>
  <defs>
    <style>
      .sans {{ font-family: "Noto Sans CJK KR", "Noto Sans KR", "NanumGothic", "NanumBarunGothic", "Apple SD Gothic Neo", "Malgun Gothic", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
      .serif {{ font-family: Georgia, "Times New Roman", serif; }}
      .label {{ font-size: 13px; font-weight: 700; letter-spacing: 1.7px; }}
      .small {{ font-size: 14px; font-weight: 600; letter-spacing: .2px; }}
    </style>
  </defs>
  {body}
</svg>'''


def write_themed_asset(name: str, light_svg: str, dark_svg: str) -> None:
    (ASSETS / f"{name}.svg").write_text(light_svg, encoding="utf-8")
    (ASSETS / f"{name}-light.svg").write_text(light_svg, encoding="utf-8")
    (ASSETS / f"{name}-dark.svg").write_text(dark_svg, encoding="utf-8")


def split_name(value: str) -> list[str]:
    words = value.split()
    if len(value) <= 14 or len(words) == 1:
        return [value]
    if len(words) == 2:
        return words

    best_index = 1
    best_delta = len(value)
    for index in range(1, len(words)):
        left = " ".join(words[:index])
        right = " ".join(words[index:])
        delta = abs(len(left) - len(right))
        if delta < best_delta:
            best_index = index
            best_delta = delta
    return [" ".join(words[:best_index]), " ".join(words[best_index:])]


def render_hero(cfg: dict) -> None:
    name = str(cfg["name"]).strip()
    role = str(cfg["role"]).strip().upper()
    tagline = str(cfg["tagline"]).strip()
    location = str(cfg["location"]).strip().upper()
    username = str(cfg["username"]).strip().lstrip("@")
    website_label = display_url(cfg.get("website", ""), username).upper()
    accent = str(cfg.get("accent", "#b54a36"))

    name_lines = split_name(name)[:2]
    longest = max(len(line) for line in name_lines)
    if len(name_lines) == 1:
        font_size = 104 if longest <= 12 else 92 if longest <= 16 else 78 if longest <= 21 else 66
        name_y = [246]
    else:
        font_size = 86 if longest <= 12 else 76 if longest <= 16 else 66 if longest <= 21 else 58
        line_height = round(font_size * 0.93)
        first_y = 198 if font_size >= 76 else 190
        name_y = [first_y, first_y + line_height]

    tagline_lines = visual_wrap(tagline, 27, max_lines=3)

    def build(theme: str) -> str:
        p = palette(theme, accent)
        left_bg, left_ink, left_meta, left_rule = p["bg"], p["ink"], p["muted"], p["rule"]
        right_bg, right_ink = p["inverse_bg"], p["inverse_ink"]
        right_meta, right_rule = p["inverse_muted"], p["inverse_rule"]

        name_markup = "".join(
            f'<text x="64" y="{y}" class="sans" fill="{left_ink}" font-size="{font_size}" font-weight="760" letter-spacing="-4.8px">{esc(line)}</text>'
            for line, y in zip(name_lines, name_y)
        )
        tagline_markup = "".join(
            f'<text x="982" y="{170 + index * 46}" class="serif" fill="{right_ink}" font-size="33" letter-spacing="-.6px">{esc(line)}</text>'
            for index, line in enumerate(tagline_lines)
        )
        body = f'''
  <rect width="936" height="440" fill="{left_bg}"/>
  <rect x="936" width="464" height="440" fill="{right_bg}"/>
  <rect x="932" width="4" height="440" fill="{accent}"/>

  <text x="64" y="52" class="sans label" fill="{left_meta}">GITHUB PROFILE</text>
  <text x="872" y="52" text-anchor="end" class="sans label" fill="{left_meta}">@{esc(username)}</text>
  <line x1="64" y1="72" x2="872" y2="72" stroke="{left_rule}"/>

  {name_markup}
  <line x1="64" y1="366" x2="872" y2="366" stroke="{left_rule}"/>
  <text x="64" y="400" class="sans label" fill="{left_meta}">{esc(location)}</text>
  <text x="872" y="400" text-anchor="end" class="sans label" fill="{left_meta}">{esc(website_label)}</text>

  <text x="982" y="70" class="sans label" fill="{right_meta}">{esc(role)}</text>
  {tagline_markup}
  <line x1="982" y1="326" x2="1340" y2="326" stroke="{right_rule}"/>
  <text x="982" y="362" class="sans small" fill="{right_meta}">Selected work, open source, and notes below.</text>
  <path d="M982 390 H1030 M1022 382 L1030 390 L1022 398" fill="none" stroke="{right_ink}" stroke-width="1.5"/>
'''
        return svg_document(
            1400,
            440,
            f"{name} - {role}",
            f"GitHub profile introduction for {name}.",
            body,
        )

    write_themed_asset("hero", build("light"), build("dark"))


def render_focus(cfg: dict) -> None:
    accent = str(cfg.get("accent", "#b54a36"))
    focus = list(cfg.get("focus", []))[:3]
    while len(focus) < 3:
        focus.append({"label": "Focus", "value": "Add this in profile.json"})

    def build(theme: str) -> str:
        p = palette(theme, accent)
        columns: list[str] = []
        starts = [64, 501, 938]
        for index, (item, x) in enumerate(zip(focus, starts), start=1):
            label = str(item.get("label", "Focus")).strip().upper()
            value_lines = visual_wrap(item.get("value", ""), 27, max_lines=2)
            value_markup = "".join(
                f'<text x="{x}" y="{156 + row * 34}" class="sans" fill="{p["ink"]}" font-size="25" font-weight="650" letter-spacing="-.5px">{esc(line)}</text>'
                for row, line in enumerate(value_lines)
            )
            columns.append(
                f'''
  <text x="{x}" y="116" class="serif" fill="{p['muted']}" font-size="21">0{index}</text>
  <text x="{x + 52}" y="115" class="sans label" fill="{p['muted']}">{esc(label)}</text>
  {value_markup}
'''
            )

        body = f'''
  <rect width="1400" height="250" fill="{p['bg']}"/>
  <rect y="0" width="1400" height="4" fill="{accent}"/>
  <text x="64" y="48" class="sans label" fill="{p['muted']}">CURRENT FOCUS</text>
  <text x="1336" y="48" text-anchor="end" class="sans label" fill="{p['muted']}">01 / PROFILE</text>
  <line x1="64" y1="70" x2="1336" y2="70" stroke="{p['rule']}"/>
  <line x1="469" y1="94" x2="469" y2="214" stroke="{p['rule']}"/>
  <line x1="906" y1="94" x2="906" y2="214" stroke="{p['rule']}"/>
  {''.join(columns)}
'''
        return svg_document(1400, 250, "Current focus", "Three current areas of focus.", body)

    write_themed_asset("focus", build("light"), build("dark"))


def render_stack(cfg: dict) -> None:
    accent = str(cfg.get("accent", "#b54a36"))
    groups = list(cfg.get("stack", {}).items())[:4]
    while len(groups) < 4:
        groups.append(("OTHER", ["Add tools", "in profile.json"]))

    def build(theme: str) -> str:
        p = palette(theme, accent)
        starts = [64, 389, 714, 1039]
        markup: list[str] = []
        for index, ((group, items), x) in enumerate(zip(groups, starts), start=1):
            item_lines: list[str] = []
            y = 146
            for item in list(items)[:5]:
                item_lines.append(
                    f'<text x="{x}" y="{y}" class="sans" fill="{p["ink"]}" font-size="21" font-weight="600" letter-spacing="-.3px">{esc(item)}</text>'
                )
                y += 35
            markup.append(
                f'''
  <text x="{x}" y="104" class="serif" fill="{p['muted']}" font-size="18">0{index}</text>
  <text x="{x + 42}" y="103" class="sans label" fill="{p['muted']}">{esc(str(group).upper())}</text>
  <line x1="{x}" y1="118" x2="{x + 256}" y2="118" stroke="{accent}" stroke-width="2"/>
  {''.join(item_lines)}
'''
            )

        body = f'''
  <rect width="1400" height="338" fill="{p['bg']}"/>
  <text x="64" y="48" class="sans label" fill="{p['muted']}">SELECTED STACK</text>
  <text x="1336" y="48" text-anchor="end" class="sans label" fill="{p['muted']}">02 / TOOLS</text>
  <line x1="64" y1="70" x2="1336" y2="70" stroke="{p['rule']}"/>
  <line x1="357" y1="92" x2="357" y2="304" stroke="{p['rule']}"/>
  <line x1="682" y1="92" x2="682" y2="304" stroke="{p['rule']}"/>
  <line x1="1007" y1="92" x2="1007" y2="304" stroke="{p['rule']}"/>
  {''.join(markup)}
'''
        return svg_document(
            1400,
            338,
            "Selected technology stack",
            "A curated technology stack grouped by area.",
            body,
        )

    write_themed_asset("stack", build("light"), build("dark"))


def render_project(cfg: dict, project: dict, index: int) -> None:
    accent = str(cfg.get("accent", "#b54a36"))
    title = str(project.get("title", f"PROJECT {index}")).strip()
    subtitle = str(project.get("subtitle", "SELECTED WORK")).strip().upper()
    description = str(project.get("description", "")).strip()
    tags = [str(value).strip() for value in project.get("tags", []) if str(value).strip()][:5]

    title_lines, title_font_size = project_title_layout(title)
    desc_lines = visual_wrap(description, 50, max_lines=3)
    tags_line = "  /  ".join(tags[:4])

    def build(theme: str) -> str:
        p = palette(theme, accent)
        inverse = index % 2 == 0
        bg = p["inverse_bg"] if inverse else p["bg"]
        ink = p["inverse_ink"] if inverse else p["ink"]
        muted = p["inverse_muted"] if inverse else p["muted"]
        rule = p["inverse_rule"] if inverse else p["rule"]

        title_y = 113 if len(title_lines) == 1 else 100
        title_line_height = int(title_font_size * 1.14)
        title_markup = "".join(
            f'<text x="306" y="{title_y + row * title_line_height}" class="sans" fill="{ink}" font-size="{title_font_size}" font-weight="720" letter-spacing="-1.35px">{esc(line)}</text>'
            for row, line in enumerate(title_lines)
        )
        desc_markup = "".join(
            f'<text x="790" y="{116 + row * 27}" class="sans" fill="{ink}" font-size="17" font-weight="470" letter-spacing="-.1px">{esc(line)}</text>'
            for row, line in enumerate(desc_lines)
        )
        body = f'''
  <rect width="1400" height="270" fill="{bg}"/>
  <rect width="4" height="270" fill="{accent}"/>
  <text x="64" y="48" class="sans label" fill="{muted}">PROJECT {index:02d}  /  {esc(subtitle)}</text>
  <line x1="64" y1="68" x2="1336" y2="68" stroke="{rule}"/>

  <text x="64" y="183" class="serif" fill="{muted}" font-size="96" letter-spacing="-4px">{index:02d}</text>
  <line x1="270" y1="92" x2="270" y2="224" stroke="{rule}"/>
  {title_markup}
  <line x1="752" y1="92" x2="752" y2="224" stroke="{rule}"/>

  {desc_markup}
  <text x="790" y="215" class="sans label" fill="{muted}">{esc(tags_line.upper())}</text>
  <text x="1240" y="215" class="sans label" fill="{ink}">VIEW</text>
  <path d="M1292 210 H1334 M1326 202 L1334 210 L1326 218" fill="none" stroke="{ink}" stroke-width="1.5"/>
'''
        return svg_document(
            1400,
            270,
            f"Project {index}: {title}",
            description or f"Selected project {title}.",
            body,
        )

    write_themed_asset(f"project-{index:02d}", build("light"), build("dark"))


def social_entries(cfg: dict) -> list[dict[str, str]]:
    # Keep link order aligned with the editorial navigation strip.
    entries: list[dict[str, str]] = []
    username = str(cfg.get("username", "")).strip().lstrip("@")
    if username:
        entries.append(
            {
                "key": "github",
                "label": "GitHub",
                "meta": f"@{username}",
                "url": f"https://github.com/{username}",
            }
        )
    if cfg.get("linkedin"):
        entries.append(
            {
                "key": "linkedin",
                "label": "LinkedIn",
                "meta": "CONNECT",
                "url": str(cfg["linkedin"]),
            }
        )
    if cfg.get("email"):
        email = str(cfg["email"]).strip()
        domain = email.rsplit("@", 1)[-1] if "@" in email else "SEND A NOTE"
        entries.append(
            {
                "key": "email",
                "label": "Email",
                "meta": domain.upper(),
                "url": f"mailto:{email}",
            }
        )
    if cfg.get("website"):
        entries.append(
            {
                "key": "website",
                "label": "Website",
                "meta": display_url(str(cfg["website"]), username).upper(),
                "url": str(cfg["website"]),
            }
        )
    return entries


def social_widths(entries: list[dict[str, str]]) -> list[int]:
    # Continue the hero split at x=932, including its 4 px accent rule.
    keys = [entry["key"] for entry in entries]
    if keys == ["github", "linkedin", "email", "website"]:
        return [311, 311, 310, 468]
    if not entries:
        return []

    base = 1400 // len(entries)
    widths = [base] * len(entries)
    widths[-1] += 1400 - sum(widths)
    return widths


def social_icon(kind: str, ink: str) -> str:
    common = (
        f'fill="none" stroke="{ink}" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round"'
    )
    if kind == "github":
        return f'''<g {common}>
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3.28-.36 6.72-1.61 6.72-7.25A5.65 5.65 0 0 0 19.22 3.3 5.26 5.26 0 0 0 19.13 0S17.95-.36 15 1.5a13.38 13.38 0 0 0-7 0C5.05-.36 3.87 0 3.87 0a5.26 5.26 0 0 0-.09 3.3 5.65 5.65 0 0 0-1.5 3.95c0 5.63 3.44 6.89 6.72 7.25A4.8 4.8 0 0 0 8 18v4"/>
    <path d="M9 18c-4.51 2-5-2-7-2"/>
  </g>'''
    if kind == "linkedin":
        return f'''<g {common}>
    <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-7a6 6 0 0 1 6-6z"/>
    <rect x="2" y="9" width="4" height="12"/>
    <circle cx="4" cy="4" r="2"/>
  </g>'''
    if kind == "email":
        return f'''<g {common}>
    <rect x="2" y="4" width="20" height="16" rx="2"/>
    <path d="M22 6 12 13 2 6"/>
  </g>'''
    return f'''<g {common}>
    <circle cx="12" cy="12" r="10"/>
    <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
  </g>'''


def render_social_asset(
    cfg: dict,
    entry: dict[str, str],
    width: int,
    index: int,
    inverse: bool,
    accent_edge: bool,
) -> None:
    accent = str(cfg.get("accent", "#b54a36"))
    label = entry["label"].upper()
    meta = _truncate_to_units(entry["meta"], 31 if width >= 400 else 13)

    def build(theme: str) -> str:
        p = palette(theme, accent)
        bg = p["inverse_bg"] if inverse else p["bg"]
        ink = p["inverse_ink"] if inverse else p["ink"]
        muted = p["inverse_muted"] if inverse else p["muted"]
        rule = p["inverse_rule"] if inverse else p["rule"]
        edge = f'<rect width="4" height="112" fill="{accent}"/>' if accent_edge else ""
        separator = (
            f'<line x1="{width - 0.5}" y1="18" x2="{width - 0.5}" y2="94" stroke="{rule}"/>'
            if not inverse
            else ""
        )
        body = f'''
  <rect width="{width}" height="112" fill="{bg}"/>
  {edge}
  <line x1="0" y1="0.5" x2="{width}" y2="0.5" stroke="{rule}"/>
  {separator}
  <rect x="28" y="28" width="56" height="56" fill="none" stroke="{rule}"/>
  <g transform="translate(44 44) scale(1.05)">
    {social_icon(entry['key'], ink)}
  </g>
  <text x="104" y="49" class="sans" fill="{ink}" font-size="19" font-weight="720" letter-spacing="-.25px">{esc(label)}</text>
  <text x="104" y="75" class="sans label" fill="{muted}">{esc(meta)}</text>
  <text x="{width - 62}" y="40" class="serif" fill="{muted}" font-size="15">0{index}</text>
  <path d="M{width - 62} 68 H{width - 28} M{width - 36} 60 L{width - 28} 68 L{width - 36} 76" fill="none" stroke="{ink}" stroke-width="1.5"/>
'''
        return svg_document(
            width,
            112,
            f"{entry['label']} link",
            f"Open {entry['label']} for this profile.",
            body,
        )

    write_themed_asset(f"social-{entry['key']}", build("light"), build("dark"))


def render_socials(cfg: dict) -> None:
    entries = social_entries(cfg)
    widths = social_widths(entries)
    expected: set[str] = set()
    hero_continuation = [entry["key"] for entry in entries] == [
        "github",
        "linkedin",
        "email",
        "website",
    ]

    for index, (entry, width) in enumerate(zip(entries, widths), start=1):
        inverse = hero_continuation and entry["key"] == "website"
        accent_edge = inverse
        render_social_asset(cfg, entry, width, index, inverse, accent_edge)
        stem = f"social-{entry['key']}"
        expected.update({f"{stem}.svg", f"{stem}-light.svg", f"{stem}-dark.svg"})

    for path in ASSETS.glob("social-*.svg"):
        if path.name not in expected:
            path.unlink()


def social_markdown(cfg: dict, version: str) -> str:
    entries = social_entries(cfg)
    widths = social_widths(entries)
    children = "".join(
        f'<a href="{esc(safe_url(entry["url"]))}" aria-label="Open {esc(entry["label"])}">'
        f'{picture(f"social-{entry["key"]}", entry["label"], version, f"{width / 14:.6f}%")}'
        f'</a>'
        for entry, width in zip(entries, widths)
    )
    return children


def picture(asset: str, alt: str, version: str, width: str = "100%") -> str:
    """Compact HTML is intentional: adjacent block images must not gain text-node gaps."""
    return (
        f'<picture><source media="(prefers-color-scheme: dark)" '
        f'srcset="./assets/{asset}-dark.svg?v={version}" />'
        f'<source media="(prefers-color-scheme: light)" '
        f'srcset="./assets/{asset}-light.svg?v={version}" />'
        f'<img src="./assets/{asset}.svg?v={version}" width="{width}" align="top" '
        f'alt="{esc(alt)}" /></picture>'
    )


def stacked_linked_pictures(cards: Iterable[tuple[str, str, str]], version: str) -> str:
    """Keep cards in one raw HTML block so GitHub does not wrap each in a <p>."""
    children = "".join(
        f'<a href="{esc(safe_url(url))}" aria-label="{esc(alt)}">{picture(asset, alt, version)}</a>'
        for asset, alt, url in cards
    )
    return f'<div align="center">{children}</div>'


def project_markdown(cfg: dict, version: str) -> str:
    cards: list[tuple[str, str, str]] = []
    for index, project in enumerate(cfg.get("projects", [])[:3], start=1):
        cards.append(
            (
                f"project-{index:02d}",
                str(project.get("title", f"Project {index}")),
                str(project.get("repo", "#")),
            )
        )
    return stacked_linked_pictures(cards, version)


def _extract_marked_block(text: str, start: str, end: str) -> str:
    match = re.search(re.escape(start) + r".*?" + re.escape(end), text, flags=re.DOTALL)
    return match.group(0) if match else ""


def render_readme(cfg: dict) -> None:
    version = asset_version(cfg)
    template_path = ROOT / "README_TEMPLATE.md"
    if not template_path.exists():
        raise SystemExit(
            f"Missing {template_path.name}. Keep it in the repository root next to profile.json."
        )

    template = template_path.read_text(encoding="utf-8")
    rendered = (
        template.replace("{{VERSION}}", version)
        .replace("{{SOCIALS}}", social_markdown(cfg, version))
        .replace("{{PROJECTS}}", project_markdown(cfg, version))
        .replace("{{CTA}}", esc(cfg.get("cta", "Build something worth opening.")))
    )

    # A profile re-render should not temporarily erase the last successful blog update.
    readme_path = ROOT / "README.md"
    if readme_path.exists():
        previous = readme_path.read_text(encoding="utf-8")
        previous_blog = _extract_marked_block(previous, BLOG_START_MARKER, BLOG_END_MARKER)
        if previous_blog:
            rendered = re.sub(
                re.escape(BLOG_START_MARKER) + r".*?" + re.escape(BLOG_END_MARKER),
                lambda _: previous_blog,
                rendered,
                count=1,
                flags=re.DOTALL,
            )

    readme_path.write_text(rendered, encoding="utf-8")


def main() -> None:
    profile_path = ROOT / "profile.json"
    if not profile_path.exists():
        raise SystemExit(f"Missing {profile_path.name} in the repository root.")

    cfg = json.loads(profile_path.read_text(encoding="utf-8"))
    required = ["username", "name", "role", "tagline", "location"]
    missing = [key for key in required if not str(cfg.get(key, "")).strip()]
    if missing:
        raise SystemExit("Missing or empty keys in profile.json: " + ", ".join(missing))

    render_hero(cfg)
    render_socials(cfg)
    render_focus(cfg)
    render_stack(cfg)
    for index, project in enumerate(cfg.get("projects", [])[:3], start=1):
        render_project(cfg, project, index)
    render_readme(cfg)
    print("Rendered README.md and the gapless editorial SVG system, including social navigation.")


if __name__ == "__main__":
    main()
