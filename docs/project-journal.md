# Project journal

## 13 October 2026 — Start of version 1

### Goal
Build a beginner-friendly local PDF organizer for the course Applied Programming Projects.

### Starting point
The repository contained a short README only. The available conversation describes
the workflow but does not specify the five topic names. Initial editable categories:
Digital History, Archival Studies, Social History, Political History, Cultural History.

### Decisions
- Use pypdf for text and embedded metadata; no OCR, ML, embeddings, or external API.
- Prefer readable functions and standard-library unittest over a framework.
- Count each distinct matching keyword once; tied or zero scores mean Unclassified.
- Require human acceptance after every preview, including after corrections.
- Avoid overwriting files; add numeric suffixes for duplicate names.
- Ignore all PDFs and local input/archive folders in Git.
- No CSV, reference-manager integration, open-source license, or LICENSE file.

### AI assistance
Codex drafted the implementation, documentation and tests based on the user's scope.
Automated checks are recorded below; personal review and evaluation with 20–50
lawfully obtained research PDFs remain tasks for the project owner. This entry does
not claim that the owner has already reviewed or understood the generated code.

### Limitations and next evaluation
Metadata is a suggestion, not verified bibliographic data. Scans without a text layer
cannot be read. Keywords may occur in references or unrelated contexts. Evaluate
metadata accuracy, classification and usability with a local collection; record
mistakes and corrections here without uploading the papers.

### Automated validation
Six unittest cases passed with Python 3.12.14 and pypdf 6.10.0: synthetic PDF text
and metadata extraction, corrupt/encrypted input, keyword boundaries and ties,
collision protection, failed-copy cleanup, and Change/Skip/Accept behavior.
Test fixtures are generated temporarily, not committed. Initial sandbox execution
could not write to the system temporary folder; the authorized run outside the
sandbox passed. Real-paper accuracy and personal code review remain unverified.
