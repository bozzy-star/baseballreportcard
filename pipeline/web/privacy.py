"""プライバシーポリシー（PC・スマホ）。"""
import os
import pathlib
import sys

sys.argv = ["build.py", "__first__"]
import build as B  # noqa: E402

INK, SUB, RED = B.INK, B.SUB, B.RED

SECTIONS = [
    ("運営者", ["ベースボール通信簿（baseballreportcard.com）は、1000% が運営しています。"]),
    ("アクセス解析ツールについて", [
        "当サイトでは、サイトの利用状況を把握して改善に役立てるため、Google LLC が提供する「Google アナリティクス」を、「Google タグ マネージャー」を通じて利用しています。",
        "これらのツールは Cookie などを使って、次のような情報を Google LLC に送信します。個人を特定する情報（氏名・メールアドレスなど）は含みません。",
    ]),
    ("送信される情報", [
        "・閲覧したページの URL、閲覧した日時",
        "・どのサイトやリンクから来たか（参照元）",
        "・ブラウザや端末の種類、画面の大きさ、おおよその地域（IP アドレスから推定）",
        "・ページ内での操作（スクロールやリンクのクリックなど）",
    ]),
    ("送信先と利用目的", [
        "送信先：Google LLC",
        "利用目的：閲覧数や閲覧の傾向を集計し、サイトの内容や使い勝手の改善、投稿の時間帯の検討などに利用します。",
        "Google による情報の取り扱いは、Google のプライバシーポリシーをご覧ください：https://policies.google.com/privacy",
    ]),
    ("情報の送信を止めたい場合", [
        "ブラウザの設定で Cookie を無効にするか、Google が提供する「Google アナリティクス オプトアウト アドオン」を利用すると、送信を止められます：https://tools.google.com/dlpage/gaoptout",
    ]),
    ("掲載している情報について", [
        "試合のデータは公開されている速報をもとにしており、公式記録と異なる場合があります。勝利確率と採点は簡易モデルによる試算で、選手の評価・実力を決めるものではありません。",
    ]),
    ("お問い合わせ", ["X（@BaseBalltannin）のメッセージからご連絡ください。"]),
    ("改定", ["このポリシーは、必要に応じて改定することがあります。改定した場合は、このページでお知らせします。", "制定：2026年11月22日"]),
]


def page(mobile):
    body = ""
    for h, ps in SECTIONS:
        body += f'<h2 style="margin: 24px 0 8px; font-size: {17 if mobile else 19}px; font-weight: 900; padding-left: 10px; border-left: 4px solid {RED}">{h}</h2>'
        body += "".join(f'<p style="margin: 4px 0; font-size: {14 if mobile else 15}px; line-height: 1.9">{p}</p>' for p in ps)
    wrap = "width: 390px; " if mobile else ""
    return f"""<div style="{wrap}min-height: 100vh; background-color: #0B1A36; color: #FFFFFF; font-family: 'Noto Sans JP', sans-serif; line-height: 1.6">
{B.header(mobile)}  <main style="max-width: 860px; margin: 0 auto; padding: {'18px 16px 56px' if mobile else '24px 24px 72px'}">
    <h1 style="margin: 8px 0 16px; font-size: {28 if mobile else 38}px; font-weight: 900"><span class="marker">プライバシーポリシー</span></h1>
    <div class="sheet" style="padding: {'16px' if mobile else '24px 28px'}; border-radius: 8px; color: {INK}">{body}</div>
  </main>
{B.footer(mobile)}</div>
"""


out = pathlib.Path(os.environ.get("OUT", "/tmp/brc-build"))
(out / "Privacy.dc.html").write_text(B.HEAD.format(title="プライバシーポリシー") + page(False) + B.TAIL.format(w=1280, h=2400))
(out / "PrivacyMobile.dc.html").write_text(B.HEAD.format(title="プライバシーポリシー") + page(True) + B.TAIL.format(w=390, h=3600))
print("privacy ok")
