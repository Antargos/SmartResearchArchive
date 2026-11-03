# Smart Research Archive

## Windows desktop version 2.0.0

Branch **`feature/archive-workflow-v2`** adds a persistent, reviewed archive workflow
to the German desktop app. Download the Windows installer or portable ZIP from
[Releases](https://github.com/Antargos/SmartResearchArchive/releases).
The build publishes downloads after regression tests, real Windows GUI checks,
packaged startup, installation and uninstallation checks succeed.

1. Install **SmartResearchArchive-2.0.0-Setup.exe** and open the app from the Start menu.
2. Choose **Lokal** or **ChatGPT (LLM)**, then your own topics/keywords or suggestions.
3. Select your PDF folder. For ChatGPT, connect in the browser, choose a model and
   allow external processing.
4. **PDFs analysieren**, review the topics, then **Regeln bestätigen & weiter**.
5. Review each PDF and choose **Bestätigen & einsortieren**. It moves only that file
   into a topic subfolder of the selected folder.

The archive remembers approved topics, descriptions and keywords. Later, place
new downloads directly in the same main folder and analyze with **Archivregeln
verwenden**. Existing topic folders are reused. They are only analyzed again
through **Bestehende Sammlung ausdrücklich neu prüfen**, followed by file review.
Old folder names are retained when rules change; a rule edit does not rename folders.

ChatGPT checks user-defined topics without replacing them. Optional additions
require selection and confirmation. Local proposals are unselected vocabulary
helpers, not reliable semantic categories. At most five topics can be approved;
unmatched or ambiguous files use Unclassified. Keywords are required locally;
ChatGPT uses descriptions and keywords as content guidance. No embeddings.

Metadata also recognizes layouts such as `02_Jones_Origins_2006.pdf`. Provenance
and conflicts are shown for review. **PDF öffnen**, **Später prüfen**,
**Überspringen**, **Erneut prüfen** and safe **Rückgängig** support manual decisions.
Exact duplicate PDFs are identified before LLM analysis and left untouched.
Successful extraction, model sections, summaries and assignments are cached for
restart. Repeated corrections can produce optional keyword drafts; rules never
change automatically.

State is stored in **`.smart-research-archive/archive.sqlite3` inside the selected
folder**: approved rules, extracted text, summaries, decisions, hashes and move
history. It contains document content and is not encrypted. Include it when backing
up or relocating an archive. **Analysecache leeren** deletes cached analysis while
retaining rules, decisions, files and move history. Saved ChatGPT credentials live
separately in the protected per-user store described below; they are not in the archive.

Windows 10/11 x64; Python is included in the package. For the portable ZIP, extract
all files and keep `_internal` beside the EXE. Close the old app before updating.
The installer is unsigned. Keep backups: file confirmation changes the original
collection. Existing files are not overwritten, and changed sources require reanalysis.
Duplicate detection means identical bytes, not matching scholarly works.
OCR, CSV output and scholarly accuracy guarantees are outside scope.

Saved ChatGPT connections can still be removed with **Verbindung löschen**.
Live eligibility and model quality need evaluation with your own account.
No research PDFs or credentials are committed to GitHub.

**[Windows user guide (German)](docs/windows-user-guide.md)**

### Run or build from source

```sh
python -m pip install -r requirements.txt
python desktop_app.py
# Windows builds additionally need Inno Setup 6.3+:
python -m pip install -r requirements-build.txt
python tools/build_windows.py
```

The GUI stays responsive during analysis. Cancel stops at the next safe step after
a current network request or copy finishes. The build workflow is in
`.github/workflows/windows-desktop.yml`; generated binaries are release assets.

The following sections describe the older, optional command-line interfaces.
Persistent archive profiles and the revised workflow above apply to the desktop
app; the CLI retains its own per-session topics and separate input/output folders.

A beginner-friendly Python tool for organizing academic PDFs for historical
research. Academic prototype for **Applied Programming Projects**, developed with
AI assistance. All rights reserved; see the notice below.

## Experimental ChatGPT integration

Branch `feature/chatgpt-semantic-topics` adds optional content analysis using your
ChatGPT plan through **Sign in with ChatGPT**. It builds on the vocabulary-suggestion
branch. The default keyword modes remain local; ChatGPT mode sends extracted text
and summaries to OpenAI and consumes your existing plan allowance. No embeddings.

### Connect and run

Reinstall requirements in your Python 3.10+ virtual environment. This branch adds
`cryptography` for identity-token signature verification. With the environment's
Python (on Windows `.venv\Scripts\python`):

```sh
python -m pip install -r requirements.txt
python -m src.main --chatgpt-login
# Preview semantic topics, without moving files:
python -m src.main --chatgpt --topics-only
# Suggest topics, classify documents, then review each proposed move:
python -m src.main --chatgpt
# Optional: use a model slug shown in your account's model catalog:
python -m src.main --chatgpt --model YOUR_AVAILABLE_MODEL_SLUG
# Revoke and clear a selected renewable session:
python -m src.main --chatgpt-logout
```

Continue with ChatGPT opens your browser. Sign in, select the account/workspace,
and authorize **ChatGPT plan usage**. A login alone is insufficient. Eligibility
and available models are decided by OpenAI; Plus does not guarantee every account,
workspace or model is supported. Intended for a personal project run locally;
the repository's rights notice remains unchanged. No API key or copied browser/
Codex credential is needed, and no separately billed API-key fallback exists.

`--input` and `--output` work as before. Before sending document text, the program
asks for `y`; any other answer cancels. Choose a saved connection or add another,
then choose from the account-specific models. Manage usage and disconnect access
in ChatGPT's usage and connected-app settings. This app has no separate allowance.

### Semantic workflow

1. Extract text locally and analyze **all sections**, each up to 12,000 characters.
   Limit: 20 sections / 240,000 characters per PDF and 50 input PDFs per run.
   Over-limit text is rejected, not silently truncated. OCR remains outside scope.
2. Generate a concise document summary and short exact quotations. Quotes are
   checked against extracted text with PDF-layout normalization. Unverified quotes
   are discarded; if any section has no valid quote, that document's automatic
   analysis is rejected and it is retained as Unclassified for manual review.
   Other documents continue. Displayed evidence always uses actual source text.
   Multiple section summaries are synthesized. Up to three quotes are displayed
   per document; they verify wording, not the correctness of interpretation.
3. Suggest up to five common themes with descriptions and related PDF IDs.
   Larger collections use batches of eight summaries and a consolidation step.
4. Accept, change or skip topics. Edits return to a preview. Descriptions define
   the topics by content; no keyword matching is used for semantic classification.
5. Classify against the approved topics using the document summary and excerpts.
   Show a reason, then require the usual Accept/Change/Skip before any move.
   You can correct the topic. The displayed reason refers to the original suggestion.

No accepted topics or no readable text means Unclassified. Invalid JSON, unsafe
folder names, unknown document IDs/topics and failed/incomplete model streams are
rejected. Individual invalid document answers/assignments are isolated and marked
Unclassified with a review reason. Account/network/usage and incomplete-stream
errors still stop the run; accepted files stay archived and unaccepted
files stay in input. There are no automatic paid retries. Summaries and topic
choices apply only to the current run and are not written to an index.

### Credential storage and validation status

Saved connections live under **`%LOCALAPPDATA%\SmartResearchArchive\chatgpt`** on
Windows (or `~/.local/share/SmartResearchArchive/chatgpt` on other systems).
Credentials are independent of installation/input folders. On Windows they use encryption through the current user's
DPAPI. On macOS/Linux, files use owner-only permissions (600, directory 700),
not encryption. Never share or commit these files. This OS-user store retains
the installation's stable host ID and separate account registrations.
Only one ChatGPT run can use a store at a time. After a crash, first confirm no run
is active before removing the empty `runtime.lock` directory inside the credential store.

The implementation verifies PKCE/state and the identity token's signature,
issuer, audience, expiry and nonce, plus explicit plan permission. It refreshes
tokens near expiry under the run's lock. Sign-out attempts remote revocation and
clears local tokens; if revocation is unconfirmed, disconnect in ChatGPT settings.
Model requests use the public Responses API with streamed, unstored requests,
not ChatGPT's private browser endpoints. Model outputs cannot execute tools or
choose arbitrary filesystem paths.

The command-line integration tests pass on the Windows build runner, including simulated OAuth, signed-token checks,
Windows protected storage, incomplete responses, semantic output validation and
the entire file-review workflow. **Live sign-in, actual account eligibility and
scholarly classification quality have not yet been verified.** Start with your own
sign-in and a topic-only run on a few lawfully obtained PDFs. Summarization can
lose nuance; quotations do not make generated conclusions automatically correct.

Official documentation checked on 13 October 2026:

- [Registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Accounts and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
- [Personal local projects](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt)

## Project goal
Unsorted research PDFs and inconsistent filenames make literature hard to find.
This tool suggests metadata, a topic and a consistent name. You review every file
before it is renamed and moved. PDF contents are unchanged. Default keyword modes
do not transmit text; the optional ChatGPT mode is described above.

## Command-line development (optional)
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

## Command-line review workflow
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
   Names use safe letters/numbers/spaces/underscores/hyphens (max 60 characters),
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

The original local modes use no ML or embeddings. This branch additionally offers
the optional external ChatGPT mode described above. CSV, GUI, multi-tags and
reference-manager integration are not implemented. A local evaluation with 20–50 lawfully obtained PDFs
is planned. Future possibilities include CSV, Streamlit, better metadata and
optional Citavi or other reference-manager adapters.

## Digital archiving and History
The project applies descriptive metadata, consistent naming, thematic organization
and retrieval to historical research literature. Transparent rules and human review
make decisions inspectable. It is not a complete long-term preservation system,
does not implement OAIS or PREMIS and does not replace scholarly source criticism.
The desktop move history and metadata-source hints are a practical local audit trail,
not a formal archival provenance or preservation database.

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
| `src/chatgpt_auth.py` | Browser sign-in, verified identity and protected local sessions |
| `src/chatgpt_client.py` | Available models and completed Responses API streams |
| `src/semantic.py` | Section summaries, semantic topics and validated model results |
| `src/chatgpt_workflow.py` | External-processing consent and human file review |
| `src/archive_store.py` | Per-folder rules, checkpoints, hashes and move history |
| `src/archive_workflow.py` | Resume, duplicate checks, rule review and undo |
| `src/desktop.py` | German desktop interface and background jobs |
| `tests/` | Synthetic PDF, workflow, authentication and Windows GUI checks |

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
