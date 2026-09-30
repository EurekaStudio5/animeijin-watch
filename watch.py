# -*- coding: utf-8 -*-
"""アニ名人（animeijin.com）の見張り。GitHub Actions から10分おきに1回動く短いプログラム（AI は使わない）。

外からお客様と同じようにアクセスして、次を確かめる（読むだけ。本番のデータは作らない・変えない）:
  1. トップページが開くか（HEAD＝本体は受け取らない）
  2. ヘルスチェックの入口 /api/packs が 200 か
  3. 公開の状態窓口 /api/status で、DB への書き込みが失敗していないか・履歴が読めるか・裏の仕事が動いているか

判定と通知:
  - 1回の実行の中で、異常なら3分おいてもう一度確かめる。2回とも異常＝この回は「異常」。時間が足りず確かめきれなかった回は
    「確認できず」（異常にも正常にも数えない＝見張り側の都合を本番の障害として知らせない）。
  - 前の回も異常だった（約10〜15分続いている）ら LINE で知らせる。前の回の記録が読めないときは、この回だけで知らせる
    （記録が壊れても「黙って知らせない」側に倒れないように）。
  - 続いていれば念押し（最初の24時間は3時間ごと・以降は1日1回。LINE の月の枠が残り少なければ念押しは送らない）。
  - 直ったら「直った」を1通。
  - 記録（state.json）はこのリポジトリの `state` ブランチに GitHub の API で書く（書けたことを確かめてから LINE を送る）。
    書くのは中身が変わったときだけ（ふだんの正常な回は書かない）。
  - 送る通知は「送る予定（outbox）」に本文と再送用の番号（X-Line-Retry-Key）ごと記録してから送る。送れなかったものは次の回に
    同じ本文・同じ番号で送り直す（LINE が受け取っていれば二重に届かない）。直っても捨てない。

⚠️検知の限界（2026-09-30 Codex レビュー）: /api/status の書き込みの印（stat_err の write:・stat_write_age_sec）は
「書き込みを試みて失敗したとき」に出る。利用がある間は1分ごとに試みるので、書けなくなってからおおむね15〜25分で知らせる。
誰も使っていない深夜は1時間ごとの定期書き込みまで気づけない（通常の実行間隔なら最長で約90分・GitHub の定時実行は遅れる・
抜けることがある＝保証ではない）。本番に「数分おきに必ず書く」確認口を足すのは第2段。
公開ログ（誰でも見られる）には、決まった文言だけを出す（本番のエラー文・通知の本文は出さない）。
"""
import base64
import json
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.request
import uuid

SITE = "https://animeijin.com"
UA = "animeijin-watch/1.0 (+github-actions; uptime check)"
STATE_VER = 3
STATE_BRANCH = "state"
RECHECK_SEC = 180                # 1回の実行の中で、異常ならこれだけ待ってもう一度確かめる
REMIND_FIRST_SEC = 3 * 3600      # 念押しの間隔（最初の24時間）
REMIND_LATER_SEC = 24 * 3600     # 念押しの間隔（24時間を過ぎたら）
QUOTA_KEEP = 10                  # LINE の月の枠の残りがこれ以下なら念押しは送らない（最初の知らせと「直った」は送る）
WRITE_STALE_SEC = 900            # 計測の書き込みがこれ以上止まっていたら異常（書けないときだけ伸びる値）
RETRY_KEY_TTL = 23 * 3600        # LINE の再送用の番号が効くのは24時間＝それより古い予定は番号を作り直す
BG_NAMES = ("expiry", "cleanup", "stats", "refund")
KINDS = ("alert", "remind", "recovered")
T0 = time.monotonic()
REQ_SEC = 15                     # 1回の本番への通信の絶対の上限（応答が少しずつ届き続けても打ち切る）
# 確認に使ってよい時間＝1回目（3通信）＋待ち＋2回目（3通信）＋余裕。3通信とも時間切れになる全面停止でも2回目まで確かめられる
CHECK_BUDGET_SEC = 3 * REQ_SEC + RECHECK_SEC + 3 * REQ_SEC + 30
RUN_LIMIT_SEC = 540              # 実行全体の上限（workflow の上限10分）。これを過ぎそうなら通知は次の回に回す
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class Deadline(Exception):
    pass


def _alarm(signum, frame):
    raise Deadline()


_HAS_ALARM = hasattr(signal, "setitimer")
if _HAS_ALARM:
    signal.signal(signal.SIGALRM, _alarm)


def within(sec, fn):
    """fn を最大 sec 秒で打ち切る（Linux の runner では絶対の期限。手元の Windows ではソケットの timeout だけ）。"""
    if _HAS_ALARM:
        signal.setitimer(signal.ITIMER_REAL, max(0.5, sec))
    try:
        return fn()
    finally:
        if _HAS_ALARM:
            signal.setitimer(signal.ITIMER_REAL, 0)


def fetch(url, method="GET", headers=None, data=None, sec=20, limit=2_000_000):
    """(status, body)。通信の失敗・時間切れは (None, b"")。"""
    req = urllib.request.Request(url, method=method, data=data, headers=headers or {})

    def go():
        try:
            with urllib.request.urlopen(req, timeout=sec) as r:
                return r.status, (r.read(limit) if method != "HEAD" else b"")
        except urllib.error.HTTPError as e:
            try:
                return e.code, e.read(limit)
            except Exception:
                return e.code, b""
    try:
        return within(sec, go)
    except (Deadline, Exception):
        return None, b""


# ---------------- 本番の確認 ----------------
def site(method, path):
    sep = "&" if "?" in path else "?"
    return fetch(f"{SITE}{path}{sep}_w={int(time.time())}", method,          # 途中のキャッシュの古い応答を見ないように毎回変える
                 {"User-Agent": UA, "Cache-Control": "no-cache"}, sec=REQ_SEC)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and 0 <= v < 10 ** 9


def check_once():
    """異常の理由のリストを返す（空＝正常）。項目の欠落・型の違いも異常にする（黙って正常にしない）。"""
    bad = []
    code, _ = site("HEAD", "/")
    if code != 200:
        bad.append(f"トップページが開かない（{code}）")
    code, _ = site("GET", "/api/packs")
    if code != 200:
        bad.append(f"ヘルスチェックの入口が応答しない（{code}）")
    code, body = site("GET", "/api/status")
    if code != 200:
        bad.append(f"状態の窓口が応答しない（{code}）")
        return bad
    try:
        d = json.loads(body)
    except Exception:
        d = None
    if not isinstance(d, dict):
        bad.append("状態の窓口の中身が読めない")
        return bad
    err = d.get("stat_err")
    if not isinstance(err, str):
        bad.append("状態の窓口に書き込みの印（stat_err）が無い")
    elif err.startswith("write:"):
        bad.append("DBへの書き込みが失敗している")
    age = d.get("stat_write_age_sec")
    if age is None:
        bad.append("計測の書き込みの記録が無い（起動直後でなければ異常）")
    elif not _is_num(age):
        bad.append("計測の書き込みの経過時間が読めない")
    elif age > WRITE_STALE_SEC:
        bad.append(f"計測の書き込みが{int(age) // 60}分止まっている（DBに書けていない疑い）")
    if d.get("history_available") is not True:
        bad.append("履歴を読み込めない（生成の受付が止まる）")
    if d.get("stat_thread_alive") is not True:
        bad.append("計測のスレッドが止まっている")
    # 裏の仕事4本（2026-10-01 の反映で /api/status に pid と bg が入る）。pid がある版では必ず4本そろって alive=true
    if "pid" in d:
        bg = d.get("bg")
        if not isinstance(bg, dict):
            bad.append("裏の仕事の状態が読めない")
        else:
            dead = [k for k in BG_NAMES if not (isinstance(bg.get(k), dict) and bg[k].get("alive") is True)]
            if dead:
                bad.append("裏の仕事が止まっている（" + "・".join(dead) + "）")
    return bad


def check():
    """("ok"|"bad"|"incomplete", 理由のリスト)。時間は確認を始めた時点から数える（記録の読み込みの時間は含めない）。"""
    c0 = time.monotonic()
    bad = check_once()
    if not bad:
        return "ok", []
    print("1回目の確認で異常（3分後にもう一度確かめる）:")
    for x in bad:
        print("  -", x.split("（")[0])                   # 公開ログには決まった文言だけ
    need = RECHECK_SEC + 3 * REQ_SEC + 5
    if CHECK_BUDGET_SEC - (time.monotonic() - c0) < need:
        return "incomplete", bad                    # 2回目を確かめる時間が無い＝異常と決めない
    time.sleep(RECHECK_SEC)
    bad = check_once()
    return ("bad", bad) if bad else ("ok", [])


# ---------------- LINE ----------------
def line_send(text, key):
    """"ok"＝LINE が受け取った（409＝同じ番号で受け取り済みも含む）／"retry"＝次の回に送り直す／"drop"＝送り直しても通らない。"""
    tok, to = os.environ.get("LINE_TOKEN", ""), os.environ.get("LINE_TO", "")
    if not tok or not to:
        print("LINE の鍵か宛先が設定されていない")
        return "retry"
    body = json.dumps({"to": to, "messages": [{"type": "text", "text": text[:4800]}]}).encode()
    for a in range(3):
        code, _ = fetch("https://api.line.me/v2/bot/message/push", "POST",
                        {"Authorization": "Bearer " + tok, "Content-Type": "application/json", "X-Line-Retry-Key": key},
                        body, sec=15, limit=10_000)
        if code in (200, 409):
            return "ok"
        print("LINE 送信失敗", code)
        if code == 400:
            return "drop"                           # 本文や番号がおかしい＝何度送っても通らない（後ろの予定を止めない）
        if code in (401, 403):
            return "retry"                          # 鍵の問題＝直るまで予定は残す
        time.sleep(3 * (a + 1))
    return "retry"


def line_quota_left():
    """LINE の今月の残り通数（分からなければ None）。"""
    tok = os.environ.get("LINE_TOKEN", "")
    if not tok:
        return None
    h = {"Authorization": "Bearer " + tok}
    try:
        c1, b1 = fetch("https://api.line.me/v2/bot/message/quota", headers=h, sec=10, limit=100_000)
        c2, b2 = fetch("https://api.line.me/v2/bot/message/quota/consumption", headers=h, sec=10, limit=100_000)
        q, u = json.loads(b1), json.loads(b2)
        if c1 != 200 or c2 != 200 or q.get("type") != "limited":
            return None
        return int(q.get("value", 0)) - int(u.get("totalUsage", 0))
    except Exception:
        return None


# ---------------- 記録（state ブランチの state.json） ----------------
def blank():
    return {"ver": STATE_VER, "fails": 0, "alerted": False, "down_since": None, "alert_at": 0, "outbox": []}


def _valid_ts(v):
    return isinstance(v, int) and not isinstance(v, bool) and 1_600_000_000 <= v <= 4_000_000_000


def _valid_msg(m):
    return (isinstance(m, dict) and isinstance(m.get("text"), str) and m["text"].strip() != ""
            and isinstance(m.get("key"), str) and UUID_RE.match(m["key"]) is not None
            and _valid_ts(m.get("made")) and m.get("kind") in KINDS)


def last_kind(outbox):
    """送る予定のうち、いちばん後ろの「止まった／念押し」（down）か「直った」（up）か。どちらも無ければ None。"""
    k = None
    for m in outbox:
        k = "down" if m["kind"] in ("alert", "remind") else ("up" if m["kind"] == "recovered" else k)
    return k


def normalize(raw):
    """(記録, 読めたか)。項目ごとに確かめ、壊れた項目は初期値に。送る予定は形の合うものだけ残す（直せないものは捨てて数える）。
    「止まった」「念押し」の予定が残っていれば、その障害はまだ知らせた扱い（直ったら「直った」も送る）。"""
    st, ok = blank(), True
    if not isinstance(raw, dict) or raw.get("ver") != STATE_VER:
        ok = False
        raw = raw if isinstance(raw, dict) else {}
    f = raw.get("fails")
    if isinstance(f, int) and not isinstance(f, bool) and 0 <= f < 10 ** 6:
        st["fails"] = f
    else:
        ok = False
    if isinstance(raw.get("alerted"), bool):
        st["alerted"] = raw["alerted"]
    else:
        ok = False
    ds = raw.get("down_since")
    if ds is None or _valid_ts(ds):
        st["down_since"] = ds
    else:
        ok = False
    aa = raw.get("alert_at")
    if aa == 0 or _valid_ts(aa):
        st["alert_at"] = aa
    else:
        ok = False
    box = raw.get("outbox") if isinstance(raw.get("outbox"), list) else []
    if not isinstance(raw.get("outbox"), list):
        ok = False
    good = [m for m in box if _valid_msg(m)]
    if len(good) != len(box):
        ok = False
        print(f"送る予定のうち {len(box) - len(good)} 件は形が壊れていて捨てた")
    st["outbox"] = [{k: m[k] for k in ("text", "key", "made", "kind")} for m in good]
    # 記録が壊れていたときだけの救済: 「止まった」を送る予定が残っていて、その後ろに「直った」が無い＝まだ知らせた扱い
    if not ok and last_kind(st["outbox"]) == "down" and not st["alerted"]:
        st["alerted"] = True
        if st["down_since"] is None:
            st["down_since"] = min(m["made"] for m in st["outbox"])
    return st, ok


class Store:
    """このリポジトリの state ブランチの state.json を GitHub の API で読み書きする。"""

    def __init__(self):
        self.repo = os.environ.get("GITHUB_REPOSITORY", "")
        self.tok = os.environ.get("GITHUB_TOKEN", "")
        self.sha = None

    def _h(self):
        return {"Authorization": "Bearer " + self.tok, "Accept": "application/vnd.github+json", "User-Agent": UA}

    def load(self):
        """(記録, 読めたか)。"""
        if not (self.repo and self.tok):
            print("記録の置き場が設定されていない")
            return blank(), False
        code, body = fetch(f"https://api.github.com/repos/{self.repo}/contents/state.json?ref={STATE_BRANCH}", headers=self._h())
        if code == 404:
            print("前回の記録なし（初回）")
            return blank(), False
        try:
            j = json.loads(body)
            self.sha = j["sha"]
            raw = json.loads(base64.b64decode(j["content"]).decode("utf-8"))
        except Exception:
            print("前回の記録を読めない")
            return blank(), False
        st, ok = normalize(raw)
        if not ok:
            print("前回の記録の一部が壊れていた")
        return st, ok

    def save(self, st):
        """書けたら True。"""
        if not (self.repo and self.tok):
            return False
        data = json.dumps(st, ensure_ascii=False, sort_keys=True).encode("utf-8")
        for a in range(2):
            body = {"message": "見張りの記録を更新", "branch": STATE_BRANCH,
                    "content": base64.b64encode(data).decode("ascii")}
            if self.sha:
                body["sha"] = self.sha
            code, resp = fetch(f"https://api.github.com/repos/{self.repo}/contents/state.json", "PUT", self._h(),
                               json.dumps(body).encode(), limit=200_000)
            if code in (200, 201):
                try:
                    self.sha = json.loads(resp)["content"]["sha"]
                except Exception:
                    self.sha = None
                return True
            print("記録を書けなかった", code)
            if code in (409, 422):                  # 置き場の中身が変わっていた＝今の sha を取り直してもう1回
                c2, b2 = fetch(f"https://api.github.com/repos/{self.repo}/contents/state.json?ref={STATE_BRANCH}", headers=self._h())
                try:
                    self.sha = json.loads(b2)["sha"] if c2 == 200 else None
                except Exception:
                    self.sha = None
                continue
            return False
        return False


def jst(ts):
    try:
        return time.strftime("%m/%d %H:%M", time.gmtime(int(ts) + 9 * 3600))
    except Exception:
        return "?"


def queue(st, text, kind):
    st["outbox"].append({"text": text, "key": str(uuid.uuid4()), "made": int(time.time()), "kind": kind})


def flush_outbox(st, store):
    """送る予定を古い順に送る。送れた・捨てたものはその都度消して記録を書く。(捨てた件数, 記録を書けたか)。"""
    dropped, saved = 0, True
    for m in list(st["outbox"]):
        if time.monotonic() - T0 > RUN_LIMIT_SEC - 90:   # 1通の送信と記録の書き込みに要る時間を残す
            print("時間が足りないので残りの通知は次の回に送る")
            break
        now = int(time.time())
        if now - m["made"] > RETRY_KEY_TTL:           # 番号が切れる＝作り直す。**新しい番号を記録に書いてから**送る
            m["key"], m["made"] = str(uuid.uuid4()), now
            if not store.save(st):
                print("新しい番号を記録に書けなかった＝送らずに次の回へ（書けないまま送ると二重に届き得る）")
                return dropped, False
        if m["kind"] == "remind":
            q = line_quota_left()
            if q is not None and q <= QUOTA_KEEP:
                print("LINE の月の枠が残り少ないので念押しは送らない")
                st["outbox"].remove(m)
                saved = store.save(st) and saved
                continue
        r = line_send(m["text"], m["key"])
        if r == "ok":
            st["outbox"].remove(m)
            print("通知を送った（" + m["kind"] + "）")
            saved = store.save(st) and saved
        elif r == "drop":
            st["outbox"].remove(m)
            dropped += 1
            print("通知を送れない形だったので捨てた（" + m["kind"] + "）")
            saved = store.save(st) and saved
        else:
            print("通知を送れなかった（" + m["kind"] + "）＝次の回に送り直す")
            break
    return dropped, saved


def main():
    if os.environ.get("WATCH_MODE") == "test":
        r = line_send("🧪【見張りのテスト送信】アニ名人の10分おきの見張りを作りました。本番が止まったら、このLINEに知らせます"
                      "（直ったらもう1通）。このメッセージへの返信は不要です。", str(uuid.uuid4()))
        print("テスト送信", r)
        sys.exit(0 if r == "ok" else 1)
    store = Store()
    st, readable = store.load()
    before = json.dumps(st, sort_keys=True)
    result, bad = check()
    now = int(time.time())
    if result == "incomplete":
        print("確認できず（時間が足りず2回目を確かめられなかった）")
    elif result == "bad":
        prev = st["fails"]
        st["fails"] = prev + 1
        if st["down_since"] is None:
            st["down_since"] = now
        print("異常（" + str(st["fails"]) + "回目）:")
        for b in bad:
            print("  -", b.split("（")[0])                 # 公開ログには決まった文言だけ
        since = st["down_since"]
        body = "\n".join("・" + b for b in bad)
        if not st["alerted"] and (prev >= 1 or not readable):
            why = "10分おきの確認で続けて異常でした。" if prev >= 1 else "3分おいた2回の確認で続けて異常でした（前回の記録は読めず）。"
            queue(st, f"🚨【アニ名人の見張り】本番が止まっているかもしれません（{jst(now)}・最初に異常を見つけたのは {jst(since)}）\n"
                      f"{body}\n{why}PCでClaudeを開いて「アニ名人の見張りが鳴った」と伝えてください。", "alert")
            st["alerted"], st["alert_at"] = True, now        # 予定にした時点で「知らせた」扱い（直ったら必ず「直った」も送る）
        elif st["alerted"]:
            gap = REMIND_FIRST_SEC if now - since < 24 * 3600 else REMIND_LATER_SEC
            if now - (st["alert_at"] or now) >= gap:
                queue(st, f"🚨【アニ名人の見張り】まだ異常が続いています（{jst(now)}・最初に異常を見つけてから約{(now - since) // 60}分）\n"
                          f"{body}\nPCでClaudeを開いて「アニ名人の見張りが鳴った」と伝えてください。", "remind")
                st["alert_at"] = now
    else:
        print("正常")
        if st["alerted"] and last_kind(st["outbox"]) != "up":    # 「直った」を送る予定が既にあれば重ねない
            queue(st, f"✅【アニ名人の見張り】本番が元に戻りました（{jst(now)}確認・最初に異常を見つけたのは {jst(st['down_since'] or now)}）",
                  "recovered")
        st.update({"fails": 0, "alerted": False, "down_since": None, "alert_at": 0})
    saved = True
    if json.dumps(st, sort_keys=True) != before or not readable:
        saved = store.save(st)                           # 送る前に記録を書く（書けたかを API の応答で確かめる）
        if not saved:
            print("記録を書けなかった（通知は送る＝黙らない側。次の回に二重に届く可能性がある）")
    dropped = 0
    if st["outbox"]:
        dropped, s2 = flush_outbox(st, store)
        saved = saved and s2
    # 送れていない予定・書けていない記録・送れない形で捨てた通知がある＝この回は失敗（GitHub の実行一覧に赤く残る）
    rc = 1 if (st["outbox"] or not saved or dropped) else 0
    sys.exit(rc)


if __name__ == "__main__":
    main()
