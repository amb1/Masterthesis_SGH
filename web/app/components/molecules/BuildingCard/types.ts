export interface BuildingCardProps {
  /**
   * Eindeutige ID des Gebäudes
   */
  gmlId: string;
  
  /**
   * Höhe des Gebäudes in Metern
   */
  height?: number;
  
  /**
   * Anzahl der Stockwerke über dem Boden
   */
  storeys?: number;
  
  /**
   * Typ des Gebäudes (z.B. residential, commercial)
   */
  buildingType?: string;
  
  /**
   * Objekt-ID des Gebäudes
   */
  objectId?: string;
  
  /**
   * Handler für Klick-Events
   */
  onClick?: (gmlId: string) => void;
  
  /**
   * CSS-Klassen für zusätzliches Styling
   */
  className?: string;
} 