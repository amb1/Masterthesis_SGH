export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  public: {
    Tables: {
      buildings: {
        Row: {
          created_at: string
          geometry: Json
          id: string
          project_id: string | null
          properties: Json | null
          source_id: string
          source_type: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          geometry: Json
          id?: string
          project_id?: string | null
          properties?: Json | null
          source_id: string
          source_type: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          geometry?: Json
          id?: string
          project_id?: string | null
          properties?: Json | null
          source_id?: string
          source_type?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "buildings_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      project_boundaries: {
        Row: {
          created_at: string
          id: string
          max_lat: number
          max_lon: number
          min_lat: number
          min_lon: number
          polygon: Json
          project_id: string | null
          updated_at: string
        }
        Insert: {
          created_at?: string
          id?: string
          max_lat: number
          max_lon: number
          min_lat: number
          min_lon: number
          polygon: Json
          project_id?: string | null
          updated_at?: string
        }
        Update: {
          created_at?: string
          id?: string
          max_lat?: number
          max_lon?: number
          min_lat?: number
          min_lon?: number
          polygon?: Json
          project_id?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "project_boundaries_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: true
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      projects: {
        Row: {
          cesium_token: string | null
          created_at: string
          description: string | null
          id: string
          name: string
          owner_id: string | null
          updated_at: string
        }
        Insert: {
          cesium_token?: string | null
          created_at?: string
          description?: string | null
          id?: string
          name: string
          owner_id?: string | null
          updated_at?: string
        }
        Update: {
          cesium_token?: string | null
          created_at?: string
          description?: string | null
          id?: string
          name?: string
          owner_id?: string | null
          updated_at?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      add_column_if_not_exists: {
        Args: {
          _table: string
          _column: string
          _type: string
        }
        Returns: undefined
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type PublicSchema = Database[Extract<keyof Database, "public">]

export interface Tables {
  projects: {
    Row: {
      id: string;
      name: string;
      cesium_token: string | null;
      created_at: string;
      updated_at: string;
    };
  };
  project_boundaries: {
    Row: {
      id: string;
      project_id: string;
      min_lat: number;
      min_lon: number;
      max_lat: number;
      max_lon: number;
    };
  };
}
