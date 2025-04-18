# SGH - Sustainability Geo Hub

Ein Webtool zur Visualisierung und Analyse von Gebäudedaten mit CesiumJS, kombiniert mit einem Python-Backend zur Verarbeitung von CityGML-Daten für CEA (City Energy Analyst).

## Projektstruktur

Das Projekt besteht aus zwei Hauptkomponenten:
- `/local`: Python-Backend für CityGML-Verarbeitung
- `/web`: React-Frontend mit CesiumJS

## Local Setup (Python Backend)

### Voraussetzungen
- Python 3.9+
- pip

### Installation
1. Navigieren Sie in das `/local` Verzeichnis
2. Erstellen Sie eine virtuelle Umgebung:

bash
python -m venv venv
source venv/bin/activate # Linux/Mac
venv\Scripts\activate # Windows

3. Installieren Sie die Abhängigkeiten:

bash
pip install -r requirements.txt


### Ausführung
Das Hauptskript befindert sich unter '/scripts/':

bash
python scripts/process_citygml.py

Dieses Skript hat die Funktionen:
- CityGML Dateie aus /data/citygml zu laden und zu verarbeiten
- Reichert die Daten mit WFS-Streams an
- Erstellt die Projektordner für CEA

## Web Setup (React Frontend)

### Tech Stack
- React 18
- TypeScript
- Vite
- CesiumJS
- Supabase (Auth & Backend)
- TailwindCSS

### Installation
1. Navigieren Sie in das `/web` Verzeichnis
2. Installieren Sie die Abhängigkeiten:

bash
npm install

### Ausführung
Starten Sie den Entwicklungsserver:

bash
npm run dev

### Entwicklung
Für Entwicklungszwecke ist das Projekt mit Hot Module Replacement (HMR) konfiguriert.

Der Server ist dann unter `http://localhost:5173` erreichbar.

### Benutzung
1. Registrieren Sie sich mit Ihrer E-Mail-Adresse
2. Bestätigen Sie Ihre E-Mail über den zugesendeten Link
3. Melden Sie sich an
4. Nutzen Sie die 3D-Visualisierung mit CesiumJS