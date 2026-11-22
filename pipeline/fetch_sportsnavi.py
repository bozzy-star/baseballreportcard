"""スポーツナビ（バーチャル高校野球・大学野球）から試合を取得する。

- list_games(league, id_from, id_to): 試合IDの範囲を見て、日付・カード・状態を返す
- fetch_game(league, game_id): テキスト速報＋選手一覧を、brc.parse_yahoo が読める文章にして返す
  （あわせて学年・開始/終了時刻・回戦などのメタ情報も返す）

ページの HTML をブラウザの innerText に近い形の文章に直してから使う。
"""
import html
import re
import time
import urllib.request
from html.parser import HTMLParser

BASE = "https://baseball.yahoo.co.jp"
UA = "Mozilla/5.0 (compatible; BaseballReportCard/1.0; +https://baseballreportcard.com)"
BLOCK = set("p div li ul ol h1 h2 h3 h4 h5 h6 section header footer article nav table thead tbody tr dl dt dd main aside figure form".split())
SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}
VOID = {"br", "img", "input", "meta", "link", "hr", "source", "wbr", "col", "area", "base", "embed", "param", "track"}


def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
            with urllib.request.urlopen(req, timeout=30) as res:
                return res.status, res.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, ""
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(2 + i * 3)
    raise RuntimeError(f"取得に失敗しました: {url} ({last})")


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent

    def cls(self):
        return self.attrs.get("class", "") or ""

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.iter()

    def find_all(self, tag=None, cls=None):
        for n in self.iter():
            if (tag is None or n.tag == tag) and (cls is None or cls in n.cls().split()):
                yield n

    def find(self, tag=None, cls=None):
        return next(self.find_all(tag, cls), None)

    def text(self):
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse_html(s):
    b = _TreeBuilder()
    b.feed(s)
    return b.root


def inner_text(node):
    """ブラウザの innerText に近い文章（行ごと、空行なし）。"""
    out = []

    def walk(n, in_cell=False):
        if isinstance(n, str):
            out.append(re.sub(r"[ \t\r\n]+", " ", n))
            return
        if n.tag in SKIP:
            return
        if n.tag == "br":
            out.append(" " if in_cell else "\n")
            return
        blk = n.tag in BLOCK and not in_cell  # 表のマスの中の段落は改行しない（空の回の <p></p> など）
        if blk:
            out.append("\n")
        cell = n.tag in ("td", "th")
        if cell:
            out.append("\t")
        for c in n.children:
            walk(c, in_cell or cell)
        if blk:
            out.append("\n")

    walk(node)
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in "".join(out).split("\n")]
    return [l for l in lines if l]


def _title(doc):
    t = doc.find("title")
    return html.unescape(t.text()).split(" - ")[0].strip() if t else ""


def game_status(doc):
    """試合カードの状態表示（試合前／〇回表／試合終了／中止 など）から状態を返す。"""
    n = doc.find(cls="bb-gameCard__state")
    t = re.sub(r"\s+", "", n.text()) if n else ""
    if t == "試合終了":
        return "final"
    if re.search(r"中止|順延|ノーゲーム|継続", t):
        return "cancelled"
    if t in ("試合前", "") or re.search(r"見どころ|予告", t):
        return "scheduled"
    return "live"


def list_games(league, id_from, id_to):
    """[{id, date, home, away, title, status}] 。存在しない ID は飛ばす。"""
    out = []
    for gid in range(id_from, id_to + 1):
        st, s = get(f"{BASE}/{league}/game/{gid}/top")
        if st != 200 or not s:
            continue
        doc = parse_html(s)
        title = _title(doc)
        m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日 (.+?)vs\.(.+)$", title)
        if not m:
            continue
        status = game_status(doc)
        out.append({"id": gid, "date": f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}", "home": m[4].strip(), "away": m[5].strip(),
                    "title": title, "status": status})
    return out


def _roster(doc):
    """選手一覧（parse_yahoo 用の行）と学年 {name: '2年'}。"""
    team_of_cls, tables = {}, []
    for t in doc.find_all("table", "bb-splitsTable"):
        mcls = re.search(r"bb-splitsTable--(\S+)", t.cls())
        key = mcls.group(1) if mcls else None
        sec = t.parent
        while sec is not None and sec.tag != "section":
            sec = sec.parent
        h = sec.find("h1") if sec is not None else None
        if h is not None and key:
            team_of_cls.setdefault(key, h.text().strip())
        rows = [[re.sub(r"\s+", " ", c.text()).strip() for c in tr.children if isinstance(c, Node) and c.tag in ("td", "th")]
                for tr in t.find_all("tr")]
        tables.append((key, rows))
    teams = {}
    grades = {}
    for key, rows in tables:
        team = team_of_cls.get(key)
        if not team or not rows:
            continue
        r = teams.setdefault(team, {"order": [], "bench": []})
        head = rows[0]
        for row in rows[1:]:
            if len(row) < len(head):
                continue
            rec = dict(zip(head, row))
            name = rec.get("選手名")
            if not name:
                continue
            if rec.get("学年"):
                grades.setdefault(team, {})[name] = rec["学年"]
            if head[0] == "打順" and rec.get("打順", "").isdigit():
                r["order"].append(f"{rec['打順']} {rec.get('位置', '')} {name}")
            else:
                r["bench"].append(name)
    lines = ["選手一覧"]
    for team, r in teams.items():
        lines.append(team)
        lines += r["order"]
        lines += [f"控え {n}" for n in r["bench"] if all(not o.endswith(" " + n) for o in r["order"])]
    return lines, grades


def fetch_game(league, gid):
    """parse_yahoo 用の文章と、メタ情報を返す。"""
    st, top = get(f"{BASE}/{league}/game/{gid}/top")
    if st != 200:
        raise RuntimeError(f"試合ページがありません: {league} {gid}")
    tdoc = parse_html(top)
    st, txt = get(f"{BASE}/{league}/game/{gid}/text")
    xdoc = parse_html(txt)
    lines = inner_text(xdoc.find("div", "bb-centerColumn") or xdoc)
    # 大会名の行から始める（上部のメニューを除く）
    start = next((i for i, l in enumerate(lines) if re.search(r"(大会|リーグ|選手権).*・|の部$", l)), 0)
    lines = lines[start:]
    roster_lines, grades = _roster(tdoc)
    meta = {"title": _title(tdoc), "status": game_status(tdoc), "final": game_status(tdoc) == "final"}
    head = lines[:8]
    if len(head) >= 4:
        meta["round"] = head[1]
        meta["time"] = next((l for l in head if re.match(r"^\d{1,2}:\d\d$", l)), None)
        meta["venue"] = head[head.index(meta["time"]) + 1] if meta["time"] and head.index(meta["time"]) + 1 < len(head) else None
    end = next((l for l in lines[:40] if re.match(r"^\d{4}/\d{1,2}/\d{1,2} \d{1,2}:\d\d$", l)), None)
    meta["end"] = end.split()[1] if end else None
    meta["grades"] = grades
    return "\n".join(lines + roster_lines) + "\n", meta
