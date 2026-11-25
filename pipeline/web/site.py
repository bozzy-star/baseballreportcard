"""公開用の静的サイト一式を _site に作る（PC版とスマホ版を1ページにまとめ、画面幅で切り替え）。

  python3 pipeline/web/site.py [出力先]
"""
import json, os, re, shutil, subprocess, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import theme  # noqa: E402
import datetime as _dt

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = pathlib.Path(__file__).resolve().parent
SITE = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
TMP = pathlib.Path(os.environ.get("BRC_TMP", "/tmp/brc-build")); TMP.mkdir(parents=True, exist_ok=True)
INSIGHT = pathlib.Path(os.environ.get("BRC_INSIGHT", "/tmp/brc-insight"))
REG = json.loads((ROOT / "data" / "registry.json").read_text(encoding="utf-8"))["games"]
COMPS = json.loads((ROOT / "data" / "competitions.json").read_text(encoding="utf-8"))
PUB = [g for g in REG if g.get("status") in ("published", "processed")]
X_PROFILE = "https://x.com/BaseBalltannin"
SITECFG = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8")) if (ROOT / "data" / "site.json").exists() else {}
GTM = (SITECFG.get("gtm_id") or "").strip()
GTM_HEAD = (f"""<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);}})(window,document,'script','dataLayer','{GTM}');</script>
""" if GTM else "")
GTM_BODY = (f"""<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={GTM}" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
""" if GTM else "")
GA4 = (SITECFG.get("ga4_id") or "").strip()
if GA4 and not GTM:
    GTM_HEAD = f"""<script async src="https://www.googletagmanager.com/gtag/js?id={GA4}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA4}');</script>
"""


sys.path.insert(0, str(ROOT / "pipeline"))
from brc import paths  # noqa: E402
from brc.paths import pretty  # noqa: E402
from brc.ids import player_id  # noqa: E402

BASE = "https://baseballreportcard.com/"


def urls(extra=None):
    """リンク先の一覧（サイト内のパス）。各ページで相対リンクに直して使う。"""
    extra = dict(extra or {})
    cid = extra.pop("_comp", None) or (PUB[-1]["comp"] if PUB else next(iter(COMPS)))
    comp = COMPS[cid]
    u = {"top": "index.html", "tournaments": "tournaments/index.html", "family": paths.family_page(comp),
         "tournament": paths.comp_page(comp), "archive": paths.comp_page(comp) + "#archive", "players": paths.players_page(comp),
         "rules": "scoring.html", "privacy": "privacy.html", "about": "about.html", "img_batter": "assets/batter-navy.png", "img_pitcher": "assets/pitcher-navy.png",
         "img_hero": "assets/hero-stadium.jpg", "img_hanamaru": "assets/badges/hanamaru.png"}
    for g in PUB:
        c = COMPS[g["comp"]]
        u["game:" + g["key"]] = paths.game_page(c, g)
        u["day:" + g["date"]] = paths.day_page(c, g["date"])
    u.update(extra)
    return u


def run(script, args, page, extra=None):
    env = dict(os.environ, BRC_URLS=json.dumps(urls(extra)), BRC_PAGE=page, OUT=str(TMP), BRC_INSIGHT=str(INSIGHT), BRC_ROOT=str(ROOT))
    res = subprocess.run([sys.executable, str(WEB / script), *args], cwd=str(WEB), env=env, capture_output=True, text=True)
    if res.returncode:
        sys.stderr.write(res.stdout + res.stderr)
        raise SystemExit(f"{script} {args} が失敗しました")


def inner(path):
    s = path.read_text()
    title = re.search(r"<title>(.*?)</title>", s).group(1)
    style = re.search(r"<style>(.*?)</style>", s, re.S).group(1)
    body = s.split("</helmet>", 1)[1].split("</x-dc>", 1)[0]
    return title, style, body


def merge(pc, sp, page, title, desc):
    out = SITE / page
    _, style, a = inner(TMP / pc)
    _, _, b = inner(TMP / sp)
    b = b.replace('<div style="width: 390px; min-height: 100vh;', '<div style="min-height: 100vh;', 1)
    html = f"""<!doctype html>
<html lang="ja">
<head>
{GTM_HEAD}<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/icons/favicon-32.png">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/icons/icon-192.png">
<link rel="apple-touch-icon" href="/assets/icons/apple-touch-icon.png">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{BASE}{pretty(page)}">
<meta property="og:url" content="{BASE}{pretty(page)}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@BaseBalltannin">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&amp;family=Yomogi&amp;display=swap">
<style>{style}
summary::-webkit-details-marker{{display:none}}
.v-sp{{display:none}}
@media (max-width: 760px){{.v-pc{{display:none}}.v-sp{{display:block}}}}
</style>
</head>
<body>
{GTM_BODY}<div class="v-pc">{a}</div>
<div class="v-sp">{b}</div>
</body>
</html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(theme.paper(html))


REDIRECTS = {}


def redirect(old, new):
    """古いURLに、新しいURLへ転送するだけのページを置く（GitHub Pages はサーバー側の転送ができないため）。"""
    REDIRECTS[old] = new
    out = SITE / old
    out.parent.mkdir(parents=True, exist_ok=True)
    to = paths.rel(new, old)
    out.write_text(f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><title>移動しました｜ベースボール通信簿</title>
<link rel="canonical" href="{BASE}{pretty(new)}"><meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url={to}"><script>location.replace({json.dumps(to)} + location.hash)</script></head>
<body><p>このページは移動しました。<a href="{to}">新しいページへ</a></p></body></html>
""")


if SITE.exists():
    shutil.rmtree(SITE)
shutil.copytree(ROOT / "static", SITE)
(SITE / "cards").mkdir(parents=True, exist_ok=True)

# 試合ページ
for g in PUB:
    key = g["key"]
    comp = COMPS[g["comp"]]
    page = paths.game_page(comp, g)
    cards = g.get("cards") or []
    for c in cards + (g.get("player_cards") or []):
        if (ROOT / "data" / "cards" / c).exists():
            shutil.copy(ROOT / "data" / "cards" / c, SITE / "cards" / c)
    extra = {"x_post": g.get("x_url") or X_PROFILE, "_comp": g["comp"]}
    if len(cards) == 2:
        extra.update(card_win=f"cards/{cards[0]}", card_lose=f"cards/{cards[1]}")
    run("build.py", [key], page, extra)
    t = re.search(r"<title>試合ページ（PC）(.*?)対(.*?)</title>", (TMP / f"{key}.pc.dc.html").read_text())
    title = f"{t.group(1)} 対 {t.group(2)} の通信簿｜{comp['name']}｜ベースボール通信簿"
    merge(f"{key}.pc.dc.html", f"{key}.sp.dc.html", page, title,
          f"{t.group(1)}対{t.group(2)}の全選手を10点満点で採点。勝利確率の推移と回ごとの貢献度も。")
    redirect(f"games/{key}.html", page)

run("rules.py", [], "scoring.html")
merge("Rules.dc.html", "RulesMobile.dc.html", "scoring.html", "採点のしくみ｜ベースボール通信簿",
      "ベースボール通信簿の採点方法。6.0点が及第点、勝利確率をどれだけ動かしたかで10点満点の点数をつけます。")

# 大会（年度ページ・選手一覧・部・学校・選手・日付）
for cid, c in COMPS.items():
    if not any(g["comp"] == cid for g in PUB):
        continue
    run("top.py", ["tourney", cid], paths.comp_page(c), {"_comp": cid})
    merge("Tourney.dc.html", "TourneyMobile.dc.html", paths.comp_page(c), f"{c['name']}｜ベースボール通信簿",
          f"{c['name']}の全試合を、日付ごとに。全選手を10点満点で採点した通信簿の一覧です。")
    if c.get("legacy_page"):
        redirect(c["legacy_page"], paths.comp_page(c))
    run("players.py", ["comp", cid], paths.comp_page(c), {"_comp": cid})
    for m in json.loads((TMP / f"comp-{cid}" / "manifest.json").read_text(encoding="utf-8")):
        merge(f"comp-{cid}/{m['id']}.pc.dc.html", f"comp-{cid}/{m['id']}.sp.dc.html", m["page"], m["title"], m["desc"])
        if m.get("legacy"):
            redirect(m["legacy"], m["page"])

# 大会一覧・大会ごとのトップ
run("players.py", ["hubs"], "tournaments/index.html")
for m in json.loads((TMP / "hubs" / "manifest.json").read_text(encoding="utf-8")):
    merge(f"hubs/{m['id']}.pc.dc.html", f"hubs/{m['id']}.sp.dc.html", m["page"], m["title"], m["desc"])

run("about.py", [], "about.html")
merge("About.dc.html", "AboutMobile.dc.html", "about.html", "ベースボール通信簿について｜ベースボール通信簿",
      "ベースボール通信簿を作った理由、やりたいこと、対象とする試合、通信簿の読み方をまとめています。")
run("privacy.py", [], "privacy.html")
merge("Privacy.dc.html", "PrivacyMobile.dc.html", "privacy.html", "プライバシーポリシー｜ベースボール通信簿",
      "ベースボール通信簿のプライバシーポリシー（アクセス解析と外部への情報送信について）。")
run("top.py", [], "index.html")
merge("Top.dc.html", "TopMobile.dc.html", "index.html", "ベースボール通信簿｜全試合、全選手の活躍を採点！",
      "野球の全試合・全選手を10点満点で採点する「通信簿」。打った・抑えただけでなく、その場面がどれだけ勝敗を動かしたかで点をつけます。")

# 検索エンジン向け（サイトマップと robots.txt）。転送用のページは載せない
today = _dt.date.today().isoformat()
pages = sorted(p.relative_to(SITE).as_posix() for p in SITE.rglob("*.html"))
locs = []
for rel in pages:
    if rel in REDIRECTS or rel.startswith("google"):
        continue
    pri = "1.0" if rel == "index.html" else ("0.8" if rel.startswith("tournaments/") else "0.6")
    locs.append(f"<url><loc>{BASE}{pretty(rel)}</loc><lastmod>{today}</lastmod><priority>{pri}</priority></url>")
(SITE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(locs) + "\n</urlset>\n")
(SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n")
(SITE / "redirects.json").write_text(json.dumps(REDIRECTS, ensure_ascii=False, indent=1))
print(f"{sum(1 for p in SITE.rglob('*') if p.is_file())} files -> {SITE}（転送 {len(REDIRECTS)}）")
