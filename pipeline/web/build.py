"""試合ページ（下層）のラフを、採点エンジンの実データから作る。PC版とスマホ版。"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__import__("os").environ.get("BRC_ROOT", pathlib.Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / "pipeline"))
from brc.engine import Game  # noqa: E402

import os as _os
URLS = json.loads(_os.environ.get("BRC_URLS", "{}"))  # サイト内のパス（先頭の / なし）。外部URLはそのまま
CUR = _os.environ.get("BRC_PAGE", "index.html")  # いま作っているページのパス


def R(path):
    """サイト内のパスを、いまのページからの相対リンクにする。"""
    from brc.paths import rel
    return rel(path, CUR)


def U(key):
    v = URLS.get(key)
    return R(v) if v else "#"


BATTER = U("img_batter")
PITCHER = U("img_pitcher")




RED, NAVY, INK, SUB, LINE = "#D7262E", "#0B1A36", "#14294F", "#5B6B86", "#C9D6EA"

REG = json.loads((ROOT / "data" / "registry.json").read_text(encoding="utf-8"))["games"]
COMPS = json.loads((ROOT / "data" / "competitions.json").read_text(encoding="utf-8"))
DIV_JA = {"HS": "高校の部", "UNIV": "大学の部"}
_WD = "月火水木金土日"


def _cfg(g):
    import datetime as _dt
    d_ = _dt.date.fromisoformat(g["date"])
    return dict(src=g["src"], summary=g.get("summary", ""), div=DIV_JA[g["div"]], label=g["label"], date=g["date"], comp=g["comp"],
                when=f"{d_.year}.{d_.month:02d}.{d_.day:02d}（{_WD[d_.weekday()]}）{g.get('start', '')}開始　{g.get('venue', '')}")


GAMES = {g["key"]: _cfg(g) for g in REG}
KEY = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in GAMES else REG[0]["key"]
CFG = GAMES[KEY]
d = json.loads((ROOT / CFG["src"]).read_text(encoding="utf-8"))
game = Game(d)
r = game.run()
L = game.log
g, f, a = r["game"], r["final"], r["awards"]
summary = CFG["summary"].strip()
COMP = COMPS.get(CFG["comp"], {})
GDIV = next(x["div"] for x in REG if x["key"] == KEY)
AWAY, HOME = g["away"], g["home"]
WIN = f["winner"]
LOSE = AWAY if WIN == HOME else HOME
WS = "home" if WIN == HOME else "away"
LS = "away" if WS == "home" else "home"
CG_NUM = '<col style="width: 56px">'
HAS_NUM = any(x.get("number") for x in r["ratings"])
CG = ('<colgroup><col style="width: 36px"><col style="width: 64px">' + (CG_NUM if HAS_NUM else '')
      + '<col style="width: 190px"><col style="width: 210px"><col style="width: 112px"><col style="width: 76px"><col></colgroup>')
WALKOFF = WIN == HOME and L and L[-1]["half"] == "bottom" and L[-1]["home_wp_before"] < 1 and L[-1]["inn"] >= 9 and f["home"] - f["away"] <= 4 and (L[-1]["type"] not in ("K", "OUT"))

# スコアボード（ない試合は記録から作る）
if "linescore" not in g:
    ls_ = {"away": [], "home": []}
    played_home = set()
    for x in L:
        side = "away" if x["half"] == "top" else "home"
        if side == "home":
            played_home.add(x["inn"])
    for e in d["events"]:
        if "sub" in e:
            continue
        side = "away" if e["half"] == "top" else "home"
        while len(ls_[side]) < e["inn"]:
            ls_[side].append(0)
        ls_[side][e["inn"] - 1] += e.get("runs", 0)
    n_inn = max(len(ls_["away"]), max(played_home or {0}))
    for side_ in ls_:
        ls_[side_] += [0] * (n_inn - len(ls_[side_]))
    g["linescore"] = {
        "away": [str(v) for v in ls_["away"][:n_inn]],
        "home": [(str(v) if (i + 1) in played_home else "x") for i, v in enumerate(ls_["home"][:n_inn])],
    }
    if WALKOFF:
        g["linescore"]["home"][-1] += "x"
SAME_DAY = []
for _g in REG:
    if _g.get("status") not in ("published", "processed"):
        continue
    SAME_DAY.append((_g["label"], _g.get("score", ""), _g["key"], _g["date"]))

# ---- 集計 ----
sub_order = [e["sub"]["player"] for e in d["events"] if "sub" in e]
HE = g.get("hits_errors")
hits = {"away": 0, "home": 0}
errs = {"away": 0, "home": 0}
for e in d["events"]:
    if "sub" in e:
        continue
    off = "away" if e["half"] == "top" else "home"
    de = "home" if off == "away" else "away"
    if e.get("type") in ("1B", "2B", "3B", "HR"):
        hits[off] += 1
    if e.get("type") == "E":
        errs[de] += 1

if HE:  # 公式の安打・失策があればそれを使う
    hits = {k: v[0] for k, v in HE.items()}
    errs = {k: v[1] for k, v in HE.items()}
wp = [L[0]["home_wp_before"] * 100] + [x["home_wp_after"] * 100 for x in L]
starts = {}
for i, x in enumerate(L):
    starts.setdefault((x["inn"], x["half"]), i)


from brc.engine import POS_JA  # noqa: E402
ROLE_JA = dict(POS_JA, PH="打", PR="走")


def pos_chain(x):
    """守備の変遷（例：二→投）。打席だけの代打は「打」。"""
    out = []
    for r_ in game.players.get(x["player"], {}).get("roles", []):
        j = ROLE_JA.get(r_)
        if j and (not out or out[-1] != j):
            out.append(j)
    return "→".join(out) or x["pos"]


def nm(s):
    return s.replace(" ", "")


def plink(x):
    from brc.ids import player_id
    from brc import paths
    if not COMP.get("path"):
        return nm(x["player"])
    href = R(paths.player_page(COMP, GDIV, x["team"], player_id(x["team"], x["player"])))
    return f'<a href="{href}" style="color: inherit; text-decoration: underline; text-decoration-color: #C9D6EA; text-underline-offset: 3px">{nm(x["player"])}</a>'


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


HANAMARU = ('<img src="' + U("img_hanamaru") + '" alt="" aria-hidden="true" style="position: absolute; top: {t}px; left: 50%; '
            'transform: translateX(-50%); width: {w}px; height: {w}px; opacity: 0.35">')
HANAMARU_AT = 8.5  # この点以上に花丸


def hanamaru(w, t):
    """ページごとに相対リンクを作り直す版（選手ページなど、1回の実行で複数ページを作るとき用）。"""
    return (f'<img src="{img_url("hanamaru")}" alt="" aria-hidden="true" style="position: absolute; top: {t}px; left: 50%; '
            f'transform: translateX(-50%); width: {w}px; height: {w}px; opacity: 0.35">')


def img_url(name):
    """バッジ画像のリンク（assets/badges/）。"""
    return R(f"assets/badges/{name}.png")


def face(score, size=18):
    """点数に応じた顔マーク（7.0以上＝にっこり、6.0〜6.5＝ふつう、6.0未満＝こまり顔）。"""
    name = "face-good" if score >= 7.0 else ("face-ok" if score >= 6.0 else "face-bad")
    alt = {"face-good": "よくできました", "face-ok": "及第点", "face-bad": "もう少し"}[name]
    return f'<img src="{img_url(name)}" alt="{alt}" title="{alt}" style="width: {size}px; height: {size}px; vertical-align: middle; flex: none">'


def badge(award, size=22):
    """表彰のバッジ（野手MVP・投手MVP＝MVP、敢闘賞）。"""
    if not award:
        return ""
    name = "kanto" if award == "敢闘賞" else "mvp"
    return f'<img src="{img_url(name)}" alt="{award}" title="{award}" style="width: {size}px; height: {size}px; vertical-align: middle; flex: none">'

# 試合を動かしたプレー（上位3）
TYPE_JA = {"HR": "本塁打", "3B": "三塁打", "2B": "二塁打", "1B": "ヒット"}
from brc.engine import LABELS as _LABELS  # noqa: E402
plays = []
for x in sorted(L, key=lambda x: -abs(x["home_wp_after"] - x["home_wp_before"]))[:3]:
    off = "away" if x["half"] == "top" else "home"
    deff = "home" if off == "away" else "away"
    b, af = x["home_wp_before"] * 100, x["home_wp_after"] * 100
    if off == "away":
        b, af = 100 - b, 100 - af
    who = nm(x["batter"] or x.get("runner") or "")
    if af >= b:  # 攻撃側が動かしたプレー
        best = next((q["text"] for q in r["ratings"] if q["player"] == x["batter"] for q in q.get("reasons_all", [])
                     if q["text"].startswith(f"{x['inn']}回")), None)
        label = best.split("の", 1)[1] if best and "の" in best else TYPE_JA.get(x["type"], "")
        if x.get("no_batter_credit"):
            label = "振り逃げと相手の失策"
        if not label:
            label = _LABELS.get(x["type"], "打席")
        if not who and x["type"] == "E":
            ERR_JA = {"P": "投手", "C": "捕手", "1B": "一塁手", "2B": "二塁手", "3B": "三塁手", "SS": "遊撃手", "LF": "左翼手", "CF": "中堅手", "RF": "右翼手"}
            label = f"相手{ERR_JA.get(x.get('error_by') or '', '')}の失策で得点"
        if x is L[-1] and WALKOFF and "サヨナラ" not in label:
            label += "でサヨナラ"
        plays.append({"inn": f"{x['inn']}回{'表' if x['half'] == 'top' else '裏'}", "who": who, "label": label,
                      "team": g[off], "side": "攻撃", "before": round(b), "after": round(af)})
    else:  # 守備側が動かしたプレー（併殺・ピンチでの三振など）
        plays.append({"inn": f"{x['inn']}回{'表' if x['half'] == 'top' else '裏'}", "who": who,
                      "label": _LABELS.get(x["type"], "凡退").replace("併殺打", "併殺") + "に打ち取る", "team": g[deff], "side": "守り",
                      "before": round(100 - b), "after": round(100 - af)})
for p in plays:  # 説明を整える
    p["label"] = p["label"].replace("ホームラン", "本塁打")
    if p["side"] == "守り":
        p["title"] = f"{p['who']}を{p['label']}"
    else:
        p["title"] = f"{p['who']}の{p['label']}" if p["who"] else p["label"]


def team_rows(side):
    rows = [x for x in r["ratings"] if x["side"] == side]
    bat = [x for x in rows if not x["pitcher"] or x["order"]]
    pit = [x for x in rows if x["pitcher"]]
    lineup_names = set(d["lineups"][side].values())

    def bkey(x):
        o = x["order"] or 10
        return (o, 0 if x["player"] in lineup_names else 1 + (sub_order.index(x["player"]) if x["player"] in sub_order else 9))
    bat.sort(key=bkey)
    start_p = d["lineups"][side]["P"]
    pit.sort(key=lambda x: -1 if x["player"] == start_p else (sub_order.index(x["player"]) if x["player"] in sub_order else 99))
    return bat, pit


def award_of(x):
    if x["player"] == a.get("fielder_mvp"):
        return "野手MVP"
    if x["player"] == a.get("pitcher_mvp"):
        return "投手MVP"
    if x["player"] == a.get("fighting_spirit"):
        return "敢闘賞"
    return ""


def wp_chart(width, height, compact=False):
    """勝ったチームが上、負けたチームが下。真ん中が互角。"""
    lose = AWAY if WIN == HOME else HOME
    ser = wp if WIN == HOME else [100 - v for v in wp]
    longest = max(len(WIN), len(lose))
    pad_l, pad_r, pad_t, pad_b = (max(96, longest * 15 + 18), 14, 16, 34) if not compact else (max(66, longest * 12 + 10), 8, 14, 30)
    W_, H_ = width - pad_l - pad_r, height - pad_t - pad_b
    n = len(ser) - 1
    fs = 11 if compact else 13

    def X(i):
        return pad_l + W_ * i / n

    def Y(v):
        return pad_t + H_ * (1 - v / 100)
    mid = Y(50)
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="勝利確率の推移。上が{WIN}、下が{lose}。動きが大きかったのは{'、'.join(p['inn'] + 'の' + p['title'] for p in plays)}" style="display: block">',
           f'<defs><clipPath id="up{int(compact)}"><rect x="{pad_l}" y="{pad_t}" width="{W_}" height="{mid - pad_t:.1f}"></rect></clipPath>'
           f'<clipPath id="dn{int(compact)}"><rect x="{pad_l}" y="{mid:.1f}" width="{W_}" height="{pad_t + H_ - mid:.1f}"></rect></clipPath></defs>']
    # 上下の地色
    out.append(f'<rect x="{pad_l}" y="{pad_t}" width="{W_}" height="{mid - pad_t:.1f}" fill="rgba(215,38,46,0.06)"></rect>')
    out.append(f'<rect x="{pad_l}" y="{mid:.1f}" width="{W_}" height="{pad_t + H_ - mid:.1f}" fill="rgba(92,127,186,0.06)"></rect>')
    for inn in range(1, 10):
        i = starts.get((inn, "top"))
        if i is None:
            continue
        x = X(i)
        out.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t + H_}" stroke="#24427A" stroke-width="1"></line>')
        nxt = starts.get((inn + 1, "top"), n)
        out.append(f'<text x="{(X(i) + X(nxt)) / 2:.1f}" y="{pad_t + H_ + 22}" fill="#9FB3D6" font-size="{fs}" text-anchor="middle">{inn}回</text>')
    out.append(f'<line x1="{pad_l}" y1="{mid:.1f}" x2="{pad_l + W_}" y2="{mid:.1f}" stroke="#9FB3D6" stroke-width="1" stroke-dasharray="4 4"></line>')
    # チーム名（上＝勝ち、下＝負け）と目盛り
    out.append(f'<text x="{pad_l - 8}" y="{pad_t + 14}" fill="#FFFFFF" font-size="{fs + 1}" font-weight="900" text-anchor="end">{WIN}</text>')
    out.append(f'<text x="{pad_l - 8}" y="{pad_t + 30 + (0 if compact else 2)}" fill="#F3B7BA" font-size="{fs - 1}" text-anchor="end">勝利100%</text>')
    out.append(f'<text x="{pad_l - 8}" y="{mid + 4:.1f}" fill="#9FB3D6" font-size="{fs - 1}" text-anchor="end">互角</text>')
    out.append(f'<text x="{pad_l - 8}" y="{pad_t + H_ - 18}" fill="#FFFFFF" font-size="{fs + 1}" font-weight="900" text-anchor="end">{lose}</text>')
    out.append(f'<text x="{pad_l - 8}" y="{pad_t + H_ - 2}" fill="#AFC4E6" font-size="{fs - 1}" text-anchor="end">勝利100%</text>')
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(ser))
    area = f"{X(0):.1f},{mid:.1f} " + pts + f" {X(n):.1f},{mid:.1f}"
    out.append(f'<polygon points="{area}" fill="rgba(215,38,46,0.55)" clip-path="url(#up{int(compact)})"></polygon>')
    out.append(f'<polygon points="{area}" fill="rgba(92,127,186,0.55)" clip-path="url(#dn{int(compact)})"></polygon>')
    out.append(f'<polyline points="{pts}" fill="none" stroke="#FFD23F" stroke-width="{2.5 if compact else 3}" stroke-linejoin="round"></polyline>')
    for k, x in enumerate(sorted(L, key=lambda x: -abs(x["home_wp_after"] - x["home_wp_before"]))[:3]):
        i = L.index(x) + 1
        cx, cy = X(i), Y(ser[i])
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{9 if compact else 11}" fill="{RED}" stroke="#FFFFFF" stroke-width="2"></circle>')
        out.append(f'<text x="{cx:.1f}" y="{cy + 4.5:.1f}" fill="#FFFFFF" font-size="{fs}" font-weight="900" text-anchor="middle">{k + 1}</text>')
    out.append("</svg>")
    return "".join(out)


import re as _re


def inning_rows(side):
    bat, pit = team_rows(side)
    rows = []
    seen = set()
    for x in bat + pit:
        if x["player"] in seen:
            continue
        seen.add(x["player"])
        row = [0.0] * 9
        for v, desc in game.plays.get(x["player"], []):
            m = _re.match(r"(\d+)回", desc)
            if m and int(m.group(1)) <= 9:
                row[int(m.group(1)) - 1] += v
        rows.append((x, [round(v * 100) for v in row]))
    return rows


def heat_bg(v):
    if not v:
        return "transparent"
    a = min(abs(v) / 30, 1) * 0.8 + 0.15
    return f"rgba(46,158,107,{a:.2f})" if v > 0 else f"rgba(215,38,46,{a:.2f})"


def inning_table(side, mobile):
    team = g[side]
    name_w = 86 if mobile else 150
    fs = 11 if mobile else 13
    head = "".join(f'<th scope="col" style="font-size: {fs - 1}px; font-weight: 700; color: {SUB}; text-align: center; padding: 4px 0">{i}{"" if mobile else "回"}</th>' for i in range(1, 10))
    body = ""
    for x, row in inning_rows(side):
        cells = "".join(
            f'<td style="text-align: center; padding: {4 if mobile else 7}px 0; border-radius: 4px; background-color: {heat_bg(v)}; color: {"#FFFFFF" if abs(v) >= 12 else INK}; font-size: {fs}px; font-weight: 700; font-variant-numeric: tabular-nums">{("+" if v > 0 else "") + str(v) if v else ""}</td>'
            for v in row)
        p = f'<span style="font-size: {10 if mobile else 12}px; font-weight: 700; color: {SUB}; margin-left: {3 if mobile else 8}px">{pos_chain(x)}</span>'
        raw = x["raw_score"]
        body += (f'<tr><th scope="row" style="text-align: left; font-size: {fs if mobile else fs + 1}px; font-weight: 900; color: {INK}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-right: 4px">{nm(x["player"])}{p}</th>{cells}'
                 f'<td style="text-align: center"><span class="hand" style="font-size: {18 if mobile else 22}px; color: {score_color(raw)}; line-height: 1">{raw:.1f}</span></td></tr>')
    return f"""<div style="margin-top: {14 if mobile else 18}px; padding-top: {12 if mobile else 16}px; border-top: 2px dashed {LINE}">
            <span style="display: block; font-size: {13 if mobile else 14}px; font-weight: 900; color: {RED}">回ごとの貢献度</span>
            <span style="display: block; font-size: 12px; color: {SUB}; margin: 2px 0 8px">数字はその回に動かした勝利確率（%）。緑はプラス、赤はマイナス。右端の採点は上限なし。</span>
            <table style="width: 100%; border-collapse: separate; border-spacing: 2px; table-layout: fixed">
              <colgroup><col style="width: {name_w}px">{'<col>' * 9}<col style="width: {40 if mobile else 64}px"></colgroup>
              <thead><tr><th scope="col" style="font-size: {fs - 1}px; color: {SUB}; text-align: left">選手</th>{head}<th scope="col" style="font-size: {fs - 1}px; color: {SUB}">採点</th></tr></thead>
              <tbody>{body}</tbody>
            </table>
          </div>"""


HEAD = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&amp;family=Yomogi&amp;display=swap">
<style>
body{{margin:0;background:#0B1A36}}
a{{color:#D7262E}}a:hover{{color:#A8141B}}
.paper{{background-color:#FBF8EF;background-image:repeating-linear-gradient(0deg,transparent 0,transparent 31px,#C9D6EA 31px,#C9D6EA 32px)}}
.hand{{font-family:'Yomogi',cursive}}
.marker{{background-image:linear-gradient(transparent 72%,#D7262E 72%,#D7262E 88%,transparent 88%)}}
.sheet{{background-color:#FBF8EF}}
.rc th{{font-size:12px;font-weight:700;color:#5B6B86;text-align:left;padding:8px 8px;border-bottom:2px solid #14294F;white-space:nowrap}}
.rc td{{padding:7px 8px;border-bottom:1px solid #C9D6EA;vertical-align:middle;font-size:14px}}
.rc tr:last-child td{{border-bottom:none}}
@media (max-width: 370px){{span.cm{{font-size:11.5px !important}}}}
</style>
</helmet>
"""
TAIL = """</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":{w},"height":{h}}}}}'>
class Component extends DCLogic {{
renderVals() {{ return {{}}; }}
}}
</script>
</body>
</html>
"""


def header(mobile):
    logo = 44 if mobile else 52
    nav = (f'<details style="position: relative"><summary aria-label="メニューを開く" style="list-style: none; width: 44px; height: 44px; border-radius: 10px; border: 2px solid #3D5C93; display: flex; align-items: center; justify-content: center; cursor: pointer"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"></path></svg></summary>'
           f'<nav aria-label="メインメニュー" style="position: absolute; right: 0; top: 52px; z-index: 20; display: flex; flex-direction: column; min-width: 200px; background-color: #0B1A36; border: 2px solid #3D5C93; border-radius: 10px; padding: 6px">'
           + "".join(f'<a href="{U(k)}" style="padding: 12px 14px; color: #FFFFFF; text-decoration: none; font-weight: 700">{t}</a>' for t, k in (("トップ", "top"), ("大会", "tournaments"), ("選手一覧", "players"), ("日付ごとの試合", "archive"), ("採点のしくみ", "rules"), ("通信簿について", "about")))
           + '<a href="https://x.com/BaseBalltannin" style="padding: 12px 14px; color: #F3B7BA; text-decoration: none; font-weight: 900">Xでフォロー</a></nav></details>'
           if mobile else
           '<nav aria-label="メインメニュー" style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px">'
           f'<a href="{U("tournaments")}" style="padding: 10px 14px; color: #FFFFFF; text-decoration: none; font-weight: 700; font-size: 15px">大会</a>'
           f'<a href="{U("players")}" style="padding: 10px 14px; color: #FFFFFF; text-decoration: none; font-weight: 700; font-size: 15px">選手</a>'
           f'<a href="{U("archive")}" style="padding: 10px 14px; color: #FFFFFF; text-decoration: none; font-weight: 700; font-size: 15px">日付</a>'
           f'<a href="{U("rules")}" style="padding: 10px 14px; color: #FFFFFF; text-decoration: none; font-weight: 700; font-size: 15px">採点のしくみ</a>'
           '<a href="https://x.com/BaseBalltannin" style="padding: 10px 20px; background-color: #D7262E; color: #FFFFFF; text-decoration: none; font-weight: 900; font-size: 15px; border-radius: 999px">Xでフォロー</a></nav>')
    return f"""  <header style="background-color: #0B1A36; border-bottom: 4px solid #D7262E">
    <div style="max-width: 1120px; margin: 0 auto; padding: {'10px 16px' if mobile else '14px 24px'}; display: flex; align-items: center; justify-content: space-between; gap: 12px">
      <a href="{U('top')}" aria-label="ベースボール通信簿 トップ" style="display: flex; align-items: center; gap: 10px; text-decoration: none">
        <span style="width: {logo}px; height: {logo}px; border-radius: 999px; background-color: #FFFFFF; border: 3px solid #14294F; box-shadow: 0 0 0 2px #FFFFFF; display: flex; align-items: center; justify-content: center; overflow: hidden; flex: none"><img src="{U('img_batter')}" alt="" aria-hidden="true" style="width: 82%; height: auto; margin-top: 18%"></span>
        <span style="display: flex; flex-direction: column; line-height: 1.15"><span style="font-size: {19 if mobile else 22}px; font-weight: 900; color: #FFFFFF">ベースボール<span style="border-bottom: 3px solid #D7262E">通信簿</span></span><span style="font-size: 11px; font-weight: 700; color: #9FB3D6; letter-spacing: 0.12em">BASEBALL REPORT CARD</span></span>
      </a>
      {nav}
    </div>
  </header>
"""


def footer(mobile):
    return f"""  <footer style="background-color: #081327; border-top: 4px solid #D7262E">
    <div style="max-width: 1120px; margin: 0 auto; padding: {'28px 16px 40px' if mobile else '36px 24px 48px'}; display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: #9FB3D6">
      <span style="font-size: 17px; font-weight: 900; color: #FFFFFF">ベースボール<span style="border-bottom: 3px solid #D7262E">通信簿</span></span>
      <span>運営：1000%　<a href="{U('about')}" style="color: #C9D6EA">ベースボール通信簿について</a>　<a href="{U('privacy')}" style="color: #C9D6EA">プライバシーポリシー</a></span>
      <span>勝利確率と採点は、簡易モデルによる試算です。選手の評価・実力を決めるものではありません。</span>
      <span>© 2026 1000%</span>
    </div>
  </footer>
"""


def h2(text, mobile):
    return f'<h2 style="margin: 0; font-size: {24 if mobile else 30}px; font-weight: 900; color: #FFFFFF"><span class="marker">{text}</span></h2>'


def scoreboard(mobile):
    cell = "padding: 6px 0; text-align: center; font-family: 'Noto Sans JP', sans-serif; font-weight: 900"
    inn_w = 26 if mobile else 44
    n_inn = max(9, len(g["linescore"]["away"])) if len(g["linescore"]["away"]) >= 9 else len(g["linescore"]["away"])
    head = "".join(f'<th scope="col" style="{cell}; width: {inn_w}px; color: #9FB3D6; font-size: {12 if mobile else 14}px">{i}</th>' for i in range(1, n_inn + 1))
    head += "".join(f'<th scope="col" style="{cell}; width: {inn_w + 6}px; color: #9FB3D6; font-size: {12 if mobile else 14}px">{k}</th>' for k in ("計", "安", "失"))
    rows = ""
    for side in ("away", "home"):
        ls = g["linescore"][side]
        tds = "".join(f'<td style="{cell}; color: #FFD23F; font-size: {17 if mobile else 24}px">{v}</td>' for v in ls)
        tds += f'<td style="{cell}; color: #FFFFFF; font-size: {19 if mobile else 26}px">{f[side]}</td>'
        tds += f'<td style="{cell}; color: #C9D6EA; font-size: {15 if mobile else 20}px">{hits[side]}</td>'
        tds += f'<td style="{cell}; color: #C9D6EA; font-size: {15 if mobile else 20}px">{errs[side]}</td>'
        win = "　<span style=\"color: #D7262E\">●</span>" if g[side] == WIN else ""
        rows += f'<tr><th scope="row" style="text-align: left; padding: 6px {6 if mobile else 12}px 6px 0; font-size: {14 if mobile else 18}px; font-weight: 900; color: #FFFFFF; white-space: nowrap">{g[side]}{win}</th>{tds}</tr>'
    return f"""<div style="padding: {'14px 12px' if mobile else '18px 22px'}; background-color: #0A1222; border: 6px solid #3D5C93; border-radius: 10px; box-shadow: inset 0 0 0 2px #0A1222, inset 0 0 0 4px #24427A; overflow-x: auto">
          <table style="width: 100%; border-collapse: collapse"><thead><tr><th scope="col" style="text-align: left"><span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0)">チーム</span></th>{head}</tr></thead><tbody>{rows}</tbody></table>
        </div>"""


def award_cards(mobile):
    items = [("野手MVP", a.get("fielder_mvp"), "7.0点以上の野手なし"),
             ("投手MVP", a.get("pitcher_mvp"), "7.0点以上の投手なし"),
             ("敢闘賞", a.get("fighting_spirit"), "8.0点以上の選手なし")]
    out = []
    for label, who, none in items:
        x = next((q for q in r["ratings"] if who and q["player"] == who), None)
        band = RED if label != "敢闘賞" else "#3D5C93"
        if not x and not mobile:
            out.append(f"""<div style="display: flex; align-items: center; gap: 16px; padding: 12px 16px; border: 2px dashed #3D5C93; border-radius: 8px; color: #C9D6EA">
              <span style="font-size: 16px; font-weight: 900; width: 96px; flex: none">{label}</span><span style="font-size: 15px; font-weight: 900">該当者なし</span><span style="font-size: 13px; color: #9FB3D6">{none}</span></div>""")
            continue
        if not x:
            out.append(f"""<div class="sheet" style="display: flex; flex-direction: column; border-radius: 8px; overflow: hidden; box-shadow: 0 6px 0 rgba(0,0,0,0.25); color: {INK}; border: 2px dashed #B8C3D6">
              <div style="padding: 8px 16px; background-color: #B8C3D6; color: #FFFFFF; font-size: 15px; font-weight: 900">{label}</div>
              <div style="flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 16px">
                <span style="font-size: 20px; font-weight: 900; color: {SUB}">該当者なし</span>
                <span style="font-size: 13px; color: {SUB}">{none}</span>
              </div></div>""")
            continue
        ico = PITCHER if x["pitcher"] else BATTER
        over = x["raw_score"] > 10
        role = f'{x["order"]}番・{pos_chain(x)}' if x["order"] and not x["pitcher"] else pos_chain(x)
        reason = x["reasons"][0]["text"] if x.get("reasons") else ""
        rw = (x["reasons"][0].get("wpa") or 0) if x.get("reasons") else 0
        if not mobile:
            out.append(f"""<div class="sheet" style="display: flex; align-items: stretch; border-radius: 8px; overflow: hidden; box-shadow: 0 6px 0 rgba(0,0,0,0.25); color: {INK}">
              <div style="flex: none; width: 128px; display: flex; flex-direction: column; justify-content: center; gap: 4px; padding: 14px 16px; background-color: {band}; color: #FFFFFF">
                <span style="display: inline-flex; padding: 3px; background-color: #FFFFFF; border-radius: 999px; align-self: flex-start; margin-bottom: 4px">{badge(label, 44)}</span><span style="font-size: 18px; font-weight: 900; white-space: nowrap">{label}</span><span style="font-size: 13px; font-weight: 700">{x["team"]}</span></div>
              <div style="flex: 1 1 auto; min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 12px 24px; padding: 14px 20px">
                <span style="display: flex; align-items: center; gap: 12px; flex: none">
                  <img src="{ico}" alt="" aria-hidden="true" style="width: 52px; height: auto; flex: none">
                  <span style="display: flex; flex-direction: column"><span style="font-size: 26px; font-weight: 900; line-height: 1.25; white-space: nowrap">{nm(who)}</span>
                  <span style="font-size: 14px; color: {SUB}; white-space: nowrap">{role}　{x['stat']}</span></span>
                </span>
                <span style="flex: 1 1 260px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 14px; background-color: #FFFFFF; border-left: 4px solid {band}; border-radius: 4px">
                  <span style="display: flex; flex-direction: column"><span style="font-size: 11px; font-weight: 900; color: {band}">決め手のプレー</span><span style="font-size: 16px; font-weight: 900">{reason}</span></span>
                  <span style="font-size: 16px; font-weight: 900; color: {band}; white-space: nowrap">{f"{rw * 100:+.0f}%" if rw else ""}</span>
                </span>
              </div>
              <div style="flex: none; width: 140px; display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative; padding: 10px 0">
                {HANAMARU.format(w=88, t=0) if x['score'] >= HANAMARU_AT else ''}
                <span class="hand" style="font-size: 56px; color: {band}; line-height: 1; position: relative">{x['score']:.1f}</span>
                {f'<span style="font-size: 11px; font-weight: 900; color: #FFFFFF; background-color: {RED}; padding: 1px 8px; border-radius: 999px; position: relative; white-space: nowrap">上限突破 {x["raw_score"]:.1f}</span>' if over else ''}
              </div>
            </div>""")
            continue
        out.append(f"""<div class="sheet" style="display: flex; flex-direction: column; border-radius: 8px; overflow: hidden; box-shadow: 0 6px 0 rgba(0,0,0,0.25); color: {INK}">
              <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 16px; background-color: {band}; color: #FFFFFF">
                <span style="display: inline-flex; align-items: center; gap: 8px"><span style="display: inline-flex; padding: 2px; background-color: #FFFFFF; border-radius: 999px">{badge(label, 30)}</span><span style="font-size: 15px; font-weight: 900; letter-spacing: 0.05em">{label}</span></span>
                <span style="font-size: 13px; font-weight: 700; white-space: nowrap">{x["team"]}</span>
              </div>
              <div style="display: flex; align-items: center; gap: 12px; padding: 14px 16px 10px">
                <img src="{ico}" alt="" aria-hidden="true" style="width: 52px; height: auto; flex: none">
                <span style="flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column">
                  <span style="font-size: {26 if mobile else 25}px; font-weight: 900; line-height: 1.25; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{nm(who)}</span>
                  <span style="font-size: 14px; font-weight: 700; color: {SUB}">{role}</span>
                </span>
                <span style="display: flex; flex-direction: column; align-items: center; flex: none; position: relative; min-width: 84px">
                  {HANAMARU.format(w=80, t=-12) if x['score'] >= HANAMARU_AT else ''}
                  <span class="hand" style="font-size: 52px; color: {band}; line-height: 1; position: relative">{x['score']:.1f}</span>
                  {f'<span style="font-size: 11px; font-weight: 900; color: #FFFFFF; background-color: {RED}; padding: 1px 8px; border-radius: 999px; position: relative; white-space: nowrap">上限突破 {x["raw_score"]:.1f}</span>' if over else ''}
                </span>
              </div>
              <div style="padding: 0 16px 14px; display: flex; flex-direction: column; gap: 8px; flex: 1">
                <span style="font-size: 14px">{x['stat']}</span>
                <span style="margin-top: auto; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 12px; background-color: #FFFFFF; border-left: 4px solid {band}; border-radius: 4px">
                  <span style="display: flex; flex-direction: column"><span style="font-size: 11px; font-weight: 900; color: {band}">決め手のプレー</span><span style="font-size: 15px; font-weight: 900">{reason}</span></span>
                  <span style="font-size: 15px; font-weight: 900; color: {band}; white-space: nowrap">{f"{rw * 100:+.0f}%" if rw else ""}</span>
                </span>
              </div>
            </div>""")
    cols = "1"
    return f'<div style="display: grid; grid-template-columns: repeat({cols}, minmax(0, 1fr)); gap: 14px">{"".join(out)}</div>'


def plays_list(mobile):
    out = []
    for k, p in enumerate(plays):
        delta = p["after"] - p["before"]
        out.append(f"""<div style="display: flex; align-items: center; gap: 14px; padding: {'12px 14px' if mobile else '14px 18px'}; background-color: #0A1222; border: 2px solid #24427A; border-radius: 8px">
              <span style="width: 32px; height: 32px; border-radius: 999px; background-color: #D7262E; color: #FFFFFF; font-weight: 900; display: flex; align-items: center; justify-content: center; flex: none">{k + 1}</span>
              <span style="flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 2px">
                <span style="font-size: 12px; color: #9FB3D6">{p['inn']}　{p['team']}の{p['side']}</span>
                <span style="font-size: {16 if mobile else 18}px; font-weight: 900; color: #FFFFFF">{p['title']}</span>
                <span style="font-size: 12px; color: #C9D6EA">{p['team']}の勝利確率 {p['before']}% → {p['after']}%</span>
              </span>
              <span style="font-size: {28 if mobile else 30}px; font-weight: 900; color: #FFD23F; flex: none">+{delta}%</span>
            </div>""")
    return "".join(out)


def score_color(s):
    return RED if s >= 6.0 else "#3D5C93"


def bar(w, max_w):
    width = min(abs(w) / 0.5, 1) * max_w
    col = "#2E9E6B" if w >= 0 else RED
    return (f'<span style="display: flex; align-items: center; gap: 6px"><span style="display: block; width: {max_w}px; height: 8px; position: relative; background-color: #E7ECF4; border-radius: 4px">'
            f'<span style="position: absolute; top: 0; bottom: 0; {"left: 50%" if w >= 0 else "right: 50%"}; width: {width / 2:.0f}px; background-color: {col}; border-radius: 4px"></span>'
            f'<span style="position: absolute; left: 50%; top: -2px; bottom: -2px; width: 1px; background-color: {SUB}"></span></span>'
            f'<span style="font-size: 12px; color: {SUB}; font-variant-numeric: tabular-nums">{w:+.2f}</span></span>')


def team_table(side, mobile):
    bat, pit = team_rows(side)
    team = g[side]
    res = "勝" if team == WIN else "敗"

    def mark(x):
        aw = award_of(x)
        return (f'<span style="display: inline-flex; align-items: center; gap: 3px; margin-left: 6px; vertical-align: middle">{badge(aw, 24)}'
                f'<span style="font-size: 11px; font-weight: 900; color: #FFFFFF; background-color: #D7262E; padding: 1px 8px; border-radius: 999px; white-space: nowrap">{aw}</span></span>') if aw else ""

    if mobile:
        def card(x, kind):
            pos = pos_chain(x)
            order = f'{x["order"]}番・' if x["order"] and kind == "bat" else ""
            cm = esc(x['comment'])
            for band in ("文句なしの花丸です。", "よくできました。", "及第点です。", "もう少し。", "今日は試練の日。"):
                if cm.startswith(band):
                    cm = cm[len(band):]
            for tail in ("次の試合でも主役を。", "次はもうひと押しを。", "次に期待しています。", "切り替えて次へ。"):
                if cm.endswith(tail) and len(cm) > len(tail):
                    cm = cm[: -len(tail)]
            cm = re.sub(r"で勝利確率を(\d+)%押し上げました。", r"で勝利確率+\1%。", cm)
            cm = re.sub(r"で勝利確率を(\d+)%落としました。", r"で勝利確率−\1%。", cm)
            cm = re.sub(r"この試合の合計では勝利確率\+(\d+)%の働きでした。", r"合計+\1%。", cm)
            wc = "#2E9E6B" if x['wpa'] >= 0.005 else (RED if x['wpa'] <= -0.005 else SUB)
            hl = "background-color: #FFF4D6; " if award_of(x) else ""
            return f"""<div style="{hl}display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; padding: 9px 2px; border-bottom: 1px solid {LINE}">
                <span style="flex: none; width: 52px; display: flex; flex-direction: column; align-items: center; gap: 2px"><span class="hand" style="font-size: 32px; color: {score_color(x['score'])}; line-height: 1">{x['score']:.1f}</span>{face(x['score'], 18)}{f'<span style="font-size: 9px; font-weight: 900; color: {RED}; white-space: nowrap">突破 {x["raw_score"]:.1f}</span>' if x['raw_score'] > 10 else ''}</span>
                <span style="flex: 1 1 0%; min-width: 0; display: flex; flex-direction: column; gap: 1px">
                  <span style="display: flex; align-items: center; justify-content: space-between; gap: 6px"><span style="font-size: 16px; font-weight: 900; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{plink(x)}{mark(x)}</span><span style="font-size: 12px; font-weight: 900; color: {wc}; white-space: nowrap; font-variant-numeric: tabular-nums">{x['wpa'] * 100:+.0f}%</span></span>
                  <span style="font-size: 12px; color: {SUB}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{order}{pos}　{x['stat']}</span>
                </span>
                <span class="cm" style="flex: 1 1 100%; font-size: 12px; line-height: 1.55; letter-spacing: -0.01em">{cm}</span>
              </div>"""
        body = "".join(card(x, "bat") for x in bat)
        pbody = "".join(card(x, "pit") for x in pit)
        return f"""<div class="sheet" style="padding: 16px 10px 6px; border-radius: 8px; color: {INK}; box-shadow: 0 6px 0 rgba(0,0,0,0.25); border-top: 6px solid #D7262E">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 4px"><h3 style="margin: 0; font-size: 20px; font-weight: 900">{team}の通信簿</h3><span style="font-size: 13px; font-weight: 900; color: #FFFFFF; background-color: {RED if res == '勝' else '#3D5C93'}; padding: 2px 12px; border-radius: 999px">{res}</span></div>
            <span style="display: flex; justify-content: space-between; margin: 10px 4px 0; font-size: 13px; font-weight: 900; color: {RED}"><span>打者</span><span style="font-size: 11px; color: {SUB}; font-weight: 700">右の％＝動かした勝利確率</span></span>
            {body}
            <span style="display: block; margin: 14px 4px 0; font-size: 13px; font-weight: 900; color: {RED}">投手</span>
            {pbody}
            {inning_table(side, True)}
            <div style="height: 10px"></div>
          </div>"""

    def row(x, kind):
        order = x["order"] if (x["order"] and kind == "bat") else ""
        hl = ' style="background-color: #FFF4D6"' if award_of(x) else ""
        return f"""<tr{hl}>
                <td style="color: {SUB}; text-align: center">{order}</td>
                <td style="white-space: nowrap">{pos_chain(x)}</td>
                {f'<td style="color: {SUB}">{x.get("number") or ""}</td>' if HAS_NUM else ''}
                <td><span style="display: block; font-weight: 900; font-size: 16px; white-space: nowrap">{plink(x)}{mark(x)}</span><span style="display: block; font-size: 12px; color: {SUB}; max-width: 15em; line-height: 1.5">{x['stat']}</span></td>
                <td style="white-space: nowrap">{bar(x['wpa'], 40)}</td>
                <td style="text-align: center; white-space: nowrap"><span style="display: inline-flex; align-items: center; gap: 6px">{face(x['score'], 22)}<span class="hand" style="font-size: 30px; color: {score_color(x['score'])}; line-height: 1">{x['score']:.1f}</span></span>{f'<span style="display: block; font-size: 10px; font-weight: 900; color: {RED}; white-space: nowrap">上限突破 {x["raw_score"]:.1f}</span>' if x['raw_score'] > 10 else ''}</td>
                <td style="width: 100%"><div class="cm" style="font-size: 13px; line-height: 1.6; min-width: 44em">{esc(x['comment'])}</div></td>
              </tr>"""
    thead = f'<tr><th scope="col">打順</th><th scope="col">守備</th>{'<th scope="col">背番号</th>' if HAS_NUM else ''}<th scope="col">選手・成績</th><th scope="col">貢献度</th><th scope="col" style="text-align: center">採点</th><th scope="col">担任からの一言</th></tr>'
    return f"""<div class="sheet" style="padding: 20px 22px; border-radius: 8px; color: {INK}; box-shadow: 0 6px 0 rgba(0,0,0,0.25); border-top: 6px solid #D7262E">
            <div style="display: flex; align-items: center; gap: 12px"><h3 style="margin: 0; font-size: 22px; font-weight: 900">{team}の通信簿</h3><span style="font-size: 13px; font-weight: 900; color: #FFFFFF; background-color: {RED if res == '勝' else '#3D5C93'}; padding: 2px 12px; border-radius: 999px">{res}</span></div>
            <div style="overflow-x: auto; margin-top: 10px"><table class="rc" style="width: 100%; border-collapse: collapse">
              <caption style="text-align: left; font-size: 14px; font-weight: 900; color: {RED}; padding: 6px 0">打者</caption>
              <thead>{thead}</thead><tbody>{''.join(row(x, 'bat') for x in bat)}</tbody>
            </table></div>
            <div style="overflow-x: auto; margin-top: 18px"><table class="rc" style="width: 100%; border-collapse: collapse">
              <caption style="text-align: left; font-size: 14px; font-weight: 900; color: {RED}; padding: 6px 0">投手</caption>
              <thead>{thead.replace('打順', '').replace('<th scope="col"></th>', '<th scope="col"><span style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0)">打順</span></th>')}</thead><tbody>{''.join(row(x, 'pit') for x in pit)}</tbody>
            </table></div>
            {inning_table(side, False)}
          </div>"""


def page(mobile):
    W = 390 if mobile else None
    gap = 36 if mobile else 52
    wrap_style = f"width: {W}px; " if mobile else ""
    order = [s for s in ("home", "away") if g[s] == WIN] + [s for s in ("home", "away") if g[s] != WIN]
    crumbs = " <span style=\"color: #5C7FBA\">›</span> ".join(
        f'<a href="{U(k)}" style="color: #C9D6EA; text-decoration: none">{c}</a>' for c, k in (("大会", "tournaments"), (COMP.get("family_name", COMP.get("short", "大会")), "family"), (str(COMP.get("year", "")), "tournament"), (f'{int(CFG["date"][5:7])}.{int(CFG["date"][8:10])}', "day:" + CFG["date"]))) + ' <span style="color: #5C7FBA">›</span> <span style="color: #FFFFFF">' + CFG["label"] + '</span>'
    return f"""<div style="{wrap_style}min-height: 100vh; background-color: #0B1A36; background-image: radial-gradient(circle at 50% 0, #1A3260 0, #0B1A36 60%); color: #FFFFFF; font-family: 'Noto Sans JP', sans-serif; line-height: 1.6">
{header(mobile)}  <main style="max-width: 1120px; margin: 0 auto; padding: {'18px 16px 56px' if mobile else '24px 24px 72px'}; display: flex; flex-direction: column; gap: {gap}px">
    <section aria-label="試合の結果" style="display: flex; flex-direction: column; gap: 16px">
      <nav aria-label="パンくずリスト" style="font-size: 13px">{crumbs}</nav>
      <div style="display: flex; flex-direction: column; gap: 4px">
        <span style="font-size: 13px; color: #9FB3D6">{COMP.get('formal', '')} {CFG['label']}</span>
        <span style="font-size: 13px; color: #9FB3D6">{CFG['when']}</span>
        <h1 style="margin: 6px 0 0; font-size: {26 if mobile else 40}px; font-weight: 900; line-height: 1.3"><span class="marker">{WIN} 対 {LOSE} の通信簿</span></h1>
        <span style="font-size: {20 if mobile else 26}px; font-weight: 900; color: #FFD23F; margin-top: 6px">{WIN} {f[WS]}-{f[LS]} {LOSE}{'（サヨナラ）' if WALKOFF else ''}</span>
      </div>
      {scoreboard(mobile)}
      <div class="paper" style="padding: 16px 18px; border-radius: 8px; color: {INK}; font-size: {14 if mobile else 16}px; line-height: 2; box-shadow: 0 6px 0 rgba(0,0,0,0.25)">{summary}</div>
    </section>
    <section aria-label="表彰" style="display: flex; flex-direction: column; gap: 16px">
      {h2('MVP', mobile)}
      {award_cards(mobile)}
    </section>
    <section aria-label="勝利確率の推移" style="display: flex; flex-direction: column; gap: 16px">
      {h2('勝利確率の推移', mobile)}
      <div style="padding: {'12px 8px' if mobile else '18px 22px'}; background-color: #0A1222; border: 6px solid #3D5C93; border-radius: 10px; box-shadow: inset 0 0 0 2px #0A1222, inset 0 0 0 4px #24427A">
        {wp_chart(358 if mobile else 1040, 220 if mobile else 300, compact=mobile)}
      </div>
      <h3 style="margin: 8px 0 0; font-size: {17 if mobile else 19}px; font-weight: 900; color: #FFFFFF">試合を動かしたプレー</h3>
      <div style="display: flex; flex-direction: column; gap: 10px">{plays_list(mobile)}</div>
    </section>
    <section aria-label="通信簿" style="display: flex; flex-direction: column; gap: 16px">
      {h2('通信簿（全選手の採点）', mobile)}
      <span style="font-size: 13px; color: #C9D6EA">採点＝6.0（及第点）＋勝利確率をどれだけ動かしたか×12。0.5点刻み・10点満点。<a href="{U('rules')}" style="color: #F3B7BA; font-weight: 700">採点のしくみ →</a></span>
      {''.join(team_table(s, mobile) for s in order)}
    </section>
    <section aria-label="この試合をシェア" style="display: flex; flex-direction: column; gap: 14px">
      {h2('カードとシェア', mobile)}
      <div style="display: flex; flex-wrap: wrap; gap: 12px">
        <a href="{U('x_post')}" style="padding: 12px 22px; background-color: #D7262E; color: #FFFFFF; text-decoration: none; font-weight: 900; border-radius: 999px">Xの投稿を見る</a>
        <a href="{U('card_win')}" style="padding: 12px 22px; border: 2px solid #3D5C93; color: #FFFFFF; text-decoration: none; font-weight: 700; border-radius: 999px">{WIN}のカード画像</a>
        <a href="{U('card_lose')}" style="padding: 12px 22px; border: 2px solid #3D5C93; color: #FFFFFF; text-decoration: none; font-weight: 700; border-radius: 999px">{LOSE}のカード画像</a>
      </div>
    </section>
    <section aria-label="同じ日の試合" style="display: flex; flex-direction: column; gap: 14px">
      {h2('同じ日の試合', mobile)}
      <div style="display: grid; grid-template-columns: repeat({1 if mobile else 3}, minmax(0, 1fr)); gap: 12px">
        {''.join(f'<a href="{U("game:" + key)}" class="paper" style="display: flex; flex-direction: column; gap: 4px; padding: 14px 16px; border-radius: 8px; text-decoration: none; color: {INK}; box-shadow: 0 6px 0 rgba(0,0,0,0.25)"><span style="font-size: 12px; font-weight: 700; color: {SUB}">{k}</span><span style="font-size: 17px; font-weight: 900">{v}</span></a>' for k, v, key, dt in SAME_DAY if key != KEY and dt == CFG["date"])}
      </div>
      <a href="{U('top')}" style="align-self: flex-start; font-size: 14px; font-weight: 700; color: #F3B7BA">トップへ戻る →</a>
    </section>
  </main>
{footer(mobile)}</div>
"""


out = pathlib.Path(_os.environ.get("OUT", "/tmp/brc-build"))
out.mkdir(parents=True, exist_ok=True)
out.mkdir(parents=True, exist_ok=True)
H_PC, H_SP = (int(x) for x in (sys.argv[2:4] if len(sys.argv) > 3 else (4000, 8000)))
pc, sp = f"{KEY}.pc", f"{KEY}.sp"
_ins = pathlib.Path(_os.environ.get("BRC_INSIGHT", "/tmp/brc-insight"))
_ins.mkdir(parents=True, exist_ok=True)
(_ins / f"{KEY}.json").write_text(json.dumps({"plays": plays, "walkoff": bool(WALKOFF)}, ensure_ascii=False), encoding="utf-8")
(out / f"{pc}.dc.html").write_text(HEAD.format(title=f"試合ページ（PC）{WIN}対{LOSE}") + page(False) + TAIL.format(w=1280, h=H_PC))
(out / f"{sp}.dc.html").write_text(HEAD.format(title=f"試合ページ（スマホ）{WIN}対{LOSE}") + page(True) + TAIL.format(w=390, h=H_SP))
print(plays)
print("ok")
