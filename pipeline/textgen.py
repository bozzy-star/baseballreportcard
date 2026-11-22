"""試合のサマリー・一言・X投稿文を作る。

ANTHROPIC_API_KEY があれば Claude で書き、なければ記録から決まった形の文章を作る。
"""
import json
import os
import re
import urllib.request

MODEL = os.environ.get("BRC_MODEL", "claude-opus-5-5")
STYLE = os.path.join(os.path.dirname(__file__), "..", "data", "style.md")
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
    # 試合が動いた場面（勝利確率の動きが大きい順）。どちらのチームから見た動きかを付ける
    turns = []
    for x in sorted(log, key=lambda x: -abs(x["home_wp_after"] - x["home_wp_before"]))[:5]:
        hb, ha = x["home_wp_before"], x["home_wp_after"]
        gain_home = ha >= hb
        team = g["home"] if gain_home else g["away"]
        before, after = (hb, ha) if gain_home else (1 - hb, 1 - ha)
        off = "away" if x["half"] == "top" else "home"
        side = "攻撃" if g[off] == team else "守り"
        txt = next((e.get("result_text") for e in data["events"] if e.get("inn") == x["inn"] and e.get("half") == x["half"]
                    and e.get("batter") == x.get("batter") and e.get("type") == x["type"]), "") or ""
        turns.append(f"{x['inn']}回{'表' if x['half'] == 'top' else '裏'}（{team}の{side}） {nm(x.get('batter'))} {TYPE_JA.get(x['type'], x['type'])} "
                     f"→ {team}の勝利確率 {before:.0%}→{after:.0%}（{(after - before) * 100:+.0f}ポイント） {txt[:40]}")
    # 試合の流れ（逆転・リード変更・最大点差・サヨナラ）
    sc_ = {"away": 0, "home": 0}
    lead, changes, max_behind = None, 0, {"away": 0, "home": 0}
    for e in data["events"]:
        if not e.get("runs"):
            continue
        sc_["away" if e["half"] == "top" else "home"] += e["runs"]
        cur = "away" if sc_["away"] > sc_["home"] else ("home" if sc_["home"] > sc_["away"] else None)
        if cur and lead and cur != lead:
            changes += 1
        if cur:
            lead = cur
        for t in ("away", "home"):
            o = "home" if t == "away" else "away"
            max_behind[t] = max(max_behind[t], sc_[o] - sc_[t])
    ws = "home" if f["winner"] == g["home"] else "away"
    last = log[-1] if log else {}
    story = {"リードが入れ替わった回数": changes, "勝ったチームが最大で何点負けていたか": max_behind[ws],
             "サヨナラ勝ち": bool(ws == "home" and last.get("half") == "bottom" and (last.get("inn") or 0) >= 9 and last.get("home_wp_before", 1) < 0.9),
             "コールド": "コールド" in label}
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
        "scoring": scoring, "turning_points": turns, "story": story, "awards": aw, "pitchers": pit,
    }


PROMPT = """あなたは野球の試合を伝えるスポーツライターです。下の「書き方の指示書」に従い、「試合の材料」だけを使って日本語で書いてください。
「turning_points」は試合が動いた場面（勝利確率が大きく動いた順）です。山場はここから選んでください。
「story」は試合の流れの要約です（逆転・最大点差・サヨナラなど）。書き出しの見出しづくりに使ってください。
{context}

--- 書き方の指示書 ---
{style}
--- ここまで ---

出力は次のJSONだけ（前後に何も書かない）：
{{"summary": "試合の流れ（200〜300字。先制→同点・逆転→決着の順に）",
 "card_summary": "画像カード用の短い要約（100〜140字）",
 "comment": "大会ページ用の一言（35〜55字）",
 "post_lead": "X投稿の一言（30〜50字）"}}

試合の材料：
{facts}
"""


def _call(prompt, key, max_tokens=3000):
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(API, data=body, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            out = json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:300]}")
    text = "".join(c.get("text", "") for c in out.get("content", []) if c.get("type") == "text")
    if not text.strip():
        raise RuntimeError(f"文章が返ってきませんでした（stop_reason={out.get('stop_reason')}, 種類={[c.get('type') for c in out.get('content', [])]}）")
    return text


def _claude(prompt, key):
    text = _call(prompt, key)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError(f"JSONが見つかりません: {text[:200]!r}")
    return json.loads(m.group(0))


def _fallback(fx):
    pts = [re.sub(r"（.*", "", x).strip() for x in fx["scoring"]][:6]
    s = f"{fx['winner']}が{fx['score_w']}で勝利。" + (("得点経過は、" + "、".join(pts) + "。") if pts else "")
    return {"summary": s, "card_summary": s[:140], "comment": f"{fx['winner']}が{fx['score_w']}で勝利。", "post_lead": f"{fx['winner']}が勝利。",
            "generated_by": "template"}


def _style():
    try:
        return open(STYLE, encoding="utf-8").read()
    except OSError:
        return ""


def write_texts(data, r, log, label, context="", request=""):
    fx = facts(data, r, log, label)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        try:
            ctx = context + (f"\n今回は次の注文があります。必ず反映してください：{request}" if request else "")
            out = _claude(PROMPT.format(facts=json.dumps(fx, ensure_ascii=False, indent=1), style=_style(), context=ctx), key)
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
        return _call(DIV_PROMPT.format(div=div_name, games="\n".join(games_lines)), key, 1500).strip()
    except Exception as e:  # noqa: BLE001
        print(f"[textgen] 大会まとめの作成に失敗: {e}")
        return None


def post_text(comp, label, score_line, lead, r, url):
    """X投稿文（重み付き280字以内）。"""
    from brc.post import weighted_len as _wl

    def weighted_len(t):  # Xは URL を23文字として数える
        return _wl(re.sub(r"https?://\S+", "x" * 23, t))
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
