"""
Logging-Konfiguration für das Projekt.
"""
import logging
import sys
from contextlib import contextmanager
from typing import Optional

def setup_logging(level: int = logging.INFO) -> None:
    """Konfiguriert das Logging-System.
    
    Args:
        level: Logging-Level (default: INFO)
    """
    # Prüfe, ob Logger bereits konfiguriert ist
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    
    # Formatter erstellen
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Root Logger konfigurieren
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # Bestätige Initialisierung
    root_logger.debug("🔧 Logging-System initialisiert")

@contextmanager
def LoggedOperation(operation_name: str):
    """Kontext-Manager für geloggte Operationen.
    
    Args:
        operation_name: Name der Operation
    """
    logger = logging.getLogger(__name__)
    logger.info(f"🔄 Starte: {operation_name}")
    try:
        yield
    except Exception as e:
        logger.error(f"❌ Fehler bei {operation_name}: {str(e)}")
        raise
    finally:
        logger.info(f"✅ Beendet: {operation_name}") 