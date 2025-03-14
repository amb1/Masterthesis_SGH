import logging

def setup_logger(name: str, force_output: bool = False) -> logging.Logger:
    """Zentrale Logger-Konfiguration für alle Module.
    
    Args:
        name (str): Name des Loggers
        force_output (bool): Wenn True, wird der Logger immer Ausgaben erzeugen,
                           auch wenn das Modul importiert wurde
    """
    logger = logging.getLogger(name)
    
    # Wenn der Logger bereits Handler hat, entferne sie
    if logger.handlers:
        logger.handlers.clear()
        
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Verhindere Propagation zu Parent-Loggern
    
    # Füge Handler nur hinzu, wenn wir im Hauptmodul sind oder force_output True ist
    if force_output or name == "__main__" or name == "__mp_main__":
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
        
    return logger 