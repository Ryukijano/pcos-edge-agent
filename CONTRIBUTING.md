# Contributing to PCOS

Thank you for your interest in contributing to PCOS! This document covers the basics.

## Getting Started

1. Fork the repository and create a feature branch (`git checkout -b feat/my-feature`)
2. Install dependencies: `pip install -r requirements.txt`
3. Run tests: `python -m pytest tests/ -q`
4. Make your changes, keeping code style consistent with existing files

## Code Style

- **Python**: Follow PEP 8, use `ruff` for linting (`ruff check .`)
- **Kotlin**: Follow Kotlin coding conventions, 4-space indent
- **JavaScript**: Follow standard style, 2-space indent

## Pull Request Process

1. Ensure all tests pass: `python -m pytest tests/ -q`
2. Update documentation if you change APIs or routing logic
3. Write tests for new features — aim for meaningful coverage, not 100%
4. Keep PRs focused — one feature or fix per PR
5. Reference issues in your PR description (`Fixes #123`, `Closes #456`)

## Architecture Overview

PCOS has three planes:
- **Chrome** — Built-in AI APIs (Prompt, Summarizer, Writer, Rewriter, Proofreader, Translator, Language Detector)
- **Android** — LiteRT-LM on-device inference with FunctionGemma + Tool Use API
- **Memory** — PiecesOS MCP connector for long-term memory

The broker routes tasks to the best surface based on privacy, latency, and capability.

## Reporting Issues

Use GitHub Issues. Include:
- Expected vs actual behavior
- Steps to reproduce
- Logs (if applicable)
- Environment (OS, Chrome version, Android version)
