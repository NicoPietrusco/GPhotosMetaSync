# Contributing to Hic Pic Nunc

Thanks for contributing to Hic Pic Nunc!

This guide covers the local development setup, project structure, checks, and workflow for contributing changes.

## Setup

### Prerequisites

You will need:

* Python 3.11
* [`uv`](https://docs.astral.sh/uv/)
* [`just`](https://github.com/casey/just)

Clone the repository and enter the project directory:

```bash
git clone https://github.com/NicoPietrusco/HicPicNunc.git
cd HicPicNunc
```

Create the development environment and install dependencies:

```bash
just setup
```

This creates a Python 3.11 virtual environment and installs the development dependencies.

### Google Photos OAuth setup

When running Hic Pic Nunc from source, you need your own Google OAuth Desktop client. The release OAuth client is not shared for development.

Follow the setup instructions in [`docs/google-oauth-setup.md`](docs/google-oauth-setup.md) to create and configure your Desktop OAuth client.

After setup, start the local web application with:

```bash
just web
```

You can also verify the local setup with:

```bash
just verify
```

## Project layout

The main source code is organized as follows:

```text
src/hicpicnunc/
├── core/
├── google_photos/
└── web/
```

* `src/hicpicnunc/core/` — EXIF processing, metadata field selection, and export jobs.
* `src/hicpicnunc/google_photos/` — Google OAuth and Google Photos Picker API client.
* `src/hicpicnunc/web/` — Flask app factory, routes, templates, and static files.
* `tests/` — Mirrors `src/hicpicnunc/`; tests use the `*_test.py` naming convention.
* `packaging/` — PyInstaller configuration for desktop releases.

## Checks

Before opening a pull request, run the project's quality checks:

```bash
just lint
just typecheck
just test
```

If you change anything under `.github/`, also run `just lint-workflows`. Pin new actions to a full commit SHA with the version as a comment (`uses: owner/action@<sha> # v1.2.3`), and set `persist-credentials: false` on `actions/checkout`.

You can format the source code with:

```bash
just format
```

To build the desktop package locally:

```bash
just package
```

CI runs on Ubuntu, Windows, and macOS, so changes should work across all supported platforms.

## Development workflow

* Create your branch from `main`.
* Keep commits small and use clear commit messages.
* Do not push directly to `main`.
* Open a pull request when your changes are ready for review.
* Pull requests are rebase-merged.

Before submitting a pull request, make sure the relevant checks pass locally.

## Privacy

Hic Pic Nunc handles Google Photos data locally, so privacy-related changes require special care.

If a change:

* adds a new network call, or
* adds a new Google API scope,

update [`site/privacy.html`](site/privacy.html) in the same change so that the privacy policy accurately describes the application's behavior.

Please also mention the relevant privacy-policy update in your pull request.

## Pull requests and issues

Use the provided GitHub issue and pull request templates when opening issues or pull requests. Include enough detail for another contributor to reproduce, review, or test the change.
