"""サイト全体で使うデータ（試合の台帳・大会の台帳・採点結果）を読み、TOPと大会ページ用に整える。"""
import datetime as dt
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(os.environ.get("BRC_ROOT", pathlib.Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / "pipeline"))
from brc.engine import Game  # noqa: E402

DATA = ROOT / "data"
DIV_JA = {"HS": "高校の部", "UNIV": "大学の部"}
WD = "月火水木金土日"


def load(name, default=None):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


REG = load("registry.json", {"games": []})["games"]
COMPS = load("competitions.json", {})
PLAYERS = load("players.json", {})
DIVTEXT = load("divisions.json", {})
SCHEDULE = load("schedule.json", {})
INSIGHT_DIR = pathlib.Path(os.environ.get("BRC_INSIGHT", "/tmp/brc-insight"))

_cache = {}


def result(key):
    if key not in _cache:
        g = next(x for x in REG if x["key"] == key)
        d = json.loads((ROOT / g["src"]).read_text(encoding="utf-8"))
        game = Game(d)
        _cache[key] = (game.run(), game.log, d)
    return _cache[key]


def insight(key):
    p = INSIGHT_DIR / f"{key}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def nm(s):
    return (s or "").replace(" ", "")


def date_ja(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.year}.{d.month:02d}.{d.day:02d}（{WD[d.weekday()]}）"


def md_ja(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.month}.{d.day}（{WD[d.weekday()]}）"


def published():
    return sorted([g for g in REG if g.get("status") in ("published", "processed")],
                  key=lambda g: (g["date"], int(g.get("start", "0:0").split(":")[0]) * 60 + int(g.get("start", "0:0").split(":")[1])))


def score_line(key):
    r, _, _ = result(key)
    g, f = r["game"], r["final"]
    win = f["winner"]
    if win == g["home"]:
        return f"{g['home']} {f['home']}-{f['away']} {g['away']}"
    return f"{g['away']} {f['away']}-{f['home']} {g['home']}"


def grade(team, name):
    return (PLAYERS.get(team) or {}).get(name)


def rating(key, name):
    r, _, _ = result(key)
    return next((x for x in r["ratings"] if x["player"] == name), None)


def today_date():
    ps = published()
    return ps[-1]["date"] if ps else None


def today_games():
    d = today_date()
    out = []
    for g in published():
        if g["date"] != d:
            continue
        r, _, _ = result(g["key"])
        a = r["awards"]
        sc = {x["player"]: x["score"] for x in r["ratings"]}
        fm = (nm(a["fielder_mvp"]), sc[a["fielder_mvp"]]) if a.get("fielder_mvp") else None
        pm = (nm(a["pitcher_mvp"]), sc[a["pitcher_mvp"]]) if a.get("pitcher_mvp") else None
        state = "試合終了"
        if "コールド" in g.get("label", ""):
            state = g["label"].split("（")[-1].rstrip("）")
        out.append((g["label"].replace("（5回コールド）", "").replace("（7回コールド）", ""), score_line(g["key"]), state, fm, pm, "game:" + g["key"]))
    return out


POS_LONG = {"投": "投手", "捕": "捕手", "一": "一塁手", "二": "二塁手", "三": "三塁手", "遊": "遊撃手", "左": "左翼手", "中": "中堅手", "右": "右翼手", "指": "指名打者"}


def heroes():
    d = today_date()
    out = {}
    for div in ("HS", "UNIV"):
        games = [g for g in published() if g["date"] == d and g["div"] == div]
        if not games:
            continue
        bats, pits = [], []
        for g in games:
            r, _, _ = result(g["key"])
            for x in r["ratings"]:
                (pits if x["pitcher"] else bats).append((x["score"], x["raw_score"], x["wpa"], g, x))
        hs = []
        if bats:
            s, raw, w, g, x = max(bats, key=lambda t: (t[0], t[1], t[2]))
            gr = grade(x["team"], x["player"])
            meta = "・".join(v for v in (x["team"], gr, f"{x['order']}番" if x.get("order") else None, POS_LONG.get(x["pos"], x["pos"])) if v)
            rs = x.get("reasons") or []
            play = f"{rs[0]['text']}（{rs[0]['wpa']:+.2f}）" if rs and rs[0].get("wpa") is not None else (rs[0]["text"] if rs else "")
            hs.append(dict(kind="野手", name=nm(x["player"]), meta=meta, play=play, score=s, raw=raw, src=score_line(g["key"]), link="game:" + g["key"], img="batter"))
        good = [p for p in pits if p[0] >= 7.0]
        if good:
            s, raw, w, g, x = max(good, key=lambda t: (t[0], t[1], t[2]))
            gr = grade(x["team"], x["player"])
            meta = f"{x['team']}{('・' + gr) if gr else ''}　{x['stat']}"
            rs = x.get("reasons") or []
            play = rs[0]["text"] if rs else ""
            r_, _, _ = result(g["key"])
            if x["team"] != r_["final"]["winner"]:
                play += "（敗れたチームから）"
            hs.append(dict(kind="投手", name=nm(x["player"]), meta=meta, play=play, score=s, raw=raw, src=score_line(g["key"]), link="game:" + g["key"], img="pitcher"))
        out[DIV_JA[div]] = hs
    return out


def big_play():
    d = today_date()
    best = None
    for g in published():
        if g["date"] != d:
            continue
        for p in insight(g["key"]).get("plays", []):
            delta = p["after"] - p["before"]
            if best is None or delta > best[0]:
                best = (delta, p, g)
    if not best:
        return None
    delta, p, g = best
    title = f"{p['inn']}　{p['who']}の<br>{p['label']}" if p.get("who") and p["side"] == "攻撃" else f"{p['inn']}　{p['title']}"
    return dict(game=f"{g['label']}　{score_line(g['key'])}", title=title, delta=delta, team=p["team"],
                before=p["before"], after=p["after"], link="game:" + g["key"])


def comp_of_today():
    ps = published()
    return COMPS.get(ps[-1]["comp"]) if ps else None


def tournament_status(comp_id):
    c = COMPS[comp_id]
    out = []
    for dv in c["divisions"]:
        div = dv["div"]
        games = [g for g in published() if g["comp"] == comp_id and g["div"] == div]
        if not games:
            continue
        last = games[-1]["date"]
        lastg = [g for g in games if g["date"] == last]
        rnd = lastg[0]["round"].split("（")[0]
        winners = "・".join(result(g["key"])[0]["final"]["winner"] for g in lastg)
        if rnd == "決勝":
            line = f"決勝 終了（{winners}が優勝）"
        else:
            line = f"{md_ja(last)} {rnd} {len(lastg)}試合終了（{winners}が勝ち上がり）"
        nxt = [s for s in SCHEDULE.get(comp_id, {}).get(div, []) if s["status"] in ("scheduled", "live") and s["date"] > last]
        nxt.sort(key=lambda s: (s["date"], s["id"]))
        if nxt:
            day = nxt[0]["date"]
            cards = "／".join(f"{s['home']}−{s['away']}" for s in nxt if s["date"] == day)
            nline = f"次の試合：{md_ja(day)} {cards}"
        elif rnd == "決勝":
            nline = "全試合終了"
        else:
            nline = "次の試合：日程が決まり次第掲載"
        out.append((DIV_JA[div], line, nline))
    return out


def leaders(comp_id, div, n=3):
    agg = {}
    for g in published():
        if g["comp"] != comp_id or g["div"] != div:
            continue
        r, _, _ = result(g["key"])
        for x in r["ratings"]:
            k = (x["player"], x["team"])
            a = agg.setdefault(k, {"pt": 0.0, "wpa": 0.0, "sc": [], "best": (-99, x["pos"])})
            a["pt"] += x["raw_score"] - 6
            a["wpa"] += x["wpa"]
            a["sc"].append(x["raw_score"])
            if x["raw_score"] > a["best"][0]:
                a["best"] = (x["raw_score"], x["pos"])
    top = sorted(agg.items(), key=lambda kv: (-round(kv[1]["pt"], 2), -kv[1]["wpa"]))[:n]
    out = []
    for (name, team), a in top:
        gr = grade(team, name)
        gp = "・".join(v for v in (gr, a["best"][1]) if v)
        out.append((nm(name), gp, team, a["pt"], a["sc"]))
    return out


def div_info(comp_id):
    c = COMPS[comp_id]
    out = []
    for dv in sorted(c["divisions"], key=lambda d: 0 if d["div"] == "UNIV" else 1):
        div = dv["div"]
        if not any(g["comp"] == comp_id and g["div"] == div for g in published()):
            continue
        summ = (DIVTEXT.get(comp_id) or {}).get(div, {}).get("summary", "")
        out.append((DIV_JA[div], summ, leaders(comp_id, div)))
    return out


def days(comp_id):
    by = {}
    for g in published():
        if g["comp"] != comp_id:
            continue
        by.setdefault(g["date"], {}).setdefault(g["div"], []).append(g)
    out = []
    for d in sorted(by, reverse=True):
        dv = []
        for div in ("UNIV", "HS"):
            if div in by[d]:
                dv.append((DIV_JA[div], [(g["round"], score_line(g["key"]), g["key"], g.get("comment", "")) for g in by[d][div]]))
        out.append((date_ja(d), dv))
    return out
