# Smart Research Archive 2.1.0 — Windows

Drei Analysewege:
1. Lokal: eigene Themen und Keywords; keine automatischen lokalen Themenvorschläge.
2. Lokal mit LLM-Keywords: eigene Oberthemen eingeben, Keywords mit ChatGPT vorschlagen
   lassen, je Thema prüfen und übernehmen, dann Regeln bestätigen. Die PDF-Auswertung
   erfolgt lokal. Zur Keyword-Erzeugung werden nur Themen/Beschreibungen gesendet.
3. ChatGPT: vollständige Inhaltsanalyse mit geprüften Belegstellen und Themenzuordnung.

Beschleunigung: höchstens zwei PDFs gleichzeitig (abschaltbar), gebündelte Zuordnung
von bis zu vier Zusammenfassungen und kombinierte Zusammenfassung/Zuordnung bei
bereits bestätigten Regeln. Vorhandene Analysen bleiben wiederverwendbar.
Die reale Laufzeit hängt vom Modell, den Dokumenten und den Abo-Limits ab.

Lokale OCR je Seite bei fehlender/unbrauchbarer Textebene. Vorhandener Text wird
verwendet, erfolgreiche OCR gespeichert, Original-PDFs werden nicht verändert.
Tesseract mit Deutsch/Englisch und der PDF-Renderer sind im Windows-Paket enthalten.
Bei fehlgeschlagenen Seiten erfolgt keine unbemerkte LLM-Auswertung eines Teiltexts:
Die PDF bleibt zur späteren Prüfung. OCR für Handschrift/Fraktur ist nicht zugesichert.

Vorherige App schließen und SmartResearchArchive-2.1.0-Setup.exe installieren.
Python oder eine separate OCR-Installation sind für das Komplettpaket nicht nötig.
Alternativ die portable ZIP vollständig entpacken und SmartResearchArchive.exe starten.

Bestehende Archive, Regeln, Duplikatprüfung, Einzelbestätigung, Rückgängig,
Kontoverwaltung und Abbruch/Fortsetzen bleiben verfügbar. Die Anleitung im Paket
beschreibt den Ablauf. PDFs und lokale Zugangsdaten werden nicht nach GitHub geladen.

Automatische Prüfungen verwenden synthetische PDFs, echte lokale OCR und simulierte
Modellantworten. Live-Anmeldung und wissenschaftliche Qualität weiterhin selbst
prüfen. Der Installer ist nicht digital signiert. Sicherungskopien behalten.

All rights reserved. Drittkomponenten behalten ihre eigenen Lizenzen;
deren Hinweise sind im Download enthalten.
