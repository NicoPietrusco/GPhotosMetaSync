# GPhotoMetaSync — https://github.com/casey/just
# Install: brew install just  (or see https://github.com/casey/just)

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

# List recipes (run when you type: just)
default:
    @just --list

# Launch the Flask web app
[group('Run')]
run: web

# Confirm client_secrets.json is present and the Flask app loads
[group('Setup')]
verify:
    uv run python scripts/verify_setup.py

[group('Run')]
web:
    @echo "Launching Flask app..."
    uv run gphotometasync

[group('Setup')]
install:
    @echo "Installing dependencies..."
    uv sync --group dev
    @echo "Done."

# Build a local desktop bundle for the current operating system
[group('Packaging')]
package:
    uv run pyinstaller --noconfirm --clean GPhotoMetaSync.spec

# Create a distributable macOS disk image after `just package`
[group('Packaging')]
package-macos: package
    hdiutil create -volname "Photo Meta Sync" -srcfolder "dist/Photo Meta Sync.app" -ov -format UDZO "dist/PhotoMetaSync-macOS-arm64.dmg"

[group('Setup')]
setup:
    @echo "Creating venv (Python 3.11)..."
    uv venv --python python3.11 .venv
    uv sync --group dev
    @echo "Done."

[group('Quality')]
lint:
    uv run ruff check src/

[group('Quality')]
typecheck:
    uv run ty check src/

[group('Quality')]
format:
    uv run ruff format src/

[group('Maintenance')]
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name ".DS_Store" -delete 2>/dev/null || true
    @echo "Cache cleaned."

[group('Maintenance')]
clean-all: clean
    rm -rf data/outputs/* data/uploads/* 2>/dev/null || true
    rm -rf output/*.json output/*_dated.* 2>/dev/null || true
    @echo "Outputs cleaned."
