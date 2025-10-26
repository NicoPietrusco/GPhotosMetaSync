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
  - [Makefile Commands](#makefile-commands)
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
- Tkinter (for GUI) - Usually included with Python

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/GPhotoMetaSync.git
cd GPhotoMetaSync

# One-command setup (creates venv + installs everything)
make setup

# That's it! Now launch the GUI:
make run
```

### Manual Setup (Alternative)

```bash
# Create virtual environment
uv venv --python python3.11 .venv

# Install dependencies
uv sync

# Launch GUI
source .venv/bin/activate
python -m src.gphotometasync.gui
```

---

## 💻 Usage

### Desktop GUI

The easiest way to use GPhotoMetaSync is through the graphical interface:

```bash
make run
```

**GUI Features:**
1. **📁 Select Files/Directory** - Choose images to process
2. **📂 Browse Output** - Pick where to save results
3. **📊 Extract EXIF Data** - Save metadata to JSON files
4. **📅 Embed EXIF Dates** - Restore original timestamps
5. **📝 Live Logs** - See real-time processing status
6. **📈 Progress Bar** - Visual feedback during processing
7. **📊 Summary Report** - Detailed statistics with failed files list

**Workflow Example:**
```
1. Click "Select Directory" → Choose your photos folder
2. Click "Browse" → Choose output location (optional)
3. Click "Extract EXIF Data" or "Embed EXIF Dates"
4. Watch progress in real-time
5. Review summary report with success/failure details
```

### Command Line Interface

For automation and scripting (activate venv first):

```bash
# Activate virtual environment
source .venv/bin/activate

# Extract EXIF data to JSON files
python -m src.gphotometasync.main extract photos/ --output metadata/

# Embed EXIF dates into new images
python -m src.gphotometasync.main embed photos/ --output corrected/

# Use verbose mode for detailed logs
python -m src.gphotometasync.main extract photos/ --verbose
```

**Or use the Makefile shortcuts:**

```bash
make extract    # Extract EXIF from input/ folder
make embed      # Embed EXIF dates in input/ folder
```

### Makefile Commands

The project includes a comprehensive Makefile for common tasks:

```bash
# Main commands
make run          # Launch GUI application ⭐
make gui          # Launch GUI (alias)

# CLI shortcuts
make cli          # Run CLI on input/ folder
make extract      # Extract EXIF from input/ folder
make embed        # Embed EXIF dates in input/ folder

# Setup & maintenance
make setup        # First-time setup (create venv + install)
make clean        # Remove cache files
make clean-all    # Remove cache + output files

# Code quality
make lint         # Run code linter (ruff)
make format       # Format code with ruff
```

**Typical workflow:**
```bash
make setup    # First time only
make run      # Daily use
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
│       ├── main.py               # CLI interface
│       ├── gui.py                # Desktop GUI (Tkinter)
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
├── Makefile                      # Build automation
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
make setup

# Activate virtual environment
source .venv/bin/activate
```

### Code Quality

```bash
# Lint code
make lint

# Format code
make format

# Clean cache
make clean
```

### Architecture

**Core Modules:**
- `exif_utils.py` - EXIF data extraction, GPS conversion, date embedding
- `photo_utils.py` - Batch processing, progress tracking, error handling
- `file_utils.py` - File discovery, JSON serialization, path management
- `logger_utils.py` - Centralized logging with loguru

**Design Principles:**
- Modular architecture with clear separation of concerns
- Comprehensive error handling and logging
- Thread-safe GUI with message queues
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
   make lint
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

- Follow PEP 8 style guidelines (use `make format`)
- Run linter before committing (`make lint`)
- Update documentation as needed
- Keep commits atomic and well-described
- Test your changes with the GUI and CLI

---

## 📦 Dependencies

### Core Dependencies
| Package | Purpose |
|---------|---------|
| [Pillow](https://python-pillow.org/) | Image processing and EXIF handling |
| [piexif](https://github.com/hMatoba/Piexif) | EXIF manipulation |
| [Typer](https://typer.tiangolo.com/) | Modern CLI framework |
| [tqdm](https://tqdm.github.io/) | Progress bars |
| [loguru](https://loguru.readthedocs.io/) | Enhanced logging |

### Optional Dependencies
| Package | Purpose |
|---------|---------|
| pillow-heif | HEIC/HEIF format support |
| ruff | Code linting and formatting |

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
- **CLI Framework** - [Typer](https://typer.tiangolo.com/) by Sebastián Ramírez
- **Progress Bars** - [tqdm](https://tqdm.github.io/) library
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
