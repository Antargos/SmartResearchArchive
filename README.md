# Smart Research Archive

A beginner-friendly local Python tool for organizing academic PDFs for historical
research. Academic prototype / work in progress for **Applied Programming Projects**.

## Project goal
Unsorted research PDFs and inconsistent filenames make literature hard to find.
This tool suggests metadata, a topic and a consistent name. You review every file
before it is renamed and moved. PDF contents are unchanged; no PDFs are uploaded.

## Getting started
Install Python **3.10 or newer**, download/clone the repository, then open a terminal
in its folder. On Windows, `py` can replace `python` if needed:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
mkdir input
# Copy your local PDFs into input, then run:
.venv\Scripts\python -m src.main
```

On macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
mkdir -p input
.venv/bin/python -m src.main
```

Keep backup copies: accepting a suggestion **moves** the original out of input.
Only files directly in input are scanned, including `.PDF`; subfolders and symbolic
links are ignored. Custom folders can be supplied with your environment's Python:

```sh
python -m src.main --input "path/to/papers" --output "path/to/archive"
```

Input and output must be separate folders, neither nested in the other.

## Workflow
Input → text extraction → metadata suggestions → keyword scores → preview
→ Accept / Change / Skip → rename and organize.

- **Accept (A):** move into `archive/<Topic>/Author_Year_Title.pdf`.
- **Change (C):** edit title, author, year and/or select a topic by number.
  Enter keeps the current value. Review the updated preview and accept separately.
- **Skip (S):** leave the original untouched.
- **Ctrl+C:** stop. Previously accepted files remain archived.

Example: `Ada Example`, `2024`, `Digital History Methods` becomes
`Ada_Example_2024_Digital_History_Methods.pdf`. Portable filenames use ASCII
letters, digits, underscores and hyphens, with length limits. Accented/non-Latin
characters are replaced. Duplicate names get `_2`, `_3`, etc. Existing files are
never overwritten. If an operation fails, inspect input and archive: failure to
delete an input after copying can leave two copies, without losing the original.

## Transparent classification
### Experimental branch: topics from your collection

On `feature/pdf-topic-suggestions`, you can generate vocabulary-based topic
suggestions from the PDFs in your **local input folder**. This is not a web upload
interface. No documents are sent to GitHub or an AI service.

Using your virtual environment's Python:

```sh
# Preview and review topics only; never move files:
python -m src.main --topics-only
# Review topics, then review and organize each PDF:
python -m src.main --suggest-topics
```

Both options support `--input` and `--output`. Without either option, the original
five predefined categories are used. In suggestion mode, those categories are
replaced for the current run by up to five topics you explicitly accept.

How it works:

1. Read the available PDFs and extract text locally. Unreadable/encrypted files
   are reported and excluded; empty scans supply no topic evidence.
2. Find words of at least four letters and adjacent word pairs, excluding a small
   editable English/German stop list. Phrases do not bridge stopwords, numbers or
   punctuation. No stemming or synonym detection is performed.
3. Count **how many PDFs contain each term**, not how often it is repeated.
   Terms must appear in at least two readable PDFs. With only one readable PDF,
   single-document suggestions are allowed and explicitly show one PDF as evidence.
4. Rank by document count, then prefer pairs, then alphabetical order. Show up to
   ten candidates and their evidence filenames. Redundant individual words with
   the same evidence as an already selected phrase are suppressed.
5. Accept, change or skip each proposal. Change lets you set a topic name and
   comma-separated matching keywords; accept the updated preview separately.
   Names must use ASCII letters/numbers/spaces/underscores/hyphens (max 60 characters),
   and cannot be duplicate, reserved device names or Unclassified.
6. Classify each PDF with the accepted keywords and the original transparent scoring
   rules. A separate Accept/Change/Skip review is still required for every file move.

If nothing is accepted or no recurring terms are found, suggestions do not silently
fall back to predefined topics: files receive Unclassified and can still be skipped.
Topic choices apply only to the current session and are not saved. `--topics-only`
ends after reviewing the topics and leaves all PDFs unchanged.

These are **vocabulary suggestions, not semantic topic discovery**. Frequent names,
generic words and bibliography terms may rank highly. Stop words and keywords can
be adjusted in `src/suggestions.py`. Review terms critically and rename them into
meaningful research categories. The experiment keeps extracted collection text in
memory until the run finishes; start with a small collection. No new dependency,
ML, embeddings, CSV or API is introduced.

### Original predefined categories
Initial categories and editable English/German keywords are in `src/analysis.py`:

| Topic | Keywords |
| --- | --- |
| Digital History | digital history, digital humanities, text mining, digitale geschichte |
| Archival Studies | archive, archives, archival, preservation, archiv, archivierung |
| Social History | social history, labor, labour, migration, sozialgeschichte |
| Political History | political history, diplomacy, parliament, democracy, politikgeschichte |
| Cultural History | cultural history, memory, ritual, identity, kulturgeschichte |

Each distinct matching keyword gives one point. Matching ignores case and repeated
whitespace and uses word boundaries; repetition adds no points. The unique highest
score wins. Zero matches or a tie yield **Unclassified**. All scores and matching
terms appear in the preview, even if you override the topic. Scores are rules,
not confidence probabilities. Categories are a starting point, not a scholarly taxonomy.

## Metadata and scope
Embedded title and author take priority. Otherwise the tool suggests a first-page
title line (or filename) and looks for a labelled `By:`/`Author:` line. Unlabelled
names are not guessed. Year is the first printed year from 1800–2099 on the first
page; PDF creation dates are not publication dates. Missing values use
`UnknownAuthor` and `UnknownYear`. Always check suggestions against the paper.

Text is extracted from all pages; references and unrelated mentions can distort
classification. Large PDFs can be slow or consume substantial memory. Start with
ordinary journal papers. Image-only scans need OCR, which is outside version 1;
empty text yields Unclassified and permits manual metadata entry. Encrypted or
unreadable files are reported for manual handling and do not stop the collection.

No ML, embeddings, CSV, GUI, cloud service, multi-tags or reference-manager
integration is implemented. A local evaluation with 20–50 lawfully obtained PDFs
is planned. Future possibilities include CSV, Streamlit, better metadata and
optional Citavi or other reference-manager adapters.

## Digital archiving and History
The project applies descriptive metadata, consistent naming, thematic organization
and retrieval to historical research literature. Transparent rules and human review
make decisions inspectable. It is not a complete long-term preservation system,
does not implement OAIS or PREMIS and does not replace scholarly source criticism.
It does not maintain an archival provenance database.

## Learning and AI-assisted coding
The project starts from beginner experience, mainly AI-assisted “vibe coding”.
Small, commented functions support learning to understand and explain the code,
rather than only generating it. Codex drafted version 1 and its tests; automated
checks do not replace personal review. Decisions and AI assistance are recorded
in `docs/project-journal.md`; review with real research papers remains to be done.

## Structure and tests
| File | Responsibility |
| --- | --- |
| `src/analysis.py` | Text extraction, metadata guesses, keywords and scoring |
| `src/files.py` | Scanning, filenames, collision protection and moving |
| `src/main.py` | Command-line options and interactive review |
| `src/suggestions.py` | Collection vocabulary, evidence and human topic approval |
| `tests/test_archive.py` | Temporary synthetic PDFs and behavior checks |

Run with the virtual environment's Python:

```sh
python -m unittest discover -s tests -v
```

Tests cover extraction, metadata fallbacks, scoring, ties, duplicate names, failed
copies, encrypted/corrupt PDFs and Accept/Change/Skip. Test PDFs are generated in
temporary folders. No research PDFs are included. `.gitignore` excludes PDFs,
input/archive folders and virtual environments. Do not force-add copyrighted papers.

Dependency: [pypdf documentation](https://pypdf.readthedocs.io/en/stable/).
`requirements.txt` pins the tested version. Third-party dependencies retain their
own licenses; the following notice concerns this project's code.

## Rights
Copyright © 2026 Antargos

All rights reserved.

This repository contains an academic prototype developed as part of
the course "Applied Programming Projects".

The source code is publicly available for demonstration and academic
evaluation purposes only. No permission is granted to reproduce,
redistribute, modify, or use the software in derivative or commercial
products without prior written permission.

This is a rights notice, not an open-source license. No LICENSE file is included.
