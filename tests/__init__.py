"""
Test-Suite für das CEA-Projekt.

Dieses Paket enthält alle Tests für die CEA-Funktionalität,
einschließlich Unit-Tests und Integrationstests.
"""

import pytest
import os
import sys

# Füge das Hauptverzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 