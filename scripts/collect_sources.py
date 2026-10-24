
import json
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "knowledge_base" / "sources.json"
OUTPUT_FILE = ROOT / "knowledge_base" / "raw_documents.json"

USER_AGENT = "PlantCareResearchBot/1.0 (educational research)"
ALLOWED_DOMAINS = {
    "extension.umd.edu",
    "ipm.ucanr.edu",
    "www.rhs.org.uk",
    "hgic.clemson.edu",
    "plants.ces.ncsu.edu",
    "extension.sdstate.edu",
    "extension.psu.edu",
}
# Extract only paragraphs relevant to our research.
KEYWORDS = (
    "yellow", "wilting", "wilt", "drooping", "brown",
    "spot", "pest", "root rot", "overwater", "underwater",
    "drainage", "light", "humidity", "growth", "leaf",
    "leaves", "houseplant", "plant"
)

MAX_PARAGRAPHS = 50
MAX_PARAGRAPH_LENGTH = 350
DELAY_SECONDS = 2

session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "text/html",
})


def robots_allows(url):
    """Proceed only when robots.txt can be retrieved and permits access."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        response = session.get(robots_url, timeout=15)

        if response.status_code != 200:
            print(f"SKIP: Cannot verify robots.txt ({response.status_code})")
            return False

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())

        return parser.can_fetch(USER_AGENT, url)

    except requests.RequestException as error:
        print(f"SKIP: Could not check robots.txt: {error}")
        return False


def extract_document(source):
    url = source["url"]
    domain = urlparse(url).hostname

    if domain not in ALLOWED_DOMAINS:
        return {
            "source_id": source["source_id"],
            "url": url,
            "status": "skipped_domain_not_allowed",
        }

    if not robots_allows(url):
        return {
            "source_id": source["source_id"],
            "url": url,
            "status": "skipped_robots_permission",
        }

    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type.lower():
            return {
                "source_id": source["source_id"],
                "url": url,
                "status": "skipped_not_html",
            }

        # Avoid unexpectedly large downloads.
        if len(response.content) > 3_000_000:
            return {
                "source_id": source["source_id"],
                "url": url,
                "status": "skipped_page_too_large",
            }

        soup = BeautifulSoup(response.text, "html.parser")

        for element in soup.select(
            "script, style, nav, footer, header, aside, "
            "form, noscript, iframe"
        ):
            element.decompose()

        title_tag = soup.find("title")
        title = title_tag.get_text(" ", strip=True) if title_tag else ""

        main = soup.find("main") or soup.find("article") or soup.body or soup
        headings = [
            heading.get_text(" ", strip=True)
            for heading in main.select("h1, h2, h3")
            if heading.get_text(" ", strip=True)
        ]

        excerpts = []
        seen = set()

        for paragraph in main.find_all(["p", "li"]):
            text = " ".join(paragraph.get_text(" ", strip=True).split())

            if len(text) < 45:
                continue

            if not any(word in text.lower() for word in KEYWORDS):
                continue

            if text in seen:
                continue

            seen.add(text)
            excerpts.append(text[:MAX_PARAGRAPH_LENGTH])

            if len(excerpts) >= MAX_PARAGRAPHS:
                break

        return {
            "source_id": source["source_id"],
            "source_title": source.get("title", title),
            "page_title": title,
            "organization": source.get("organization", ""),
            "url": url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "status": "collected" if excerpts else "no_relevant_excerpts",
            "headings": headings[:30],
            "excerpts": excerpts,
            "review_status": "needs_manual_review",
        }

    except requests.RequestException as error:
        return {
            "source_id": source["source_id"],
            "url": url,
            "status": "request_failed",
            "error": str(error),
        }


def main():
    if not SOURCES_FILE.exists():
        raise FileNotFoundError(
            f"Source register not found: {SOURCES_FILE}"
        )

    sources = json.loads(SOURCES_FILE.read_text(encoding="utf-8-sig"))

    if not isinstance(sources, list):
        raise ValueError("sources.json must contain a JSON list")

    documents = []

    for index, source in enumerate(sources):
        print(f"\n[{index + 1}/{len(sources)}] {source['url']}")
        document = extract_document(source)
        documents.append(document)

        print("Status:", document["status"])
        print("Relevant excerpts:", len(document.get("excerpts", [])))

        if index < len(sources) - 1:
            time.sleep(DELAY_SECONDS)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(documents, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    collected = sum(d["status"] == "collected" for d in documents)

    print(f"\nFinished. Successful pages: {collected}/{len(documents)}")
    print(f"Saved results to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
