# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-02-27

### Added
- MIT License file
- Custom exceptions (DerushError, TranscriptionError, MediaInfoError, ExportError, ValidationError)
- Type hints improvements in base exporter methods
- Code coverage minimum (80%) configuration
- Pre-commit hooks configuration (Ruff, Mypy, and base hooks)
- Structured logging in CLI with proper error handling
- CHANGELOG.md for tracking changes
- CONTRIBUTING.md for contributors
- Dependency groups (test, lint, dev) for selective installation
- Configuration via environment variables (.env support)
- Configuration guide documentation (README_CONFIG.md)

### Changed
- **Major refactor**: Package structure renamed from `src/` to `derush/` for better Python standards
- Imports updated from `from src.xxx` to `from derush.xxx` throughout codebase
- pyproject.toml updated to reference new package structure
- Improved project documentation with best practices guide (PYTHON_BEST_PRACTICES.md)
- Enhanced type hints across codebase
- Better error handling with custom exceptions
- Improved test coverage and quality assurance
- Split dev dependencies into test, lint, and dev groups

### Fixed
- Type hints in BaseExporter class methods
- Python version constraints in pyproject.toml (>=3.10,<3.14)

## [0.1.0] - 2026-02-XX

### Added
- First release of derush tool
- WhisperX transcription with word-level alignment
- Filler words detection (euh, ben, bah, hmm, um, uh)
- Silence detection for automatic cutting
- Export formats: FCPXML (Final Cut Pro), EDL (DaVinci Resolve, Premiere Pro), JSON
- CLI with Typer
- Comprehensive test suite
- Code quality tools: Ruff, pytest, pytest-cov
- Modern Python packaging with pyproject.toml
