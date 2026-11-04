"""The installed app's chrome has to be the app's design system.

CLAUDE.md is explicit: the UI design system is Depot, and "the
marcdeller.com house header and palette do NOT apply to the app UI. They do
apply to the README." `depot.css` repeats it at the top of the file, naming
the colour: "header and #1e73be palette do NOT apply here".

`site.webmanifest` set `theme_color` to #1e73be, the exact colour that line
excludes, and `background_color` to white where Depot's background is
concrete. Nothing contradicted it, because `base.html` carries its own
`<meta name="theme-color">` with the right values and that is what a browser
tab uses. The manifest only takes effect once the app is installed, so the
installed app would have shown house-brand chrome and a white splash while
every other surface was Depot (F68).

Three places hold the same colour now: the CSS variable, the meta tag and
the manifest. This checks they agree rather than that each is a particular
string, on the reasoning that fixed F54 and F55.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CSS = ROOT / "nobble" / "app" / "static" / "css" / "depot.css"
BASE = ROOT / "nobble" / "app" / "templates" / "base.html"
MANIFEST = ROOT / "nobble" / "app" / "static" / "img" / "site.webmanifest"

# The colour the house style reserves for the README and the blog mark.
HOUSE_BLUE = "#1e73be"


def _depot_background(dark: bool = False) -> str:
    """Depot's --bg, from the stylesheet rather than from memory."""
    text = CSS.read_text()
    if dark:
        # The opening brace is what distinguishes the rule from the prose
        # about it. depot.css's header comment quotes the query in full,
        # including the @media prefix, so both a bare "prefers-color-scheme:
        # dark" anchor and the full query matched the comment and found the
        # light --bg twenty lines below it.
        block = text[text.index("@media (prefers-color-scheme: dark) {"):]
    else:
        block = text[text.index(":root"):]
    match = re.search(r"--bg:\s*(#[0-9A-Fa-f]{3,8})", block)
    assert match, "depot.css no longer declares --bg"
    return match.group(1).lower()


def _meta_theme_colours() -> dict[str, str]:
    out = {}
    for match in re.finditer(
            r'<meta name="theme-color" content="(#[0-9A-Fa-f]{3,8})"'
            r'\s+media="\(prefers-color-scheme:\s*(\w+)\)"', BASE.read_text()):
        out[match.group(2)] = match.group(1).lower()
    return out


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def test_the_manifest_does_not_use_the_house_palette():
    """The defect. A colour the design system names as excluded must not
    be the one the installed app paints its chrome with."""
    manifest = _manifest()
    for field in ("theme_color", "background_color"):
        assert manifest[field].lower() != HOUSE_BLUE, (
            f"{field} is the marcdeller.com blue, which depot.css says does "
            "not apply to the app UI"
        )


def test_the_manifest_and_the_meta_tag_agree_in_light_mode():
    """Two declarations of the same thing, one used by the tab and one by
    the installed app. Equal today is not the point; one value feeding
    both is, and that is what this asserts by comparing them."""
    assert _manifest()["theme_color"].lower() == _meta_theme_colours()["light"]


def test_both_come_from_depot_rather_than_from_anywhere_else():
    light = _depot_background()
    assert _meta_theme_colours()["light"] == light
    assert _manifest()["theme_color"].lower() == light


def test_the_dark_meta_colour_is_depot_dark():
    assert _meta_theme_colours()["dark"] == _depot_background(dark=True)


def test_the_splash_background_is_not_white():
    """Depot's background is concrete. A white splash is the one surface a
    reader sees before any stylesheet loads, so it is the first thing that
    would look like a different product."""
    manifest = _manifest()
    assert manifest["background_color"].lower() not in ("#fff", "#ffffff")
    assert manifest["background_color"].lower() == _depot_background()


def test_the_manifest_icons_exist_where_it_says():
    """The paths are absolute and served under /static/img/, which is not
    where the icon skill's template puts them."""
    for icon in _manifest()["icons"]:
        source = icon["src"]
        assert source.startswith("/static/"), source
        path = (ROOT / "nobble" / "app" / "static"
                / source[len("/static/"):].lstrip("/"))
        assert path.exists(), f"{source} is declared and not on disk"


def test_the_root_copy_matches_the_served_copy():
    """The icon skill keeps a master at the project root and a served copy
    under static. Two copies drift, and the root one is what a later
    regeneration would read as the current state."""
    root_copy = ROOT / "site.webmanifest"
    if not root_copy.exists():
        return
    assert json.loads(root_copy.read_text()) == _manifest(), (
        "the root site.webmanifest and the served one disagree"
    )


def test_the_house_blue_is_still_absent_from_the_app_css():
    """It appears in depot.css only in the comment saying it does not
    apply. If it appears anywhere else, the exclusion has stopped holding."""
    text = CSS.read_text()
    for number, line in enumerate(text.splitlines(), start=1):
        if HOUSE_BLUE in line.lower():
            assert "do NOT apply" in line or line.strip().startswith(("*", "/*", "//")), (
                f"depot.css:{number} uses the house blue: {line.strip()}"
            )
