import { render, screen, fireEvent } from '@testing-library/react'
import { BuildingCard } from './BuildingCard'

describe('BuildingCard', () => {
  const mockProps = {
    gmlId: 'test-123',
    height: 25.5,
    storeys: 5,
    buildingType: 'residential',
    objectId: 'obj-456'
  }

  it('should render all building information', () => {
    render(<BuildingCard {...mockProps} />)
    
    // Überprüfe, ob alle Informationen angezeigt werden
    expect(screen.getByText('residential')).toBeInTheDocument()
    expect(screen.getByText('test-123')).toBeInTheDocument()
    expect(screen.getByText('25.5 m')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('obj-456')).toBeInTheDocument()
  })

  it('should handle click events', () => {
    const handleClick = jest.fn()
    render(<BuildingCard {...mockProps} onClick={handleClick} />)
    
    // Klick-Event auslösen
    fireEvent.click(screen.getByTestId('building-card'))
    
    // Überprüfe, ob der Click-Handler aufgerufen wurde
    expect(handleClick).toHaveBeenCalledWith(mockProps.gmlId)
  })

  it('should render without optional props', () => {
    render(<BuildingCard gmlId="test-123" />)
    
    // Überprüfe, ob nur die erforderlichen Informationen angezeigt werden
    expect(screen.getByText('Gebäude')).toBeInTheDocument()
    expect(screen.getByText('test-123')).toBeInTheDocument()
    
    // Überprüfe, ob optionale Informationen nicht angezeigt werden
    expect(screen.queryByText('m')).not.toBeInTheDocument()
    expect(screen.queryByText('Stockwerke:')).not.toBeInTheDocument()
    expect(screen.queryByText('Objekt ID:')).not.toBeInTheDocument()
  })

  it('should apply custom className', () => {
    render(<BuildingCard gmlId="test-123" className="custom-class" />)
    
    // Überprüfe, ob die benutzerdefinierte Klasse angewendet wurde
    const card = screen.getByTestId('building-card')
    expect(card).toHaveClass('custom-class')
  })
}) 