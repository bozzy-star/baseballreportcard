"""採点カード画像（X投稿用 1080×1350）を、勝ちチーム・負けチームで1枚ずつ作る。

使い方:  python -m brc.card 採点結果.result.json -o output
フォントは Noto Sans CJK（Mac では BRC_FONT_DIR で場所を指定、例: ヒラギノを使う場合は下の FONT_CANDIDATES を参照）。
"""
import argparse
import json
import os
import pathlib
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
NAVY, PANEL, INK, SUB = (14, 27, 51), (26, 44, 78), (245, 247, 250), (150, 165, 190)
GOLD, UP, DOWN, LINE = (226, 180, 72), (84, 196, 140), (232, 104, 104), (40, 56, 86)
BRAND = "ベースボール通信簿"
HANDLE = "@BaseBalltannin"
SITE = "baseballreportcard.com"

FONT_CANDIDATES = [
    os.environ.get("BRC_FONT_DIR", ""),
    "/usr/share/fonts/opentype/noto",
    "/opt/homebrew/share/fonts",
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
]
WEIGHT_FALLBACK = {  # Mac 標準のヒラギノ（Noto がない場合）
    "Black": "ヒラギノ角ゴシック W8.ttc", "Bold": "ヒラギノ角ゴシック W6.ttc",
    "Medium": "ヒラギノ角ゴシック W5.ttc", "Regular": "ヒラギノ角ゴシック W3.ttc",
}
_cache = {}
ASSETS = pathlib.Path(__file__).with_name("assets")


def silhouette(name, height, color, line=None):
    """シルエット画像を指定色に塗り替える（白い線は line 色に）。"""
    im = Image.open(ASSETS / f"{name}.png").convert("RGBA")
    im = im.resize((int(im.width * height / im.height), height), Image.LANCZOS)
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r_, g_, b_, a_ = px[x, y]
            if a_ == 0:
                continue
            c = color if (r_ + g_ + b_) < 384 else (line or color)
            px[x, y] = (*c[:3], a_)
    return im


def wrap(d, text, font, max_w):
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=font) > max_w:
            if ch in "、。，．）」』！？ー" and cur:  # 句読点は行頭に置かず、前の行の最後の字と一緒に次の行へ
                lines.append(cur[:-1])
                cur = cur[-1] + ch
            else:
                lines.append(cur)
                cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def F(weight, size):
    key = (weight, size)
    if key in _cache:
        return _cache[key]
    for d in FONT_CANDIDATES:
        if d and os.path.exists(os.path.join(d, f"NotoSansCJK-{weight}.ttc")):
            f = ImageFont.truetype(os.path.join(d, f"NotoSansCJK-{weight}.ttc"), size, index=0)
            break
    else:
        f = ImageFont.truetype(os.path.join("/System/Library/Fonts", WEIGHT_FALLBACK[weight]), size)
    _cache[key] = f
    return f


def rcol(r):
    return UP if r >= 7.0 else (INK if r >= 6.0 else DOWN)


def fit(d, text, weight, size, max_w):
    """幅に収まるまで文字を小さくする。"""
    while size > 14 and d.textlength(text, font=F(weight, size)) > max_w:
        size -= 1
    return F(weight, size)


def team_card(r, side, path):
    g, f, a = r["game"], r["final"], r["awards"]
    team = g[side]
    won = f["winner"] == team
    rows = [x for x in r["ratings"] if x["side"] == side]

    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)

    # ヘッダー
    d.text((60, 44), BRAND, font=F("Bold", 26), fill=GOLD)
    d.text((60, 80), f"{team} 通信簿", font=fit(d, f"{team} 通信簿", "Black", 60, W - 260), fill=INK)
    chip = "勝" if won else "敗"
    d.rounded_rectangle((W - 160, 84, W - 60, 156), radius=16, fill=GOLD if won else LINE)
    d.text((W - 110, 120), chip, font=F("Black", 44), fill=NAVY if won else INK, anchor="mm")
    m, dd = g.get("date", "----")[5:7], g.get("date", "----")[8:10]
    sub = f"{g.get('tournament', '')} {g.get('round', '')}　{g['away']} {f['away']}-{f['home']} {g['home']}　{int(m)}.{int(dd)}"
    d.text((62, 160), sub, font=fit(d, sub, "Medium", 28, W - 124), fill=SUB)

    # 表彰枠
    if won:
        picks = [("投手MVP", a.get("pitcher_mvp")), ("野手MVP", a.get("fielder_mvp"))]
    else:
        picks = [("敢闘賞", a.get("fighting_spirit"))]
    picks = [(lab, next(x for x in rows if x["player"] == n)) for lab, n in picks if n]
    if not picks and rows:  # 該当者なしのときはチーム最高点
        picks = [("チーム最高点", rows[0])]
    top, bot = 214, 420
    d.rounded_rectangle((60, top, W - 60, bot), radius=24, fill=PANEL)
    colw = (W - 120) // len(picks)
    for i, (lab, x) in enumerate(picks):
        x0 = 60 + i * colw
        if i:
            d.line((x0, top + 28, x0, bot - 28), fill=LINE, width=2)
        name_w = colw - (230 if len(picks) == 1 else 180)
        d.text((x0 + 36, top + 24), lab, font=F("Bold", 28), fill=GOLD)
        d.text((x0 + 36, top + 64), x["player"].replace(" ", ""),
               font=fit(d, x["player"].replace(" ", ""), "Black", 60 if len(picks) == 1 else 50, name_w), fill=INK)
        d.text((x0 + 38, top + 152), f"{x['pos']}　{x['stat']}",
               font=fit(d, f"{x['pos']}　{x['stat']}", "Medium", 26, colw - 60), fill=SUB)
        d.text((x0 + colw - 36, top + 18), f"{x['score']:.1f}",
               font=F("Black", 100 if len(picks) == 1 else 80), fill=GOLD, anchor="ra")
    if not any(lab != "チーム最高点" for lab, _ in picks):
        note = "MVP該当なし" if won else "敢闘賞該当なし"
        d.text((W - 96, bot - 44), note, font=F("Medium", 22), fill=SUB, anchor="ra")

    # 一覧
    shown = {x["player"] for _, x in picks}
    rest = [x for x in rows if x["player"] not in shown]
    y0 = bot + 30
    d.text((60, y0), "選手", font=F("Medium", 24), fill=SUB)
    d.text((W - 290, y0), "貢献度(WPA)", font=F("Medium", 22), fill=SUB, anchor="ma")
    d.text((W - 60, y0), "採点", font=F("Medium", 24), fill=SUB, anchor="ra")
    y = y0 + 42
    avail = H - 160 - y
    rowh = max(40, min(64, avail // max(1, len(rest))))
    big = rowh >= 56
    for x in rest:
        d.line((60, y, W - 60, y), fill=LINE, width=2)
        w, sc = x["wpa"], x["score"]
        cy = y + rowh // 2
        d.text((60, cy), x["pos"], font=F("Bold", 26 if big else 22), fill=SUB, anchor="lm")
        nm = x["player"].replace(" ", "")
        d.text((106, cy), nm, font=fit(d, nm, "Bold", 32 if big else 26, 210), fill=INK, anchor="lm")
        d.text((330, cy), x["stat"], font=fit(d, x["stat"], "Regular", 22 if big else 19, 330), fill=SUB, anchor="lm")
        cx, scale = W - 290, 500
        bw = min(int(abs(w) * scale), 110)
        col = UP if w > 0.005 else (DOWN if w < -0.005 else SUB)
        by = cy + (10 if big else 8)
        if w >= 0:
            d.rectangle((cx, by, cx + max(bw, 2), by + 7), fill=col)
        else:
            d.rectangle((cx - bw, by, cx, by + 7), fill=col)
        d.text((cx, cy - 2), "±0.000" if abs(w) < 0.0005 else f"{w:+.3f}",
               font=F("Medium", 22 if big else 19), fill=col, anchor="mb")
        d.text((W - 60, cy), f"{sc:.1f}", font=F("Black", 42 if big else 34), fill=rcol(sc), anchor="rm")
        y += rowh
    d.line((60, y, W - 60, y), fill=LINE, width=2)

    # フッター
    d.text((60, H - 134), "採点＝6.0（及第点）＋ 勝利確率をどれだけ動かしたか（WPA）× 12。0.5点刻み・10点満点。",
           font=F("Regular", 21), fill=SUB)
    d.text((60, H - 102), "守備・走塁の手柄も配分。勝利確率は簡易モデルによる試算。", font=F("Regular", 21), fill=SUB)
    d.text((60, H - 44), f"{BRAND}　{HANDLE}", font=F("Bold", 22), fill=GOLD, anchor="lm")
    d.text((W - 60, H - 44), SITE, font=F("Medium", 22), fill=SUB, anchor="rm")
    img.save(path)
    return path


POS_FULL = {"P": "投手", "C": "捕手", "1B": "一塁手", "2B": "二塁手", "3B": "三塁手", "SS": "遊撃手",
            "LF": "左翼手", "CF": "中堅手", "RF": "右翼手", "DH": "指名打者"}


def player_meta(x, league):
    """「仙台育英　2番・遊撃手」＋大学以上は「#6」。"""
    parts = []
    if x.get("order"):
        parts.append(f"{x['order']}番")
    pos = POS_FULL.get(x.get("pos_code") or "", "") or {"打": "代打", "走": "代走"}.get(x.get("pos"), x.get("pos", ""))
    if pos:
        parts.append(pos)
    s = f"{x['team']}　" + "・".join(parts)
    if league not in ("HS",) and x.get("number"):
        s += f"・背番号{x['number']}"
    return s


def _reason_text(x):
    parts = []
    for rs in x.get("reasons", []):
        parts.append(rs["text"] + (f"（{rs['wpa']:+.2f}）" if rs.get("wpa") is not None else ""))
    return parts


def ranking_card(r, path, top=3, summary=None, meta=None, side=None):
    """高校向け：ベースボール通信簿／大見出し／結果／大会名・日時／試合運び／打者（1位はMVP枠）／投手MVP。"""
    meta = meta or {}
    g, f, a = r["game"], r["final"], r["awards"]
    ws = "home" if f["home"] > f["away"] else "away"
    ls = "away" if ws == "home" else "home"
    side = side or ws
    team = g[side]
    batters = [x for x in r["ratings"] if not x["pitcher"] and x["side"] == side][:top]
    award_p = a.get("pitcher_mvp") if side == ws else a.get("fighting_spirit")
    pm = next((x for x in r["ratings"] if x["player"] == award_p and x["pitcher"]), None)
    plabel = "投手MVP" if side == ws else ("敢闘賞" if pm else "投手部門")

    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    # ベースボール通信簿
    d.text((60, 40), BRAND, font=F("Bold", 26), fill=GOLD)
    # 大見出し
    short = meta.get("short_name") or g.get("tournament", "").split(" ")[0]
    head = f"{short} {g[ws]} 対 {g[ls]} の通信簿"
    d.text((60, 76), head, font=fit(d, head, "Black", 46, W - 120), fill=INK)
    # 結果
    res = f"{g[ws]} {f[ws]} - {f[ls]} {g[ls]}"
    d.text((60, 140), res, font=fit(d, res, "Bold", 38, W - 120), fill=GOLD)
    # 大会名・日付
    ev = meta.get("event_name") or g.get("tournament", "")
    ev = f"{ev} {g.get('round', '')}".strip()
    d.text((60, 198), ev, font=fit(d, ev, "Medium", 24, W - 120), fill=SUB)
    date = g.get("date", "").replace("-", ".")
    if date:
        y_, m_, d_ = date.split(".")
        date = f"{y_}.{int(m_)}.{int(d_)}"
    when = date + (f"　{meta['start']}開始" if meta.get("start") else "") + (f"　{meta['end']}終了" if meta.get("end") else "")
    d.text((60, 232), when, font=F("Medium", 24), fill=SUB)
    # 試合運び（見出しなし）
    y = 280
    summary = summary or r.get("summary")
    if summary:
        size, lh = 23, 33
        while True:
            f_ = F("Regular", size)
            lines_ = wrap(d, summary.strip(), f_, W - 120)
            if len(lines_) * lh <= 140 or size <= 18:
                break
            size, lh = size - 1, lh - 2
        for k, line in enumerate(lines_):
            d.text((60, y + k * lh), line, font=f_, fill=INK)
        y += len(lines_) * lh + 10

    # 打者
    d.text((60, y), f"打者　{team}", font=F("Bold", 26), fill=GOLD)
    y += 40
    for i, x in enumerate(batters):
        nm = x["player"].replace(" ", "")
        over = x.get("raw_score", 0) > 10
        if i == 0:
            label = "野手MVP" if x["player"] == a.get("fielder_mvp") else ("敢闘賞" if x["player"] == a.get("fighting_spirit") else "チーム1位")
            bh = 206
            d.rounded_rectangle((60, y, W - 60, y + bh), radius=22, outline=GOLD, width=3)
            ico = silhouette("batter", bh - 28, GOLD)
            img.paste(ico, (72, y + 12), ico)
            x0 = 72 + ico.width + 14
            d.text((x0, y + 14), label, font=F("Bold", 28), fill=GOLD)
            d.text((x0, y + 48), nm, font=fit(d, nm, "Black", 44, 400), fill=INK)
            mt = f"{player_meta(x, g.get('league'))}　{x['stat']}"
            d.text((x0 + 2, y + 104), mt, font=fit(d, mt, "Medium", 22, (W - 300 - x0) if over else 540), fill=SUB)
            for j, t in enumerate(_reason_text(x)[:2]):
                d.text((x0 + 2, y + 136 + j * 28), "・" + t, font=fit(d, "・" + t, "Regular", 21, 540), fill=INK)
            d.text((W - 96, y + 18), f"{x['score']:.1f}", font=F("Black", 74 if over else 84), fill=GOLD, anchor="ra")
            if over:
                _badge(d, x, W - 96, y + 118)
            y += bh + 14
        else:
            bh = 148
            d.rounded_rectangle((60, y, W - 60, y + bh), radius=18, fill=PANEL)
            d.text((104, y + bh // 2), str(i + 1), font=F("Black", 70), fill=INK, anchor="mm")
            d.text((160, y + 14), nm, font=fit(d, nm, "Black", 36, 420), fill=INK)
            mt = f"{player_meta(x, g.get('league'))}　{x['stat']}"
            d.text((162, y + 60), mt, font=fit(d, mt, "Medium", 21, 560), fill=SUB)
            for j, t in enumerate(_reason_text(x)[:2]):
                d.text((162, y + 88 + j * 27), "・" + t, font=fit(d, "・" + t, "Regular", 20, 560), fill=INK)
            d.text((W - 96, y + 14), f"{x['score']:.1f}", font=F("Black", 60), fill=rcol(x["score"]), anchor="ra")
            if over:
                _badge(d, x, W - 96, y + 98)
            elif x["player"] == a.get("fighting_spirit"):
                d.text((W - 96, y + 112), "敢闘賞", font=F("Bold", 22), fill=GOLD, anchor="ra")
            y += bh + 10

    # 投手
    y += 2
    d.text((60, y), f"投手　{team}", font=F("Bold", 26), fill=GOLD)
    y += 40
    if pm:
        bh = 164
        d.rounded_rectangle((60, y, W - 60, y + bh), radius=22, outline=GOLD, width=3)
        ico = silhouette("pitcher", bh - 28, GOLD, NAVY)
        img.paste(ico, (72, y + 12), ico)
        x0 = 72 + ico.width + 14
        d.text((x0, y + 12), plabel, font=F("Bold", 28), fill=GOLD)
        nm = pm["player"].replace(" ", "")
        d.text((x0, y + 46), nm, font=fit(d, nm, "Black", 44, 420), fill=INK)
        mt = f"{pm['team']}　{pm['stat'].split('／投 ')[-1]}"
        d.text((x0 + 2, y + 102), mt, font=fit(d, mt, "Medium", 22, 560), fill=SUB)
        rs = [q["text"] + f"（{q['wpa']:+.2f}）" for q in pm.get("reasons_all", []) if q.get("wpa") is not None][:1]
        if rs:
            d.text((x0 + 2, y + 130), "・" + rs[0], font=fit(d, "・" + rs[0], "Regular", 21, 560), fill=INK)
        pover = pm.get("raw_score", 0) > 10
        d.text((W - 96, y + 18 - (8 if pover else 0)), f"{pm['score']:.1f}", font=F("Black", 74 if pover else 84), fill=GOLD, anchor="ra")
        if pover:
            _badge(d, pm, W - 96, y + 112)
    else:
        bh = 96
        d.rounded_rectangle((60, y, W - 60, y + bh), radius=22, outline=LINE, width=3)
        ico = silhouette("pitcher", 80, SUB, NAVY)
        img.paste(ico, (80, y + 8), ico)
        d.text((180, y + bh // 2), plabel, font=F("Bold", 28), fill=GOLD, anchor="lm")
        d.text((330, y + bh // 2), "該当者なし", font=F("Black", 38), fill=INK, anchor="lm")
        note = "7.0点以上の投手なし" if side == ws else "8.0点以上の投手なし"
        d.text((W - 96, y + bh // 2), note, font=F("Medium", 21), fill=SUB, anchor="rm")

    d.text((60, H - 108), "採点＝6.0（及第点）＋ 勝利確率をどれだけ動かしたか × 12。0.5点刻み・10点満点。",
           font=F("Regular", 19), fill=SUB)
    d.text((60, H - 82), "（ ）内はそのプレーで勝利確率が動いた量。上限突破は10点を超えた分も含めた試算。",
           font=F("Regular", 19), fill=SUB)
    d.text((60, H - 34), f"{BRAND}　{HANDLE}", font=F("Bold", 22), fill=GOLD, anchor="lm")
    d.text((W - 60, H - 34), SITE, font=F("Medium", 22), fill=SUB, anchor="rm")
    img.save(path)
    return path


def _badge(d, x, right, top):
    badge = f"上限突破！ {x['raw_score']:.1f}"
    bw_ = d.textlength(badge, font=F("Bold", 21)) + 26
    d.rounded_rectangle((right - bw_, top, right, top + 30), radius=15, fill=GOLD)
    d.text((right - bw_ / 2, top + 15), badge, font=F("Bold", 21), fill=NAVY, anchor="mm")


def player_card(r, x, label, path, meta=None):
    """選手1人の通信簿カード（MVP・敢闘賞）。本人や家族が保存・共有しやすい形。"""
    meta = meta or {}
    g, f = r["game"], r["final"]
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    d.text((60, 44), BRAND, font=F("Bold", 26), fill=GOLD)
    short = meta.get("short_name") or g.get("tournament", "").split(" ")[0]
    ev = f"{short} {g.get('round', '')}".strip()
    d.text((W - 60, 44), ev, font=fit(d, ev, "Medium", 24, 520), fill=SUB, anchor="ra")
    # ラベル
    lw = d.textlength(label, font=F("Black", 40)) + 56
    d.rounded_rectangle((60, 110, 60 + lw, 176), radius=33, fill=GOLD)
    d.text((60 + lw / 2, 143), label, font=F("Black", 40), fill=NAVY, anchor="mm")
    # 名前と所属
    nm = x["player"].replace(" ", "")
    d.text((60, 206), nm, font=fit(d, nm, "Black", 118, W - 120), fill=INK)
    sub = player_meta(x, g.get("league"))
    if meta.get("grade"):
        sub = sub.replace("　", f"（{meta['grade']}）　", 1)
    d.text((64, 356), sub, font=fit(d, sub, "Bold", 34, W - 128), fill=SUB)
    # 点数
    top, bot = 430, 760
    d.rounded_rectangle((60, top, W - 60, bot), radius=28, fill=PANEL)
    ico = silhouette("pitcher" if x["pitcher"] else "batter", bot - top - 40, GOLD, PANEL if x["pitcher"] else None)
    img.paste(ico, (90, top + 20), ico)
    d.text((W - 110, top + (bot - top) // 2 - 10), f"{x['score']:.1f}", font=F("Black", 230), fill=GOLD, anchor="rm")
    d.text((W - 110, bot - 40), "10点満点", font=F("Bold", 28), fill=SUB, anchor="rm")
    if x.get("raw_score", 0) > 10:
        _badge(d, x, W - 110, top + 26)
    # 成績と決め手
    y = 800
    st = x["stat"]
    d.text((60, y), st, font=fit(d, st, "Bold", 36, W - 120), fill=INK)
    y += 62
    agg = {}
    for q in (x.get("reasons_all") or x.get("reasons") or []):
        if q.get("wpa") is not None:
            a_ = agg.setdefault(q["text"], {"text": q["text"], "wpa": 0.0, "n": 0})
            a_["wpa"] += q["wpa"]
            a_["n"] += 1
    rs = sorted((q for q in agg.values() if q["wpa"] >= 0.01), key=lambda q: -q["wpa"])[:3]
    for q in rs:
        if q["n"] > 1:
            q["text"] += f"（{q['n']}度）"
        t = f"・{q['text']}"
        d.text((64, y), t, font=fit(d, t, "Medium", 30, W - 330), fill=INK)
        d.text((W - 60, y), f"勝利確率 +{q['wpa'] * 100:.0f}%", font=F("Bold", 28), fill=UP, anchor="ra")
        y += 48
    # 試合
    y = max(y + 20, 1060)
    res = f"{g['away']} {f['away']} - {f['home']} {g['home']}"
    d.line((60, y, W - 60, y), fill=LINE, width=2)
    d.text((60, y + 24), res, font=fit(d, res, "Bold", 34, W - 120), fill=GOLD)
    date = g.get("date", "")
    if date:
        y_, m_, d_ = date.split("-")
        date = f"{y_}.{int(m_)}.{int(d_)}"
    evf = f"{meta.get('event_name') or g.get('tournament', '')}　{date}".strip()
    d.text((60, y + 78), evf, font=fit(d, evf, "Medium", 22, W - 120), fill=SUB)
    d.text((60, H - 44), f"{BRAND}　{HANDLE}", font=F("Bold", 22), fill=GOLD, anchor="lm")
    d.text((W - 60, H - 44), SITE, font=F("Medium", 22), fill=SUB, anchor="rm")
    img.save(path)
    return path


def award_picks(r, limit=2):
    """選手カードを作る選手（野手MVP→投手MVP→敢闘賞の順で最大 limit 人）。"""
    a = r["awards"]
    out = []
    for label, key in (("野手MVP", "fielder_mvp"), ("投手MVP", "pitcher_mvp"), ("敢闘賞", "fighting_spirit")):
        x = next((q for q in r["ratings"] if a.get(key) and q["player"] == a[key]), None)
        if x and x["player"] not in [p[1]["player"] for p in out]:
            out.append((label, x))
    return out[:limit]


def player_cards(r, out_dir, meta=None, grades=None):
    out = pathlib.Path(out_dir)
    gid = r["game"].get("id", "game")
    paths = []
    for i, (label, x) in enumerate(award_picks(r)):
        m = dict(meta or {}, grade=((grades or {}).get(x["team"]) or {}).get(x["player"]))
        paths.append(player_card(r, x, label, out / f"{gid}-p{i + 1}.png", m))
    return paths


def make_cards(r, out_dir, summary=None, meta=None):
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    gid = r["game"].get("id", "game")
    if r["game"].get("league") in ("HS", "UNIV") or summary:
        f = r["final"]
        ws = "home" if f["home"] > f["away"] else "away"
        ls = "away" if ws == "home" else "home"
        return [ranking_card(r, out / f"{gid}-1-{ws}.png", summary=summary, meta=meta, side=ws),
                ranking_card(r, out / f"{gid}-2-{ls}.png", summary=summary, meta=meta, side=ls)]
    winner = r["final"]["winner"]
    order = ["away", "home"]
    if winner == r["game"]["home"]:
        order = ["home", "away"]
    return [team_card(r, s, out / f"{gid}-{i + 1}-{s}.png") for i, s in enumerate(order)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("result_json")
    ap.add_argument("-o", "--out", default="output")
    ap.add_argument("--summary", help="試合運びの文章（テキストファイル、120〜160字）")
    ap.add_argument("--event-name", help="大会の正式名称 例: 明治神宮外苑創建百年記念 第57回明治神宮野球大会 高校の部")
    ap.add_argument("--short-name", help="大見出し用の大会名 例: 明治神宮大会")
    ap.add_argument("--start", help="開始時刻 例 8:30")
    ap.add_argument("--end", help="終了時刻 例 10:45")
    a = ap.parse_args()
    r = json.loads(pathlib.Path(a.result_json).read_text(encoding="utf-8"))
    summ = pathlib.Path(a.summary).read_text(encoding="utf-8") if a.summary else None
    meta = {"event_name": a.event_name, "short_name": a.short_name, "start": a.start, "end": a.end}
    for p in make_cards(r, a.out, summ, meta):
        print(p)


if __name__ == "__main__":
    main()
