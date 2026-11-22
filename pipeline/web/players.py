"""選手ページ（1人1ページ）と選手一覧ページを作る。PC・スマホの2版を OUT/players/ に書き、manifest.json に一覧を残す。"""
import json
import os
import pathlib
import sys

sys.argv = ["build.py", "__first__"]
import build as B  # noqa: E402
import data as D  # noqa: E402
from brc.ids import player_id  # noqa: E402

INK, SUB, RED, LINE = B.INK, B.SUB, B.RED, B.LINE
OUT = pathlib.Path(os.environ.get("OUT", "/tmp/brc-build")) / "players"
OUT.mkdir(parents=True, exist_ok=True)
AWARD_JA = {"fielder_mvp": "野手MVP", "pitcher_mvp": "投手MVP", "fighting_spirit": "敢闘賞"}


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
                                    "div": g["div"], "comp": g["comp"], "games": []})
            opp = r["game"]["home"] if x["side"] == "away" else r["game"]["away"]
            mine, theirs = f[x["side"]], f["away" if x["side"] == "home" else "home"]
            p["games"].append({"key": g["key"], "date": g["date"], "comp": comp.get("short", ""), "div": D.DIV_JA.get(g["div"], ""),
                               "round": g.get("round", ""), "opp": opp, "res": "勝" if mine > theirs else ("敗" if mine < theirs else "分"),
                               "score": f"{mine}-{theirs}", "pos": x["pos"], "stat": x["stat"], "pt": x["score"], "raw": x["raw_score"],
                               "wpa": x["wpa"], "comment": x.get("comment", ""), "award": aw.get(x["player"])})
    for p in ps.values():
        p["games"].sort(key=lambda q: q["date"], reverse=True)
        p["total"] = sum(q["raw"] - 6 for q in p["games"])
        p["best"] = max(q["raw"] for q in p["games"])
        p["grade"] = D.grade(p["team"], p["raw"])
        p["awards"] = [q["award"] for q in p["games"] if q["award"]]
        pos = {}
        for q in p["games"]:
            pos[q["pos"]] = pos.get(q["pos"], 0) + 1
        p["pos"] = max(pos, key=pos.get) if pos else ""
    return ps


def chip(text, bg=RED):
    return f'<span style="font-size: 12px; font-weight: 900; color: #FFFFFF; background-color: {bg}; padding: 2px 10px; border-radius: 999px; white-space: nowrap">{text}</span>'


def player_page(p, mobile):
    comp = D.COMPS.get(p["comp"], {})
    sub = "・".join(v for v in (p["team"], p["grade"], B.POS_JA.get(p["pos"], p["pos"]) if hasattr(B, "POS_JA") else p["pos"]) if v)
    stats = [("出場", f'{len(p["games"])}<span style="font-size: 14px">試合</span>'),
             ("通算", f'{p["total"]:+.1f}'), ("最高", f'{p["best"]:.1f}')]
    stat_html = "".join(f'<div style="flex: 1; min-width: 90px; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; font-weight: 700; color: {SUB}">{k}</span>'
                        f'<span class="hand" style="font-size: {34 if mobile else 40}px; color: {RED}; line-height: 1.1">{v}</span></div>' for k, v in stats)
    awards = "".join(chip(a) for a in p["awards"])
    rows = ""
    for q in p["games"]:
        d = D.md_ja(q["date"])
        head = f'{d}　{q["comp"]} {q["div"]} {q["round"]}'
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
    wrap = "width: 390px; " if mobile else ""
    return f"""<div style="{wrap}min-height: 100vh; background-color: #0B1A36; color: #FFFFFF; font-family: 'Noto Sans JP', sans-serif; line-height: 1.6">
{B.header(mobile)}  <main style="max-width: 860px; margin: 0 auto; padding: {'18px 16px 56px' if mobile else '28px 24px 72px'}; display: flex; flex-direction: column; gap: 18px">
    <nav style="font-size: 13px; color: #9FB3D6"><a href="index.html" style="color: #C9D6EA">選手一覧</a>　›　{esc(p['team'])}</nav>
    <div style="display: flex; flex-direction: column; gap: 6px">
      <h1 style="margin: 0; font-size: {34 if mobile else 46}px; font-weight: 900; line-height: 1.2"><span class="marker">{esc(p['name'])}</span><span style="font-size: {16 if mobile else 20}px; font-weight: 700; color: #C9D6EA; margin-left: 10px">の通信簿</span></h1>
      <span style="font-size: {15 if mobile else 17}px; font-weight: 700; color: #C9D6EA">{esc(sub)}</span>
      {f'<span style="display: flex; flex-wrap: wrap; gap: 6px">{awards}</span>' if awards else ''}
    </div>
    <div class="sheet" style="padding: {'14px 16px' if mobile else '18px 24px'}; border-radius: 8px; color: {INK}; display: flex; flex-wrap: wrap; gap: 12px; border-top: 6px solid {RED}">{stat_html}
      <span style="flex: 1 1 100%; font-size: 12px; color: {SUB}">通算＝各試合の点数から及第点6.0を引いた合計（上限突破分も含む）。プラスが大きいほど勝利に貢献しています。</span></div>
    <section style="display: flex; flex-direction: column; gap: 10px">
      {B.h2('試合ごとの通信簿', mobile)}
      <div class="sheet" style="padding: {'4px 12px' if mobile else '6px 20px'}; border-radius: 8px">{rows}</div>
    </section>
    <span style="font-size: 13px"><a href="../{comp.get('page', 'index.html')}" style="color: #F3B7BA; font-weight: 900">{esc(comp.get('name', '大会'))}のページへ</a>　<a href="index.html" style="color: #C9D6EA">選手一覧へ</a></span>
  </main>
{B.footer(mobile)}</div>
"""


def index_page(ps, mobile):
    by = {}
    for p in ps.values():
        by.setdefault((p["comp"], p["div"]), {}).setdefault(p["team"], []).append(p)
    body = ""
    for (cid, div) in sorted(by, key=lambda k: (k[0], 0 if k[1] == "UNIV" else 1)):
        comp = D.COMPS.get(cid, {})
        body += f'<section style="display: flex; flex-direction: column; gap: 10px">{B.h2(esc(comp.get("name", "")) + "　" + D.DIV_JA.get(div, ""), mobile)}'
        teams = by[(cid, div)]
        for team in sorted(teams, key=lambda t: -max(p["total"] for p in teams[t])):
            lst = sorted(teams[team], key=lambda p: -p["total"])
            items = "".join(f'<a href="{p["pid"]}.html" style="display: inline-flex; align-items: baseline; gap: 6px; padding: 6px 10px; border: 1px solid {LINE}; border-radius: 6px; color: {INK}; text-decoration: none; background-color: #FFFFFF">'
                            f'<span style="font-weight: 900">{esc(p["name"])}</span>' + (f'<span style="font-size: 12px; color: {RED}; font-weight: 900">{p["total"]:+.1f}</span>' if p["total"] > 0 else '') + '</a>' for p in lst)
            body += (f'<div class="sheet" style="padding: {"12px" if mobile else "14px 20px"}; border-radius: 8px; color: {INK}; display: flex; flex-direction: column; gap: 8px">'
                     f'<h3 style="margin: 0; font-size: 18px; font-weight: 900">{esc(team)}</h3><div style="display: flex; flex-wrap: wrap; gap: 6px">{items}</div></div>')
        body += "</section>"
    wrap = "width: 390px; " if mobile else ""
    return f"""<div style="{wrap}min-height: 100vh; background-color: #0B1A36; color: #FFFFFF; font-family: 'Noto Sans JP', sans-serif; line-height: 1.6">
{B.header(mobile)}  <main style="max-width: 960px; margin: 0 auto; padding: {'18px 16px 56px' if mobile else '28px 24px 72px'}; display: flex; flex-direction: column; gap: 22px">
    <h1 style="margin: 0; font-size: {30 if mobile else 40}px; font-weight: 900"><span class="marker">選手一覧</span></h1>
    <p style="margin: 0; font-size: 14px; color: #C9D6EA">名前を押すと、その選手の試合ごとの通信簿が見られます。数字は通算（各試合の点数−6.0の合計）で、プラスの選手だけ表示しています。</p>
    {body}
  </main>
{B.footer(mobile)}</div>
"""


ps = collect()
manifest = []
for p in ps.values():
    t = f"{p['name']}（{p['team']}）"
    for mobile, suf in ((False, "pc"), (True, "sp")):
        (OUT / f"{p['pid']}.{suf}.dc.html").write_text(B.HEAD.format(title=t) + player_page(p, mobile) + B.TAIL.format(w=390 if mobile else 1280, h=2400))
    gs = p["games"]
    desc = (f"{p['team']}・{p['name']}選手の通信簿。{len(gs)}試合に出場、最高{p['best']:.1f}点。"
            f"直近は{D.md_ja(gs[0]['date'])}の{gs[0]['comp']}{gs[0]['round']}で{gs[0]['pt']:.1f}点。")
    manifest.append({"pid": p["pid"], "title": f"{p['name']}（{p['team']}）の通信簿｜ベースボール通信簿", "desc": desc})
for mobile, suf in ((False, "pc"), (True, "sp")):
    (OUT / f"index.{suf}.dc.html").write_text(B.HEAD.format(title="選手一覧") + index_page(ps, mobile) + B.TAIL.format(w=390 if mobile else 1280, h=3600))
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False))
print(f"players ok: {len(manifest)}")
