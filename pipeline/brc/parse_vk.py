"""バーチャル高校野球の試合ページ（打席結果・打撃成績）の文章を、採点エンジンの入力JSONに変換する。

使い方:  python -m brc.parse_vk ページの文章.txt -o 試合.json [--league HS|UNIV] [--id 試合ID]

ページの文章（打撃成績と打席結果の部分）をそのまま貼ったテキストを読む。
ファインプレー・好走塁・打球の難しさ・普通を超えた進塁は文章から判断できないので、
必要なら出力JSONに手で書き足す（README参照）。
"""
import argparse
import json
import pathlib
import re

BASE_NUM = {"一": 1, "二": 2, "三": 3, "本": 4}
POS_CHAR = {"投": "P", "捕": "C", "一": "1B", "二": "2B", "三": "3B", "遊": "SS",
            "左": "LF", "中": "CF", "右": "RF", "指": "DH"}
POS_WORD = {"ピッチャー": "P", "キャッチャー": "C", "ファースト": "1B", "セカンド": "2B",
            "サード": "3B", "ショート": "SS", "レフト": "LF", "センター": "CF", "ライト": "RF"}
NAME_RE = r"([^、。｜\s][^、。｜]*?\s?[^、。｜\s]*?)[①-⑳㉑-㉟]"


def clean_name(s):
    s = re.sub(r"[①-⑳㉑-㉟]", "", s).strip()
    return s


def find_fielder(result):
    r = result.replace("バント", "")
    for w, p in POS_WORD.items():
        if r.startswith(w):
            return p
    if r and r[0] in POS_CHAR and r[0] != "指":
        return POS_CHAR[r[0]]
    return None


def classify(result):
    if "併殺" in result:
        return "DP"
    if "三振" in result or "振り逃げ" in result:
        return "K"
    if "敬遠" in result:
        return "IBB"
    if "フォアボール" in result or "四球" in result:
        return "BB"
    if "デッドボール" in result or "死球" in result:
        return "HBP"
    if "ホームラン" in result or "本塁打" in result:
        return "HR"
    if "スリーベース" in result or "三塁打" in result:
        return "3B"
    if "ツーベース" in result or "二塁打" in result:
        return "2B"
    if "ヒット" in result or "安打" in result or "適時打" in result:
        return "1B"
    if "失策" in result:
        return "E"
    if "犠飛" in result:
        return "SF"
    if "犠打" in result:
        return "SH"
    if "セーフ" in result or "野選" in result:
        return "FC"
    return "OUT"


def dest_of(text):
    if "本塁生還" in text:
        return 4
    if "アウト" in text:
        return 0
    m = re.search(r"([一二三])塁進塁", text)
    return BASE_NUM[m.group(1)] if m else None


class Parser:
    def __init__(self, text, league="HS", game_id=None, date=None, tournament=None):
        self.text = text
        self.date = date
        self.tournament = tournament
        self.league = league
        self.game_id = game_id
        self.warnings = []

    def parse(self):
        lines = [l.strip() for l in self.text.splitlines() if l.strip()]
        header = self._header(lines)
        if self.date:
            header["date"] = self.date
        if self.tournament:
            header["tournament"] = self.tournament
        box = self._box(lines) if "打撃成績" in lines else self._lineup(lines, header)
        plays_start = next(i for i, l in enumerate(lines) if "回表開始" in l)
        play_lines = lines[plays_start:]
        full_names = {n for side in box.values() for _, _, n in side if " " in n}
        self.numbers = {}
        circ = {chr(0x2460 + i): i + 1 for i in range(20)}
        circ.update({chr(0x3251 + i): i + 21 for i in range(15)})
        for l in lines[plays_start:]:
            for m in re.finditer(r"([^\s、。｜・]+ [^\s、。｜・]+?)([①-⑳㉑-㉟])", l):
                self.numbers.setdefault(m.group(1), circ[m.group(2)])
        self.orders = {}
        for l in play_lines:
            for m in re.finditer(r"([^\s、。｜・]+ [^\s、。｜・]+?)[①-⑳㉑-㉟]", l):
                full_names.add(m.group(1))
        self.full = full_names

        lineups, slots = {}, {}
        for side in ("away", "home"):
            lineups[side] = {}
            slots[side] = {}
            slot = -1
            for pos_mark, starter, bname in box[side]:
                full = self._full(bname) if " " not in bname else bname
                if starter:
                    slot += 1
                    lineups[side][POS_CHAR.get(pos_mark, pos_mark)] = full
                slots[side][full] = slot

        events, warnings = self._plays(play_lines, lineups, slots)
        data = {
            "game": dict(header, league=self.league, id=self.game_id or header.get("id", "game")),
            "lineups": lineups,
            "events": events,
            "final": header.pop("_final"),
            "players": {n: {"order": self.orders.get(n), "number": self.numbers.get(n)}
                        for n in set(self.orders) | set(self.numbers)},
        }
        data["game"].pop("_final", None)
        self.warnings += warnings
        return data

    def _full(self, short):
        cands = [f for f in self.full if f.replace(" ", "").startswith(short)]
        if len(cands) == 1:
            return cands[0]
        if len(cands) > 1:
            self.warnings.append(f"「{short}」に当たる選手が複数います: {cands}")
            return sorted(cands)[0]
        return short

    def _header(self, lines):
        h = {}
        for i, l in enumerate(lines):
            m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(.*)", l)
            if m and "date" not in h:
                h["date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                h["venue"] = m.group(4)
                if i >= 1:
                    t = re.match(r"(.+?)（(.+?)）", lines[i - 1])
                    if t:
                        h["tournament"], h["round"] = t.group(1), t.group(2)
            t2 = re.match(r"^(.+?) - (.+?)（(.+?)）$", l)
            if t2 and "round" not in h:
                h["round"] = t2.group(3).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
            if l.startswith("学校名"):
                a = lines[i + 1].split()
                b = lines[i + 2].split()
                h["away"], h["home"] = a[0], b[0]
                h["_final"] = {"away": int(a[-1]), "home": int(b[-1])}
                h["linescore"] = {"away": a[1:-1], "home": b[1:-1]}
        return h

    def _box(self, lines):
        out = {"away": [], "home": []}
        side = None
        in_bat = False
        for l in lines:
            if l == "打撃成績":
                in_bat = True
                continue
            if l == "投手成績":
                break
            if not in_bat:
                continue
            if side is None and not l.startswith("守備"):
                side = "away"
                continue
            if l.startswith("チーム合計"):
                side = "home" if side == "away" else "done"
                continue
            if side == "home" and not out["home"] and not l.startswith(("守備", "[")) and not re.match(r"^\S+ \S+ \d", l):
                continue  # チーム名の行
            m = re.match(r"^\[(.)\]\s*(\S+)", l)
            if m and side in out:
                out[side].append((m.group(1), True, m.group(2)))
                continue
            m = re.match(r"^(\S+)\s+(\S+)\s+\d", l) or re.match(r"^(\S+)\s+(\S+)$", l)
            if m and side in out and not l.startswith("守備"):
                out[side].append((m.group(1)[-1], False, m.group(2)))
        return out

    def _lineup(self, lines, header):
        """神宮大会の打席速報ページ：「打順 守備 選手名 背番号」の表から先発を読む。"""
        out = {"away": [], "home": []}
        side = None
        for i, l in enumerate(lines):
            if l.startswith("打順 守備 選手名"):
                team = lines[i - 1]
                side = "away" if team == header.get("away") else ("home" if team == header.get("home") else None)
                if side is None:
                    self.warnings.append(f"打順表のチーム名「{team}」がスコアと一致しません")
                continue
            if "回表開始" in l or l == "打席速報":
                side = None
            if side is None:
                continue
            m = re.match(r"^(\d+|-)\s+(\S)\s+(.+?)\s*[①-⑳㉑-㉟]$", l)
            if m:
                order, pos, name = m.groups()
                if order != "-" or pos == "投":
                    out[side].append((pos, True, name))
                else:
                    out[side].append(("-", False, name))
        # 控え（-）は先発ではないので lineups には入れないが、名前の照合には使う
        return {k: [x for x in v] for k, v in out.items()}

    def _plays(self, lines, lineups, slots):
        events, warnings = [], []
        inn, half = 1, "top"
        bases = {}  # 塁番号 -> 走者名
        outs = 0
        def_side = lambda: "home" if half == "top" else "away"
        off_side = lambda: "away" if half == "top" else "home"
        current_p = {"home": lineups["home"].get("P"), "away": lineups["away"].get("P")}
        pa_count = {"home": 0, "away": 0}

        for l in lines:
            m = re.match(r"(\d+)回(表|裏)開始｜投手、(.+?)。", l)
            if m:
                inn, half = int(m.group(1)), "top" if m.group(2) == "表" else "bottom"
                bases, outs = {}, 0
                if self.league in ("HS", "UNIV", "MLB", "INTL") and inn >= 10:
                    self.warnings.append(f"{inn}回はタイブレーク：開始時の走者（一・二塁）を確認してください")
                p = clean_name(m.group(3))
                if p != current_p[def_side()]:
                    events.append({"sub": {"team": def_side(), "pos": "P", "player": p}})
                    current_p[def_side()] = p
                continue
            if re.match(r"\d+回(表|裏)終了", l) or l == "試合終了":
                continue
            m = re.match(r"(投手交代|守備交代)｜(.+)$", l)
            if m:
                for part in m.group(2).split("、"):
                    mm = re.match(r"(.+?)に(.+)$", part)
                    if not mm:
                        continue
                    pos = POS_WORD.get(mm.group(1), mm.group(1))
                    p = clean_name(mm.group(2))
                    events.append({"sub": {"team": def_side(), "pos": pos, "player": p}})
                    if pos == "P":
                        current_p[def_side()] = p
                continue
            m = re.match(r"(代走|代打|代打者)｜(.+)$", l)
            if m:
                p = clean_name(m.group(2))
                if m.group(1) == "代走":
                    team = off_side()
                    slot = slots[team].get(p)
                    replaced = [b for b, n in bases.items() if slots[team].get(n) == slot]
                    if replaced:
                        bases[replaced[0]] = p
                    else:
                        warnings.append(f"{inn}回：代走 {p} が誰と代わったか特定できません")
                events.append({"sub": {"team": off_side(), "player": p, "role": "PR" if m.group(1) == "代走" else "PH"}})
                continue

            parts = l.rstrip("。").split("。")
            first = parts[0]
            runner_clauses = parts[1:]
            ev = None
            if first.startswith(("牽制死", "盗塁", "重盗", "暴投", "捕逸", "ボーク")):
                kind = "ボーク" if first.startswith("ボーク") else first[:2]
                t = {"牽制": "PO", "盗塁": "SB", "重盗": "SB", "暴投": "WP", "捕逸": "PB", "ボーク": "BK"}.get(kind, "OTHER")
                if first.startswith(("盗塁死", "盗塁失敗")):
                    t = "CS"
                ev = {"type": t}
                moved = self._apply_runners(runner_clauses, bases)
                outs += moved["outs"]
                runs = moved["runs"]
                if moved["names"]:
                    ev["runner"] = moved["names"][0]
            else:
                segs = first.split("、")
                if len(segs) < 2:
                    if "。" in l or len(l) > 12:
                        warnings.append(f"読めない行: {l}")
                    continue
                batter = clean_name(segs[0])
                result = segs[1]
                self.orders.setdefault(batter, pa_count[off_side()] % 9 + 1)
                pa_count[off_side()] += 1
                bdest_text = "、".join(segs[2:])
                t = classify(result)
                ev = {"batter": batter, "type": t, "result_text": result}
                f = find_fielder(result)
                if f and t not in ("K", "BB", "IBB", "HBP"):
                    ev["fielders"] = [f]
                if t == "E" and f:
                    ev["error_by"] = f
                if t == "DP":
                    ev["fielders"] = [f] if f else []
                explicit = [c for c in runner_clauses if "走者・" in c]
                later = [c for c in runner_clauses if "走者・" not in c]
                moved = self._apply_runners(explicit, bases)
                runs = moved["runs"]
                outs += moved["outs"]
                d = 4 if t == "HR" else dest_of(bdest_text)
                if d is None:
                    d = {"1B": 1, "2B": 2, "3B": 3, "BB": 1, "IBB": 1, "HBP": 1, "E": 1, "FC": 1}.get(t, 0)
                if d == 0:
                    outs += 1
                elif d == 4:
                    runs += 1
                else:
                    bases[d] = batter
                if later:
                    m2 = self._apply_runners(later, bases)
                    runs += m2["runs"]
                    outs += m2["outs"]
            ev.update(inn=inn, half=half, outs=min(outs, 3),
                      bases="".join(str(b) for b in sorted(bases) if b < 4), runs=runs)
            events.append(ev)
        return events, warnings

    def _apply_runners(self, clauses, bases):
        """走者の記述を順に反映する。「一塁走者・名前、二塁進塁」も「名前、二塁進塁」も読む。"""
        res = {"runs": 0, "outs": 0, "names": []}
        for c in clauses:
            if "、" not in c and re.match(r"^(封殺|盗塁刺|.?失策|タッチアウト)", c):
                continue  # 補足の記述（走者の動きは次の文に書かれる）
            m = re.match(r"([一二三])塁走者・(.+?)、(.+)$", c)
            if m:
                frm, name, dest = BASE_NUM[m.group(1)], clean_name(m.group(2)), dest_of(m.group(3))
                if bases.get(frm) not in (None, name):
                    self.warnings.append(f"{frm}塁の走者が記録と食い違います（{bases.get(frm)} / {name}）")
            else:
                m = re.match(r"(.+?)、(.+)$", c)
                if not m:
                    if c:
                        self.warnings.append(f"走者の記述を読めません: {c}")
                    continue
                name, dest = clean_name(m.group(1)), dest_of(m.group(2))
                frm = next((b for b, n in bases.items() if n == name), None)
                if frm is None:
                    self.warnings.append(f"塁上にいない走者の記述: {c}")
            if frm is not None:
                bases.pop(frm, None)
            res["names"].append(name)
            if dest == 4:
                res["runs"] += 1
            elif dest == 0 or dest is None:
                res["outs"] += 1
            else:
                bases[dest] = name
        return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--league", default="HS")
    ap.add_argument("--id")
    ap.add_argument("--date", help="試合日（ページに日付がないとき）例 2026-11-19")
    ap.add_argument("--tournament", help="大会名 例 明治神宮大会 高校の部")
    a = ap.parse_args()
    p = Parser(pathlib.Path(a.text).read_text(encoding="utf-8"), a.league, a.id, a.date, a.tournament)
    data = p.parse()
    pathlib.Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len([e for e in data['events'] if 'sub' not in e])} プレーを変換しました → {a.out}")
    for w in p.warnings:
        print("注意:", w)


if __name__ == "__main__":
    main()
