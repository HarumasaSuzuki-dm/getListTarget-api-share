from typing import List
from bs4 import BeautifulSoup
from models import CandidateData

def extract_candidates_from_html(html: str) -> List[CandidateData]:
    """
    結果ページの <div class="userSet"> を解析し、候補者情報を抽出
    """
    soup = BeautifulSoup(html, "html.parser")
    user_sets = soup.find_all("div", class_="userSet")

    results = []
    for us in user_sets:
        # 1) ID
        input_id = us.find("input", class_="js_sid")
        cid = None
        if input_id and input_id.has_attr("value"):
            try:
                cid = int(input_id["value"])
            except:
                cid = None

        # 2) 性別/年齢/住所
        gender, age, location = None, None, None
        prof_div = us.find("div", class_="prof")
        if prof_div:
            txt = prof_div.get_text(strip=True)
            if "女性" in txt:
                gender = "女性"
            elif "男性" in txt:
                gender = "男性"

            import re
            m_age = re.search(r'(\d+)歳', txt)
            if m_age:
                age = int(m_age.group(1))
            m_loc = re.search(r'歳\s*/\s*(\S+)', txt)
            if m_loc:
                location = m_loc.group(1)

        # 3) UserNo
        user_no = None
        num_div = us.find("div", class_="num")
        if num_div:
            tmp = num_div.get_text(strip=True)
            if tmp.startswith("No."):
                try:
                    user_no = int(tmp.replace("No.", ""))
                except:
                    pass

        # 4) 企業情報
        company, sub_info = None, None
        comp_div = us.find("div", class_="companyData")
        if comp_div:
            name_div = comp_div.find("div", class_="name")
            if name_div:
                company = name_div.get_text(strip=True)
            sub_div = comp_div.find("div", class_="sub")
            if sub_div:
                sub_info = sub_div.get_text(strip=True)

        # 5) 学歴/転職回数/職種/言語
        edu, change_times, language = None, None, None
        past_jobs = []
        data_li = us.find_all("li", class_="data")
        for li in data_li:
            cls = li.get("class", [])
            text_li = li.get_text(strip=True)
            if "school" in cls:
                edu = text_li
            elif "change" in cls:
                change_times = text_li.replace("転職回数：", "")
            elif "pastjob" in cls:
                past_jobs.append(text_li)
            elif "language" in cls:
                language = text_li

        # 6) 自己PR/summary
        summary = None
        summary_div = us.find("div", class_="resumeContent")
        if summary_div:
            summary = summary_div.get_text(strip=True)

        candidate = CandidateData(
            id=cid,
            gender=gender,
            age=age,
            location=location,
            no=user_no,
            company=company,
            sub=sub_info,
            education=edu,
            change_times=change_times,
            past_jobs=past_jobs,
            language=language,
            summary=summary
        )
        results.append(candidate)

    return results
