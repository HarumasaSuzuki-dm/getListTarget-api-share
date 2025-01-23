from pydantic import BaseModel
from typing import Optional, List

# ----------------------------------------
# 絞り込み条件モデル
# ----------------------------------------
class AmbiSearchFilter(BaseModel):
    """
    AMBIの検索フォーム (例: scout/index/action/?PK=CC1E9D) を想定
    """
    AgeMin: Optional[int] = None
    AgeMax: Optional[int] = None
    School: Optional[int] = None
    JobChange: Optional[int] = None
    IncomeMin: Optional[int] = None
    IncomeMax: Optional[int] = None
    Situation: Optional[int] = None

    SearchKeyword1: Optional[str] = None
    SearchKeyword2: Optional[str] = None
    SearchKeyword3: Optional[str] = None

    SearchOutKeyword1: Optional[str] = None
    SearchOutKeyword2: Optional[str] = None
    SearchOutKeyword3: Optional[str] = None

    # 対象人材チェックボックス
    ScoutUserFlg: Optional[bool] = None

    # ページネーション用: Trueなら可能な限り全ページ取得
    fetch_all_pages: Optional[bool] = False
    # fetch_all_pages=Falseの場合の最大ページ数 (1 => 1ページのみ)
    max_pages: Optional[int] = 1


# ----------------------------------------
# 候補者情報(スクレイピング結果)モデル
# ----------------------------------------
class CandidateData(BaseModel):
    id: Optional[int]
    gender: Optional[str]
    age: Optional[int]
    location: Optional[str]
    no: Optional[int]
    company: Optional[str]
    sub: Optional[str]
    education: Optional[str]
    change_times: Optional[str]
    past_jobs: List[str] = []
    language: Optional[str]
    summary: Optional[str]


# ----------------------------------------
# API リクエスト/レスポンスモデル（検索用）
# ----------------------------------------
class SearchRequest(BaseModel):
    username: str
    password: str
    target_url: Optional[str] = None
    filters: AmbiSearchFilter


class SearchResponse(BaseModel):
    status: str
    candidates: List[CandidateData] = []
    message: str


# ----------------------------------------
# スカウトメッセージ送信用モデル
# ----------------------------------------
class ScoutMessageRequest(BaseModel):
    """
    スカウトメッセージ送信APIのリクエストボディ
    """
    username: str            # ログインユーザー
    password: str            # パスワード
    UID: int                 # ユーザーID
    ScoutType: int           # スカウトタイプ
    attachedWorkIDs: List[int]  # 添付求人IDを複数指定できる

    Title: str               # メッセージタイトル
    Body: str                # メッセージ本文

    # 追加パラメータ(任意)
    ReplyDeadline: Optional[str] = None
    isScout: Optional[int] = None
    sendPage: Optional[int] = None

    # 再スカウト関連
    rescout: Optional[int] = None
    retransmission: Optional[int] = None
    rescoutTransSelect: Optional[int] = None
    rescoutTitle: Optional[str] = None
    rescoutBody: Optional[str] = None

    # 今回追加: cURL 相当の事前リクエストで使うパラメータ (SearchID)
    # 送信前に fetch_scout_list_frame() を呼ぶ際に使用
    search_id: Optional[int] = None


class ScoutMessageResponse(BaseModel):
    """
    スカウトメッセージ送信APIのレスポンス
    """
    status: str
    message: str
