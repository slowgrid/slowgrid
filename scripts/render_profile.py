#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)
RENDERER_VERSION = "editorial-complete-1"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def safe_url(url: str) -> str:
    value = str(url).strip()
    if re.match(r"^(https://|mailto:)", value):
        return value
    return "#"


def wrap(text: object, width: int) -> list[str]:
    return textwrap.wrap(
        str(text),
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]


def display_url(value: str, username: str) -> str:
    value = re.sub(r"^https?://", "", str(value).strip(), flags=re.IGNORECASE)
    value = re.sub(r"^www\.", "", value, flags=re.IGNORECASE).rstrip("/")
    return value or f"github.com/{username}"


def asset_version(cfg: dict) -> str:
    raw = json.dumps(cfg, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"{RENDERER_VERSION}:{raw}".encode("utf-8")).hexdigest()[:10]


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
      .sans {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
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

    tagline_lines = wrap(tagline, 22)[:3]

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
            f'<text x="982" y="{170 + i * 46}" class="serif" fill="{right_ink}" font-size="33" letter-spacing="-.6px">{esc(line)}</text>'
            for i, line in enumerate(tagline_lines)
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
        return svg_document(1400, 440, f"{name} - {role}", f"GitHub profile introduction for {name}.", body)

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
            value_lines = wrap(item.get("value", ""), 25)[:2]
            value_markup = "".join(
                f'<text x="{x}" y="{156 + row * 34}" class="sans" fill="{p["ink"]}" font-size="25" font-weight="650" letter-spacing="-.5px">{esc(line)}</text>'
                for row, line in enumerate(value_lines)
            )
            columns.append(f'''
  <text x="{x}" y="116" class="serif" fill="{p['muted']}" font-size="21">0{index}</text>
  <text x="{x + 52}" y="115" class="sans label" fill="{p['muted']}">{esc(label)}</text>
  {value_markup}
''')

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
            markup.append(f'''
  <text x="{x}" y="104" class="serif" fill="{p['muted']}" font-size="18">0{index}</text>
  <text x="{x + 42}" y="103" class="sans label" fill="{p['muted']}">{esc(str(group).upper())}</text>
  <line x1="{x}" y1="118" x2="{x + 256}" y2="118" stroke="{accent}" stroke-width="2"/>
  {''.join(item_lines)}
''')

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
        return svg_document(1400, 338, "Selected technology stack", "A curated technology stack grouped by area.", body)

    write_themed_asset("stack", build("light"), build("dark"))


def render_project(cfg: dict, project: dict, index: int) -> None:
    accent = str(cfg.get("accent", "#b54a36"))
    title = str(project.get("title", f"PROJECT {index}")).strip()
    subtitle = str(project.get("subtitle", "SELECTED WORK")).strip().upper()
    description = str(project.get("description", "")).strip()
    tags = [str(value).strip() for value in project.get("tags", []) if str(value).strip()][:5]

    title_lines = wrap(title, 24)[:2]
    desc_lines = wrap(description, 58)[:3]
    tags_line = "  /  ".join(tags)

    def build(theme: str) -> str:
        p = palette(theme, accent)
        inverse = index % 2 == 0
        bg = p["inverse_bg"] if inverse else p["bg"]
        ink = p["inverse_ink"] if inverse else p["ink"]
        muted = p["inverse_muted"] if inverse else p["muted"]
        rule = p["inverse_rule"] if inverse else p["rule"]

        title_y = 112 if len(title_lines) == 1 else 94
        title_markup = "".join(
            f'<text x="306" y="{title_y + row * 46}" class="sans" fill="{ink}" font-size="42" font-weight="720" letter-spacing="-1.5px">{esc(line)}</text>'
            for row, line in enumerate(title_lines)
        )
        desc_markup = "".join(
            f'<text x="790" y="{119 + row * 28}" class="sans" fill="{ink}" font-size="18" font-weight="470" letter-spacing="-.15px">{esc(line)}</text>'
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
        return svg_document(1400, 270, f"Project {index}: {title}", description or f"Selected project {title}.", body)

    write_themed_asset(f"project-{index:02d}", build("light"), build("dark"))


def markdown_links(cfg: dict) -> str:
    values: list[tuple[str, str]] = []
    username = str(cfg.get("username", "")).strip().lstrip("@")
    if username:
        values.append(("GitHub", f"https://github.com/{username}"))
    if cfg.get("linkedin"):
        values.append(("LinkedIn", str(cfg["linkedin"])))
    if cfg.get("email"):
        values.append(("Email", f"mailto:{cfg['email']}"))
    if cfg.get("website"):
        values.append(("Website", str(cfg["website"])))
    return " &nbsp;&nbsp;·&nbsp;&nbsp; ".join(
        f'<a href="{esc(safe_url(url))}"><strong>{esc(label)}</strong></a>'
        for label, url in values
    )


def picture(asset: str, alt: str, version: str, width: str = "100%") -> str:
    return f'''<picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/{asset}-dark.svg?v={version}" />
    <source media="(prefers-color-scheme: light)" srcset="./assets/{asset}-light.svg?v={version}" />
    <img src="./assets/{asset}.svg?v={version}" width="{width}" alt="{esc(alt)}" />
  </picture>'''


def project_markdown(cfg: dict, version: str) -> str:
    blocks: list[str] = []
    for index, project in enumerate(cfg.get("projects", [])[:3], start=1):
        url = esc(safe_url(project.get("repo", "#")))
        alt = esc(project.get("title", f"Project {index}"))
        blocks.append(
            f'''<a href="{url}">
  {picture(f"project-{index:02d}", alt, version)}
</a>'''
        )
    return "\n\n".join(blocks)


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
        .replace("{{LINKS}}", markdown_links(cfg))
        .replace("{{PROJECTS}}", project_markdown(cfg, version))
        .replace("{{CTA}}", esc(cfg.get("cta", "Build something worth opening.")))
    )
    (ROOT / "README.md").write_text(rendered, encoding="utf-8")


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
    render_focus(cfg)
    render_stack(cfg)
    for index, project in enumerate(cfg.get("projects", [])[:3], start=1):
        render_project(cfg, project, index)
    render_readme(cfg)
    print("Rendered README.md and the complete editorial SVG system.")


if __name__ == "__main__":
    main()
