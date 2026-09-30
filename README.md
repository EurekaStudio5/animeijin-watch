# animeijin-watch

アニ名人（https://animeijin.com ）が動いているかを、GitHub Actions で10分おきに外から確かめる見張り。

- 見るもの: トップページ（HEAD）・`/api/packs`・公開の `/api/status`（読むだけ。本番のデータは作らない・変えない）
- 2回続けて異常なら運営者の LINE に知らせる（続いていれば3時間ごと・直ったら1通）
- AI は使わない。秘密は GitHub の Secrets（`LINE_TOKEN`・`LINE_TO`）だけに置く
