"""使い方:  python -m brc.cli 試合.json  [-o 出力フォルダ]

採点結果を JSON（サイト・X投稿用）と Markdown（確認用）で書き出す。
"""
import argparse
import json
import pathlib
from .engine import score_game, POS_JA


def to_markdown(r):
    g, f, a = r["game"], r["final"], r["awards"]
    lines = [f"# {g.get('tournament', '')} {g.get('round', '')}".strip(),
             f"{g.get('date', '')}　{g['away']} {f['away']} - {f['home']} {g['home']}", ""]
    lines.append("## 表彰")
    lines.append(f"- 投手MVP：{a['pitcher_mvp'] or '該当なし'}")
    lines.append(f"- 野手MVP：{a['fielder_mvp'] or '該当なし'}")
    lines.append(f"- 敢闘賞：{a['fighting_spirit'] or '該当なし'}")
    for side in ("away", "home"):
        lines += ["", f"## {g[side]}", "", "| 選手 | 採点 | WPA | 担任からの一言 |", "|---|---|---|---|"]
        for row in [x for x in r["ratings"] if x["side"] == side]:
            mark = "（投）" if row["pitcher"] else ""
            lines.append(f"| {row['player']}{mark} | {row['score']:.1f} | {row['wpa']:+.3f} | {row['comment']} |")
    if r["warnings"]:
        lines += ["", "## 記録チェック"] + [f"- {w}" for w in r["warnings"]]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="ベースボール通信簿 採点エンジン")
    ap.add_argument("game_json")
    ap.add_argument("-o", "--out", default="output")
    args = ap.parse_args()
    src = pathlib.Path(args.game_json)
    data = json.loads(src.read_text(encoding="utf-8"))
    r = score_game(data)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    gid = data["game"].get("id", src.stem)
    (out / f"{gid}.result.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / f"{gid}.md").write_text(to_markdown(r), encoding="utf-8")
    print(to_markdown(r))


if __name__ == "__main__":
    main()
