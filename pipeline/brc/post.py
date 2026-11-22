"""採点カードをXに投稿する（X API v2・OAuth 1.0a）。

1) 鍵の登録（最初の1回だけ。ターミナルで本人が入力する。画面には表示されない）
     python3 -m brc.post --setup
   → ~/.config/baseball-report-card/x.env に保存（本人だけが読める権限）

2) 投稿内容の確認（投稿はしない）
     python3 -m brc.post output/<試合ID>.result.json output/<試合ID>-1-*.png output/<試合ID>-2-*.png

3) 本当に投稿する
     python3 -m brc.post output/<試合ID>.result.json <画像...> --send

追加のライブラリは不要（Python標準だけ）。
"""
import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import sys
import time
import urllib.parse
import urllib.request

KEY_FILE = pathlib.Path.home() / ".config" / "baseball-report-card" / "x.env"
KEYS = ["X_API_KEY", "X_API_KEY_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
MEDIA_URL = "https://api.x.com/2/media/upload"
TWEET_URL = "https://api.x.com/2/tweets"
HASHTAG = "#ベースボール通信簿"


# ---------- 鍵 ----------
def setup():
    print("Xの開発者コンソールで作った4つの鍵を貼り付けてください（入力は画面に出ません）。")
    labels = {"X_API_KEY": "API Key", "X_API_KEY_SECRET": "API Key Secret",
              "X_ACCESS_TOKEN": "Access Token", "X_ACCESS_TOKEN_SECRET": "Access Token Secret"}
    vals = {k: getpass.getpass(f"{labels[k]}: ").strip() for k in KEYS}
    if not all(vals.values()):
        sys.exit("空の項目があります。やり直してください。")
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text("".join(f"{k}={v}\n" for k, v in vals.items()), encoding="utf-8")
    os.chmod(KEY_FILE, 0o600)
    print(f"保存しました: {KEY_FILE}")


def load_keys():
    vals = {k: os.environ.get(k) for k in KEYS}
    if not all(vals.values()) and KEY_FILE.exists():
        for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                vals.setdefault(k, None)
                if not vals.get(k):
                    vals[k] = v.strip()
    missing = [k for k in KEYS if not vals.get(k)]
    if missing:
        sys.exit("鍵が見つかりません。先に  python3 -m brc.post --setup  を実行してください。")
    return vals


# ---------- OAuth 1.0a ----------
def _q(s):
    return urllib.parse.quote(str(s), safe="~")


def oauth_header(method, url, keys, params=None, nonce=None, timestamp=None):
    """params は署名に含めるクエリ／フォーム値（JSON・multipart の本文は含めない）。"""
    oauth = {
        "oauth_consumer_key": keys["X_API_KEY"],
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(timestamp or int(time.time())),
        "oauth_token": keys["X_ACCESS_TOKEN"],
        "oauth_version": "1.0",
    }
    allp = dict(params or {}, **oauth)
    pstr = "&".join(f"{k}={v}" for k, v in sorted((_q(k), _q(v)) for k, v in allp.items()))
    base = "&".join([method.upper(), _q(url), _q(pstr)])
    key = f"{_q(keys['X_API_KEY_SECRET'])}&{_q(keys['X_ACCESS_TOKEN_SECRET'])}"
    sig = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    oauth["oauth_signature"] = sig
    return "OAuth " + ", ".join(f'{_q(k)}="{_q(v)}"' for k, v in sorted(oauth.items()))


def _request(req):
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.exit(f"Xからエラーが返りました（{e.code}）: {body}")


def upload_image(path, keys):
    data = pathlib.Path(path).read_bytes()
    boundary = "----brc" + secrets.token_hex(12)
    parts = []
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="media_category"\r\n\r\ntweet_image\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="media"; filename="{pathlib.Path(path).name}"\r\n'
                 f"Content-Type: image/png\r\n\r\n".encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(MEDIA_URL, data=body, method="POST", headers={
        "Authorization": oauth_header("POST", MEDIA_URL, keys),
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    })
    res = _request(req)
    mid = (res.get("data") or {}).get("id") or res.get("media_id_string")
    if not mid:
        sys.exit(f"画像のIDを受け取れませんでした: {res}")
    return mid


def create_post(text, media_ids, keys):
    body = json.dumps({"text": text, "media": {"media_ids": media_ids}}).encode()
    req = urllib.request.Request(TWEET_URL, data=body, method="POST", headers={
        "Authorization": oauth_header("POST", TWEET_URL, keys),
        "Content-Type": "application/json",
    })
    return _request(req)


def delete_post(post_id, keys):
    url = f"{TWEET_URL}/{post_id}"
    req = urllib.request.Request(url, method="DELETE", headers={"Authorization": oauth_header("DELETE", url, keys)})
    return _request(req)


# ---------- 本文 ----------
def weighted_len(text):
    """Xの文字数（日本語などは2、英数字は1。上限280）。"""
    return sum(1 if ord(c) < 0x1100 else 2 for c in text)


def compose(r, url=None, comments=None):
    g, f, a = r["game"], r["final"], r["awards"]
    scores = {x["player"]: x["score"] for x in r["ratings"]}
    nm = lambda n: n.replace(" ", "")
    lines = [f"【{g.get('tournament', '')} {g.get('round', '')}】".replace(" 】", "】"),
             f"{g['away']} {f['away']}-{f['home']} {g['home']}", ""]
    for lab, key in (("投手MVP", "pitcher_mvp"), ("野手MVP", "fielder_mvp"), ("敢闘賞", "fighting_spirit")):
        n = a.get(key)
        lines.append(f"{lab} {nm(n)} {scores[n]:.1f}" if n else f"{lab} 該当なし")
        if n and comments and comments.get(n):
            lines.append(f"「{comments[n]}」")
    tags = [HASHTAG]
    t = g.get("tournament", "")
    if "神宮" in t:
        tags.insert(0, "#神宮大会")
    lines += ["", " ".join(tags)]
    if url:
        lines.append(url)
    text = "\n".join(lines)
    if weighted_len(text) > 280:
        text = "\n".join(lines[:2] + lines[3:5] + ["", " ".join(tags)] + ([url] if url else []))
    return text


def main():
    ap = argparse.ArgumentParser(description="採点カードをXに投稿")
    ap.add_argument("result_json", nargs="?")
    ap.add_argument("images", nargs="*")
    ap.add_argument("--setup", action="store_true", help="鍵を登録する")
    ap.add_argument("--delete", help="投稿IDを指定して削除する（元に戻せない）")
    ap.add_argument("--send", action="store_true", help="本当に投稿する（付けなければ確認だけ）")
    ap.add_argument("--text", help="本文を自分で指定する（ファイルのパス）")
    ap.add_argument("--url", help="本文の最後に付けるURL")
    ap.add_argument("--comments", help="受賞者への一言（JSON: {\"選手名\": \"一言\"}）")
    a = ap.parse_args()
    if a.setup:
        return setup()
    if a.delete:
        res = delete_post(a.delete, load_keys())
        print("削除しました" if (res.get("data") or {}).get("deleted") else f"結果: {res}")
        return
    if not a.result_json:
        ap.error("採点結果のJSONを指定してください")
    r = json.loads(pathlib.Path(a.result_json).read_text(encoding="utf-8"))
    text = pathlib.Path(a.text).read_text(encoding="utf-8").strip() if a.text else compose(r, a.url, json.loads(pathlib.Path(a.comments).read_text(encoding="utf-8")) if a.comments else None)
    if not 1 <= len(a.images) <= 4:
        sys.exit("画像は1〜4枚で指定してください")
    print("----- 本文 -----")
    print(text)
    print(f"----- 文字数 {weighted_len(text)}/280・画像 {len(a.images)}枚 -----")
    for p in a.images:
        print("  ", p)
    if not a.send:
        print("\n（確認だけです。投稿するには --send を付けて実行してください）")
        return
    keys = load_keys()
    ids = [upload_image(p, keys) for p in a.images]
    res = create_post(text, ids, keys)
    pid = (res.get("data") or {}).get("id")
    print(f"投稿しました: https://x.com/BaseBalltannin/status/{pid}" if pid else f"結果: {res}")


if __name__ == "__main__":
    main()
