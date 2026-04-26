# Cross-Platform Notes Product

This directory holds the product-oriented note-taking deliverables for the repo.

## Product Docs

| File | Purpose |
| --- | --- |
| [`contract.md`](contract.md) | Shared behavior, storage model, and UI rules for the product. |
| [`glossary.md`](glossary.md) | Product and raw-X11 terms used by the notes docs. |
| [`docs-and-tests.md`](docs-and-tests.md) | Per-artifact documentation and test strategy. |
| [`plans/`](plans/) | Platform-specific implementation plans. |

## Targets

Each target directory keeps the executable, its byte-level Markdown explanation,
the verifier binary, and the verifier Markdown together.

| Target | Status | Directory |
| --- | --- | --- |
| Linux x86_64 | Raw-X11 reference build with printable input, uppercase/symbols, borders, colors, load, save, and delete. | [`targets/linux/x86_64/`](targets/linux/x86_64/) |
| Linux ARM64 | GUI scaffold/container and structural verifier. | [`targets/linux/arm64/`](targets/linux/arm64/) |
| Windows x86_64 | Runnable two-pane Win32 GUI with editor, list, `Add`, and `Delete`. | [`targets/windows/x86_64/`](targets/windows/x86_64/) |
| Windows ARM64 | GUI-subsystem scaffold/container and structural verifier. | [`targets/windows/arm64/`](targets/windows/arm64/) |
| macOS arm64 | Mach-O GUI scaffold/container and structural verifier. | [`targets/apple/macos-arm64/`](targets/apple/macos-arm64/) |
| iOS arm64 | Mach-O GUI scaffold/container and structural verifier. | [`targets/apple/ios-arm64/`](targets/apple/ios-arm64/) |
| Android | NativeActivity APK with native framebuffer-rendered panes and structural verifier. | [`targets/android/`](targets/android/) |
| WebAssembly | Browser-hosted Wasm GUI module and structural verifier. | [`targets/wasm/`](targets/wasm/) |

Browser runner files for the Wasm target live in [`runners/web/`](runners/web/).

## Current Linux x86_64 Behavior

The reference build provides the requested core interaction pattern:

- a left editor pane for the full note text
- `Enter` saves the current left-pane note
- a right-side alphabetical list derived from the first words of stored notes
- mouse clicks on the right-side list load a note into the left pane
- each visible right-pane row also shows a `Del` affordance on its far right
- normal printable ASCII input, including shifted uppercase letters and symbols
- a dark window background with light text and simple pane borders

The Linux build keeps the existing tiny record format inherited from the repo's
earlier note tools. Clicking a note loads it for amendment, clicking `Del`
rewrites `notes.db` from the current in-memory list so the deletion persists,
and pressing `Enter` stores the current editor contents as a new note record in
the shared database.

## Verification

Run target verifiers from their target directories:

```bash
cd products/notes/targets/linux/x86_64
./test-notes-linux-x86_64
./test-notes-linux-x86_64-clicks

cd ../arm64
./test-notes-linux-arm64

cd ../../windows/x86_64
./test-notes-win64

cd ../arm64
./test-notes-winarm64

cd ../../apple/macos-arm64
./test-notes-macos

cd ../ios-arm64
./test-notes-ios

cd ../../android
./test-notes-android

cd ../wasm
./test-notes-web
```
