
import asyncio
import logging
from typing import Dict, List, Optional
import datetime

from playwright.async_api import async_playwright
import aiohttp
from bs4 import BeautifulSoup

from models import AmbiSearchFilter, CandidateData
from models import ScoutMessageRequest
from scraper import extract_candidates_from_html

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class AmbiHybridClient:
    BASE_URL = "https://en-ambi.com"
    
    def __init__(self):
        # Cookieやヘッダーは後でセット
        self.cookies: Dict[str, str] = {}
        self.headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'ja,en-US;q=0.9,en;q=0.8',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.BASE_URL,
            'pragma': 'no-cache',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        }

    async def login_with_playwright(self, username: str, password: str) -> bool:
        """
        Playwrightを使用してログインし、重要Cookie (PHPSESSID, C13CCなど) を取得
        """
        LOGIN_URL = f"{self.BASE_URL}/company_login/login/?PK=CC1E9D"
        logger.info(f"ログインを開始: {LOGIN_URL}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                await page.goto(LOGIN_URL)
                # ログインフォームへの入力
                await page.fill('input[name="accLoginID"]', username)
                await page.fill('input[name="accLoginPW"]', password)
                await page.click('button.loginbtn')

                # ネットワーク待ち + 画面安定化待ち
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)

                if "/company_login/login/" in page.url:
                    raise Exception("ログイン認証に失敗しました")

                # Cookie を取得
                cookies = await context.cookies()
                self.cookies = {cookie['name']: cookie['value'] for cookie in cookies}

                # 重要クッキーがちゃんと取れているか確認
                required_cookies = ['PHPSESSID', 'C13CC']
                missing_cookies = [c for c in required_cookies if c not in self.cookies]
                if missing_cookies:
                    raise Exception(f"必要なクッキーが取得できませんでした: {missing_cookies}")

                logger.info("ログイン成功")
                return True

            except Exception as e:
                logger.error(f"ログインエラー: {str(e)}")
                raise

            finally:
                await browser.close()

    def _build_search_params(self, filters: AmbiSearchFilter) -> Dict[str, str]:
        """
        検索パラメータの構築。
        必要そうなフォーム項目を cURL に合わせて網羅的に入れておく。
        """
        params = {
            'saved': '',
            'HopeIncomeMin': '',
            'IncludeNoHopeAreaFlg': '1',
            'SearchKeyword1': filters.SearchKeyword1 or '',
            'SearchKeyword2': filters.SearchKeyword2 or '',
            'SearchKeyword3': filters.SearchKeyword3 or '',
            'SearchKeyword4': '',
            'SearchKeyword5': '',
            'SearchKeyword6': '',
            'SearchKeyword7': '',
            'SearchKeyword8': '',
            'SearchKeyword9': '',
            'SearchKeyword10': '',
            'SearchKeyword11': '',
            'SearchKeyword12': '',
            'SearchKeyword13': '',
            'SearchKeyword14': '',
            'SearchKeyword15': '',
            'SearchKeyword16': '',
            'SearchKeyword17': '',
            'SearchKeyword18': '',
            'SearchKeyword19': '',
            'SearchKeyword20': '',
            'SearchKeyword21': '',
            'SearchKeyword22': '',
            'SearchKeyword23': '',
            'SearchKeyword24': '',
            'SearchKeyword25': '',
            'SearchKeyword26': '',
            'SearchKeyword27': '',
            'SearchKeyword28': '',
            'SearchKeyword29': '',
            'SearchKeyword30': '',

            'SearchOutKeyword1': filters.SearchOutKeyword1 or '',
            'SearchOutKeyword2': filters.SearchOutKeyword2 or '',
            'SearchOutKeyword3': filters.SearchOutKeyword3 or '',

            'EnglishLevel': '0',
            'EnglishConversation': '0',
            'EnglishComprehension': '0',
            'EnglishComposition': '0',
            'Toeic': '',
            'Toefl': '',
            'OtherLanguageID': '0',
            'OtherLanguageName': '',
            'QualificationOther1': '',
            'QualificationOther2': '',
            'QualificationOther3': '',
            'QualificationOther4': '',
            'QualificationOther5': '',

            'DepartmentName1': '',
            'DepartmentName2': '',
            'DepartmentName3': '',
            'DepartmentName4': '',
            'DepartmentName5': '',
            'CareerManageNumber': '',

            'UnemployedTerm': '0',
            'SchoolEducation1': '',
            'SchoolEducation2': '',
            'SchoolEducation3': '',
            'SchoolEducation4': '',
            'SchoolEducation5': '',
            'SchoolEducation6': '',
            'SchoolEducation7': '',
            'SchoolEducation8': '',
            'SchoolEducation9': '',
            'SchoolEducation10': '',
            'SchoolTypeIDList': '',

            'AgeMin': str(filters.AgeMin) if filters.AgeMin else '',
            'AgeMax': str(filters.AgeMax) if filters.AgeMax else '',
            'School': str(filters.School) if filters.School else '',
            'JobChange': str(filters.JobChange) if filters.JobChange else '',
            'IncomeMin': str(filters.IncomeMin) if filters.IncomeMin else '',
            'IncomeMax': str(filters.IncomeMax) if filters.IncomeMax else '',
            # Situation が None の場合は '0'
            'Situation': str(filters.Situation) if filters.Situation is not None else '0',
        }

        if filters.ScoutUserFlg:
            params['ScoutUserFlg'] = '1'
        
        return params

    async def _post_search(
        self,
        session: aiohttp.ClientSession,
        url: str,
        params: Dict[str, str],
        headers: Dict[str, str],
        save_filename_prefix: str
    ) -> str:
        """
        与えられたparamsをPOSTしてHTMLを取得する共通関数
        """
        async with session.post(url, data=params, headers=headers, allow_redirects=True) as response:
            text = await response.text()
            status_code = response.status

            # デバッグ用にレスポンスを保存
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{save_filename_prefix}_{status_code}_{timestamp}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"URL: {url}\n")
                f.write(f"Status: {status_code}\n")
                f.write("Request Headers:\n")
                for k, v in headers.items():
                    f.write(f"{k}: {v}\n")
                f.write("\nRequest Params:\n")
                f.write(str(params))
                f.write("\nResponse Headers:\n")
                for k, v in response.headers.items():
                    f.write(f"{k}: {v}\n")
                f.write("\nBody:\n")
                f.write(text)

            logger.info(f"レスポンス保存: {filename}")
            if status_code != 200:
                raise Exception(f"検索失敗: status={status_code}, url={url}")

            return text

    async def search_candidates(self, filters: AmbiSearchFilter) -> List[CandidateData]:
        """
        1) index画面へGET→ hiddenトークン(C13CT)取得
        2) 1ページ目のPOST送信→HTML取得
        3) ページ下部のリンク(href=?per_page=50...)を解析
        4) fetch_all_pages=True or max_pages指定に応じて 2ページ目以降を繰り返し取得
        5) すべてのページのCandidateDataを結合して返却
        """
        index_url = f"{self.BASE_URL}/company/scout/index/action/?PK=3FFFF4"
        search_url = f"{self.BASE_URL}/company/scout/search_list/?PK=3FFFF4"

        # ベースパラメータ (フォーム)
        base_params = self._build_search_params(filters)

        # POST時に送る拡張パラメータ
        extended_params = {
            **base_params,
            'C13CT': '',  # 後でindex画面から取得
            'TargetFirst': '1',
            'UserDateType': '0',
            'UserDateRange': '0',
            'ScoutReceiveCount': '-1',
            'Site[]': ['2', '1'],
            'CID': '62427',
            'isAvailableScoutMerge': '1',
            'AccID': '5886966',
            'VicariousAccID': '0',
            'SalesAccountID': '0',
            'isInputEnglish': '0',
            'isSaveCondition': '',
            'isSendMail': '',
        }

        # HTTP セッションとヘッダー
        headers = {
            **self.headers,
            'referer': index_url,
            'cookie': '; '.join([f"{k}={v}" for k, v in self.cookies.items()]),
        }

        all_candidates: List[CandidateData] = []

        async with aiohttp.ClientSession() as session:
            session.cookie_jar.update_cookies(self.cookies)

            # (A) index画面でCSRFトークン取得
            async with session.get(index_url, headers=headers) as index_resp:
                index_html = await index_resp.text()
                if index_resp.status != 200:
                    raise Exception("検索画面へのアクセスに失敗")

            soup = BeautifulSoup(index_html, 'html.parser')
            c13ct_input = soup.find('input', {'name': 'C13CT'})
            if not c13ct_input or not c13ct_input.has_attr('value'):
                raise Exception("CSRFトークン(C13CT)を取得できませんでした")
            extended_params['C13CT'] = c13ct_input['value']

            # (B) 1ページ目をPOST
            first_page_html = await self._post_search(
                session=session,
                url=search_url,
                params=extended_params,
                headers=headers,
                save_filename_prefix="response_first_page"
            )

            candidates_page1 = extract_candidates_from_html(first_page_html)
            all_candidates.extend(candidates_page1)

            # ページネーションが不要ならここで終了
            if (not filters.fetch_all_pages) and (filters.max_pages is None or filters.max_pages <= 1):
                return all_candidates

            # (C) 1ページ目のHTMLから、ページ下のリンクに含まれる per_page= の値を解析
            soup_1st = BeautifulSoup(first_page_html, 'html.parser')
            page_links = soup_1st.select("ul.pageList li a.link")

            offsets = []
            for link in page_links:
                href = link.get("href", "")
                if "per_page=" in href:
                    import re
                    m = re.search(r"per_page=(\d+)", href)
                    if m:
                        val = int(m.group(1))
                        if val > 0:
                            offsets.append(val)

            offsets = sorted(set(offsets))

            if not offsets:
                logger.info("2ページ目以降のリンクが見当たらなかったため終了")
                return all_candidates

            current_page = 1
            if not filters.fetch_all_pages and filters.max_pages:
                needed_pages_count = filters.max_pages - 1  # 1ページ目は取得済
                offsets = offsets[:needed_pages_count]

            for offset in offsets:
                current_page += 1
                logger.info(f"=== {current_page}ページ目を取得します (per_page={offset}) ===")

                page_url = f"{search_url}&per_page={offset}"
                page_params = {
                    **extended_params,
                    'per_page': str(offset)
                }

                page_html = await self._post_search(
                    session=session,
                    url=page_url,
                    params=page_params,
                    headers=headers,
                    save_filename_prefix=f"response_page{current_page}"
                )

                page_candidates = extract_candidates_from_html(page_html)
                if not page_candidates:
                    logger.info(f"{current_page}ページ目に候補者が見つからないため終了します。")
                    break
                all_candidates.extend(page_candidates)
                await asyncio.sleep(1)

        return all_candidates

    # ============== 追加: cURL相当の事前POST関数 ==============
    async def fetch_scout_list_frame(
        self,
        SID: int,
        search_id: int,
        c13ct: Optional[str] = None,
        sendpage: str = "scoutfolder"
    ) -> str:
        """
        cURLで指定されている下記URLに対してPOST:
         https://en-ambi.com/company/api/scout_list_message_frame/index/scoutfolder/?sendpage=scoutfolder&SearchID=XXXX
        - data: SID, C13CT
        これによりスカウトフォルダ一覧などを事前取得し、サーバー側の状態を整える。
        """
        url = f"{self.BASE_URL}/company/api/scout_list_message_frame/index/scoutfolder/?sendpage={sendpage}&SearchID={search_id}"

        async with aiohttp.ClientSession() as session:
            session.cookie_jar.update_cookies(self.cookies)

            # CSRFトークンが指定されていなければ取得
            if not c13ct:
                c13ct = await self._get_c13ct_token(session)

            post_data = {
                "SID": str(SID),
                "C13CT": c13ct
            }
            # XHRと同等のヘッダ追加
            headers = {
                **self.headers,
                "cookie": "; ".join([f"{k}={v}" for k, v in self.cookies.items()]),
                "x-requested-with": "XMLHttpRequest",
                "referer": f"{self.BASE_URL}/company/scout/folder/?SearchID={search_id}&PK=CC1E9D"
            }

            async with session.post(url, data=post_data, headers=headers) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise Exception(
                        f"fetch_scout_list_frame 失敗: status={resp.status}, url={url}"
                    )
                # 必要に応じてログ保存や解析
                return text

    async def _get_c13ct_token(self, session: aiohttp.ClientSession) -> str:
        """
        スカウト送信時などに必要なC13CTトークンを再取得。
        """
        index_url = f"{self.BASE_URL}/company/scout/index/action/?PK=3FFFF4"
        headers = {
            **self.headers,
            "cookie": "; ".join([f"{k}={v}" for k,v in self.cookies.items()]),
            "referer": f"{self.BASE_URL}/company_login/login/",
        }
        async with session.get(index_url, headers=headers) as resp:
            if resp.status != 200:
                raise Exception("C13CTトークン取得ページへのアクセスに失敗")

            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            c13ct_input = soup.find('input', {'name': 'C13CT'})
            if not c13ct_input or not c13ct_input.has_attr("value"):
                raise Exception("CSRFトークン(C13CT)を取得できませんでした")
            return c13ct_input["value"]

    async def send_scout_message(self, request: ScoutMessageRequest) -> bool:
        """
        スカウトメッセージ送信処理
        - 事前に login_with_playwright() で cookies を取得しておく前提。
        - 内部で C13CT (CSRFトークン) を再取得し、POST を投げる。
        """
        url = f"{self.BASE_URL}/company/api/scout_send/run"

        async with aiohttp.ClientSession() as session:
            session.cookie_jar.update_cookies(self.cookies)

            # (1) 最新の C13CT を取得
            c13ct_value = await self._get_c13ct_token(session)

            # (2) POST データの組み立て
            post_data = {
                "C13CT": c13ct_value,
                "UID": str(request.UID),
                "ScoutType": str(request.ScoutType),
            }
            # attachedWorkID[] は複数ある場合に対応
            for i, w_id in enumerate(request.attachedWorkIDs):
                post_data[f"attachedWorkID[{i}]"] = str(w_id)

            post_data["Title"] = request.Title
            post_data["Body"] = request.Body

            # 任意パラメータ
            if request.ReplyDeadline is not None:
                post_data["ReplyDeadline"] = request.ReplyDeadline
            if request.isScout is not None:
                post_data["isScout"] = str(request.isScout)
            if request.sendPage is not None:
                post_data["sendPage"] = str(request.sendPage)

            # 再スカウト関連
            if request.rescout is not None:
                post_data["rescout"] = str(request.rescout)
            if request.retransmission is not None:
                post_data["retransmission"] = str(request.retransmission)
            if request.rescoutTransSelect is not None:
                post_data["rescoutTransSelect"] = str(request.rescoutTransSelect)
            if request.rescoutTitle is not None:
                post_data["rescoutTitle"] = request.rescoutTitle
            if request.rescoutBody is not None:
                post_data["rescoutBody"] = request.rescoutBody

            # (3) POST 送信
            headers = {
                **self.headers,
                "cookie": "; ".join([f"{k}={v}" for k, v in self.cookies.items()]),
                "referer": f"{self.BASE_URL}/company/scout/index/action/?PK=3FFFF4",
            }

            async with session.post(url, data=post_data, headers=headers) as resp:
                resp_text = await resp.text()
                status_code = resp.status

                # デバッグ用にレスポンスを保存
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"scout_send_{status_code}_{timestamp}.html"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(resp_text)
                logger.info(f"Scout message response saved to: {filename}")

                if status_code != 200:
                    logger.error(f"スカウト送信APIがステータス {status_code} を返しました")
                    return False

                # レスポンス内容をチェック (実際の判定ロジックは運用に合わせて実装)
                if "エラー" in resp_text or "error" in resp_text.lower():
                    logger.error("スカウト送信APIのレスポンスにエラーらしき文字が含まれます")
                    return False

                logger.info("スカウト送信完了")
                return True


async def search_with_hybrid(username: str, password: str, filters: AmbiSearchFilter) -> List[CandidateData]:
    """
    ハイブリッド方式での検索実行:
    1) Playwrightでログイン (重要Cookie取得)
    2) HTTPセッション(aiohttp) + CSRFトークン で1ページ目POST
    3) HTMLからページネーションリンクを抽出 → 2ページ目以降もPOSTで取得
    4) すべてのページの候補者を連結して返す
    """
    client = AmbiHybridClient()
    max_retries = 2
    retry_delay = 3

    for attempt in range(max_retries):
        try:
            # 1) ログイン → Cookie保持
            await client.login_with_playwright(username, password)
            await asyncio.sleep(1)

            # 2) ページネーション対応で全候補者を取得
            candidates = await client.search_candidates(filters)

            if not candidates:
                logger.warning("検索結果が0件でした")
            return candidates

        except Exception as e:
            logger.error(f"試行 {attempt + 1}/{max_retries} 回目でエラー: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"{retry_delay}秒後にリトライします...")
                await asyncio.sleep(retry_delay)
            else:
                raise Exception(f"最大リトライ回数に達しました: {str(e)}")


