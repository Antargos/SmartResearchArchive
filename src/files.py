"""Safe filenames and file organization, without overwriting existing papers."""

from pathlib import Path
import re
import shutil
import stat
import hashlib

from .analysis import Metadata, TOPICS, UNCLASSIFIED


def is_link(path: Path) -> bool:
    """Also exclude Windows junctions/reparse points, not only symbolic links."""
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0)
                                         & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
    except FileNotFoundError:
        return False


def scan_pdfs(folder: Path) -> list[Path]:
    """Only scan the input folder itself, not subfolders or symbolic links."""
    return sorted((path for path in folder.iterdir()
                   if path.is_file() and not is_link(path)
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
    if is_link(folder):
        raise ValueError("Topic folder must not be a symbolic link")
    candidate = folder / filename(metadata)
    number = 2
    while candidate.exists():
        candidate = folder / f"{Path(filename(metadata)).stem}_{number}.pdf"
        number += 1
    return candidate


def content_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def move_pdf(source: Path, target: Path, expected_hash=None) -> None:
    """Exclusive creation also protects against collisions after the preview."""
    target.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with source.open("rb") as original, target.open("xb") as archived:
            created = True
            shutil.copyfileobj(original, archived)
        if expected_hash is not None and (is_link(source) or content_hash(source) != expected_hash
                                          or content_hash(target) != expected_hash):
            raise ValueError('Source changed while copying; input was kept and incomplete archive removed.')
    except Exception:
        if created:
            target.unlink()  # Remove only the incomplete copy we created.
        raise
    # Delete the input only after the full copy has succeeded.
    source.unlink()
