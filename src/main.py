"""Run from the repository root: python -m src.main."""

import argparse
from pathlib import Path
import re

from .analysis import TOPICS, UNCLASSIFIED, classify, read_pdf
from .files import destination, move_pdf, scan_pdfs
from .suggestions import approve_topics, suggest_topics


def review(source, metadata, topic, matches, output_folder, ask=input, show=print,
           topic_keywords=None):
    """Corrections return to the preview; only Accept performs a move."""
    topic_keywords = TOPICS if topic_keywords is None else topic_keywords
    topics = [*topic_keywords, UNCLASSIFIED]
    while True:
        target = destination(output_folder, topic, metadata, topic_keywords)
        show(f"\nFile: {source.name}\nTitle: {metadata.title}\nAuthor: {metadata.author}"
             f"\nYear: {metadata.year}\nTopic: {topic}\nDestination: {target}")
        for name, words in matches.items():
            show(f"  {name}: {len(words)} point(s) — {', '.join(words) or 'no matches'}")
        choice = ask("[A]ccept / [C]hange / [S]kip: ").strip().lower()
        if choice in ("s", "skip"):
            show("Skipped; input file unchanged.")
            return False
        if choice in ("a", "accept"):
            move_pdf(source, target)
            show(f"Archived: {target}")
            return True
        if choice in ("c", "change"):
            for field in ("title", "author", "year"):
                value = ask(f"New {field} (Enter keeps current value): ").strip()
                if value:
                    if field == "year" and not re.fullmatch(r"\d{4}|UnknownYear", value):
                        show("Year must be four digits or UnknownYear; kept current value.")
                    else:
                        setattr(metadata, field, value)
            for number, name in enumerate(topics, 1):
                show(f"{number}. {name}")
            value = ask("Topic number (Enter keeps current topic): ").strip()
            if value:
                if value.isdigit() and 1 <= int(value) <= len(topics):
                    topic = topics[int(value) - 1]
                else:
                    show("Invalid topic; kept current topic.")
        else:
            show("Please choose Accept, Change or Skip.")


def main():
    parser = argparse.ArgumentParser(description="Review and organize local academic PDFs.")
    parser.add_argument("--input", type=Path, default=Path("input"))
    parser.add_argument("--output", type=Path, default=Path("archive"))
    parser.add_argument("--suggest-topics", action="store_true",
                        help="Propose and review topics from the input collection before sorting.")
    parser.add_argument("--topics-only", action="store_true",
                        help="Review topic suggestions only; never rename or move PDFs.")
    args = parser.parse_args()
    input_folder, output_folder = args.input.resolve(), args.output.resolve()
    if input_folder == output_folder or input_folder in output_folder.parents or output_folder in input_folder.parents:
        parser.error("Input and output folders must be separate, not nested.")
    if not input_folder.is_dir():
        parser.error(f"Input folder does not exist: {input_folder}. Create it and add PDFs first.")
    if output_folder.exists() and not output_folder.is_dir():
        parser.error("Output path must be a folder.")
    papers = scan_pdfs(input_folder)
    if not papers:
        print("No PDFs found in the input folder.")
    try:
        topic_keywords = TOPICS
        loaded = {}
        if args.suggest_topics or args.topics_only:
            print('Analyzing local PDFs for vocabulary-based topic suggestions...')
            for source in papers:
                try:
                    loaded[source] = read_pdf(source)
                except Exception as error:
                    print(f'Could not read {source.name}: {error}; excluded from suggestions.')
            documents = [(source.name, text) for source, (_, text) in loaded.items()]
            candidates = suggest_topics(documents)
            if not candidates:
                print('No recurring topic terms found. Try more text-based PDFs or edit the stop list.')
            topic_keywords = approve_topics(candidates)
            if args.topics_only:
                print('Topic review finished; no PDF files changed. Topics apply only to this run.')
                return
            papers = list(loaded)
        for source in papers:
            try:
                metadata, text = loaded[source] if source in loaded else read_pdf(source)
                topic, matches = classify(text, topic_keywords)
                if not text.strip():
                    print(f"\n{source.name}: no extractable text; OCR is outside this version.")
                review(source, metadata, topic, matches, output_folder,
                       topic_keywords=topic_keywords)
            except EOFError:
                raise
            except Exception as error:
                # A bad PDF must not prevent reviewing the rest of the collection.
                print(f"Could not finish {source.name}: {error}. Check input and archive folders.")
    except (EOFError, KeyboardInterrupt):
        print("\nStopped. Unaccepted files remain in the input folder.")


if __name__ == "__main__":
    main()
