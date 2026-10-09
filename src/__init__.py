"""TomoDesk package root.

Kept dependency-free on purpose: importing any ``src.*`` submodule executes
this file, so a heavy import here (PySide6, chromadb, ollama) would be paid
by every consumer, including the CLI mode which must run without a GUI
stack. Only the version lives here; ``build/bump_version.py`` and the CI
release guard read it with a positional regex.
"""

__version__ = "1.6.0"
