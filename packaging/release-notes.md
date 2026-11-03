# Smart Research Archive 1.0.1 — Windows desktop candidate

Fix for hidden analysis buttons on smaller displays and larger Windows text scaling:
the form now scrolls, while the main action buttons remain in fixed bars. Layout
checks cover 720×480, 800×500 and 1100×780 windows at 100%, 150% and 200% scaling.
Close the previous app and run this installer to update your existing installation.

Download **SmartResearchArchive-1.0.1-Setup.exe** and follow the installer.
Alternatively extract the portable ZIP and run SmartResearchArchive.exe, keeping
the _internal folder beside it. Python does not need to be installed.

1. Select a folder containing PDFs, such as Downloads.
2. Choose fixed local topics, local topic suggestions, or ChatGPT content analysis.
3. For ChatGPT, connect in the browser, authorize plan use and select a model.
4. Review the topics, then each PDF's metadata and proposed destination.
5. Confirm each file to move it into a topic subfolder of the selected folder.

Keep backups. Skipped files and subfolders remain untouched. Credentials are
stored separately and protected on Windows. No PDF collection is uploaded to GitHub.

The download is a release candidate, not a claim of verified scholarly accuracy.
Automated tests and EXE startup checks run before publication. Live ChatGPT plan
eligibility and model quality still require your own browser sign-in and evaluation.
The installer is not code-signed; Windows may display an unknown-publisher notice.

All rights reserved. Third-party component notices are included in the package.
See README and docs/windows-user-guide.md in the repository for details.
