"""スポーツナビ（baseball.yahoo.co.jp）のテキスト速報を、採点エンジンの入力JSONに変換する。

使い方:  python -m brc.parse_yahoo ページの文章.txt -o 試合.json --league UNIV --id 試合ID
         [--date 2026-11-19] [--tournament "明治神宮大会 大学の部"] [--round 1回戦]

入力テキストには、テキスト速報ページの文章（「テキスト速報」から「試合前情報」の先発メンバーまで）と、
一球速報ページの選手一覧（「1 二 鈴木 湧陽 …」の行とベンチ入り選手）を貼る。
各打席の「打つ前のアウト・走者」と、次の打席の「打つ前」から、打席の結果の状況を決める。
"""
import argparse
import json
import pathlib
import re

OUTS = {"無死": 0, "一死": 1, "二死": 2}
BASES_JA = {"走者なし": 0, "一塁": 1, "二塁": 2, "三塁": 4, "一二塁": 3, "一三塁": 5, "二三塁": 6, "満塁": 7}
POS_CHAR = {"投": "P", "捕": "C", "一": "1B", "二": "2B", "三": "3B", "遊": "SS",
            "左": "LF", "中": "CF", "右": "RF", "指": "DH"}
POS_WORD = {"ピッチャー": "P", "キャッチャー": "C", "ファースト": "1B", "セカンド": "2B", "サード": "3B",
            "ショート": "SS", "レフト": "LF", "センター": "CF", "ライト": "RF"}
POS_NUM = {"1": "P", "2": "C", "3": "1B", "4": "2B", "5": "3B", "6": "SS", "7": "LF", "8": "CF", "9": "RF"}


def bases_str(b):
    return "".join(str(i + 1) for i in range(3) if b & (1 << i))


def tail_bases(text):
    """文末の「一二塁」「三塁」などから走者の状況を読む（なければ None）。"""
    m = re.search(r"(満塁|一二塁|一三塁|二三塁|一塁|二塁|三塁)\s*$", text)
    return BASES_JA[m.group(1)] if m else None


def classify(t):
    if "併殺" in t or "ダブルプレー" in t or re.search(r"\d-\d-\d", t):
        return "DP"
    if "振り逃げ" in t and re.search(r"悪送球|後逸|エラー|失策|ファンブル", t):
        return "E"  # 振り逃げで、捕手の悪送球などで生きた・点が入った
    if "三振" in t or "振り逃げ" in t:
        return "K"
    if "敬遠" in t:
        return "IBB"
    if "フォアボール" in t or "四球" in t:
        return "BB"
    if "死球" in t or "デッドボール" in t:
        return "HBP"
    if "ホームラン" in t or "本塁打" in t:
        return "HR"
    if "スリーベース" in t or "三塁打" in t:
        return "3B"
    if "ツーベース" in t or "二塁打" in t:
        return "2B"
    if "ヒット" in t or "安打" in t:
        return "1B"
    if "試みるも" in t:
        return "OUT"
    if "落球" in t or "ファンブル" in t or "エラー" in t or "失策" in t or "悪送球" in t or "後逸" in t:
        return "E"
    if "犠牲フライ" in t or "犠飛" in t:
        return "SF"
    if "バント" in t and ("成功" in t or "決め" in t) and "セーフティ" not in t:
        return "SH"
    if "セーフティバント" in t:
        return "1B"
    if "野選" in t or "フィルダースチョイス" in t:
        return "FC"
    return "OUT"


def fielders_of(t):
    t = re.sub(r"\S+ \d+-\d+ \S+", "", t)
    m = re.search(r"([1-9])-([1-9])-([1-9])", t)  # 6-4-3 など（カウントや得点の「1-0」とは区別）
    if m:
        return [POS_NUM[g] for g in m.groups()]
    m = re.search(r"\((.)\)[のが]", t)
    if m and m.group(1) in POS_CHAR:
        return [POS_CHAR[m.group(1)]]
    for w, p in POS_WORD.items():
        if w in t:
            return [p]
    return []


BATTER_RE = re.compile(r"^(\d番|代打|代走) (.+?) (無死|一死|二死)(.+)$")
NOISE = ("試合終了", "リクエスト", "リプレー", "－", "治療中")


class YahooParser:
    def __init__(self, text, league="UNIV", game_id=None, date=None, tournament=None, round_=None):
        self.lines = [l.strip() for l in text.splitlines() if l.strip()]
        self.league, self.game_id, self.date = league, game_id, date
        self.tournament, self.round = tournament, round_
        self.warnings = []

    # ---- 選手 ----
    def _roster(self):
        roster = {}   # team -> {"starters": {pos: name}, "order": {name: n}, "names": [..]}
        team = None
        teams = self.teams
        for l in self.lines:
            if l in teams:
                team = l
                roster.setdefault(team, {"starters": {}, "order": {}, "names": []})
                continue
            if team is None:
                continue
            m = re.match(r"^(\d) (\S) (\S+ \S+?)(?: \d年.*)?$", l)
            if m:
                n, pos, name = m.groups()
                roster[team]["starters"][POS_CHAR.get(pos, pos)] = name
                roster[team]["order"][name] = int(n)
                roster[team]["names"].append(name)
                continue
            m = re.match(r"^(投手|捕手|内野手|外野手|控え) (\S+(?: \S+)?)(?: \d年.*)?$", l)
            if m:
                roster[team]["names"].append(m.group(2))
        return roster

    def full(self, team, short):
        names = self.roster.get(team, {}).get("names", [])
        if short in names:
            return short
        c = [n for n in names if n.replace(" ", "").startswith(short.replace(" ", ""))]
        if len(c) == 1:
            return c[0]
        return short

    # ---- 本体 ----
    def parse(self):
        L = self.lines
        # 先攻・後攻
        away = home = None
        for l in L:
            m = re.match(r"先攻:(.+?)のスターティング", l)
            if m:
                away = m.group(1)
            m = re.match(r"後攻:(.+?)のスターティング", l)
            if m:
                home = m.group(1)
        self.teams = {away, home}
        self.away, self.home = away, home
        self.roster = self._roster()
        # 先発投手
        sp = {}
        for l in L:
            m = re.match(r"先発ピッチャーは(.+?)が(.+?)、(.+?)が(.+)$", l)
            if m:
                sp[m.group(1)] = m.group(2)
                sp[m.group(3)] = m.group(4)
        lineups = {}
        for side, team in (("away", away), ("home", home)):
            st = dict(self.roster.get(team, {}).get("starters", {}))
            if team in sp:
                st["P"] = self.full(team, sp[team])
            lineups[side] = st

        # 半イニングごとのブロック（ページは新しい順）
        start = L.index("テキスト速報") + 1 if "テキスト速報" in L else 0
        first = next((i for i in range(start, len(L)) if re.match(r"^\d+回(表|裏)$", L[i])), start)
        end = next((i for i in range(first, len(L)) if L[i] in ("試合前情報", "提供", "選手一覧")), len(L))
        halves, cur = [], None
        i = start
        while i < end:
            l = L[i]
            m = re.match(r"^(\d+)回(表|裏)$", l)
            if m:
                cur = {"inn": int(m.group(1)), "half": "top" if m.group(2) == "表" else "bottom", "entries": []}
                halves.append(cur)
            elif re.match(r"^\d+：$", l) and cur is not None:
                cur["entries"].append({"lines": []})
            elif l.startswith("得点 ") or l.endswith("の攻撃"):
                pass
            elif cur is not None and cur["entries"]:
                cur["entries"][-1]["lines"].append(l)
            i += 1
        # ページが新しい順なら古い順に並べ直す（試合終了後のページは古い順）
        if len(halves) > 1 and (halves[0]["inn"], halves[0]["half"] == "bottom") > (halves[-1]["inn"], halves[-1]["half"] == "bottom"):
            halves.reverse()
            for h in halves:
                h["entries"].reverse()
        for h in halves:
            for e in h["entries"]:
                ls = []
                for x in e["lines"]:
                    ls += [y for y in re.split(r"\s+(?=投手交代|守備交代|守備変更|[一二三]塁走者[^\s:：]+?→)", x) if y]
                ls = [x for x in ls if not any(x.startswith(n) or n in x for n in NOISE)]
                merged = []
                for x in ls:  # 「九州共立大先制！ 日体大 0-1 九共大 …」は前の行（打席の結果）の続き
                    if merged and (re.match(r"^[^\s\d、。！!]{1,10}(先制|同点|勝ち越し|逆転|サヨナラ)[！!]", x)
                                   or (x is ls[-1] and re.match(r"^\S+\(.\)[:：](悪送球|ファンブル|失策|エラー|落球|後逸|捕球ミス|暴投|ワイルドピッチ|パスボール|捕逸)", x))):
                        merged[-1] = merged[-1] + " " + x
                    else:
                        merged.append(x)
                e["lines"] = merged

        events = []
        score = {"away": 0, "home": 0}
        orders = {}
        for h in halves:
            off = "away" if h["half"] == "top" else "home"
            deff = "home" if off == "away" else "away"
            ents = [e for e in h["entries"] if e["lines"]]
            for k, e in enumerate(ents):
                bl = e["lines"][0]
                m = BATTER_RE.match(bl)
                if not m:
                    self.warnings.append(f"打者の行を読めません: {bl}")
                    continue
                order, bname, o, b = m.groups()
                bteam = self.away if off == "away" else self.home
                bname = self.full(bteam, bname)
                if order.endswith("番"):
                    orders.setdefault(bname, int(order[:-1]))
                else:  # 代打: 「村松→代打:原」から、代わった選手の打順を引き継ぐ
                    for sl in e["lines"][1:]:
                        mm = re.match(r"(?:[一二三]塁走者)?(.+?)→(代打|代走)[:：](.+)$", sl)
                        if mm:
                            old = self.full(bteam, mm.group(1).strip())
                            if old in orders:
                                orders.setdefault(bname, orders[old])
                outs, bases = OUTS[o], BASES_JA.get(b, 0)
                body = e["lines"][1:]
                if not body:
                    continue
                # 打席が終わらずに攻撃が終わった（盗塁死・牽制死で3アウトなど）
                runner_end = bool(re.match(r"^[一二三]塁走者[^、。\s]+?[:：]", body[-1]))
                # 打席の途中の出来事
                for sl in (body if runner_end else body[:-1]):
                    mm = re.match(r"投手交代[:：](.+?)→(.+)$", sl)
                    if mm:
                        team = self.home if off == "away" else self.away
                        events.append({"sub": {"team": deff, "pos": "P", "player": self.full(team, mm.group(2).strip())}})
                        continue
                    mm = re.match(r"守備変更[:：](.+?)→(.+)$", sl)
                    if mm:
                        team = self.home if off == "away" else self.away
                        pos = POS_WORD.get(mm.group(2).strip())
                        who_ = mm.group(1).strip()
                        for w in POS_WORD:
                            if who_.endswith(w) and len(who_) > len(w):
                                who_ = who_[:-len(w)]
                        mm = re.match(r"(.+?)→(.+)$", who_ + "→" + mm.group(2))
                        if pos:
                            events.append({"sub": {"team": deff, "pos": pos, "player": self.full(team, mm.group(1).strip())}})
                        continue
                    mm = re.match(r"(?:[一二三]塁走者)?(.+?)→(代打|代走)[:：](.+)$", sl)
                    if mm:
                        team = self.away if off == "away" else self.home
                        events.append({"sub": {"team": off, "player": self.full(team, mm.group(3).strip()),
                                               "role": "PR" if mm.group(2) == "代走" else "PH"}})
                        continue
                    mm = re.match(r"守備交代[:：](.+)$", sl)
                    if mm:
                        team = self.home if off == "away" else self.away
                        for part in re.split(r"[、/／\s]+", mm.group(1)):
                            for w, pos in POS_WORD.items():
                                if part.startswith(w):
                                    events.append({"sub": {"team": deff, "pos": pos,
                                                           "player": self.full(team, part[len(w):].strip())}})
                        continue
                    mm = re.match(r"(代打|代走|守備交代)[:：](.+?)→(.+)$", sl)
                    if mm:
                        team = self.away if off == "away" else self.home
                        side = off if mm.group(1) != "守備交代" else deff
                        events.append({"sub": {"team": side, "player": self.full(team, mm.group(3).strip()),
                                               "role": "PR" if mm.group(1) == "代走" else "PH"}})
                        continue
                    t = None
                    if "暴投" in sl or "ワイルドピッチ" in sl:
                        t = "WP"
                    elif "パスボール" in sl or "捕逸" in sl:
                        t = "PB"
                    elif "ボーク" in sl:
                        t = "BK"
                    elif ("盗塁" in sl or "スチール" in sl) and ("失敗" in sl or "アウト" in sl):
                        t = "CS"
                    elif "盗塁" in sl or "スチール" in sl:
                        t = "SB"
                    elif "けん制" in sl and "アウト" in sl:
                        t = "PO"
                    if not t and re.search(r"\S+ \d+-\d+ \S+", sl):
                        # 走者が悪送球などで進んで点が入った（例：一塁走者内山はさらに三塁まで進塁 神医大 0-3 仙台大）
                        prev = " ".join(body[:body.index(sl)])
                        me = re.search(r"\((.)\)[:：]?(悪送球|ファンブル|落球|捕球ミス|失策)", prev + " " + sl)
                        t = "E" if me else "OTHER"
                        err_pos = POS_CHAR.get(me.group(1)) if me else None
                    else:
                        err_pos = None
                    if not t:
                        continue  # けん制（帰塁）・治療中など
                    nb = tail_bases(sl)
                    new_outs = outs + (1 if t in ("CS", "PO") else 0)
                    rteam = self.away if off == "away" else self.home
                    rs = re.findall(r"([一二三])塁走者(.+?)(?:、|の|[:：])", sl)
                    if t in ("SB", "CS") and len(rs) == 2 and t == "SB" and nb is not None:
                        # ダブルスチール: 前の走者から順に1人ずつ
                        rs.sort(key=lambda x: "一二三".index(x[0]), reverse=True)
                        mid = bases
                        for base, nm in rs:
                            bit = 1 << "一二三".index(base)
                            mid = (mid & ~bit) | (bit << 1)
                            events.append({"type": "SB", "inn": h["inn"], "half": h["half"], "outs": outs,
                                           "bases": bases_str(mid & 7), "runs": 0,
                                           "runner": self.full(rteam, nm.strip())})
                        bases = nb
                        continue
                    runs = self._runs(sl, score, off)
                    ev = {"type": t, "inn": h["inn"], "half": h["half"], "outs": min(new_outs, 3),
                          "bases": bases_str(nb if nb is not None else bases), "runs": runs}
                    if rs and t in ("SB", "CS"):
                        ev["runner"] = self.full(rteam, rs[0][1].strip())
                    if t == "E" and err_pos:
                        ev["error_by"] = err_pos
                    events.append(ev)
                    outs, bases = new_outs, (nb if nb is not None else bases)
                if runner_end:
                    pa_count_skip = True
                    continue
                # 打席の結果
                rl = body[-1]
                t = classify(rl)
                runs = self._runs(rl, score, off)
                if k + 1 < len(ents):
                    nm = BATTER_RE.match(ents[k + 1]["lines"][0])
                    a_outs, a_bases = OUTS[nm.group(3)], BASES_JA.get(nm.group(4), 0)
                else:
                    a_outs = 3
                    a_bases = tail_bases(rl) or 0
                    if "アウト" not in rl and "3アウト" not in rl:
                        a_outs = outs  # サヨナラなど、アウトで終わらない最後の打席
                ev = {"batter": bname, "type": t, "result_text": rl, "inn": h["inn"], "half": h["half"],
                      "outs": a_outs, "bases": bases_str(a_bases), "runs": runs}
                f = fielders_of(rl)
                if f and t not in ("K", "BB", "IBB", "HBP"):
                    ev["fielders"] = f
                me_ = re.search(r"\((.)\)[:：]?(悪送球|後逸|ファンブル|落球|失策)", rl)
                if t == "E" and "振り逃げ" in rl:
                    ev["no_batter_credit"] = True  # 打者は三振。生きたのは捕手の失策なので打者の手柄にしない
                if t == "E" and me_ and me_.group(1) in POS_CHAR:
                    ev["error_by"] = POS_CHAR[me_.group(1)]
                    ev["fielders"] = [POS_CHAR[me_.group(1)]]
                elif t == "E" and f:
                    ev["error_by"] = f[0]
                events.append(ev)

        # 最終スコア（試合が終わっていれば）
        final = self._linescore()
        data = {
            "game": {"id": self.game_id or "game", "date": self.date, "tournament": self.tournament or "",
                     "round": self.round or "", "league": self.league, "away": away, "home": home},
            "lineups": lineups,
            "events": events,
            "players": {n: {"order": o, "number": None} for n, o in orders.items()},
        }
        if final:
            he = final.pop("he", None)
            data["final"] = final
            if he:
                data["game"]["hits_errors"] = he
        if (score["away"], score["home"]) != ((final or {}).get("away", score["away"]), (final or {}).get("home", score["home"])):
            self.warnings.append(f"速報の得点 {score} がスコアボードと一致しません: {final}")
        return data

    def _runs(self, text, score, off):
        m = re.search(r"(\S+) (\d+)-(\d+) (\S+)", text)
        if not m:
            return 0
        a_name, a, b, b_name = m.groups()
        new = dict(score)
        def match(name, team):
            if name == team:
                return True
            it = iter(team)  # 「環太大」→「環太平洋大」のような略称（文字が順に含まれる）
            return len(name) >= 2 and all(c in it for c in name)  # 「育英」→「仙台育英」も
        for name, val in ((a_name, int(a)), (b_name, int(b))):
            if match(name, self.away):
                new["away"] = val
            elif match(name, self.home):
                new["home"] = val
        runs = new[off] - score[off]
        score.update(new)
        return max(runs, 0)

    def _linescore(self):
        L = self.lines
        try:
            i = next(i for i, l in enumerate(L) if re.match(r"^1 2 3 [\d ]*計", l))
        except StopIteration:
            return None
        out, j = {}, i + 1
        for side in ("away", "home"):
            # 1行形式「チーム名 0 0 3 … 7 11 4」
            if j < len(L) and re.match(r"^\S+( [\dXx\-]+){4,}$", L[j]) and not re.match(r"^[\dXx\-]", L[j]):
                parts = L[j].split()
                out[side] = int(parts[-3])
                out.setdefault("he", {})[side] = [int(parts[-2]), int(parts[-1])]
                j += 1
                continue
            j += 1  # チーム名
            while j < len(L) and not re.match(r"^\d+ \d+ \d+$", L[j]):
                j += 1
            if j >= len(L):
                return None
            parts = L[j].split()
            out[side] = int(parts[0])
            out.setdefault("he", {})[side] = [int(parts[1]), int(parts[2])]  # 公式の安打・失策
            j += 1
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--league", default="UNIV")
    ap.add_argument("--id")
    ap.add_argument("--date")
    ap.add_argument("--tournament")
    ap.add_argument("--round")
    a = ap.parse_args()
    p = YahooParser(pathlib.Path(a.text).read_text(encoding="utf-8"), a.league, a.id, a.date, a.tournament, a.round)
    data = p.parse()
    pathlib.Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len([e for e in data['events'] if 'sub' not in e])} プレーを変換しました → {a.out}")
    for w in p.warnings:
        print("注意:", w)


if __name__ == "__main__":
    main()
