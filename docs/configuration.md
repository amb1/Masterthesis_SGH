# Konfigurationsstruktur

Die Konfiguration des SGH-Master-Projekts ist in mehrere logische Einheiten aufgeteilt, die jeweils spezifische Aspekte der Anwendung steuern.

## Übersicht

```
config/
├── global.yml          # Zentrale Projektkonfiguration
├── cea/               # City Energy Analyst Konfiguration
│   └── mapping.yml    # Gebäudetyp- und Feldmappings
├── wfs/               # Web Feature Service
│   └── stream_config.yml  # WFS-Endpunkte und Layer
└── osm/               # OpenStreetMap
    └── sources.yml    # OSM-Datenquellen und Filter

.cursor/rules/base/    # Entwicklungs- und Validierungsregeln
├── 010-transformations.mdc    # Transformationsregeln
├── 015-global-config.mdc      # Globale Konfigurationsvalidierung
├── 016-cea-config.mdc         # CEA-Konfigurationsvalidierung
├── 017-wfs-config.mdc         # WFS-Konfigurationsvalidierung
├── 018-osm-config.mdc         # OSM-Konfigurationsvalidierung
├── 020-citygml.mdc            # CityGML-Verarbeitungsregeln
├── 030-config.mdc             # Allgemeine Konfigurationsregeln
├── 040-logging.mdc            # Logging-Regeln
├── 050-pipeline.mdc           # Pipeline-Verarbeitungsregeln
├── 060-testing.mdc            # Testregeln
└── ...                        # Weitere Entwicklungsregeln
```

## Globale Konfiguration (global.yml)

Die zentrale Konfigurationsdatei enthält:
- Projektinformationen (Name, Version, etc.)
- Logging-Einstellungen
- Pipeline-Konfiguration
- Verarbeitungseinstellungen

Beispiel:
```yaml
project:
  name: "SGH-Master"
  version: "1.0.0"
  paths:
    data: "data"
    output: "outputs"
```

## CEA-Konfiguration (cea/mapping.yml)

Definiert die Mappings für:
- Gebäudetypen und deren CEA-Entsprechungen
- Geometrische Einstellungen
- Feldvalidierung
- Quellsystem-Mappings

## WFS-Konfiguration (wfs/stream_config.yml)

Konfiguriert:
- WFS-Endpunkte
- Layer-Definitionen
- Feldmappings
- Cache-Einstellungen

## OSM-Konfiguration (osm/sources.yml)

Definiert:
- Bounding Box für Datenextraktion
- Tag-Filter für Gebäude und Straßen
- Standardwerte
- Cache-Einstellungen

## Verwendung im Code

```python
from core.config_manager import config_manager

# Globale Konfiguration laden
global_config = config_manager.get_global_config()

# CEA-Konfiguration laden
cea_config = config_manager.get_cea_config()

# WFS-Konfiguration laden
wfs_config = config_manager.get_wfs_config()

# OSM-Konfiguration laden
osm_config = config_manager.get_osm_config()
```

## Validierung

Die Konfigurationsvalidierung erfolgt über `.mdc`-Dateien im `base/`-Verzeichnis:
- `015-global-config.mdc`: Validierung der globalen Konfiguration
- `016-cea-config.mdc`: Validierung der CEA-Konfiguration
- `017-wfs-config.mdc`: Validierung der WFS-Konfiguration
- `018-osm-config.mdc`: Validierung der OSM-Konfiguration

## Cache

Der ConfigManager implementiert ein Caching-System für Konfigurationsdateien:
- Dateien werden nur einmal geladen
- `reload_all()` erzwingt ein Neuladen aller Konfigurationen
- Cache ist prozessweit gültig 