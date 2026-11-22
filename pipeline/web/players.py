"""大会まわりの下層ページを作る（URLは brc/paths.py とディレクトリマップに合わせる）。

  python players.py comp <大会ID>  … 選手一覧（ランキング）／部（学校の一覧）／学校／選手／日付 の各ページ
  python players.py hubs           … 大会一覧（/tournaments/）と大会ごとのトップ（/tournaments/<大会>/）

PC版とスマホ版を OUT/comp-<大会ID>/ または OUT/hubs/ に書き、manifest.json に「どのページをどこに置くか」を残す。
"""
import json
import os
import pathlib
import sys

_MODE = sys.argv[1] if len(sys.argv) > 1 else "comp"
_CID = sys.argv[2] if len(sys.argv) > 2 else ""
sys.argv = ["build.py", "__first__"]
import build as B  # noqa: E402
import data as D  # noqa: E402
from brc import paths as P  # noqa: E402
from brc.ids import player_id  # noqa: E402

INK, SUB, RED, LINE = B.INK, B.SUB, B.RED, B.LINE
OUTROOT = pathlib.Path(os.environ.get("OUT", "/tmp/brc-build"))
AWARD_JA = {"fielder_mvp": "野手MVP", "pitcher_mvp": "投手MVP", "fighting_spirit": "敢闘賞"}
DIV_SHORT = {"UNIV": "大学", "HS": "高校"}
POS_LONG = {"投": "投手", "捕": "捕手", "一": "一塁", "二": "二塁", "三": "三塁", "遊": "遊撃", "左": "左翼", "中": "中堅", "右": "右翼",
            "指": "指名打者", "打": "代打", "走": "代走"}


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def R(path):
    return B.R(path)


def collect(cid):
    comp = D.COMPS[cid]
    ps = {}
    for g in D.published():
        if g["comp"] != cid:
            continue
        r, _, _ = D.result(g["key"])
        aw = {v: AWARD_JA[k] for k, v in r["awards"].items() if v and k in AWARD_JA}
        f = r["final"]
        for x in r["ratings"]:
            pid = player_id(x["team"], x["player"])
            p = ps.setdefault(pid, {"pid": pid, "name": D.nm(x["player"]), "raw": x["player"], "team": x["team"],
                                    "div": g["div"], "comp": cid, "games": [], "pitcher": False})
            p["pitcher"] = p["pitcher"] or bool(x["pitcher"])
            opp = r["game"]["home"] if x["side"] == "away" else r["game"]["away"]
            mine, theirs = f[x["side"]], f["away" if x["side"] == "home" else "home"]
            p["games"].append({"key": g["key"], "page": P.game_page(comp, g), "date": g["date"], "comp": comp.get("short", ""),
                               "div": D.DIV_JA.get(g["div"], ""), "round": g.get("round", ""), "opp": opp,
                               "res": "勝" if mine > theirs else ("敗" if mine < theirs else "分"), "score": f"{mine}-{theirs}",
                               "pos": x["pos"], "stat": x["stat"], "pt": x["score"], "raw": x["raw_score"], "wpa": x["wpa"],
                               "comment": x.get("comment", ""), "award": aw.get(x["player"])})
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
        p["page"] = P.player_page(comp, p["div"], p["team"], p["pid"])
    return ps


def chip(text, bg=RED):
    return f'<span style="font-size: 12px; font-weight: 900; color: #FFFFFF; background-color: {bg}; padding: 2px 10px; border-radius: 999px; white-space: nowrap">{text}</span>'


def crumbs(items):
    out = []
    for label, path in items:
        out.append(f'<a href="{R(path)}" style="color: #C9D6EA; text-decoration: none">{esc(label)}</a>' if path else f'<span style="color: #FFFFFF">{esc(label)}</span>')
    return ' <span style="color: #5C7FBA">›</span> '.join(out)


def comp_crumbs(comp, *rest):
    return crumbs([("大会", "tournaments/index.html"), (comp.get("family_name", comp["short"]), P.family_page(comp)),
                   (str(comp.get("year", "")), P.comp_page(comp)), *rest])


def shell(mobile, crumb_html, body, width=960):
    wrap = "width: 390px; " if mobile else ""
    return f"""<div style="{wrap}min-height: 100vh; background-color: #0B1A36; color: #FFFFFF; font-family: 'Noto Sans JP', sans-serif; line-height: 1.6">
{B.header(mobile)}  <main style="max-width: {width}px; margin: 0 auto; padding: {'18px 16px 56px' if mobile else '28px 24px 72px'}; display: flex; flex-direction: column; gap: 22px">
    <nav aria-label="パンくずリスト" style="font-size: 13px; color: #9FB3D6">{crumb_html}</nav>
    {body}
  </main>
{B.footer(mobile)}</div>
"""


def h1(text, mobile, small=""):
    return (f'<h1 style="margin: 0; font-size: {28 if mobile else 40}px; font-weight: 900; line-height: 1.25"><span class="marker">{esc(text)}</span>'
            + (f'<span style="font-size: {15 if mobile else 18}px; font-weight: 700; color: #C9D6EA; margin-left: 10px">{esc(small)}</span>' if small else "") + "</h1>")


# ---------- 選手 ----------

def player_page(comp, p, mobile):
    cr = comp_crumbs(comp, (D.DIV_JA[p["div"]], P.div_page(comp, p["div"])), (p["team"], P.team_page(comp, p["div"], p["team"])), (p["name"], None))
    sub = "・".join(v for v in (p["team"], p["grade"], p["pos"]) if v)
    stats = [("出場", f'{len(p["games"])}<span style="font-size: 14px">試合</span>'), ("大会通算", f'{p["total"]:+.1f}'), ("最高", f'{p["best"]:.1f}')]
    stat_html = "".join(f'<div style="flex: 1; min-width: 90px; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; font-weight: 700; color: {SUB}">{k}</span>'
                        f'<span class="hand" style="font-size: {34 if mobile else 40}px; color: {RED}; line-height: 1.1">{v}</span></div>' for k, v in stats)
    awards = "".join(chip(a) for a in p["awards"])
    rows = ""
    for q in p["games"]:
        head = f'{D.md_ja(q["date"])}　{q["comp"]} {q["div"]} {q["round"]}'
        res = chip(q["res"], RED if q["res"] == "勝" else "#3D5C93")
        aw = chip(q["award"], "#E2B448") if q["award"] else ""
        over = f'<span style="display: block; font-size: 10px; font-weight: 900; color: {RED}">上限突破 {q["raw"]:.1f}</span>' if q["raw"] > 10 else ""
        rows += f"""<a href="{R(q['page'])}" style="display: flex; gap: {12 if mobile else 18}px; align-items: flex-start; padding: 14px 4px; border-bottom: 1px solid {LINE}; color: {INK}; text-decoration: none">
          <span style="flex: none; width: {56 if mobile else 72}px; text-align: center"><span class="hand" style="font-size: {34 if mobile else 40}px; color: {B.score_color(q['pt'])}; line-height: 1">{q['pt']:.1f}</span>{over}</span>
          <span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px">
            <span style="font-size: 12px; color: {SUB}">{esc(head)}</span>
            <span style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px"><span style="font-size: {16 if mobile else 18}px; font-weight: 900">対 {esc(q['opp'])}　{q['score']}</span>{res}{aw}</span>
            <span style="font-size: 13px; color: {SUB}">{esc(q['pos'])}　{esc(q['stat'])}　勝利確率 {q['wpa'] * 100:+.0f}%</span>
            <span style="font-size: 13px; line-height: 1.7">{esc(q['comment'])}</span>
          </span></a>"""
    body = f"""<div style="display: flex; flex-direction: column; gap: 6px">
      {h1(p['name'], mobile, 'の通信簿')}
      <span style="font-size: {15 if mobile else 17}px; font-weight: 700; color: #C9D6EA">{esc(sub)}</span>
      {f'<span style="display: flex; flex-wrap: wrap; gap: 6px">{awards}</span>' if awards else ''}
    </div>
    <div class="sheet" style="padding: {'14px 16px' if mobile else '18px 24px'}; border-radius: 8px; color: {INK}; display: flex; flex-wrap: wrap; gap: 12px; border-top: 6px solid {RED}">{stat_html}
      <span style="flex: 1 1 100%; font-size: 12px; color: {SUB}">大会通算＝各試合の点数から及第点6.0を引いた合計（上限突破分も含む）。プラスが大きいほど勝利に貢献しています。</span></div>
    <section style="display: flex; flex-direction: column; gap: 10px">
      {B.h2('試合ごとの通信簿', mobile)}
      <div class="sheet" style="padding: {'4px 12px' if mobile else '6px 20px'}; border-radius: 8px">{rows}</div>
    </section>
    <span style="font-size: 13px"><a href="{R(P.team_page(comp, p['div'], p['team']))}" style="color: #F3B7BA; font-weight: 900">{esc(p['team'])}の選手一覧へ</a>　<a href="{R(P.players_page(comp))}" style="color: #C9D6EA">大会の選手ランキングへ</a></span>"""
    return shell(mobile, cr, body, 860)


# ---------- 選手一覧（ランキング） ----------

def rank_table(lst, mobile):
    rows = ""
    for i, p in enumerate(lst):
        sc = "／".join(f"{q['raw']:.1f}" for q in reversed(p["games"]))
        team = esc(p["team"]) + (f'<span style="color: {SUB}">（{esc(p["grade"])}）</span>' if p["grade"] else "")
        rows += f"""<tr>
          <td style="text-align: center"><span class="hand" style="font-size: 24px; color: {RED}; line-height: 1">{i + 1}</span></td>
          <td><a href="{R(p['page'])}" style="font-weight: 900; font-size: 16px; color: {INK}; white-space: nowrap">{esc(p['name'])}</a>
            {f'<span style="display: block; font-size: 12px">{team}・{esc(p["pos"])}　{sc}</span>' if mobile else ''}</td>
          {'' if mobile else f'<td style="white-space: nowrap">{team}</td><td style="text-align: center; white-space: nowrap">{esc(p["pos"])}</td>'}
          {'' if mobile else f'<td style="font-size: 13px; color: {SUB}; white-space: nowrap">{sc}</td>'}
          <td style="text-align: right; white-space: nowrap"><span class="hand" style="font-size: 26px; color: {RED}; line-height: 1">{p['total']:+.1f}</span>{f'<span style="display: block; font-size: 11px; color: {SUB}">{len(p["games"])}試合</span>' if mobile else ''}</td>
        </tr>"""
    head = ('<tr><th scope="col" style="text-align: center">順位</th><th scope="col">選手</th><th scope="col" style="text-align: right">通算</th></tr>' if mobile else
            '<tr><th scope="col" style="text-align: center">順位</th><th scope="col">選手</th><th scope="col">所属</th><th scope="col" style="text-align: center">守備</th><th scope="col">各試合の採点</th><th scope="col" style="text-align: right">大会通算</th></tr>')
    if not rows:
        return f'<p style="margin: 0; padding: 12px; color: {SUB}">まだ該当する選手はいません。</p>'
    return f'<div style="overflow-x: auto"><table class="rc" style="width: 100%; border-collapse: collapse"><thead>{head}</thead><tbody>{rows}</tbody></table></div>'


def ranking(ps, div, pitcher, n=10):
    lst = [p for p in ps.values() if p["div"] == div and p["pitcher"] == pitcher and p["total"] > 0]
    return sorted(lst, key=lambda p: (-round(p["total"], 2), -p["wpa"]))[:n]


def divs_of(comp, ps):
    return [d["div"] for d in sorted(comp["divisions"], key=lambda d: 0 if d["div"] == "UNIV" else 1) if any(p["div"] == d["div"] for p in ps.values())]


def players_index(comp, ps, mobile):
    divs = divs_of(comp, ps)
    links = "".join(f'<a href="{R(P.div_page(comp, dv))}" style="flex: 1; min-width: 150px; display: flex; flex-direction: column; gap: 4px; padding: {"14px 16px" if mobile else "18px 22px"}; border-radius: 10px; background-color: #14306A; border: 2px solid #3D5C93; color: #FFFFFF; text-decoration: none">'
                    f'<span style="font-size: {20 if mobile else 24}px; font-weight: 900">{D.DIV_JA[dv]} →</span><span style="font-size: 13px; color: #C9D6EA">{DIV_SHORT[dv]}ごとに、全選手の試合ごとの採点を表で</span></a>' for dv in divs)
    sections = ""
    for dv in divs:
        for pit, lab in ((False, "野手"), (True, "投手")):
            sections += f"""<section style="display: flex; flex-direction: column; gap: 10px">
      <h2 style="margin: 0; font-size: {22 if mobile else 26}px; font-weight: 900"><span class="marker">{DIV_SHORT[dv]}・{lab}</span><span style="font-size: 14px; color: #C9D6EA; margin-left: 10px">大会通算ランキング</span></h2>
      <div class="sheet" style="padding: {'8px 10px' if mobile else '12px 20px'}; border-radius: 8px; color: {INK}">{rank_table(ranking(ps, dv, pit), mobile)}</div>
    </section>"""
    note = '<p style="margin: 0; font-size: 12px; color: #9FB3D6">大会通算＝各試合の採点から及第点の6.0点を引いた分の合計（10点を超えた上限突破の分も数えます）。同点のときは勝利確率を多く動かした選手を上にしています。1試合でも登板した選手は投手に入れています。上位10人（通算がプラスの選手）を表示しています。</p>'
    body = f"""<div style="display: flex; flex-direction: column; gap: 8px">
      {h1(comp['name'] + '　選手一覧', mobile)}
      <p style="margin: 0; font-size: 14px; color: #C9D6EA">大会通算の採点で、大学・高校の野手と投手を順位にしました。部ごとのページでは、学校ごとに全選手の採点を見られます。</p>
    </div>
    <div style="display: flex; flex-wrap: wrap; gap: 12px">{links}</div>
    {sections}{note}"""
    return shell(mobile, comp_crumbs(comp, ("選手一覧", None)), body)


# ---------- 部（学校の一覧）と学校 ----------

def team_games(ps, div):
    teams, tg = {}, {}
    for p in ps.values():
        if p["div"] == div:
            teams.setdefault(p["team"], []).append(p)
    for team, lst in teams.items():
        gs = {}
        for p in lst:
            for q in p["games"]:
                gs[q["key"]] = q
        tg[team] = sorted(gs.values(), key=lambda q: q["date"])
    order = sorted(teams, key=lambda t: (-len(tg[t]), -sum(p["total"] for p in teams[t])))
    return teams, tg, order


def div_index(comp, ps, div, mobile):
    teams, tg, order = team_games(ps, div)
    cards = ""
    for team in order:
        games = tg[team]
        w = sum(1 for q in games if q["res"] == "勝")
        l_ = sum(1 for q in games if q["res"] == "敗")
        best = max(teams[team], key=lambda p: (p["total"], p["wpa"]))
        last = games[-1]
        res = " ".join(f'<span style="color: {RED if q["res"] == "勝" else "#3D5C93"}; font-weight: 900">{q["res"]}</span>' for q in games)
        cards += f"""<a href="{R(P.team_page(comp, div, team))}" class="sheet" style="display: flex; flex-direction: column; gap: 6px; padding: {'12px 14px' if mobile else '16px 18px'}; border-radius: 8px; color: {INK}; text-decoration: none; border-top: 5px solid {RED}">
          <span style="display: flex; align-items: baseline; justify-content: space-between; gap: 8px"><span style="font-size: {19 if mobile else 21}px; font-weight: 900">{esc(team)}</span><span style="font-size: 13px; color: {SUB}; white-space: nowrap">{w}勝{l_}敗</span></span>
          <span style="font-size: 13px">{res}　<span style="color: {SUB}">最終：{D.md_ja(last['date'])} 対{esc(last['opp'])} {last['score']}</span></span>
          <span style="font-size: 13px; color: {SUB}">チーム最高：<span style="font-weight: 900; color: {INK}">{esc(best['name'])}</span>（大会通算 {best['total']:+.1f}）</span>
        </a>"""
    other = [d for d in divs_of(comp, ps) if d != div]
    body = f"""<div style="display: flex; flex-direction: column; gap: 8px">
      {h1(comp['name'] + '　' + D.DIV_JA[div], mobile)}
      <p style="margin: 0; font-size: 14px; color: #C9D6EA">出場した{DIV_SHORT[div]}の一覧です。{DIV_SHORT[div]}名を押すと、全選手の試合ごとの採点表が見られます。</p>
    </div>
    <div style="display: grid; grid-template-columns: {'1fr' if mobile else 'repeat(2, 1fr)'}; gap: 12px">{cards}</div>
    <span style="font-size: 13px"><a href="{R(P.players_page(comp))}" style="color: #F3B7BA; font-weight: 900">大会の選手ランキングへ</a>{''.join(f'　<a href="{R(P.div_page(comp, d))}" style="color: #C9D6EA">{D.DIV_JA[d]}へ</a>' for d in other)}</span>"""
    return shell(mobile, comp_crumbs(comp, (D.DIV_JA[div], None)), body)


def team_page(comp, ps, div, team, mobile):
    teams, tg, _ = team_games(ps, div)
    games = tg[team]
    hs = div == "HS"
    th = "".join(f'<th scope="col" style="text-align: center; white-space: nowrap; padding: 6px {2 if mobile else 8}px"><a href="{R(q["page"])}" style="color: {SUB}; text-decoration: none">{n + 1}試合目'
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
                out += (f'<tr><td style="white-space: nowrap; padding-left: 2px; padding-right: 2px"><a href="{R(p["page"])}" style="font-weight: 900; color: {INK}; font-size: 14px">{esc(p["name"])}</a>'
                        f'<span style="display: block; font-size: 10px; color: {SUB}">{esc(meta)}</span></td>{cells}<td style="text-align: right; white-space: nowrap; padding-left: 2px; padding-right: 2px">{tot}</td></tr>')
            else:
                gr = f'<span style="font-size: 11px; color: {SUB}; margin-left: 4px">{esc(p["grade"])}</span>' if p["grade"] else ""
                out += (f'<tr><td style="white-space: nowrap"><a href="{R(p["page"])}" style="font-weight: 900; color: {INK}">{esc(p["name"])}</a>{gr}</td>'
                        f'<td style="text-align: center; color: {SUB}; white-space: nowrap">{esc(p["pos"])}</td>{cells}<td style="text-align: right; white-space: nowrap">{tot}</td></tr>')
        return out
    key = lambda p: (-round(p["total"], 2), -p["wpa"])  # noqa: E731
    bat = sorted([p for p in teams[team] if not p["pitcher"]], key=key)
    pit = sorted([p for p in teams[team] if p["pitcher"]], key=key)
    head = (f'<tr><th scope="col" style="padding: 6px 2px">選手</th>{th}<th scope="col" style="text-align: right; padding: 6px 2px">通算</th></tr>' if mobile else
            f'<tr><th scope="col">選手</th><th scope="col" style="text-align: center">守備</th>{th}<th scope="col" style="text-align: right">大会通算</th></tr>')
    sub = lambda t: f'<tr><td colspan="{len(games) + (2 if mobile else 3)}" style="font-size: 13px; font-weight: 900; color: {RED}; padding-top: 12px">{t}</td></tr>'  # noqa: E731
    w = sum(1 for q in games if q["res"] == "勝")
    l_ = sum(1 for q in games if q["res"] == "敗")
    note = ('<p style="margin: 0; font-size: 12px; color: #9FB3D6">数字は各試合の採点（10点満点、6.0が及第点）。「—」はその試合に出場していません。大会通算は各試合の採点から6.0を引いた分の合計です。'
            + ('高校の部の大会通算は、プラスの選手だけ表示しています。' if hs else '') + '名前を押すと、その選手の通信簿が見られます。</p>')
    body = f"""<div style="display: flex; flex-direction: column; gap: 6px">
      {h1(team, mobile, f'{comp["name"]}　{D.DIV_JA[div]}')}
      <span style="font-size: 14px; font-weight: 700; color: #C9D6EA">{len(games)}試合　{w}勝{l_}敗</span>
    </div>
    <section class="sheet" style="padding: {'12px 10px' if mobile else '16px 22px'}; border-radius: 8px; color: {INK}; border-top: 6px solid {RED}">
      <div style="overflow-x: auto"><table class="rc" style="width: 100%; border-collapse: collapse"><thead>{head}</thead>
        <tbody>{sub('野手')}{rows(bat)}{sub('投手')}{rows(pit)}</tbody></table></div>
    </section>
    {note}
    <span style="font-size: 13px"><a href="{R(P.div_page(comp, div))}" style="color: #F3B7BA; font-weight: 900">{D.DIV_JA[div]}の{DIV_SHORT[div]}一覧へ</a>　<a href="{R(P.players_page(comp))}" style="color: #C9D6EA">大会の選手ランキングへ</a></span>"""
    return shell(mobile, comp_crumbs(comp, (D.DIV_JA[div], P.div_page(comp, div)), (team, None)), body, 1120)


# ---------- 日付 ----------

def day_page(comp, cid, date, mobile):
    gs = [g for g in D.published() if g["comp"] == cid and g["date"] == date]
    blocks = ""
    for div in ("UNIV", "HS"):
        sel = [g for g in gs if g["div"] == div]
        if not sel:
            continue
        rows = "".join(f"""<a href="{R(P.game_page(comp, g))}" class="sheet" style="display: flex; flex-direction: column; gap: 4px; padding: {'12px 14px' if mobile else '16px 20px'}; border-radius: 8px; color: {INK}; text-decoration: none">
            <span style="font-size: 12px; color: {SUB}">{esc(g.get('round', ''))}{('　' + esc(g.get('start', '')) + '開始') if g.get('start') else ''}</span>
            <span style="font-size: {17 if mobile else 20}px; font-weight: 900">{esc(D.score_line(g['key']))}</span>
            <span style="font-size: 13px; line-height: 1.8">{esc(g.get('comment', ''))}</span>
            <span style="font-size: 13px; font-weight: 900; color: {RED}">この試合の通信簿 →</span></a>""" for g in sel)
        blocks += f'<section style="display: flex; flex-direction: column; gap: 10px">{B.h2(D.DIV_JA[div], mobile)}{rows}</section>'
    days = sorted({g["date"] for g in D.published() if g["comp"] == cid})
    nav = "".join(f'<a href="{R(P.day_page(comp, d))}" style="font-size: 13px; font-weight: 700; color: {"#0B1A36" if d == date else "#FFFFFF"}; background-color: {"#FFFFFF" if d == date else "transparent"}; text-decoration: none; padding: 4px 12px; border: 1px solid #3D5C93; border-radius: 999px; white-space: nowrap">{D.md_ja(d)}</a>' for d in days)
    body = f"""<div style="display: flex; flex-direction: column; gap: 8px">
      {h1(D.date_ja(date) + 'の試合', mobile)}
      <p style="margin: 0; font-size: 14px; color: #C9D6EA">{esc(comp['name'])}</p>
      <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px">{nav}</div>
    </div>
    {blocks}"""
    return shell(mobile, comp_crumbs(comp, (f"{int(date[5:7])}.{int(date[8:10])}", None)), body, 860)


# ---------- 大会一覧・大会ごとのトップ ----------

def families():
    fam = {}
    for cid, c in D.COMPS.items():
        if not any(g["comp"] == cid for g in D.published()):
            continue
        fam.setdefault(c["family"], []).append((cid, c))
    for v in fam.values():
        v.sort(key=lambda kv: -kv[1].get("year", 0))
    return fam


def status_of(c):
    import datetime as dt
    today = D.today_date() or dt.date.today().isoformat()
    return "開催中" if c["start"] <= today <= c["end"] else ("終了" if today > c["end"] else "開催前")


def tournaments_index(mobile):
    cards = ""
    for fam, lst in families().items():
        cid, c = lst[0]
        n = sum(1 for g in D.published() if g["comp"] == cid)
        st = status_of(c)
        cards += f"""<a href="{R(P.family_page(c))}" style="display: flex; flex-direction: column; gap: 8px; padding: {'18px 16px' if mobile else '24px 26px'}; border-radius: 12px; background-color: #14306A; border: 2px solid #3D5C93; color: #FFFFFF; text-decoration: none">
          <span style="align-self: flex-start">{chip(st, RED if st == '開催中' else '#3D5C93')}</span>
          <span style="font-size: {24 if mobile else 30}px; font-weight: 900">{esc(c['family_name'])}</span>
          <span style="font-size: 13px; color: #C9D6EA">最新：{esc(c['name'])}（{n}試合を採点）</span></a>"""
    soon = "".join(f'<span style="padding: 8px 14px; border: 1px dashed #3D5C93; border-radius: 8px; color: #9FB3D6; font-size: 14px; font-weight: 700">{t}</span>' for t in ("選抜高校野球（センバツ）", "全国高校野球選手権（夏の甲子園）", "全日本大学野球選手権"))
    body = f"""<div style="display: flex; flex-direction: column; gap: 8px">
      {h1('大会', mobile)}
      <p style="margin: 0; font-size: 14px; color: #C9D6EA">ベースボール通信簿で採点している大会の一覧です。</p>
    </div>
    <div style="display: grid; grid-template-columns: {'1fr' if mobile else 'repeat(2, 1fr)'}; gap: 14px">{cards}</div>
    <section style="display: flex; flex-direction: column; gap: 10px">{B.h2('今後追加する大会', mobile)}<div style="display: flex; flex-wrap: wrap; gap: 8px">{soon}</div></section>"""
    return shell(mobile, crumbs([("大会", None)]), body)


def family_index(lst, mobile):
    c0 = lst[0][1]
    years = ""
    for _, c in lst:
        st = status_of(c)
        years += f"""<a href="{R(P.comp_page(c))}" class="sheet" style="display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: {'14px 16px' if mobile else '18px 24px'}; border-radius: 8px; color: {INK}; text-decoration: none; border-left: 6px solid {RED}">
          <span style="display: flex; flex-direction: column"><span style="font-size: {22 if mobile else 26}px; font-weight: 900">{c.get('year', '')}年</span><span style="font-size: 13px; color: {SUB}">{esc(c['formal'])}</span></span>
          {chip(st, RED if st == '開催中' else '#3D5C93')}</a>"""
    body = f"""<div style="display: flex; flex-direction: column; gap: 8px">
      {h1(c0['family_name'], mobile)}
      <p style="margin: 0; font-size: 14px; line-height: 1.9; color: #C9D6EA">毎年11月に神宮球場で開かれる、高校の部と大学の部の全国大会です。秋の各地区大会を勝ち上がったチームが出場します。年ごとのページで、全試合・全選手の通信簿が見られます。</p>
    </div>
    <section style="display: flex; flex-direction: column; gap: 10px">{B.h2('年ごとの大会', mobile)}{years}</section>"""
    return shell(mobile, crumbs([("大会", "tournaments/index.html"), (c0["family_name"], None)]), body, 860)


# ---------- 書き出し ----------

def emit(outdir, manifest, ident, page, title, desc, render, legacy=None):
    B.CUR = page
    pc, sp = render(False), render(True)
    (outdir / f"{ident}.pc.dc.html").write_text(B.HEAD.format(title=title) + pc + B.TAIL.format(w=1280, h=2400))
    (outdir / f"{ident}.sp.dc.html").write_text(B.HEAD.format(title=title) + sp + B.TAIL.format(w=390, h=3600))
    m = {"id": ident, "page": page, "title": title, "desc": desc}
    if legacy:
        m["legacy"] = legacy
    manifest.append(m)


if _MODE == "comp":
    comp = D.COMPS[_CID]
    out = OUTROOT / f"comp-{_CID}"
    out.mkdir(parents=True, exist_ok=True)
    ps = collect(_CID)
    man = []
    name = comp["name"]
    emit(out, man, "players", P.players_page(comp), f"選手一覧｜{name}｜ベースボール通信簿",
         f"{name}の選手一覧。大会通算の採点で、大学・高校の野手と投手のランキングを掲載。", lambda m: players_index(comp, ps, m))
    for div in divs_of(comp, ps):
        dj = D.DIV_JA[div]
        emit(out, man, f"div-{div}", P.div_page(comp, div), f"{dj}｜{name}｜ベースボール通信簿",
             f"{name} {dj}に出場した{DIV_SHORT[div]}の一覧。{DIV_SHORT[div]}ごとに全選手の試合ごとの採点が見られます。", lambda m, d=div: div_index(comp, ps, d, m))
        teams, _, order = team_games(ps, div)
        for team in order:
            emit(out, man, f"team-{div}-{P.team_slug(div, team)}", P.team_page(comp, div, team), f"{team}の通信簿｜{name} {dj}｜ベースボール通信簿",
                 f"{name} {dj}、{team}の全選手の採点を試合ごとに一覧にしました。", lambda m, d=div, t=team: team_page(comp, ps, d, t, m))
    for p in ps.values():
        gs = p["games"]
        emit(out, man, f"p-{p['pid']}", p["page"], f"{p['name']}（{p['team']}）の通信簿｜{name}｜ベースボール通信簿",
             f"{p['team']}・{p['name']}選手の{name}での通信簿。{len(gs)}試合に出場、最高{p['best']:.1f}点。",
             lambda m, p=p: player_page(comp, p, m), legacy=f"players/{p['pid']}.html")
    for date in sorted({g["date"] for g in D.published() if g["comp"] == _CID}):
        emit(out, man, f"day-{date}", P.day_page(comp, date), f"{D.md_ja(date)}の試合｜{name}｜ベースボール通信簿",
             f"{name}、{D.date_ja(date)}の全試合の結果と通信簿。", lambda m, d=date: day_page(comp, _CID, d, m))
    (out / "manifest.json").write_text(json.dumps(man, ensure_ascii=False))
    print(f"comp ok: {_CID} {len(man)} pages")
else:
    out = OUTROOT / "hubs"
    out.mkdir(parents=True, exist_ok=True)
    man = []
    emit(out, man, "tournaments", "tournaments/index.html", "大会｜ベースボール通信簿",
         "ベースボール通信簿で採点している大会の一覧。", tournaments_index)
    for fam, lst in families().items():
        c0 = lst[0][1]
        emit(out, man, f"fam-{fam}", P.family_page(c0), f"{c0['family_name']}｜ベースボール通信簿",
             f"{c0['family_name']}の通信簿。年ごとに全試合・全選手の採点を掲載。", lambda m, l=lst: family_index(l, m))
    (out / "manifest.json").write_text(json.dumps(man, ensure_ascii=False))
    print(f"hubs ok: {len(man)} pages")
