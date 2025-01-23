from fastapi import FastAPI
from models import SearchRequest, SearchResponse
from models import ScoutMessageRequest, ScoutMessageResponse
from hybrid_client import search_with_hybrid, AmbiHybridClient

app = FastAPI(title="AMBI Scraping API")

@app.post("/search", response_model=SearchResponse)
async def search_ambi(request: SearchRequest):
    """
    1) Playwrightでログイン・cookie取得
    2) 取得したcookieを使ってHTTPリクエスト
    3) 結果HTMLを解析→候補者一覧を返す
    """
    try:
        candidates = await search_with_hybrid(
            username=request.username,
            password=request.password,
            filters=request.filters
        )

        return SearchResponse(
            status="success",
            candidates=candidates,
            message=f"検索結果: {len(candidates)}件の候補者が見つかりました"
        )

    except Exception as e:
        error_message = str(e)
        if "ログイン認証に失敗" in error_message:
            message = "ログインに失敗しました。認証情報を確認してください。"
        elif "最大リトライ回数" in error_message:
            message = "一時的なエラーが発生しました。しばらく時間をおいて再試行してください。"
        else:
            message = f"エラーが発生しました: {error_message}"

        return SearchResponse(
            status="error",
            candidates=[],
            message=message
        )

@app.post("/scout/send", response_model=ScoutMessageResponse)
async def scout_send(request: ScoutMessageRequest):
    """
    スカウトメッセージ送信エンドポイント
    1) Playwrightでログイン (Cookie取得)
    2) (追加) 送信前に scout_list_message_frame を呼んでサーバ状態を整える
    3) send_scout_message() でスカウト送信
    """
    client = AmbiHybridClient()

    try:
        # (1) ログイン
        await client.login_with_playwright(
            username=request.username,
            password=request.password
        )

        # (2) cURL相当の事前リクエスト
        #     search_id が指定されていればfetch実行
        if request.search_id:
            try:
                await client.fetch_scout_list_frame(
                    SID=request.UID,
                    search_id=request.search_id
                )
            except Exception as ex:
                # 事前リクエスト失敗したらログ残して続行するか、エラー返すかは運用判断
                # ここではエラー返却にする
                return ScoutMessageResponse(
                    status="error",
                    message=f"事前リクエストに失敗しました: {str(ex)}"
                )

        # (3) スカウトメッセージ送信
        success = await client.send_scout_message(request)
        if success:
            return ScoutMessageResponse(
                status="success",
                message="スカウトメッセージの送信に成功しました。"
            )
        else:
            return ScoutMessageResponse(
                status="error",
                message="スカウトメッセージの送信に失敗しました。"
            )

    except Exception as e:
        error_message = str(e)
        if "ログイン認証に失敗" in error_message:
            msg = "ログインに失敗しました。認証情報を確認してください。"
        else:
            msg = f"スカウト送信時にエラーが発生: {error_message}"

        return ScoutMessageResponse(
            status="error",
            message=msg
        )
