# Tauri Icons

Tauri requires platform-specific application icons in this directory before
building desktop installers. The `tauri.conf.json` references:

- `icons/32x32.png` — Linux small icon
- `icons/128x128.png` — Linux standard icon
- `icons/128x128@2x.png` — Linux high-DPI icon
- `icons/icon.icns` — macOS icon set
- `icons/icon.ico` — Windows multi-resolution icon

## How to generate icons

Install the Tauri CLI and run the icon generator:

```powershell
cd frontend/atomreasonx
npm install
npx tauri icon path/to/your/source-image.png
```

The source image should be a square PNG, at least 1024x1024, with transparency.
`tauri icon` generates all required formats automatically.

Until real icons are added, Tauri builds will fail at the bundling stage.
The CI workflow does not build desktop installers (it only validates structure).
The release workflow will fail if icons are missing — add them before tagging a release.
