"""
LinkedIn API → data.json 생성
GitHub Actions에서 매주 실행 → GitHub Pages 대시보드 자동 업데이트
"""

import os
import json
import requests
from datetime import datetime

ACCESS_TOKEN = os.environ["LINKEDIN_ACCESS_TOKEN"]
ORG_ID       = "70998576"
DATA_FILE    = "docs/data.json"

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "X-Restli-Protocol-Version": "2.0.0",
    "LinkedIn-Version": "202401",
}

# ── 1. 팔로워 수 ──────────────────────────────────────────────────
def get_followers():
    url = f"https://api.linkedin.com/v2/networkSizes/urn:li:organization:{ORG_ID}?edgeType=CompanyFollowedByMember"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        return res.json().get("firstDegreeSize", 0)
    print(f"[팔로워 오류] {res.status_code}: {res.text}")
    return 0

# ── 2. 포스팅 목록 ────────────────────────────────────────────────
def get_posts(count=20):
    url = f"https://api.linkedin.com/v2/shares?q=owners&owners=urn:li:organization:{ORG_ID}&count={count}&sortBy=LAST_MODIFIED"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        print(f"[포스팅 오류] {res.status_code}: {res.text}")
        return []
    return res.json().get("elements", [])

# ── 3. 포스팅별 성과 ──────────────────────────────────────────────
def get_stats(share_urn):
    encoded = requests.utils.quote(share_urn, safe="")
    url = (
        f"https://api.linkedin.com/v2/organizationalEntityShareStatistics"
        f"?q=organizationalEntity"
        f"&organizationalEntity=urn:li:organization:{ORG_ID}"
        f"&shares=List({encoded})"
    )
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        return {}
    els = res.json().get("elements", [])
    if not els:
        return {}
    s = els[0].get("totalShareStatistics", {})
    return {
        "impressions": s.get("impressionCount", 0),
        "reactions":   s.get("likeCount", 0),
        "clicks":      s.get("clickCount", 0),
        "comments":    s.get("commentCount", 0),
        "shares":      s.get("shareCount", 0),
    }

# ── 4. 기존 data.json 로드 (히스토리 누적용) ─────────────────────
def load_existing():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"follower_history": [], "posts": [], "last_updated": ""}

# ── MAIN ──────────────────────────────────────────────────────────
def main():
    today = datetime.today().strftime("%Y-%m-%d")
    print(f"[{today}] 데이터 수집 시작")

    existing = load_existing()

    # 팔로워
    followers = get_followers()
    print(f"팔로워: {followers:,}")

    # 히스토리 누적 (같은 날짜 중복 방지)
    history = existing.get("follower_history", [])
    if not history or history[-1]["date"] != today:
        history.append({"date": today, "count": followers})
    history = history[-52:]  # 최근 52주 유지

    # 포스팅 성과
    posts = get_posts(count=20)
    posts_data = []
    for post in posts:
        urn = post.get("activity") or post.get("id", "")
        if not urn:
            continue
        stats = get_stats(urn)
        text  = ""
        content = post.get("text", {})
        if isinstance(content, dict):
            text = content.get("text", "")[:80]

        impr = stats.get("impressions", 0)
        reac = stats.get("reactions", 0)
        clk  = stats.get("clicks", 0)
        comm = stats.get("comments", 0)
        eng  = round((reac + clk + comm) / impr * 100, 2) if impr > 0 else 0

        posts_data.append({
            "urn":         urn,
            "url":         f"https://www.linkedin.com/feed/update/{urn}",
            "text":        text,
            "date":        today,
            "impressions": impr,
            "reactions":   reac,
            "clicks":      clk,
            "comments":    comm,
            "shares":      stats.get("shares", 0),
            "eng_rate":    eng,
        })
    print(f"포스팅 {len(posts_data)}개 수집")

    # 저장
    os.makedirs("docs", exist_ok=True)
    data = {
        "last_updated":     today,
        "follower_count":   followers,
        "follower_goal":    200000,
        "follower_history": history,
        "posts":            posts_data,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ {DATA_FILE} 저장 완료")

if __name__ == "__main__":
    main()
