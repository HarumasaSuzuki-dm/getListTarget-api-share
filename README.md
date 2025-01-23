
# 一覧表取得API 仕様書

## エンドポイント

```
POST /search
```

## 概要

- 本APIは AMBI（https://en-ambi.com/ ）の候補者一覧をスクレイピングで取得し、条件に合致する候補者のリストを返却します。
- API内部では
  1. 指定したユーザーID/パスワードで**Playwright**を用いてログイン  
  2. 取得したクッキーを利用し、**aiohttp** で検索パラメータを投げて一覧を取得  
  3. 結果ページのHTMLを**BeautifulSoup**で解析して候補者情報を抽出  
  4. JSON形式でレスポンス  
  の流れが実行されます。

## リクエスト仕様

### リクエスト形式

- **HTTPメソッド**: `POST`
- **Content-Type**: `application/json`
- **エンドポイントURL**: `http://<your-server>/search`

### リクエストボディ

#### JSON構造

```json
{
  "username": "<AMBIログイン用ユーザー名>",
  "password": "<AMBIログイン用パスワード>",
  "target_url": "https://en-ambi.com/company/scout/index/action/?PK=CC1E9D", 
  "filters": {
    "AgeMin": 25,
    "AgeMax": 35,
    "School": 90,
    "JobChange": 0,
    "IncomeMin": 500,
    "IncomeMax": 800,
    "SearchKeyword1": "python",
    "ScoutUserFlg": true,
    "max_pages": 3,
    "fetch_all_pages": false
  }
}
```

- `username` / `password`: AMBIのログイン情報
- `target_url` : 一般的には `https://en-ambi.com/company/scout/index/action/?PK=CC1E9D` のようなURL  
  - ※実装コード上ではあまり使われておらず、今後の拡張で利用予定(任意)。  
- `filters`: 検索フィルタ条件。**主にここが検索パラメータの実態**です。

### 検索フィルタパラメータ一覧

下記は `filters` オブジェクトに含めるプロパティとその意味です。  
（値が `None` や空の場合はサーバ側で指定無しとして扱います。例: `"AgeMin": null` など）

| 項目                             | パラメータ名                                         | 型・例                                                    | 説明                                                                                                                     |
| -------------------------------- | ---------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **1. 年齢フィルタ**              | `AgeMin`, `AgeMax`                                   | `AgeMin=25`, `AgeMax=35`                                  | 年齢の最小値・最大値を指定。<br>例: `25` ～ `35` で 25～35歳の候補者に絞り込み。<br>0 or `null`で指定無効                |
| **2. 学校区分**                  | `School`                                             | `0` / `90` / `80` / `70` / ...                            | 最終学歴の指定。<br>`0`: 問わない, `90`: 大学院以上, `80`: 大学以上, `70`: 高専以上, など                                |
| **3. 転職回数**                  | `JobChange`                                          | `99` / `0` / `1` / `2` / `3` / `4`                        | 転職回数の上限。<br>`99`: 問わない, `0`: 転職経験なし, `1`: 1回以内, など                                                |
| **4. 年収フィルタ**              | `IncomeMin`,`IncomeMax`                              | `500`, `800`                                              | 希望年収の下限・上限。<br>空または `null` で未指定。                                                                     |
| **5. 英語スキル**                | ※現コード例: 未定義（将来拡張）                      | 例: `EnglishLevel=20` etc.                                | 現状のコードではパラメータ定義されていないが、追加実装する場合は以下のように対応可能。<br>例: `EnglishLevel=0`=問わない. |
| **6. TOEIC / TOEFL**             | ※現コード例: 未定義（将来拡張）                      | `"Toeic": "600"`, `"Toefl": "60"`                         | 同上。実際に送る場合は `Toeic="", Toefl=""` などで空にすると問わない扱い。                                               |
| **7. 離職期間**                  | ※同上                                                | `"UnemployedTerm": "3"` など                              | これも現実装では定義されていないが、拡張可能。<br>`0`: 問わない, `1`: 1ヶ月未満, など                                    |
| **8. 希望勤務地**                | ※同上                                                | `"HopeAreaIDList": [13,14]`, <br>`IncludeNoHopeAreaFlg=1` | エリアIDと「未指定を含むか」をセット。                                                                                   |
| **9. フリーワード検索**          | `SearchKeyword1` ～ `SearchKeyword3`                 | `"SearchKeyword1": "python"` etc.                         | 1～3 つのキーワード指定が可能。<br>複数キーワードの入力欄を増やす場合は `SearchKeyword2`,`SearchKeyword3` も使用。       |
| **10. 表示順**                   | `TargetFirst`, `UserDateType`, `UserDateRange`       | 例: `TargetFirst=1`(おすすめ順)                           | 公開日や更新日などでソート・フィルタしたい場合に使用。<br>必要に応じて拡張してください。                                 |
| **11. その他**<br>(対象サイト等) | `ScoutUserFlg`<br>`Site[]`, `ScoutReceiveCount` など | `ScoutUserFlg = true`                                     | - `ScoutUserFlg`: true/false で対象人材にスカウト可能フラグを指定。<br> - `Site[]`: `1`=ミドルの転職, `2`=AMBI 等        |

#### 追加のページネーション制御

| 項目         | パラメータ        | 型・例              | 説明                                                                             |
| ------------ | ----------------- | ------------------- | -------------------------------------------------------------------------------- |
| ページ数指定 | `max_pages`       | 整数(例: `3`)       | 取得する最大ページ数。1 なら1ページ目のみ取得。                                  |
| 全ページ取得 | `fetch_all_pages` | 真偽値(例: `false`) | `true`の場合、最終ページまで一括取得しようと試みる。<br>ただしサーバ負荷に注意。 |

### リクエスト例

#### 例1: 最大3ページ取得、25～35歳、大学院卒以上、転職経験なし、年収下限1000万、キーワード `python`、スカウトフラグON
```bash
curl -X POST 'http://localhost:8000/search' \
-H 'Content-Type: application/json' \
-d '{
  "username": "MBYXB001",
  "password": "$brbJ#Z7vkcwk",
  "target_url": "https://en-ambi.com/company/scout/index/action/",
  "filters": {
    "AgeMin": 25,
    "AgeMax": 35,
    "School": 90,
    "JobChange": 0,
    "IncomeMin": 1000,
    "SearchKeyword1": "python",
    "ScoutUserFlg": true,
    "max_pages": 3,
    "fetch_all_pages": false
  }
}'
```

#### 例2: 全ページ取得、25～35歳、大学院卒以上、転職経験なし、年収下限1000万、キーワード `python`、スカウトフラグON
```bash
curl -X POST 'http://localhost:8000/search' \
-H 'Content-Type: application/json' \
-d '{
  "username": "MBYXB001",
  "password": "$brbJ#Z7vkcwk",
  "target_url": "https://en-ambi.com/company/scout/index/action/",
  "filters": {
    "AgeMin": 25,
    "AgeMax": 35,
    "School": 90,
    "JobChange": 0,
    "IncomeMin": 1000,
    "SearchKeyword1": "python",
    "ScoutUserFlg": true,
    "fetch_all_pages": true
  }
}'
```

---

## レスポンス仕様

### レスポンス形式

- **Content-Type**: `application/json`
- **HTTPステータスコード**: 常に200（FastAPIの都合上、内部的なエラーはjsonの`status="error"`で表現）

### レスポンスボディ

#### JSON構造

```json
{
  "status": "success",
  "candidates": [
    {
      "id": 123456,
      "gender": "男性",
      "age": 28,
      "location": "東京都",
      "no": 12345,
      "company": "株式会社Sample",
      "sub": "リードエンジニア",
      "education": "早稲田大学大学院",
      "change_times": "転職回数：0",
      "past_jobs": ["Webアプリ開発", "データ分析"],
      "language": "英語：ビジネスレベル",
      "summary": "自己PRや経歴の要約文..."
    },
    ...
  ],
  "message": "検索結果: 20件の候補者が見つかりました"
}
```

| フィールド   | 型                                    | 説明                                                                                                                                                                                                                                                                                                                                                                             |
| ------------ | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `status`     | 文字列 (`"success"` または `"error"`) | 成功時は `"success"`, 失敗時は `"error"`.                                                                                                                                                                                                                                                                                                                                        |
| `candidates` | 配列(オブジェクトのリスト)            | 候補者情報のリスト。1要素につき以下のフィールドを持つ。<br> - `id`: サイト内部ID <br> - `gender`: 性別<br> - `age`: 年齢<br> - `location`: 住所<br> - `no`: 表示番号<br> - `company`: 現職企業<br> - `sub`: 表示用サブテキスト<br> - `education`: 学歴<br> - `change_times`: 転職回数(文字列)<br> - `past_jobs`: 職種の配列<br> - `language`: 語学レベル<br> - `summary`: 自己PR |
| `message`    | 文字列                                | 処理結果に応じたメッセージ                                                                                                                                                                                                                                                                                                                                                       |

#### 失敗例

```json
{
  "status": "error",
  "candidates": [],
  "message": "ログインに失敗しました。認証情報を確認してください。"
}
```

- ログイン情報が間違っている場合などに発生。
- `candidates` は空配列、`status="error"`、詳細は `message` に記載。

---

## 補足

- **Cookie管理**や**CSRFトークン**取得などは内部で自動的に行います。  
- 連続して大量のページを取得すると先方サーバに負荷がかかるため、`max_pages` や `fetch_all_pages` の指定には注意ください。  
- パラメータ値は基本的に `int` / `str` / `bool` などで指定し、サーバー側で適切な形式に変換します。  
- 一部パラメータ（英語スキル、TOEIC/TOEFL、希望勤務地など）は**将来的な拡張**に備えています。現在のサンプルコードには未定義・未使用の場合もあります。

---

# スカウトメッセージ送信API 仕様書

## エンドポイント

```
POST /scout/send
```

## 概要

- 本APIでは AMBI (https://en-ambi.com/) へ**スカウトメッセージを送信**します。
- API内部では
  1. 指定されたユーザーID/パスワードで **Playwright** を用いてログインし、重要クッキー(`PHPSESSID`, `C13CC`)を取得
  2. 取得したクッキーと、取得し直した **CSRFトークン(`C13CT`)** を利用してスカウト送信API（ `/company/api/scout_send/run` ）にフォームデータをPOST
  3. POST結果のHTML/レスポンスを解析し、送信の成否を判定  
  のフローが実行されます。

## リクエスト仕様

### リクエスト形式

- **HTTPメソッド**: `POST`
- **Content-Type**: `application/json`
- **エンドポイントURL**: `http://<your-server>/scout/send`

### リクエストボディ

#### JSON構造

```json
{
  "username": "<AMBIログイン用ユーザー名>",
  "password": "<AMBIログイン用パスワード>",
  "UID": 287864,
  "ScoutType": 10,
  "attachedWorkIDs": [3284016],
  "Title": "【AI×HR Tech で事業拡大】営業職の募集",
  "Body": "NAME様\r\n\r\nはじめまして...",
  "ReplyDeadline": "2025年02月07日",
  "isScout": 1,
  "sendPage": 30,
  "rescout": 1,
  "retransmission": 1,
  "rescoutTransSelect": 3,
  "rescoutTitle": "【転職意向不問】まずはフランクにお話ししませんか？",
  "rescoutBody": "度々のご連絡を..."
}
```

| パラメータ名         | 型         | 必須 | 説明                                                                                                    |
| -------------------- | ---------- | ---- | ------------------------------------------------------------------------------------------------------- |
| `username`           | 文字列     | 必須 | ログイン時に使用するID                                                                                  |
| `password`           | 文字列     | 必須 | ログイン時に使用するパスワード                                                                          |
| `UID`                | 数値 (int) | 必須 | スカウト対象ユーザーID                                                                                  |
| `ScoutType`          | 数値 (int) | 必須 | スカウトの種類を示すID<br>例: `10`=通常スカウト など                                                    |
| `attachedWorkIDs`    | 数値配列   | 必須 | 添付する求人IDの配列<br>AMBI上の求人ID（例: `[3284016]` など）                                          |
| `Title`              | 文字列     | 必須 | スカウトメール件名                                                                                      |
| `Body`               | 文字列     | 必須 | スカウトメール本文<br>改行は `\r\n` を含めるか、URLエンコード(`%0D%0A`)を使用すると自然に表示されます。 |
| `ReplyDeadline`      | 文字列     | 任意 | 返信期限を文字列で指定<br>例: `2025年02月07日`                                                          |
| `isScout`            | 数値 (int) | 任意 | スカウトフラグ<br>通常 `1`=スカウト扱い、`0`=非スカウト。<br>指定が無い場合は `None`                    |
| `sendPage`           | 数値 (int) | 任意 | 送信ページ番号。<br>再スカウト・リマインド時などに利用                                                  |
| `rescout`            | 数値 (int) | 任意 | 再スカウトフラグ<br> `1`=再スカウトする, `0`=しない                                                     |
| `retransmission`     | 数値 (int) | 任意 | 再送信フラグ<br> `1`=再送信する, `0`=しない                                                             |
| `rescoutTransSelect` | 数値 (int) | 任意 | 再送信方法の選択<br>例: `3`=3回目の送信, etc. 上限`10`                                                  |
| `rescoutTitle`       | 文字列     | 任意 | リマインド時などに使用する**再スカウト件名**                                                            |
| `rescoutBody`        | 文字列     | 任意 | リマインド時などに使用する**再スカウト本文**                                                            |

> **注意**:  
> - **`rescoutTemplateID` は除外**しています。再スカウト時にテンプレートIDを使用しない仕様です。  
> - `Body`内の `{NAME}` はAMBI側の仕様で、送信時に候補者名に自動置換されるケースがあります（サイト設定に依存）。  
> - 日本語や改行コードを含む際には、適宜URLエンコードして送る必要がある場合があります（AMBI側サーバ設定による）。

### リクエスト例

```bash
curl -X POST "http://localhost:8000/scout/send" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_account",
    "password": "your_password",
    "UID": 287864,
    "ScoutType": 10,
    "attachedWorkIDs": [3284016],
    "Title": "【AI×HR Tech で事業拡大】営業職の募集",
    "Body": "NAME様\r\n\r\nはじめまして...",
    "ReplyDeadline": "2025年02月07日",
    "isScout": 1,
    "sendPage": 30,
    "rescout": 1,
    "retransmission": 1,
    "rescoutTransSelect": 3,
    "rescoutTitle": "【転職意向不問】まずはフランクにお話ししませんか？",
    "rescoutBody": "度々のご連絡を..."
  }'
```

---

## レスポンス仕様

### レスポンス形式

- **Content-Type**: `application/json`
- **HTTPステータスコード**: 常に200（内部的にエラーがあった場合はJSONで `status="error"` を返却）

### レスポンスボディ

#### JSON構造

```json
{
  "status": "success",
  "message": "スカウトメッセージの送信に成功しました。"
}
```

| フィールド | 型                                | 説明                                         |
| ---------- | --------------------------------- | -------------------------------------------- |
| `status`   | 文字列 (`"success"` or `"error"`) | `"success"` = 送信成功, `"error"` = 送信失敗 |
| `message`  | 文字列                            | 処理結果メッセージ                           |

### 成功例

```json
{
  "status": "success",
  "message": "スカウトメッセージの送信に成功しました。"
}
```

### 失敗例

```json
{
  "status": "error",
  "message": "ログインに失敗しました。認証情報を確認してください。"
}
```

例として、下記のような状況で `status="error"` が返されます。  
- ログインID/パスワードの誤り
- 必須Cookieが取得できない
- スカウト送信先のURLにアクセスできない、またはAMBI側のエラー  
- CSRFトークンが不正、もしくは期限切れ

---

## 処理フロー

1. **ログイン**  
   - `username` / `password` を受け取り、Playwright でログイン画面(`company_login/login/`)へアクセス  
   - ログインフォームを送信し、成功時にクッキー(`PHPSESSID`, `C13CC` 等)を取得  
   - ログインに失敗した場合、`status="error"` を返却し処理終了  

2. **CSRFトークン取得**  
   - ログインで得たクッキーを使い、`/company/scout/index/action/?PK=3FFFF4` などにGETアクセス  
   - HTML内の`<input name="C13CT">` からCSRFトークンを抜き取り  

3. **スカウトメッセージ送信**  
   - `/company/api/scout_send/run` へ `UID`, `ScoutType`, `attachedWorkID[]`, `Title`, `Body` などをフォームデータとしてPOST  
   - レスポンスHTMLを確認し、エラーが含まれるかどうかを簡易チェック  

4. **レスポンス返却**  
   - スカウト送信結果を判定し、成功時は `{"status": "success", "message": "..."}`
   - 失敗時は `{"status": "error", "message": "..."}`
   - これをJSONでクライアントに返す  

---

## 注意事項

- **連続送信**や**大量送信**を行う場合は、相手サーバへの負荷や利用規約をご確認ください。  
- `Body` などに改行や全角文字が含まれる場合は、**適切なURLエンコード**を行わないと文字化けが発生する場合があります。  
- 再スカウト (`rescout`) や再送信 (`retransmission`) に関するパラメータは必須ではありません。使用時のみ指定してください。  
- **`rescoutTemplateID`** は本仕様では**除外**しています。テンプレートIDを使った再スカウトは行いません。  

---