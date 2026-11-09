"""구글 뉴스 RSS로 상하수도 기사를 모아 data.json을 갱신한다 (표준 라이브러리만 사용)."""
import json, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
TODAY = NOW.date()
DATA = "data.json"

REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원",
           "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
REGION_WORDS = {
    "서울": ["서울"], "부산": ["부산"], "대구": ["대구"], "인천": ["인천", "송도", "옹진", "강화군"],
    "광주": ["광주광역시", "광주시 광산", "광산구"], "대전": ["대전"], "울산": ["울산"], "세종": ["세종시", "세종특별"],
    "경기": ["경기", "수원", "성남", "고양", "용인", "부천", "안산", "안양", "남양주", "화성", "평택", "의정부", "시흥", "파주", "김포", "광명", "군포", "하남", "오산", "이천", "안성", "의왕", "양평", "여주", "가평", "연천", "포천", "동두천", "양주", "구리"],
    "강원": ["강원", "춘천", "원주", "강릉", "동해시", "속초", "삼척", "태백", "정선", "평창", "홍천", "횡성", "영월", "철원", "화천", "양구", "인제", "고성군", "양양"],
    "충북": ["충북", "충청북도", "청주", "충주", "제천", "보은", "옥천", "영동", "증평", "진천", "괴산", "음성", "단양"],
    "충남": ["충남", "충청남도", "천안", "공주", "보령", "아산", "서산", "논산", "계룡", "당진", "금산", "부여", "서천", "청양", "홍성", "예산", "태안"],
    "전북": ["전북", "전라북도", "전주", "군산", "익산", "정읍", "남원", "김제", "완주", "진안", "무주", "장수", "임실", "순창", "고창", "부안"],
    "전남": ["전남", "전라남도", "목포", "여수", "순천", "나주", "광양", "담양", "곡성", "구례", "고흥", "보성", "화순", "장흥", "강진", "해남", "영암", "무안", "함평", "영광", "장성", "완도", "진도", "신안"],
    "경북": ["경북", "경상북도", "포항", "경주", "김천", "안동", "구미", "영주", "영천", "상주", "문경", "경산", "의성", "청송", "영양", "영덕", "청도", "고령", "성주", "칠곡", "예천", "봉화", "울진", "울릉"],
    "경남": ["경남", "경상남도", "창원", "진주", "통영", "사천", "김해", "밀양", "거제", "양산", "의령", "함안", "창녕", "남해", "하동", "산청", "함양", "거창", "합천"],
    "제주": ["제주", "서귀포", "애월", "한림", "조천", "구좌", "성산", "표선", "남원읍", "대정", "안덕"],
}
FOCUS_KW = ["개인하수처리시설", "개인오수처리시설", "오수처리시설", "정화조"]
GENERAL_KW = ["하수처리장", "하수처리시설", "하수관로", "하수도", "상수도", "상수관", "수돗물", "정수장",
              "단수", "누수", "분뇨", "오수 유출", "오수 방류", "하수 역류", "마을하수도", "지하수 관정",
              "환경영향평가 오수", "오수 자체처리", "용수 공급 계획", "가축분뇨 무단"]
WATER = re.compile(r"하수|오수|상수|수돗물|정화조|분뇨|정수장|단수|누수|지하수|용수|배수설비|맨홀|싱크홀|급수|취수|수도요금|수도관")
FOCUS = re.compile(r"개인하수|개인 하수|오수처리시설|개인오수|정화조|(?<!가축)(?<!축산 )분뇨|오수 (?:자체|유출|방류)|화장실 오수")
FOREIGN = re.compile(r"베트남|호치민|하노이|중국|일본|미국|파리|런던|태국|필리핀|인도네시아|캄보디아|몽골|Vietnam")
OPINION = re.compile(r"^\s*[\[【<〈(]\s*(기고|칼럼|사설|시론|오피니언|기자수첩|데스크|발언대|열린마당|독자투고)")
TAGS = [("정화조", "정화조"), ("개인오수|오수처리시설", "개인오수처리시설"), ("개인하수", "개인하수처리시설"),
        ("분뇨", "분뇨"), ("점검|단속|적발", "점검"), ("지원", "지원사업"), ("과태료|고발|처분", "행정처분"),
        ("유출|역류|방류", "유출"), ("하수관|관로", "하수관로"), ("하수처리장|하수처리시설", "하수처리장"),
        ("상수|수돗물|정수장|급수", "상수도"), ("지하수|관정", "지하수"), ("가뭄|저수율", "가뭄"),
        ("요금", "요금"), ("악취", "악취"), ("침수", "침수"), ("싱크홀|지반침하", "싱크홀"), ("조례|법 개정|하수도법|수도법", "제도")]


def rss(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": f"{query} when:3d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (water-news-briefing)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return parse(r.read())
    except Exception as e:
        print("skip", query, e)
        return []


def parse(xml_bytes):
    out = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        title = (it.findtext("title") or "").strip()
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        while source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)].strip()
        try:
            d = parsedate_to_datetime(it.findtext("pubDate")).astimezone(KST).date()
        except Exception:
            continue
        out.append({"title": title, "url": (it.findtext("link") or "").strip(), "source": source, "date": d.isoformat()})
    return out


def region_of(text, hint):
    for r in REGIONS:
        if any(w in text for w in REGION_WORDS[r]):
            return r
    return hint or "전국"


def norm(t):
    return re.sub(r"[\W_]+", "", re.sub(r"\[[^\]]*\]", "", t)).lower()


def toks(t):
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", t)
    return {w for w in re.findall(r"[가-힣A-Za-z0-9]+", t) if len(w) >= 2}


def similar(a, b):
    A, B = toks(a), toks(b)
    return bool(A and B) and len(A & B) / min(len(A), len(B)) >= 0.5


def group(arts):
    """같은 보도자료를 여러 매체가 실은 기사를 한 묶음으로 표시한다(지우지 않음). group = 대표 기사 url."""
    reps = []
    for a in sorted(arts, key=lambda a: (not a.get("summary"), a.get("date", ""))):
        rep = None if a.get("summary") else next(
            (r for r in reps if r["region"] == a["region"] and similar(r["title"], a["title"])), None)
        if rep:
            a["group"] = rep["url"]
        else:
            a["group"] = a["url"]
            reps.append(a)
    return len(reps)


def keep(a):
    days = 183 if a.get("region") == "제주" else 30
    try:
        return datetime.fromisoformat(a["date"]).date() >= TODAY - timedelta(days=days)
    except Exception:
        return False


def make_reports(arts):
    by = {}
    for a in arts:
        by.setdefault(a["region"], []).append(a)
    reps = []
    for region, items in list(by.items()) + [("전국", arts)]:
        items = sorted(items, key=lambda a: a["date"], reverse=True)
        foc = [a for a in items if a.get("focus")]
        tags = Counter(t for a in items for t in a.get("tags", []))
        top = ", ".join(f"{t}({n})" for t, n in tags.most_common(5)) or "없음"
        reps.append({
            "id": region, "region": region, "count": len(items),
            "updatedText": NOW.strftime("%Y.%m.%d") + " 자동 집계",
            "headline": f"{region} 상하수도 기사 {len(items)}건 · 개인하수처리시설 {len(foc)}건",
            "focus": ["최근 개인하수처리시설 기사: " + (" / ".join(f"{a['title']} ({a['source']}, {a['date']})" for a in foc[:3]) if foc else "최근 개인하수처리시설 기사가 없습니다.")],
            "body": ["많이 나온 주제: " + top + ".", "최신 기사: " + " / ".join(f"{a['title']} ({a['date']})" for a in items[:3]) + "."],
            "keyPoints": [f"전체 {len(items)}건", f"개인하수처리시설 {len(foc)}건", f"기고·칼럼 {sum(a.get('kind') == '기고' for a in items)}건"],
        })
    return reps


def main():
    try:
        data = json.load(open(DATA, encoding="utf-8"))
    except Exception:
        data = {"articles": []}
    arts = [a for a in data.get("articles", []) if keep(a)]
    seen_url = {a["url"] for a in arts}
    seen_title = {norm(a["title"]) for a in arts}

    queries = [(f"{k} {r}", r) for k in FOCUS_KW for r in REGIONS] + [(k, None) for k in GENERAL_KW + FOCUS_KW] \
        + [(f"{k} 제주", "제주") for k in ["오수", "하수", "상수도", "지하수", "용수 공급"]]
    new = 0
    for q, hint in queries:
        for it in rss(q):
            t = it["title"]
            if not WATER.search(t) or it["url"] in seen_url or norm(t) in seen_title:
                continue
            if not keep({"date": it["date"], "region": "제주"}):
                continue
            it["region"] = "해외" if FOREIGN.search(t + " " + it["source"]) else region_of(t, hint)
            if not keep(it):
                continue
            it["city"] = ""
            it["focus"] = bool(FOCUS.search(t))
            it["kind"] = "기고" if OPINION.search(t) else "기사"
            it["tags"] = [name for pat, name in TAGS if re.search(pat, t)][:3]
            it["summary"] = ""
            it["figures"] = []
            arts.append(it)
            seen_url.add(it["url"]); seen_title.add(norm(t)); new += 1
        time.sleep(1)

    for a in arts:
        if not a.get("summary"):
            a["focus"] = bool(FOCUS.search(a["title"]))
        if not a.get("summary") and FOREIGN.search(a["title"] + " " + a.get("source", "")):
            a["region"] = "해외"
    stories = group(arts)
    arts.sort(key=lambda a: a["date"], reverse=True)
    cnt = Counter(a["region"] for a in arts)
    order = sorted(cnt, key=lambda r: (REGIONS + ["전국", "해외"]).index(r) if r in REGIONS + ["전국", "해외"] else 99)
    foc = sum(bool(a.get("focus")) for a in arts)
    opn = sum(a.get("kind") == "기고" for a in arts)
    meta = {
        "lastRun": TODAY.isoformat(),
        "lastRunText": NOW.strftime("%Y.%m.%d %H:%M") + (f" 갱신 · 신규 {new}건" if new else " 확인 · 신규 없음"),
        "overall": [
            f"상하수도 기사 {len(arts)}건(같은 내용 묶음 기준 {stories}건, 개인하수처리시설 {foc}건, 기고 {opn}건)을 " + "·".join(f"{r}({cnt[r]})" for r in order)
            + "에서 모았습니다. 제주는 최근 6개월, 그 밖의 지역은 최근 30일 기사를 남깁니다.",
            "구글 뉴스 검색 결과를 매일 자동으로 모은 목록입니다. 여러 매체가 같은 보도자료를 실은 기사는 한 묶음으로 보여 주며, 해외 상하수도 소식은 [해외]로 따로 모읍니다. 제목의 지역명과 검색어로 분류했으므로 일부 분류가 다를 수 있고, 정확한 내용은 원문 링크로 확인하세요.",
        ],
    }
    json.dump({"articles": arts, "reports": make_reports(arts), "meta": meta}, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("new", new, "total", len(arts))


if __name__ == "__main__":
    main()
