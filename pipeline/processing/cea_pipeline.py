"""
Pipeline für die CEA-Datenverarbeitung.
"""
from typing import Dict, Any, List
from .cea_base import CEABaseProcessor, CEAProcessingError
from .cea_processors import CEAGeometryProcessor, CEAAttributeProcessor, CEAValidationProcessor

class CEAProcessingPipeline:
    """
    Verarbeitungspipeline für CEA-Daten.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.processors: List[CEABaseProcessor] = []
        self._initialize_pipeline()
        
    def _initialize_pipeline(self):
        """
        Initialisiert die Standard-Prozessoren.
        """
        self.processors = [
            CEAValidationProcessor(self.config),
            CEAGeometryProcessor(self.config),
            CEAAttributeProcessor(self.config)
        ]
        
    def add_processor(self, processor: CEABaseProcessor):
        """
        Fügt einen zusätzlichen Prozessor zur Pipeline hinzu.
        """
        self.processors.append(processor)
        
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Führt die Verarbeitung durch die gesamte Pipeline durch.
        """
        result = data
        for processor in self.processors:
            try:
                result = processor.process(result)
                if not result:
                    # Wenn ein Prozessor leere Daten zurückgibt, brechen wir ab
                    return {}
            except Exception as e:
                # Fehlerbehandlung für jeden Prozessor
                raise CEAProcessingError(f"Fehler im Prozessor {processor.__class__.__name__}: {str(e)}")
                
        return result 