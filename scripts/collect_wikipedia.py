
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "knowledge_base" / "raw_wikipedia.json"
API_URL = "https://en.wikipedia.org/w/api.php"

# Replace this with a real contact email if possible.
HEADERS = {
    "User-Agent": (
        "PlantCareExpert/1.0 "
        "(educational plant-care research; contact: YOUR_EMAIL@example.com)"
    )
}

PLANTS = [
    {
        "plant_id": "PLANT001",
        "plant_name": "Money Plant",
        "wiki_title": "Epipremnum aureum",
    },
    {
        "plant_id": "PLANT002",
        "plant_name": "Snake Plant",
        "wiki_title": "Dracaena trifasciata",
    },
    {
        "plant_id": "PLANT003",
        "plant_name": "Aloe Vera",
        "wiki_title": "Aloe vera",
    },
    {
        "plant_id": "PLANT004",
        "plant_name": "Spider Plant",
        "wiki_title": "Chlorophytum comosum",
    },
    {
        "plant_id": "PLANT005",
        "plant_name": "Peace Lily",
        "wiki_title": "Spathiphyllum",
    },
]


def collect_article(session, plant):
    params = {
        "action": "parse",
        "page": plant["wiki_title"],
        "prop": "text|revid|displaytitle",
        "format": "json",
    }

    response = session.get(
        API_URL,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        return {
            **plant,
            "status": "api_error",
            "error": data["error"].get("info", "Unknown API error"),
            "review_status": "needs_manual_review",
        }

    article = data.get("parse", {})

    if not article:
        return {
            **plant,
            "status": "empty_article",
            "review_status": "needs_manual_review",
        }

    html = article.get("text", "")

    # Support both possible response formats.
    if isinstance(html, dict):
        html = html.get("*", "")

    soup = BeautifulSoup(html, "html.parser")

    # Remove page elements that are not article content.
    for element in soup.select(
        "sup.reference, .mw-editsection, "
        ".navbox, .metadata, style, script"
    ):
        element.decompose()

    text_content = soup.get_text(" ", strip=True)
    word_count = len(text_content.split())

    title = article.get("title", plant["wiki_title"])
    page_url = (
        "https://en.wikipedia.org/wiki/"
        + quote(title.replace(" ", "_"), safe="()_'")
    )

    return {
        "plant_id": plant["plant_id"],
        "plant_name": plant["plant_name"],
        "wiki_title": title,
        "source_url": page_url,
        "source_type": "Wikipedia",
        "revision_id": article.get("revid"),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "status": "collected" if word_count > 0 else "empty_article",
        "word_count": word_count,
        "text": text_content,
        "attribution": (
            "Article text from Wikipedia contributors. "
            "Review the article's licensing and attribution requirements "
            "before redistributing its content."
        ),
        "review_status": "needs_manual_review",
    }


def main():
    results = []

    with requests.Session() as session:
        session.headers.update(HEADERS)

        for index, plant in enumerate(PLANTS):
            try:
                result = collect_article(session, plant)
            except (requests.RequestException, ValueError) as error:
                result = {
                    **plant,
                    "status": "request_error",
                    "error": str(error),
                    "review_status": "needs_manual_review",
                }

            results.append(result)

            print(
                f"{plant['plant_name']} | "
                f"{result['status']} | "
                f"words: {result.get('word_count', 0)}"
            )

            # Keep requests sequential and avoid hammering the API.
            if index < len(PLANTS) - 1:
                time.sleep(1)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_FILE.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    successful = sum(
        item["status"] == "collected"
        for item in results
    )

    print(f"\nSaved to: {OUTPUT_FILE}")
    print(f"Successfully collected: {successful}/{len(PLANTS)} articles")


if __name__ == "__main__":
    main()
