import { prisma } from '@/lib/prisma';
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { bbox, polygon } = body;

    const projectBoundary = await prisma.projectBoundary.create({
      data: {
        minLon: bbox.minLon,
        minLat: bbox.minLat,
        maxLon: bbox.maxLon,
        maxLat: bbox.maxLat,
        polygon: polygon // Speichert die kompletten Polygon-Koordinaten
      }
    });

    return NextResponse.json(projectBoundary);
  } catch (error) {
    console.error('Fehler beim Speichern der Projektgrenzen:', error);
    return NextResponse.json(
      { error: 'Fehler beim Speichern der Projektgrenzen' },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    const projectBoundary = await prisma.projectBoundary.findFirst({
      orderBy: { createdAt: 'desc' }
    });

    return NextResponse.json(projectBoundary);
  } catch (error) {
    console.error('Fehler beim Laden der Projektgrenzen:', error);
    return NextResponse.json(
      { error: 'Fehler beim Laden der Projektgrenzen' },
      { status: 500 }
    );
  }
}