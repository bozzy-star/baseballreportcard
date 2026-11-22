"""毎日の自動処理：試合の取得 → 採点 → 文章 → カード → 台帳の更新。

  python3 pipeline/run.py --slot hs|univ|all [--date 2026-11-22] [--late]

- 大会の台帳（data/competitions.json）で、期間中の大会・部だけを処理する
- 「終了していて、まだ処理していない試合」だけを処理する（何度動かしても二重にならない）
- 結果は data/ に書き、まとめを --out の JSON に出す（GitHub Actions の後続ステップが使う）
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from brc.engine import Game  # noqa: E402
from brc.parse_yahoo import YahooParser  # noqa: E402
from brc.card import make_cards  # noqa: E402
import fetch_sportsnavi as SN  # noqa: E402
import textgen  # noqa: E402

DATA = ROOT / "data"
DIV_JA = {"HS": "高校の部", "UNIV": "大学の部"}
DIV_SLUG = {"HS": "hs", "UNIV": "univ"}
SITE_URL = "https://baseballreportcard.com"
JST = dt.timezone(dt.timedelta(hours=9))


def load(name, default):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def stage_context(comp, div, rnd):
    r = (rnd or "").split("（")[0]
    meaning = "勝ったチームが優勝" if r == "決勝" else ("勝ったチームは決勝へ進む" if r == "準決勝" else "勝ったチームは次の試合へ進む")
    return f"大会：{comp['formal']} {DIV_JA[div]} {r}（{meaning}）"


def score_line(r):
    g, f = r["game"], r["final"]
    if f["winner"] == g["home"]:
        return f"{g['home']} {f['home']}-{f['away']} {g['away']}"
    return f"{g['away']} {f['away']}-{f['home']} {g['home']}"


def process_game(comp_id, comp, dv, sg, reg, players, log):
    div = dv["div"]
    league = dv["source"]["league"]
    text, meta = SN.fetch_game(league, sg["id"])
    if not meta.get("final"):
        log.append(f"  {sg['title']}: まだ終了していません（{meta.get('status')}）")
        return None
    same = [g for g in reg["games"] if g["date"] == sg["date"] and g["comp"] == comp_id and g["div"] == div]
    key = f"{sg['date']}-{comp['slug']}-{DIV_SLUG[div]}-{len(same) + 1}"
    rnd = meta.get("round") or ""
    data = YahooParser(text, div, key, sg["date"], f"{comp['short']} {DIV_JA[div]}", rnd).parse()
    if data.get("warnings"):
        log.append(f"  注意（{key}）: " + " / ".join(data["warnings"][:5]))
    (DATA / "games").mkdir(exist_ok=True)
    (DATA / "raw").mkdir(exist_ok=True)
    (DATA / "raw" / f"{key}.txt").write_text(text, encoding="utf-8")
    (DATA / "games" / f"{key}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    game = Game(data)
    r = game.run()
    innings = max((e.get("inn") or 0) for e in data["events"]) if data["events"] else 9
    label = f"{DIV_JA[div]} {rnd}"
    if innings < 9:
        label += f"（{innings}回コールド）"
    texts = textgen.write_texts(data, r, game.log, label, stage_context(comp, div, rnd))
    for team, gr in (meta.get("grades") or {}).items():
        players.setdefault(team, {}).update(gr)
    cmeta = {"event_name": f"{comp['formal']} {DIV_JA[div]}", "short_name": comp["short"], "start": meta.get("time"), "end": meta.get("end")}
    (DATA / "cards").mkdir(exist_ok=True)
    paths = make_cards(r, DATA / "cards", texts.get("card_summary"), cmeta)
    url = f"{SITE_URL}/games/{key}.html"
    entry = dict(key=key, comp=comp_id, div=div, date=sg["date"], start=meta.get("time") or "", end=meta.get("end"),
                 venue=meta.get("venue") or comp.get("venue", ""), round=rnd + (f"（{innings}回コールド）" if innings < 9 else ""),
                 label=label, src=f"data/games/{key}.json", score=score_line(r),
                 summary=texts.get("summary", ""), card_summary=texts.get("card_summary", ""), comment=texts.get("comment", ""),
                 post_text=textgen.post_text(comp, label, score_line(r), texts.get("post_lead", ""), r, url),
                 text_by=texts.get("generated_by"), x_url=None, cards=[pathlib.Path(p).name for p in paths],
                 status="published", post_status="pending",
                 source={"site": "sportsnavi", "league": league, "id": sg["id"]},
                 processed_at=dt.datetime.now(JST).isoformat(timespec="minutes"))
    reg["games"].append(entry)
    log.append(f"  処理しました: {key} {entry['score']}（文章: {entry['text_by']}）")
    return entry


def refresh_texts(comps, reg, log):
    """定型文のまま投稿前の試合を、APIキーが使えるようになったら書き直す。"""
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return
    for g in reg["games"]:
        if g.get("text_by") != "template" or g.get("post_status") not in ("pending", "draft"):
            continue
        data = json.loads((ROOT / g["src"]).read_text(encoding="utf-8"))
        game = Game(data)
        r = game.run()
        comp = comps[g["comp"]]
        t = textgen.write_texts(data, r, game.log, g["label"], stage_context(comp, g["div"], g["round"]))
        if t.get("generated_by") == "template":
            continue
        g.update(summary=t.get("summary", ""), card_summary=t.get("card_summary", ""), comment=t.get("comment", ""), text_by=t["generated_by"],
                 post_text=textgen.post_text(comp, g["label"], g["score"], t.get("post_lead", ""), r, f"{SITE_URL}/games/{g['key']}.html"),
                 post_status="pending")
        cmeta = {"event_name": f"{comp['formal']} {DIV_JA[g['div']]}", "short_name": comp["short"], "start": g.get("start"), "end": g.get("end")}
        g["cards"] = [pathlib.Path(p).name for p in make_cards(r, DATA / "cards", g["card_summary"], cmeta)]
        log.append(f"  文章を書き直しました: {g['key']}")


def rewrite(comps, reg, keys, request, log):
    """指定した試合の文章を書き直す（Issue のコメント「直して：…」から呼ぶ）。"""
    for g in reg["games"]:
        if g["key"] not in keys:
            continue
        data = json.loads((ROOT / g["src"]).read_text(encoding="utf-8"))
        game = Game(data)
        r = game.run()
        comp = comps[g["comp"]]
        t = textgen.write_texts(data, r, game.log, g["label"], stage_context(comp, g["div"], g["round"]), request)
        g.update(summary=t.get("summary", ""), card_summary=t.get("card_summary", ""), comment=t.get("comment", ""), text_by=t.get("generated_by"),
                 post_text=textgen.post_text(comp, g["label"], g["score"], t.get("post_lead", ""), r, f"{SITE_URL}/games/{g['key']}.html"))
        if g.get("post_status") in ("pending", "draft"):
            g["post_status"] = "pending"
        cmeta = {"event_name": f"{comp['formal']} {DIV_JA[g['div']]}", "short_name": comp["short"], "start": g.get("start"), "end": g.get("end")}
        g["cards"] = [pathlib.Path(p).name for p in make_cards(r, DATA / "cards", g["card_summary"], cmeta)]
        log.append(f"  書き直しました: {g['key']}（{t.get('generated_by')}）")


def backfill_grades(comp, players, reg, log):
    """学年が未登録の試合（過去分）を、試合ページの選手一覧から補う。"""
    done = set()
    for g in reg["games"]:
        s = g.get("source") or {}
        if s.get("site") != "sportsnavi" or g.get("grades_done"):
            continue
        try:
            _, meta = SN.fetch_game(s["league"], s["id"])
        except Exception as e:  # noqa: BLE001
            log.append(f"  学年の取得に失敗: {g['key']} {e}")
            continue
        for team, gr in (meta.get("grades") or {}).items():
            players.setdefault(team, {}).update(gr)
        g["grades_done"] = True
        done.add(g["key"])
    if done:
        log.append(f"  学年を補完: {len(done)}試合")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", default="all", help="hs / univ / all")
    ap.add_argument("--date", help="処理する日（既定は今日・日本時間）")
    ap.add_argument("--late", action="store_true", help="遅い時間の再確認（終わっていない試合を知らせる）")
    ap.add_argument("--out", default="/tmp/brc-run.json")
    ap.add_argument("--rewrite", default="", help="文章を書き直す試合（カンマ区切り）")
    ap.add_argument("--request", default="", help="書き直しの注文")
    a = ap.parse_args()
    if a.rewrite:
        comps = load("competitions.json", {})
        reg = load("registry.json", {"games": []})
        log = []
        rewrite(comps, reg, [k for k in a.rewrite.split(",") if k], a.request, log)
        save("registry.json", reg)
        print("\n".join(log))
        return
    today = a.date or dt.datetime.now(JST).date().isoformat()
    comps = load("competitions.json", {})
    reg = load("registry.json", {"games": []})
    players = load("players.json", {})
    sched = load("schedule.json", {})
    divtext = load("divisions.json", {})
    log, new, unfinished = [f"実行日 {today}（{a.slot}）"], [], []
    done_ids = {(g["source"].get("league"), g["source"].get("id")) for g in reg["games"] if g.get("source")}
    for cid, c in comps.items():
        end = dt.date.fromisoformat(c["end"]) + dt.timedelta(days=c.get("buffer_days", 2))
        if not (c["start"] <= today <= end.isoformat()):
            continue
        log.append(f"{c['name']}")
        changed_divs = set()
        for dv in c["divisions"]:
            if a.slot not in ("all", dv.get("slot")):
                continue
            src = dv["source"]
            games = SN.list_games(src["league"], src["id_from"], src["id_to"])
            sched.setdefault(cid, {})[dv["div"]] = [{k: g[k] for k in ("id", "date", "home", "away", "status")} for g in games]
            for sg in games:
                if (src["league"], sg["id"]) in done_ids or sg["date"] > today:
                    continue
                if sg["status"] == "final":
                    e = process_game(cid, c, dv, sg, reg, players, log)
                    if e:
                        new.append(e["key"])
                        changed_divs.add(dv["div"])
                elif sg["date"] == today and sg["status"] in ("live", "scheduled"):
                    unfinished.append(f"{c['short']} {DIV_JA[dv['div']]} {sg['home']}vs{sg['away']}（{sg['status']}）")
        if a.slot == "all" or new:
            backfill_grades(c, players, reg, log)
        for div in changed_divs:
            lines = [f"{g['date']} {g['round']} {g['score']} {g.get('comment', '')}" for g in reg["games"] if g["comp"] == cid and g["div"] == div]
            s = textgen.division_summary(DIV_JA[div], lines)
            if s:
                divtext.setdefault(cid, {})[div] = {"summary": s, "updated": today}
    refresh_texts(comps, reg, log)
    reg["games"].sort(key=lambda g: (g["date"], int((g.get("start") or "0:0").split(":")[0]) * 60 + int((g.get("start") or "0:0").split(":")[1])))
    save("registry.json", reg)
    save("players.json", players)
    save("schedule.json", sched)
    save("divisions.json", divtext)
    if unfinished:
        log.append("終わっていない試合: " + "、".join(unfinished))
    out = {"date": today, "slot": a.slot, "new": new, "unfinished": unfinished if a.late else [], "log": log}
    pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main()
