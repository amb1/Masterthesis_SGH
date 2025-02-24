import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as Cesium from 'cesium';
import "cesium/Build/Cesium/Widgets/widgets.css";
import { Layers, Eye, EyeOff, Globe2, Building2, Box } from 'lucide-react';
import { createClient } from '@supabase/supabase-js';
import { fetchViennaWFS } from '../../services/viennaService';
import { toast } from 'react-hot-toast';
import type { Tables } from '@/lib/database.types';
import { BoundaryService } from '@/services/boundaryService';
import { logger } from '@/utils/logger';

interface Layer {
  id: string;
  name: string;
  enabled: boolean;
  layer: Cesium.Cesium3DTileset | Cesium.Globe | null;
  icon: React.ReactNode;
  zoomTo: () => void;
  isLoading: boolean;
}

type ProjectBoundary = Tables['project_boundaries']['Row'];

interface CesiumViewerProps {
  projectId: string;
  token: string;
  viewerOptions?: Cesium.Viewer.ConstructorOptions;
  onSaveBoundingBox?: (bbox: {
    minLon: number;
    minLat: number;
    maxLon: number;
    maxLat: number;
  }) => Promise<void>;
}

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

export function CesiumViewer({ projectId, token, viewerOptions, onSaveBoundingBox }: CesiumViewerProps) {
  const viewerContainer = useRef<HTMLDivElement>(null);
  const viewer = useRef<Cesium.Viewer | null>(null);
  const [showSidebar, setShowSidebar] = useState(true);
  const [isDrawing, setIsDrawing] = useState(false);
  const [positions, setPositions] = useState<Cesium.Cartesian3[]>([]);
  const [layers, setLayers] = useState<Layer[]>([
    { 
      id: 'globe', 
      name: 'Globe', 
      enabled: true, 
      layer: null,
      isLoading: false,
      icon: <Globe2 className="h-4 w-4" />,
      zoomTo: () => {
        if (viewer.current) {
          viewer.current.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(15, 45, 20000000),
            duration: 1.5
          });
        }
      }
    },
    { 
      id: 'osmBuildings', 
      name: 'OSM Buildings', 
      enabled: true, 
      layer: null,
      isLoading: false,
      icon: <Building2 className="h-4 w-4" />,
      zoomTo: () => {
        if (viewer.current) {
          viewer.current.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(16.37, 48.21, 2000),
            orientation: {
              heading: 0.0,
              pitch: -Cesium.Math.PI_OVER_FOUR,
              roll: 0.0
            },
            duration: 1.5
          });
        }
      }
    }
  ]);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [drawingEntity, setDrawingEntity] = useState<Cesium.Entity | null>(null);
  const [points, setPoints] = useState<Cesium.Entity[]>([]);
  const [viennaDataLoaded, setViennaDataLoaded] = useState(false);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [hasProjectBoundary, setHasProjectBoundary] = useState(false);
  const [isEditingBoundary, setIsEditingBoundary] = useState(false);
  const [editablePoints, setEditablePoints] = useState<Cesium.Entity[]>([]);
  const [osmBuildingsLoaded, setOsmBuildingsLoaded] = useState(false);

  useEffect(() => {
    if (!viewerContainer.current) return;

    const initViewer = async () => {
      try {
        Cesium.Ion.defaultAccessToken = token;

        // Viewer mit angepassten Optionen initialisieren
        viewer.current = new Cesium.Viewer(viewerContainer.current, {
          ...viewerOptions,
          geocoder: false, // Geocoder komplett deaktivieren
          baseLayerPicker: false,
          homeButton: false,
          sceneModePicker: false,
          navigationHelpButton: false,
          animation: false,
          timeline: false,
          fullscreenButton: false,
          scene3DOnly: true
        });

        const scene = viewer.current.scene;
        scene.globe.enableLighting = false;
        scene.globe.baseColor = Cesium.Color.WHITE;

        // Globe-Referenz speichern
        setLayers(prev => prev.map(layer => {
          if (layer.id === 'globe') {
            return { ...layer, layer: scene.globe };
          }
          return layer;
        }));

        // OSM Buildings laden
        const osmBuildingsTileset = await Cesium.Cesium3DTileset.fromIonAssetId(96188);
        osmBuildingsTileset.style = new Cesium.Cesium3DTileStyle({
          color: 'color("white", 1.0)',
          show: true
        });

        const osmBuildingsLayer = scene.primitives.add(osmBuildingsTileset);
        
        setLayers(prev => prev.map(layer => {
          if (layer.id === 'osmBuildings') {
            return { ...layer, layer: osmBuildingsLayer };
          }
          return layer;
        }));

        // Initiale Kameraposition (Wien)
        viewer.current.camera.setView({
          destination: Cesium.Cartesian3.fromDegrees(16.37, 48.21, 2000),
          orientation: {
            heading: 0.0,
            pitch: -Cesium.Math.PI_OVER_FOUR,
            roll: 0.0
          }
        });

      } catch (error) {
        console.error('Fehler beim Initialisieren des Viewers:', error);
      }
    };

    initViewer();

    return () => {
      if (viewer.current) {
        viewer.current.destroy();
        viewer.current = null;
      }
    };
  }, [token, viewerOptions]);

  // Laden existierender Grenzen
  useEffect(() => {
    if (!projectId) {
      logger.error('Keine Project ID vorhanden');
      return;
    }
    
    const loadBoundary = async () => {
      try {
        const { data, error } = await supabase
          .from('project_boundaries')
          .select('*')
          .eq('project_id', projectId)
          .single();

        if (error && error.code !== 'PGRST116') throw error;
        
        if (data && !isDrawing) {
          setHasProjectBoundary(true);
          displayBoundary(data);
          
          // Projektgrenzen Layer hinzufügen
          setLayers(prev => {
            if (!prev.find(layer => layer.id === 'projectBoundary')) {
              return [...prev, {
                id: 'projectBoundary',
                name: 'Projektgrenze',
                enabled: true,
                layer: null, // wird beim displayBoundary gesetzt
                icon: <Box className="h-4 w-4" />
              }];
            }
            return prev;
          });
        }
      } catch (error) {
        logger.error('Fehler beim Laden der Grenzen:', error);
      }
    };

    loadBoundary();
  }, [projectId, isDrawing]);

  // Projektgrenzen Layer hinzufügen
  const addBoundaryLayer = (boundary: ProjectBoundary) => {
    const boundaryLayer: Layer = {
      id: 'projectBoundary',
      name: 'Projektgrenze',
      enabled: true,
      layer: null,
      icon: <Box className="h-4 w-4" />,
      zoomTo: () => {
        if (viewer.current) {
          viewer.current.camera.flyTo({
            destination: Cesium.Rectangle.fromDegrees(
              boundary.min_lon,
              boundary.min_lat,
              boundary.max_lon,
              boundary.max_lat
            ),
            orientation: {
              heading: 0.0,
              pitch: -Cesium.Math.PI_OVER_FOUR,
              roll: 0.0
            }
          });
        }
      }
    };

    setLayers(prev => {
      const existingIndex = prev.findIndex(l => l.id === 'projectBoundary');
      if (existingIndex >= 0) {
        const newLayers = [...prev];
        newLayers[existingIndex] = boundaryLayer;
        return newLayers;
      }
      return [...prev, boundaryLayer];
    });
  };

  // Grenzen anzeigen
  const displayBoundary = (boundary: ProjectBoundary) => {
    if (!viewer.current) return;
    
    viewer.current.entities.removeAll();
    const coordinates = boundary.polygon.map((coord: number[]) =>
      Cesium.Cartesian3.fromDegrees(coord[0], coord[1])
    );

    viewer.current.entities.add({
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(coordinates),
        material: Cesium.Color.BLUE.withAlpha(0.3),
        outline: true,
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
      }
    });

    addBoundaryLayer(boundary);
  };

  // Zeichenfunktion überarbeitet
  const handleClick = useCallback((event: any) => {
    if (!isDrawing || !viewer.current) return;

    // Hole die aktuelle Mausposition
    const canvas = viewer.current.scene.canvas;
    const rect = canvas.getBoundingClientRect();
    const windowPosition = new Cesium.Cartesian2(
      event.clientX - rect.left,
      event.clientY - rect.top
    );

    // Versuche einen Pick auf der Oberfläche mit Ray Casting
    const ray = viewer.current.camera.getPickRay(windowPosition);
    const cartesian = ray ? viewer.current.scene.globe.pick(ray, viewer.current.scene) : undefined;

    if (Cesium.defined(cartesian)) {
      // Füge einen Punkt hinzu
      const point = viewer.current.entities.add({
        position: cartesian,
        point: {
          pixelSize: 10,
          color: Cesium.Color.WHITE,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
        }
      });
      
      setPoints(prev => [...prev, point]);
      setPositions(prev => [...prev, cartesian]);

      // Aktualisiere das Polygon wenn mindestens 3 Punkte vorhanden sind
      if (positions.length >= 2) {
        if (drawingEntity) {
          viewer.current.entities.remove(drawingEntity);
        }

        const polygon = viewer.current.entities.add({
          polygon: {
            hierarchy: new Cesium.PolygonHierarchy([...positions, cartesian]),
            material: Cesium.Color.WHITE.withAlpha(0.5),
            outline: true,
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 2,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
          }
        });

        setDrawingEntity(polygon);
      }
    }
  }, [isDrawing, positions, drawingEntity]);

  // Rechtsklick Handler
  const handleRightClick = useCallback((event: MouseEvent) => {
    if (!isDrawing) return;
    event.preventDefault();
    
    if (positions.length < 3) {
      toast.error('Mindestens 3 Punkte erforderlich');
      return;
    }
    finishDrawing();
  }, [isDrawing, positions]);

  // Event Listener für Rechtsklick
  useEffect(() => {
    if (!viewerContainer.current) return;

    const container = viewerContainer.current;
    container.addEventListener('click', handleClick);
    container.addEventListener('contextmenu', handleRightClick);

    return () => {
      container.removeEventListener('click', handleClick);
      container.removeEventListener('contextmenu', handleRightClick);
    };
  }, [handleClick, handleRightClick]);

  // Zeichnen beenden
  const finishDrawing = useCallback(() => {
    if (positions.length < 3) {
      toast.error('Mindestens 3 Punkte erforderlich');
      return;
    }

    // Polygon schließen
    const closedPositions = [...positions, positions[0]];
    setPositions(closedPositions);
    setIsDrawing(false);
    setShowSaveDialog(true);
  }, [positions]);

  // Zeichnen zurücksetzen
  const resetDrawing = useCallback(() => {
    if (!viewer.current) return;
    
    viewer.current.entities.removeAll();
    setPositions([]);
    setPoints([]);
    setDrawingEntity(null);
    setIsDrawing(false);
  }, []);

  // Funktion zum Umschalten in die Vogelperspektive
  const switchToTopView = useCallback(() => {
    if (!viewer.current) return;
    
    const camera = viewer.current.camera;
    const currentPosition = camera.position;
    const currentCartographic = Cesium.Cartographic.fromCartesian(currentPosition);
    
    // Aktuelle Längen- und Breitengrade beibehalten, nur Höhe und Ausrichtung ändern
    camera.flyTo({
      destination: Cesium.Cartesian3.fromRadians(
        currentCartographic.longitude,
        currentCartographic.latitude,
        currentCartographic.height
      ),
      orientation: {
        heading: 0.0, // Norden ist oben
        pitch: Cesium.Math.toRadians(-90), // Direkt nach unten schauen
        roll: 0.0
      },
      duration: 1.5 // Dauer der Animation in Sekunden
    });
  }, []);

  // Zeichnen starten
  const startDrawing = useCallback(() => {
    if (!viewer.current) return;

    // Bestehende Entities löschen
    viewer.current.entities.removeAll();
    
    // States zurücksetzen
    setPositions([]);
    setPoints([]);
    setDrawingEntity(null);
    setIsDrawing(true);
    setIsEditingBoundary(true);
    
    // Kamera ausrichten
    switchToTopView();
  }, [switchToTopView]);

  const loadViennaData = useCallback(async (bbox: {
    minLon: number;
    minLat: number;
    maxLon: number;
    maxLat: number;
  }) => {
    try {
      // Bestehende Entities löschen
      viewer.current?.entities.removeAll();

      // FMZKBKMOGD laden (Flächenmehrzweckkarte Bauklassen)
      const bauklassenData = await fetchViennaWFS(bbox, 'FMZKBKMOGD');
      
      // GEBAEUDETYPOGD laden (Gebäudetypen)
      const gebaeudetypenData = await fetchViennaWFS(bbox, 'GEBAEUDETYPOGD');

      if (viewer.current) {
        // Bauklassen visualisieren
        bauklassenData.features.forEach((feature: any) => {
          const coordinates = feature.geometry.coordinates[0].map((coord: number[]) =>
            Cesium.Cartesian3.fromDegrees(coord[0], coord[1])
          );

          viewer.current?.entities.add({
            polygon: {
              hierarchy: new Cesium.PolygonHierarchy(coordinates),
              material: Cesium.Color.YELLOW.withAlpha(0.3),
              outline: true,
              outlineColor: Cesium.Color.WHITE,
              outlineWidth: 2,
              heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
            },
            properties: feature.properties
          });
        });

        // Gebäudetypen visualisieren mit Pickable-Option
        gebaeudetypenData.features.forEach((feature: any) => {
          const coordinates = feature.geometry.coordinates[0].map((coord: number[]) =>
            Cesium.Cartesian3.fromDegrees(coord[0], coord[1])
          );

          viewer.current?.entities.add({
            polygon: {
              hierarchy: new Cesium.PolygonHierarchy(coordinates),
              material: Cesium.Color.BLUE.withAlpha(0.3),
              outline: true,
              outlineColor: Cesium.Color.WHITE,
              outlineWidth: 2,
              heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
            },
            properties: feature.properties
          });
        });
      }
    } catch (error) {
      logger.error('Fehler beim Laden der Wien Daten:', error);
    }
  }, []);

  // Speichern der gezeichneten Grenzen
  const saveProjectBoundary = async () => {
    if (!projectId) {
      toast.error('Keine Projekt-ID vorhanden');
      return;
    }

    if (positions.length < 3) {
      toast.error('Mindestens 3 Punkte erforderlich');
      return;
    }

    try {
      const coordinates = positions.map(position => {
        const cartographic = Cesium.Cartographic.fromCartesian(position);
        return [
          Cesium.Math.toDegrees(cartographic.longitude),
          Cesium.Math.toDegrees(cartographic.latitude)
        ];
      });

      const lons = coordinates.map(coord => coord[0]);
      const lats = coordinates.map(coord => coord[1]);

      // Zuerst alte Grenzen löschen
      await supabase
        .from('project_boundaries')
        .delete()
        .eq('project_id', projectId);

      // Neue Grenzen speichern
      const { error } = await supabase
        .from('project_boundaries')
        .insert({
          project_id: projectId,
          min_lon: Math.min(...lons),
          min_lat: Math.min(...lats),
          max_lon: Math.max(...lons),
          max_lat: Math.max(...lats),
          polygon: coordinates
        });

      if (error) throw error;

      setHasProjectBoundary(true);
      setIsDrawing(false);
      setShowSaveDialog(false);
      
      // Grenzen neu laden
      const { data: newBoundary } = await supabase
        .from('project_boundaries')
        .select('*')
        .eq('project_id', projectId)
        .single();

      if (newBoundary) {
        displayBoundary(newBoundary);
        // Layer aktualisieren
        setLayers(prev => {
          if (!prev.find(layer => layer.id === 'projectBoundary')) {
            return [...prev, {
              id: 'projectBoundary',
              name: 'Projektgrenze',
              enabled: true,
              layer: null,
              icon: <Box className="h-4 w-4" />
            }];
          }
          return prev;
        });
      }

      toast.success('Projektgrenzen wurden gespeichert');
    } catch (error) {
      logger.error('Fehler beim Speichern:', error);
      toast.error('Fehler beim Speichern der Projektgrenzen');
    }
  };

  // Layer Toggle Funktion
  const toggleLayer = useCallback(async (layerId: string) => {
    if (!viewer.current) return;

    setLayers(prev => prev.map(layer => {
      if (layer.id === layerId) {
        if (layer.layer instanceof Cesium.Cesium3DTileset) {
          layer.layer.show = !layer.enabled;
        } else if (layer.id === 'globe') {
          viewer.current!.scene.globe.show = !layer.enabled;
        }
        return { ...layer, enabled: !layer.enabled };
      }
      return layer;
    }));
  }, []);

  // Funktion zum Starten der Bearbeitung
  const startEditing = useCallback(() => {
    setIsEditingBoundary(true);
    setIsDrawing(true);
    viewer.current?.entities.removeAll();
    setPositions([]);
    setPoints([]);
    switchToTopView();
  }, [switchToTopView]);

  // Funktion zum Verschieben der Eckpunkte
  const handlePointDrag = useCallback((entity: Cesium.Entity, index: number) => {
    if (!viewer.current || !entity.position) return;

    const position = entity.position.getValue(Cesium.JulianDate.now());
    if (position) {
      const newPositions = [...positions];
      newPositions[index] = position;
      setPositions(newPositions);

      // Polygon aktualisieren
      if (drawingEntity) {
        viewer.current.entities.remove(drawingEntity);
      }

      const polygon = viewer.current.entities.add({
        polygon: {
          hierarchy: new Cesium.PolygonHierarchy(newPositions),
          material: Cesium.Color.BLUE.withAlpha(0.3),
          outline: true,
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
        }
      });

      setDrawingEntity(polygon);
    }
  }, [positions, drawingEntity]);

  // Event Handler für Kamera-Änderungen
  const handleCameraChange = useCallback(() => {
    if (!viewer.current || osmBuildingsLoaded) return;

    const height = viewer.current.camera.positionCartographic.height;
    const LOAD_BUILDINGS_HEIGHT = 30000; // Meter - anpassen nach Bedarf

    if (height < LOAD_BUILDINGS_HEIGHT) {
      loadOsmBuildings();
    }
  }, [osmBuildingsLoaded]);

  // OSM Buildings Laden in separate Funktion auslagern
  const loadOsmBuildings = async () => {
    if (!viewer.current) return;
    
    setLayers(prev => prev.map(layer => 
      layer.id === 'osmBuildings' ? { ...layer, isLoading: true } : layer
    ));

    try {
      const osmBuildingsTileset = await Cesium.Cesium3DTileset.fromIonAssetId(96188, {
        maximumScreenSpaceError: 16, // Reduziert Fragmentierung
        maximumMemoryUsage: 512, // Begrenzt Speichernutzung
        preloadWhenHidden: true, // Lädt Tiles im Hintergrund
        preferLeaves: true // Bevorzugt detailliertere Tiles
      });

      osmBuildingsTileset.style = new Cesium.Cesium3DTileStyle({
        color: 'color("white", 1.0)',
        show: true
      });

      const osmBuildingsLayer = viewer.current.scene.primitives.add(osmBuildingsTileset);

      setLayers(prev => prev.map(layer => 
        layer.id === 'osmBuildings' 
          ? { ...layer, layer: osmBuildingsLayer, isLoading: false } 
          : layer
      ));

    } catch (error) {
      console.error('Fehler beim Laden der OSM Buildings:', error);
      setLayers(prev => prev.map(layer => 
        layer.id === 'osmBuildings' ? { ...layer, isLoading: false } : layer
      ));
    }
  };

  // Camera Change Event Listener hinzufügen
  useEffect(() => {
    if (!viewer.current) return;

    const cameraListener = viewer.current.camera.changed.addEventListener(handleCameraChange);
    
    return () => {
      cameraListener && cameraListener();
    };
  }, [handleCameraChange]);

  // Zoom zu Projektgrenzen
  const zoomToBoundary = useCallback((boundary: ProjectBoundary) => {
    if (!viewer.current) return;

    const rectangle = Cesium.Rectangle.fromDegrees(
      boundary.min_lon,
      boundary.min_lat,
      boundary.max_lon,
      boundary.max_lat
    );

    viewer.current.camera.flyTo({
      destination: rectangle,
      orientation: {
        heading: 0.0,
        pitch: -Cesium.Math.PI_OVER_FOUR,
        roll: 0.0
      }
    });
  }, []);

  // OSM Buildings Initialisierung
  const initOsmBuildings = async () => {
    if (!viewer.current) return;
    
    setLayers(prev => prev.map(layer => 
      layer.id === 'osmBuildings' ? { ...layer, isLoading: true } : layer
    ));

    try {
      const osmBuildingsTileset = await Cesium.Cesium3DTileset.fromIonAssetId(96188, {
        maximumScreenSpaceError: 16, // Reduziert Fragmentierung
        maximumMemoryUsage: 512, // Begrenzt Speichernutzung
        preloadWhenHidden: true, // Lädt Tiles im Hintergrund
        preferLeaves: true // Bevorzugt detailliertere Tiles
      });

      osmBuildingsTileset.style = new Cesium.Cesium3DTileStyle({
        color: 'color("white", 1.0)',
        show: true
      });

      const osmBuildingsLayer = viewer.current.scene.primitives.add(osmBuildingsTileset);

      setLayers(prev => prev.map(layer => 
        layer.id === 'osmBuildings' 
          ? { ...layer, layer: osmBuildingsLayer, isLoading: false } 
          : layer
      ));

    } catch (error) {
      console.error('Fehler beim Laden der OSM Buildings:', error);
      setLayers(prev => prev.map(layer => 
        layer.id === 'osmBuildings' ? { ...layer, isLoading: false } : layer
      ));
    }
  };

  // Im useEffect aufrufen
  useEffect(() => {
    if (!projectId || !viewer.current) return;
    initOsmBuildings();
  }, [projectId]);

  // Asset zum Projekt hinzufügen
  const addAssetToProject = async (assetId: number) => {
    if (!projectId) return;

    try {
      const { error } = await supabase
        .from('project_assets')
        .upsert({
          project_id: projectId,
          asset_id: assetId,
          type: 'cesium_ion'
        });

      if (error) throw error;
      toast.success('Asset wurde zum Projekt hinzugefügt');
    } catch (error) {
      console.error('Fehler beim Hinzufügen des Assets:', error);
      toast.error('Fehler beim Hinzufügen des Assets');
    }
  };

  // Asset Handler in der Hauptkomponente
  const handleAssetSelect = async (assetId: number) => {
    if (!viewer.current) return;

    try {
      const tileset = await Cesium.Cesium3DTileset.fromIonAssetId(assetId);
      const layer = viewer.current.scene.primitives.add(tileset);
      
      setLayers(prev => [...prev, {
        id: `asset_${assetId}`,
        name: `Asset ${assetId}`,
        enabled: true,
        layer,
        icon: <Box className="h-4 w-4" />,
        zoomTo: () => {
          if (viewer.current) {
            viewer.current.zoomTo(tileset);
          }
        }
      }]);

    } catch (error) {
      console.error('Fehler beim Laden des Assets:', error);
      toast.error('Fehler beim Laden des Assets');
    }
  };

  const LayerControl = ({ layer }: { layer: Layer }) => (
    <div className="flex items-center gap-2">
      <button
        onClick={() => toggleLayer(layer.id)}
        className="text-gray-600 hover:text-gray-800"
        disabled={layer.isLoading}
      >
        {layer.enabled ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
      </button>
      <button
        onClick={layer.zoomTo}
        className="flex items-center gap-2 text-gray-600 hover:text-gray-800"
        disabled={layer.isLoading}
      >
        {layer.icon}
        {layer.name}
        {layer.isLoading && <span className="ml-2">Laden...</span>}
      </button>
    </div>
  );

  return (
    <div className="relative w-full h-full">
      <div ref={viewerContainer} className="w-full h-full" />
      
      {/* Zeichenwerkzeuge */}
      {isDrawing && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 flex gap-2 bg-white p-2 rounded shadow z-10">
          <button
            onClick={finishDrawing}
            className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
          >
            Zeichnen beenden
          </button>
          <button
            onClick={resetDrawing}
            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            Zurücksetzen
          </button>
        </div>
      )}

      {/* Hilfetext */}
      {isDrawing && (
        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 bg-white p-2 rounded shadow z-10">
          <p className="text-sm text-gray-600">
            Klicken Sie auf die Karte um Punkte zu setzen
            <br />
            Rechtsklick oder Button um das Zeichnen zu beenden
          </p>
          <p className="text-sm text-gray-500 mt-1">
            Punkte: {positions.length}
          </p>
        </div>
      )}

      {/* Linke Sidebar mit Layer Controls und Projektgrenzen-Button */}
      <div className="absolute top-4 left-4 flex flex-col gap-4 z-10">
        {/* Layer Toggle Buttons */}
        <div className="bg-white p-4 rounded shadow">
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="text-gray-600 hover:text-gray-800"
            >
              <Layers className="h-6 w-6" />
            </button>
          </div>

          {showSidebar && (
            <div className="space-y-4">
              <AssetDropdown 
                onAssetSelect={handleAssetSelect} 
                token={token}
              />
              {layers.map(layer => (
                <LayerControl key={layer.id} layer={layer} />
              ))}

              {/* Projektgrenzen Button nur anzeigen wenn keine existieren */}
              {!hasProjectBoundary && (
                <div className="pt-4 border-t border-gray-200">
                  <button
                    onClick={startDrawing}
                    className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 flex items-center gap-2"
                  >
                    <Box className="h-4 w-4" />
                    Projektgrenzen zeichnen
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Dialog zum Speichern der Projektgrenzen */}
      {showSaveDialog && (
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-white p-6 rounded-lg shadow-xl">
          <h3 className="text-lg font-medium mb-4">Projektgrenzen speichern</h3>
          <p className="mb-4">Möchten Sie diese Fläche als Projektgrenzen speichern?</p>
          <div className="flex justify-end gap-3">
            <button
              onClick={() => {
                setShowSaveDialog(false);
                setIsDrawing(false);
                setIsEditingBoundary(false);
              }}
              className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
            >
              Abbrechen
            </button>
            <button
              onClick={saveProjectBoundary}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              Speichern
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const handleSaveBoundingBox = async (bbox: {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}) => {
  try {
    await fetch('/api/project-boundaries', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ bbox }),
    });
    // Erfolgsbehandlung
  } catch (error) {
    // Fehlerbehandlung
  }
};

// Asset Dropdown Komponente
interface IonAsset {
  id: number;
  name: string;
  type: string;
  description: string;
}

interface AssetDropdownProps {
  onAssetSelect: (assetId: number) => void;
  token: string;
}

function AssetDropdown({ onAssetSelect, token }: AssetDropdownProps) {
  const [assets, setAssets] = useState<IonAsset[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const loadAssets = async () => {
      if (!token) return;
      
      setIsLoading(true);
      try {
        // Direkt die Assets API aufrufen
        const response = await fetch('https://api.cesium.com/v1/assets', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        if (!response.ok) {
          throw new Error('Fehler beim Laden der Assets');
        }

        const data = await response.json();
        setAssets(data.items || []);
      } catch (error) {
        console.error('Fehler beim Laden der Ion Assets:', error);
        toast.error('Fehler beim Laden der Assets');
      } finally {
        setIsLoading(false);
      }
    };

    loadAssets();
  }, [token]);

  const handleAssetSelect = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const assetId = Number(e.target.value);
    if (!assetId) return;

    try {
      await addAssetToProject(assetId);
      onAssetSelect(assetId);
    } catch (error) {
      console.error('Fehler beim Laden des Assets:', error);
      toast.error('Fehler beim Laden des Assets');
    }
  };

  return (
    <div className="bg-white p-4 rounded shadow">
      <h3 className="text-lg font-medium mb-4">Verfügbare Assets</h3>
      {isLoading ? (
        <div>Lade Assets...</div>
      ) : assets.length === 0 ? (
        <div>Keine Assets gefunden</div>
      ) : (
        <select 
          className="w-full p-2 border rounded"
          onChange={handleAssetSelect}
        >
          <option value="">Asset auswählen...</option>
          {assets.map(asset => (
            <option key={asset.id} value={asset.id}>
              {asset.name} ({asset.type})
            </option>
          ))}
        </select>
      )}
    </div>
  );
}