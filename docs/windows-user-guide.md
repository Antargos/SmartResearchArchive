# Smart Research Archive — Windows-Anleitung

## Installieren

Lade auf der [GitHub-Release-Seite](https://github.com/Antargos/SmartResearchArchive/releases)
die Datei **SmartResearchArchive-1.0.0-Setup.exe** aus dem neuesten Desktop-Build herunter.
Starte sie und folge dem Assistenten. Die Installation erfolgt für dein Windows-Konto,
ohne Administratorrechte. Danach findest du die App im Startmenü. Python muss nicht
separat installiert werden. Unterstützt: Windows 10/11, 64 Bit.

Alternativ: Portable ZIP vollständig entpacken und SmartResearchArchive.exe starten.
Der Ordner `_internal` muss neben der EXE bleiben. Einzelnes Herausziehen nur der
EXE funktioniert nicht. Die Downloads enthalten keine wissenschaftlichen PDFs.

Die App ist nicht digital signiert; Windows kann einen unbekannten Herausgeber
anzeigen. Vergleiche im Zweifel den Download mit den veröffentlichten SHA256-Prüfsummen.

## 1. Ordner und Analyse wählen

Mit **Ordner auswählen** öffnest du beispielsweise Downloads oder einen eigenen
Literaturordner. Eingelesen werden ausschließlich PDFs direkt darin. Vorhandene
Unterordner und deren Dateien werden nicht durchsucht.

Analysearten:

- **Feste Themen:** fünf vordefinierte Kategorien, transparente Keyword-Punkte.
- **Themen aus Begriffen:** wiederkehrende Wörter/Wortpaare aus deiner Sammlung.
- **ChatGPT:** inhaltliche Zusammenfassungen, gemeinsame Themen und begründete Zuordnung.

Die ersten beiden Modi sind lokal und brauchen keinen KI-Zugang. Vor dem ersten
Einsortieren solltest du Backup-Kopien behalten. Akzeptieren verschiebt Originaldateien.

## 2. ChatGPT verbinden (optional)

Wähle eine gespeicherte Verbindung oder **Neues Konto / Workspace** und klicke auf
**Mit ChatGPT verbinden**. Die App öffnet deinen Browser. Melde dich an und erlaube
die Nutzung deines ChatGPT-Abos. Eine Anmeldung allein reicht nicht; die Berechtigung
muss tatsächlich erteilt werden. Die App prüft sie und bietet die für dein Konto
verfügbaren Modelle an. **Modelle laden** aktualisiert die Auswahl für ein gespeichertes
Konto. **Nutzung verwalten** öffnet die Einstellungen in ChatGPT.

Bestätige das Kontrollkästchen zur externen Verarbeitung. Nur bei gewählter
ChatGPT-Analyse werden PDF-Texte und Zusammenfassungen an OpenAI gesendet.
Original-PDFs werden nicht als Dateien hochgeladen; Dateinamen werden beim Modell
durch interne IDs ersetzt. Es ist kein API-Schlüssel nötig und es gibt keinen
automatischen Wechsel zu separat bezahlter API-Nutzung.

OpenAI entscheidet über die tatsächliche Freigabe deiner Anmeldung, deines
Workspaces und der Modelle. App-Anfragen zählen zu deinen bestehenden Abo-Limits.
Der Live-Zugang und die inhaltliche Qualität müssen mit deinem Konto geprüft werden.

## 3. Analysieren und Themen prüfen

**PDFs analysieren** verändert noch keine Datei. Fortschritt und Probleme erscheinen
unten und im Verlauf. Beschädigte/verschlüsselte PDFs werden als nicht lesbar gemeldet.
Bildscans ohne Textlayer benötigen OCR; diese Version enthält keine OCR.

Im zweiten Reiter wählst du ein Thema, änderst den Namen und die Beschreibung bzw.
Keywords und setzt **Dieses Thema verwenden**. Danach **Änderungen am Thema übernehmen**.
**Neues Thema** erlaubt eine eigene Kategorie. Es dürfen höchstens fünf Themen
ausgewählt sein. Namen verwenden ASCII-Buchstaben/Ziffern, Leerzeichen, Unterstriche
oder Bindestriche (max. 60 Zeichen); doppelte und unsichere Namen werden abgelehnt.
Für lokale Analyse sind Keywords kommagetrennt; ChatGPT nutzt eine inhaltliche Beschreibung.

Mit **Themen bestätigen & PDFs zuordnen** entstehen die Dateivorschläge. Ohne
ausgewählte Themen schlägt die App nach Rückfrage Unclassified vor.

## 4. Dateien bestätigen

Wähle eine PDF im dritten Reiter. Prüfe Titel, Autor, Jahr, Thema und den Zielpfad.
Alle Metadaten sind Vorschläge und dürfen korrigiert werden. Fehlende Angaben
nutzen UnknownAuthor / UnknownYear. Das Jahr ist vierstellig oder UnknownYear.

**Bestätigen & einsortieren** verschiebt ausschließlich diese Datei:

```text
Downloads/
  Political History/
    Ada_2024_Example_Title.pdf
  Unclassified/
    UnknownAuthor_UnknownYear_Another_Paper.pdf
  Noch_nicht_bestaetigt.pdf
```

Die Themenordner werden im ausgewählten Ordner angelegt. Dateinamen sind portable
ASCII-Namen nach Author_Year_Title.pdf. Namenskollisionen erhalten `_2`, `_3`, usw.
Existierende Dateien werden nicht überschrieben. Vor und nach dem Kopieren prüft
die App den PDF-Inhalt; bei Änderungen muss die Datei neu analysiert werden.

**Überspringen** lässt die Datei unverändert. Eine neue Analyse liest nur noch die
PDFs direkt im Ordner, ohne bereits einsortierte Unterordner erneut einzubeziehen.

## Abbrechen, Fehler und Abmelden

**Abbrechen** stoppt vor dem nächsten Arbeitsschritt. Eine bereits laufende
Netzwerkanfrage oder Kopie wird zunächst beendet. Bereits bestätigte Dateien
bleiben einsortiert. Schließe die App erst, wenn der laufende Vorgang beendet ist.
Bei einem Kopier-/Löschfehler kontrolliere Ausgangs- und Themenordner: Zwei Kopien
können zurückbleiben, wenn die Quelle nach erfolgreicher Kopie nicht gelöscht werden konnte.

Für ChatGPT gelten 50 Input-PDFs und maximal 240.000 extrahierte Zeichen pro PDF.
Es werden alle Abschnitte analysiert; überlange PDFs werden nicht still gekürzt.
KI-Zusammenfassungen können Details verlieren, Zuordnungen können falsch sein.
Geprüfte Belegzitate beweisen Wortlaut, nicht die Richtigkeit einer Interpretation.

**Abmelden** löscht lokale Tokens und versucht die Sitzung bei OpenAI zu widerrufen.
Wenn das nicht bestätigt werden kann, trenne die App zusätzlich in ChatGPTs
verbundenen Anwendungen. Windows speichert die Verbindung verschlüsselt unter
`%LOCALAPPDATA%\SmartResearchArchive\chatgpt`. Die Deinstallation löscht weder
deine PDFs noch diesen separaten Kontospeicher. Vor einer Deinstallation abmelden.
Nach einem Absturz: Nur wenn keine App-Instanz mehr läuft, den leeren Unterordner
`runtime.lock` im Kontospeicher löschen. Niemals Kontodateien weitergeben.

## Status

Version 1.0.0 ist ein Desktop-Release-Kandidat für das Kursprojekt. Automatisierte
Tests sowie EXE-/Installationschecks sind Bestandteil des Builds; ein persönlicher
Live-Test mit ChatGPT und deiner PDF-Sammlung bleibt erforderlich.
All rights reserved. Drittanbieter-Komponenten behalten ihre eigenen Lizenzen.
