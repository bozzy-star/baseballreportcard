"""採点のしくみページ（PC・スマホ）。見た目の部品は build.py と共通。"""
import os
import pathlib
import sys

sys.argv = ["build.py", "__first__"]
import build as B  # noqa: E402  （試合ページの部品を流用。読み込み時に試合ページも作り直される）

RED, INK, SUB, LINE = B.RED, B.INK, B.SUB, B.LINE


def card(inner, mobile, extra="", id_=""):
    return f'<div{f' id="{id_}"' if id_ else ''} class="sheet" style="padding: {"16px" if mobile else "22px 24px"}; border-radius: 8px; color: {INK}; box-shadow: 0 6px 0 rgba(0,0,0,0.25); border-top: 6px solid {RED}{extra}">{inner}</div>'


def h3(t, mobile):
    return f'<h3 style="margin: 0 0 8px; font-size: {18 if mobile else 20}px; font-weight: 900">{t}</h3>'


def p(t, mobile, extra=""):
    return f'<p style="margin: 0; font-size: {14 if mobile else 15}px; line-height: 2{extra}">{t}</p>'


def scale(mobile):
    # (範囲, 一言, どんな選手か, 勝利確率の目安, 出現率, 色見本)
    bands = [("8.5〜", "試合を決めた", "たいへんよくできました", "その試合の勝ち負けを決めた選手。くわしくは下の「8.5点以上はこんな選手」へ。", "＋19%〜", "約7%", "9.0"),
             ("7.0〜8.0", "勝利に貢献した", "よくできました", "勝ちに大きく貢献した選手。先制や中押しのタイムリー、先発としてしっかり試合を作った投球など。MVPの基準もここからです。", "＋6〜19%", "約15%", "7.5"),
             ("6.0〜6.5", "役目を果たした", "できました", "役目は果たした選手。大きな失敗がなく、勝負どころで少しプラスを積んだ。点差が開いた場面のヒットもここに入りやすいです。", "−2〜＋6%", "約39%", "6.0"),
             ("5.0〜5.5", "あと一歩でした", "あと一歩", "あと一歩だった選手。チャンスであと一本が出なかったり、終盤に失点したりして、勝利確率を少し相手に渡しました。", "−10〜−2%", "約26%", "5.0"),
             ("〜4.5", "今日は試練の日", "今日は試練の日", "大きく流れを渡した選手。勝負どころでの併殺打、逆転を許す被打、決勝点につながるエラーなど。", "−10%〜", "約14%", "4.0")]
    rows = ""
    for rng, word_w, word_l, who, w, freq, sample in bands:
        mark = (f'<img src="{B.img_url("hanamaru")}" alt="花丸" style="width: 26px; height: 26px; vertical-align: middle">' if float(sample) >= 8.5 else "") + B.face(float(sample), 24)
        word = (f'<span style="display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px">{mark}'
                f'<span><span style="font-size: 11px; font-weight: 700; color: {SUB}">勝ったチーム</span> {word_w}</span>'
                + (f'<span><span style="font-size: 11px; font-weight: 700; color: {SUB}">負けたチーム</span> {word_l}</span>' if word_l != word_w else "") + '</span>')
        col = RED if float(sample) >= 6 else "#3D5C93"
        tag = lambda t: f'<span style="font-size: 12px; font-weight: 700; color: {SUB}; border: 1px solid {LINE}; border-radius: 999px; padding: 1px 10px; white-space: nowrap">{t}</span>'
        rows += f"""<div style="display: flex; align-items: flex-start; gap: {12 if mobile else 18}px; padding: 14px 0; border-bottom: 1px solid {LINE}">
          <span class="hand" style="font-size: {24 if mobile else 36}px; color: {col}; line-height: 1.1; width: {96 if mobile else 190}px; flex: none; white-space: nowrap">{rng}</span>
          <span style="display: flex; flex-direction: column; gap: 4px; min-width: 0"><span style="font-size: {15 if mobile else 17}px; font-weight: 900">{word}</span>
            <span style="font-size: {13 if mobile else 14}px; line-height: 1.8">{who}</span>
            <span style="display: flex; flex-wrap: wrap; gap: 6px">{tag("勝利確率 " + w)}{tag("出る割合 " + freq)}</span></span>
        </div>"""
    return card(h3("点数の目安", mobile) + p("6.0点が及第点です。0.5点刻みで、上限は10点。下限はありません。点数の帯ごとに呼び名と顔マークがあり、担任からの一言の書き出しになります。呼び名は、勝ったチームと負けたチームで変わります。", mobile)
                + f'<div style="margin-top: 8px">{rows}</div>'
                + p("「勝利確率」は、その選手が試合を通して動かした勝利確率の合計の目安です（ファインプレー・好走塁の加点を除く）。「出る割合」は明治神宮大会2026の12試合・のべ327人の採点から出しています。", mobile, f"; margin-top: 12px; font-size: 13px; color: {SUB}"),
                mobile, id_="r-scale")


TOP_TIERS = [
    ("10.0", "満点", "＋31%〜", "1試合に1人出るかどうか（約2%）",
     "ひとりで試合をひっくり返した選手です。終盤の同点打やサヨナラ打、逆転につながる一打を含めて、何度も勝ち負けを動かしています。投手なら、接戦で完投・完封し、最後まで相手に流れを渡さなかった投球。10点を超えた分は、試合ページで「上限突破」として添えます。",
     [("有本豪琉", "仙台育英", "9回裏のサヨナラ本塁打", "g1"), ("山田悠希", "神戸医療未来大", "9回無失点・12奪三振で2-0完封", "g4"), ("川島連十", "二松学舎大付", "9回1失点の完投", "qf1")]),
    ("9.0〜9.5", "殊勲", "＋23〜31%", "約2.5%",
     "試合の流れを大きく変えた選手です。打者なら、終盤や接戦での逆転打・勝ち越し打。それも走者をまとめて還す一打が多いです。投手なら、長いイニングを0点に抑えて、相手にずっと勝機を与えなかった投球。負けたチームから出ることもあります。",
     [("川北健瑠", "京都国際", "5回裏の走者一掃の逆転二塁打（9.5）", "qf4"), ("高橋快心", "北海", "8回裏の勝ち越し三塁打（9.5）", "g2"), ("安食琥太郎", "横浜", "5回裏の逆転タイムリー（9.0）", "qf3"), ("平嶋桂知", "明治大", "敗れたが6回無失点・9奪三振（9.0）", "g7")]),
    ("8.5", "花丸", "＋19〜23%", "約3%",
     "試合の主役のひとりです。打者なら、均衡を破る先制打や決勝打、終盤の同点弾など、一打で試合を大きく動かした選手。投手なら、ピンチでのリリーフや、先発で試合を作って勝ちにつなげた投球です。",
     [("西口友翔", "筑波大", "0-0の7回表の先制タイムリー", "g7"), ("山口滉起", "大阪商業大", "2回裏の先制3ラン", "g6"), ("小久保颯弥", "仙台育英", "敗れたが8回表の同点本塁打", "qf3"), ("近藤悠人", "常葉大菊川", "リリーフで2回1/3を無失点", "qf2")]),
]


def top_tiers(mobile):
    blocks = ""
    for sc, name, w, freq, who, exs in TOP_TIERS:
        lis = "".join(f'<li style="margin-bottom: 4px"><a href="{B.U("game:" + k)}" style="color: {INK}; font-weight: 900">{n}</a>'
                      f'<span style="color: {SUB}">（{t}）</span>　{d}</li>' for n, t, d, k in exs)
        blocks += f"""<div style="padding: {"14px" if mobile else "18px 20px"}; border-radius: 8px; background-color: #FFFFFF; border: 2px solid {LINE}; border-left: 6px solid {RED}">
          <div style="display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 14px">
            <span class="hand" style="font-size: {32 if mobile else 40}px; color: {RED}; line-height: 1">{sc}</span>
            <span style="font-size: {17 if mobile else 19}px; font-weight: 900">{name}</span>
            <span style="font-size: 12px; color: {SUB}">勝利確率 {w}　・　出る割合 {freq}</span>
          </div>
          <p style="margin: 8px 0 0; font-size: {14 if mobile else 15}px; line-height: 1.9">{who}</p>
          <p style="margin: 10px 0 4px; font-size: 12px; font-weight: 900; color: {RED}">明治神宮大会2026では</p>
          <ul style="margin: 0; padding-left: 20px; font-size: {13 if mobile else 14}px; line-height: 1.8">{lis}</ul>
        </div>"""
    note = ("8.5点以上は、1試合に2人ほど。1回のプレーで勝利確率を20%以上動かすのは、終盤の接戦の場面くらいです。"
            "そのため、序盤の一打だけで8.5点に届くことはあまりなく、多くは「終盤」「接戦」「走者がいる場面」の一打や好投が重なっています。"
            "反対に、大差の試合でたくさんヒットを打っても、勝ち負けへの影響が小さいため7点台にとどまることがあります。")
    return card(h3("8.5点以上はこんな選手", mobile) + p(note, mobile)
                + f'<div style="display: flex; flex-direction: column; gap: 12px; margin-top: 14px">{blocks}</div>', mobile, id_="r-top")


def formula(mobile):
    box = lambda big, small, col=INK: (f'<span style="display: flex; flex-direction: column; align-items: center; gap: 2px; padding: {"10px 8px" if mobile else "14px 18px"}; '
                                       f'border: 2px solid {LINE}; border-radius: 8px; background-color: #FFFFFF; min-width: {0 if mobile else 120}px">'
                                       f'<span style="font-size: {20 if mobile else 28}px; font-weight: 900; color: {col}">{big}</span>'
                                       f'<span style="font-size: 12px; color: {SUB}; text-align: center">{small}</span></span>')
    op = lambda t: f'<span style="font-size: {20 if mobile else 26}px; font-weight: 900; color: {SUB}">{t}</span>'
    eq = (f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: {6 if mobile else 12}px; margin: 14px 0">'
          + box("採点", "") + op("＝") + box("6.0", "及第点") + op("＋") + box("WPA × 12", "勝利確率を動かした量", RED)
          + op("＋") + box("+0.5", "ファインプレー・好走塁") + "</div>")
    ex = f"""<div style="display: grid; grid-template-columns: repeat({1 if mobile else 2}, minmax(0, 1fr)); gap: 12px; margin-top: 6px">
        <div style="padding: 14px 16px; border-radius: 8px; background-color: #FFFFFF; border: 2px solid {LINE}">
          <span style="font-size: 12px; font-weight: 900; color: {RED}">例：上限突破</span>
          <span style="display: block; font-size: 15px; font-weight: 900; margin-top: 2px">砂涼人（仙台育英）WPA ＋0.46</span>
          <span style="display: block; font-size: 14px; margin-top: 4px">6.0 ＋ 0.46 × 12 ＝ 11.5 → 採点は <span class="hand" style="font-size: 26px; color: {RED}">10.0</span>
          <span style="font-size: 11px; font-weight: 900; color: #FFFFFF; background-color: {RED}; padding: 2px 10px; border-radius: 999px; white-space: nowrap">上限突破！ 11.5</span></span>
        </div>
        <div style="padding: 14px 16px; border-radius: 8px; background-color: #FFFFFF; border: 2px solid {LINE}">
          <span style="font-size: 12px; font-weight: 900; color: #3D5C93">例：マイナス</span>
          <span style="display: block; font-size: 15px; font-weight: 900; margin-top: 2px">勝利確率を −0.32 動かした場合</span>
          <span style="display: block; font-size: 14px; margin-top: 4px">6.0 − 0.32 × 12 ＝ 2.16 → 採点は <span class="hand" style="font-size: 26px; color: #3D5C93">2.0</span></span>
        </div>
      </div>"""
    steps = [("1", "プレーごとに勝利確率の動きを出す", "打席や走塁、守備のたびに、チームの勝利確率がどれだけ動いたかを計算します。"),
             ("2", "関わった選手に分けて合計する", "動いた分を、打者・走者・投手・捕手・野手に決まった割合で分け、試合を通して選手ごとに足し合わせます（下の「守備と走塁」）。"),
             ("3", "12倍して6.0点に足す", "合計を12倍し、及第点の6.0点に足します。ファインプレーや好走塁があれば ＋0.5点。"),
             ("4", "0.5点刻みに四捨五入する", "最後に0.5点刻みに丸めます。10点を超えたら採点は10.0点、丸める前の点数は「上限突破」として添えます。")]
    st = "".join(f'<li style="display: flex; gap: 12px; padding: 10px 0; border-bottom: 1px solid {LINE}"><span style="flex: none; width: 28px; height: 28px; border-radius: 999px; background-color: {RED}; color: #FFFFFF; font-weight: 900; display: flex; align-items: center; justify-content: center">{n}</span>'
                 f'<span style="display: flex; flex-direction: column"><span style="font-size: {15 if mobile else 16}px; font-weight: 900">{t}</span><span style="font-size: {13 if mobile else 14}px; line-height: 1.8">{d}</span></span></li>' for n, t, d in steps)
    why = [("なぜ6.0点が及第点なのか",
            "勝ち負けに対してプラスもマイナスもなかった選手（勝利確率の合計が0）を、ちょうど6.0点にしています。"
            "「出場して、役目をきちんと果たした」が及第点。そこから試合を動かした分だけ上がり、流れを渡した分だけ下がります。"
            "10点満点の6点を合格ラインとするのは、学校の「60点で合格」と同じ感覚です。上には4点、下には6点の幅があるので、活躍も失敗も点数に表せます。"),
           ("なぜ12倍なのか", "__X12__"),
           ("なぜ0.5点刻みで四捨五入するのか",
            "勝利確率は過去のデータをもとにした試算なので、小数点以下の細かい差には意味がありません。"
            "0.5点は勝利確率でいうと約4%、ヒット1本ぶんほどの差です。この「ヒット1本ぶん」を、点数の差として見分けるいちばん小さな単位にしました。"
            "丸め方はふつうの四捨五入です。たとえば7.24点は7.0点、7.25点は7.5点になります。"
            "サッカーの採点などで見慣れた0.5点刻みにそろえることで、点数をひと目で比べやすくしています。"),
           ("ファインプレー・好走塁の ＋0.5点",
            "勝利確率は「アウトになったか」「進塁したか」という結果しか見ません。抜けそうな打球を止めた守備や、相手のすきを突いた走塁の価値は、結果だけでは測りきれないことがあります。"
            "そこで、記録からわかる範囲で、1回につき ＋0.5点（ヒット1本ぶん）を加えています。")]
    def why_body(d):
        if d != "__X12__":
            return f'<p style="margin: 6px 0 0; font-size: {14 if mobile else 15}px; line-height: 1.9">{d}</p>'
        conv = [("＋4%", "ふつうの場面のヒット1本", "＋0.5点"), ("＋8%", "先制のタイムリー", "＋1.0点"),
                ("＋17%", "終盤の逆転打", "＋2.0点"), ("＋33%", "1人で試合を決めた", "＋4.0点 → 10点")]
        rows = "".join(f'<div style="display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid {LINE}">'
                       f'<span style="width: 64px; font-size: 18px; font-weight: 900; color: #3D5C93">{w}</span><span style="color: {SUB}">→ ×12 →</span>'
                       f'<span style="width: {120 if mobile else 160}px; font-size: 18px; font-weight: 900; color: {RED}">{pt}</span><span style="font-size: 13px; color: {SUB}">{ex}</span></div>' for w, ex, pt in conv)
        para = lambda t: f'<p style="margin: 8px 0 0; font-size: {14 if mobile else 15}px; line-height: 1.9">{t}</p>'
        return (para("ひとことで言うと、<b>「勝ったチームに、ちょうど6点分の手柄を配る」</b>ための倍率です。")
                + para("① 試合が始まったとき、どちらのチームも勝利確率は50%です。")
                + para("② 試合に勝つと、そのチームの勝利確率は100%になります。つまり勝ったチームは、試合の中で勝利確率を合わせて<b>＋50%</b>積み上げたことになります。負けたチームは−50%です。")
                + para("③ この＋50%（＝0.5）を、選手たちが分け合います。0.5を12倍すると<b>6点</b>。勝ったチームの選手の「6.0点より上の分」を全員ぶん足すと、だいたい＋6点になります。負けたチームは−6点です。")
                + para("④ 6点にそろえたのは、及第点の6.0点と同じ幅にするためです。勝ちに必要な働きを全部ひとりでやれば、6.0＋6.0＝12点。上限の10点を超える「上限突破」になります。")
                + f'<div style="margin-top: 10px; padding: 4px 14px; border-radius: 6px; background-color: #F4F6FA">{rows}</div>'
                + para("勝利確率の動きを点数に直すと、だいたい上の表のようになります（右側のプレーは一例です）。「ヒット1本でおよそ0.5点」「試合を1人で決めれば10点」。野球を見ている人の感覚とずれないように、この倍率にしています。"))

    wh = "".join(f'<div style="padding: {"14px" if mobile else "16px 20px"}; border-radius: 8px; background-color: #FFFFFF; border: 2px solid {LINE}">'
                 f'<span style="display: block; font-size: {16 if mobile else 17}px; font-weight: 900; color: {RED}">{t}</span>'
                 + why_body(d) + '</div>' for t, d in why)
    return card(h3("点数の決め方", mobile) + p("その選手のプレーで、チームの勝利確率がどれだけ上がったか・下がったかを合計し、12倍して6.0点に足します。最後に0.5点刻みに四捨五入します。", mobile)
                + eq + f'<ol style="list-style: none; margin: 4px 0 16px; padding: 0">{st}</ol>'
                + f'<div style="display: flex; flex-direction: column; gap: 12px">{wh}</div>'
                + f'<div style="margin-top: 16px">{p("計算の例", mobile, "; font-weight: 900")}</div>' + ex, mobile, id_="r-formula")


def link(href, text):
    return f'<a href="{href}" target="_blank" rel="noopener" style="color: {RED}; font-weight: 700">{text}</a>'


def sub(t, mobile):
    return f'<h4 style="margin: 22px 0 6px; font-size: {16 if mobile else 17}px; font-weight: 900; padding-left: 10px; border-left: 4px solid {RED}">{t}</h4>'


def wpa(mobile):
    bar = f"""<div style="margin-top: 14px; padding: {"14px" if mobile else "18px 20px"}; background-color: #0A1222; border: 6px solid #3D5C93; border-radius: 10px; color: #FFFFFF">
        <span style="font-size: 13px; color: #9FB3D6">例：9回裏 6-6 同点・ノーアウト走者なし</span>
        <span style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; margin: 6px 0 10px">
          <span style="font-size: {17 if mobile else 20}px; font-weight: 900">先頭打者がサヨナラ本塁打</span>
          <span style="font-size: {30 if mobile else 40}px; font-weight: 900; color: #FFD23F">+36%</span>
        </span>
        <span style="display: flex; justify-content: space-between; font-size: 13px; color: #C9D6EA"><span>打ったチームの勝利確率</span><span>64% → 100%</span></span>
        <span style="position: relative; display: block; height: 14px; margin-top: 6px; background-color: #1C2A44; border-radius: 3px; overflow: hidden">
          <span style="position: absolute; left: 0; top: 0; bottom: 0; width: 64%; background-color: #5C7FBA"></span>
          <span style="position: absolute; left: 64%; top: 0; bottom: 0; width: 36%; background-color: #FFD23F"></span>
        </span>
        <span style="display: block; font-size: 13px; color: #C9D6EA; margin-top: 10px">このプレーで打者には ＋0.36。採点では ＋0.36 × 12 ＝ ＋4.3点分です。</span>
      </div>"""
    fs = 14 if mobile else 15
    P = lambda t, extra="": p(t, mobile, "; margin-top: 8px" + extra)
    inputs = ["回（何回か）", "表か裏か", "アウトの数", "走者の位置（一塁・二塁・三塁）", "点差"]
    chips = "".join(f'<span style="padding: 4px 12px; border-radius: 999px; background-color: #FFFFFF; border: 2px solid {LINE}; font-size: 13px; font-weight: 700">{t}</span>' for t in inputs)
    cmp_rows = [("1回裏・同点・無死一塁", "2ラン本塁打", "58.3% → 73.5%", "＋0.152"),
                ("9回裏・1点負け・無死一塁", "逆転サヨナラ2ラン", "33.4% → 100%", "＋0.666")]
    cmp = "".join(f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; padding: 10px 0; border-bottom: 1px solid {LINE}">'
                  f'<span style="font-size: 13px; color: {SUB}; min-width: 180px">{a}</span><span style="font-size: 15px; font-weight: 900; min-width: 150px">{b}</span>'
                  f'<span style="font-size: 14px">{c}</span><span style="margin-left: auto; font-size: 18px; font-weight: 900; color: {RED}">{d}</span></div>' for a, b, c, d in cmp_rows)
    diffs = [("配る相手", "打者と投手だけ（守備側の動きはすべて投手の責任）", "打者・走者・投手・捕手・野手に分ける"),
             ("勝利確率の表", "過去の大量の試合データから作った表", "MLBの標準的な得点の表をもとに、カテゴリーごとの点の入りやすさで調整"),
             ("使い方", "シーズン通算で合計し、勝負強さを見る", "1試合ごとに点数（通信簿）に直す")]
    if mobile:
        dt = "".join(f'<div style="padding: 10px 0; border-bottom: 1px solid {LINE}"><span style="display: block; font-size: 14px; font-weight: 900">{a}</span>'
                     f'<span style="display: block; font-size: 13px"><b style="color: {SUB}">一般的なWPA：</b>{b}</span><span style="display: block; font-size: 13px"><b style="color: {RED}">通信簿：</b>{c}</span></div>' for a, b, c in diffs)
    else:
        dt = ('<table style="width: 100%; border-collapse: collapse; font-size: 14px"><thead><tr>'
              + "".join(f'<th scope="col" style="text-align: left; padding: 8px; border-bottom: 2px solid {INK}; font-size: 12px; color: {SUB}">{h}</th>' for h in ("", "一般的なWPA（MLB・NPB）", "ベースボール通信簿"))
              + '</tr></thead><tbody>'
              + "".join(f'<tr><th scope="row" style="text-align: left; padding: 8px; border-bottom: 1px solid {LINE}; white-space: nowrap">{a}</th><td style="padding: 8px; border-bottom: 1px solid {LINE}">{b}</td><td style="padding: 8px; border-bottom: 1px solid {LINE}; color: {RED}; font-weight: 700">{c}</td></tr>' for a, b, c in diffs)
              + '</tbody></table>')
    lg = [("高校", "0.50点"), ("大学", "0.45点"), ("NPB", "0.40点"), ("MLB・国際大会", "0.48点")]
    lgs = "".join(f'<span style="display: flex; flex-direction: column; align-items: center; padding: 8px 14px; border-radius: 8px; background-color: #FFFFFF; border: 2px solid {LINE}"><span style="font-size: 12px; color: {SUB}">{a}</span><span style="font-size: 17px; font-weight: 900">{b}</span></span>' for a, b in lg)
    refs = [("MLB.com Glossary：Win Probability Added (WPA)", "https://www.mlb.com/glossary/advanced-stats/win-probability-added", "MLB公式の用語集。WPAは、ひとつの出来事でチームの勝つ見込みが何%変わったかを表す、と定義しています。"),
            ("MLB.com Glossary：Win Expectancy (WE)", "https://www.mlb.com/glossary/advanced-stats/win-expectancy", "WPAのもとになる「勝利確率（勝利期待値）」の定義。"),
            ("FanGraphs Library：WPA", "https://library.fangraphs.com/misc/wpa", "MLBの全試合で勝利確率グラフと選手ごとのWPAを出しているサイトの解説。WPAは「起きたことを描く指標」で、将来の予測には向かないと説明しています。"),
            ("Baseball-Reference：Win Expectancy / WPA", "https://www.baseball-reference.com/about/wpa.shtml", "回・塁・アウト・点差ごとの勝つ確率から計算し、打者に加え投手から差し引く、という計算の決まりを説明しています。"),
            ("1.02 Essence of Baseball（DELTA）：WPA", "https://1point02.jp/op/gnav/glossary/gls_explanation.aspx?eid=20064", "日本語での解説。NPBのWPAも公開しています（一部は有料会員向け）。")]
    rl = "".join(f'<li style="margin-bottom: 10px">{link(u, t)}<span style="display: block; font-size: 13px; color: {SUB}; line-height: 1.7">{d}</span></li>' for t, u, d in refs)
    return card(h3("勝利確率（WPA）とは", mobile)
                + p("WPA（Win Probability Added／勝利確率の増減）は、ひとつのプレーでチームの「勝つ見込み」が何%動いたかを表す指標です。アメリカのMLBで広く使われ、日本のプロ野球でもデータ会社が算出しています。", mobile)
                + sub("① まず「勝利確率」を出す", mobile)
                + P("試合のどの場面にも、「この状況からなら、だいたい何%の確率で勝てるか」という数字があります。これが勝利確率（勝利期待値）です。使うのは次の5つだけです。")
                + f'<div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px">{chips}</div>'
                + P("たとえば試合開始時は、どちらも約50%。終盤に大きくリードしているチームは90%を超えます。どの選手が打席に立っているかは考えません。")
                + sub("② プレーの前と後の差が WPA", mobile)
                + P("プレーの直前と直後で勝利確率を比べ、その差をプレーした選手の手柄（または責任）にします。打った側がプラスなら、守った側は同じ分だけマイナスです。")
                + bar
                + sub("③ 同じ本塁打でも、場面で重さが変わる", mobile)
                + P("WPAのいちばんの特徴は、場面の重さがそのまま数字に出ることです。下はFanGraphsの勝利確率をもとにした例です（DELTA「1.02」の解説より）。")
                + f'<div style="margin-top: 8px">{cmp}</div>'
                + P("同じ2ランでも、試合終盤の逆転サヨナラは序盤の4倍以上の重さになります。逆に、大差の試合でのヒットは勝利確率をほとんど動かしません。")
                + sub("④ WPAの読み方と注意点", mobile)
                + f'<ul style="margin: 8px 0 0; padding-left: 20px; font-size: {fs}px; line-height: 1.9">'
                  '<li><b>0が平均</b>：プラスなら勝ちに近づけた、マイナスなら負けに近づけた選手です。</li>'
                  '<li><b>「その日に起きたこと」を描く指標</b>：勝負どころでの活躍は高く出ますが、選手の実力そのものや、次の試合の活躍を予測する指標ではありません。</li>'
                  '<li><b>チャンスが回ってくるかは運</b>：重い場面で打席が回るかどうかは、本人の力とは関係ありません。</li></ul>'
                + sub("⑤ 一般的なWPAとベースボール通信簿の違い", mobile)
                + f'<div style="margin-top: 8px">{dt}</div>'
                + P("勝利確率は、塁とアウトの状況ごとの「この回にあと何点入りそうか」を表すMLBの標準的な表をもとに、残りの回を積み上げて計算しています。カテゴリーによって点の入りやすさが違うため、1イニングあたりの平均得点で調整しています。10回以降のタイブレーク（無死一・二塁から）にも対応しています。")
                + f'<div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px">{lgs}</div>'
                + p("1イニングあたりの平均得点（調整に使う値）", mobile, f"; margin-top: 4px; font-size: 12px; color: {SUB}")
                + sub("⑥ 基準・参考にしている資料", mobile)
                + f'<ul style="margin: 8px 0 0; padding-left: 20px; font-size: {fs}px">{rl}</ul>',
                mobile, id_="r-wpa")


PUBLIC = [
    ("MLB", "打率・本塁打・防御率などの公式記録に加え、WPAなどの指標をMLB公式の用語集で定義",
     "◎ 試合ごとのWPAと勝利確率グラフ", "MLB.com、FanGraphs、Baseball-Reference"),
    ("NPB", "公式サイト（npb.jp）は打率・本塁打・打点・防御率などの公式記録が中心",
     "○ データ会社が算出（WPA・WAR・UZRなど）", "DELTA「1.02 Essence of Baseball」（一部有料）"),
    ("国際大会", "WBSC公式サイトで、試合のボックススコアと打率・本塁打などのリーダーをリアルタイムに公開",
     "△ 公式な公開は確認できず", "WBSC、MLB.com（WBC）"),
    ("大学野球", "各連盟・大会が、打率・防御率など基本の成績を公開。一球ごとの速報も各種サービスで見られる",
     "× 公開は確認できず", "各連盟、スポーツナビ、一球速報サービス"),
    ("高校野球", "打数・安打・打点・防御率など基本の成績が中心。主に報道機関が集計して紹介",
     "× 公開は確認できず", "日本高野連、報道各社、一球速報サービス"),
]


def public(mobile):
    if mobile:
        body = "".join(f'<div style="padding: 12px 0; border-bottom: 1px solid {LINE}"><span style="display: flex; justify-content: space-between; gap: 8px"><span style="font-size: 16px; font-weight: 900">{c}</span><span style="font-size: 13px; font-weight: 900; color: {RED}">{w}</span></span>'
                       f'<span style="display: block; font-size: 13px; line-height: 1.7; margin-top: 4px">{o}</span><span style="display: block; font-size: 12px; color: {SUB}">主な公開元：{s}</span></div>' for c, o, w, s in PUBLIC)
    else:
        body = ('<table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 8px"><thead><tr>'
                + "".join(f'<th scope="col" style="text-align: left; padding: 8px; border-bottom: 2px solid {INK}; font-size: 12px; color: {SUB}; white-space: nowrap">{h}</th>' for h in ("カテゴリー", "公式に出ている主な記録", "WPAなどの指標", "主な公開元"))
                + '</tr></thead><tbody>'
                + "".join(f'<tr><th scope="row" style="text-align: left; padding: 10px 8px; border-bottom: 1px solid {LINE}; white-space: nowrap">{c}</th><td style="padding: 10px 8px; border-bottom: 1px solid {LINE}; line-height: 1.7">{o}</td>'
                          f'<td style="padding: 10px 8px; border-bottom: 1px solid {LINE}; font-weight: 900; color: {RED}; white-space: nowrap">{w}</td><td style="padding: 10px 8px; border-bottom: 1px solid {LINE}; font-size: 13px; color: {SUB}">{s}</td></tr>' for c, o, w, s in PUBLIC)
                + '</tbody></table>')
    links = [("npb.jp（日本野球機構）", "https://npb.jp/"), ("1.02 Essence of Baseball", "https://1point02.jp/"),
             ("WBSC 公式サイト", "https://www.wbsc.org/"), ("FanGraphs", "https://www.fangraphs.com/"), ("Baseball-Reference", "https://www.baseball-reference.com/")]
    ll = "　".join(link(u, t) for t, u in links)
    return card(h3("カテゴリーごとに公開されている指標", mobile)
                + p("WPAのような「勝ち負けへの貢献」を表す指標が、どこまで公開されているかをまとめました（2026年11月時点で確認できた範囲）。", mobile)
                + body
                + p("MLBでは、試合ごとの勝利確率グラフや選手のWPAを誰でも見られます。NPBでもデータ会社が算出していますが、高校・大学・国際大会では、打率や防御率などの基本の成績が中心で、WPAのような指標はほとんど公開されていません。ベースボール通信簿は、この「まだ数字で語られていない試合」に、勝ち負けへの貢献という物差しを当てる試みです。", mobile, "; margin-top: 12px")
                + p(ll, mobile, "; margin-top: 10px; font-size: 13px"), mobile, id_="r-public")


SPLITS = [
    ("三振・四球・死球・本塁打", "投手 75%　捕手 25%", "バッテリーの責任として分けます"),
    ("平凡な打球でのアウト", "投手 70%　野手 30%", "捕った野手にも少し手柄"),
    ("難しい打球でのアウト", "野手 最大 80%", "難しいほど野手の取り分を増やします"),
    ("ヒットを打たれた", "投手 65%　捕手 25%　野手 10%", ""),
    ("エラー", "その野手 100%", ""),
    ("併殺", "関わった野手で 100% を分け合う", ""),
    ("盗塁を決めた", "走者 100%", "守備側は投手と捕手で半分ずつマイナス"),
    ("盗塁死・牽制死・走塁ミス", "走者がマイナス", ""),
    ("ふつう以上の進塁", "走者の手柄", "打者の分から切り分けます"),
]


def splits(mobile):
    if mobile:
        rows = "".join(f'<div style="padding: 10px 0; border-bottom: 1px solid {LINE}"><span style="display: block; font-size: 14px; font-weight: 900">{a}</span>'
                       f'<span style="display: block; font-size: 14px; color: {RED}; font-weight: 700">{b}</span>'
                       f'{f"<span style=\"display: block; font-size: 12px; color: {SUB}\">{c}</span>" if c else ""}</div>' for a, b, c in SPLITS)
        body = f'<div style="margin-top: 8px">{rows}</div>'
    else:
        rows = "".join(f'<tr><th scope="row" style="text-align: left; padding: 10px 12px 10px 0; font-size: 15px; font-weight: 900; border-bottom: 1px solid {LINE}; white-space: nowrap">{a}</th>'
                       f'<td style="padding: 10px 12px; font-size: 15px; font-weight: 700; color: {RED}; border-bottom: 1px solid {LINE}; white-space: nowrap">{b}</td>'
                       f'<td style="padding: 10px 0; font-size: 13px; color: {SUB}; border-bottom: 1px solid {LINE}">{c}</td></tr>' for a, b, c in SPLITS)
        body = (f'<table style="width: 100%; border-collapse: collapse; margin-top: 10px"><thead><tr>'
                f'<th scope="col" style="text-align: left; font-size: 12px; color: {SUB}; padding-bottom: 6px; border-bottom: 2px solid {INK}">プレー</th>'
                f'<th scope="col" style="text-align: left; font-size: 12px; color: {SUB}; padding: 0 12px 6px; border-bottom: 2px solid {INK}">分け方</th>'
                f'<th scope="col" style="text-align: left; font-size: 12px; color: {SUB}; padding-bottom: 6px; border-bottom: 2px solid {INK}">補足</th></tr></thead><tbody>{rows}</tbody></table>')
    return card(h3("守備と走塁の手柄の分け方", mobile)
                + p("打席の結果で動いた勝利確率は、打った側では打者と走者に、守る側では投手・捕手・野手に分けます。打者が得た分だけ、守備側の誰かが失う考え方です。", mobile)
                + body
                + p("ファインプレーや好走塁は、わかる範囲で1回につき ＋0.5点を加えます。", mobile, "; margin-top: 12px"), mobile, id_="r-splits")


def awards(mobile):
    items = [(B.BATTER, "野手MVP", "勝ったチームの打者で、いちばん点の高い選手", "7.0点以上"),
             (B.PITCHER, "投手MVP", "勝ったチームの投手で、いちばん点の高い選手", "7.0点以上"),
             (B.BATTER, "敢闘賞", "負けたチームで、いちばん点の高い選手", "8.0点以上")]
    cards = "".join(f"""<div style="display: flex; align-items: center; gap: 12px; padding: 14px; border-radius: 8px; background-color: #FFFFFF; border: 2px solid {LINE}">
          <img src="{ico}" alt="" aria-hidden="true" style="width: 56px; height: auto; flex: none">
          <span style="display: flex; flex-direction: column; gap: 2px"><span style="font-size: 17px; font-weight: 900">{t}</span><span style="font-size: 13px">{d}</span>
          <span style="font-size: 12px; font-weight: 900; color: {RED}">{c}</span></span>
        </div>""" for ico, t, d, c in items)
    return card(h3("MVPと敢闘賞", mobile)
                + f'<div style="display: grid; grid-template-columns: repeat({1 if mobile else 3}, minmax(0, 1fr)); gap: 12px; margin: 8px 0 12px">{cards}</div>'
                + p("基準に届く選手がいないときは「該当者なし」です。点数が同じときは、0.5点刻みに丸める前の点数で決めます。", mobile), mobile, id_="r-awards")


def scope(mobile):
    items = ["1打席だけの代打や、1人だけ投げた投手も採点します。",
             "試合データは速報をもとにしているため、公式記録と異なる場合があります。",
             "勝利確率と採点は、簡易モデルによる試算です。選手の評価・実力を決めるものではありません。"]
    lis = "".join(f'<li style="margin-bottom: 6px">{t}</li>' for t in items)
    return card(h3("対象とご注意", mobile) + f'<ul style="margin: 0; padding-left: 20px; font-size: {14 if mobile else 15}px; line-height: 1.9">{lis}</ul>', mobile)


def page(mobile):
    wrap = "width: 390px; " if mobile else ""
    gap = 28 if mobile else 36
    crumbs = (f'<a href="{B.U('top')}" style="color: #C9D6EA; text-decoration: none">トップ</a> <span style="color: #5C7FBA">›</span> <span style="color: #FFFFFF">採点のしくみ</span>')
    toc = "".join(f'<a href="#{a}" style="padding: 8px 14px; border: 2px solid #3D5C93; border-radius: 999px; color: #FFFFFF; text-decoration: none; font-size: 13px; font-weight: 700">{t}</a>'
                  for t, a in (("点数の目安", "r-scale"), ("8.5点以上", "r-top"), ("点数の決め方", "r-formula"), ("勝利確率とは", "r-wpa"), ("守備と走塁", "r-splits"), ("MVPと敢闘賞", "r-awards")))
    return f"""<div style="{wrap}min-height: 100vh; background-color: #0B1A36; background-image: radial-gradient(circle at 50% 0, #1A3260 0, #0B1A36 60%); color: #FFFFFF; font-family: 'Noto Sans JP', sans-serif; line-height: 1.6">
{B.header(mobile)}  <main style="max-width: 960px; margin: 0 auto; padding: {'18px 16px 56px' if mobile else '24px 24px 72px'}; display: flex; flex-direction: column; gap: {gap}px">
    <section aria-label="採点のしくみ" style="display: flex; flex-direction: column; gap: 14px">
      <nav aria-label="パンくずリスト" style="font-size: 13px">{crumbs}</nav>
      <h1 style="margin: 0; font-size: {30 if mobile else 44}px; font-weight: 900; line-height: 1.3"><span class="marker">採点のしくみ</span></h1>
      <p style="margin: 0; font-size: {15 if mobile else 17}px; line-height: 2; color: #E6ECF6">1試合ごとに、出場した全選手へ10点満点の点数をつけます。打った・抑えただけでなく、そのプレーが勝ち負けをどれだけ動かしたかで点が決まります。</p>
      <div style="display: flex; flex-wrap: wrap; gap: 8px">{toc}</div>
    </section>
    {scale(mobile)}
    {top_tiers(mobile)}
    {formula(mobile)}
    {wpa(mobile)}
    {splits(mobile)}
    {awards(mobile)}
    {scope(mobile)}
    <a href="{B.U('top')}" style="align-self: flex-start; padding: 12px 22px; background-color: #D7262E; color: #FFFFFF; text-decoration: none; font-weight: 900; border-radius: 999px">今日の通信簿を見る →</a>
  </main>
{B.footer(mobile)}</div>
"""


out = pathlib.Path(os.environ.get("OUT", "/tmp/brc-build"))
H_PC, H_SP = (int(x) for x in (sys.argv[2:4] if False else (3600, 5600)))
import os  # noqa: E402
H_PC = int(os.environ.get("H_PC", 3600))
H_SP = int(os.environ.get("H_SP", 5600))
(out / "Rules.dc.html").write_text(B.HEAD.format(title="採点のしくみ（PC）") + page(False) + B.TAIL.format(w=1280, h=H_PC))
(out / "RulesMobile.dc.html").write_text(B.HEAD.format(title="採点のしくみ（スマホ）") + page(True) + B.TAIL.format(w=390, h=H_SP))
print("rules ok")
