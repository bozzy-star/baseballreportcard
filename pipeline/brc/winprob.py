"""勝利確率（Win Probability）モデル。

塁・アウト状況ごとの「この回の残り得点の分布」を作り、
残りイニングを動的計画法で積み上げて、ホームチームの勝利確率を出す。

- 基準となる得点期待値表（RE24）と得点確率表は MLB の標準的な値。
- リーグごとに 1イニングあたり平均得点で全体をスケールする
  （NPB 基準 / MLB 基準 / 高校 / 大学）。
- タイブレーク（10回から無死一・二塁など）にも対応。
"""
from functools import lru_cache

# 塁状況はビットで表す：一塁=1, 二塁=2, 三塁=4
# RE24（その状況から回終了までの平均得点）  [outs][bases]
_RE = {
    0: {0: .48, 1: .85, 2: 1.06, 3: 1.42, 4: 1.31, 5: 1.70, 6: 1.91, 7: 2.25},
    1: {0: .25, 1: .50, 2: .64, 3: .88, 4: .89, 5: 1.10, 6: 1.35, 7: 1.52},
    2: {0: .10, 1: .21, 2: .31, 3: .42, 4: .35, 5: .47, 6: .55, 7: .74},
}
# その状況から1点以上入る確率  [outs][bases]
_PSCORE = {
    0: {0: .27, 1: .42, 2: .61, 3: .62, 4: .83, 5: .85, 6: .85, 7: .86},
    1: {0: .16, 1: .27, 2: .41, 3: .42, 4: .66, 5: .64, 6: .68, 7: .67},
    2: {0: .07, 1: .13, 2: .22, 3: .23, 4: .27, 5: .28, 6: .27, 7: .32},
}
_BASE_RUNS_PER_INNING = 0.48  # 上の表が前提とする1イニング平均得点

# リーグ別の設定（1イニング平均得点、ホーム有利、タイブレーク開始回）
LEAGUES = {
    "NPB":  {"runs_per_inning": 0.40, "tiebreak_from": None, "max_inning": 12},
    "MLB":  {"runs_per_inning": 0.48, "tiebreak_from": 10,   "max_inning": 15},
    "INTL": {"runs_per_inning": 0.48, "tiebreak_from": 10,   "max_inning": 15},  # 国際試合はMLB基準
    "HS":   {"runs_per_inning": 0.50, "tiebreak_from": 10,   "max_inning": 15},  # 高校
    "UNIV": {"runs_per_inning": 0.45, "tiebreak_from": 10,   "max_inning": 15},  # 大学
}
TIEBREAK_BASES = 3  # 無死一・二塁
MAX_RUNS = 20
DIFF_CAP = 25


def bases_from_str(s):
    """'13' のような文字列（塁番号の並び）をビットに。空文字は走者なし。"""
    b = 0
    for ch in str(s or ""):
        if ch == "1":
            b |= 1
        elif ch == "2":
            b |= 2
        elif ch == "3":
            b |= 4
    return b


def bases_to_str(b):
    return "".join(str(i + 1) for i in range(3) if b & (1 << i))


class WinProbModel:
    def __init__(self, league="NPB", tiebreak_from="default", max_inning=None):
        cfg = LEAGUES[league]
        self.league = league
        self.scale = cfg["runs_per_inning"] / _BASE_RUNS_PER_INNING
        self.tiebreak_from = cfg["tiebreak_from"] if tiebreak_from == "default" else tiebreak_from
        self.max_inning = max_inning or cfg["max_inning"]
        self._dist_cache = {}
        self._V = lru_cache(maxsize=None)(self._V_impl)

    # ---- 1イニング内の残り得点分布 ----
    def run_dist(self, outs, bases):
        key = (outs, bases)
        if key in self._dist_cache:
            return self._dist_cache[key]
        re = _RE[outs][bases] * self.scale
        p0 = 1 - _PSCORE[outs][bases]
        # 得点の起きやすさもスケール（0点の確率を調整）
        p = 1 - p0 ** self.scale
        p = min(max(p, 1e-6), 0.999)
        m1 = max(re / p, 1.0001)  # 得点したときの平均得点
        q = 1 - 1 / m1             # 2点目以降は幾何分布
        dist = [1 - p] + [p * (1 - q) * q ** (k - 1) for k in range(1, MAX_RUNS + 1)]
        tot = sum(dist)
        dist = [x / tot for x in dist]
        self._dist_cache[key] = dist
        return dist

    def _fresh_dist(self, inning):
        if self.tiebreak_from and inning >= self.tiebreak_from:
            return self.run_dist(0, TIEBREAK_BASES)
        return self.run_dist(0, 0)

    # ---- 半イニング開始時点でのホーム勝率 ----
    def _V_impl(self, inning, half, diff):
        """diff = ホーム得点 − ビジター得点。half は 'top' / 'bottom'。"""
        diff = max(-DIFF_CAP, min(DIFF_CAP, diff))
        if inning > self.max_inning:
            return 0.5 if diff == 0 else (1.0 if diff > 0 else 0.0)
        dist = self._fresh_dist(inning)
        if half == "top":
            return sum(pk * self._after_top(inning, diff - k) for k, pk in enumerate(dist))
        return sum(pk * self._after_bottom(inning, diff + k) for k, pk in enumerate(dist))

    def _after_top(self, inning, diff):
        if inning >= 9 and diff > 0:
            return 1.0  # 裏の攻撃なしでホーム勝ち
        return self._V(inning, "bottom", diff)

    def _after_bottom(self, inning, diff):
        if inning >= 9:
            if diff > 0:
                return 1.0
            if diff < 0:
                return 0.0
        return self._V(inning + 1, "top", diff)

    # ---- 任意の状況でのホーム勝率 ----
    def home_wp(self, inning, half, outs, bases, home_score, away_score, game_over=False):
        diff = home_score - away_score
        if game_over:
            return 1.0 if diff > 0 else (0.0 if diff < 0 else 0.5)
        if half == "bottom" and inning >= 9 and diff > 0:
            return 1.0  # サヨナラ成立
        if outs >= 3:
            return self._after_top(inning, diff) if half == "top" else self._after_bottom(inning, diff)
        dist = self.run_dist(outs, bases)
        if half == "top":
            return sum(pk * self._after_top(inning, diff - k) for k, pk in enumerate(dist))
        return sum(pk * self._after_bottom(inning, diff + k) for k, pk in enumerate(dist))
