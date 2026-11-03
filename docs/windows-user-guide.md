# Smart Research Archive — Windows-Anleitung

## Installieren und aktualisieren

Auf der [Release-Seite](https://github.com/Antargos/SmartResearchArchive/releases)
**SmartResearchArchive-2.0.0-Setup.exe** herunterladen. Eine laufende ältere App
schließen, dann installieren. Der Assistent installiert für dein Windows-Konto
ohne Administratorrechte. Danach die App über das Startmenü starten.
Windows 10/11, 64 Bit; Python ist im Download enthalten.

Alternativ die portable ZIP vollständig entpacken und SmartResearchArchive.exe
starten. Der Ordner `_internal` muss neben der EXE bleiben.
Der Installer ist nicht digital signiert. SHA256-Prüfsummen stehen beim Release.
Die Downloads enthalten keine wissenschaftlichen PDFs.

## 1. Analyseart und Ordner wählen

Zuerst **Lokal** oder **ChatGPT (LLM)** auswählen. Lokal bleibt der Dokumenttext auf
deinem Rechner; die Zuordnung zählt nachvollziehbare Keyword-Treffer.
ChatGPT wertet Textabschnitte inhaltlich aus und begründet seine Vorschläge.

Danach wählen, woher die Themen kommen:

- **Eigene Themen:** über **Themen / Keywords festlegen oder bearbeiten** Namen,
  Beschreibungen und Keywords eingeben. Das geht vor der ersten PDF-Analyse.
- **Themen vorschlagen:** ChatGPT schlägt inhaltliche Kategorien vor. Lokal entstehen
  lediglich ungeprüfte Begriffshilfen aus Titeln und Textanfängen. Diese sind nicht
  vorausgewählt; wiederkehrende Wörter sind noch keine sinnvolle Forschungssystematik.
- **Vorhandene Unterordner übernehmen:** über den Bearbeiten-Button vorhandene
  Ordnernamen als unbestätigten Entwurf laden, Beschreibung/Keywords ergänzen und
  bewusst auswählen. Unterordner werden dabei nicht inhaltlich analysiert.
- **Archivregeln verwenden:** für einen bereits eingerichteten Archivordner. Diese
  Auswahl wird automatisch geladen; die Themen müssen nicht erneut eingegeben werden.

Mit **Ordner auswählen …** beispielsweise Downloads oder einen eigenen
Literaturordner wählen. Normalerweise werden ausschließlich PDFs direkt darin
eingelesen. Bestätigte Dateien landen in Themen-Unterordnern desselben Ordners.
Vor dem ersten Einsortieren Sicherungskopien behalten.

**PDFs analysieren** bleibt unten in einer festen Leiste sichtbar. Formulare
lassen sich senkrecht und bei Bedarf waagerecht scrollen. Themenbestätigung und
Einsortieren haben ebenfalls feste Aktionsleisten.

## 2. ChatGPT verbinden (optional)

Im LLM-Modus eine gespeicherte Verbindung auswählen oder **Mit ChatGPT verbinden**
anklicken. Im Browser anmelden und die Nutzung des ChatGPT-Abos erlauben.
Danach ein verfügbares Modell wählen und **Externe Verarbeitung mit ChatGPT erlauben**
aktivieren. **Modelle laden** aktualisiert die Auswahl; **Nutzung verwalten** öffnet
die ChatGPT-Einstellungen.

Die App sendet extrahierte PDF-Texte und Zusammenfassungen an OpenAI. PDF-Dateien
werden nicht als Originaldateien hochgeladen; im Modellkontext stehen interne IDs.
Es wird kein API-Schlüssel benötigt. Die Verfügbarkeit von Konto, Workspace,
Modellen und Abo-Limits bestimmt OpenAI. Den Live-Zugang mit dem eigenen Konto prüfen.

**Abmelden** versucht den Sitzungswiderruf und entfernt lokale Sitzungstoken, behält
den Verbindungseintrag aber zur späteren Anmeldung.
**Verbindung löschen** entfernt nach Rückfrage zusätzlich die lokale Registrierung.
Andere Verbindungen bleiben erhalten. Nicht bestätigter Remote-Widerruf wird angezeigt;
eine verbleibende App-Freigabe gegebenenfalls in den ChatGPT-Einstellungen trennen.

## 3. Analysieren und Regeln bestätigen

**PDFs analysieren** erzeugt eine Vorschau und verschiebt noch keine Datei.
Fortschritt und Hinweise stehen unten und unter **Verlauf**.

Bei eigenen LLM-Regeln prüft ChatGPT deren Eignung für die Dokumente. Die eigene
Forschungsfrage bleibt maßgeblich. Neue Themen erscheinen als zusätzliche,
nicht ausgewählte Vorschläge. Erst deine Auswahl und Bestätigung ändern die Regeln.
Bei einem gespeicherten Archiv wird diese Themenprüfung nicht automatisch wiederholt.

Im Reiter **2 Themen** ein Thema auswählen und bearbeiten:

- **Themenname:** Name des Zielordners.
- **Themenbeschreibung:** inhaltliche Abgrenzung für ChatGPT.
- **Keywords:** kommagetrennte Wörter/Phrasen; für lokale Themen erforderlich.
  Im LLM-Modus dienen sie als zusätzliche Orientierung.
- **Dieses Thema verwenden:** nur ausgewählte Themen werden gespeichert.

**Änderungen übernehmen** speichert die Eingaben im Entwurf. **Neues Thema** ergänzt
eine Kategorie. Höchstens fünf Themen auswählen. Sichere Namen mit Buchstaben
(einschließlich Umlauten), Ziffern, Leerzeichen, Unterstrichen und Bindestrichen
sind erlaubt, maximal 60 Zeichen. Reservierte Windows-Namen, doppelte Namen und
Unclassified als eigener Themenname sind ausgeschlossen.

**Regeln bestätigen & weiter** speichert die ausgewählten Regeln für diesen
Archivordner und ordnet die PDFs zu. Ohne ausgewählte Themen ist nach Rückfrage
Unclassified möglich. Bei bereits gespeicherten Regeln geht es nach der Analyse
direkt zur Dateivorschau.

## 4. Jede Datei prüfen und einsortieren

Im Reiter **3 PDFs** Titel, Autor, Jahr, Thema und Zielpfad prüfen.
Die Detailansicht nennt die Herkunft der Metadaten und mögliche Widersprüche.
Neben PDF-Metadaten werden erkennbare Dateinamen wie
`02_Jones_Origins_2006.pdf`, `Jones_2006_Origins.pdf` und
`Jones - 2006 - Origins.pdf` ausgewertet. Das sind Vorschläge, keine verifizierten
bibliografischen Angaben. Fehlende Werte bleiben UnknownAuthor / UnknownYear.

**PDF öffnen** zeigt das Original im üblichen PDF-Programm.
**Bestätigen & einsortieren** benennt ausschließlich die ausgewählte Datei um und
verschiebt sie, beispielsweise nach:

```text
Literatur/
  .smart-research-archive/
    archive.sqlite3
  Migration/
    Jones_2006_Origins.pdf
  Unclassified/
    UnknownAuthor_UnknownYear_Another_Paper.pdf
  Noch_nicht_bestaetigt.pdf
```

Dateinamen folgen Author_Year_Title.pdf mit portablen ASCII-Zeichen.
Kollisionen bekommen _2, _3 usw.; vorhandene Dateien werden nicht überschrieben.
Geänderte Quelldateien müssen neu analysiert werden.

**Später prüfen** merkt die Datei einschließlich der eingegebenen Metadaten vor.
**Überspringen** lässt sie unverändert. Beide Zustände werden beim nächsten Lauf
wiederhergestellt. **Erneut prüfen** öffnet die ausgewählte vorgemerkte oder
übersprungene Datei wieder zur Zuordnung und manuellen Prüfung.

Identische Dateien erhalten **Duplikat** und einen Verweis auf die vorhandene
Datei. Sie werden vor einer weiteren LLM-Auswertung erkannt und bleiben liegen.
Die App löscht keine Duplikate. Erkannt wird gleicher Dateiinhalt, nicht derselbe
Aufsatz in einer anderen Scanversion.

## 5. Später neue PDFs hinzufügen

Neue Downloads direkt in denselben Hauptordner legen. Die App merkt sich den zuletzt
verwendeten Ordner. Beim Öffnen eines eingerichteten Archivs lädt sie dessen Regeln
und wählt **Archivregeln verwenden**. **PDFs analysieren** prüft die neuen Dateien
mit diesen Regeln. Bestehende Themenordner werden nicht erneut inhaltlich analysiert;
für die Duplikatprüfung werden dort Dateiprüfsummen gelesen.

Regeln über **Themen / Keywords festlegen oder bearbeiten** bewusst ändern.
Alte Themenordner bleiben erhalten. Ein neuer Themenname benennt einen vorhandenen
Ordner nicht automatisch um.

**Bestehende Sammlung ausdrücklich neu prüfen** nimmt nach Rückfrage zusätzlich
PDFs direkt in den verwalteten Themenordnern und Unclassified auf. Fremde und
tiefer verschachtelte Ordner bleiben außen vor. Jede Umbenennung oder Umsortierung
braucht weiterhin eine Einzelbestätigung.

Im LLM-Modus fordert **Neue Themen vorschlagen / Regeln prüfen** bewusst eine neue
Prüfung an. **Regelvorschläge aus Korrekturen** bietet nach Korrekturen an mindestens
zwei verschiedenen PDFs gemeinsame Begriffe als Entwurf an. Das ist eine einfache
Begriffshilfe; die App lernt und ändert Regeln nicht unbemerkt.
Die eigentliche Regeländerung braucht anschließend die Themenbestätigung.

## Abbruch, Fortsetzen und Rückgängig

**Abbrechen** stoppt am nächsten sicheren Schritt. Eine laufende Netzwerkanfrage
oder Dateikopie wird zunächst beendet. Bestätigte Einsortierungen bleiben bestehen.

Erfolgreiche Textextraktionen, LLM-Abschnitte, Zusammenfassungen und Zuordnungen
werden nach jedem Schritt lokal gespeichert. Zum Fortsetzen denselben Ordner und
dasselbe Modell wählen und erneut analysieren. Bei einer Regeländerung werden
Zuordnungen neu berechnet; passende Zusammenfassungen können weiterverwendet werden.
Ein Themenentwurf wird beim Analysestart gesichert. Ein abgebrochener, noch nicht
bestätigter Themenvorschlag kann erneut eine Modellanfrage benötigen.

**Analysecache leeren** entfernt nach Rückfrage gespeicherte Analysedaten und
Zuordnungen. Regeln, PDFs, Entscheidungen und Verschiebungsverlauf bleiben erhalten.
Die nächste LLM-Analyse benötigt entsprechend neue Anfragen.

**Letzte Einsortierung rückgängig machen** zeigt Original- und Zielpfad zur
Bestätigung. Nur die unveränderte PDF wird zurückverschoben. Ist der ursprüngliche
Name inzwischen belegt oder die archivierte Datei verändert, bricht die App ab.
Die Aktion funktioniert auch nach einem Neustart; wiederholtes Aufrufen geht
schrittweise durch den Verschiebungsverlauf.

## Lokale Daten und Grenzen

`.smart-research-archive/archive.sqlite3` im Hauptordner enthält Regeln, extrahierte
Texte, Zusammenfassungen, Entscheidungen, Dateiprüfsummen und Verschiebungsverlauf.
Sie enthält keine ChatGPT-Zugangsdaten und ist nicht verschlüsselt.
Beim Sichern oder Umziehen des Archivs den gesamten Ordner einschließlich dieses
Unterordners mitnehmen. Bei Weitergabe kann die Datenbank Dokumentinhalte enthalten.

Zugangsdaten liegen separat unter
`%LOCALAPPDATA%\SmartResearchArchive\chatgpt` und sind unter Windows durch DPAPI
an dein Benutzerkonto gebunden. Die zuletzt gewählte Ordneradresse wird ebenfalls
im Benutzerprofil gespeichert. Diese Daten nicht auf GitHub hochladen.

Keine OCR: Bildscans ohne Textlayer und nicht lesbare PDFs gehen nach **Später prüfen**.
Unbelegte Modellzitate werden abgelehnt; sie führen zur manuellen Prüfung dieser
Datei. Konten-/Netzwerk-/Limitfehler stoppen den Lauf, gespeicherte Schritte bleiben
erhalten. Es gibt keine versteckten automatischen Wiederholungen.
Ein neuer Lauf bearbeitet höchstens 50 noch nicht gespeicherte LLM-Dokumente;
lange Texte sind auf 20 Abschnitte beziehungsweise 240.000 Zeichen je PDF begrenzt.

Das Programm ist ein akademischer, AI-assisted entwickelter Prototyp. Automatisierte
Tests mit synthetischen PDFs und simulierten Modellantworten prüfen die Abläufe,
nicht die historische Richtigkeit der Ergebnisse. Inhaltliche Vorschläge und
Metadaten weiterhin selbst prüfen. Keine CSV-Ausgabe und keine Embeddings.

All rights reserved; siehe Rechtehinweis in der README. Keine Open-Source-Lizenz.
