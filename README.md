# Photo Meta Sync

Keep the date, camera details, and location inside your photos.

Photo Meta Sync creates a new copy of each image with its EXIF metadata preserved. Use photos already on your device or choose them from Google Photos, then download one ZIP that keeps the original file dates when extracted.

![Photo Meta Sync home screen](docs/images/photo-meta-sync-home.png)

## What You Get

- Process individual photos or an entire folder.
- Choose photos from Google Photos without giving the app a cloud backend.
- Preserve EXIF capture date, camera details, and GPS coordinates when available.
- Optionally include a readable JSON metadata sidecar.
- Keep originals unchanged: processed copies use the `_exif` suffix.

## Use The App

1. Open the app and choose **On this device** or **Google Photos**.
2. Select the photos to process. Turn on the JSON option only if you need a separate metadata file.
3. On the results page, choose **Download ZIP** and extract it.

The ZIP is intentional: browsers give individually downloaded files the current date. Extracting the ZIP preserves each photo's capture date as its **file modification date**.

## Download A Release

Download the right file from the [latest GitHub Release](https://github.com/NicoPietrusco/GPhotosMetaSync/releases/latest):

| Your computer | Download |
| --- | --- |
| Mac with Apple Silicon (M1 and later) | `macOS-arm64.dmg` |
| Mac with Intel processor | `macOS-x64.dmg` |
| Windows | `Windows-x64.zip` |

### macOS Notice

The macOS app is currently unsigned, so Gatekeeper may block it after download.

1. Move `Photo Meta Sync.app` into `Applications`.
2. Control-click the app in Finder and choose **Open**.
3. Confirm **Open** in the next dialog.

If macOS still blocks an app you intentionally downloaded from this repository, run:

```bash
xattr -dr com.apple.quarantine "/Applications/Photo Meta Sync.app"
```

## Google Photos And Privacy

The app runs only on your computer at `localhost`. Your Google login and photos are used locally; there is no hosted Photo Meta Sync server.

For a published desktop release, end users only sign in with their Google account. They do not need a Google Cloud project or their own OAuth credentials.

## Supported Formats

JPEG, PNG, TIFF, BMP, WebP, HEIC, and HEIF are accepted. HEIC/HEIF support requires the optional `pillow-heif` dependency when running from source.

## Run From Source

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), and optionally [just](https://github.com/casey/just).

```bash
git clone https://github.com/NicoPietrusco/GPhotosMetaSync.git
cd GPhotosMetaSync
just setup
just web
```

For Google Photos when running from source, follow the maintainer setup in [credentials/README.md](credentials/README.md).

## Development

```bash
just lint
just typecheck
just format
just package
```

The release workflow builds Apple Silicon macOS, Intel macOS, and Windows artifacts when a `v*` tag is pushed.

## License

[MIT](LICENSE)
