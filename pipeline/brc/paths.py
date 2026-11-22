"""サイトのURL（ページの置き場所）を決める。ディレクトリマップ（Googleスプレッドシート）と同じ形にそろえる。

すべてサイトの一番上からのパス（先頭の / なし）で返す。リンクにするときは rel() で相対にする。
"""
import hashlib
import json
import pathlib
import posixpath

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITE_URL = "https://baseballreportcard.com"
DIV_SLUG = {"UNIV": "univ", "HS": "hs"}
_TEAMS = None


def _teams():
    global _TEAMS
    if _TEAMS is None:
        p = ROOT / "data" / "teams.json"
        _TEAMS = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _TEAMS


def team_slug(div, team):
    s = (_teams().get(div) or {}).get(team)
    return s or "t-" + hashlib.sha1(team.encode("utf-8")).hexdigest()[:6]


def comps():
    return json.loads((ROOT / "data" / "competitions.json").read_text(encoding="utf-8"))


def comp_dir(comp):
    return comp["path"]


def comp_page(comp):
    return comp["path"] + "index.html"


def family_page(comp):
    return f"tournaments/{comp['family']}/index.html"


def players_page(comp):
    return comp["path"] + "players/index.html"


def div_page(comp, div):
    return comp["path"] + f"{DIV_SLUG[div]}/index.html"


def team_page(comp, div, team):
    return comp["path"] + f"{DIV_SLUG[div]}/{team_slug(div, team)}/index.html"


def player_page(comp, div, team, pid):
    return comp["path"] + f"{DIV_SLUG[div]}/{team_slug(div, team)}/{pid}.html"


def day_page(comp, date):
    return comp["path"] + f"days/{date[5:7]}{date[8:10]}/index.html"


def game_page(comp, g):
    """g は台帳（registry）の1試合。キー末尾（1, qf1 など）を番号に使う。"""
    suffix = g["key"].rsplit("-", 1)[-1]
    return comp["path"] + f"days/{g['date'][5:7]}{g['date'][8:10]}/{DIV_SLUG[g['div']]}-{suffix}.html"


def game_url(comp, g):
    return f"{SITE_URL}/{game_page(comp, g)}"


def pretty(path):
    """公開用のURL（index.html を省く）。"""
    return path[: -len("index.html")] if path.endswith("index.html") else path


def rel(target, current):
    """current（このページ）から target へのリンク。外部URLやページ内リンクはそのまま。"""
    if not target or target.startswith(("http://", "https://", "#", "mailto:")):
        return target
    frag = ""
    if "#" in target:
        target, frag = target.split("#", 1)
        frag = "#" + frag
    base = posixpath.dirname(current) or "."
    return posixpath.relpath(target, base) + frag
