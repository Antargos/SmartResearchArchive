"""Extract suggestions and explain a deliberately simple keyword classifier."""

from dataclasses import dataclass, field
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
    sources: dict = field(default_factory=dict, compare=False)
    warnings: list = field(default_factory=list, compare=False)


def filename_metadata(path):
    """Recognize explicit author/year/title layouts, including numbered downloads."""
    stem = re.sub(r'^\d{1,3}[_ .-]+', '', path.stem)
    year_pattern = r'(?:18|19|20)\d{2}'
    match = re.fullmatch(rf'(.+?)[_]+({year_pattern})[_]+(.+)', stem)
    if match:
        author, year, title = match.groups()
    else:
        match = re.fullmatch(rf'([^_]+)[_](.+)[_]({year_pattern})', stem)
        if match:
            author, title, year = match.groups()
        else:
            match = re.fullmatch(rf'(.+?)\s+-\s+({year_pattern})\s+-\s+(.+)', stem)
            if not match:
                return {}
            author, year, title = match.groups()
    author = author.replace('_', ' ').strip()
    # A leading surname is a suggestion, never an invented expanded first name.
    if not re.fullmatch(r"[^\W\d_][\w .,'’&-]{1,99}", author, re.UNICODE):
        return {}
    return {'author': author, 'year': year, 'title': title.replace('_', ' ').strip()}


def plausible_metadata(value):
    value = str(value or '').strip()
    placeholders = ('unknown', 'untitled', 'microsoft word', 'acrobat', 'latex', 'admin', 'user')
    return value if value and value.casefold() not in placeholders and len(value) <= 500 else ''


def normalize(text: str) -> str:
    """Ignore case and repeated whitespace; keep word boundaries meaningful."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def classify(text: str, topics=None) -> tuple[str, dict[str, list[str]]]:
    """One point per distinct keyword, independent of repetition or PDF length."""
    topics = TOPICS if topics is None else topics
    text = normalize(text)
    matches = {}
    for topic, keywords in topics.items():
        matches[topic] = [word for word in keywords
                          if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text)]
    highest = max(map(len, matches.values()), default=0)
    winners = [topic for topic, words in matches.items() if len(words) == highest]
    topic = winners[0] if highest > 0 and len(winners) == 1 else UNCLASSIFIED
    return topic, matches


def guess_metadata(embedded: dict, first_page: str, path: Path) -> Metadata:
    """Prefer PDF title/author, then conservative first-page guesses."""
    lines = [line.strip() for line in first_page.splitlines() if line.strip()]
    from_name = filename_metadata(path)
    sources, warnings = {}, []
    title = plausible_metadata(embedded.get('/Title'))
    sources['title'] = 'PDF-Metadaten'
    if not title:
        title = from_name.get('title') or next((line for line in lines[:8] if len(line) >= 8), path.stem)
        sources['title'] = 'Dateiname' if from_name.get('title') or title == path.stem else 'Erste PDF-Seite'
    author = plausible_metadata(embedded.get('/Author'))
    sources['author'] = 'PDF-Metadaten'
    if author and from_name.get('author') and normalize(from_name['author']) not in normalize(author):
        warnings.append('Autor in PDF-Metadaten und Dateiname weicht ab; bitte prüfen.')
    if not author and from_name.get('author'):
        author, sources['author'] = from_name['author'], 'Dateiname'
    if not author:
        # Unlabelled names are too ambiguous to guess reliably.
        match = re.search(r"^(?:author|authors|by|autor|autoren)\s*:?\s+(.+)$",
                          first_page, re.IGNORECASE | re.MULTILINE)
        author = match.group(1).strip() if match else "UnknownAuthor"
        sources['author'] = 'Erste PDF-Seite' if match else 'Nicht erkannt'
    # Creation dates are not publication dates. Use the first printed year only.
    year = re.search(r"\b(?:18|19|20)\d{2}\b", first_page)
    year_value = from_name.get('year') or (year.group() if year else 'UnknownYear')
    sources['year'] = 'Dateiname' if from_name.get('year') else ('Erste PDF-Seite' if year else 'Nicht erkannt')
    if year and from_name.get('year') and year.group() != from_name['year']:
        warnings.append('Jahr auf erster Seite und im Dateinamen weicht ab; Dateiname vorgeschlagen.')
    return Metadata(title, author, year_value, sources, warnings)


def read_pdf(path: Path) -> tuple[Metadata, str]:
    """Read locally and close the file before moving it (important on Windows)."""
    with path.open("rb") as source:
        reader = PdfReader(source)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDF: skipped; decrypt a local copy first.")
        pages = [page.extract_text() or "" for page in reader.pages]
        metadata = guess_metadata(reader.metadata or {}, pages[0] if pages else "", path)
    return metadata, "\n".join(pages)
