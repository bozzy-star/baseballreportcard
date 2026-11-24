"""サイト全体の配色を「紙の通信簿」に変える。

ページの部品は濃紺の地を前提に色を直書きしているので、
できあがったHTMLを最後に読み、背景の文脈（紙の上か、色付きの帯の上か）を見ながら色を置き換える。
"""
import re
from html.parser import HTMLParser

PAPER = "#F6F1E4"      # 地（生成りの紙）
PAPER2 = "#EFE7D4"     # 一段濃い紙（区切りの帯）
CARD = "#FFFDF7"       # カード・表
INK = "#222831"        # 本文
INK2 = "#3D4552"       # 弱めの本文
MUTED = "#5B6270"      # 補足
NAVY = "#1F2D4D"       # ヘッダー・見出し
RED = "#B8202E"        # 赤ペン
LINE = "#D6CCB4"       # 罫線（紙）
RULE = "#D6DEE8"       # 罫線（ノートの青）

# 背景：濃紺の地 → 紙
BG_PAGE = {"#0B1A36", "#081327", "#0A1222", "#0E1E40", "#0E2147", "#1C2A44", "#14294F", "#1A3260"}
BG_MAP = {
    "#0B1A36": PAPER, "#081327": PAPER2, "#0A1222": PAPER2, "#0E1E40": PAPER2, "#0E2147": PAPER2,
    "#1C2A44": PAPER2, "#14294F": PAPER2, "#1A3260": PAPER,
    "#FFFFFF": CARD, "#FBF8EF": CARD, "#E7ECF4": "#F1EBDD",
    "#D7262E": RED, "#14306A": NAVY, "#3D5C93": NAVY, "#5C7FBA": "#2B5C99", "#FFD23F": RED,
}
# 色付きの帯（白文字のまま）
ACCENT_BG = {"#D7262E", "#B8202E", "#3D5C93", "#5B6B86", "#2E9E6B", "#14306A", "#1F2D4D", "#5C7FBA", "#2B5C99"}

# 紙の上の文字色
FG_ON_PAPER = {
    "#FFFFFF": INK, "#C9D6EA": INK2, "#E6ECF6": INK2, "#E7ECF4": INK2, "#F4F6FA": INK2, "#B8C3D6": MUTED,
    "#9FB3D6": MUTED, "#AFC4E6": MUTED, "#5C7FBA": "#2B5C99", "#3D5C93": NAVY, "#F3B7BA": RED,
    "#FFD23F": RED, "#FFF4D6": INK2, "#FBF8EF": INK, "#0B1A36": INK, "#0A1222": INK, "#081327": INK,
    "#14294F": NAVY, "#5B6B86": MUTED, "#D7262E": RED, "#A8141B": "#8E1822",
}
FG_ANY = {"#D7262E": RED, "#A8141B": "#8E1822"}

BORDER = {"#3D5C93": LINE, "#24427A": LINE, "#14294F": NAVY, "#FFFFFF": LINE, "#C9D6EA": RULE, "#D7262E": RED, "#0B1A36": LINE}
SVG_FILL = {"#9FB3D6": MUTED, "#FFFFFF": NAVY, "#F3B7BA": RED, "#AFC4E6": MUTED, "#D7262E": RED, "#FFD23F": RED}
SVG_STROKE = {"#24427A": RULE, "#FFFFFF": NAVY, "#9FB3D6": MUTED, "#FFD23F": RED, "#D7262E": RED}

HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def _decls(style):
    out = []
    for part in style.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out.append([k.strip(), v.strip()])
    return out


def _sub(v, table):
    return HEX.sub(lambda m: table.get(m.group(0).upper(), m.group(0)), v)


def _bg_of(decls):
    for k, v in decls:
        if k in ("background-color", "background"):
            m = HEX.search(v)
            if m:
                return m.group(0).upper()
            m = re.search(r"rgba?\(([^)]*)\)", v)
            if m:
                parts = [p.strip() for p in m.group(1).split(",")]
                if len(parts) == 4 and float(parts[3]) >= 0.9:
                    return "ACCENT"
    return None


def restyle(style, ctx, tag):
    """1つの要素の style を書き換える。戻り値は (新しいstyle, 子に渡す文脈)。"""
    d = _decls(style)
    bg = _bg_of(d)
    new_ctx = ctx
    if tag in ("header", "footer"):
        new_ctx = "accent"
    elif bg in BG_PAGE:
        new_ctx = "paper"
    elif bg in ACCENT_BG or bg == "ACCENT":
        new_ctx = "accent"
    elif bg:
        new_ctx = "paper"
    out = []
    for k, v in d:
        if tag in ("header", "footer") and k in ("background-color", "background"):
            v = NAVY
        elif k in ("background-color", "background"):
            v = _sub(v, BG_MAP)
        elif k == "background-image" and "gradient" in v and bg in BG_PAGE:
            continue
        elif k == "color":
            if tag in ("h1", "h2", "h3") and new_ctx != "accent":
                v = _sub(v, {"#FFFFFF": NAVY, "#14294F": NAVY})
            v = _sub(v, FG_ANY if new_ctx == "accent" else FG_ON_PAPER)
        elif k.startswith("border") or k in ("outline", "text-decoration-color"):
            v = _sub(v, BORDER if new_ctx != "accent" else {"#D7262E": RED})
        elif k == "box-shadow":
            v = re.sub(r"rgba\(0,\s*0,\s*0,\s*[0-9.]+\)", "rgba(90, 70, 30, 0.12)", v)
            v = _sub(v, {"#FFFFFF": LINE, "#0A1222": LINE})
        elif k in ("fill", "stroke") and new_ctx != "accent":
            v = _sub(v, SVG_FILL if k == "fill" else SVG_STROKE)
        out.append(f"{k}: {v}")
    return "; ".join(out), new_ctx


class _T(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out, self.stack, self.in_style = [], ["paper"], False

    def _attrs(self, tag, attrs):
        ctx = self.stack[-1]
        parts, new_ctx = [], ctx
        has_style = False
        for k, v in attrs:
            if k == "style" and v is not None:
                v, new_ctx = restyle(v, ctx, tag)
                has_style = True
            elif k in ("fill", "stroke") and v and ctx != "accent":
                v = _sub(v, SVG_FILL if k == "fill" else SVG_STROKE)
            elif k == "stop-color" and v:
                v = _sub(v, SVG_FILL)
            parts.append(k if v is None else f'{k}="{v}"')
        if tag in ("header", "footer") and not has_style:
            new_ctx = "accent"
        return (" " + " ".join(parts)) if parts else "", new_ctx

    def handle_starttag(self, tag, attrs):
        a, ctx = self._attrs(tag, attrs)
        self.out.append(f"<{tag}{a}>")
        if tag == "style":
            self.in_style = True
        if tag not in VOID:
            self.stack.append(ctx)

    def handle_startendtag(self, tag, attrs):
        a, _ = self._attrs(tag, attrs)
        self.out.append(f"<{tag}{a}/>")

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False
        if tag not in VOID and len(self.stack) > 1:
            self.stack.pop()
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if self.in_style:
            data = _style_block(data)
        self.out.append(data)

    def handle_entityref(self, name):
        self.out.append(f"&{name};")

    def handle_charref(self, name):
        self.out.append(f"&#{name};")

    def handle_comment(self, data):
        self.out.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.out.append(f"<!{decl}>")


def _style_block(css):
    css = re.sub(r"background(-color)?:\s*#0B1A36", f"background:{PAPER}", css, flags=re.I)
    css = HEX.sub(lambda m: {"#D7262E": RED, "#A8141B": "#8E1822", "#FFFFFF": INK, "#C9D6EA": RULE}.get(m.group(0).upper(), m.group(0)), css)
    return css + EXTRA_CSS


EXTRA_CSS = f"""
body{{background:{PAPER} !important;color:{INK}}}
h1,h2,h3{{font-family:'Shippori Mincho','Noto Serif JP',serif;letter-spacing:0.02em}}
header a,header span,footer a,footer span,footer p{{color:#F6F1E4}}
header nav a[href*="x.com"]{{background:{RED} !important}}
"""

FONT_LINK = "family=Shippori+Mincho:wght@600;800&amp;"


def paper(html):
    t = _T()
    t.feed(html)
    t.close()
    s = "".join(t.out)
    s = s.replace("css2?family=Noto+Sans+JP", "css2?" + FONT_LINK + "family=Noto+Sans+JP", 1) if FONT_LINK not in s else s
    return s
