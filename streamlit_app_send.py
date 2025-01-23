# streamlit_app_send.py

import streamlit as st
import requests
import json
import io
import csv
import pandas as pd
from datetime import datetime

def main():
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
    # 共通: ログイン情報
    # =========================================
    st.markdown("### ログイン情報")
    username = st.text_input("Username (AMBIアカウント)")
    password = st.text_input("Password (AMBIパスワード)", type="password")

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
            if not username or not password:
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
                "username": username,
                "password": password,
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
            if not username or not password:
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
                    "username": username,
                    "password": password,
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
            st.write("送信結果一覧:")
            st.write(results)


if __name__ == "__main__":
    main()
