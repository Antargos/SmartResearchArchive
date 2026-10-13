"""Extract suggestions and explain a deliberately simple keyword classifier."""

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from pypdf import PdfReader

# Edit these English/German keywords to fit your research collection.
TOPICS = {
    "Digital History": ("digital history", "digital humanities", "text mining", "digitale geschichte"),
    "Archival Studies": ("archive", "archives", "archival", "preservation", "archiv", "archivierung"),
    "Social History": ("social history", "labor", "labour", "migration", "sozialgeschichte"),
    "Political History": ("political history", "diplomacy", "parliament", "democracy", "politikgeschichte"),
    "Cultural History": ("cultural history", "memory", "ritual", "identity", "kulturgeschichte"),
}
UNCLASSIFIED = "Unclassified"


@dataclass
class Metadata:
    title: str
    author: str
    year: str


def normalize(text: str) -> str:
    """Ignore case and repeated whitespace; keep word boundaries meaningful."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def classify(text: str) -> tuple[str, dict[str, list[str]]]:
    """One point per distinct keyword, independent of repetition or PDF length."""
    text = normalize(text)
    matches = {}
    for topic, keywords in TOPICS.items():
        matches[topic] = [word for word in keywords
                          if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text)]
    highest = max(map(len, matches.values()))
    winners = [topic for topic, words in matches.items() if len(words) == highest]
    topic = winners[0] if highest > 0 and len(winners) == 1 else UNCLASSIFIED
    return topic, matches


def guess_metadata(embedded: dict, first_page: str, path: Path) -> Metadata:
    """Prefer PDF title/author, then conservative first-page guesses."""
    lines = [line.strip() for line in first_page.splitlines() if line.strip()]
    title = str(embedded.get("/Title") or "").strip()
    if not title:
        title = next((line for line in lines[:8] if len(line) >= 8), path.stem)
    author = str(embedded.get("/Author") or "").strip()
    if not author:
        # Unlabelled names are too ambiguous to guess reliably.
        match = re.search(r"^(?:author|authors|by|autor|autoren)\s*:?\s+(.+)$",
                          first_page, re.IGNORECASE | re.MULTILINE)
        author = match.group(1).strip() if match else "UnknownAuthor"
    # Creation dates are not publication dates. Use the first printed year only.
    year = re.search(r"\b(?:18|19|20)\d{2}\b", first_page)
    return Metadata(title, author, year.group() if year else "UnknownYear")


def read_pdf(path: Path) -> tuple[Metadata, str]:
    """Read locally and close the file before moving it (important on Windows)."""
    with path.open("rb") as source:
        reader = PdfReader(source)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDF: skipped; decrypt a local copy first.")
        pages = [page.extract_text() or "" for page in reader.pages]
        metadata = guess_metadata(reader.metadata or {}, pages[0] if pages else "", path)
    return metadata, "\n".join(pages)
