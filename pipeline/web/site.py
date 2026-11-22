"""公開用の静的サイト一式を _site に作る（PC版とスマホ版を1ページにまとめ、画面幅で切り替え）。

  python3 pipeline/web/site.py [出力先]
"""
import json, os, re, shutil, subprocess, sys, pathlib

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


def urls(depth, extra=None):
    p = "../" * depth
    comp = COMPS[(extra or {}).pop("_comp", None) or (PUB[-1]["comp"] if PUB else next(iter(COMPS)))]
    u = {"top": p + "index.html", "tournament": p + comp["page"], "archive": p + comp["page"] + "#archive",
         "rules": p + "scoring.html", "privacy": p + "privacy.html", "img_batter": p + "assets/batter-navy.png", "img_pitcher": p + "assets/pitcher-navy.png",
         "img_hero": p + "assets/hero-stadium.jpg"}
    for g in PUB:
        u["game:" + g["key"]] = p + f"games/{g['key']}.html"
    u.update(extra or {})
    return u


def run(script, args, depth, extra=None):
    env = dict(os.environ, BRC_URLS=json.dumps(urls(depth, dict(extra or {}))), OUT=str(TMP), BRC_INSIGHT=str(INSIGHT), BRC_ROOT=str(ROOT))
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


def merge(pc, sp, out, title, desc):
    _, style, a = inner(TMP / pc)
    _, _, b = inner(TMP / sp)
    b = b.replace('<div style="width: 390px; min-height: 100vh;', '<div style="min-height: 100vh;', 1)
    html = f"""<!doctype html>
<html lang="ja">
<head>
{GTM_HEAD}<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
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
    out.write_text(html)


if SITE.exists():
    shutil.rmtree(SITE)
shutil.copytree(ROOT / "static", SITE)
(SITE / "cards").mkdir(parents=True, exist_ok=True)

for g in PUB:
    key = g["key"]
    cards = g.get("cards") or []
    for c in cards:
        if (ROOT / "data" / "cards" / c).exists():
            shutil.copy(ROOT / "data" / "cards" / c, SITE / "cards" / c)
    extra = {"x_post": g.get("x_url") or X_PROFILE, "_comp": g["comp"]}
    if len(cards) == 2:
        extra.update(card_win=f"../cards/{cards[0]}", card_lose=f"../cards/{cards[1]}")
    run("build.py", [key], 1, extra)
    t = re.search(r"<title>試合ページ（PC）(.*?)対(.*?)</title>", (TMP / f"{key}.pc.dc.html").read_text())
    cname = COMPS[g["comp"]]["name"]
    title = f"{t.group(1)} 対 {t.group(2)} の通信簿｜{cname}｜ベースボール通信簿"
    merge(f"{key}.pc.dc.html", f"{key}.sp.dc.html", SITE / "games" / f"{key}.html", title,
          f"{t.group(1)}対{t.group(2)}の全選手を10点満点で採点。勝利確率の推移と回ごとの貢献度も。")

run("rules.py", [], 0)
merge("Rules.dc.html", "RulesMobile.dc.html", SITE / "scoring.html", "採点のしくみ｜ベースボール通信簿",
      "ベースボール通信簿の採点方法。6.0点が及第点、勝利確率をどれだけ動かしたかで10点満点の点数をつけます。")
for cid, c in COMPS.items():
    if not any(g["comp"] == cid for g in PUB):
        continue
    depth = c["page"].count("/")
    run("top.py", ["tourney", cid], depth, {"_comp": cid})
    merge("Tourney.dc.html", "TourneyMobile.dc.html", SITE / c["page"], f"{c['name']}｜ベースボール通信簿",
          f"{c['name']}の全試合を、日付ごとに。全選手を10点満点で採点した通信簿の一覧です。")
run("privacy.py", [], 0)
merge("Privacy.dc.html", "PrivacyMobile.dc.html", SITE / "privacy.html", "プライバシーポリシー｜ベースボール通信簿",
      "ベースボール通信簿のプライバシーポリシー（アクセス解析と外部への情報送信について）。")
run("top.py", [], 0)
merge("Top.dc.html", "TopMobile.dc.html", SITE / "index.html", "ベースボール通信簿｜全試合、全選手の活躍を採点！",
      "野球の全試合・全選手を10点満点で採点する「通信簿」。打った・抑えただけでなく、その場面がどれだけ勝敗を動かしたかで点をつけます。")
print(f"{sum(1 for p in SITE.rglob('*') if p.is_file())} files -> {SITE}")
