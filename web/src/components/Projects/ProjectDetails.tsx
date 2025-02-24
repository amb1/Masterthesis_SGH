import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { createClient } from '@supabase/supabase-js';
import { toast } from 'react-hot-toast';
import * as Cesium from 'cesium';
import "cesium/Build/Cesium/Widgets/widgets.css";
import { SearchBar } from '../Search/SearchBar';
import { Earth, Building2, MapPin } from 'lucide-react'; // Icons importieren

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

export function ProjectDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [projectName, setProjectName] = useState('');
  const [cesiumToken, setCesiumToken] = useState<string | null>(null);
  const [viewer, setViewer] = useState<Cesium.Viewer | null>(null);
  const [layers, setLayers] = useState([
    { id: 'terrain', name: 'Gelände', visible: true },
    { id: 'buildings', name: 'Gebäude', visible: true },
    { id: 'imagery', name: 'Luftbild', visible: true }
  ]);
  const [availableAssets, setAvailableAssets] = useState([
    { 
      id: 'globe', 
      name: 'Globe', 
      icon: Earth, 
      visible: true,
      position: { lon: 16.37, lat: 48.21, height: 10000000 } // Globale Ansicht
    },
    { 
      id: 'osmBuildings', 
      name: 'OSM Buildings', 
      icon: Building2, 
      visible: true,
      position: { lon: 16.37, lat: 48.21, height: 2000 } // Näher an den Gebäuden
    },
    { 
      id: 'projectBoundary', 
      name: 'Projektgrenze', 
      icon: MapPin, 
      visible: true,
      position: { lon: 16.37, lat: 48.21, height: 5000 } // Mittlere Höhe
    }
  ]);
  const [drawingMode, setDrawingMode] = useState(false);
  const [projectBoundary, setProjectBoundary] = useState<Cesium.Entity | null>(null);

  useEffect(() => {
    const loadProject = async () => {
      if (!id) return;

      try {
        const { data, error } = await supabase
          .from('projects')
          .select('*')
          .eq('id', id)
          .single();

        console.log('Geladene Projektdaten:', data);
        console.log('Fehler beim Laden:', error);

        if (error) throw error;
        
        if (data) {
          setProjectName(data.name);
          const token = data.cesium_token || import.meta.env.VITE_CESIUM_ION_ACCESS_TOKEN;
          if (!token) {
            throw new Error('Kein Cesium Token verfügbar');
          }
          setCesiumToken(token);
        } else {
          throw new Error('Projekt nicht gefunden');
        }
      } catch (error) {
        console.error('Fehler beim Laden des Projekts:', error);
        toast.error('Fehler beim Laden des Projekts');
      }
    };

    loadProject();
  }, [id]);

  useEffect(() => {
    const initCesium = async () => {
      if (!cesiumToken) return;

      try {
        Cesium.Ion.defaultAccessToken = cesiumToken;
        
        const cesiumViewer = new Cesium.Viewer('cesiumContainer', {
          baseLayerPicker: false,
          geocoder: false,
          homeButton: false,
          sceneModePicker: false,
          navigationHelpButton: false,
          animation: false,
          timeline: false,
          fullscreenButton: false,
          scene3DOnly: true,
          // Bing Maps als Basemap
          imageryProvider: new Cesium.BingMapsImageryProvider({
            url: 'https://dev.virtualearth.net',
            mapStyle: Cesium.BingMapsStyle.AERIAL_WITH_LABELS
          })
        });

        // Globe Konfiguration
        cesiumViewer.scene.globe.enableLighting = false;
        cesiumViewer.scene.globe.atmosphereEnabled = false;
        cesiumViewer.scene.globe.showGroundAtmosphere = false;
        
        // Terrain konfigurieren
        const terrainProvider = await Cesium.CesiumTerrainProvider.fromIonAssetId(1);
        cesiumViewer.terrainProvider = terrainProvider;

        // OSM Buildings
        const osmBuildingsTileset = await Cesium.Cesium3DTileset.fromIonAssetId(96188, {
          maximumScreenSpaceError: 16,
          maximumMemoryUsage: 512
        });
        
        osmBuildingsTileset.style = new Cesium.Cesium3DTileStyle({
          color: 'color("white", 1.0)',
          show: true
        });

        cesiumViewer.scene.primitives.add(osmBuildingsTileset);

        // Kamera-Position
        cesiumViewer.camera.setView({
          destination: Cesium.Cartesian3.fromDegrees(16.37, 48.21, 2000),
          orientation: {
            heading: 0.0,
            pitch: -Cesium.Math.PI_OVER_FOUR,
            roll: 0.0
          }
        });

        setViewer(cesiumViewer);
      } catch (error) {
        console.error('Fehler beim Initialisieren des Cesium Viewers:', error);
        toast.error('Fehler beim Laden der 3D-Ansicht');
      }
    };

    initCesium();

    return () => {
      if (viewer && !viewer.isDestroyed()) {
        viewer.destroy();
      }
    };
  }, [cesiumToken]);

  const handleEdit = () => {
    if (!id) return;
    navigate(`/projects/${id}/edit`);
  };

  const handleSearch = (searchResult: any) => {
    if (viewer && searchResult.coordinates) {
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(
          searchResult.coordinates.lon,
          searchResult.coordinates.lat,
          2000
        )
      });
    }
  };

  const handleLayerToggle = (layerId: string) => {
    if (!viewer) return;

    setLayers(prevLayers => prevLayers.map(layer => {
      if (layer.id === layerId) {
        const visible = !layer.visible;
        
        try {
          switch(layerId) {
            case 'terrain':
              // Terrain kann nicht komplett ausgeschaltet werden,
              // stattdessen schalten wir zwischen flach und 3D
              if (visible) {
                viewer.terrainProvider = new Cesium.CesiumTerrainProvider({
                  url: Cesium.IonResource.fromAssetId(1)
                });
              } else {
                viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider();
              }
              break;
            
            case 'buildings':
              // Alle 3D Tileset Primitives finden und togglen
              viewer.scene.primitives._primitives.forEach((primitive: any) => {
                if (primitive instanceof Cesium.Cesium3DTileset) {
                  primitive.show = visible;
                }
              });
              break;
            
            case 'imagery':
              // Basis-Layer (Luftbild) togglen
              viewer.imageryLayers.get(0).show = visible;
              break;
          }
          
          return { ...layer, visible };
        } catch (error) {
          console.error(`Fehler beim Umschalten von Layer ${layerId}:`, error);
          return layer;
        }
      }
      return layer;
    }));
  };

  const zoomToAsset = (asset: typeof availableAssets[0]) => {
    if (!viewer) return;

    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(
        asset.position.lon,
        asset.position.lat,
        asset.position.height
      ),
      orientation: {
        heading: 0.0,
        pitch: -Cesium.Math.PI_OVER_FOUR,
        roll: 0.0
      },
      duration: 2 // Sekunden für die Animation
    });
  };

  const toggleAsset = async (assetId: string) => {
    if (!viewer) return;

    try {
      switch (assetId) {
        case 'globe':
          const isGlobeVisible = viewer.scene.globe.show;
          viewer.scene.globe.show = !isGlobeVisible;
          setAvailableAssets(prev => prev.map(a => 
            a.id === 'globe' ? { ...a, visible: !isGlobeVisible } : a
          ));
          break;

        case 'osmBuildings':
          const primitives = viewer.scene.primitives;
          const buildingTileset = primitives._primitives.find(
            (p: any) => p instanceof Cesium.Cesium3DTileset
          );
          
          if (buildingTileset) {
            const isVisible = buildingTileset.show;
            buildingTileset.show = !isVisible;
            setAvailableAssets(prev => prev.map(a => 
              a.id === 'osmBuildings' ? { ...a, visible: !isVisible } : a
            ));
          }
          break;

        case 'projectBoundary':
          // Projektgrenze Toggle-Logik hier...
          break;
      }
    } catch (error) {
      console.error(`Fehler beim Togglen von Asset ${assetId}:`, error);
      toast.error('Fehler beim Umschalten des Assets');
    }
  };

  // Zeichenfunktionen
  const startDrawing = () => {
    if (!viewer) return;

    setDrawingMode(true);
    const positions: Cesium.Cartesian3[] = [];
    let polyline: Cesium.Entity | null = null;
    let polygon: Cesium.Entity | null = null;

    // Mouse-Handler für das Zeichnen
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);

    // Linker Mausklick: Punkt hinzufügen
    handler.setInputAction((click: any) => {
      const cartesian = viewer.scene.pickPosition(click.position);
      if (cartesian) {
        positions.push(cartesian);

        if (positions.length === 1) {
          // Erste Position: Polyline erstellen
          polyline = viewer.entities.add({
            polyline: {
              positions: new Cesium.CallbackProperty(() => positions, false),
              width: 2,
              material: Cesium.Color.YELLOW
            }
          });
        }
        if (positions.length > 2) {
          // Ab 3 Punkten: Polygon erstellen/aktualisieren
          if (!polygon) {
            polygon = viewer.entities.add({
              polygon: {
                hierarchy: new Cesium.CallbackProperty(() => ({
                  positions: [...positions, positions[0]]
                }), false),
                material: Cesium.Color.YELLOW.withAlpha(0.5),
                outline: true,
                outlineColor: Cesium.Color.YELLOW
              }
            });
          }
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    // Rechter Mausklick: Zeichnung abschließen
    handler.setInputAction(() => {
      handler.destroy();
      if (polyline) {
        viewer.entities.remove(polyline);
      }
      if (positions.length > 2) {
        // Finales Polygon erstellen
        if (projectBoundary) {
          viewer.entities.remove(projectBoundary);
        }
        const finalPolygon = viewer.entities.add({
          polygon: {
            hierarchy: new Cesium.PolygonHierarchy(positions),
            material: Cesium.Color.GREEN.withAlpha(0.5),
            outline: true,
            outlineColor: Cesium.Color.GREEN
          }
        });
        setProjectBoundary(finalPolygon);
        
        // Koordinaten in der Datenbank speichern
        saveProjectBoundary(positions);
      }
      setDrawingMode(false);
    }, Cesium.ScreenSpaceEventType.RIGHT_CLICK);
  };

  const saveProjectBoundary = async (positions: Cesium.Cartesian3[]) => {
    if (!id) return;

    // Konvertiere Cartesian3 zu [lon, lat] Format
    const coordinates = positions.map(pos => {
      const cartographic = Cesium.Cartographic.fromCartesian(pos);
      return [
        Cesium.Math.toDegrees(cartographic.longitude),
        Cesium.Math.toDegrees(cartographic.latitude)
      ];
    });

    try {
      const { error } = await supabase
        .from('project_boundaries')
        .upsert({
          project_id: id,
          polygon: {
            type: 'Polygon',
            coordinates: [coordinates]  // GeoJSON Format
          }
        });

      if (error) throw error;
      toast.success('Projektgrenze gespeichert');
    } catch (error) {
      console.error('Fehler beim Speichern der Projektgrenze:', error);
      toast.error('Fehler beim Speichern der Projektgrenze');
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">{projectName}</h1>
      </div>

      <div className="w-full max-w-2xl">
        <SearchBar onSearch={handleSearch} />
      </div>
      
      <div className="relative border rounded-lg overflow-hidden bg-gray-100" style={{ height: '600px' }}>
        <div id="cesiumContainer" className="absolute inset-0" />
        
        {/* Linke Sidebar */}
        <div className="absolute top-4 left-4 flex flex-col gap-4 z-10">
          <div className="bg-white p-4 rounded-lg shadow-lg">
            <h3 className="font-semibold mb-4">Verfügbare Assets</h3>
            <div className="space-y-3">
              {availableAssets.map(asset => {
                const Icon = asset.icon;
                return (
                  <div key={asset.id} className="flex items-center gap-2">
                    <button
                      onClick={() => toggleAsset(asset.id)}
                      className={`flex items-center gap-2 flex-grow text-left p-2 rounded hover:bg-gray-50 ${
                        asset.visible ? 'text-gray-800' : 'text-gray-400'
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                      <span>{asset.name}</span>
                    </button>
                    <button
                      onClick={() => zoomToAsset(asset)}
                      className="p-2 text-blue-500 hover:text-blue-600 hover:bg-gray-50 rounded"
                      title={`Zoom zu ${asset.name}`}
                    >
                      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    </button>
                  </div>
                );
              })}
              <button
                onClick={startDrawing}
                disabled={drawingMode}
                className={`flex items-center gap-2 w-full text-left p-2 rounded hover:bg-gray-50 ${
                  drawingMode ? 'text-gray-400' : 'text-gray-800'
                }`}
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                </svg>
                Projektgrenze zeichnen
              </button>
            </div>
          </div>
        </div>

        {/* Rechte obere Ecke */}
        <div className="absolute top-4 right-4 z-10">
          <button 
            onClick={handleEdit}
            className="bg-white px-4 py-2 rounded-md shadow-lg hover:bg-gray-50 transition-colors"
          >
            Bearbeiten
          </button>
        </div>
      </div>
    </div>
  );
}