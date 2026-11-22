"""トップページ（PC・スマホ）を、その日の採点データから作る。見た目はキャンバスのTOPラフと同じ。"""
import json
import os
import pathlib
import sys

_MODE = sys.argv[1] if len(sys.argv) > 1 else ""
_COMP_ID = sys.argv[2] if len(sys.argv) > 2 else ""
sys.argv = ["build.py", "__first__"]
import build as B  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import data as D  # noqa: E402

RED, INK, SUB, LINE = B.RED, B.INK, B.SUB, B.LINE
U = B.U
HERO = B.URLS.get("img_hero", "/_blob/01340370d7598e38f5362ee4eef17f9b")
COMP_ID = _COMP_ID or (D.published()[-1]["comp"] if D.published() else next(iter(D.COMPS)))
COMP = D.COMPS[COMP_ID]
TODAY = D.date_ja(D.today_date()) if D.today_date() else ""
TOURNEY_SHORT = COMP.get("short", "")
TODAY_GAMES = D.today_games()
HEROES = D.heroes()
BIG = D.big_play()
ARCHIVE = []
TOURNAMENT = D.tournament_status(COMP_ID)


def _period(c):
    s_, e_ = c["start"].split("-"), c["end"].split("-")
    return f"{s_[0]}.{s_[1]}.{s_[2]}〜{e_[1]}.{e_[2]}"


def h2(t, m, extra=""):
    return (f'<div style="position: relative; display: flex; align-items: center; gap: 12px"><h2 style="margin: 0; font-size: {24 if m else 30}px; font-weight: 900; color: #FFFFFF">'
            f'<span class="marker">{t}</span></h2>{extra}</div>')


def hand(v, size, col=RED):
    return f'<span class="hand" style="font-size: {size}px; color: {col}; line-height: 1">{v}</span>'


def hero_section(m):
    pad = "22px 20px 30px" if m else "56px 24px"
    stamp = (f'<div class="paper" style="position: relative; width: {340 if m else 420}px; max-width: 100%; box-sizing: border-box; padding: 18px 20px 14px; border-radius: 6px; transform: rotate(-3deg); box-shadow: 0 10px 24px rgba(0,0,0,0.35); display: flex; align-items: center; gap: 14px">'
             f'<span style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; flex: 1 1 auto">'
             + "".join(f'<span class="hand" style="font-size: {30 if m else 38}px; color: {RED}; border-bottom: 2px solid {RED}">{v}</span>' for v in ("6.5", "7.0", "8.5"))
             + f'</span><span style="position: relative; width: {64 if m else 78}px; height: {64 if m else 78}px; flex: none">{B.HANAMARU.format(w=64 if m else 78, t=0).replace("opacity: 0.35", "opacity: 1")}</span></div>')
    h1 = f'<h1 style="margin: 0; font-size: {30 if m else 52}px; font-weight: 900; line-height: 1.35; color: #FFFFFF; text-shadow: 0 3px 0 rgba(0,0,0,0.3)"><span class="marker">全試合、全選手の</span><br><span class="marker">活躍を採点！</span></h1>'
    lead = "<span style=\"display: inline-block\">スコアブックに残らない</span><span style=\"display: inline-block\">「効いた一打」を、点数に。</span><br><span style=\"display: inline-block\">試合ごとに、</span><span style=\"display: inline-block\">全選手の試合ごとの貢献度。</span>"
    if m:
        return f"""<section aria-label="ベースボール通信簿とは" style="background-color: #0E1E40">
    <div style="position: relative; height: 420px; background-image: url('{HERO}'); background-size: auto 100%; background-position: 100% center; background-repeat: no-repeat; border-bottom: 3px solid {RED}">
      <span aria-hidden="true" style="position: absolute; inset: 0; background-image: linear-gradient(180deg, rgba(11,26,54,0.8) 0, rgba(11,26,54,0) 32%, rgba(11,26,54,0) 62%, rgba(11,26,54,0.85) 100%)"></span>
      <div style="position: relative; height: 100%; box-sizing: border-box; padding: {pad}; display: flex; flex-direction: column; align-items: center; justify-content: space-between; text-align: center">{h1}{stamp}</div>
    </div>
    <div style="padding: 20px 20px 28px; text-align: center"><p style="margin: 0; font-size: 15px; font-weight: 500; color: #E6ECF6">{lead}</p></div>
  </section>"""
    return f"""<section aria-label="ベースボール通信簿とは" style="position: relative; overflow: hidden; background-color: #0E1E40; background-image: url('{HERO}'); background-size: cover; background-position: right center">
    <span aria-hidden="true" style="position: absolute; inset: 0; background-image: linear-gradient(90deg, rgba(11,26,54,0.85) 0, rgba(11,26,54,0.55) 38%, rgba(11,26,54,0) 62%)"></span>
    <div style="position: relative; max-width: 1120px; margin: 0 auto; padding: {pad}; display: flex; flex-direction: column; align-items: flex-start; gap: 22px; min-height: 400px; justify-content: center">
      {h1}<p style="margin: 0; max-width: 560px; font-size: 18px; font-weight: 500; color: #E6ECF6">{lead}</p>{stamp}
    </div>
  </section>"""


def game_cards(m):
    out = []
    for div, card, state, fm, pm, link in TODAY_GAMES:
        rows = []
        if fm or pm:
            for lab, v in (("野手MVP", fm), ("投手MVP", pm)):
                right = (f'<span>{v[0]}</span>{hand(f"{v[1]:.1f}", 26)}' if v else f'<span style="color: {SUB}">該当者なし</span>')
                rows.append(f'<span style="display: flex; align-items: baseline; justify-content: space-between; gap: 8px; font-size: 14px"><span style="font-weight: 700">{lab}</span><span style="display: flex; align-items: baseline; gap: 8px">{right}</span></span>')
        else:
            rows.append(f'<span style="display: flex; justify-content: space-between; font-size: 14px"><span style="font-weight: 700">通信簿</span><span style="color: {SUB}">試合終了後に公開</span></span>')
        tag = "a" if link else "div"
        href = f' href="{U(link)}"' if link else ""
        out.append(f'<{tag}{href} class="paper" style="display: flex; flex-direction: column; gap: 10px; padding: 16px 18px; border-radius: 8px; text-decoration: none; color: {INK}; box-shadow: 0 6px 0 rgba(0,0,0,0.25)">'
                   f'<span style="display: flex; justify-content: space-between; gap: 8px; font-size: 12px; font-weight: 700"><span style="color: {SUB}">{div}</span><span style="color: {RED}">{state}</span></span>'
                   f'<span style="font-size: {19 if m else 20}px; font-weight: 900; line-height: 1.3">{card}</span>'
                   f'<span style="display: flex; flex-direction: column; gap: 4px; border-top: 2px dashed {LINE}; padding-top: 8px">{"".join(rows)}</span></{tag}>')
    cols = "1fr" if m else "repeat(auto-fit, minmax(240px, 1fr))"
    return f'<div style="display: grid; grid-template-columns: {cols}; gap: 16px">{"".join(out)}</div>'


def hero_card(h, m):
    img = B.BATTER if h["img"] == "batter" else B.PITCHER
    over = h["raw"] > 10
    badge = (f'<span style="font-size: 11px; font-weight: 900; color: #FFFFFF; background-color: {RED}; padding: 2px 10px; border-radius: 999px; position: relative">上限突破！ {h["raw"]:.1f}</span>' if over else "")
    flower = B.HANAMARU.format(w=84 if m else 104, t=-12) if h["score"] >= 9.5 else ""
    return f"""<div class="paper" style="display: flex; flex-direction: column; gap: 10px; padding: 16px 18px; border-radius: 8px; box-shadow: 0 6px 0 rgba(0,0,0,0.25); color: {INK}">
            <div style="display: flex; align-items: center; gap: {12 if m else 18}px">
              <img src="{img}" alt="" aria-hidden="true" style="width: {72 if m else 96}px; height: auto; flex: none">
              <span style="flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 2px">
                <span style="font-size: 13px; font-weight: 900; color: {RED}">{h['kind']}</span>
                <span style="font-size: {24 if m else 28}px; font-weight: 900; line-height: 1.25">{h['name']}</span>
                <span style="font-size: 13px; color: {SUB}">{h['meta']}</span>
                <span style="font-size: 13px; font-weight: 700">{h['play']}</span>
              </span>
              <span style="display: flex; flex-direction: column; align-items: center; gap: 2px; flex: none; position: relative; min-width: {84 if m else 104}px">
                {flower}{hand(f"{h['score']:.1f}", 44 if m else 56)}{badge}
              </span>
            </div>
            <a href="{U(h['link'])}" style="font-size: 13px; font-weight: 700; border-top: 2px dashed {LINE}; padding-top: 8px">出典：{h['src']} の通信簿 →</a>
          </div>"""


def heroes(m):
    blocks = []
    for div, hs in HEROES.items():
        head = (f'<h3 style="margin: 0; display: flex; align-items: center; gap: 10px; font-size: 17px; font-weight: 900; color: #FFFFFF">'
                f'<span style="width: 10px; height: 10px; background-color: {RED}; transform: rotate(45deg); flex: none"></span>{div}</h3>')
        if hs:
            body = "".join(hero_card(h, m) for h in hs)
        else:
            body = (f'<div class="paper" style="padding: 18px; border-radius: 8px; color: {INK}; font-size: 14px; box-shadow: 0 6px 0 rgba(0,0,0,0.25)">'
                    f'今日の試合の採点が終わりしだい、ここに出します。</div>')
        cols = "1fr" if m else "repeat(auto-fit, minmax(320px, 1fr))"
        blocks.append(f'<div style="display: flex; flex-direction: column; gap: 12px">{head}<div style="display: grid; grid-template-columns: {cols}; gap: 14px">{body}</div></div>')
    tip = (f'<details style="position: relative"><summary aria-label="今日のヒーローの選び方" style="list-style: none; width: 32px; height: 32px; border-radius: 999px; border: 2px solid #FFFFFF; '
           f'color: #FFFFFF; font-weight: 900; display: flex; align-items: center; justify-content: center; cursor: pointer">?</summary>'
           f'<div class="paper" style="position: absolute; top: 40px; left: 0; z-index: 10; width: min(440px, 80vw); box-sizing: border-box; padding: 16px 18px; color: {INK}; border-radius: 8px; font-size: 14px; line-height: 2; box-shadow: 0 10px 24px rgba(0,0,0,0.4); border-top: 4px solid {RED}">'
           f'<b style="display: block">今日のヒーローの選び方</b>その日の試合の通信簿から、<b>高校の部・大学の部それぞれ</b>でいちばん点の高い野手と投手を選んでいます。<br>'
           f'・野手は、両チームの打者全員が対象<br>・投手は、7.0点以上の選手がいるときだけ<br>・同点は、丸める前の点数で決定</div></details>')
    return f'<section aria-label="今日のヒーロー" style="display: flex; flex-direction: column; gap: 18px">{h2("今日のヒーロー", m, tip)}{"".join(blocks)}</section>'


def big_play(m):
    b = BIG
    if not b:
        return ""
    return f"""<section aria-label="今日いちばん試合を動かしたプレー" style="display: flex; flex-direction: column; gap: 18px">
      {h2('試合を動かしたプレー' if m else '今日いちばん試合を動かしたプレー', m)}
      <a href="{U(b['link'])}" style="display: flex; flex-direction: column; gap: 14px; padding: {18 if m else 26}px; background-color: #0A1222; border: 6px solid #3D5C93; border-radius: 10px; text-decoration: none; color: #FFFFFF">
        <span style="font-size: 13px; color: #9FB3D6">{b['game']}</span>
        <span style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px">
          <span style="font-size: {20 if m else 26}px; font-weight: 900">{b['title']}</span>
          <span style="font-size: {44 if m else 60}px; font-weight: 900; color: #FFD23F">+{b['delta']}%</span>
        </span>
        <span style="display: flex; flex-direction: column; gap: 6px">
          <span style="display: flex; justify-content: space-between; font-size: 13px; color: #C9D6EA"><span>{b['team']}の勝利確率</span><span>{b['before']}% → {b['after']}%</span></span>
          <span style="position: relative; display: block; height: 14px; background-color: #1C2A44; border-radius: 3px; overflow: hidden">
            <span style="position: absolute; left: 0; top: 0; bottom: 0; width: {b['before']}%; background-color: #5C7FBA"></span>
            <span style="position: absolute; left: {b['before']}%; top: 0; bottom: 0; width: {b['delta']}%; background-color: #FFD23F"></span>
          </span>
        </span>
      </a>
    </section>"""


def tournament(m):
    cards = TOURNAMENT
    body = "".join(f'<div class="paper" style="display: flex; flex-direction: column; gap: 6px; padding: 16px 18px; border-radius: 8px; color: {INK}; box-shadow: 0 6px 0 rgba(0,0,0,0.25)">'
                   f'<span style="font-size: 19px; font-weight: 900">{a}</span><span style="font-size: 13px">{b}</span><span style="font-size: 13px; color: {SUB}">{c}</span></div>' for a, b, c in cards)
    cols = "1fr" if m else "repeat(auto-fit, minmax(280px, 1fr))"
    return f"""<section id="tournament" aria-label="開催中の大会" style="display: flex; flex-direction: column; gap: 18px">
      {h2('開催中の大会', m)}
      <div style="display: flex; flex-direction: column; gap: 4px"><span style="font-size: {22 if m else 26}px; font-weight: 900">{COMP['name']}</span>
        <span style="font-size: 13px; color: #9FB3D6">{COMP['formal']}　{_period(COMP)[5:]}　{COMP['venue']}</span></div>
      <div style="display: grid; grid-template-columns: {cols}; gap: 14px">{body}</div>
      <a href="{U('tournament')}" style="align-self: flex-start; font-size: 14px; font-weight: 700; color: #F3B7BA">{COMP['name']} のページへ（全試合の結果）→</a>
    </section>"""


def about(m):
    items = [("0.5点刻みの10点満点", "6.0点が及第点。上限は10点ですが、加点で10点を超えたときは、その点数も記載します。"),
             ("勝利確率をどれだけ動かしたか", "同じヒットでも、終盤の同点の場面ほど点が大きく動きます。"),
             ("ファインプレーや好走塁も", "ファインプレーや好走塁も、わかれば評価に加えます。")]
    body = "".join(f'<div class="paper" style="display: flex; flex-direction: column; gap: 6px; padding: 16px 18px; border-radius: 8px; color: {INK}; box-shadow: 0 6px 0 rgba(0,0,0,0.25)">'
                   f'<span style="display: flex; align-items: center; gap: 10px">{hand(i + 1, 36)}<span style="font-size: 17px; font-weight: 900">{t}</span></span>'
                   f'<span style="font-size: 13px; line-height: 1.9">{d}</span></div>' for i, (t, d) in enumerate(items))
    cols = "1fr" if m else "repeat(3, minmax(0, 1fr))"
    return f"""<section id="about" aria-label="採点のしくみ" style="display: flex; flex-direction: column; gap: 18px">
      {h2('採点のしくみ', m)}
      <div style="display: grid; grid-template-columns: {cols}; gap: 14px">{body}</div>
      <a href="{U('rules')}" style="align-self: flex-start; font-size: 14px; font-weight: 700; color: #F3B7BA">くわしい採点のしくみへ →</a>
    </section>"""


def archive(m):
    blocks = []
    for day, games in ARCHIVE:
        links = "".join(f'<a href="{U(k)}" style="display: flex; justify-content: space-between; gap: 10px; padding: 10px 0; border-bottom: 1px solid #24427A; color: #FFFFFF; text-decoration: none">'
                        f'<span style="font-size: 12px; color: #9FB3D6; flex: none; width: {96 if m else 130}px">{d}</span><span style="flex: 1 1 auto; font-weight: 700">{c}</span><span style="color: #F3B7BA">→</span></a>' for d, c, k in games)
        blocks.append(f'<div style="display: flex; flex-direction: column"><h3 style="margin: 0 0 4px; font-size: 16px; font-weight: 900; color: #FFFFFF">{day}</h3>{links}</div>')
    cols = "1fr" if m else "repeat(2, minmax(0, 1fr))"
    return f"""<section id="archive" aria-label="日付ごとの試合" style="display: flex; flex-direction: column; gap: 14px">
      {h2('日付ごとの試合', m)}
      <div style="display: grid; grid-template-columns: {cols}; gap: 24px">{''.join(blocks)}</div>
    </section>"""


def page(m):
    gap = 44 if m else 60
    return f"""<div style="min-height: 100vh; background-color: #0B1A36; background-image: radial-gradient(circle at 50% 0, #1A3260 0, #0B1A36 60%); color: #FFFFFF; font-family: 'Noto Sans JP', sans-serif; line-height: 1.6">
{B.header(m)}  {hero_section(m)}
  <main style="max-width: 1120px; margin: 0 auto; padding: {'28px 16px 56px' if m else '48px 24px 72px'}; display: flex; flex-direction: column; gap: {gap}px">
    <section aria-label="今日の試合" style="display: flex; flex-direction: column; gap: 18px">
      {h2('今日の試合', m)}<div style="display: flex; flex-direction: column; gap: 2px"><span style="font-size: {17 if m else 19}px; font-weight: 900; color: #FFFFFF">{TOURNEY_SHORT}</span><span style="font-size: 14px; font-weight: 700; color: #F3B7BA">{TODAY}</span></div>
      {game_cards(m)}
    </section>
    {heroes(m)}
    {big_play(m)}
    {tournament(m)}
    {about(m)}
  </main>
{B.footer(m)}</div>
"""


DIV_INFO = D.div_info(COMP_ID)
DAYS = D.days(COMP_ID)


def tourney_page(m):
    gap = 44 if m else 60
    n = sum(len(gs) for _, divs in DAYS for _, gs in divs)
    crumbs = (f'<a href="{U("top")}" style="color: #C9D6EA; text-decoration: none">トップ</a> <span style="color: #5C7FBA">›</span> <span style="color: #FFFFFF">{COMP["name"]}</span>')
    facts = [("会期", _period(COMP)), ("会場", COMP["venue"]), ("採点した試合", f"{n}試合")]
    chips = "".join(f'<span style="display: flex; flex-direction: column; padding: {"10px 14px" if m else "12px 20px"}; border-radius: 8px; background-color: rgba(255,255,255,0.06); border: 1px solid #3D5C93">'
                    f'<span style="font-size: 11px; font-weight: 700; color: #9FB3D6; letter-spacing: 0.08em">{k}</span><span style="font-size: {16 if m else 19}px; font-weight: 900">{v}</span></span>' for k, v in facts)
    hero = f"""<section aria-label="大会の概要" style="position: relative; overflow: hidden; border-radius: 12px; padding: {'24px 18px' if m else '40px 44px'}; background-color: #0E2147; background-image: linear-gradient(135deg, #14306A 0%, #0B1A36 70%); border: 2px solid #3D5C93; box-shadow: 0 10px 0 rgba(0,0,0,0.25)">
      <div aria-hidden="true" style="position: absolute; right: -40px; top: -40px; width: 220px; height: 220px; border-radius: 999px; border: 18px solid rgba(215,38,46,0.18)"></div>
      <div aria-hidden="true" style="position: absolute; right: 40px; bottom: -60px; width: 160px; height: 160px; border-radius: 999px; border: 12px solid rgba(255,210,63,0.12)"></div>
      <div style="position: relative; display: flex; flex-direction: column; gap: 12px">
        <span style="align-self: flex-start; font-size: 12px; font-weight: 900; color: #FFFFFF; background-color: {RED}; padding: 3px 12px; border-radius: 999px; letter-spacing: 0.06em">開催中</span>
        <h1 style="margin: 0; font-size: {32 if m else 48}px; font-weight: 900; line-height: 1.25"><span class="marker">{COMP["name"]}</span></h1>
        <p style="margin: 0; font-size: {13 if m else 15}px; font-weight: 700; color: #C9D6EA">{COMP["formal"].replace(" ", "　")}</p>
        <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-top: 4px">{chips}</div>
        <p style="margin: 6px 0 0; font-size: {14 if m else 15}px; line-height: 1.9; color: #E6ECF6">高校の部・大学の部の全試合で、出場した全選手に10点満点の通信簿をつけています。</p>
      </div>
    </section>"""

    def div_block(name, summary, leaders):
        lc = "".join(f"""<div class="paper" style="display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 8px; color: {INK}; box-shadow: 0 4px 0 rgba(0,0,0,0.25)">
            <span class="hand" style="flex: none; width: 34px; font-size: 30px; color: {RED}; line-height: 1; text-align: center">{i + 1}</span>
            <span style="flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column">
              <span style="font-size: {17 if m else 19}px; font-weight: 900">{nm}<span style="font-size: 13px; font-weight: 700; color: {SUB}">（{gp}）</span></span>
              <span style="font-size: 13px; color: {SUB}">{tm}　{len(sc)}試合の採点：{"／".join(f"{v:.1f}" + ("（上限突破）" if v > 10 else "") for v in sc)}</span>
            </span>
            <span style="flex: none; display: flex; flex-direction: column; align-items: flex-end"><span style="font-size: 10px; font-weight: 900; color: {SUB}">大会通算</span><span class="hand" style="font-size: 28px; color: {RED}; line-height: 1">+{pt:.1f}</span></span>
          </div>""" for i, (nm, gp, tm, pt, sc) in enumerate(leaders))
        cols = "1fr"
        return f"""<div style="display: flex; flex-direction: column; gap: 12px">
          <h3 style="margin: 0; font-size: {20 if m else 22}px; font-weight: 900; padding-left: 12px; border-left: 6px solid {RED}">{name}</h3>
          <p style="margin: 0; font-size: {14 if m else 15}px; line-height: 1.95; color: #E6ECF6">{summary}</p>
          <span style="font-size: 13px; font-weight: 900; color: #F3B7BA; margin-top: 4px">ここまでの活躍選手</span>
          <div style="display: grid; grid-template-columns: {cols}; gap: 12px">{lc}</div>
        </div>"""
    divs = "".join(div_block(*d) for d in DIV_INFO)
    note = '<p style="margin: 0; font-size: 12px; color: #9FB3D6">「大会通算」は、各試合の採点から及第点の6.0点を引いた分の合計です。10点を超えた「上限突破」の分も数えます（例：11.5点と7.0点なら ＋5.5＋1.0＝＋6.5）。同点のときは、勝利確率を多く動かした選手を上にしています。</p>'

    def game_row(rnd, res, key, cm):
        return f"""<a href="{U('game:' + key)}" style="display: flex; align-items: center; gap: 14px; padding: {'12px 0' if m else '14px 4px'}; border-bottom: 1px solid #24427A; color: #FFFFFF; text-decoration: none">
            <span style="flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 3px">
              <span style="display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px"><span style="font-size: 12px; color: #9FB3D6">{rnd}</span><span style="font-size: {16 if m else 18}px; font-weight: 900">{res}</span></span>
              <span style="font-size: {13 if m else 14}px; line-height: 1.7; color: #C9D6EA">{cm}</span>
            </span>
            <span style="flex: none; color: #F3B7BA; font-weight: 900">→</span></a>"""
    days = ""
    for day, dv in DAYS:
        inner = ""
        for dname, games in dv:
            inner += (f'<div style="display: flex; flex-direction: column"><span style="align-self: flex-start; font-size: 12px; font-weight: 900; color: {INK}; background-color: #F3B7BA; padding: 2px 10px; border-radius: 4px; margin: 8px 0 2px">{dname}</span>'
                      + "".join(game_row(*g) for g in games) + "</div>")
        days += f"""<div style="display: flex; flex-direction: column; gap: 4px">
          <h3 style="margin: 0; font-size: {18 if m else 20}px; font-weight: 900; color: #FFFFFF; display: flex; align-items: center; gap: 10px"><span style="display: inline-block; width: 10px; height: 10px; border-radius: 999px; background-color: {RED}"></span>{day}</h3>
          {inner}
        </div>"""
    return f"""<div style="min-height: 100vh; background-color: #0B1A36; background-image: radial-gradient(circle at 50% 0, #1A3260 0, #0B1A36 60%); color: #FFFFFF; font-family: 'Noto Sans JP', sans-serif; line-height: 1.6">
{B.header(m)}  <main style="max-width: 1120px; margin: 0 auto; padding: {'18px 16px 56px' if m else '24px 24px 72px'}; display: flex; flex-direction: column; gap: {gap}px">
    <div style="display: flex; flex-direction: column; gap: 14px"><nav aria-label="パンくずリスト" style="font-size: 13px">{crumbs}</nav>{hero}</div>
    <section aria-label="部ごとの状況" style="display: flex; flex-direction: column; gap: 36px">{h2('大会の状況', m)}{divs}{note}
      <a href="{U('players')}" style="align-self: flex-start; display: inline-flex; align-items: center; gap: 10px; padding: 14px 22px; border-radius: 999px; background-color: {RED}; color: #FFFFFF; text-decoration: none; font-weight: 900; font-size: {16 if m else 18}px">選手一覧（大学の部・高校の部）を見る →</a></section>
    <section id="archive" aria-label="日付ごとの試合" style="display: flex; flex-direction: column; gap: 28px">{h2('日付ごとの試合', m)}{days}</section>
    <a href="{U('rules')}" style="align-self: flex-start; font-size: 14px; font-weight: 700; color: #F3B7BA">採点のしくみ →</a>
  </main>
{B.footer(m)}</div>
"""


if _MODE == "tourney":
    out = pathlib.Path(os.environ.get("OUT", "/tmp/brc-build"))
    (out / "Tourney.dc.html").write_text(B.HEAD.format(title=COMP["name"]) + tourney_page(False) + B.TAIL.format(w=1280, h=2400))
    (out / "TourneyMobile.dc.html").write_text(B.HEAD.format(title=COMP["name"]) + tourney_page(True) + B.TAIL.format(w=390, h=3600))
    print("tourney ok")
    raise SystemExit
out = pathlib.Path(os.environ.get("OUT", "/tmp/brc-build"))
(out / "Top.dc.html").write_text(B.HEAD.format(title="ベースボール通信簿") + page(False) + B.TAIL.format(w=1280, h=3600))
(out / "TopMobile.dc.html").write_text(B.HEAD.format(title="ベースボール通信簿") + page(True) + B.TAIL.format(w=390, h=5200))
print("top ok")
