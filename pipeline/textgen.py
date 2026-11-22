"""試合のサマリー・一言・X投稿文を作る。

ANTHROPIC_API_KEY があれば Claude で書き、なければ記録から決まった形の文章を作る。
"""
import json
import os
import re
import urllib.request

MODEL = os.environ.get("BRC_MODEL", "claude-sonnet-5-5")
API = "https://api.anthropic.com/v1/messages"
TYPE_JA = {"HR": "本塁打", "3B": "三塁打", "2B": "二塁打", "1B": "安打", "BB": "四球", "HBP": "死球", "SF": "犠飛", "E": "失策",
           "OUT": "内野ゴロ", "WP": "暴投", "PB": "捕逸", "DP": "併殺打"}


def nm(s):
    return (s or "").replace(" ", "")


def facts(data, r, log, label):
    """文章を書くための材料（試合経過の要点）。"""
    g, f = r["game"], r["final"]
    score = {"away": 0, "home": 0}
    scoring = []
    for e in data["events"]:
        runs = e.get("runs") or 0
        if not runs:
            continue
        side = "away" if e.get("half") == "top" else "home"
        score[side] += runs
        who = nm(e.get("batter")) or "（走者・守備のミス）"
        scoring.append(f"{e['inn']}回{'表' if e['half'] == 'top' else '裏'} {g[side]} {who} {TYPE_JA.get(e.get('type'), e.get('type'))} "
                       f"{runs}点（{g['away']} {score['away']}-{score['home']} {g['home']}） {(e.get('result_text') or '')[:40]}")
    big = sorted(log, key=lambda x: -abs(x["home_wp_after"] - x["home_wp_before"]))[:4]
    bigs = [f"{x['inn']}回{'表' if x['half'] == 'top' else '裏'} {nm(x.get('batter'))} {x['type']} 勝利確率(ホーム) {x['home_wp_before']:.0%}→{x['home_wp_after']:.0%}"
            for x in big]
    a = r["awards"]
    sc = {x["player"]: x for x in r["ratings"]}
    aw = []
    for lab, k in (("野手MVP", "fielder_mvp"), ("投手MVP", "pitcher_mvp"), ("敢闘賞", "fighting_spirit")):
        n = a.get(k)
        if n:
            x = sc[n]
            aw.append(f"{lab}: {nm(n)}（{x['team']}）{x['score']:.1f}点 {x['stat']} 決め手={(x.get('reasons') or [{}])[0].get('text', '')}")
    pit = [f"{nm(x['player'])}（{x['team']}）{x['stat']}" for x in r["ratings"] if x["pitcher"]]
    ls = g.get("linescore") or {}
    return {
        "label": label, "away": g["away"], "home": g["home"], "final": f"{g['away']} {f['away']}-{f['home']} {g['home']}",
        "winner": f["winner"], "score_w": f"{max(f['away'], f['home'])}-{min(f['away'], f['home'])}", "innings": len(ls.get("away", [])) or None,
        "scoring": scoring, "big_plays": bigs, "awards": aw, "pitchers": pit,
    }


PROMPT = """あなたは野球の試合を伝えるライターです。下の「試合の材料」だけを使い、事実を足さずに日本語で書いてください。
選手名は姓だけ（例：川北）。数字・回・得点経過は材料どおりに。材料にない出来事（球速、観客、天気、通算記録、過去の対戦など）は書かない。
接戦・逆転・サヨナラなど劇的な試合は、少し色をつけた書き出しにしてよい（例：「手に汗にぎる〜」）。大差の試合は淡々と。

出力は次のJSONだけ（前後に何も書かない）：
{{"summary": "試合の流れ（200〜300字。先制→同点・逆転→決着の順に）",
 "card_summary": "画像カード用の短い要約（100〜140字）",
 "comment": "大会ページ用の一言（35〜55字）",
 "post_lead": "X投稿の一言（30〜50字）"}}

試合の材料：
{facts}
"""


def _claude(prompt, key):
    body = json.dumps({"model": MODEL, "max_tokens": 1200, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(API, data=body, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as res:
        out = json.loads(res.read().decode())
    text = "".join(c.get("text", "") for c in out.get("content", []))
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0))


def _fallback(fx):
    pts = [re.sub(r"（.*", "", x).strip() for x in fx["scoring"]][:6]
    s = f"{fx['winner']}が{fx['score_w']}で勝利。" + (("得点経過は、" + "、".join(pts) + "。") if pts else "")
    return {"summary": s, "card_summary": s[:140], "comment": f"{fx['winner']}が{fx['score_w']}で勝利。", "post_lead": f"{fx['winner']}が勝利。",
            "generated_by": "template"}


def write_texts(data, r, log, label):
    fx = facts(data, r, log, label)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        try:
            out = _claude(PROMPT.format(facts=json.dumps(fx, ensure_ascii=False, indent=1)), key)
            out["generated_by"] = MODEL
            return out
        except Exception as e:  # noqa: BLE001
            print(f"[textgen] Claude API に失敗したので定型文にします: {e}")
    return _fallback(fx)


DIV_PROMPT = """あなたは野球の大会を伝えるライターです。下の「これまでの試合」だけを使い、{div}のここまでの流れを日本語で180〜260字にまとめてください。
勝ち上がったチームと、印象的な試合・選手に触れる。事実を足さない。選手名は姓だけ。文章だけを出力。

これまでの試合（古い順）：
{games}
"""


def division_summary(div_name, games_lines):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        body = json.dumps({"model": MODEL, "max_tokens": 800, "messages": [{"role": "user", "content": DIV_PROMPT.format(div=div_name, games="\n".join(games_lines))}]}).encode()
        req = urllib.request.Request(API, data=body, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as res:
            out = json.loads(res.read().decode())
        return "".join(c.get("text", "") for c in out.get("content", [])).strip()
    except Exception as e:  # noqa: BLE001
        print(f"[textgen] 大会まとめの作成に失敗: {e}")
        return None


def post_text(comp, label, score_line, lead, r, url):
    """X投稿文（重み付き280字以内）。"""
    from brc.post import weighted_len
    a = r["awards"]
    sc = {x["player"]: x["score"] for x in r["ratings"]}
    lines = [f"【{comp['short']} {label}】", score_line, "", lead, ""]
    for lab, k in (("野手MVP", "fielder_mvp"), ("投手MVP", "pitcher_mvp"), ("敢闘賞", "fighting_spirit")):
        n = a.get(k)
        if n:
            lines.append(f"{lab} {nm(n)} {sc[n]:.1f}")
        elif k != "fighting_spirit":
            lines.append(f"{lab} 該当者なし")
    tags = " ".join(comp.get("hashtags", []) + ["#ベースボール通信簿"])
    tail = ["", tags, url]
    text = "\n".join(lines + tail)
    while weighted_len(text) > 280 and len(lead) > 10:
        lead = lead[:-6] + "…"
        lines[3] = lead
        text = "\n".join(lines + tail)
    return text
