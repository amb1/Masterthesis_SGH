/*
  # Create storage bucket for CityGML files

  1. Storage Bucket
    - Creates a storage bucket named 'citygml' if it doesn't exist
    - Ensures public access for reading files
  2. Security
    - Adds policies for public read access
    - Adds policies for authenticated user operations (upload, update, delete)
*/

DO $$
BEGIN
    -- Check if bucket exists before creating
    IF NOT EXISTS (
        SELECT 1 FROM storage.buckets WHERE id = 'citygml'
    ) THEN
        INSERT INTO storage.buckets (id, name, public)
        VALUES ('citygml', 'citygml', true);
    END IF;
END $$;

-- Drop existing policies if they exist
DO $$
BEGIN
    DROP POLICY IF EXISTS "Public Access" ON storage.objects;
    DROP POLICY IF EXISTS "Authenticated users can upload files" ON storage.objects;
    DROP POLICY IF EXISTS "Authenticated users can update their files" ON storage.objects;
    DROP POLICY IF EXISTS "Authenticated users can delete their files" ON storage.objects;
EXCEPTION
    WHEN others THEN null;
END $$;

-- Create policy to allow public access to files
CREATE POLICY "Public Access"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'citygml');

-- Create policy to allow authenticated users to upload files
CREATE POLICY "Authenticated users can upload files"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'citygml');

-- Create policy to allow authenticated users to update their files
CREATE POLICY "Authenticated users can update their files"
ON storage.objects FOR UPDATE
TO authenticated
USING (bucket_id = 'citygml' AND owner = auth.uid())
WITH CHECK (bucket_id = 'citygml');

-- Create policy to allow authenticated users to delete their files
CREATE POLICY "Authenticated users can delete their files"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'citygml' AND owner = auth.uid());