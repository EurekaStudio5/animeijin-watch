# animeijin-watch

アニ名人（https://animeijin.com ）とバズ名人！（https://buzzmeijin.com ）が動いているかを、GitHub Actions で10分おきに外から確かめる見張り。

- 見るもの（読むだけ。本番のデータは作らない・変えない）
  - アニ名人: トップページ（HEAD）・`/api/packs`・公開の `/api/status`
  - バズ名人！: `/healthz`（取得ワーカーの数も）・`/pricing`
- 2回続けて異常なら運営者の LINE に知らせる（続いていれば3時間ごと・直ったら1通）。バズ名人！の取得ワーカーは続けて60分以上0台のときだけ
- AI は使わない。秘密は GitHub の Secrets（`LINE_TOKEN`・`LINE_TO`）だけに置く
