# -*- coding: utf-8 -*-
"""アニ名人（animeijin.com）とバズ名人！（buzzmeijin.com）の見張り。GitHub Actions から10分おきに1回動く短いプログラム（AI は使わない）。
（GitHub の定時実行は実際には3〜9時間おきに間引かれる。10分おきの主役はサブPC の「つなぎ」run_local.py＝同じこのファイルを動かす）

外からお客様と同じようにアクセスして、次を確かめる（読むだけ。本番のデータは作らない・変えない）:
  アニ名人
    1. トップページが開くか（HEAD＝本体は受け取らない）
    2. ヘルスチェックの入口 /api/packs が 200 か
    3. 公開の状態窓口 /api/status で、DB への書き込みが失敗していないか・履歴が読めるか・裏の仕事が動いているか
  バズ名人！（2026-11-04 追加・統合計画 N02）
    4. /healthz が 200 で {"ok": true, ...} か（Render のヘルスチェック先。匿名の利用者は作らない）
    5. /pricing が 200 で、料金の表があるか（テンプレートを描くだけ。DB に触らない）
    ※バズ名人！へは UA に monitor を入れる（BUZZ_UA＝本番の訪問の数に入らない）
    6. /healthz の fetch_workers（動画を取りに行く自宅PCの取得ワーカーの数）が0でないか
    ⚠️/api/me など匿名の利用者が作られる口は叩かない。

判定と通知（サイトごとに別々に記録する＝片方が直っても、もう片方の「直った」は出さない）:
  ①サイトが落ちている（アニ名人は 1〜3、バズ名人！は 4・5 のどれか）
  - 1回の実行の中で、異常なら3分おいてもう一度確かめる。2回とも異常＝この回は「異常」。時間が足りず確かめきれなかった回は
    「確認できず」（異常にも正常にも数えない＝見張り側の都合を本番の障害として知らせない）。
  - 前の回も異常だった（約10〜15分続いている）ら LINE で知らせる。前の回の記録が読めないときは、この回だけで知らせる
    （記録が壊れても「黙って知らせない」側に倒れないように）。
  - 続いていれば念押し（最初の24時間は3時間ごと・以降は1日1回。LINE の月の枠が残り少なければ念押しは送らない）。
  - 直ったら「直った」を1通。
  ②バズ名人！の取得ワーカーが0台（サイトは動いている）
  - 0台の間は「動画のリンクから作る」が受け付けで断られる（クレジットは取らない＝お金の事故にはならない）。
    **続けて15分以上0台**のときだけ知らせる（2026-11-05 に60分から縮めた。理由＝取得ワーカーが NGO（常時起動）とメインPCの
    2台になり、0台＝両方止まった＝本当に困っている。一瞬の0は本番の側で90秒の猶予（FETCH_ALIVE_SEC）と再起動の猶予が
    吸い、Claude がワーカーを入れ替える数分・NGO の Windows Update の再起動（5〜15分）は15分で吸う。60分のままでは
    バズった日に1時間以上リンクから作れないまま気づけない）。0台が始まった時刻は、本番の
    fetch_worker_last_sec（どれかのワーカーが最後に来てからの秒数）を正とする（見張りの回の間に一瞬でも来ていれば、
    そこから数え直す）。本番が秒数を出せない（再起動の後に一度も来ていない等）ときは、見張りが0台を最初に見た時刻から数える。
  - 「15分」を数え始めるのは、見張りが最後に /healthz の異常（2回の確認で続けて異常、または落ちていて確かめきれなかった回）を
    見た時刻より後から（サイトが落ちている間はワーカーもつながれない＝サイトが戻った直後の「長く来ていない」を②に数えない）。
    その回の1回目で /healthz が落ちていた回は②を数えない（3分以内に戻った揺れでは数え始めは動かさない）。料金のページだけの
    異常では②は止めない。
  - 15分を超えていそうなら①と同じく3分おいて確かめ直し、それでも0台なら知らせる。
  - 知らせた件は、1台以上を見るまで閉じない（回の間に一瞬だけ来て、また0台になっても「戻った」も新しい「止まった」も出さない）。
    念押しは①と同じ間隔で、今の0台が15分以上続いているときだけ。戻ったら「戻った」を1通。
  - 念押しの間隔は、件を知らせてから24時間までは3時間ごと・以降は1日1回（①と同じ）。
  - 新しい件の「止まった」は、前の②の知らせ（止まった・念押し・戻った）から6時間たっていれば15分で出す。6時間たっていなく
    ても、新しい件が60分続いたら1回だけ出す（2026-11-05 改。前は6時間あけるだけ＝一度鳴って「戻った」の直後に始まった本当の
    停止〔直したつもりがまた落ちた、など〕が約5.5時間黙った。60分なら前の版より遅れない）。この「もう1回」で知らせた件が
    戻った後は、6時間たつまで出さない（ノートPCを開いたり閉じたりして0台を繰り返すときに連打しない）。②はお金の事故では
    ないので遅れてよい。LINE の月の枠（無料の月200通・ほかの用途と共有）が残り10通以下なら、②の知らせは送らない
    （①の分を残す。「止まった」を捨てた件の「戻った」だけが届かないように、②は全部）。
  - 夜の Windows Update などで2台とも止まり、0台が約20〜30分を超えると、「止まった」「戻った」の2通が届く（内容は正しい）。
  - ⚠️限界：NGO は見張り（つなぎ）と取得ワーカーを兼ねる＝NGO ごと止まった（ノートPCも寝ている）ときは、GitHub の回
    （3〜9時間おき）でしか気づけない。GitHub だけが知らせた件の「戻った」も次の GitHub の回まで遅れる（①も同じ）。
  - ②の知らせの再送用の番号は、本番の秒数から出した0台の始まり（15分単位＝しきい値以下にして、別の件が同じ番号にならない
    ようにする）と念押しの周期から決まる番号にする＝GitHub とサブPCのつなぎの両方が同じ件を送っても、LINE が後の方を
    「受け取り済み」（409）にして二重に届かない（同じ LINE チャンネル）。「戻った」と念押しの番号は、知らせたときの区切り（w_key）
    から作る（回の間に一瞬来て0台の始まりが動いても、前の件と同じ番号にならない）。念押しには今の0台の始まりの区切りも入れる
    （一瞬来て念押しの周期が数え直しになっても、前の念押しと同じ番号にならない）。
  見張り側の回線
  - 両方のサイトへの通信が全部「応答なし」のときは、外のサイト（Google・Cloudflare）にも届くか確かめる。届かなければ
    見張り側の回線が切れている＝「確認できず」（両方の「止まった」「直った」を誤って出さない）。
  共通
  - 記録（state.json）はこのリポジトリの `state` ブランチに GitHub の API で書く（書けたことを確かめてから LINE を送る）。
    書くのは中身が変わったときだけ（ふだんの正常な回は書かない）。
  - 送る通知は「送る予定（outbox）」に本文と再送用の番号（X-Line-Retry-Key）ごと記録してから送る。送れなかったものは次の回に
    同じ本文・同じ番号で送り直す（LINE が受け取っていれば二重に届かない）。直っても捨てない。
  - 記録の形（ver 3）は前の版のまま。足したのは "buzz"（バズ名人！の記録）と、送る予定の "ch"（どのサイトの知らせか。
    無ければアニ名人）だけ＝前の版の記録をそのまま読める。
  - バズ名人！の確認・判定で例外が出た回は、アニ名人の分だけ進めて rc=1（GitHub の実行一覧に赤く残る＝黙って見なくならない）。

確かめ用の道（本番の LINE に送らない）:
  - WATCH_MODE=dry … 本番を確かめて結果を出すが、LINE は送らず（送る予定は「送らない」と出すだけ）、記録も書かない。
  - WATCH_DRY_LINE=1 … LINE に送る代わりに標準出力へ（WATCH_DRY_SHOW_TEXT=1 なら本文も）。記録は書く。
  - WATCH_DRY_QUOTA=<数> … LINE の残り枠を問い合わせずにこの数にする（WATCH_DRY_LINE / dry のとき）。
  - WATCH_NOW=<UNIX秒> … 今の時刻を差し替える（記録・判定・本文の時刻。本番への通信の時間切れは本物の時計）。

⚠️検知の限界（2026-09-30 Codex レビュー）: /api/status の書き込みの印（stat_err の write:・stat_write_age_sec）は
「書き込みを試みて失敗したとき」に出る。利用がある間は1分ごとに試みるので、書けなくなってからおおむね15〜25分で知らせる。
誰も使っていない深夜は1時間ごとの定期書き込みまで気づけない（通常の実行間隔なら最長で約90分・GitHub の定時実行は遅れる・
抜けることがある＝保証ではない）。本番に「数分おきに必ず書く」確認口を足すのは第2段。
公開ログ（誰でも見られる）には、決まった文言だけを出す（本番のエラー文・通知の本文は出さない）。
"""
import base64
import copy
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
BUZZ = "https://buzzmeijin.com"
UA = "animeijin-watch/1.0 (+github-actions; uptime check)"
# バズ名人！へは UA に monitor を入れる（本番の _BOT_RE に当たる＝訪問・画面の計器に数えない。2026-11-05 統合計画 N02）
BUZZ_UA = "buzzmeijin-healthcheck/1.0 monitor (+animeijin-watch; uptime check)"
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
CHANNELS = ("anime", "buzz", "buzzw")   # 送る予定の印：アニ名人／バズ名人！のサイト／バズ名人！の取得ワーカー
CH_NAME = {"anime": "アニ名人", "buzz": "バズ名人！", "buzzw": "バズ名人！の取得ワーカー"}
WORKER_ALERT_SEC = 900           # バズ名人！の取得ワーカーがこれ以上続けて0台なら知らせる（2026-11-05 60分→15分・理由は冒頭）
FETCH_ALIVE_SEC = 90             # バズ名人！がワーカーを「生きている」と数える秒数（config.FETCH_WORKER_ALIVE_SEC と同じ）
SAME_SINCE_SEC = 120             # 0台が始まった時刻の見当がこれ以内しか動かないなら記録を書き換えない（毎回書かない。しきい値15分に合わせて300→120）
W_NEW_GAP_SEC = 6 * 3600         # ②の新しい件の「止まった」は、前の②の知らせからこれだけあける（この間に1回だけ例外）
WORKER_AGAIN_SEC = 3600          # その例外：6時間の中でも、新しい件がこれだけ続いたら1回だけ知らせる
# ②の再送用の番号を決める0台の始まりの区切り（2か所の時計の数秒のずれで番号が割れにくいように）。しきい値以下にする
# （別の件の始まりは必ずしきい値以上離れる＝区切りがこれ以下なら別の件の番号が重ならない）
KEY_BUCKET_SEC = min(900, WORKER_ALERT_SEC)
PRICE_RE = re.compile(r"[0-9][0-9,]*\s*円|¥\s*[0-9]")
T0 = time.monotonic()
_CODES = []                      # この回の本番への通信の応答コード（None＝応答なし）。見張り側の回線の確かめに使う
_BUZZ_ERR = []                   # バズ名人！の確認・判定で出た例外（あれば rc=1）
REQ_SEC = 15                     # 1回の本番への通信の絶対の上限（応答が少しずつ届き続けても打ち切る）
# 1回の確認（それぞれの口で通信失敗なら3秒おいて1回やり直す）にかかる最長の時間。アニ名人3か所・バズ名人！2か所
ANIME_CHECK_MAX_SEC = 3 * (2 * REQ_SEC + 3)
BUZZ_CHECK_MAX_SEC = 2 * (2 * REQ_SEC + 3)
ONE_CHECK_MAX_SEC = ANIME_CHECK_MAX_SEC + BUZZ_CHECK_MAX_SEC
NET_SEC = 10                     # 見張り側の回線の確かめ（外のサイト2か所・各この秒数まで）
NET_MAX_SEC = 2 * NET_SEC
NET_URLS = ("https://www.google.com/generate_204", "https://www.cloudflare.com/cdn-cgi/trace")
# 確認に使ってよい時間＝1回目＋回線の確かめ＋待ち＋2回目＋回線の確かめ＋余裕。両方のサイトの全部の通信が時間切れになる
# 全面停止でも2回目まで確かめられる
CHECK_BUDGET_SEC = ONE_CHECK_MAX_SEC + NET_MAX_SEC + RECHECK_SEC + ONE_CHECK_MAX_SEC + NET_MAX_SEC + 30
# 実行全体の上限（workflow の上限17分）。記録の読み込み（〜20秒）＋確認（〜570秒）＋記録の書き込み（〜60秒）の後でも、
# 通知を送り始められるように（送り始める期限＝これ−90秒）。これを過ぎそうなら通知は次の回に回す
RUN_LIMIT_SEC = 780
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


def now_ts():
    """今の時刻（UNIX秒）。確かめ用に WATCH_NOW で差し替えられる。"""
    v = os.environ.get("WATCH_NOW", "")
    if v:
        try:
            return int(v)
        except ValueError:
            pass
    return int(time.time())


def _dry():
    return os.environ.get("WATCH_MODE") == "dry" or os.environ.get("WATCH_DRY_LINE") == "1"


# ---------------- 本番の確認 ----------------
def site(method, path, base=SITE):
    """本番への1回の確認。通信そのものの失敗（応答なし）は3秒おいて1回だけやり直す（2026-10-01：本番に届く前の一瞬の揺れを
    異常に数えないため。本番が返した 4xx/5xx はやり直さない＝そのまま異常）。"""
    for attempt in range(2):
        sep = "&" if "?" in path else "?"
        code, body = fetch(f"{base}{path}{sep}_w={int(time.time())}", method,   # 途中のキャッシュの古い応答を見ないように毎回変える
                           {"User-Agent": BUZZ_UA if base == BUZZ else UA, "Cache-Control": "no-cache"}, sec=REQ_SEC)
        if code is not None:
            _CODES.append(code)
            return code, body
        if attempt == 0:
            time.sleep(3)
    _CODES.append(code)
    return code, body


def net_ok():
    """見張り側の回線が外に届くか（外のサイトのどれかが何か返せば True）。"""
    for u in NET_URLS:
        code, _ = fetch(u, headers={"User-Agent": UA}, sec=NET_SEC, limit=10_000)
        if code is not None:
            return True
    return False


def watcher_offline():
    """この確認で本番への通信が全部「応答なし」で、外のサイトにも届かない＝見張り側の回線が切れている。"""
    if not _CODES or any(c is not None for c in _CODES):
        return False
    if net_ok():
        return False
    print("見張り側の回線が切れている疑い（両方のサイトにも外のサイトにも届かない）＝この回は確認できず")
    return True


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and 0 <= v < 10 ** 9


def check_once():
    """アニ名人。異常の理由のリストを返す（空＝正常）。項目の欠落・型の違いも異常にする（黙って正常にしない）。"""
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


def _code(c):
    return "応答なし" if c is None else str(c)


def buzz_once():
    """バズ名人！の1回の確認。{"down": サイトが落ちている理由のリスト（空＝動いている）, "fw": 取得ワーカーの数（読めなければ None）,
    "last": 最後にワーカーが来てからの秒数（無ければ None）, "hz_down": /healthz が落ちていたか, "at": 見た時刻}。
    hz_down のときの fw・last は使わない。"""
    down, d = [], None
    code, body = site("GET", "/healthz", BUZZ)
    at = now_ts()                         # 本番が last を数えた時点に近い時刻（/pricing を待った時間を入れない）
    if code != 200:
        down.append(f"状態の窓口（/healthz）が応答しない（{_code(code)}）")
    else:
        try:
            d = json.loads(body)
        except Exception:
            d = None
        if not isinstance(d, dict) or d.get("ok") is not True:
            down.append("状態の窓口（/healthz）が正常を返さない")
            d = None
    hz_down = d is None
    code, body = site("GET", "/pricing", BUZZ)
    if code != 200:
        down.append(f"料金のページが開かない（{_code(code)}）")
    elif b"<table" not in body or not PRICE_RE.search(body.decode("utf-8", "replace")):
        down.append("料金のページに料金の表が無い")
    fw = last = None
    if d is not None:
        v = d.get("fetch_workers")
        fw = v if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 10 ** 6 else None
        v = d.get("fetch_worker_last_sec")
        last = int(v) if _is_num(v) else None
    return {"down": down, "hz_down": hz_down, "fw": fw, "last": last, "at": at}


def zero_since(obs, prev):
    """取得ワーカーの0台が始まった時刻の見当（1台以上なら None）。prev＝記録にある前の見当。
    本番の「最後に来てからの秒数」があればそれを正とする（＝見張りの回の間にワーカーが来ていれば、そこから数え直す）。
    見当が前と SAME_SINCE_SEC 以内しか違わなければ前の値のまま（毎回記録を書き換えない）。
    数が読めない・本番が秒数を出せないときは、前の見当（無ければ見た時刻）から数える。
    ⚠️ここには「サイトの異常を見た時刻」を混ぜない（再送用の番号を GitHub とつなぎでそろえるため。15分の判断だけ別に下限をかける）。"""
    fw, last, at = obs.get("fw"), obs.get("last"), obs["at"]
    if fw is not None and fw >= 1:
        return None
    if fw == 0 and last is not None:
        zs = at - max(0, last - FETCH_ALIVE_SEC)
        if prev is not None and abs(zs - prev) < SAME_SINCE_SEC:
            zs = prev
        return zs
    return prev if prev is not None else at


def zero_counted(zs, b):
    """15分（WORKER_ALERT_SEC）を数え始める時刻＝0台の始まりと、最後に /healthz の異常を見た時刻の遅い方。"""
    return max(zs, b["w_floor"]) if b.get("w_floor") is not None else zs


def new_inc_need(b, at):
    """新しい件の「止まった」に要る0台の長さ（秒）。None＝今は出さない。
    前の②の知らせから6時間たった＝15分／たっていないが、前の件が「もう1回」で知らせた件でない＝60分／それ以外＝出さない。"""
    if at - (b.get("w_note_at") or 0) >= W_NEW_GAP_SEC:
        return WORKER_ALERT_SEC
    if not b.get("w_second"):
        return WORKER_AGAIN_SEC
    return None


def workers_alarming(obs, b):
    """この観測で、まだ知らせていない0台が知らせる長さ（ふだん15分）以上になっているか（3分おいて確かめ直すかの判断に使う）。b＝記録のバズ名人！の分。"""
    need = new_inc_need(b, obs["at"])
    if obs.get("hz_down") or b["w_alerted"] or need is None:
        return False                      # 知らせ済み・前の知らせから6時間たっていない＝確かめ直しても送らない
    zs = zero_since(obs, b["w_since"])
    return zs is not None and obs["at"] - zero_counted(zs, b) >= need


def check(b_state=None):
    """{"anime": (結果, 理由), "buzz": (結果, 観測)}。結果は "ok"|"bad"|"incomplete"。
    バズ名人！の "ok" はサイトが動いているという意味（取得ワーカーの数は観測の fw を見る）。
    1回目で異常な（または取得ワーカーが知らせる長さ〔ふだん15分・前の知らせから6時間以内は60分〕以上0台に見える）サイトだけ、
    3分おいてもう一度確かめる（待つのは1回だけ）。
    時間は確認を始めた時点から数える（記録の読み込みの時間は含めない）。b_state＝記録のバズ名人！の分（0台の数え方に使う）。
    バズ名人！の観測には "first_down"（この回の1回目でサイトが落ちていたか）・"first_hz_down"（同じく /healthz が）を足して返す。"""
    c0 = time.monotonic()
    b_state = b_state or blank_buzz()
    _CODES.clear()
    a_bad = check_once()
    try:
        b1 = buzz_once()
    except Exception as e:                           # バズ名人！の確認の不具合でアニ名人の見張りを止めない
        print("バズ名人！: 確認の途中で例外", type(e).__name__)
        _BUZZ_ERR.append(type(e).__name__)
        b1 = None
    if watcher_offline():
        return {"anime": ("incomplete", a_bad), "buzz": ("incomplete", None)}
    need_a = bool(a_bad)
    try:
        need_b = b1 is not None and (bool(b1["down"]) or workers_alarming(b1, b_state))
    except Exception as e:
        print("バズ名人！: 判定の途中で例外", type(e).__name__)
        _BUZZ_ERR.append(type(e).__name__)
        b1, need_b = None, False
    if b1 is not None:
        b1["first_down"], b1["first_hz_down"] = bool(b1["down"]), bool(b1["hz_down"])
    res = {"anime": ("ok", []), "buzz": ("ok", b1) if b1 is not None else ("incomplete", None)}
    if not need_a and not need_b:
        return res
    if need_a:
        print("アニ名人: 1回目の確認で異常（3分後にもう一度確かめる）:")
        for x in a_bad:
            print("  -", x)                              # 決まった文言と応答コード・分数だけ（本番のエラー文は入らない）
    if need_b:
        print("バズ名人！: 1回目の確認で異常（3分後にもう一度確かめる）:")
        for x in b1["down"] or [f"取得ワーカーが{(new_inc_need(b_state, b1['at']) or WORKER_ALERT_SEC) // 60}分以上0台に見える"]:
            print("  -", x)
    need = RECHECK_SEC + (ANIME_CHECK_MAX_SEC if need_a else 0) + (BUZZ_CHECK_MAX_SEC if need_b else 0) + 5
    if CHECK_BUDGET_SEC - (time.monotonic() - c0) < need:
        if need_a:                                   # 2回目を確かめる時間が無い＝異常と決めない
            res["anime"] = ("incomplete", a_bad)
        if need_b:
            res["buzz"] = ("incomplete", b1)
        return res
    time.sleep(RECHECK_SEC)
    _CODES.clear()
    if need_a:
        a_bad = check_once()
        res["anime"] = ("bad", a_bad) if a_bad else ("ok", [])
    b2 = None
    if need_b:
        try:
            b2 = buzz_once()
            b2["first_down"], b2["first_hz_down"] = b1["first_down"], b1["first_hz_down"]
        except Exception as e:
            print("バズ名人！: 確認の途中で例外", type(e).__name__)
            _BUZZ_ERR.append(type(e).__name__)
            b2 = None
    if watcher_offline():                            # 2回目だけ全部届かない＝見張り側の回線が切れた＝確かめ直した分は決めない
        if need_a:
            res["anime"] = ("incomplete", a_bad)
        if need_b:
            res["buzz"] = ("incomplete", b1)
        return res
    if need_b:
        if b2 is None:
            res["buzz"] = ("incomplete", b1)
        elif b2["down"]:
            # 1回目も落ちていた＝異常。1回目は動いていて2回目だけ落ちた＝1回きりの観測なので決めない
            res["buzz"] = ("bad", b2) if b1["down"] else ("incomplete", b2)
        else:
            res["buzz"] = ("ok", b2)                 # 2回目の観測で取得ワーカーも数える
    return res


# ---------------- LINE ----------------
def line_send(text, key, ch="anime", kind=""):
    """"ok"＝LINE が受け取った（409＝同じ番号で受け取り済みも含む）／"retry"＝次の回に送り直す／"drop"＝送り直しても通らない。"""
    if _dry():
        print(f"[送らない] LINE（{CH_NAME.get(ch, ch)}・{kind}）")
        if os.environ.get("WATCH_DRY_SHOW_TEXT") == "1":
            print(text)
        return "ok"
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
            if code == 409:
                print("LINE が同じ番号で受け取り済み（409＝二重には届かない）")
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
    if _dry():
        v = os.environ.get("WATCH_DRY_QUOTA", "")
        try:
            return int(v) if v else None
        except ValueError:
            return None
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
def blank_buzz():
    return {"fails": 0, "alerted": False, "down_since": None, "alert_at": 0,
            "w_since": None, "w_alerted": False, "w_alert_at": 0, "w_floor": None, "w_note_at": 0, "w_inc_at": 0,
            "w_key": None, "w_second": False}


def blank():
    return {"ver": STATE_VER, "fails": 0, "alerted": False, "down_since": None, "alert_at": 0, "outbox": [],
            "buzz": blank_buzz()}


def unread():
    return {"anime": False, "buzz": False}


def _valid_ts(v):
    return isinstance(v, int) and not isinstance(v, bool) and 1_600_000_000 <= v <= 4_000_000_000


def _valid_msg(m):
    return (isinstance(m, dict) and isinstance(m.get("text"), str) and m["text"].strip() != ""
            and isinstance(m.get("key"), str) and UUID_RE.match(m["key"]) is not None
            and _valid_ts(m.get("made")) and m.get("kind") in KINDS
            and m.get("ch", "anime") in CHANNELS)    # ch が無い＝前の版の予定＝アニ名人


def last_kind(outbox, ch="anime"):
    """そのサイトの送る予定のうち、いちばん後ろの「止まった／念押し」（down）か「直った」（up）か。どちらも無ければ None。"""
    k = None
    for m in outbox:
        if m.get("ch", "anime") != ch:
            continue
        k = "down" if m["kind"] in ("alert", "remind") else ("up" if m["kind"] == "recovered" else k)
    return k


def _norm_down(raw, s):
    """「止まった」の決まりの4項目（fails・alerted・down_since・alert_at）を raw から s へ。壊れていれば初期値のまま False。"""
    ok = True
    f = raw.get("fails")
    if isinstance(f, int) and not isinstance(f, bool) and 0 <= f < 10 ** 6:
        s["fails"] = f
    else:
        ok = False
    if isinstance(raw.get("alerted"), bool):
        s["alerted"] = raw["alerted"]
    else:
        ok = False
    ds = raw.get("down_since")
    if ds is None or _valid_ts(ds):
        s["down_since"] = ds
    else:
        ok = False
    aa = raw.get("alert_at")
    if aa == 0 or _valid_ts(aa):
        s["alert_at"] = aa
    else:
        ok = False
    return ok


def normalize(raw):
    """(記録, {"anime": 読めたか, "buzz": 読めたか})。項目ごとに確かめ、壊れた項目は初期値に。送る予定は形の合うものだけ残す
    （直せないものは捨てて数える）。「止まった」「念押し」の予定が残っていれば、その障害はまだ知らせた扱い（直ったら「直った」も送る）。
    前の版の記録（"buzz" が無い）は、アニ名人の分はそのまま読め、バズ名人！の分は「初回」になる。"""
    st, ok = blank(), True
    if not isinstance(raw, dict) or raw.get("ver") != STATE_VER:
        ok = False
        raw = raw if isinstance(raw, dict) else {}
    ver_ok = ok
    ok = _norm_down(raw, st) and ok
    box = raw.get("outbox") if isinstance(raw.get("outbox"), list) else []
    box_ok = isinstance(raw.get("outbox"), list)
    good = [m for m in box if _valid_msg(m)]
    if len(good) != len(box):
        box_ok = False
        print(f"送る予定のうち {len(box) - len(good)} 件は形が壊れていて捨てた")
    ok = ok and box_ok
    st["outbox"] = [{"text": m["text"], "key": m["key"], "made": m["made"], "kind": m["kind"], "ch": m.get("ch", "anime")}
                    for m in good]
    # バズ名人！の分（2026-11-04〜）
    b, rb = st["buzz"], raw.get("buzz")
    if isinstance(rb, dict):
        bok = _norm_down(rb, b) and ver_ok and box_ok
        ws = rb.get("w_since")
        if ws is None or _valid_ts(ws):
            b["w_since"] = ws
        else:
            bok = False
        if isinstance(rb.get("w_alerted"), bool):
            b["w_alerted"] = rb["w_alerted"]
        else:
            bok = False
        wa = rb.get("w_alert_at")
        if wa == 0 or _valid_ts(wa):
            b["w_alert_at"] = wa
        else:
            bok = False
        wf = rb.get("w_floor")
        if wf is None or _valid_ts(wf):
            b["w_floor"] = wf
        else:
            bok = False
        for k in ("w_note_at", "w_inc_at"):
            v = rb.get(k, 0)
            if v == 0 or _valid_ts(v):
                b[k] = v
            else:
                bok = False
        wk = rb.get("w_key")             # 2026-11-05〜。無い（前の版の記録）＝None＝今の0台の始まりから番号を作る
        if wk is None or (isinstance(wk, int) and not isinstance(wk, bool) and 0 <= wk < 10 ** 9):
            b["w_key"] = wk
        else:
            bok = False
        v = rb.get("w_second", False)    # 2026-11-05〜。無い（前の版の記録）＝False＝6時間の中の「もう1回」はまだ使える
        if isinstance(v, bool):
            b["w_second"] = v
        else:
            bok = False
    else:
        bok = False
        if "buzz" in raw:
            print("バズ名人！の前回の記録が壊れていた")
    # 記録が壊れていたときだけの救済: 「止まった」を送る予定が残っていて、その後ろに「直った」が無い＝まだ知らせた扱い
    def made_min(ch):
        return min(m["made"] for m in st["outbox"] if m["ch"] == ch)
    if not ok and last_kind(st["outbox"], "anime") == "down" and not st["alerted"]:
        st["alerted"] = True
        if st["down_since"] is None:
            st["down_since"] = made_min("anime")
    if not bok and last_kind(st["outbox"], "buzz") == "down" and not b["alerted"]:
        b["alerted"] = True
        if b["down_since"] is None:
            b["down_since"] = made_min("buzz")
    if not bok and last_kind(st["outbox"], "buzzw") == "down" and not b["w_alerted"]:
        b["w_alerted"] = True
        if b["w_since"] is None:
            b["w_since"] = made_min("buzzw") - WORKER_ALERT_SEC   # 知らせたのは0台が WORKER_ALERT_SEC 続いた後
    return st, {"anime": ok, "buzz": bok}


class Store:
    """このリポジトリの state ブランチの state.json を GitHub の API で読み書きする。"""

    def __init__(self):
        self.repo = os.environ.get("GITHUB_REPOSITORY", "")
        self.tok = os.environ.get("GITHUB_TOKEN", "")
        self.sha = None

    def _h(self):
        return {"Authorization": "Bearer " + self.tok, "Accept": "application/vnd.github+json", "User-Agent": UA}

    def load(self):
        """(記録, {"anime": 読めたか, "buzz": 読めたか})。"""
        if not (self.repo and self.tok):
            print("記録の置き場が設定されていない")
            return blank(), unread()
        code, body = fetch(f"https://api.github.com/repos/{self.repo}/contents/state.json?ref={STATE_BRANCH}", headers=self._h())
        if code == 404:
            print("前回の記録なし（初回）")
            return blank(), unread()
        try:
            j = json.loads(body)
            self.sha = j["sha"]
            raw = json.loads(base64.b64decode(j["content"]).decode("utf-8"))
        except Exception:
            print("前回の記録を読めない")
            return blank(), unread()
        st, ok = normalize(raw)
        if not ok["anime"]:
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


class LocalStore:
    """手元（PC）で動かすときの記録の置き場（GitHub の定時実行が動かない間のつなぎ・2026-10-01）。
    環境変数 WATCH_STATE_FILE のファイルに書く（一時ファイル→置き換え）。"""

    def __init__(self, path):
        self.path = path

    def load(self):
        try:
            raw = json.load(open(self.path, encoding="utf-8"))
        except FileNotFoundError:
            print("前回の記録なし（初回）")
            return blank(), unread()
        except Exception:
            print("前回の記録を読めない")
            return blank(), unread()
        return normalize(raw)

    def save(self, st):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            tmp = self.path + ".tmp"
            json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
            os.replace(tmp, self.path)
            return True
        except Exception:
            return False


class DryStore:
    """WATCH_MODE=dry のとき：記録は読むだけで書かない（書けたことにする）。"""

    def __init__(self, inner):
        self.inner = inner

    def load(self):
        return self.inner.load()

    def save(self, st):
        print("[書かない] 記録（dry）")
        return True


def jst(ts):
    try:
        return time.strftime("%m/%d %H:%M", time.gmtime(int(ts) + 9 * 3600))
    except Exception:
        return "?"


def _dur(sec):
    m = max(0, int(sec)) // 60
    return f"約{m}分" if m < 120 else f"約{m // 60}時間"


def queue(st, text, kind, ch="anime", key=None):
    st["outbox"].append({"text": text, "key": key or str(uuid.uuid4()), "made": now_ts(), "kind": kind, "ch": ch})


def stable_key(*parts):
    """同じ件なら、どこから送っても同じになる再送用の番号（LINE が2通目を 409 にする＝二重に届かない）。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "animeijin-watch:" + ":".join(str(p) for p in parts)))


def flush_outbox(st, store):
    """送る予定を古い順に送る。送れた・捨てたものはその都度消して記録を書く。(捨てた件数, 記録を書けたか)。"""
    dropped, saved = 0, True
    for m in list(st["outbox"]):
        if time.monotonic() - T0 > RUN_LIMIT_SEC - 90:   # 1通の送信と記録の書き込みに要る時間を残す
            print("時間が足りないので残りの通知は次の回に送る")
            break
        now = now_ts()
        name = CH_NAME.get(m.get("ch", "anime"), "?") + "・" + m["kind"]
        if now - m["made"] > RETRY_KEY_TTL:           # 番号が切れる＝作り直す。**新しい番号を記録に書いてから**送る
            m["key"], m["made"] = str(uuid.uuid4()), now
            if not store.save(st):
                print("新しい番号を記録に書けなかった＝送らずに次の回へ（書けないまま送ると二重に届き得る）")
                return dropped, False
        if m["kind"] == "remind" or m.get("ch") == "buzzw":
            q = line_quota_left()                     # ②（取得ワーカー）はお金の事故ではない＝②は全部、枠を①に残す
            if q is not None and q <= QUOTA_KEEP:
                print("LINE の月の枠が残り少ないので送らない（" + name + "）")
                st["outbox"].remove(m)
                saved = store.save(st) and saved
                continue
        r = line_send(m["text"], m["key"], m.get("ch", "anime"), m["kind"])
        if r == "ok":
            st["outbox"].remove(m)
            print(("[送らない] 通知を済ませた（" if _dry() else "通知を送った（") + name + "）")
            saved = store.save(st) and saved
        elif r == "drop":
            st["outbox"].remove(m)
            dropped += 1
            print("通知を送れない形だったので捨てた（" + name + "）")
            saved = store.save(st) and saved
        else:
            print("通知を送れなかった（" + name + "）＝次の回に送り直す")
            break
    return dropped, saved


# ---------------- 知らせの文面 ----------------
# アニ名人の文面は 2026-11-04 より前と同じ（変えない）。バズ名人！は頭の【バズ名人！】で区別がつくようにし、最後の1行に
# Shingo さんがやることを書く。
def anime_alert(now, since, body, cont):
    why = "10分おきの確認で続けて異常でした。" if cont else "3分おいた2回の確認で続けて異常でした（前回の記録は読めず）。"
    return (f"🚨【アニ名人の見張り】本番が止まっているかもしれません（{jst(now)}・最初に異常を見つけたのは {jst(since)}）\n"
            f"{body}\n{why}PCでClaudeを開いて「アニ名人の見張りが鳴った」と伝えてください。")


def anime_remind(now, since, body):
    return (f"🚨【アニ名人の見張り】まだ異常が続いています（{jst(now)}・最初に異常を見つけてから約{(now - since) // 60}分）\n"
            f"{body}\nPCでClaudeを開いて「アニ名人の見張りが鳴った」と伝えてください。")


def anime_recovered(now, since):
    return f"✅【アニ名人の見張り】本番が元に戻りました（{jst(now)}確認・最初に異常を見つけたのは {jst(since or now)}）"


BUZZ_DO = "やること：PCでClaudeを開いて「バズ名人の見張りが鳴った」と伝えてください。"
BUZZW_DO = "やること：自宅PC（NGO・メインPC）が起きているか確かめてください（起きていれば、PCでClaudeに「バズ名人の見張りが鳴った」と伝える）。"
NOTHING_DO = "やること：ありません。"


def _buzz_head(body):
    """落ちている（応答しない・開かない）なら「サイトが応答しません」、料金の表だけなら「サイトに異常があります」。"""
    return "サイトが応答しません" if ("応答しない" in body or "開かない" in body) else "サイトに異常があります"


def buzz_alert(now, since, body, cont):
    why = "前の回の確認でも異常でした。" if cont else "3分おいた2回の確認で続けて異常でした（前回の記録は読めず）。"
    return (f"🚨【バズ名人！】{_buzz_head(body)}（{jst(now)}・最初に異常を見つけたのは {jst(since)}）\n"
            f"{body}\n{why}\n{BUZZ_DO}")


def buzz_remind(now, since, body):
    return (f"🚨【バズ名人！】まだ{_buzz_head(body)}（{jst(now)}・最初に異常を見つけてから{_dur(now - since)}）\n"
            f"{body}\n{BUZZ_DO}")


def buzz_recovered(now, since):
    return f"✅【バズ名人！】サイトが元に戻りました（{jst(now)}確認・最初に異常を見つけたのは {jst(since or now)}）\n{NOTHING_DO}"


def buzzw_alert(now, since, unreadable):
    what = "取得ワーカーの数を読めないまま" if unreadable else "動画を取りに行く自宅PC（取得ワーカー）が0台のまま"
    return (f"⚠️【バズ名人！】{what}{_dur(now - since)}たちました（{jst(now)}・{jst(since)}ごろから）\n"
            f"いまは「動画のリンクから作る」を受け付けで断っています（クレジットは取りません）。\n{BUZZW_DO}")


def buzzw_remind(now, since, unreadable):
    what = "取得ワーカーの数を読めません" if unreadable else "取得ワーカーが0台です"
    return (f"⚠️【バズ名人！】まだ{what}（{jst(now)}・{jst(since)}ごろから{_dur(now - since)}）\n{BUZZW_DO}")


def buzzw_recovered(now, since, n):
    return (f"✅【バズ名人！】取得ワーカーが戻りました（{jst(now)}確認・{n}台・0台になったのは {jst(since or now)}ごろ）\n"
            f"{NOTHING_DO}")


# ---------------- 判定（サイトごと） ----------------
def step_down(st, s, ch, result, bad, readable, now, txt):
    """①サイトが落ちている、の決まり（アニ名人の 2026-09-30 からの決まりそのまま）。s＝そのサイトの記録（アニ名人は st 自身）。
    txt＝(alert, remind, recovered) の文面を作る関数。"""
    name = CH_NAME[ch]
    if result == "incomplete":
        print(name + ": 確認できず（2回目を確かめられなかった・見張り側の回線断など＝数えない）")
    elif result == "bad":
        prev = s["fails"]
        s["fails"] = prev + 1
        if s["down_since"] is None:
            s["down_since"] = now
        print(name + ": 異常（" + str(s["fails"]) + "回目）:")
        for b in bad:
            print("  -", b)                                # 決まった文言と応答コード・分数だけ（本番のエラー文は入らない）
        since = s["down_since"]
        body = "\n".join("・" + b for b in bad)
        if not s["alerted"] and (prev >= 1 or not readable):
            queue(st, txt[0](now, since, body, prev >= 1), "alert", ch)
            s["alerted"], s["alert_at"] = True, now        # 予定にした時点で「知らせた」扱い（直ったら必ず「直った」も送る）
        elif s["alerted"]:
            gap = REMIND_FIRST_SEC if now - since < 24 * 3600 else REMIND_LATER_SEC
            if now - (s["alert_at"] or now) >= gap:
                queue(st, txt[1](now, since, body), "remind", ch)
                s["alert_at"] = now
    else:
        print(name + ": 正常")
        if s["alerted"] and last_kind(st["outbox"], ch) != "up":    # 「直った」を送る予定が既にあれば重ねない
            queue(st, txt[2](now, s["down_since"]), "recovered", ch)
        s.update({"fails": 0, "alerted": False, "down_since": None, "alert_at": 0})


def step_workers(st, obs, now):
    """②取得ワーカーが0台、の決まり。/healthz がこの回の1回目から動いていた回だけ呼ぶ。
    時間は観測した時刻（obs["at"]）で数える（アニ名人を3分待った回でも、待つ前の観測を待った後の時刻で数えない）。"""
    b = st["buzz"]
    at = obs["at"]
    zs = zero_since(obs, b["w_since"])
    if zs is None:
        print(f"バズ名人！: 取得ワーカー {obs['fw']}台")
        if b["w_alerted"] and last_kind(st["outbox"], "buzzw") != "up":
            key = b["w_key"] if b.get("w_key") is not None else (b["w_since"] or 0) // KEY_BUCKET_SEC
            queue(st, buzzw_recovered(at, b["w_since"], obs["fw"]), "recovered", "buzzw", stable_key("buzzw", "recovered", key))
            b["w_note_at"] = at           # w_second は残す（「もう1回」で知らせた件の後は、6時間たつまで出さない）
        b.update({"w_since": None, "w_alerted": False, "w_alert_at": 0, "w_inc_at": 0, "w_key": None})
        return
    b["w_since"] = zs                     # 回の間に一瞬来ていれば始まりは新しくなる（知らせた件は閉じない＝連打しない）
    start = zero_counted(zs, b)
    dur = at - start
    fw = "読めない" if obs["fw"] is None else f"{obs['fw']}台"
    print(f"バズ名人！: 取得ワーカー {fw}（0台の見当 {max(0, dur) // 60}分）")
    bucket = zs // KEY_BUCKET_SEC
    if not b["w_alerted"]:
        if dur >= WORKER_ALERT_SEC:
            need = new_inc_need(b, at)
            if need is None:
                print("バズ名人！: 前の取得ワーカーの知らせから6時間たっていないので、まだ知らせない")
                return
            if dur < need:
                print(f"バズ名人！: 前の取得ワーカーの知らせから6時間たっていないので、{need // 60}分続くまで待つ")
                return
            queue(st, buzzw_alert(at, start, obs["fw"] is None), "alert", "buzzw", stable_key("buzzw", "alert", bucket))
            b["w_second"] = at - (b["w_note_at"] or 0) < W_NEW_GAP_SEC   # 6時間の間の「もう1回」で知らせた件（w_note_at を更新する前に決める）
            b["w_alerted"], b["w_alert_at"], b["w_note_at"], b["w_inc_at"] = True, at, at, at
            b["w_key"] = bucket
    elif dur >= WORKER_ALERT_SEC:         # 念押しは、今の0台が15分以上続いているときだけ
        gap = REMIND_FIRST_SEC if at - (b["w_inc_at"] or at) < 24 * 3600 else REMIND_LATER_SEC   # 件を知らせてからの時間で
        if at - (b["w_alert_at"] or at) >= gap:
            slot = (at - zs) // REMIND_FIRST_SEC  # 同じ0台の中で3時間ごとに変わる＝自分の念押しどうしは別の番号・2か所ではそろう
            key = b["w_key"] if b.get("w_key") is not None else bucket
            queue(st, buzzw_remind(at, start, obs["fw"] is None), "remind", "buzzw",
                  stable_key("buzzw", "remind", key, bucket, slot))   # 今の始まりの区切りも入れる（一瞬来て slot が数え直しでも重ならない）
            b["w_alert_at"], b["w_note_at"] = at, at


def step_buzz(st, res, readable, now):
    result, obs = res
    bad = obs["down"] if (result == "bad" and obs) else []
    step_down(st, st["buzz"], "buzz", result, bad, readable, now, (buzz_alert, buzz_remind, buzz_recovered))
    if obs is None:
        return
    if obs.get("hz_down") and (result == "bad" or (result == "incomplete" and obs.get("first_hz_down"))):
        st["buzz"]["w_floor"] = now       # /healthz の異常を見た＝ここより前の「長く来ていない」は②に数えない
        #                                   （1回目だけ落ちて3分以内に戻った揺れでは動かさない＝揺れが続いても②が鳴らなくならない）
    if result != "incomplete" and not obs.get("hz_down") and not obs.get("first_hz_down"):
        step_workers(st, obs, now)        # 料金のページだけの異常では②を止めない（確かめきれなかった回は数えない）


def main():
    global T0
    T0 = time.monotonic()
    mode = os.environ.get("WATCH_MODE", "")
    if mode == "test":
        r = line_send("🧪【見張りのテスト送信】アニ名人とバズ名人！の見張りです。本番が止まったら、このLINEに知らせます"
                      "（直ったらもう1通）。このメッセージへの返信は不要です。", str(uuid.uuid4()), "anime", "test")
        print("テスト送信", r)
        sys.exit(0 if r == "ok" else 1)
    store = LocalStore(os.environ["WATCH_STATE_FILE"]) if os.environ.get("WATCH_STATE_FILE") else Store()
    if mode == "dry":
        print("dry：LINE は送らず、記録も書かない")
        store = DryStore(store)
    st, readable = store.load()
    before = json.dumps(st, sort_keys=True)
    del _BUZZ_ERR[:]
    res = check(st["buzz"])
    now = now_ts()
    step_down(st, st, "anime", res["anime"][0], res["anime"][1], readable["anime"], now,
              (anime_alert, anime_remind, anime_recovered))
    try:
        b = copy.deepcopy(st)                            # バズ名人！の判定の不具合で、アニ名人の記録・予定を壊さない
        step_buzz(b, res["buzz"], readable["buzz"], now)
        st = b
    except Exception as e:
        print("バズ名人！: 判定の途中で例外（この回は数えない）", type(e).__name__)
        _BUZZ_ERR.append(type(e).__name__)
    saved = True
    if json.dumps(st, sort_keys=True) != before or not (readable["anime"] and readable["buzz"]):
        saved = store.save(st)                           # 送る前に記録を書く（書けたかを API の応答で確かめる）
        if not saved:
            print("記録を書けなかった（通知は送る＝黙らない側。次の回に二重に届く可能性がある）")
    dropped = 0
    if st["outbox"]:
        dropped, s2 = flush_outbox(st, store)
        saved = saved and s2
    # 送れていない予定・書けていない記録・送れない形で捨てた通知・バズ名人！の例外がある＝この回は失敗（実行一覧に赤く残る）
    rc = 1 if (st["outbox"] or not saved or dropped or _BUZZ_ERR) else 0
    sys.exit(rc)


if __name__ == "__main__":
    main()
