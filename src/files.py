"""Safe filenames and file organization, without overwriting existing papers."""

from pathlib import Path
import re
import shutil

from .analysis import Metadata, TOPICS, UNCLASSIFIED


def scan_pdfs(folder: Path) -> list[Path]:
    """Only scan the input folder itself, not subfolders or symbolic links."""
    return sorted((path for path in folder.iterdir()
                   if path.is_file() and not path.is_symlink()
                   and path.suffix.lower() == ".pdf"), key=lambda p: p.name.casefold())


def safe_part(value: str, fallback: str, limit: int) -> str:
    # ASCII keeps filenames portable; replace spaces and forbidden characters.
    value = re.sub(r"[^a-zA-Z0-9-]+", "_", value).strip("_")[:limit].rstrip("_")
    return value or fallback


def filename(metadata: Metadata) -> str:
    return "_".join((safe_part(metadata.author, "UnknownAuthor", 40),
                     safe_part(metadata.year, "UnknownYear", 12),
                     safe_part(metadata.title, "Untitled", 80))) + ".pdf"


def valid_topic_name(name: str) -> bool:
    """Keep user-defined folder names portable and inside the archive."""
    reserved = {'CON', 'PRN', 'AUX', 'NUL',
                *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    return bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,59}', name)
                and name == name.strip() and name.upper() not in reserved)


def destination(root: Path, topic: str, metadata: Metadata, topics=None) -> Path:
    topics = TOPICS if topics is None else topics
    if topic not in (*topics, UNCLASSIFIED) or not valid_topic_name(topic):
        raise ValueError("Unknown topic")
    folder = root / topic
    if folder.is_symlink():
        raise ValueError("Topic folder must not be a symbolic link")
    candidate = folder / filename(metadata)
    number = 2
    while candidate.exists():
        candidate = folder / f"{Path(filename(metadata)).stem}_{number}.pdf"
        number += 1
    return candidate


def move_pdf(source: Path, target: Path) -> None:
    """Exclusive creation also protects against collisions after the preview."""
    target.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with source.open("rb") as original, target.open("xb") as archived:
            created = True
            shutil.copyfileobj(original, archived)
    except Exception:
        if created:
            target.unlink()  # Remove only the incomplete copy we created.
        raise
    # Delete the input only after the full copy has succeeded.
    source.unlink()
