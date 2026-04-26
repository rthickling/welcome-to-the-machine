# Windows GUI Product Plan

This file covers both Windows product targets:

- `notes-win64.exe`
- `notes-winarm64.exe`

## Goal

Deliver the same user-visible note workflow as the Linux reference build, but
through native Win32 GUI behavior rather than raw X11:

- left editor pane
- right first-word list
- click list item to load note into the editor
- `Enter` saves the current editor contents
- normal printable ASCII input, including uppercase letters and shifted symbols
- simple pane borders with readable foreground/background colours

## Starting point

The repo's current Windows precedent is a console PE in
[`../../../experiments/poc-08-windows-pe/hello.exe.md`](../../../experiments/poc-08-windows-pe/hello.exe.md). That is useful as a PE
container/import-table reference only. The product itself needs a real windowed
subsystem path.

## Required Windows-specific work

For `notes-win64.exe` first, then `notes-winarm64.exe`:

1. `PE32+` / ARM64 GUI executable container
2. Win32 window creation and message loop
3. keyboard input handling
4. mouse hit-testing on the note list pane
5. native text drawing for labels, editor contents, and list rows
6. file I/O against the shared `notes.db` format
7. border drawing for the editor/list panes
8. foreground/background colour setup matching the simple product colour policy

## Shared product behavior

The Windows versions should keep:

- same record format from [`../contract.md`](../contract.md)
- same first-word derivation rule
- same append-on-Enter behavior used by the Linux reference build
- same printable ASCII editing policy as the Linux reference build
- same visible pane separation and contrast requirements

## Delivery order

1. Windows x86_64
2. Windows ARM64 after the x86_64 GUI behavior is stable

## Testing

Each Windows artifact should ship with:

- one committed machine-code verifier binary
- one detailed `.md`
- one test `.md`

Like the current Windows POC, the first automated checks can be Linux x86_64
structural verifiers. Runtime proof can be added separately via `wine64` for
x86_64 and a later Windows ARM64 test path when practical.

The first structural verifier should anchor at least:

- window title / visible label strings
- printable input dispatch or translation table bytes
- colour constants or Win32 brush/pen setup bytes
- border drawing path bytes
