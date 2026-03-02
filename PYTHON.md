# Python dans ce projet

Référence pour l’environnement et les commandes (dev, tests, lint). Package : `derush/` (pas `src/`).

## Mise en place (une fois)

Python 3.10–3.14. À la racine du projet :

```bash
python3 -m venv venv
./venv/bin/pip install -e ".[dev,lint]"
```

Pour l’export FCPXML en local, ajouter l’extra `export` : `".[dev,lint,export]"`.

## Commandes

| Action   | Commande |
|----------|----------|
| Tests    | `make test` ou `./venv/bin/pytest tests/ -v` |
| Lint     | `make lint` ou `./venv/bin/ruff check derush/ tests/` |
| Format   | `make format` ou `./venv/bin/ruff format derush/ tests/` |
| App      | `./venv/bin/derush --help` (ou `derush` si venv activé) |

Toujours exécuter depuis la racine du dépôt. Ne pas supposer que `python`, `pytest` ou `ruff` sont dans le PATH (utiliser `make` ou `./venv/bin/...`). Si le venv n’existe pas : `make install` ou les commandes ci‑dessus.
