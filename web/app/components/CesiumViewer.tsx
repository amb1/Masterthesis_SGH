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
  Cartesian2
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
    if (!tileset) return;

    try {
      // Erstelle einen Stil, der versteckte Features berücksichtigt
      const styleConditions: [string, string][] = [];
      
      // Füge Bedingungen für versteckte Features hinzu
      hiddenFeatures.forEach(hidden => {
        if (hidden.tilesetId === selectedTilesetId) {
          styleConditions.push([
            `\${id} === '${hidden.featureId}' || \${gmlid} === '${hidden.featureId}' || \${fid} === '${hidden.featureId}'`, 
            'color("transparent", 0.0)'
          ]);
        }
      });

      // Füge Bedingung für das ausgewählte Feature hinzu
      if (feature) {
        const featureId = feature.getProperty('id') || 
                         feature.getProperty('gmlid') ||
                         feature.getProperty('fid');
        
        styleConditions.push([
          `\${id} === '${featureId}' || \${gmlid} === '${featureId}' || \${fid} === '${featureId}'`, 
          'color("yellow", 1.0)'
        ]);
      }

      // Füge Standardfarbe für alle anderen Features hinzu
      styleConditions.push(['true', 'color("white", 1.0)']);

      const style = new Cesium3DTileStyle({
        color: {
          conditions: styleConditions
        },
        show: {
          conditions: [
            ...hiddenFeatures
              .filter(hidden => hidden.tilesetId === selectedTilesetId)
              .map(hidden => [
                `\${id} === '${hidden.featureId}' || \${gmlid} === '${hidden.featureId}' || \${fid} === '${hidden.featureId}'`,
                false
              ]),
            ['true', true]
          ]
        }
      });

      tileset.style = style;
    } catch (err) {
      console.error('Fehler beim Hervorheben des Features:', err);
    }
  }, [hiddenFeatures, selectedTilesetId]);

  const handleFeatureClick = useCallback(async (movement: any) => {
    if (!viewer || !selectedTilesetId) return;

    const scene = viewer.scene;
    const pickedObject = scene.pick(movement.position);

    if (pickedObject instanceof Cesium3DTileFeature) {
      const properties: Record<string, any> = {};
      
      try {
        // Debug: Zeige das komplette Feature-Objekt
        console.log('Picked Object:', pickedObject);

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

        // Versuche den batchId zu bekommen und die entsprechenden Features
        const batchId = (pickedObject as any)._batchId;
        console.log('Batch ID:', batchId);
        
        if (batchTable && batchId !== undefined) {
          const feature = batchTable._features[batchId];
          console.log('Feature from Batch Table:', feature);
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

      const tileset = await Cesium3DTileset.fromIonAssetId(assetId);
      
      // Verbesserte Darstellung für 3D-Gebäude
      tileset.maximumScreenSpaceError = 8; // Höhere Detailgenauigkeit
      
      // Optimierte Darstellungseinstellungen
      tileset.preloadWhenHidden = true;
      tileset.loadSiblings = true;
      tileset.cullRequestsWhileMoving = true;
      tileset.cullRequestsWhileMovingMultiplier = 0.5;

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

      await viewer.zoomTo(tileset, new HeadingPitchRange(0, -0.5, 0));

      const extras = tileset.asset.extras;
      if (extras?.ion?.defaultStyle) {
        tileset.style = new Cesium3DTileStyle(extras.ion.defaultStyle);
      }

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
        />
      )}

      {/* Settings Sidebar */}
      {showSettings && (
        <div className="absolute top-0 right-0 h-full w-80 bg-white shadow-lg z-50 flex flex-col">
          <div className="flex justify-between items-center p-4 border-b">
            <h2 className="text-lg font-semibold">Einstellungen</h2>
            <button 
              onClick={onToggleSettings}
              className="text-gray-500 hover:text-gray-700"
            >
              <X size={20} />
            </button>
          </div>
          <div className="p-4 space-y-4">
            <div className="flex items-center justify-between">
              <span>Timeline anzeigen</span>
              <button
                onClick={() => setShowTimeline(!showTimeline)}
                className={`px-3 py-1 rounded ${
                  showTimeline ? 'bg-blue-500 text-white' : 'bg-gray-200'
                }`}
              >
                {showTimeline ? 'An' : 'Aus'}
              </button>
            </div>
            {/* Weitere Einstellungen hier */}
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
          <div className="space-y-2">
            {Object.entries(selectedFeature.properties)
              .filter(([key, value]) => 
                value !== undefined && 
                value !== null && 
                value !== '' &&
                typeof value !== 'object' &&
                !key.startsWith('_') // Ignoriere interne Properties
              )
              .sort(([keyA], [keyB]) => keyA.localeCompare(keyB)) // Sortiere alphabetisch
              .map(([key, value]) => (
                <div key={key} className="flex">
                  <span className="font-medium w-1/3 text-gray-600">
                    {key.split(/(?=[A-Z])|_/).map(word => 
                      word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
                    ).join(' ')}:
                  </span>
                  <span className="w-2/3">
                    {typeof value === 'number' ? value.toLocaleString('de-DE') : value.toString()}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
});

CesiumViewerComponent.displayName = 'CesiumViewerComponent';

export default CesiumViewerComponent; 