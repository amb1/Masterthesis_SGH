.PHONY: test test-e2e clean

# Grundlegende Variablen
PYTHON := python
TEST_PATH := tests/
PYTEST := pytest
PYTEST_ARGS := -v --capture=no

# Test-Verzeichnisse erstellen
setup-test:
	mkdir -p tests/fixtures/data/citygml
	mkdir -p tests/fixtures/data/cea
	mkdir -p tests/output
	mkdir -p tests/temp

# Alle Tests ausführen
test: setup-test
	$(PYTEST) $(PYTEST_ARGS) $(TEST_PATH)

# Nur E2E Tests ausführen
test-e2e: setup-test
	$(PYTEST) $(PYTEST_ARGS) $(TEST_PATH)/pipeline/test_pipeline_e2e.py

# Aufräumen
clean:
	rm -rf tests/output/*
	rm -rf tests/temp/* 