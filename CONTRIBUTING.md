# Contributing to Omni Pre-Processor

Thank you for your interest in contributing!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/1StepMore/Omni_Pre_Processor.git
cd Omni_Pre_Processor

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Unix
.venv\Scripts\activate     # Windows

# Install with development dependencies
pip install -e ".[dev]"

# Install all optional dependencies
pip install -e ".[all]"
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/opp --cov-report=term-missing

# Run specific test file
pytest tests/extractor/test_docx.py

# Run with verbose output
pytest -v
```

## Code Style

This project uses standard Python conventions:
- Follow PEP 8
- Use type hints where possible
- Write docstrings for public functions/classes
- Keep lines under 120 characters

## Linting

```bash
# Type checking with pyright
pyright src/opp

# Or with ruff
ruff check src/opp
```

## Building Documentation

```bash
# Build this README
# Documentation is generated from source code docstrings
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Reporting Issues

Please report issues at:
https://github.com/1StepMore/Omni_Pre_Processor/issues

When reporting bugs, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages if applicable

## Feature Requests

We welcome feature requests! Please open an issue with:
- Clear description of the feature
- Use case / motivation
- Any relevant context or alternatives considered

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
