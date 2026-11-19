# BP 100 HE – Proof of Concept

`index.html` lokal im Browser öffnen. Die Anwendung benötigt keinen Server und versendet keine Daten. Die Konfiguration kann als JSON gespeichert oder über den Browser als PDF gedruckt werden.

Grundlage: BP 100 HE Order checklist Rev. 08, Produktionsblatt-Header, blattbezogene technische/kommerzielle Zuordnungen und Produktionsnotizen. `python poc/export_data.py` erzeugt `history.js` aus diesen Excel-Dateien erneut (Python und openpyxl erforderlich). Historische Treffer werden nach Anzahl übereinstimmender kommerzieller Codes sortiert; sie sind keine Ableitung einer gültigen Stückliste. Historische Notizen können auftragsspezifisch sein und sind nicht automatisch zu übernehmen.

Der Prototyp prüft ausgewählte ausdrücklich dokumentierte Abhängigkeiten. Er ist nicht vollständig validiert und erzeugt keine Produktionsstückliste, keinen Preis und keine Freigabe. Die allgemeinen Codezuordnungen, Produktionsaufträge, Komponentenlisten und technischen Stücklisten sind noch nicht integriert. Die separate Anforderungs-PDF und die G-1.5-Referenz waren im bereitgestellten Verzeichnis nicht vorhanden.

## Einordnung BP100-Gesamtfamilie

Die sechs Checklisten teilen Auftragsdaten, Installationsangaben, Stromversorgung und Optionsauswahl, nutzen aber verschiedene Codepräfixe (FBAA, FBBA, FBCA, FBEA, FBFA, FBGA) und unterschiedliche Varianten/Optionen. Empfohlen wird ein gemeinsamer Konfigurator mit eigenständigen, versionierten Familien-Datenmodellen und Regeln. Die Machbarkeit ist für eine gemeinsame Oberfläche plausibel; die Richtigkeit einer vollständigen gemeinsamen Regel- und Stücklistenlogik ist ohne detaillierten Abgleich aller Checklisten und historischer Daten nicht belegt. Vor Erweiterung: Regeln und Pflichtfelder mit Fachbereich validieren, revisions- und gültigkeitsbezogene technische Zuordnungen klären und Soll-Ausgabe einschließlich BOM definieren.
