# streamlit_app_combined.py

import streamlit as st
import requests
import json
import google.generativeai as genai
import os
from dotenv import load_dotenv
import pandas as pd
from typing import Dict, Any
import io
import csv
from datetime import datetime

# 環境変数の読み込み
load_dotenv()

# --- Gemini API の設定 ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("環境変数 GOOGLE_API_KEY が設定されていません。.envファイルを確認してください。")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# --- グローバル定数の設定 ---
def init_global_constants():
    if 'AMBI_USERNAME' not in st.session_state:
        st.session_state.AMBI_USERNAME = os.getenv("AMBI_USERNAME", "MBYXB001")
    if 'AMBI_PASSWORD' not in st.session_state:
        st.session_state.AMBI_PASSWORD = os.getenv("AMBI_PASSWORD", "$brbJ#Z7vkcwk")

# --- サイドバーでログイン情報を入力 ---
def sidebar_login():
    with st.sidebar:
        st.markdown("### ログイン情報")
        st.session_state.AMBI_USERNAME = st.text_input("AMBIアカウント", value=st.session_state.AMBI_USERNAME)
        st.session_state.AMBI_PASSWORD = st.text_input("AMBIパスワード", value=st.session_state.AMBI_PASSWORD, type="password")
        if not st.session_state.AMBI_USERNAME or not st.session_state.AMBI_PASSWORD:
            st.warning("ログイン情報が未入力です")

# --- 1) Gemini（AI）を呼び出すためのプロンプトテンプレート ---
GEMINI_PROMPT_TEMPLATE = """
あなたはAMBiの検索フィルタを生成するアシスタントです。
ユーザーの回答(10個)に基づいて、以下のJSON形式で出力してください。

必ずJSON形式のみで、値が無い場合はキーごと省略してください。
JSON形式:
{{
    "AgeMin": int,              # 最小年齢 (0: 下限なし)
    "AgeMax": int,              # 最大年齢 (99: 上限なし)
    "School": int,              # 学歴 (0:問わない, 90:大学院卒以上, 80:大学卒以上, 70:高専卒以上, 60:短大卒以上, 50:専門各種学校卒以上, 40:高校卒以上)
    "JobChange": int,           # 転職回数 (99:問わない, 0:転職なし, 1:1回以内, 2:2回以内, 3:3回以内, 4:4回以内)
    "IncomeMin": int,           # 最低年収（万円）
    "IncomeMax": int,           # 最高年収（万円）
    "EnglishLevel": int,        # 英語レベル (0:問わない, 10:基礎以上, 20:日常会話以上, 30:ビジネス以上, 40:ネイティブ以上)
    "EnglishConversation": int, # 英会話力 (0:問わない, 1:初級以上, 2:中級以上, 3:上級以上)
    "EnglishComprehension": int,# 英語読解力 (0:問わない, 1:初級以上, 2:中級以上, 3:上級以上)
    "EnglishComposition": int,  # 英作文力 (0:問わない, 1:初級以上, 2:中級以上, 3:上級以上)
    "Toeic": int,              # TOEICスコア (600:600点以上, 700:700点以上, 以降50点刻み)
    "Toefl": int,              # TOEFLスコア (60:60点以上, 80:80点以上, 以降10点刻み)
    "UnemployedTerm": int,      # 離職期間 (0:問わない, 1:1ヶ月未満, 3:3ヶ月未満, 6:6ヶ月未満)
    "HopeAreaIDList": [int],   # 希望勤務地ID
    "IncludeNoHopeAreaFlg": int,# 勤務地未指定を含む (0:含まない, 1:含む)
    "SearchKeyword1": string,   # フリーワード1
    "SearchKeyword2": string,   # フリーワード2
    "SearchKeyword3": string,   # フリーワード3
    "TargetFirst": int,        # 表示順 (0:指定なし, 1:おすすめ順)
    "UserDateType": int,       # 日付種別 (0:指定なし, 1:スカウト公開日, 2:職務経歴書更新日, 3:職務経歴書登録日, 4:最終ログイン日)
    "UserDateRange": int,      # 日付範囲 (1:1日以内, 3:3日以内, etc)
    "ScoutReceiveCount": int,  # スカウト受信数 (-1:指定なし, 0:0件, 1:1-5件, 6:6-10件)
    "Site": [int],            # 対象サイト ([1]:ミドルの転職, [2]:AMBI)
    "ScoutUserFlg": bool      # スカウト可能フラグ
}}

ユーザーの回答:
1) 希望する職種・ポジション: {q1}
2) 転職回数の上限: {q2}
3) 希望する英語レベル: {q3}
4) 学歴に関する希望: {q4}
5) 希望する最低年収: {q5}
6) 使いたいスキルや経験: {q6}
7) 働きたい勤務地（都道府県、リモートなど）: {q7}
8) 英語以外で希望する言語スキル: {q8}
9) いつまでに転職したいか: {q9}
10) その他の希望・自由記述: {q10}

上記の回答を元に、AMBi検索フィルタを推論し、JSON形式だけで出力してください。
特に以下の点に注意して推論してください：
1. 英語に関する要件は、EnglishLevel, 会話/読解/作文, TOEIC/TOEFLスコアを適切に設定
2. 勤務地は可能な限りHopeAreaIDListに変換（リモート希望の場合は適切に対応）
3. スキルや経験はSearchKeywordに分解して設定
4. 転職時期から適切なUserDateTypeとUserDateRangeを設定
5. その他の記述から関連するパラメータを抽出して設定
"""


def construct_gemini_prompt(answers: dict) -> str:
    """
    10個のユーザー回答(answers)をGeminiのプロンプト文字列に差し込む。
    answersは { "q1": "...", "q2": "...", ... "q10": "..."} の想定
    """
    return GEMINI_PROMPT_TEMPLATE.format(
        q1=answers["q1"],
        q2=answers["q2"],
        q3=answers["q3"],
        q4=answers["q4"],
        q5=answers["q5"],
        q6=answers["q6"],
        q7=answers["q7"],
        q8=answers["q8"],
        q9=answers["q9"],
        q10=answers["q10"]
    )

def call_gemini_api(prompt: str) -> dict:
    """
    Gemini (AI) にプロンプトを投げて、検索フィルタのJSONを受け取る。
    """
    try:
        # Geminiモデルの設定
        model = genai.GenerativeModel('gemini-pro')
        
        # プロンプトを送信して応答を取得
        response = model.generate_content(prompt)
        
        # レスポンスからJSONを抽出
        try:
            # レスポンステキストからJSONを抽出
            response_text = response.text
            # JSON文字列の開始と終了位置を見つける
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
            else:
                return {"ScoutUserFlg": False, "error": "JSONが見つかりませんでした"}
                
        except json.JSONDecodeError:
            return {"ScoutUserFlg": False, "error": "JSONのパースに失敗しました"}
            
    except Exception as e:
        return {
            "ScoutUserFlg": False,
            "error": f"Gemini APIエラー: {str(e)}"
        }

def merge_filters(ai_filters: dict, user_select_filters: dict) -> dict:
    """
    Geminiが返したフィルタ (ai_filters) と、
    ユーザーがボタン/セレクトで選んだフィルタ (user_select_filters) をマージ。
    重複キーがある場合はユーザーの選択を優先 or AI結果を優先など要件に応じて調整。
    """
    # 例: ユーザーの選択を最優先、AIは不足分を補う
    merged = {**ai_filters, **user_select_filters}  
    return merged

def call_ambi_search_api(username: str, password: str, final_filters: dict) -> dict:
    """
    FastAPIで用意したAMBi検索エンドポイント (/search) を呼び出す。
    """
    api_url = "https://ambi-service-1077541053369.asia-northeast1.run.app/search"
    payload = {
        "username": username,
        "password": password,
        "filters": final_filters
    }
    try:
        resp = requests.post(api_url, json=payload)
        resp.raise_for_status()
        return resp.json()  # { "status": "success", "candidates": [...], "message": "..." }
    except Exception as e:
        return {
            "status": "error",
            "candidates": [],
            "message": f"API呼び出し失敗: {e}"
        }

def scout_message_tool(api_base_url: str):
    """
    単体送信 + 一括送信 をまとめた Streamlit アプリ。
    ・サイドバーで送信モードを切り替え
    ・一括送信は Data Editor(スプレッドシート風) + CSVファイルアップロード
    ・ID列は整数型(カンマなし)、件名/本文はテキスト型(日本語OK)
    ・古いバージョンの Streamlit では動きません(1.22+ が必要)
    """

    st.title("AMBI スカウトメッセージ送信ツール")

    # =========================================
    # APIサーバーURL (適宜変更)
    # =========================================
    api_base_url = "https://ambi-service-1077541053369.asia-northeast1.run.app/"

    # =========================================
    # サイドバーで「単体送信」 or 「一括送信」 を選択
    # =========================================
    mode = st.sidebar.radio("送信モードを選択", ("単体送信", "一括送信"))

    # =========================================
    # 共通: スカウト送信に使うパラメータ
    # =========================================
    st.markdown("---")
    st.markdown("### スカウト共通設定")
    scout_type = st.selectbox(
        "スカウト種別 (ScoutType)",
        options=[10, 20, 30],
        format_func=lambda x: f"{x} (通常スカウト)" if x == 10 else str(x),
        index=0,
        help="10=通常スカウト など"
    )
    attached_work_input = st.text_input(
        "添付求人ID (複数ある場合はカンマ区切り)",
        value="3284016"
    )

    # =========================================
    # オプションパラメータ
    # =========================================
    with st.expander("詳細設定"):
        # 返信期限
        reply_deadline = st.date_input(
            "返信期限 (ReplyDeadline)",
            value=None,
            help="返信期限を設定してください（例: 2025年02月07日）"
        )

        # スカウトフラグ
        is_scout = st.selectbox(
            "スカウトフラグ (isScout)",
            options=[None, 1, 0],
            format_func=lambda x: "未指定" if x is None else ("スカウト扱い" if x == 1 else "非スカウト扱い"),
            index=0,
            help="1=スカウト扱い、0=非スカウト扱い"
        )

        # 送信ページ
        send_page = 30

        # 再スカウト関連
        st.markdown("#### 再スカウト・再送信関連")
        rescout = st.selectbox(
            "再スカウトフラグ (rescout)",
            options=[None, 1, 0],
            format_func=lambda x: "未指定" if x is None else ("再スカウトする" if x == 1 else "再スカウトしない"),
            index=0
        )
        
        retransmission = st.selectbox(
            "再送信フラグ (retransmission)",
            options=[None, 1, 0],
            format_func=lambda x: "未指定" if x is None else ("再送信する" if x == 1 else "再送信しない"),
            index=0
        )
        
        rescout_trans_select = st.selectbox(
            "再送信方法の選択 (rescoutTransSelect)",
            options=[None] + list(range(1, 11)),
            format_func=lambda x: "未指定" if x is None else f"{x}回目の送信",
            index=0,
            help="1〜10回目の送信を選択可能"
        )
        
        rescout_title = st.text_input(
            "再スカウト件名 (rescoutTitle)",
            value="",
            help="リマインド時などに使用する件名"
        )
        
        rescout_body = st.text_area(
            "再スカウト本文 (rescoutBody)",
            value="",
            help="リマインド時などに使用する本文。{NAME}は候補者名に自動置換されます"
        )

        # 送信前に叩く事前リクエスト用 SearchID
        search_id = 0

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # (1) 単体送信モード
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    if mode == "単体送信":
        st.markdown("---")
        st.markdown("### スカウト送信情報（単体）")

        # 単体送信用フィールド
        uid = st.number_input("スカウト先ユーザーID (UID)", min_value=1, value=287864)
        title = st.text_input("メッセージタイトル", value="【AI×HR Tech で事業拡大】営業職の募集")
        body = st.text_area(
            "メッセージ本文",
            value="NAME様\r\n\r\nはじめまして..."
        )

        if st.button("スカウトメッセージ送信（単体）"):
            # ログイン必須
            if not st.session_state.AMBI_USERNAME or not st.session_state.AMBI_PASSWORD:
                st.error("Username / Password が入力されていません。")
                return

            # 添付求人IDを整数配列に変換
            attachedWorkIDs = []
            if attached_work_input.strip():
                try:
                    for w_id_str in attached_work_input.split(","):
                        attachedWorkIDs.append(int(w_id_str.strip()))
                except ValueError:
                    st.error("添付求人IDはカンマ区切りの数字で入力してください。")
                    return

            # リクエストボディ
            payload = {
                "username": st.session_state.AMBI_USERNAME,
                "password": st.session_state.AMBI_PASSWORD,
                "UID": uid,
                "ScoutType": scout_type,
                "attachedWorkIDs": attachedWorkIDs,
                "Title": title,
                "Body": body
            }

            # オプションパラメータ
            if reply_deadline is not None:
                formatted_date = reply_deadline.strftime("%Y年%m月%d日")
                payload["ReplyDeadline"] = formatted_date

            if is_scout is not None:
                payload["isScout"] = is_scout
                
            if send_page > 0:
                payload["sendPage"] = send_page
                
            if rescout is not None:
                payload["rescout"] = rescout
                
            if retransmission is not None:
                payload["retransmission"] = retransmission
                
            if rescout_trans_select is not None:
                payload["rescoutTransSelect"] = rescout_trans_select
                
            if rescout_title.strip():
                payload["rescoutTitle"] = rescout_title.strip()
                
            if rescout_body.strip():
                payload["rescoutBody"] = rescout_body.strip()

            if search_id > 0:
                payload["search_id"] = search_id

            # 送信API
            scout_api_url = f"{api_base_url}/scout/send"
            st.info(f"以下のデータで {scout_api_url} に送信します: {payload}")

            try:
                response = requests.post(scout_api_url, json=payload, timeout=60)
                if response.status_code == 200:
                    resp_json = response.json()
                    if resp_json.get("status") == "success":
                        st.success(f"送信成功！message: {resp_json.get('message')}")
                    else:
                        st.error(f"送信エラー: {resp_json.get('message')}")
                else:
                    st.error(f"HTTPエラー: status_code={response.status_code}, body={response.text}")
            except Exception as e:
                st.exception(e)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # (2) 一括送信モード
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    else:
        st.markdown("---")
        st.markdown("### 一括送信情報（複数ユーザー）")

        st.write("**CSV のフォーマット例（ヘッダ必須）**:")
        st.code("ID,件名,本文\n12345,『件名A』,『本文A』\n23456,『件名B』,『本文B』", language="csv")

        # CSVファイルアップローダ
        uploaded_file = st.file_uploader("CSVファイルをアップロード (任意)", type=["csv"])
        st.write("アップロードしたCSVの内容は下のテーブルに反映されます。")

        # ★ Data Editor初期: 空DataFrame (型を明示指定) ★
        df = pd.DataFrame({"ID": pd.Series(dtype="Int64"),
                           "件名": pd.Series(dtype="string"),
                           "本文": pd.Series(dtype="string")})
        # ↑ こうすることで、CSV 未アップロード時でも ID列は Int64,
        #   件名/本文は string 型で扱われるようになり、float にならない

        # CSV読込 → DataFrame化
        if uploaded_file is not None:
            try:
                csv_text_decoded = uploaded_file.read().decode("utf-8")
                f = io.StringIO(csv_text_decoded)
                reader = csv.DictReader(f)
                rows = list(reader)
                # 同じ列名でDF化 (ID,件名,本文)
                df = pd.DataFrame(rows, columns=["ID","件名","本文"])

                # IDは整数(Int64)、件名/本文は文字列(string)でキャスト
                df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype("Int64")
                df["件名"] = df["件名"].astype("string")
                df["本文"] = df["本文"].astype("string")

            except Exception as e:
                st.error(f"CSVファイルの読み込みに失敗しました: {e}")

        # Data Editorで表示
        st.markdown("#### Data Editor（スプレッドシート風）")
        st.caption("ID=整数（カンマなし），件名/本文=テキスト入力可。")

        edited_df = st.data_editor(
            df,
            num_rows="dynamic",  # 行の追加許可
            use_container_width=True,
            column_config={
                "ID": st.column_config.NumberColumn(
                    label="ID",
                    format="%d",  # カンマなし10進数
                    help="整数のユーザーID"
                ),
                "件名": st.column_config.TextColumn(
                    label="件名",
                    help="メッセージの件名 (日本語OK)"
                ),
                "本文": st.column_config.TextColumn(
                    label="本文",
                    help="メッセージ本文 (日本語OK)"
                )
            }
        )

        st.write("#### 上記テーブルの内容を送信します。")

        if st.button("スカウトメッセージ送信（一括）"):
            # ログイン必須
            if not st.session_state.AMBI_USERNAME or not st.session_state.AMBI_PASSWORD:
                st.error("Username / Password が入力されていません。")
                return

            # 添付求人ID
            attachedWorkIDs = []
            if attached_work_input.strip():
                try:
                    for w_id_str in attached_work_input.split(","):
                        attachedWorkIDs.append(int(w_id_str.strip()))
                except ValueError:
                    st.error("添付求人IDはカンマ区切りの数字で入力してください。")
                    return

            # Data Editorの行データを取得
            rows = edited_df.to_dict(orient="records")
            if not rows:
                st.warning("テーブルが空です。送信データがありません。")
                return

            st.info("一括送信を開始します。")

            scout_api_url = f"{api_base_url}/scout/send"
            results = []
            progress_bar = st.progress(0)
            total = len(rows)

            # 一行ずつ送信
            for i, row in enumerate(rows):
                # ID, 件名, 本文 を取り出し
                # ID列が空 or null の場合は0になる可能性があるのでチェック
                uid = row.get("ID", 0)  
                title_str = str(row.get("件名", "")).strip()
                body_str = str(row.get("本文", "")).strip()

                if uid <= 0 or not title_str or not body_str:
                    results.append({
                        "ID": uid,
                        "Title": title_str,
                        "status": "error",
                        "message": "ID(>0)/件名/本文 のいずれかが不正または空です"
                    })
                    progress_bar.progress(int((i+1)/total*100))
                    continue

                # リクエストボディ
                payload = {
                    "username": st.session_state.AMBI_USERNAME,
                    "password": st.session_state.AMBI_PASSWORD,
                    "UID": int(uid),
                    "ScoutType": scout_type,
                    "attachedWorkIDs": attachedWorkIDs,
                    "Title": title_str,
                    "Body": body_str
                }

                # オプションパラメータ
                if reply_deadline is not None:
                    formatted_date = reply_deadline.strftime("%Y年%m月%d日")
                    payload["ReplyDeadline"] = formatted_date

                if is_scout is not None:
                    payload["isScout"] = is_scout

                if send_page > 0:
                    payload["sendPage"] = send_page

                if rescout is not None:
                    payload["rescout"] = rescout

                if retransmission is not None:
                    payload["retransmission"] = retransmission

                if rescout_trans_select is not None:
                    payload["rescoutTransSelect"] = rescout_trans_select

                if rescout_title.strip():
                    payload["rescoutTitle"] = rescout_title.strip()

                if rescout_body.strip():
                    payload["rescoutBody"] = rescout_body.strip()

                if search_id > 0:
                    payload["search_id"] = search_id

                # 送信実行
                try:
                    response = requests.post(scout_api_url, json=payload, timeout=60)
                    if response.status_code == 200:
                        resp_json = response.json()
                        if resp_json.get("status") == "success":
                            results.append({
                                "ID": uid,
                                "Title": title_str,
                                "status": "success",
                                "message": resp_json.get("message")
                            })
                        else:
                            results.append({
                                "ID": uid,
                                "Title": title_str,
                                "status": "error",
                                "message": resp_json.get("message")
                            })
                    else:
                        results.append({
                            "ID": uid,
                            "Title": title_str,
                            "status": "error",
                            "message": f"HTTPエラー: {response.status_code}"
                        })
                except Exception as e:
                    results.append({
                        "ID": uid,
                        "Title": title_str,
                        "status": "error",
                        "message": str(e)
                    })

                progress_bar.progress(int((i+1)/total*100))

            # 集計
            success_count = sum(1 for r in results if r["status"] == "success")
            error_count = len(results) - success_count

            st.success(f"一括送信が完了しました。 成功: {success_count}件 / 失敗: {error_count}件")
            # st.write("送信結果一覧:")
            # st.write(results)

def ambi_ai_search_tool():
    """
    AI×AMBi 求人検索。
    """
    st.title("AI×AMBi 求人検索チャットボット")

    st.write("以下の10項目に回答すると、AI(Gemini)が最適な検索条件を推定しAMBiの候補者リストを取得します。")

    # --- (A) 5つの選択式 ---
    # 1) 職種・ポジション(ラジオの例)
    job_positions = ["エンジニア", "営業", "マーケティング"]
    sel_job_position = st.radio("1) 希望する職種/ポジション", job_positions)

    # 2) 転職回数の上限(セレクトボックス例)
    job_change_dict = {
        "問わない(99)": 99,
        "転職なし(0)": 0,
        "1回以内(1)": 1,
        "2回以内(2)": 2,
        "3回以内(3)": 3
    }
    sel_job_change = st.selectbox("2) 転職回数の上限", list(job_change_dict.keys()))

    # 3) 英語レベル(セレクト)
    english_level_dict = {
        "不問(0)": 0,
        "基礎レベル(10)": 10,
        "日常会話レベル(20)": 20,
        "ビジネスレベル(30)": 30,
        "ネイティブレベル(40)": 40
    }
    sel_english = st.selectbox("3) 英語レベル", list(english_level_dict.keys()))

    # 4) 学歴に関する希望(セレクト)
    school_dict = {
        "問わない(0)": 0,
        "大学院卒以上(90)": 90,
        "大学卒以上(80)": 80,
        "高専卒以上(70)": 70,
        "短大卒以上(60)": 60,
        "専門各種学校卒以上(50)": 50,
        "高校卒以上(40)": 40
    }
    sel_school = st.selectbox("4) 学歴に関する希望", list(school_dict.keys()))

    # 5) 希望する最低年収(テキストorスライダーでもOK)
    min_income = st.slider("5) 希望する最低年収(万円)", 0, 2000, 300, step=50)

    # 取得ページ数の設定を追加
    max_pages = st.number_input("取得するページ数 (1ページ = 20件)", min_value=1, max_value=50, value=1)

    st.write("---")

    # --- (B) 5つの自由テキスト入力 ---
    free_q1 = st.text_input("6) 使いたいスキルや経験", "")
    free_q2 = st.text_input("7) 働きたい勤務地(都道府県やリモートなど)", "")
    free_q3 = st.text_input("8) 英語以外で希望する言語スキル(あれば)", "")
    free_q4 = st.text_input("9) いつまでに転職したいか", "")
    free_q5 = st.text_area("10) その他の希望・自由記述", "")


    # 送信ボタン
    if st.button("検索実行"):
        # 1) 10項目の回答を辞書にまとめる
        user_answers = {
            # 選択式(5問)
            "q1": sel_job_position,     # 職種
            "q2": sel_job_change,       # 転職回数の上限(ラベル)
            "q3": sel_english,          # 英語レベル(ラベル)
            "q4": sel_school,           # 学歴(ラベル)
            "q5": f"{min_income} 万円", # 希望最低年収
            # 自由入力(5問)
            "q6": free_q1,
            "q7": free_q2,
            "q8": free_q3,
            "q9": free_q4,
            "q10": free_q5,
        }

        # 2) Geminiに投げるプロンプトを組み立て
        prompt = construct_gemini_prompt(user_answers)

        # 3) Gemini APIへ問い合わせ → フィルタJSON取得
        ai_filters = call_gemini_api(prompt)

        # 4) ユーザーの選択をAMBi検索用パラメータに変換
        user_select_filters = {
            "JobChange": job_change_dict[sel_job_change],
            "School": school_dict[sel_school],
            "IncomeMin": min_income,
            "EnglishLevel": english_level_dict[sel_english],
            "AgeMin": 0,
            "AgeMax": 99,
            "ScoutUserFlg": True,
            "max_pages": max_pages  # 追加：ページ数の制限
        }

        # 5) AIフィルタとユーザー選択フィルタをマージ
        final_filters = merge_filters(ai_filters, user_select_filters)

        # 6) AMBi検索APIにPOST
        with st.spinner("AMBi検索中..."):
            result = call_ambi_search_api(st.session_state.AMBI_USERNAME, st.session_state.AMBI_PASSWORD, final_filters)

        # 7) 結果表示を CSV 形式に変更
        st.subheader("検索結果")
        if result["status"] == "success":
            st.success(result["message"])
            if result["candidates"]:
                st.write(f"候補者数: {len(result['candidates'])}")
                
                # 候補者データをDataFrameに変換
                df = pd.DataFrame(result["candidates"])
                
                # CSVとしてダウンロード可能に
                csv = df.to_csv(index=False)
                st.download_button(
                    label="CSVダウンロード",
                    data=csv,
                    file_name="ambi_candidates.csv",
                    mime="text/csv"
                )
                
                # データフレームとして表示
                st.dataframe(df)
            else:
                st.warning("候補者が見つかりませんでした。")
        else:
            st.error(f"エラー: {result['message']}")

def main():
    # グローバル定数の初期化
    init_global_constants()
    
    # サイドバーでログイン情報を入力
    sidebar_login()
    
    st.sidebar.title("ツール選択")
    app_mode = st.sidebar.selectbox("アプリを選択", ["スカウト送信ツール", "AI×AMBi求人検索"])
    api_base_url = "https://ambi-service-1077541053369.asia-northeast1.run.app/"
    
    if app_mode == "スカウト送信ツール":
        scout_message_tool(api_base_url)
    else:
        ambi_ai_search_tool()

if __name__ == "__main__":
    main()
