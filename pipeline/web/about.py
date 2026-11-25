"""「ベースボール通信簿について」（PC・スマホ）。"""
import os
import pathlib
import sys

sys.argv = ["build.py", "__first__"]
import build as B  # noqa: E402

RED, U = B.RED, B.U
PAPER, CARD, INK, INK2, MUTED, NAVY, LINE = "#F6F1E4", "#FFFDF7", "#222831", "#3D4552", "#5B6270", "#1F2D4D", "#CFC4A8"

WHY = [
    ("野球が生活の一部だった", [
        "私は1977年、広島に生まれました。小学生のころのカープは黄金時代で、山本浩二さん、衣笠祥雄さん、高橋慶彦さんがグラウンドを駆けていました。友だちはみんな赤いCの帽子をかぶり、遊びといえば鬼ごっこか、ドッジボールか、野球。野球は、生活の一部でした。",
    ]),
    ("派手な一打の陰で", [
        "長く野球を見てきて、ずっと引っかかっていたことがあります。試合の印象は、どうしても派手な一打に引っぱられてしまうことです。",
        "逆転のサヨナラ満塁ホームランや、先発の完封は、誰の記憶にも残ります。でも、抑えや中継ぎのピッチャーは「抑えて当然」と見られ、打たれたときだけ責められがちです。反対に、チャンスで3度ゲッツーを打った選手が、5-1と大きくリードした場面で気楽な3ランを打っただけで、それまでのミスが帳消しになったように見えることもあります。",
        "本当にその試合の勝利に貢献したのは誰だったのか。それを、もっと平等に、数字で見てみたいと思いました。",
    ]),
    ("サッカーにあって、野球にないもの", [
        "野球には、打率やOPS、WARなど、優れた指標がたくさんあります。ただ、その多くは1年間やある期間を通した成績です。「今日のこの1試合で、出場した全員がどれだけ働いたか」を点数で示すものは、ほとんどありません。サッカーでは、試合ごとに全選手へ点数がつくのが当たり前です。サッカーにあるのに野球にないのはもったいない。そう思ったのが、この通信簿の始まりです。",
    ]),
    ("チームの中での働きも見える場所に", [
        "もちろん、野球は一人で戦うスポーツではありません。送りバントや進塁打のように、チームの中で役割を果たすことも大切です。そうした働きも含めて、「この試合、この選手はどうだったか」が分かる場所をつくりたいと考えています。",
    ]),
    ("目立たないヒーローを見つけたい", [
        "試合ごとの点数を積み重ねていくと、ヒーローインタビューにも呼ばれず、タイトルにも縁がないのに、毎試合しっかり6.5点、7点を取り続けて勝利を支えている選手が見えてくるはずです。特にアマチュアの選手にとって、「自分はちゃんとチームに貢献している」と分かるものになれば、こんなにうれしいことはありません。",
    ]),
    ("まずは一試合ずつ", [
        "今はまだ個人の取り組みなので、守備範囲まで細かく測ることはできません。いつかは全試合の映像を分析して、すべてのプレーを数字にしてみたい。その第一歩として、まずは一試合ずつ、全選手に通信簿を届けていきます。",
    ]),
]

WANT = [
    ("全試合・全選手を通信簿形式で採点", "派手な一打だけでなく、出場した全選手を毎試合採点し続けます（予算の続く限り）。"),
    ("対象を広げていく", "今は日本の主な野球を対象にしていますが、WBCやオリンピックのような国際大会にも広げていけたらと思っています。"),
    ("1試合ごとではなく、通算の勝利貢献選手も見つける", "試合ごとの点数を積み重ねて、タイトルには縁がなくても勝利を支えた選手を紹介します。"),
    ("将来は映像で全プレーを測りたい", "守備範囲や好プレー、好走塁なども、ゆくゆくは数値化していきたいと考えています。協力者募集中です。"),
]

TARGETS = [
    ("プロ野球", "セ・パ両リーグの公式戦、交流戦、クライマックスシリーズ、日本シリーズ"),
    ("大学野球", "東京六大学、東都大学1部、全日本大学野球選手権、明治神宮大会"),
    ("高校野球", "春と夏の甲子園、明治神宮大会"),
    ("国際大会", "WBC、オリンピック"),
]

CARE = [
    ("選手をけなすための点数ではありません", "目立たない貢献にも光を当てるための採点です。低い点も、その試合の一場面を数字にしたものにすぎません。"),
    ("点数は独自の計算による参考値です", "MLBなどでも使われている「WPA（勝利確率の変化）」という考え方をもとに、独自のルールで点数に直しています。公式記録とは別のものです。"),
    ("学生野球の選手は、記録として扱います", "高校生・大学生の選手については、試合の記録の範囲で紹介します。"),
]


def h2(t, m):
    return (f'<h2 style="margin: 0 0 14px; font-size: {22 if m else 28}px; font-weight: 800; color: {NAVY}">'
            f'<span class="marker">{t}</span></h2>')


def img(name, size):
    return f'<img src="{B.img_url(name)}" alt="" aria-hidden="true" style="width: {size}px; height: {size}px; flex: none">'


def page(m):
    fs, lh = (15, 1.95) if m else (16, 2.0)
    why = "".join(
        f'<h3 style="margin: {22 if i else 4}px 0 8px; font-size: {17 if m else 19}px; font-weight: 800; color: {NAVY}; padding-left: 10px; border-left: 4px solid {RED}">{h}</h3>'
        + "".join(f'<p style="margin: 0 0 10px; font-size: {fs}px; line-height: {lh}; color: {INK}">{p}</p>' for p in ps)
        for i, (h, ps) in enumerate(WHY))
    why += f'<p style="margin: 18px 0 0; text-align: right; font-size: {fs}px; color: {INK2}">――ベースボール通信簿　担任</p>'

    def items(rows, numbered=False):
        return "".join(
            f'<div style="display: flex; gap: 14px; padding: 14px 0; border-bottom: 1px solid #D6DEE8">'
            + (f'<span class="hand" style="font-size: 26px; color: {RED}; line-height: 1.2; flex: none; width: 22px">{i + 1}</span>' if numbered else "")
            + f'<span style="display: flex; flex-direction: column; gap: 4px"><b style="font-size: {16 if m else 17}px; color: {NAVY}">{t}</b>'
              f'<span style="font-size: {14 if m else 15}px; line-height: 1.85; color: {INK2}">{d}</span></span></div>'
            for i, (t, d) in enumerate(rows))

    targets = "".join(
        f'<div style="display: grid; grid-template-columns: {"88px" if m else "120px"} 1fr; gap: 12px; padding: 12px 0; border-bottom: 1px solid #D6DEE8; font-size: {14 if m else 15}px">'
        f'<b style="color: {NAVY}">{k}</b><span style="color: {INK2}; line-height: 1.8">{v}</span></div>' for k, v in TARGETS)

    read = (
        f'<div style="display: flex; flex-direction: column; gap: 14px; font-size: {14 if m else 15}px; line-height: 1.85; color: {INK2}">'
        f'<div style="display: flex; gap: 12px; align-items: flex-start"><span class="hand" style="font-size: 30px; color: {RED}; line-height: 1; flex: none; width: 54px">6.0</span>'
        f'<span><b style="color: {NAVY}">10点満点で、6.0点が及第点</b><br>勝利確率をどれだけ動かしたかで採点します。</span></div>'
        f'<div style="display: flex; gap: 12px; align-items: flex-start"><span style="display: flex; gap: 2px; flex: none; width: 54px">{img("hanamaru", 30)}</span>'
        f'<span><b style="color: {NAVY}">花丸は8.5点以上</b><br>その試合で特に光った選手です。顔マークは、7.0点以上がにっこり {img("face-good", 18)}、6.0〜6.5点がふつう {img("face-ok", 18)}、6.0点未満がこまり顔 {img("face-bad", 18)} です。</span></div>'
        f'<div style="display: flex; gap: 12px; align-items: flex-start"><span style="display: flex; gap: 2px; flex: none; width: 54px">{img("mvp", 26)}{img("kanto", 26)}</span>'
        f'<span><b style="color: {NAVY}">MVPと敢闘賞</b><br>勝ったチームの7.0点以上から野手と投手のMVPを、負けたチームの8.0点以上から敢闘賞を選びます。</span></div>'
        f'<a href="{U("rules")}" style="font-weight: 700; color: {RED}">くわしい計算は「採点のしくみ」へ →</a></div>')

    ops = (f'<div style="display: flex; flex-direction: column; gap: 12px; font-size: {14 if m else 15}px; line-height: 1.85; color: {INK2}">'
           f'<div><b style="color: {NAVY}">運営</b><br>ベースボール通信簿（担任）。ご意見やご連絡は、Xの公式アカウント <a href="https://x.com/BaseBalltannin" style="color: {RED}; font-weight: 700">@BaseBalltannin</a> までお願いします。</div>'
           f'<div><b style="color: {NAVY}">更新のタイミング</b><br>基本的には、試合終了から2時間程度で自動更新できるようにしています。プロ野球はその日のうちに、そのほかのトーナメント式の大会は、その日の22時までの更新を目標にしています。</div></div>')

    sheet = f"background-color: {CARD}; border: 1px solid {LINE}; box-shadow: 4px 4px 0 #E8DFC9; padding: {'20px 18px' if m else '32px 40px'}"
    sec = lambda t, body: f'<section aria-label="{t}">{h2(t, m)}<div style="{sheet}">{body}</div></section>'  # noqa: E731
    wrap = "width: 390px; " if m else ""
    crumbs = f'<nav aria-label="パンくずリスト" style="font-size: 13px; color: {MUTED}"><a href="{U("top")}" style="color: {MUTED}">トップ</a> › ベースボール通信簿について</nav>'
    return f"""<div style="{wrap}min-height: 100vh; background-color: #0B1A36; color: #FFFFFF; font-family: 'Noto Sans JP', sans-serif; line-height: 1.6">
{B.header(m)}  <main style="max-width: 860px; margin: 0 auto; padding: {'18px 16px 56px' if m else '24px 24px 80px'}; display: flex; flex-direction: column; gap: {36 if m else 48}px">
    <div style="display: flex; flex-direction: column; gap: 12px">{crumbs}
      <h1 style="margin: 0; font-size: {28 if m else 40}px; font-weight: 800; color: {NAVY}">ベースボール通信簿について</h1>
      <p style="margin: 0; font-size: {15 if m else 17}px; line-height: 1.9; color: {INK2}">野球の試合ごとに、出場した全選手を10点満点で採点する「通信簿」をお届けしています。</p></div>
    {sec("なぜ「ベースボール通信簿」を作ったのか", why)}
    {sec("やりたいこと", items(WANT, numbered=True))}
    {sec("対象とする試合", targets)}
    {sec("通信簿の読み方", read)}
    {sec("大事にしていること", items(CARE))}
    {sec("運営と更新のタイミング", ops)}
  </main>
{B.footer(m)}</div>
"""


out = pathlib.Path(os.environ.get("OUT", "/tmp/brc-build"))
(out / "About.dc.html").write_text(B.HEAD.format(title="ベースボール通信簿について") + page(False) + B.TAIL.format(w=1280, h=4200))
(out / "AboutMobile.dc.html").write_text(B.HEAD.format(title="ベースボール通信簿について") + page(True) + B.TAIL.format(w=390, h=6400))
print("about ok")
