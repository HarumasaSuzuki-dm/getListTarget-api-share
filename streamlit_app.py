import streamlit as st
import requests
import json
import google.generativeai as genai
import os
import pandas as pd
from typing import Dict, Any

# Gemini API の設定
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

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

def main():
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

    # ユーザー認証情報（デモ用）
    username = st.text_input("ログインID", "MBYXB001")
    password = st.text_input("パスワード", "$brbJ#Z7vkcwk", type="password")

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
        st.markdown("**[Debug] Geminiへのプロンプト**")
        st.code(prompt)

        # 3) Gemini APIへ問い合わせ → フィルタJSON取得
        ai_filters = call_gemini_api(prompt)
        st.markdown("**[Debug] Geminiからのフィルタ推定結果**")
        st.json(ai_filters)

        # 4) ユーザーの選択をAMBi検索用パラメータに変換
        #    （本来はAI推定と整合性を取りながらマージ）
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
        st.markdown("**最終フィルタ**")
        st.json(final_filters)

        # 6) AMBi検索APIにPOST
        with st.spinner("AMBi検索中..."):
            result = call_ambi_search_api(username, password, final_filters)

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

# Streamlit実行時に main() を呼び出し
if __name__ == "__main__":
    main()
