# CesiumViewer Komponente

## Konfiguration

### Layer Management
```typescript
interface LayerConfig {
  arcGIS: boolean;    // Straßenkarte
  satellite: boolean; // Satellitenbilder
  tileset: boolean;   // 3D Gebäude
}

interface LayerOpacity {
  arcGIS: number;    // 0-1
  satellite: number; // 0-1
  tileset: number;   // 0-1
}
```

### Tileset Konfiguration
```typescript
interface TilesetConfig {
  maximumScreenSpaceError: number; // Default: 1
  maximumMemoryUsage: number;      // Default: 1024
  preloadWhenHidden: boolean;      // Default: true
  preferLeaves: boolean;           // Default: true
  debugShowBoundingVolume: boolean;// Default: true (nur Development)
  debugWireframe: boolean;         // Default: true (nur Development)
}
```

### Kamera Einstellungen
```typescript
interface CameraConfig {
  initialPosition: {
    longitude: number;  // Default: 16.3287 (Wien)
    latitude: number;   // Default: 48.2082 (Wien)
    height: number;     // Default: 1000 (Meter)
  };
  orientation: {
    heading: number;    // Default: 0 (Grad)
    pitch: number;      // Default: -45 (Grad)
    roll: number;       // Default: 0 (Grad)
  };
}
```

## Anpassungsmöglichkeiten

### 1. Tileset Position
Die Position des 3D-Modells kann über die ModelMatrix angepasst werden:
```typescript
const translation = Matrix4.fromTranslation(
  Cartesian3.fromDegrees(longitude, latitude, height)
);
tileset.modelMatrix = translation;
```

### 2. Terrain Konfiguration
```typescript
const terrain = await createWorldTerrainAsync({
  requestVertexNormals: true,
  requestWaterMask: true
});
```

### 3. Layer Steuerung
- Layer können einzeln ein-/ausgeblendet werden
- Opacity für jeden Layer einstellbar (0-1)
- Reihenfolge der Layer ist wichtig für die Darstellung

### 4. Kamera Steuerung
```typescript
// Zoom to Tileset
viewer.camera.flyToBoundingSphere(boundingSphere, {
  duration: 2,
  offset: new HeadingPitchRange(heading, pitch, range)
});

// Home Position
viewer.camera.flyTo({
  destination: Cartesian3.fromDegrees(lon, lat, height),
  orientation: {
    heading: CesiumMath.toRadians(heading),
    pitch: CesiumMath.toRadians(pitch),
    roll: 0
  }
});
```

## Bekannte Probleme & Lösungen

### 1. Tileset Höhenversatz
- Problem: Tileset erscheint zu hoch/niedrig
- Lösung: Anpassung der ModelMatrix und Terrain-Clipping

### 2. Layer Sichtbarkeit
- Problem: Layer bleiben manchmal sichtbar trotz Deaktivierung
- Lösung: Explizites Setzen von `show` und `alpha` Properties

### 3. Performance
- Problem: Langsames Laden bei großen Tilesets
- Lösung: Anpassung von `maximumScreenSpaceError` und `maximumMemoryUsage`

## Nächste Schritte

1. Implementierung eines korrekten Terrain-Clippings für das Tileset
2. Verbesserung der Home-Button Funktionalität
3. Optimierung der Layer-Steuerung
4. Hinzufügen von Tileset-spezifischen Steuerungselementen

## Beispiel-Konfiguration

```typescript
const VIENNA_CONFIG = {
  camera: {
    initialPosition: {
      longitude: 16.3287,
      latitude: 48.2082,
      height: 1000
    },
    orientation: {
      heading: 0,
      pitch: -45,
      roll: 0
    }
  },
  tileset: {
    maximumScreenSpaceError: 1,
    maximumMemoryUsage: 1024,
    preloadWhenHidden: true,
    preferLeaves: true
  },
  terrain: {
    requestVertexNormals: true,
    requestWaterMask: true
  }
};
``` 