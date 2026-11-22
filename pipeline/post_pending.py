"""まだXに投稿していない試合を扱う。

  python3 pipeline/post_pending.py draft --out issue.md      確認用の文面（GitHub の Issue 本文）を作る
  python3 pipeline/post_pending.py send [--keys a,b]           Xに投稿する（鍵は環境変数から）

送った試合は台帳（data/registry.json）に投稿URLを書き込む。
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
REPO = "bozzy-star/baseballreportcard"
RAW = f"https://raw.githubusercontent.com/{REPO}/main/data/cards"
REG_PATH = ROOT / "data" / "registry.json"


def page_url(g):
    from brc import paths
    return paths.game_url(paths.comps()[g["comp"]], g)


def load():
    return json.loads(REG_PATH.read_text(encoding="utf-8"))


def save(reg):
    REG_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def pending(reg, keys=None, states=("pending", "draft")):
    return [g for g in reg["games"] if g.get("post_status") in states and g.get("status") == "published"
            and (not keys or g["key"] in keys)]


def draft(out):
    reg = load()
    ps = pending(reg, states=("pending",))
    if not ps:
        print("投稿待ちの試合はありません")
        return
    lines = ["Xへの投稿の確認です。問題なければ、この Issue に **OK** とだけコメントしてください（全試合をまとめて投稿します）。",
             "文章を直したいときは「**直して：〇〇**」とコメントしてください（例：直して：もっと逆転劇を強調して）。注文どおりに書き直して、新しい確認用 Issue を作ります。", ""]
    for g in ps:
        lines += [f"### {g['label']}　{g['score']}", f"ページ: {page_url(g)}", "", "```", g["post_text"], "```", ""]
        lines += [f"![{c}]({RAW}/{c})" for c in (g.get("player_cards", []) + g.get("cards", []))[:4]] + [""]
        g["post_status"] = "draft"
    lines.append(f"<!-- keys: {','.join(g['key'] for g in ps)} -->")
    pathlib.Path(out).write_text("\n".join(lines), encoding="utf-8")
    save(reg)
    print(f"確認用の文面を作りました: {len(ps)}試合")


def send(keys, auto=False, report=None):
    from brc.post import load_keys, upload_image, create_post
    reg = load()
    ps = pending(reg, keys, states=("pending",) if auto else ("pending", "draft"))
    if not ps:
        print("投稿する試合はありません")
        return
    k = load_keys()
    for g in ps:
        imgs = (g.get("player_cards", []) + g.get("cards", []))[:4]
        ids = [upload_image(ROOT / "data" / "cards" / c, k) for c in imgs]
        res = create_post(g["post_text"], ids, k)
        pid = (res.get("data") or {}).get("id")
        g["x_url"] = f"https://x.com/BaseBalltannin/status/{pid}" if pid else None
        g["post_status"] = "posted" if pid else "error"
        save(reg)
        print(f"投稿しました: {g['key']} {g['x_url']}")
    if report:
        lines = ["自動で X に投稿しました。内容に問題があれば、X 上で投稿を削除してください。", ""]
        for g in ps:
            lines += [f"### {g['label']}　{g['score']}", f"X: {g.get('x_url') or '投稿に失敗しました'}",
                      f"ページ: {page_url(g)}", "", "```", g["post_text"], "```", ""]
        pathlib.Path(report).write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["draft", "send"])
    ap.add_argument("--out", default="/tmp/issue.md")
    ap.add_argument("--keys", default="")
    ap.add_argument("--auto", action="store_true", help="確認なしの自動投稿（未確認の pending のみ）")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    if a.mode == "draft":
        draft(a.out)
    else:
        send([x for x in a.keys.split(",") if x], auto=a.auto, report=a.report or None)


if __name__ == "__main__":
    main()
