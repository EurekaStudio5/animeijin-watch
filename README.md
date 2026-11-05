# animeijin-watch

アニ名人（https://animeijin.com ）とバズ名人！（https://buzzmeijin.com ）が動いているかを外から確かめる見張り。GitHub Actions（10分おきの予定だが、実際は3〜9時間おきに間引かれる）と、自宅PC（NGO）のタスクが10分おきに同じ watch.py を動かす（GitHub が直近30分に動いた回は自宅PCは何もしない）。

- 見るもの（読むだけ。本番のデータは作らない・変えない）
  - アニ名人: トップページ（HEAD）・`/api/packs`・公開の `/api/status`
  - バズ名人！: `/healthz`（取得ワーカーの数も）・`/pricing`（User-Agent は `buzzmeijin-healthcheck/1.0 monitor ...`。本番はボットの語〔monitor・uptime など〕を含む UA を訪問に数えない。前の UA も uptime で外れていたが、monitor を名指しで入れた）
- 2回続けて異常なら運営者の LINE に知らせる（続いていれば3時間ごと・直ったら1通）。バズ名人！の取得ワーカーは続けて15分以上0台のときだけ（一瞬の0では知らせない。新しい件は前の知らせから6時間あける。ただし前の件が短い件なら、次の件は60分で1回だけ知らせる）
- AI は使わない。秘密は GitHub の Secrets（`LINE_TOKEN`・`LINE_TO`）だけに置く
