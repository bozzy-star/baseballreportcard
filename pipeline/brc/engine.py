"""ベースボール通信簿 採点エンジン。

試合のプレー記録（JSON）を読み、プレーごとの勝利確率の動き（WPA）を
決めたルールで選手に配分し、10点満点の採点・MVP・敢闘賞・担任からの一言を出す。
"""
import math
from collections import defaultdict
from .winprob import WinProbModel, bases_from_str

BANDS_WIN = ("試合を決めた", "勝利に貢献した", "役目を果たした", "あと一歩でした", "今日は試練の日")
BANDS_LOSE = ("たいへんよくできました", "よくできました", "できました", "あと一歩", "今日は試練の日")
BAND_OPENERS = tuple(w + "。" for w in BANDS_WIN + BANDS_LOSE) + ("文句なしの花丸です。", "及第点です。", "もう少し。")

POSITIONS = ["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
POS_JA = {"P": "投", "C": "捕", "1B": "一", "2B": "二", "3B": "三", "SS": "遊",
          "LF": "左", "CF": "中", "RF": "右", "DH": "指"}

# ---- 採点ルール（ぼじぃさん決定分）----
RULES = {
    "coef": 12.0,           # 換算係数：採点 = 6.0 + 係数 × WPA（NPB基準モデル完成後に見直し）
    "base": 6.0,            # 及第点
    "cap": 10.0,            # 上限（下限なし）
    "step": 0.5,            # 0.5点刻み
    "fine_play_bonus": 0.5,
    "good_running_bonus": 0.5,
    "mvp_min": 7.0,         # 投手MVP・野手MVPの基準
    "fighting_min": 8.0,    # 敢闘賞の基準（負けチーム）
    # 守備側の配分
    "battery_events": {"P": 0.75, "C": 0.25},              # 三振・四球・死球・本塁打
    "hit": {"P": 0.65, "C": 0.25, "F": 0.10},               # 被安打
    "out": {"normal": 0.30, "hard": 0.55, "very_hard": 0.80},  # 打球アウトの野手取り分（残りは投手）
    "sb_defense": {"P": 0.5, "C": 0.5},                     # 盗塁を許したとき
    "out_catcher": 0.0,     # 打球アウトで、投手の取り分のうち捕手に回す割合（案：0.25）
}

BATTERY_TYPES = {"K", "BB", "IBB", "HBP", "HR"}
HIT_TYPES = {"1B", "2B", "3B"}
OUT_TYPES = {"OUT", "SF", "SH", "FC"}
LABELS = {"K": "三振", "BB": "四球", "IBB": "敬遠", "HBP": "死球", "HR": "ホームラン",
          "1B": "ヒット", "2B": "二塁打", "3B": "三塁打", "OUT": "凡退", "SF": "犠牲フライ",
          "SH": "犠打", "FC": "内野ゴロ", "DP": "併殺打", "E": "相手失策での出塁", "SB": "盗塁", "CS": "盗塁死",
          "PO": "牽制死", "RO": "走塁死", "WP": "暴投", "PB": "捕逸", "BK": "ボーク", "OTHER": "プレー"}


def round_step(x, step=0.5):
    return math.floor(x / step + 0.5 + 1e-9) * step  # 四捨五入（0.25は切り上げ）


class Game:
    def __init__(self, data, rules=None):
        self.data = data
        self.rules = dict(RULES, **(rules or {}))
        g = data["game"]
        self.info = g
        self.home, self.away = g["home"], g["away"]
        tb = g.get("tiebreak_from", "default")
        self.model = WinProbModel(g.get("league", "NPB"), tiebreak_from=tb)
        if "coef" in g:
            self.rules["coef"] = g["coef"]
        # 守備位置（試合途中の交代は events の sub で更新）
        self.defense = {t: dict(data["lineups"][t]) for t in ("home", "away")}
        self.players = {}       # name -> {"team","roles"}
        for t in ("home", "away"):
            for pos, name in data["lineups"][t].items():
                self._register(name, t, pos)
        self.wpa = defaultdict(float)
        self.bonus = defaultdict(float)
        self.plays = defaultdict(list)  # name -> [(wpa, desc)]
        self.log = []
        self.warnings = []
        self.bat = defaultdict(lambda: defaultdict(int))
        self.pit = defaultdict(lambda: defaultdict(int))

    def _register(self, name, team, role):
        if not name:  # 名前のわからない走者（牽制死など）は登録しない
            return
        p = self.players.setdefault(name, {"team": team, "roles": []})
        if role not in p["roles"]:
            p["roles"].append(role)

    def _credit(self, name, value, desc):
        if not name or abs(value) < 1e-9:
            return
        self.wpa[name] += value
        self.plays[name].append((value, desc))

    def _who(self, team, pos):
        """守備位置 → 選手名（名前がそのまま来た場合はそのまま）。"""
        return self.defense[team].get(pos, pos)

    # ---- メイン ----
    def run(self):
        state = {"inning": 1, "half": "top", "outs": 0, "bases": 0, "home": 0, "away": 0}
        final = self.data.get("final")
        events = self.data["events"]
        for idx, ev in enumerate(events):
            if "sub" in ev:
                s = ev["sub"]
                team = s["team"]
                if s.get("pos"):
                    self.defense[team][s["pos"]] = s["player"]
                self._register(s["player"], team, s.get("pos") or s.get("role", "PH"))
                continue

            # イニングが変わっていたら、その半イニングの頭から
            inn, half = ev["inn"], ev["half"]
            if (inn, half) != (state["inning"], state["half"]):
                exp = self._next_half(state["inning"], state["half"])
                if (inn, half) != exp:
                    self.warnings.append(f"{state['inning']}回{self._half_ja(state['half'])}の次が"
                                         f"{inn}回{self._half_ja(half)}になっています（記録の抜けの可能性）")
                elif state["outs"] < 3:
                    self.warnings.append(f"{state['inning']}回{self._half_ja(state['half'])}が"
                                         f"{state['outs']}アウトのまま終わっています")
                state.update(inning=inn, half=half, outs=0, bases=0)
                if self.model.tiebreak_from and inn >= self.model.tiebreak_from:
                    state["bases"] = 3

            before = dict(state)
            wp_before = self._wp(before)

            off_team = "away" if half == "top" else "home"
            def_team = "home" if half == "top" else "away"
            after = dict(before)
            after["outs"] = ev.get("outs", before["outs"])
            after["bases"] = bases_from_str(ev["bases"]) if "bases" in ev else before["bases"]
            after[off_team] += ev.get("runs", 0)
            game_over = bool(ev.get("game_over")) or (idx == len(events) - 1 and final is not None)
            wp_after = self._wp(after, game_over=game_over)

            sign = 1 if off_team == "home" else -1
            delta_off = sign * (wp_after - wp_before)  # 攻撃側から見た勝率の増減
            self._game_over = game_over
            self._allocate(ev, delta_off, off_team, def_team, before, after)
            self._stats(ev, def_team, before, after, off_team)
            self.log.append({
                "inn": inn, "half": half, "type": ev.get("type"), "batter": ev.get("batter"),
                "runner": ev.get("runner"), "home_wp_before": round(wp_before, 4),
                "home_wp_after": round(wp_after, 4), "offense_delta": round(delta_off, 4),
                "score": f"{after['away']}-{after['home']}", "note": ev.get("note", ""),
                "error_by": ev.get("error_by"), "no_batter_credit": bool(ev.get("no_batter_credit")),
            })
            state = after

        if final:
            if (state["away"], state["home"]) != (final["away"], final["home"]):
                self.warnings.append(f"記録上の得点 {state['away']}-{state['home']} が最終スコア "
                                     f"{final['away']}-{final['home']} と一致しません")
        self.final_state = state
        return self.report()

    @staticmethod
    def _half_ja(h):
        return "表" if h == "top" else "裏"

    @staticmethod
    def _next_half(inning, half):
        return (inning, "bottom") if half == "top" else (inning + 1, "top")

    def _wp(self, s, game_over=False):
        return self.model.home_wp(s["inning"], s["half"], s["outs"], s["bases"],
                                  s["home"], s["away"], game_over=game_over)

    # ---- 配分ルール ----
    def _allocate(self, ev, d, off, deff, before, after):
        t = ev.get("type", "OTHER")
        inn_label = f"{ev['inn']}回{self._half_ja(ev['half'])}"
        label = ev.get("label") or self._label(t, ev, off, deff, before, after)
        desc = f"{inn_label}の{label}"
        batter = ev.get("batter")
        P = self._who(deff, ev.get("pitcher", "P"))
        C = self._who(deff, ev.get("catcher", "C"))
        fielders = [self._who(deff, f) for f in ev.get("fielders", [])]
        if batter:
            self._register(batter, off, "BAT")
        for name in (P, C, *fielders):
            self._register(name, deff, "DEF")

        # --- 攻撃側 ---
        off_share = d
        extra = ev.get("extra_advance")
        if extra:  # 普通を超えた進塁分は走者の手柄
            normal = dict(after)
            normal["bases"] = bases_from_str(extra.get("normal_bases", ""))
            normal[off] = before[off] + extra.get("normal_runs", ev.get("runs", 0))
            normal["outs"] = extra.get("normal_outs", after["outs"])
            sign = 1 if off == "home" else -1
            runner_part = sign * (self._wp(after) - self._wp(normal))
            self._register(extra["runner"], off, "RUN")
            self._credit(extra["runner"], runner_part, f"{inn_label}の好走塁（進塁）")
            off_share = d - runner_part

        if t in ("SB", "CS", "PO", "RO"):
            runner = ev.get("runner")
            self._register(runner, off, "RUN")
            self._credit(runner, d, f"{inn_label}の{label}")
        elif t in ("WP", "PB", "BK"):
            if ev.get("runner"):
                self._credit(ev["runner"], d, desc)
        elif batter and not ev.get("no_batter_credit"):
            self._credit(batter, off_share, desc)

        if ev.get("good_running"):
            self._register(ev["good_running"], off, "RUN")
            self.bonus[ev["good_running"]] += self.rules["good_running_bonus"]
            self.plays[ev["good_running"]].append((0.0, f"{inn_label}の好走塁"))

        # --- 守備側（攻撃側の増減の裏返し）---
        dd = -d
        err = ev.get("error_by")
        if t == "E" or err:
            name = self._who(deff, err or (ev.get("fielders") or ["P"])[0])
            self._credit(name, dd, f"{inn_label}の失策")
        elif t in BATTERY_TYPES:
            r = self.rules["battery_events"]
            ddesc = inn_label + {"K": "に奪った三振", "BB": "の与四球", "IBB": "の敬遠",
                                 "HBP": "の与死球", "HR": "の被本塁打"}[t]
            self._credit(P, dd * r["P"], ddesc)
            self._credit(C, dd * r["C"], ddesc)
        elif t in HIT_TYPES:
            r = self.rules["hit"]
            hl = LABELS[t]
            self._credit(P, dd * r["P"], f"{inn_label}の被{hl}")
            self._credit(C, dd * r["C"], f"{inn_label}の被{hl}")
            if fielders:
                for f in fielders:
                    self._credit(f, dd * r["F"] / len(fielders), f"{inn_label}の被{hl}")
            else:
                self._credit(P, dd * r["F"], f"{inn_label}の被{hl}")
        elif t in OUT_TYPES:
            share = self.rules["out"][ev.get("difficulty", "normal")]
            if not fielders:
                share = 0.0
            oc = self.rules["out_catcher"]
            self._credit(P, dd * (1 - share) * (1 - oc), f"{inn_label}に打ち取った場面")
            self._credit(C, dd * (1 - share) * oc, f"{inn_label}に打ち取った場面")
            for f in fielders:
                self._credit(f, dd * share / len(fielders), f"{inn_label}の守備")
        elif t == "DP":
            if fielders:
                for f in fielders:
                    self._credit(f, dd / len(fielders), f"{inn_label}に併殺を取った守備")
            else:
                self._credit(P, dd, f"{inn_label}の併殺")
        elif t == "SB":
            r = self.rules["sb_defense"]
            self._credit(P, dd * r["P"], f"{inn_label}に盗塁を許す")
            self._credit(C, dd * r["C"], f"{inn_label}に盗塁を許す")
        elif t == "CS":
            self._credit(C, dd, f"{inn_label}の盗塁阻止")
        elif t == "RO":  # 走塁ミスによるアウトは、アウトにした野手
            outs_by = fielders or [P]
            for f in outs_by:
                self._credit(f, dd / len(outs_by), f"{inn_label}に走者を刺す")
        elif t == "PO":
            self._credit(P, dd, f"{inn_label}に牽制で走者を刺した場面")
        elif t in ("WP", "BK"):
            self._credit(P, dd, f"{inn_label}の{label}")
        elif t == "PB":
            self._credit(C, dd, f"{inn_label}の{label}")
        else:
            self._credit(P, dd, f"{inn_label}の守備")

        if ev.get("fine_play"):
            name = self._who(deff, ev["fine_play"])
            self.bonus[name] += self.rules["fine_play_bonus"]
            self.plays[name].append((0.0, f"{inn_label}のファインプレー"))

    def _label(self, t, ev, off, deff, before, after):
        """得点が入ったプレーは「同点タイムリー」「サヨナラ本塁打」のように具体的に。"""
        runs = after[off] - before[off]
        base = LABELS.get(t, t)
        if runs <= 0 or t not in ("1B", "2B", "3B", "HR", "SF", "BB", "HBP", "OUT", "FC", "SH"):
            return base
        db, da = before[off] - before[deff], after[off] - after[deff]
        if getattr(self, "_game_over", False) and ev["half"] == "bottom" and da > 0 and db <= 0:
            sit = "サヨナラ"
        elif db < 0 and da == 0:
            sit = "同点"
        elif db < 0 < da:
            sit = "逆転"
        elif db == 0 and da > 0:
            sit = "先制" if before[off] == 0 and before[deff] == 0 else "勝ち越し"
        else:
            sit = ""
        if t == "HR":
            body = "本塁打" if sit else ("ソロ本塁打" if runs == 1 else f"{runs}ラン本塁打")
        elif t in ("1B", "2B", "3B"):
            body = {"1B": "タイムリー", "2B": "タイムリー二塁打", "3B": "タイムリー三塁打"}[t]
            if runs >= 2 and not sit:
                body = f"{runs}点" + body
        elif t == "SF":
            body = "犠牲フライ"
        elif t in ("BB", "HBP"):
            body = "押し出し" + base
        else:
            body = "打点付きの" + base
        return sit + body

    # ---- 成績の集計（カード表示用）----
    def _stats(self, ev, deff, before, after, off):
        t = ev.get("type")
        runs = after[off] - before[off]
        pname = self._who(deff, ev.get("pitcher", "P"))
        pt = self.pit[pname]
        pt["outs"] += max(0, after["outs"] - before["outs"])
        # 失点は、その走者を出した投手につける（引き継いだ走者の生還は前の投手の失点）
        key = (ev.get("inn"), ev.get("half"))
        if getattr(self, "_resp_key", None) != key:
            self._resp_key = key
            self._resp = [None] * bin(before["bases"] & 7).count("1")  # タイブレークの走者など
        q = self._resp
        for _ in range(runs):
            who = q.pop(0) if q else None
            self.pit[who or pname]["R"] += 1
        want = 0 if after["outs"] >= 3 else bin(after["bases"] & 7).count("1")
        while len(q) < want:
            q.append(pname)
        del q[want:]
        b = ev.get("batter")
        if not b:
            return
        bt = self.bat[b]
        bt["PA"] += 1
        if t not in ("BB", "IBB", "HBP", "SH", "SF"):
            bt["AB"] += 1
        if t in ("1B", "2B", "3B", "HR"):
            bt["H"] += 1
            pt["H"] += 1
        if t == "HR":
            bt["HR"] += 1
        if t in ("BB", "IBB", "HBP"):
            bt["BB"] += 1
            pt["BB"] += 1
        if t == "K":
            bt["K"] += 1
            pt["K"] += 1
        if t not in ("E", "DP"):
            bt["RBI"] += runs

    def stat_line(self, name, is_pitcher):
        if is_pitcher and name in self.pit:
            s = self.pit[name]
            ip = f"{s['outs'] // 3}回" + ("" if s["outs"] % 3 == 0 else f"{s['outs'] % 3}/3")
            pline = f"{ip} {s['H']}安打 {s['R']}失点 {s['K']}三振"
            if name in self.bat:  # 野手から登板した選手は打撃成績も
                b = self.bat[name]
                return f"{b['AB']}打数{b['H']}安打／投 {pline}"
            return pline
        if name in self.bat:
            s = self.bat[name]
            line = f"{s['AB']}打数{s['H']}安打"
            if s["RBI"]:
                line += f"{s['RBI']}打点"
            if s["HR"]:
                line += f"・{s['HR']}本塁打"
            if s["BB"]:
                line += f"・{s['BB']}四死球"
            return line
        roles = self.players.get(name, {}).get("roles", [])
        return "代走" if "PR" in roles else ("途中出場" if roles else "")

    # ---- 採点・表彰 ----
    def score_of(self, name):
        raw = self.rules["base"] + self.rules["coef"] * self.wpa[name] + self.bonus[name]
        return min(self.rules["cap"], round_step(raw, self.rules["step"]))

    def comment(self, name, score, won=None):
        """担任からの一言。点数の帯ごとの書き出しに、その選手の具体的なプレーを添える。"""
        agg = {}
        for v, d in self.plays[name]:
            if v != 0.0:
                agg[d] = agg.get(d, 0.0) + v
        plays = self.plays[name]
        bonus = [d for v, d in plays if v == 0.0]
        plays = [(v, d) for d, v in agg.items()] + [(0.0, d) for d in bonus]
        pos = sorted([(v, d) for v, d in plays if v >= 0.02], reverse=True)
        neg = sorted([(v, d) for v, d in plays if v <= -0.02])
        pct = lambda v: f"{abs(v) * 100:.0f}%"
        roles = self.players.get(name, {}).get("roles", [])
        pit = None
        if "P" in roles and self.pit[name]["outs"]:
            s_ = self.pit[name]
            ip = (f"{s_['outs'] // 3}回" + ("" if s_["outs"] % 3 == 0 else f"{s_['outs'] % 3}/3")) if s_["outs"] >= 3 else f"{s_['outs']}/3回"
            pit = f"{ip}を{s_['R']}失点" + (f"、{s_['K']}奪三振" if s_["K"] else "")
        out = [band_word(score, won) + "。"]
        if pit:
            out.append(f"{pit}。")
        if score >= 6.0:
            if pos:
                v, d = pos[0]
                out.append(f"{d}で勝利確率を{pct(v)}押し上げました。")
                if len(pos) > 1:
                    out.append(f"{pos[1][1]}（+{pct(pos[1][0])}）も効いています。")
            for d in bonus[:1]:
                out.append(f"{d}も見事でした。")
            if neg and neg[0][0] <= -0.05:
                out.append(f"{neg[0][1]}（−{pct(neg[0][0])}）だけは惜しかった。")
            if not pos and not bonus:
                if neg:
                    out.append(f"{neg[0][1]}は惜しかったものの、大きく流れを渡しはしませんでした。")
                elif any(r in roles for r in ("PR",)):
                    out.append("代走での出場。試合を動かす場面はありませんでした。")
                elif not plays:
                    out.append("出場は短く、勝負を動かす場面はありませんでした。")
                else:
                    out.append("大きな失点も得点もなく、役目は果たしました。")
            tot = self.wpa[name]
            if score >= 8.5 and pos and tot - pos[0][0] >= 0.04:
                out.append(f"この試合の合計では勝利確率+{pct(tot)}の働きでした。")
            closer = {True: "次の試合でも主役を。", False: "次はもうひと押しを。"}[score >= 7.0]
            out.append(closer)
        else:
            if neg:
                v, d = neg[0]
                out.append(f"{d}で勝利確率を{pct(v)}落としました。")
                if len(neg) > 1:
                    out.append(f"{neg[1][1]}（−{pct(neg[1][0])}）も響きました。")
            if pos:
                out.append(f"それでも{pos[0][1]}（+{pct(pos[0][0])}）は収穫です。")
            elif bonus:
                out.append(f"それでも{bonus[0]}は収穫です。")
            out.append("次に期待しています。" if score >= 5.0 else "切り替えて次へ。")
        return "".join(out)

    def reasons(self, name, n=2):
        """採点の理由：プラスが大きいプレー上位n件（ボーナスも含む）。投手は投球内容を先頭に。"""
        head = []
        if "P" in self.players.get(name, {}).get("roles", []) and self.pit[name]["outs"]:
            s = self.pit[name]
            ip = f"{s['outs'] // 3}回" + ("" if s["outs"] % 3 == 0 else f"{s['outs'] % 3}/3")
            head = [{"text": f"{ip}を{s['R']}失点" + (f"・{s['K']}奪三振" if s["K"] else ""), "wpa": None}]
        bonus = [{"text": d, "wpa": None} for v, d in self.plays[name] if v == 0.0]
        pos = sorted([(v, d) for v, d in self.plays[name] if v > 0.005], reverse=True)
        out = bonus + [{"text": d, "wpa": round(v, 3)} for v, d in pos]
        if not out:
            neg = sorted([(v, d) for v, d in self.plays[name] if v < -0.005])
            out = [{"text": d, "wpa": round(v, 3)} for v, d in neg]
        return (head + out)[:n]

    def report(self):
        fs = self.final_state
        winner = "home" if fs["home"] > fs["away"] else ("away" if fs["away"] > fs["home"] else None)
        rows = []
        for name, p in self.players.items():
            if name in POSITIONS:
                continue
            sc = self.score_of(name)
            is_pitcher = "P" in p["roles"]
            pos = next((r for r in p["roles"] if r in POSITIONS), None)
            pos_ja = POS_JA.get(pos) or {"PH": "打", "PR": "走"}.get(next((r for r in p["roles"] if r in ("PH", "PR")), ""), "")
            pinfo = self.data.get("players", {}).get(name, {})
            rows.append({
                "order": pinfo.get("order"), "number": pinfo.get("number"),
                "pos_code": pos,
                "pos": pos_ja, "stat": self.stat_line(name, is_pitcher),
                "player": name, "team": self.info[p["team"]], "side": p["team"],
                "pitcher": is_pitcher, "wpa": round(self.wpa[name], 4),
                "bonus": self.bonus[name], "score": sc,
                "raw_score": round_step(self.rules["base"] + self.rules["coef"] * self.wpa[name] + self.bonus[name],
                                        self.rules["step"]), "comment": self.comment(name, sc, won=(winner == p["team"]) if winner else None),
                "best_play": max(self.plays[name], default=(0, ""))[1],
                "reasons": self.reasons(name),
                "reasons_all": self.reasons(name, n=4),
            })
        rows.sort(key=lambda r: (-r["score"], -r["wpa"]))

        awards = {"pitcher_mvp": None, "fielder_mvp": None, "fighting_spirit": None}
        if winner:
            loser = "away" if winner == "home" else "home"
            win_p = [r for r in rows if r["side"] == winner and r["pitcher"]]
            win_f = [r for r in rows if r["side"] == winner and not r["pitcher"]]
            lose = [r for r in rows if r["side"] == loser]
            if win_p and win_p[0]["score"] >= self.rules["mvp_min"]:
                awards["pitcher_mvp"] = win_p[0]["player"]
            if win_f and win_f[0]["score"] >= self.rules["mvp_min"]:
                awards["fielder_mvp"] = win_f[0]["player"]
            if lose and lose[0]["score"] >= self.rules["fighting_min"]:
                awards["fighting_spirit"] = lose[0]["player"]

        return {
            "game": self.info,
            "final": {"away": fs["away"], "home": fs["home"],
                      "winner": self.info[winner] if winner else None},
            "awards": awards,
            "ratings": rows,
            "plays": self.log,
            "warnings": self.warnings,
            "rules_version": "2026-11-19 pilot",
        }


def band_word(score, won=None):
    """点数の帯の呼び名。勝ったチームは称号、負けたチーム（と引き分け）は通信簿の言葉。"""
    i = 0 if score >= 8.5 else 1 if score >= 7.0 else 2 if score >= 6.0 else 3 if score >= 5.0 else 4
    if won:
        return BANDS_WIN[i]
    return BANDS_LOSE[i]


def score_game(data, rules=None):
    return Game(data, rules).run()
