# Contributing to Derush

Thank you for your interest in contributing to Derush! This document provides guidelines and instructions for contributing to the project.

## Development Setup

**Environnement et commandes : [PYTHON.md](PYTHON.md).**

1. Fork & clone, then `cd derush`
2. `make install` (crée le venv et installe les deps), ou voir PYTHON.md pour les commandes manuelles
3. Optionnel : `pre-commit install`

## Tests

`make test` ou `pytest tests/ -v` (venv activé). Couverture : `pytest tests/ --cov=derush --cov-report=html`. Détails dans PYTHON.md.

## Code style

Ruff (config dans `pyproject.toml`). `make lint` et `make format`.

## Making Changes

### Branching Strategy

1. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bugfix-name
   ```

2. Make your changes
3. Write or update tests
4. Ensure all tests pass
5. Commit your changes with a clear message
6. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

7. Open a Pull Request on GitHub

### Commit Messages

Use clear and descriptive commit messages:
- Start with a verb (e.g., "Add", "Fix", "Update", "Refactor")
- Keep the first line under 72 characters
- Add more details in the body if needed

Example:
```
Add support for custom filler words

Users can now define custom filler words in the configuration
file, which allows better adaptation to different languages
and speaking styles.
```

## Adding Tests

- Write tests for all new features
- Ensure existing tests still pass
- Aim for good test coverage (minimum 80%)
- Use pytest fixtures for common setup

## Documentation

- Update docstrings for any modified functions
- Update the README.md for user-facing changes
- Add entries to CHANGELOG.md for significant changes

## Pre-commit Checklist

Before submitting a PR, ensure:
- [ ] All tests pass (`make test`)
- [ ] Lint and format OK (`make lint` then `make format`)
- [ ] Coverage is above 80%
- [ ] Documentation is updated
- [ ] CHANGELOG.md is updated

## Reporting Bugs

When reporting bugs, please include:
- Python version
- Derush version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Error messages or logs

## Feature Requests

For feature requests:
- Clearly describe the feature
- Explain the use case
- Consider if it fits the project's goals
- Open an issue with the "enhancement" label

## Questions

For questions:
- Check existing documentation first
- Search existing issues
- Open an issue with the "question" label

## Code of Conduct

Be respectful, constructive, and inclusive. We want everyone to feel welcome contributing to this project.

## Getting Help

If you need help:
- Open an issue on GitHub
- Check the documentation
- Look at existing tests for examples

Thank you for contributing to Derush! 🎉
