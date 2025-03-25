import React, { useRef, useEffect, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Viewer } from "resium";
import { 
  Ion, 
  ArcGisMapServerImageryProvider, 
  createWorldImageryAsync,
  ImageryLayer,
  Scene,
  Viewer as CesiumViewerInstance,
  ImageryLayerCollection,
  Cartesian3,
  Math as CesiumMath,
  createWorldTerrainAsync,
  HeightReference,
  ClippingPlane,
  ClippingPlaneCollection,
  HeadingPitchRange,
  Matrix4,
  Transforms,
  Cartographic,
  SceneMode,
  Cesium3DTileset,
  Cesium3DTileStyle,
  TerrainProvider,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Cesium3DTileFeature,
  Color,
  Matrix3,
  Quaternion,
  Ray,
  IntersectionTests,
  Plane,
  Cartesian2,
  BoundingSphere
} from "cesium";
import { X, ArrowLeft, Settings } from 'lucide-react';
import LayerSidebar from './LayerSidebar';
import { createClient } from '@supabase/supabase-js';

// Supabase Client initialisieren
const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL || '',
  import.meta.env.VITE_SUPABASE_ANON_KEY || ''
);

interface CesiumViewerComponentProps {
  token: string;
  projectId: string;
  onBack?: () => void;
  showLayerSidebar: boolean;
  onToggleLayerSidebar: () => void;
  showSettings: boolean;
  onToggleSettings: () => void;
}

export interface CesiumViewerRef {
  loadAsset: (assetId: number) => Promise<void>;
}

interface FeatureInfo {
  id?: string;
  properties: Record<string, any>;
  tileset?: Cesium3DTileset;
  metadata?: {
    building_id?: string;
    name?: string;
    address?: string;
    year_built?: number;
    building_type?: string;
    height?: number;
    floor_area?: number;
    energy_class?: string;
    last_renovation?: string;
    owner?: string;
    custom_properties?: Record<string, any>;
  };
}

interface HiddenFeature {
  featureId: string;
  tilesetId: number;
}

interface ExtendedCesium3DTileset extends Cesium3DTileset {
  selectedProperties?: string[];
}

const CesiumViewerComponent = forwardRef<CesiumViewerRef, CesiumViewerComponentProps>(({ 
  token,
  projectId,
  onBack,
  showLayerSidebar,
  onToggleLayerSidebar,
  showSettings,
  onToggleSettings
}, ref) => {
  const [viewer, setViewer] = useState<CesiumViewerInstance | null>(null);
  const [terrainProvider, setTerrainProvider] = useState<TerrainProvider | null>(null);
  const [loadingAssets, setLoadingAssets] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFeature, setSelectedFeature] = useState<FeatureInfo | null>(null);
  const [loadedTilesets, setLoadedTilesets] = useState<Map<number, ExtendedCesium3DTileset>>(new Map());
  const [selectedTilesetId, setSelectedTilesetId] = useState<number | null>(null);
  const [showTimeline, setShowTimeline] = useState(false);
  const [hiddenFeatures, setHiddenFeatures] = useState<HiddenFeature[]>([]);
  const lastHighlightedBatchId = useRef<number | null>(null);

  useImperativeHandle(ref, () => ({
    loadAsset: async (assetId: number) => {
      if (!viewer) return;
      await loadAsset(assetId);
    }
  }));

  // Terrain Provider initialisieren
  useEffect(() => {
    const initTerrainProvider = async () => {
      if (!token) {
        console.error('Kein Cesium Ion Token verfügbar');
        return;
      }

      try {
        Ion.defaultAccessToken = token;
        const terrain = await createWorldTerrainAsync({
          requestVertexNormals: true,
          requestWaterMask: true
        });
        setTerrainProvider(terrain);
      } catch (err) {
        console.error('Fehler beim Initialisieren des Terrain Providers:', err);
        setError('Terrain Provider konnte nicht initialisiert werden');
      }
    };
    initTerrainProvider();
  }, [token]);

  // Cesium Ion Assets laden
  useEffect(() => {
    const loadIonAssets = async () => {
      if (!viewer || !token) {
        console.error('Viewer oder Token nicht verfügbar');
        return;
      }

      try {
        if (Ion.defaultAccessToken !== token) {
          Ion.defaultAccessToken = token;
        }
        
        // Keine automatische Ladung von Assets mehr
        // Die Assets werden jetzt über die LayerSidebar gesteuert
      } catch (err) {
        console.error('Fehler beim Laden der Ion Assets:', err);
        setError('Fehler beim Laden der Assets');
      }
    };

    loadIonAssets();
  }, [viewer, token]);

  const highlightFeature = useCallback((feature: Cesium3DTileFeature | null, tileset: Cesium3DTileset) => {
    if (!tileset || !viewer) return;

    try {
      // Debug: Zeige Feature-Details
      const batchId = feature ? (feature as any)._batchId : null;
      console.log('🔍 Feature Details:', {
        batchId,
        hasFeature: !!feature,
        content: feature ? (feature as any)._content : null
      });

      // Hole alle Features des Tilesets
      const allFeatures = (tileset as any)._selectedTiles?.reduce((acc: any[], tile: any) => {
        if (tile.content?.batchTable?._features) {
          return [...acc, ...tile.content.batchTable._features];
        }
        return acc;
      }, []) || [];

      // Setze alle Features auf die Standardfarbe zurück
      allFeatures.forEach((f: any) => {
        if (f._batchId !== batchId) {
          f.color = Color.WHITE.withAlpha(0.6);
        }
      });

      // Wenn ein neues Feature ausgewählt wurde, färbe es gelb
      if (feature && batchId !== null) {
        const currentFeature = allFeatures.find((f: any) => f._batchId === batchId);
        if (currentFeature) {
          currentFeature.color = Color.YELLOW.withAlpha(0.8);
          console.log('🎨 Neue Farbe gesetzt für BatchId:', batchId);
        }
      }

      // Erzwinge ein Re-Rendering des Tilesets
      if (tileset.style) {
        const currentStyle = tileset.style;
        tileset.style = undefined;
        setTimeout(() => {
          tileset.style = currentStyle;
        }, 0);
      }

    } catch (err) {
      console.error('❌ Fehler beim Hervorheben des Features:', err);
    }
  }, [viewer]);

  const handleFeatureClick = useCallback(async (movement: any) => {
    if (!viewer || !selectedTilesetId) return;

    const scene = viewer.scene;
    const pickedObject = scene.pick(movement.position);

    if (pickedObject instanceof Cesium3DTileFeature) {
      const properties: Record<string, any> = {};
      
      try {
        // Debug: Zeige das komplette Feature-Objekt
        console.log('Picked Object:', pickedObject);

        // Hole die batchId als Feature-ID
        const batchId = (pickedObject as any)._batchId;
        console.log('Batch ID:', batchId);

        // Versuche alle verfügbaren Property IDs zu bekommen
        const propertyIds = pickedObject.getPropertyIds([]);
        console.log('Property IDs:', propertyIds);

        // Versuche die Batch-Tabelle direkt zu lesen
        const batchTable = (pickedObject as any)._content?.batchTable;
        if (batchTable) {
          console.log('Batch Table:', batchTable);
          
          // Versuche die Property-Tabelle zu lesen
          if (batchTable._propertyTable) {
            console.log('Property Table:', {
              properties: batchTable._propertyTable._properties,
              propertiesBySemantic: batchTable._propertyTable._propertiesBySemantic,
              propertyDescriptions: batchTable._propertyTable._propertyDescriptions
            });
          }
        }

        // Versuche alle Properties über verschiedene Methoden zu sammeln
        propertyIds.forEach(propertyId => {
          try {
            const value = pickedObject.getProperty(propertyId);
            if (value !== undefined && value !== null) {
              // Formatiere die Properties entsprechend ihrer Art
              switch(propertyId) {
                case 'Height':
                case 'TerrainHeight':
                case 'HoeheDach':
                case 'HoeheGrund':
                case 'NiedrigsteTraufeDesGebaeudes':
                case 'bldg:measuredheight':
                  // Höhenangaben auf 2 Dezimalstellen runden
                  properties[propertyId] = Number(value).toFixed(2);
                  break;
                case 'Latitude':
                case 'Longitude':
                  // Koordinaten auf 6 Dezimalstellen runden
                  properties[propertyId] = Number(value).toFixed(6);
                  break;
                case 'core:creationdate':
                  // Datum formatieren
                  properties['Erstellungsdatum'] = new Date(value).toLocaleDateString('de-DE');
                  break;
                case 'gml:id':
                  properties['ID'] = value;
                  break;
                case 'gml:name':
                  properties['Name'] = value;
                  break;
                case 'Blattnummer':
                  properties['Blattnummer'] = value;
                  break;
                case 'bldg:rooftype':
                  // Dachtyp übersetzen
                  const roofTypes: Record<string, string> = {
                    'FLAT': 'Flachdach',
                    'SHED': 'Pultdach',
                    'GABLED': 'Satteldach',
                    'HIPPED': 'Walmdach',
                    'PYRAMIDAL': 'Pyramidendach',
                    'MANSARD': 'Mansarddach',
                    'DOME': 'Kuppeldach',
                    'ONION': 'Zwiebeldach',
                    'ROUND': 'Runddach',
                    'SKILLION': 'Schleppdach',
                    'GAMBREL': 'Krüppelwalmdach',
                    'SALTBOX': 'Saltbox-Dach',
                    'BUTTERFLY': 'Schmetterlingsdach',
                    'BARREL': 'Tonnendach',
                    'HALF-HIPPED': 'Krüppelwalmdach',
                    'PAVILION': 'Zeltdach',
                    'CONE': 'Kegeldach',
                    'SAWTOOTH': 'Sheddach'
                  };
                  properties['Dachtyp'] = roofTypes[value] || value;
                  break;
                default:
                  properties[propertyId] = value;
              }
            }
          } catch (err) {
            console.warn(`Fehler beim Lesen der Eigenschaft ${propertyId}:`, err);
          }
        });

        // Versuche auch direkt auf die Batch-Tabellen-Eigenschaften zuzugreifen
        if (batchTable && batchTable._propertyTable && batchTable._propertyTable._properties) {
          Object.keys(batchTable._propertyTable._properties).forEach(prop => {
            try {
              const value = pickedObject.getProperty(prop);
              if (value !== undefined && value !== null) {
                properties[prop] = value;
              }
            } catch (err) {
              console.warn(`Fehler beim Lesen der Batch-Tabellen-Eigenschaft ${prop}:`, err);
            }
          });
        }

        // Debug-Ausgaben
        console.log('Alle verfügbaren Eigenschaften:', properties);
        
        // Versuche die Feature-ID aus verschiedenen Quellen
        const featureId = 
          pickedObject.getProperty('id') || 
          pickedObject.getProperty('gmlid') ||
          pickedObject.getProperty('fid') ||
          pickedObject.getProperty('ID') ||
          pickedObject.getProperty('OBJECTID') ||
          batchId?.toString();

        console.log('Feature ID:', featureId);

        setSelectedFeature({
          id: featureId,
          properties,
          tileset: loadedTilesets.get(selectedTilesetId)
        });

        highlightFeature(pickedObject, loadedTilesets.get(selectedTilesetId)!);
      } catch (err) {
        console.warn('Fehler beim Lesen der Eigenschaften:', err);
      }
    } else {
      setSelectedFeature(null);
      if (selectedTilesetId) {
        highlightFeature(null, loadedTilesets.get(selectedTilesetId)!);
      }
    }
  }, [viewer, selectedTilesetId, highlightFeature, loadedTilesets]);

  const toggleFeatureVisibility = useCallback((featureId: string) => {
    if (!selectedTilesetId) return;

    // Konvertiere die Feature-ID zu einer Nummer, da wir jetzt mit batchId arbeiten
    const batchId = Number(featureId);
    if (isNaN(batchId)) {
      console.warn('Invalid batchId:', featureId);
      return;
    }

    setHiddenFeatures(prev => {
      const isHidden = prev.some(hidden => 
        hidden.featureId === featureId && hidden.tilesetId === selectedTilesetId
      );

      if (isHidden) {
        // Feature wieder sichtbar machen
        return prev.filter(hidden => 
          !(hidden.featureId === featureId && hidden.tilesetId === selectedTilesetId)
        );
      } else {
        // Feature verstecken
        return [...prev, { featureId, tilesetId: selectedTilesetId }];
      }
    });

    // Aktualisiere die Darstellung sofort
    if (selectedTilesetId) {
      const tileset = loadedTilesets.get(selectedTilesetId);
      if (tileset) {
        highlightFeature(selectedFeature?.id === featureId ? null : selectedFeature as any, tileset);
      }
    }
  }, [selectedTilesetId, selectedFeature, loadedTilesets, highlightFeature]);

  useEffect(() => {
    if (!viewer || !selectedTilesetId) return;

    const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction(handleFeatureClick, ScreenSpaceEventType.LEFT_CLICK);

    return () => {
      if (handler && !handler.isDestroyed()) {
        handler.destroy();
      }
    };
  }, [viewer, selectedTilesetId, handleFeatureClick]);

  useEffect(() => {
    if (!terrainProvider) return;

    Ion.defaultAccessToken = token;

    const cesiumViewer = new CesiumViewerInstance('cesiumContainer', {
      terrainProvider,
      baseLayerPicker: true,
      timeline: showLayerSidebar,
      animation: showLayerSidebar,
      geocoder: false,
      infoBox: false,
      selectionIndicator: false
    });

    cesiumViewer.scene.globe.enableLighting = true;

    setViewer(cesiumViewer);

    return () => {
      if (cesiumViewer && !cesiumViewer.isDestroyed()) {
        cesiumViewer.destroy();
      }
    };
  }, [token, terrainProvider, showLayerSidebar]);

  const loadAsset = async (assetId: number) => {
    if (!viewer) return;

    try {
      setLoadingAssets(true);
      setError(null);

      const tileset = await Cesium3DTileset.fromIonAssetId(assetId, {
        maximumScreenSpaceError: 8,
        preloadFlightDestinations: true,
        preferLeaves: true,
        skipLevelOfDetail: false,
        baseScreenSpaceError: 1024,
        skipScreenSpaceErrorFactor: 16,
        skipLevels: 1,
        immediatelyLoadDesiredLevelOfDetail: false,
        loadSiblings: true,
        cullRequestsWhileMoving: true,
        cullRequestsWhileMovingMultiplier: 0.5,
        preloadWhenHidden: true,
        dynamicScreenSpaceError: true,
        dynamicScreenSpaceErrorDensity: 0.00278,
        dynamicScreenSpaceErrorFactor: 4.0,
        dynamicScreenSpaceErrorHeightFalloff: 0.25
      });
      
      // Aktiviere Terrain-Collision
      viewer.scene.globe.depthTestAgainstTerrain = true;

      // Standardmäßig alle Properties aktivieren
      (tileset as ExtendedCesium3DTileset).selectedProperties = [
        'Height', 'Latitude', 'Longitude', 'TerrainHeight',
        'core:creationdate', 'gml:id', 'gml:name',
        'Blattnummer', 'HoeheDach', 'HoeheGrund',
        'NiedrigsteTraufeDesGebaeudes', 'bldg:measuredheight',
        'bldg:rooftype'
      ];
      
      viewer.scene.primitives.add(tileset);
      
      setLoadedTilesets(prev => {
        const next = new Map(prev);
        next.set(assetId, tileset);
        return next;
      });

      // Initiale Kameraposition
      viewer.zoomTo(
        tileset,
        new HeadingPitchRange(0.0, -0.5, tileset.boundingSphere.radius / 4.0)
      );

      setSelectedTilesetId(assetId);

    } catch (err) {
      console.error('Fehler beim Laden des Assets:', err);
      setError(`Fehler beim Laden von Asset ${assetId}: ${err.message}`);
    } finally {
      setLoadingAssets(false);
    }
  };

  const unloadAsset = (assetId: number) => {
    const tileset = loadedTilesets.get(assetId);
    if (tileset && viewer) {
      viewer.scene.primitives.remove(tileset);
      setLoadedTilesets(prev => {
        const next = new Map(prev);
        next.delete(assetId);
        return next;
      });

      if (selectedTilesetId === assetId) {
        setSelectedTilesetId(null);
      }
    }
  };

  const handleBackToProject = () => {
    if (onBack) {
      onBack();
    } else {
      window.history.back();
    }
  };

  // Eigenschaftsgruppen und Übersetzungen definieren
  const PROPERTY_GROUPS: Record<string, { label: string; properties: string[] }> = {
    identification: {
      label: 'Identifikation',
      properties: ['ID', 'Name', 'gml:id', 'gml:name', 'Blattnummer']
    },
    geometry: {
      label: 'Geometrie',
      properties: ['Height', 'TerrainHeight', 'Latitude', 'Longitude']
    },
    building: {
      label: 'Gebäude',
      properties: ['HoeheDach', 'HoeheGrund', 'NiedrigsteTraufeDesGebaeudes', 'bldg:measuredheight', 'bldg:rooftype']
    },
    metadata: {
      label: 'Metadaten',
      properties: ['Erstellungsdatum', 'core:creationdate']
    }
  };

  const PROPERTY_TRANSLATIONS: Record<string, string> = {
    'Height': 'Höhe',
    'TerrainHeight': 'Geländehöhe',
    'Latitude': 'Breitengrad',
    'Longitude': 'Längengrad',
    'core:creationdate': 'Erstellungsdatum',
    'gml:id': 'GML ID',
    'gml:name': 'GML Name',
    'Blattnummer': 'Blattnummer',
    'HoeheDach': 'Dachhöhe',
    'HoeheGrund': 'Grundhöhe',
    'NiedrigsteTraufeDesGebaeudes': 'Niedrigste Traufe',
    'bldg:measuredheight': 'Gemessene Höhe',
    'bldg:rooftype': 'Dachtyp',
    'ID': 'ID',
    'Name': 'Name'
  };

  const formatValue = (key: string, value: any): string => {
    // Formatiere den Wert basierend auf dem Eigenschaftstyp
    if (typeof value === 'number') {
      // Höhenangaben mit 2 Dezimalstellen und Einheit
      if (key.toLowerCase().includes('height') || 
          key.toLowerCase().includes('hoehe') || 
          key.toLowerCase().includes('traufe')) {
        return `${value.toFixed(2)} m`;
      }
      // Koordinaten mit 6 Dezimalstellen
      if (key === 'Latitude' || key === 'Longitude') {
        return value.toFixed(6) + '°';
      }
      // Andere Zahlen normal formatieren
      return value.toLocaleString('de-DE');
    }
    // Datumsformatierung
    if (key.includes('date') || key.includes('datum')) {
      try {
        return new Date(value).toLocaleDateString('de-DE');
      } catch {
        return value;
      }
    }
    return value.toString();
  };

  // Timeline-Steuerung
  if (viewer) {
    const timeline = viewer.timeline?.container as HTMLElement;
    const animation = viewer.animation?.container as HTMLElement;
    if (timeline) timeline.style.visibility = showTimeline ? 'visible' : 'hidden';
    if (animation) animation.style.visibility = showTimeline ? 'visible' : 'hidden';
  }

  // Füge Mouse-Over-Effekt hinzu
  useEffect(() => {
    if (!viewer || !selectedTilesetId) return;

    const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);
    
    handler.setInputAction((movement: any) => {
      // Verwende die originale Mausposition
      const scene = viewer.scene;
      const camera = scene.camera;
      
      // Erstelle einen Ray von der Kamera durch den Mauspunkt
      const ray = camera.getPickRay(movement.endPosition);
      
      if (!ray) {
        console.log('❌ Kein gültiger Pick-Ray erstellt');
        return;
      }

      // Debug-Ausgabe für Ray und Kamera
      console.log('📍 Pick Details:', {
        mousePosition: movement.endPosition,
        cameraPosition: camera.position,
        rayDirection: ray.direction,
        rayOrigin: ray.origin
      });

      // Führe den Pick mit dem Ray durch
      const pickedObject = scene.pickFromRay({
        ray: ray,
        scene: scene,
        width: 1,
        height: 1
      });

      // Alternative Pick-Methode als Fallback
      let feature = null;
      if (pickedObject && pickedObject.object instanceof Cesium3DTileFeature) {
        feature = pickedObject.object;
      } else {
        // Fallback auf normales Pick wenn Ray-Pick nichts findet
        const regularPick = scene.pick(movement.endPosition);
        if (regularPick instanceof Cesium3DTileFeature) {
          feature = regularPick;
        }
      }

      const tileset = loadedTilesets.get(selectedTilesetId);
      if (tileset) {
        if (feature) {
          console.log('🎯 Feature gefunden:', {
            method: pickedObject ? 'ray' : 'regular',
            batchId: (feature as any)._batchId
          });
        }
        highlightFeature(feature, tileset);
      }
    }, ScreenSpaceEventType.MOUSE_MOVE);

    return () => {
      if (handler && !handler.isDestroyed()) {
        handler.destroy();
      }
    };
  }, [viewer, selectedTilesetId, highlightFeature, loadedTilesets]);

  return (
    <div className="relative w-full h-full">
      <div id="cesiumContainer" className="w-full h-full" />
      
      {/* Zurück-Button */}
      <button
        onClick={onBack}
        className="absolute top-4 left-4 bg-white p-2 rounded shadow-lg hover:bg-gray-100 z-50 flex items-center gap-2"
        title="Zurück zum Projekt"
      >
        <ArrowLeft size={20} />
        <span>Zurück zum Projekt</span>
      </button>

      {/* Layer Sidebar */}
      {showLayerSidebar && (
        <LayerSidebar
          onClose={onToggleLayerSidebar}
          token={token}
          onLoadAsset={loadAsset}
          loadedAssets={Array.from(loadedTilesets.keys())}
          onUnloadAsset={unloadAsset}
          selectedFeature={selectedFeature}
          onFeaturePropertiesChange={(properties) => {
            if (selectedFeature) {
              setSelectedFeature({
                ...selectedFeature,
                properties: Object.fromEntries(
                  Object.entries(selectedFeature.properties)
                    .filter(([key]) => properties.includes(key))
                )
              });
            }
          }}
          onSettingsClick={(assetId) => {
            const tileset = loadedTilesets.get(assetId);
            if (tileset) {
              // Öffne die Einstellungen für dieses Asset
              onToggleSettings();
              setSelectedTilesetId(assetId);
            }
          }}
        />
      )}

      {/* Settings Sidebar */}
      {showSettings && selectedTilesetId && (
        <div className="absolute top-0 right-80 h-full w-80 bg-white shadow-lg z-50 flex flex-col">
          <div className="flex justify-between items-center p-4 border-b">
            <h2 className="text-lg font-semibold">Asset Einstellungen</h2>
            <button 
              onClick={onToggleSettings}
              className="text-gray-500 hover:text-gray-700"
            >
              <X size={20} />
            </button>
          </div>
          <div className="p-4 space-y-4">
            <div>
              <h3 className="font-medium mb-2">Darstellung</h3>
              <div className="space-y-2">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={showTimeline}
                    onChange={(e) => {
                      setShowTimeline(e.target.checked);
                      if (viewer) {
                        viewer.timeline.container.style.visibility = e.target.checked ? 'visible' : 'hidden';
                        viewer.animation.container.style.visibility = e.target.checked ? 'visible' : 'hidden';
                      }
                    }}
                    className="rounded"
                  />
                  <span>Timeline anzeigen</span>
                </label>
                <div className="space-y-2">
                  <label className="block">
                    <span className="text-sm text-gray-600">Detailgrad</span>
                    <select
                      className="mt-1 block w-full rounded border-gray-300"
                      value={loadedTilesets.get(selectedTilesetId)?.maximumScreenSpaceError || 8}
                      onChange={(e) => {
                        const tileset = loadedTilesets.get(selectedTilesetId);
                        if (tileset) {
                          const newError = Number(e.target.value);
                          tileset.maximumScreenSpaceError = newError;
                          
                          // Aktualisiere auch andere relevante Einstellungen
                          tileset.maximumMemoryUsage = newError <= 4 ? 2048 : 1024;
                          tileset.preloadFlightDestinations = newError <= 8;
                          tileset.preferLeaves = newError <= 4;
                          
                          // Aktualisiere den State
                          setLoadedTilesets(new Map(loadedTilesets));
                        }
                      }}
                    >
                      <option value="16">Niedrig (bessere Performance)</option>
                      <option value="8">Mittel</option>
                      <option value="4">Hoch</option>
                      <option value="2">Sehr hoch (beste Qualität)</option>
                    </select>
                  </label>
                  <p className="text-xs text-gray-500 mt-1">
                    Niedrigere Werte bedeuten höhere Qualität, aber können die Performance beeinträchtigen
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading und Error Anzeige */}
      {loadingAssets && (
        <div className="absolute top-4 right-4 bg-white p-2 rounded shadow">
          Lade Asset...
        </div>
      )}
      {error && (
        <div className="absolute top-4 right-4 bg-red-100 p-2 rounded shadow">
          {error}
        </div>
      )}

      {/* Feature Info Box */}
      {selectedFeature && selectedTilesetId && (
        <div className="absolute top-20 left-4 bg-white p-4 rounded shadow-lg max-w-md z-50">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-lg font-semibold">
              Objekt Details {selectedFeature.id && `(ID: ${selectedFeature.id})`}
            </h3>
            <div className="flex gap-2">
              <button
                onClick={() => toggleFeatureVisibility(selectedFeature.id!)}
                className="px-3 py-1 text-sm rounded bg-red-500 text-white hover:bg-red-600"
                title="Objekt ein-/ausblenden"
              >
                {hiddenFeatures.some(hidden => 
                  hidden.featureId === selectedFeature.id && 
                  hidden.tilesetId === selectedTilesetId
                ) ? 'Einblenden' : 'Ausblenden'}
              </button>
              <button
                onClick={() => {
                  setSelectedFeature(null);
                  const tileset = loadedTilesets.get(selectedTilesetId);
                  if (tileset) {
                    highlightFeature(null, tileset);
                  }
                }}
                className="text-gray-500 hover:text-gray-700"
              >
                <X size={20} />
              </button>
            </div>
          </div>
          <div className="space-y-4">
            {Object.entries(PROPERTY_GROUPS).map(([groupKey, group]) => {
              const groupProperties = Object.entries(selectedFeature.properties)
                .filter(([key, value]) => 
                  group.properties.includes(key) &&
                  value !== undefined && 
                  value !== null && 
                  value !== '' &&
                  typeof value !== 'object' &&
                  !key.startsWith('_')
                );

              if (groupProperties.length === 0) return null;

              return (
                <div key={groupKey} className="border-t pt-2 first:border-t-0 first:pt-0">
                  <h4 className="font-medium text-gray-700 mb-2">{group.label}</h4>
                  <div className="space-y-1">
                    {groupProperties
                      .sort(([keyA], [keyB]) => keyA.localeCompare(keyB))
                      .map(([key, value]) => (
                        <div key={key} className="flex text-sm">
                          <span className="font-medium w-1/2 text-gray-600">
                            {PROPERTY_TRANSLATIONS[key] || key}:
                          </span>
                          <span className="w-1/2">
                            {formatValue(key, value)}
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              );
            })}
            
            {/* Nicht gruppierte Eigenschaften */}
            {(() => {
              const ungroupedProperties = Object.entries(selectedFeature.properties)
                .filter(([key, value]) => 
                  !Object.values(PROPERTY_GROUPS)
                    .flatMap(group => group.properties)
                    .includes(key) &&
                  value !== undefined && 
                  value !== null && 
                  value !== '' &&
                  typeof value !== 'object' &&
                  !key.startsWith('_')
                );

              if (ungroupedProperties.length === 0) return null;

              return (
                <div className="border-t pt-2">
                  <h4 className="font-medium text-gray-700 mb-2">Weitere Eigenschaften</h4>
                  <div className="space-y-1">
                    {ungroupedProperties
                      .sort(([keyA], [keyB]) => keyA.localeCompare(keyB))
                      .map(([key, value]) => (
                        <div key={key} className="flex text-sm">
                          <span className="font-medium w-1/2 text-gray-600">
                            {PROPERTY_TRANSLATIONS[key] || key}:
                          </span>
                          <span className="w-1/2">
                            {formatValue(key, value)}
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
      )}
    </div>
  );
});

CesiumViewerComponent.displayName = 'CesiumViewerComponent';

export default CesiumViewerComponent; 