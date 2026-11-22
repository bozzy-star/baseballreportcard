"""選手ページのURLに使うID（チーム名＋選手名から決まる短い文字列）。"""
import hashlib


def player_id(team, name):
    return hashlib.sha1(f"{team}|{name.replace(' ', '')}".encode("utf-8")).hexdigest()[:10]
