# Derush - Makefile
# Utilise le venv du projet (./venv/bin/). Voir PYTHON.md pour la doc complète.
# Usage : make test, make lint, make format, make install

VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff

.PHONY: install test lint format help

help:
	@echo "Commandes disponibles (voir PYTHON.md) :"
	@echo "  make install  - Créer venv et installer les deps (à lancer une fois)"
	@echo "  make test     - Lancer les tests"
	@echo "  make lint     - Vérifier le code (ruff check)"
	@echo "  make format   - Formater le code (ruff format)"

# Crée le venv s'il n'existe pas
$(VENV)/bin/pip:
	@echo "Création du venv..."
	python3 -m venv $(VENV)

install: $(VENV)/bin/pip
	$(PIP) install -e ".[dev,lint,export]"
	@echo "Environnement prêt. Utilisez : make test, make lint, make format"

test:
	$(PYTEST) tests/ -v

lint:
	$(RUFF) check derush/ tests/

format:
	$(RUFF) format derush/ tests/
