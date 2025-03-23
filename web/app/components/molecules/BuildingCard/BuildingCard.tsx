import { FC } from 'react'
import { BuildingIcon, LayersIcon } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { BuildingCardProps } from './types'
import { cn } from '@/lib/utils'

export const BuildingCard: FC<BuildingCardProps> = ({
  gmlId,
  height,
  storeys,
  buildingType,
  objectId,
  onClick,
  className
}) => {
  const handleClick = () => {
    if (onClick) {
      onClick(gmlId)
    }
  }

  return (
    <Card 
      className={cn('cursor-pointer hover:shadow-lg transition-shadow', className)}
      onClick={handleClick}
      data-testid="building-card"
    >
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <BuildingIcon className="h-5 w-5" />
          {buildingType || 'Gebäude'}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">GML ID:</span>
            <span className="font-mono">{gmlId}</span>
          </div>
          
          {height && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Höhe:</span>
              <span>{height} m</span>
            </div>
          )}
          
          {storeys && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground flex items-center gap-1">
                <LayersIcon className="h-4 w-4" />
                Stockwerke:
              </span>
              <span>{storeys}</span>
            </div>
          )}
          
          {objectId && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Objekt ID:</span>
              <span className="font-mono">{objectId}</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
} 