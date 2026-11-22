"""選手まわりのページを作る。

  python players.py players        … 選手1人1ページ（players/<id>.html）。OUT/players/ に PC・スマホ版と manifest.json
  python players.py comp <大会ID>  … 大会の選手一覧（ランキング）と部ごとの一覧（大学ごと・高校ごとの表）。OUT/comp-<大会ID>/ に書く
"""
import json
import os
import pathlib
import sys

_MODE = sys.argv[1] if len(sys.argv) > 1 else "players"
_CID = sys.argv[2] if len(sys.argv) > 2 else ""
sys.argv = ["build.py", "__first__"]
import build as B  # noqa: E402
import data as D  # noqa: E402
from brc.ids import player_id  # noqa: E402

INK, SUB, RED, LINE = B.INK, B.SUB, B.RED, B.LINE
OUTROOT = pathlib.Path(os.environ.get("OUT", "/tmp/brc-build"))
AWARD_JA = {"fielder_mvp": "野手MVP", "pitcher_mvp": "投手MVP", "fighting_spirit": "敢闘賞"}
DIV_SLUG = {"UNIV": "univ", "HS": "hs"}
DIV_SHORT = {"UNIV": "大学", "HS": "高校"}
POS_LONG = {"投": "投手", "捕": "捕手", "一": "一塁", "二": "二塁", "三": "三塁", "遊": "遊撃", "左": "左翼", "中": "中堅", "右": "右翼",
            "指": "指名打者", "打": "代打", "走": "代走"}


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def collect():
    ps = {}
    for g in D.published():
        r, _, _ = D.result(g["key"])
        comp = D.COMPS.get(g["comp"], {})
        aw = {v: AWARD_JA[k] for k, v in r["awards"].items() if v and k in AWARD_JA}
        f = r["final"]
        for x in r["ratings"]:
            pid = player_id(x["team"], x["player"])
            p = ps.setdefault(pid, {"pid": pid, "name": D.nm(x["player"]), "raw": x["player"], "team": x["team"],
                                    "div": g["div"], "comp": g["comp"], "games": [], "pitcher": False})
            p["pitcher"] = p["pitcher"] or bool(x["pitcher"])
            opp = r["game"]["home"] if x["side"] == "away" else r["game"]["away"]
            mine, theirs = f[x["side"]], f["away" if x["side"] == "home" else "home"]
            p["games"].append({"key": g["key"], "date": g["date"], "comp": comp.get("short", ""), "div": D.DIV_JA.get(g["div"], ""),
                               "round": g.get("round", ""), "opp": opp, "res": "勝" if mine > theirs else ("敗" if mine < theirs else "分"),
                               "score": f"{mine}-{theirs}", "pos": x["pos"], "stat": x["stat"], "pt": x["score"], "raw": x["raw_score"],
                               "wpa": x["wpa"], "comment": x.get("comment", ""), "award": aw.get(x["player"])})
    for p in ps.values():
        p["games"].sort(key=lambda q: q["date"], reverse=True)
        p["total"] = sum(q["raw"] - 6 for q in p["games"])
        p["wpa"] = sum(q["wpa"] for q in p["games"])
        p["best"] = max(q["raw"] for q in p["games"])
        p["grade"] = D.grade(p["team"], p["raw"])
        p["awards"] = [q["award"] for q in p["games"] if q["award"]]
        pos = {}
        for q in p["games"]:
            pos[q["pos"]] = pos.get(q["pos"], 0) + 1
        p["pos"] = POS_LONG.get("投" if p["pitcher"] else (max(pos, key=pos.get) if pos else ""), "")
    return ps


def chip(text, bg=RED):
    return f'<span style="font-size: 12px; font-weight: 900; color: #FFFFFF; background-color: {bg}; padding: 2px 10px; border-radius: 999px; white-space: nowrap">{text}</span>'


def shell(mobile, crumbs, body, width=960):
    wrap = "width: 390px; " if mobile else ""
    return f"""<div style="{wrap}min-height: 100vh; background-color: #0B1A36; color: #FFFFFF; font-family: 'Noto Sans JP', sans-serif; line-height: 1.6">
{B.header(mobile)}  <main style="max-width: {width}px; margin: 0 auto; padding: {'18px 16px 56px' if mobile else '28px 24px 72px'}; display: flex; flex-direction: column; gap: 22px">
    <nav aria-label="パンくずリスト" style="font-size: 13px; color: #9FB3D6">{crumbs}</nav>
    {body}
  </main>
{B.footer(mobile)}</div>
"""


def crumb_html(items):
    out = []
    for label, href in items:
        out.append(f'<a href="{href}" style="color: #C9D6EA; text-decoration: none">{esc(label)}</a>' if href else f'<span style="color: #FFFFFF">{esc(label)}</span>')
    return ' <span style="color: #5C7FBA">›</span> '.join(out)


# ---------- 選手1人のページ（players/<id>.html, depth 1） ----------

def player_page(p, mobile):
    comp = D.COMPS.get(p["comp"], {})
    cdir = "../" + comp.get("page", "index.html")[:-5] + "/players/"
    crumbs = crumb_html([("大会", None), (comp.get("short", ""), "../" + comp.get("page", "index.html")), ("選手一覧", cdir + "index.html"),
                         (DIV_SHORT.get(p["div"], ""), cdir + DIV_SLUG.get(p["div"], "") + ".html"), (p["name"], None)])
    sub = "・".join(v for v in (p["team"], p["grade"], p["pos"]) if v)
    stats = [("出場", f'{len(p["games"])}<span style="font-size: 14px">試合</span>'),
             ("大会通算", f'{p["total"]:+.1f}'), ("最高", f'{p["best"]:.1f}')]
    stat_html = "".join(f'<div style="flex: 1; min-width: 90px; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; font-weight: 700; color: {SUB}">{k}</span>'
                        f'<span class="hand" style="font-size: {34 if mobile else 40}px; color: {RED}; line-height: 1.1">{v}</span></div>' for k, v in stats)
    awards = "".join(chip(a) for a in p["awards"])
    rows = ""
    for q in p["games"]:
        head = f'{D.md_ja(q["date"])}　{q["comp"]} {q["div"]} {q["round"]}'
        res = chip(q["res"], RED if q["res"] == "勝" else "#3D5C93")
        aw = chip(q["award"], "#E2B448") if q["award"] else ""
        over = f'<span style="display: block; font-size: 10px; font-weight: 900; color: {RED}">上限突破 {q["raw"]:.1f}</span>' if q["raw"] > 10 else ""
        rows += f"""<a href="../games/{q['key']}.html" style="display: flex; gap: {12 if mobile else 18}px; align-items: flex-start; padding: 14px 4px; border-bottom: 1px solid {LINE}; color: {INK}; text-decoration: none">
          <span style="flex: none; width: {56 if mobile else 72}px; text-align: center"><span class="hand" style="font-size: {34 if mobile else 40}px; color: {B.score_color(q['pt'])}; line-height: 1">{q['pt']:.1f}</span>{over}</span>
          <span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px">
            <span style="font-size: 12px; color: {SUB}">{esc(head)}</span>
            <span style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px"><span style="font-size: {16 if mobile else 18}px; font-weight: 900">対 {esc(q['opp'])}　{q['score']}</span>{res}{aw}</span>
            <span style="font-size: 13px; color: {SUB}">{esc(q['pos'])}　{esc(q['stat'])}　勝利確率 {q['wpa'] * 100:+.0f}%</span>
            <span style="font-size: 13px; line-height: 1.7">{esc(q['comment'])}</span>
          </span></a>"""
    body = f"""<div style="display: flex; flex-direction: column; gap: 6px">
      <h1 style="margin: 0; font-size: {34 if mobile else 46}px; font-weight: 900; line-height: 1.2"><span class="marker">{esc(p['name'])}</span><span style="font-size: {16 if mobile else 20}px; font-weight: 700; color: #C9D6EA; margin-left: 10px">の通信簿</span></h1>
      <span style="font-size: {15 if mobile else 17}px; font-weight: 700; color: #C9D6EA">{esc(sub)}</span>
      {f'<span style="display: flex; flex-wrap: wrap; gap: 6px">{awards}</span>' if awards else ''}
    </div>
    <div class="sheet" style="padding: {'14px 16px' if mobile else '18px 24px'}; border-radius: 8px; color: {INK}; display: flex; flex-wrap: wrap; gap: 12px; border-top: 6px solid {RED}">{stat_html}
      <span style="flex: 1 1 100%; font-size: 12px; color: {SUB}">大会通算＝各試合の点数から及第点6.0を引いた合計（上限突破分も含む）。プラスが大きいほど勝利に貢献しています。</span></div>
    <section style="display: flex; flex-direction: column; gap: 10px">
      {B.h2('試合ごとの通信簿', mobile)}
      <div class="sheet" style="padding: {'4px 12px' if mobile else '6px 20px'}; border-radius: 8px">{rows}</div>
    </section>
    <span style="font-size: 13px"><a href="{cdir}{DIV_SLUG.get(p['div'], '')}.html" style="color: #F3B7BA; font-weight: 900">{DIV_SHORT.get(p['div'], '')}の選手一覧へ</a>　<a href="../{comp.get('page', 'index.html')}" style="color: #C9D6EA">{esc(comp.get('name', '大会'))}のページへ</a></span>"""
    return shell(mobile, crumbs, body, 860)


# ---------- 大会の選手一覧（ランキング） / 部ごとの一覧（depth 3） ----------

def rank_table(lst, mobile):
    rows = ""
    for i, p in enumerate(lst):
        sc = "／".join(f"{q['raw']:.1f}" for q in reversed(p["games"]))
        team = esc(p["team"]) + (f'<span style="color: {SUB}">（{esc(p["grade"])}）</span>' if p["grade"] else "")
        rows += f"""<tr>
          <td style="text-align: center"><span class="hand" style="font-size: 24px; color: {RED}; line-height: 1">{i + 1}</span></td>
          <td><a href="../../../players/{p['pid']}.html" style="font-weight: 900; font-size: 16px; color: {INK}; white-space: nowrap">{esc(p['name'])}</a>
            {f'<span style="display: block; font-size: 12px">{team}・{esc(p["pos"])}　{sc}</span>' if mobile else ''}</td>
          {'' if mobile else f'<td style="white-space: nowrap">{team}</td><td style="text-align: center">{esc(p["pos"])}</td>'}
          {'' if mobile else f'<td style="font-size: 13px; color: {SUB}; white-space: nowrap">{sc}</td>'}
          <td style="text-align: right; white-space: nowrap"><span class="hand" style="font-size: 26px; color: {RED}; line-height: 1">{p['total']:+.1f}</span>{f'<span style="display: block; font-size: 11px; color: {SUB}">{len(p["games"])}試合</span>' if mobile else ''}</td>
        </tr>"""
    head = ('<tr><th scope="col" style="text-align: center">順位</th><th scope="col">選手</th><th scope="col" style="text-align: right">通算</th></tr>' if mobile else
            '<tr><th scope="col" style="text-align: center">順位</th><th scope="col">選手</th><th scope="col">所属</th><th scope="col" style="text-align: center">守備</th><th scope="col">各試合の採点</th><th scope="col" style="text-align: right">大会通算</th></tr>')
    if not rows:
        return f'<p style="margin: 0; padding: 12px; color: {SUB}">まだ該当する選手はいません。</p>'
    return f'<div style="overflow-x: auto"><table class="rc" style="width: 100%; border-collapse: collapse"><thead>{head}</thead><tbody>{rows}</tbody></table></div>'


def ranking(ps, cid, div, pitcher, n=10):
    lst = [p for p in ps.values() if p["comp"] == cid and p["div"] == div and p["pitcher"] == pitcher and p["total"] > 0]
    return sorted(lst, key=lambda p: (-round(p["total"], 2), -p["wpa"]))[:n]


def comp_index(ps, cid, mobile):
    comp = D.COMPS[cid]
    crumbs = crumb_html([("大会", None), (comp["short"], "../../" + comp["page"].split("/")[-1]), ("選手一覧", None)])
    divs = [d["div"] for d in sorted(comp["divisions"], key=lambda d: 0 if d["div"] == "UNIV" else 1)
            if any(p["comp"] == cid and p["div"] == d["div"] for p in ps.values())]
    links = "".join(f'<a href="{DIV_SLUG[dv]}.html" style="flex: 1; min-width: 150px; display: flex; flex-direction: column; gap: 4px; padding: {"14px 16px" if mobile else "18px 22px"}; border-radius: 10px; background-color: #14306A; border: 2px solid #3D5C93; color: #FFFFFF; text-decoration: none">'
                    f'<span style="font-size: {20 if mobile else 24}px; font-weight: 900">{D.DIV_JA[dv]}の選手一覧 →</span><span style="font-size: 13px; color: #C9D6EA">{DIV_SHORT[dv]}ごとに、全選手の試合ごとの採点を表で</span></a>' for dv in divs)
    sections = ""
    for dv in divs:
        for pit, lab in ((False, "野手"), (True, "投手")):
            sections += f"""<section style="display: flex; flex-direction: column; gap: 10px">
      <h2 style="margin: 0; font-size: {22 if mobile else 26}px; font-weight: 900"><span class="marker">{DIV_SHORT[dv]}・{lab}</span><span style="font-size: 14px; color: #C9D6EA; margin-left: 10px">大会通算ランキング</span></h2>
      <div class="sheet" style="padding: {'8px 10px' if mobile else '12px 20px'}; border-radius: 8px; color: {INK}">{rank_table(ranking(ps, cid, dv, pit), mobile)}</div>
    </section>"""
    note = '<p style="margin: 0; font-size: 12px; color: #9FB3D6">大会通算＝各試合の採点から及第点の6.0点を引いた分の合計（10点を超えた上限突破の分も数えます）。同点のときは勝利確率を多く動かした選手を上にしています。1試合でも登板した選手は投手に入れています。上位10人（通算がプラスの選手）を表示しています。</p>'
    body = f"""<div style="display: flex; flex-direction: column; gap: 8px">
      <h1 style="margin: 0; font-size: {30 if mobile else 42}px; font-weight: 900; line-height: 1.25"><span class="marker">{esc(comp['name'])}　選手一覧</span></h1>
      <p style="margin: 0; font-size: 14px; color: #C9D6EA">大会通算の採点で、大学・高校の野手と投手を順位にしました。部ごとの一覧では、チームごとに全選手の採点を見られます。</p>
    </div>
    <div style="display: flex; flex-wrap: wrap; gap: 12px">{links}</div>
    {sections}{note}"""
    return shell(mobile, crumbs, body)


def div_page(ps, cid, div, mobile):
    comp = D.COMPS[cid]
    crumbs = crumb_html([("大会", None), (comp["short"], "../../" + comp["page"].split("/")[-1]), ("選手一覧", "index.html"), (DIV_SHORT[div], None)])
    teams = {}
    for p in ps.values():
        if p["comp"] == cid and p["div"] == div:
            teams.setdefault(p["team"], []).append(p)
    tg = {}
    for team, lst in teams.items():
        gs = {}
        for p in lst:
            for q in p["games"]:
                gs[q["key"]] = q
        tg[team] = sorted(gs.values(), key=lambda q: q["date"])
    order = sorted(teams, key=lambda t: (-len(tg[t]), -sum(p["total"] for p in teams[t])))
    hs = div == "HS"
    nav = "".join(f'<a href="#t{i}" style="font-size: 13px; font-weight: 700; color: #FFFFFF; text-decoration: none; padding: 4px 10px; border: 1px solid #3D5C93; border-radius: 999px; white-space: nowrap">{esc(t)}</a>' for i, t in enumerate(order))
    blocks = ""
    for i, team in enumerate(order):
        games = tg[team]
        th = "".join(f'<th scope="col" style="text-align: center; white-space: nowrap; padding: 6px {2 if mobile else 8}px"><a href="../../../games/{q["key"]}.html" style="color: {SUB}; text-decoration: none">{n + 1}試合目'
                     f'<span style="display: block; font-size: 11px; font-weight: 500">{int(q["date"][5:7])}/{int(q["date"][8:10])} 対{esc(q["opp"])}</span>'
                     f'<span style="display: block; font-size: 11px; color: {RED if q["res"] == "勝" else "#3D5C93"}">{q["res"]} {q["score"]}</span></a></th>' for n, q in enumerate(games))

        def rows(lst):
            out = ""
            for p in lst:
                by = {q["key"]: q for q in p["games"]}
                cells = ""
                for q in games:
                    x = by.get(q["key"])
                    if x:
                        aw = f'<span style="display: block; font-size: 10px; font-weight: 900; color: #B8860B; white-space: nowrap">{x["award"]}</span>' if x["award"] else ""
                        cells += f'<td style="text-align: center"><span class="hand" style="font-size: {20 if mobile else 24}px; color: {B.score_color(x["pt"])}; line-height: 1">{x["pt"]:.1f}</span>{aw}</td>'
                    else:
                        cells += '<td style="text-align: center; color: #B8C3D6">—</td>'
                tot = (f'<span class="hand" style="font-size: {20 if mobile else 24}px; color: {RED if p["total"] > 0 else SUB}; line-height: 1">{p["total"]:+.1f}</span>'
                       if (p["total"] > 0 or not hs) else '<span style="color: #B8C3D6">—</span>')
                meta = "・".join(v for v in (p["grade"], p["pos"]) if v)
                if mobile:
                    out += (f'<tr><td style="white-space: nowrap; padding-left: 2px; padding-right: 2px"><a href="../../../players/{p["pid"]}.html" style="font-weight: 900; color: {INK}; font-size: 14px">{esc(p["name"])}</a>'
                            f'<span style="display: block; font-size: 10px; color: {SUB}">{esc(meta)}</span></td>{cells}<td style="text-align: right; white-space: nowrap; padding-left: 2px; padding-right: 2px">{tot}</td></tr>')
                else:
                    gr = f'<span style="font-size: 11px; color: {SUB}; margin-left: 4px">{esc(p["grade"])}</span>' if p["grade"] else ""
                    out += (f'<tr><td style="white-space: nowrap"><a href="../../../players/{p["pid"]}.html" style="font-weight: 900; color: {INK}">{esc(p["name"])}</a>{gr}</td>'
                            f'<td style="text-align: center; color: {SUB}; white-space: nowrap">{esc(p["pos"])}</td>{cells}<td style="text-align: right; white-space: nowrap">{tot}</td></tr>')
            return out
        key = lambda p: (-round(p["total"], 2), -p["wpa"])  # noqa: E731
        bat = sorted([p for p in teams[team] if not p["pitcher"]], key=key)
        pit = sorted([p for p in teams[team] if p["pitcher"]], key=key)
        head = (f'<tr><th scope="col" style="padding: 6px 2px">選手</th>{th}<th scope="col" style="text-align: right; padding: 6px 2px">通算</th></tr>' if mobile else
                f'<tr><th scope="col">選手</th><th scope="col" style="text-align: center">守備</th>{th}<th scope="col" style="text-align: right">大会通算</th></tr>')
        sub = lambda t: f'<tr><td colspan="{len(games) + (2 if mobile else 3)}" style="font-size: 13px; font-weight: 900; color: {RED}; padding-top: 12px">{t}</td></tr>'  # noqa: E731
        blocks += f"""<section id="t{i}" class="sheet" style="padding: {'12px 10px' if mobile else '16px 22px'}; border-radius: 8px; color: {INK}; border-top: 6px solid {RED}; scroll-margin-top: 16px">
      <h2 style="margin: 0 0 6px; font-size: {20 if mobile else 22}px; font-weight: 900">{esc(team)}<span style="font-size: 13px; color: {SUB}; margin-left: 8px">{len(games)}試合</span></h2>
      <div style="overflow-x: auto"><table class="rc" style="width: 100%; border-collapse: collapse"><thead>{head}</thead>
        <tbody>{sub('野手')}{rows(bat)}{sub('投手')}{rows(pit)}</tbody></table></div>
    </section>"""
    note = ('<p style="margin: 0; font-size: 12px; color: #9FB3D6">数字は各試合の採点（10点満点、6.0が及第点）。「—」はその試合に出場していません。大会通算は各試合の採点から6.0を引いた分の合計です。'
            + ('高校の部の大会通算は、プラスの選手だけ表示しています。' if hs else '') + '名前を押すと、その選手の試合ごとの通信簿が見られます。</p>')
    body = f"""<div style="display: flex; flex-direction: column; gap: 8px">
      <h1 style="margin: 0; font-size: {28 if mobile else 40}px; font-weight: 900; line-height: 1.25"><span class="marker">{esc(comp['name'])}　{D.DIV_JA[div]}</span></h1>
      <p style="margin: 0; font-size: 14px; color: #C9D6EA">{DIV_SHORT[div]}ごとに、出場した全選手の試合ごとの採点を並べました。</p>
      <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px">{nav}</div>
    </div>
    {note}
    {blocks}"""
    return shell(mobile, crumbs, body, 1120)


def write(dirp, name, title, pc, sp):
    dirp.mkdir(parents=True, exist_ok=True)
    (dirp / f"{name}.pc.dc.html").write_text(B.HEAD.format(title=title) + pc + B.TAIL.format(w=1280, h=2400))
    (dirp / f"{name}.sp.dc.html").write_text(B.HEAD.format(title=title) + sp + B.TAIL.format(w=390, h=3600))


ps = collect()
if _MODE == "comp":
    out = OUTROOT / f"comp-{_CID}"
    comp = D.COMPS[_CID]
    write(out, "index", "選手一覧", comp_index(ps, _CID, False), comp_index(ps, _CID, True))
    for dv in comp["divisions"]:
        if any(p["comp"] == _CID and p["div"] == dv["div"] for p in ps.values()):
            write(out, DIV_SLUG[dv["div"]], D.DIV_JA[dv["div"]], div_page(ps, _CID, dv["div"], False), div_page(ps, _CID, dv["div"], True))
    print(f"comp players ok: {_CID}")
else:
    out = OUTROOT / "players"
    manifest = []
    for p in ps.values():
        write(out, p["pid"], f"{p['name']}（{p['team']}）", player_page(p, False), player_page(p, True))
        gs = p["games"]
        desc = (f"{p['team']}・{p['name']}選手の通信簿。{len(gs)}試合に出場、最高{p['best']:.1f}点。"
                f"直近は{D.md_ja(gs[0]['date'])}の{gs[0]['comp']}{gs[0]['round']}で{gs[0]['pt']:.1f}点。")
        manifest.append({"pid": p["pid"], "title": f"{p['name']}（{p['team']}）の通信簿｜ベースボール通信簿", "desc": desc})
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False))
    print(f"players ok: {len(manifest)}")
