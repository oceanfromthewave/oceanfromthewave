"""커밋 시각을 KST 기준으로 집계해 README의 waka 섹션을 갱신한다.

GitHub Search API(search/commits)로 본인이 author인 커밋을 최대 1000건 조회한 뒤
시간대(Morning/Daytime/Evening/Night) 4구간으로 나눠 막대그래프를 만든다.
WakaTime 같은 외부 서비스 없이 GH_TOKEN 하나만 있으면 동작한다.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"
KST = timezone(timedelta(hours=9))
BAR_LENGTH = 25
MAX_PAGES = 10  # Search API는 최대 1000건(100 * 10)

USER = os.environ.get("GH_USER", "oceanfromthewave")
TOKEN = os.environ["GH_TOKEN"]
README_PATH = os.environ.get("README_PATH", "README.md")

# (라벨, 시작시각, 끝시각) — 끝시각 미포함
BUCKETS = [
    ("🌞 Morning", 6, 12),
    ("🌆 Daytime", 12, 18),
    ("🌃 Evening", 18, 24),
    ("🌙 Night", 0, 6),
]


def gh_get(url):
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "coding-habits-script",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def fetch_commit_hours():
    """본인 커밋의 KST 시각(0~23)별 개수를 센다."""
    hours = Counter()
    for page in range(1, MAX_PAGES + 1):
        url = (
            f"{API}/search/commits?q=author:{USER}"
            f"&sort=author-date&order=desc&per_page=100&page={page}"
        )
        try:
            payload = gh_get(url)
        except urllib.error.HTTPError as error:
            print(f"search/commits 실패 (page {page}): {error}", file=sys.stderr)
            break

        items = payload.get("items", [])
        for item in items:
            raw = item["commit"]["author"]["date"]
            moment = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(KST)
            hours[moment.hour] += 1

        if len(items) < 100:
            break
    return hours


def build_section(hours):
    counts = []
    for label, start, end in BUCKETS:
        counts.append((label, sum(hours[h] for h in range(start, end))))

    total = sum(count for _, count in counts)
    if total == 0:
        return "아직 집계할 커밋이 없습니다."

    daylight = counts[0][1] + counts[1][1]
    title = "I'm an Early 🐤" if daylight >= total / 2 else "I'm a Night 🦉"

    lines = [f"**{title}**", "", "```text"]
    for label, count in counts:
        ratio = count / total
        filled = round(ratio * BAR_LENGTH)
        bar = "█" * filled + "░" * (BAR_LENGTH - filled)
        lines.append(f"{label:<12}{count:>5} commits  {bar}  {ratio * 100:>5.1f}%")
    lines.append("```")

    updated = datetime.now(KST).strftime("%Y-%m-%d")
    lines.append("")
    lines.append(f"<sub>최근 커밋 {total}건 기준 · KST · {updated} 갱신</sub>")
    return "\n".join(lines)


def main():
    section = build_section(fetch_commit_hours())

    with open(README_PATH, encoding="utf-8") as file:
        readme = file.read()

    pattern = re.compile(
        r"(<!--START_SECTION:waka-->).*?(<!--END_SECTION:waka-->)", re.DOTALL
    )
    if not pattern.search(readme):
        print("README에 waka 마커가 없습니다.", file=sys.stderr)
        return 1

    updated = pattern.sub(rf"\1\n\n{section}\n\n\2", readme)
    if updated == readme:
        print("변경 사항 없음")
        return 0

    with open(README_PATH, "w", encoding="utf-8") as file:
        file.write(updated)
    print("README 갱신 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
