# Contributing

Thank you for your interest in contributing!

## Getting started

- Create a virtual environment and install dependencies:
  - `make venv`
- Run the tests:
  - `make test`
- Launch the UI:
  - `make ui`

## Project layout

- `nodes/` - workflow nodes and critics
- `workflows/` - LangGraph workflow builders
- `utils/` - shared utilities
- `prompts/` - prompt templates
- `tests/` - test suite
- `logs/` - application logs and run artifacts
- `data/` - sample inputs/outputs and templates

## Coding standards

- Python 3.11+
- Keep code readable and explicit; follow the existing style
- Prefer small, focused functions; add docstrings when non-obvious
- Write tests alongside changes

## Pull requests

- Keep PRs small and focused
- Include a summary of changes and rationale
- Ensure `pytest` is green

## Logging and artifacts

- Logs and run artifacts live under `legal-document-analysis/logs/`
- The `logs/.gitignore` excludes noisy files by default
