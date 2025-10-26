# Makefile for GPhotoMetaSync
# Note: Make requires TAB characters for indentation

.PHONY: help run gui cli install clean lint format setup

help:
	@echo "GPhotoMetaSync - Available Commands:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  make run         - Launch the GUI application"
	@echo "  make gui         - Launch the GUI application"
	@echo "  make cli         - Run CLI"
	@echo "  make install     - Install dependencies with uv"
	@echo "  make setup       - Setup virtual environment"
	@echo "  make lint        - Run linter (ruff)"
	@echo "  make format      - Format code with ruff"
	@echo "  make clean       - Remove cache files"
	@echo "  make clean-all   - Remove cache and output files"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

run: gui

gui:
	@echo "🚀 Launching GUI..."
	@source .venv/bin/activate && python -m src.gphotometasync.gui

cli:
	@echo "🚀 Running CLI..."
	@source .venv/bin/activate && python -m src.gphotometasync.main extract input/ -v

install:
	@echo "�� Installing dependencies with uv..."
	@uv sync
	@echo "✅ Dependencies installed"

setup:
	@echo "🔧 Setting up virtual environment with Python 3.11..."
	@uv venv --python python3.11 .venv
	@uv sync
	@echo "✅ Setup complete"

lint:
	@echo "🔍 Running linter..."
	@source .venv/bin/activate && ruff check src/

format:
	@echo "✨ Formatting code..."
	@source .venv/bin/activate && ruff format src/

clean:
	@echo "🧹 Cleaning cache files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "✅ Cache cleaned"

clean-all: clean
	@echo "🧹 Cleaning output files..."
	@rm -rf output/*.json output/*_dated.* 2>/dev/null || true
	@echo "✅ All cleaned"

extract:
	@echo "📊 Extracting EXIF from input/ folder..."
	@source .venv/bin/activate && python -m src.gphotometasync.main extract input/ --verbose

embed:
	@echo "📅 Embedding EXIF dates from input/ folder..."
	@source .venv/bin/activate && python -m src.gphotometasync.main embed input/ --verbose
