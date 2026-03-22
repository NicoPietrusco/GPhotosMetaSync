# GPhotoMetaSync — https://github.com/casey/just
# Install: brew install just  (or see https://github.com/casey/just)

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

# List recipes (run when you type: just)
default:
    @just --list

# Launch the Flask web app
run: web

# Confirm client_secrets.json is present and the Flask app loads
verify:
    uv run python scripts/verify_setup.py

web:
    @echo "Launching Flask app..."
    uv run gphotometasync

install:
    @echo "Installing dependencies..."
    uv sync --group dev
    @echo "Done."

setup:
    @echo "Creating venv (Python 3.11)..."
    uv venv --python python3.11 .venv
    uv sync --group dev
    @echo "Done."

lint:
    uv run ruff check src/

format:
    uv run ruff format src/

clean:
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name ".DS_Store" -delete 2>/dev/null || true
    @echo "Cache cleaned."

clean-all: clean
    rm -rf data/outputs/* data/uploads/* 2>/dev/null || true
    rm -rf output/*.json output/*_dated.* 2>/dev/null || true
    @echo "Outputs cleaned."
