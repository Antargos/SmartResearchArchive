# Smart Research Archive 2.0.0 — Windows

Neuer Arbeitsablauf: zuerst lokal oder ChatGPT wählen, danach eigene Themen und
Keywords festlegen oder Vorschläge anfordern. ChatGPT prüft eigene Regeln und bietet
Ergänzungen separat zur Bestätigung an. Lokale Begriffshilfen sind nicht vorausgewählt.

Bestätigte Regeln werden im ausgewählten Archivordner gespeichert. Neue PDFs direkt
in diesem Ordner werden beim nächsten Start nach denselben Regeln vorgeschlagen.
Bestehende Themenordner bleiben erhalten. Eine Neubewertung bereits einsortierter
PDFs erfolgt ausschließlich über die eigene Aktion und nach Bestätigung.

Weitere Neuerungen:
- Metadaten aus Dateinamen, mit Herkunft und Konflikthinweisen.
- Identische PDFs vor der LLM-Analyse erkennen, ohne sie zu löschen.
- Erfolgreiche Text-/LLM-Schritte lokal speichern und nach Abbruch wiederverwenden.
- PDF öffnen, später prüfen, überspringen und erneut prüfen.
- Letzte Einsortierung sicher rückgängig machen.
- Wiederholte manuelle Korrekturen als optionale Regelvorschläge anbieten.
- Analyse-Zwischenspeicher separat löschen; Archivregeln und Verlauf behalten.

**SmartResearchArchive-2.0.0-Setup.exe** herunterladen, vorherige App schließen und
installieren. Python ist nicht erforderlich. Alternativ die portable ZIP vollständig
entpacken und SmartResearchArchive.exe starten; der Ordner _internal muss daneben bleiben.

1. Ordner wählen und lokal oder ChatGPT auswählen.
2. Eigene Themen bearbeiten oder Vorschläge wählen; bei ChatGPT verbinden,
   ein Modell wählen und externe Verarbeitung erlauben.
3. **PDFs analysieren**, Themen prüfen und bestätigen.
4. Jede Datei prüfen und **Bestätigen & einsortieren** wählen.
5. Später denselben Ordner öffnen: **Archivregeln verwenden** ist voreingestellt.

Die lokale Datei .smart-research-archive/archive.sqlite3 enthält Regeln,
extrahierten Text, Zusammenfassungen, Prüffortschritt und Verschiebungsverlauf.
Zugangsdaten werden separat im Windows-Benutzerprofil geschützt gespeichert.
Keine PDFs oder Zugangsdaten werden nach GitHub hochgeladen.

Automatisierte Prüfungen verwenden synthetische PDFs und simulierte Modellantworten.
Live-Anmeldung und wissenschaftliche Qualität müssen mit dem eigenen Konto und
eigenen Dokumenten geprüft werden. Keine OCR. Duplikate bedeuten identischen
Dateiinhalt; verschiedene Scans desselben Aufsatzes werden nicht gleichgesetzt.
Bitte Sicherungskopien behalten. Der Installer ist nicht digital signiert.

All rights reserved. Hinweise zu Drittkomponenten sind im Paket enthalten.
Details: README und docs/windows-user-guide.md.
