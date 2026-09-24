<div align="center">

# 📸 GPhotoMetaSync

**Google Photos Metadata Synchronizer**

A powerful Python tool for extracting, analyzing, and embedding EXIF metadata from images. Perfect for Google Photos workflows, photo organization, and metadata management.

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 📋 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [Usage](#-usage)
  - [Desktop GUI](#desktop-gui)
  - [Command Line](#command-line-interface)
  - [Justfile commands](#justfile-commands)
- [Supported Formats](#-supported-formats)
- [Documentation](#-documentation)
- [Development](#-development)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### Core Capabilities
- 📊 **EXIF Data Extraction** - Extract comprehensive metadata to JSON files
- 🗺️ **GPS Coordinate Processing** - Convert GPS coordinates to decimal degrees
- 🕒 **Date Embedding** - Restore original creation dates in EXIF and filesystem
- 🔄 **Batch Processing** - Process multiple images with real-time progress tracking
- 📁 **Flexible Input** - Support for files, directories, and glob patterns

### User Interfaces
- 🖥️ **Desktop GUI** - Beautiful Tkinter interface with drag-and-drop simplicity
  - Real-time progress updates
  - Detailed logging with file-by-file status
  - Browse dialogs for input/output folders
  - Summary reports with success/failure statistics
  
- ⌨️ **Command Line Interface** - Powerful CLI for automation and scripting
  - Verbose logging options
  - Custom output directories
  - Batch operations

### Technical Features
- 🎯 **Accurate Success Tracking** - See exactly which files succeeded/failed
- 🚀 **Background Processing** - Non-blocking GUI with threaded operations
- 📝 **Comprehensive Logging** - Detailed logs in both GUI and terminal
- 🔧 **Extensible** - Clean, modular architecture

---

## 🚀 Installation

### Prerequisites
- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv)
- [just](https://github.com/casey/just) (optional; for `just setup`, `just web`, etc.)

### Quick Install

```bash
git clone https://github.com/yourusername/GPhotoMetaSync.git
cd GPhotoMetaSync

just setup
just web
```

### Manual Setup (Alternative)

```bash
uv venv --python python3.11 .venv
uv sync --group dev
uv run gphotometasync
```

---

## 💻 Usage

### Web app (Flask)

```bash
just web
```

Open the URL shown in the terminal (default `http://127.0.0.1:5001`). Upload a local image or use **Google Photos** (local desktop OAuth + Photos Picker API), then download the JSON sidecar and the image with embedded EXIF.

On macOS, if you use port **5000**, **AirPlay Receiver** may answer instead of Flask and you can see **HTTP 403**. The app defaults to **5001**; override with `PORT=5000` in `.env` only if that port is free.

### Google Photos (local desktop + Picker API)

This app is meant to run **on your computer only** (not deployed as a public website). **End users** who only have a Google account sign in through the browser; they do **not** need their own Google Cloud project. **Whoever packages or installs the app** completes a **one-time** Cloud setup and adds a **Desktop / Installed** OAuth client JSON file.

Photo access uses the **[Photos Picker API](https://developers.google.com/photos/picker/guides/get-started-picker)** (`photospicker.googleapis.com`). The older Library API scopes are deprecated; picking is done through the Picker flow only.

1. In [Google Cloud Console](https://console.cloud.google.com/), enable **Google Photos Picker API**. Configure the **OAuth consent screen** if you have not already.
2. Create **Credentials** → **OAuth client ID** → type **Desktop app** (Installed). Download the JSON.
3. Save it as [`credentials/client_secrets.json`](credentials/) or set `GOOGLE_OAUTH_CLIENT_SECRETS` (see [`.env.example`](.env.example)). Full steps: [`credentials/README.md`](credentials/README.md).
4. Optional: run `just verify` to confirm the file is found and the app loads.
5. Run `just web`, click **Sign In** — a local browser window completes **OAuth 2.0** (`InstalledAppFlow`); tokens are stored in `credentials/google_token.json` (gitignored). Then **Select Photos** opens the Google picker. **Process EXIF** runs the pipeline on the server using the same OAuth session.

The app loads `.env` on startup (`python-dotenv`). Because this is a local tool, cookies and tokens stay on your machine.

### Justfile commands

Common tasks are defined in [`justfile`](justfile):

```bash
just              # list recipes
just setup        # venv + uv sync (dev group, includes ruff)
just verify       # check credentials/client_secrets.json + app import
just web          # run Flask app (same as `just run`)
just lint         # ruff check
just typecheck    # ty static type check
just format       # ruff format
just package      # build the local desktop bundle
just package-macos # build the macOS .app and .dmg
just clean        # remove caches
just clean-all    # caches + data/outputs, data/uploads, output/*
```

### Desktop releases

The published desktop app includes the Google OAuth client configured by the project
maintainer. A person who downloads the app only signs in with their Google account;
they do not download credentials or create a Google Cloud project. Their OAuth token
stays on their computer.

For a local macOS build:

```bash
just install
just package-macos
```

This creates `dist/Photo Meta Sync.app` and `dist/PhotoMetaSync-macOS-arm64.dmg`.
The GitHub release workflow builds macOS and Windows artifacts when a `v*` tag is
pushed. Before using it, add the full Desktop OAuth client JSON as the repository
secret `GOOGLE_OAUTH_CLIENT_JSON`; never add an OAuth token to repository secrets.

The unsigned artifacts are suitable for testing. Public releases may show macOS
Gatekeeper or Windows SmartScreen warnings until they are code-signed.

**Typical workflow:**

```bash
just setup
just web
```

---

## 📝 Supported Formats

| Format | Extensions | Notes |
|--------|-----------|-------|
| JPEG | `.jpg`, `.jpeg` | ✅ Full support |
| PNG | `.png` | ✅ Full support |
| TIFF | `.tiff`, `.tif` | ✅ Full support |
| BMP | `.bmp` | ✅ Full support |
| WebP | `.webp` | ✅ Full support |
| HEIC/HEIF | `.heic`, `.heif` | ⚠️ Requires `pillow-heif` |

**Install HEIC support:**
```bash
pip install pillow-heif
```

---

## 📖 Documentation

### Output Examples

**Extract Mode:**
```json
{
  "DateTime": "2022:07:31 18:54:33",
  "Make": "Google",
  "Model": "Pixel 6",
  "GPS": {
    "GPSLatitude": [45, 28, 12.34],
    "GPSLongitude": [12, 15, 43.21],
    "LatitudeDecimal": 45.4701,
    "LongitudeDecimal": 12.2620
  },
  "_file_info": {
    "filename": "photo.jpg",
    "size_bytes": 2635725,
    "format": "JPEG"
  }
}
```

**Embed Mode:**
- Creates new images with `_dated` suffix
- Preserves original files
- Updates EXIF timestamps and filesystem dates

### Programmatic Usage

```python
from pathlib import Path
from src.gphotometasync.core.exif_utils import extract_exif_data, embed_exif_dates
from src.gphotometasync.utils.file_utils import find_images

# Find images
images = find_images([Path("photos/")])

# Extract EXIF data
for img in images:
    result = extract_exif_data(img, Path("metadata"))
    if "success" in result:
        print(f"✅ {img.name}: {result['exif_fields_count']} fields")
    else:
        print(f"❌ {img.name}: {result['error']}")

# Embed dates
for img in images:
    if embed_exif_dates(img, Path("corrected")):
        print(f"✅ {img.name}: Dates embedded")
```

---

## 🏗️ Project Structure

```
GPhotoMetaSync/
├── src/
│   └── gphotometasync/
│       ├── __init__.py           # Package entry point
│       ├── web/                  # Flask app + templates
│       ├── settings.py           # Configuration
│       ├── core/
│       │   ├── exif_utils.py     # EXIF extraction/embedding
│       │   └── photo_utils.py    # Photo processing workflows
│       └── utils/
│           ├── file_utils.py     # File operations
│           └── logger_utils.py   # Logging setup
├── input/                        # Sample images
├── output/                       # Processing results
├── docs/                         # Documentation
├── justfile                      # Task runner (just)
├── pyproject.toml                # Project metadata
└── README.md                     # This file
```

---

## 🔧 Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/yourusername/GPhotoMetaSync.git
cd GPhotoMetaSync
just setup

source .venv/bin/activate
```

### Code Quality

```bash
just lint
just format
just clean
```

### Architecture

**Core Modules:**
- `exif_utils.py` - EXIF data extraction, GPS conversion, date embedding
- `photo_utils.py` - Upload / pipeline orchestration
- `file_utils.py` - File discovery, JSON serialization, path management
- `logger_utils.py` - Centralized logging with loguru

**Design Principles:**
- Modular architecture with clear separation of concerns
- Comprehensive error handling and logging
- Flask UI with OAuth for Google Photos
- Extensive type hints for better IDE support

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Make** your changes
4. **Test** your changes
   ```bash
   just lint
   pytest
   ```
5. **Commit** with clear messages
   ```bash
   git commit -m 'Add amazing feature'
   ```
6. **Push** to your fork
   ```bash
   git push origin feature/amazing-feature
   ```
7. **Open** a Pull Request

### Contribution Guidelines

- Follow PEP 8 style guidelines (use `just format`)
- Run linter before committing (`just lint`)
- Update documentation as needed
- Keep commits atomic and well-described
- Test your changes with the web app (`just web`)

---

## 📦 Dependencies

### Core Dependencies
| Package | Purpose |
|---------|---------|
| [Pillow](https://python-pillow.org/) | Image processing and EXIF handling |
| [piexif](https://github.com/hMatoba/Piexif) | EXIF manipulation |
| [Flask](https://flask.palletsprojects.com/) | Web UI |
| [PyYAML](https://pyyaml.org/) | EXIF field config |
| (Browser) [Google Identity Services](https://developers.google.com/identity/oauth2/web/guides/overview) | OAuth access token for Picker API |
| [google-auth](https://github.com/googleapis/google-auth-library-python) / [google-auth-oauthlib](https://github.com/googleapis/google-auth-library-python-oauthlib) | OAuth (Installed app) + token refresh |
| [requests](https://requests.readthedocs.io/) | Picker API HTTP |
| [loguru](https://loguru.readthedocs.io/) | Logging |

### Optional Dependencies
| Package | Purpose |
|---------|---------|
| pillow-heif | HEIC/HEIF format support |
| ruff | Code linting and formatting (dev group) |

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### MIT License Summary
- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- ✅ Private use

---

## 🙏 Acknowledgments

- **Image Processing** - [Pillow](https://python-pillow.org/) library
- **Web** - [Flask](https://flask.palletsprojects.com/)
- **Tasks** - [just](https://github.com/casey/just)
- **Logging** - [loguru](https://loguru.readthedocs.io/) library
- **EXIF Manipulation** - [piexif](https://github.com/hMatoba/Piexif) by hMatoba

---

## 📞 Support & Contact

**Found a bug?** [Open an issue](https://github.com/yourusername/GPhotoMetaSync/issues/new)

**Have a question?** [Start a discussion](https://github.com/yourusername/GPhotoMetaSync/discussions)

**Want to contribute?** See our [Contributing Guide](#-contributing)

---

<div align="center">

**Made with ❤️ by the GPhotoMetaSync team**

⭐ Star us on GitHub if you find this useful!

[Report Bug](https://github.com/yourusername/GPhotoMetaSync/issues) • [Request Feature](https://github.com/yourusername/GPhotoMetaSync/issues) • [Documentation](docs/)

</div>
