# Linux ARM64 Product Plan

This file defines the next native Linux target after the x86_64 reference build:

- binary name: `notes-linux-arm64`
- format: Linux ELF64 AArch64
- UI stack: raw X11 wire protocol, matching the Linux x86_64 product behavior

## Goal

Port the current Linux product behavior from
[`../targets/linux/x86_64/notes-linux-x86_64.md`](../targets/linux/x86_64/notes-linux-x86_64.md)
to ARM64 while preserving:

- same `notes.db` record format
- same two-pane layout concept
- same right-pane first-word list
- same click-to-load behavior
- same `Enter` save behavior
- normal printable ASCII editing, including shifted uppercase and symbols
- simple pane borders plus readable foreground/background colours

## Reuse from existing repo work

- ARM64 ELF baseline: [`../../../experiments/poc-06-linux-arm64/hello.md`](../../../experiments/poc-06-linux-arm64/hello.md)
- Android-style ARM64 ELF / tooling precedent: [`../../../experiments/poc-09-android-elf/hello.md`](../../../experiments/poc-09-android-elf/hello.md)
- Linux X11 GUI reference: [`../targets/linux/x86_64/notes-linux-x86_64.md`](../targets/linux/x86_64/notes-linux-x86_64.md), [`../../../experiments/poc-04-notes-x11/note-edit.md`](../../../experiments/poc-04-notes-x11/note-edit.md)

## Implementation notes

The Linux ARM64 product should mirror the x86_64 structure:

1. socket + connect to the X11 Unix socket
2. send setup request with baked cookie
3. patch request templates with runtime resource ids
4. load and sort notes from `notes.db`
5. draw editor pane and list pane
6. handle `KeyPress`, `Expose`, and `ButtonPress`
7. append current note buffer to `notes.db` on `Enter`
8. translate the ARM64/X11 key path through the same printable ASCII policy as
   the x86_64 reference build, including Shift state for uppercase and symbols
9. draw pane borders and use the same simple dark-background/light-foreground
   colour policy unless the target X server requires a different pixel format

## Testing

The target binary should have:

- `test-notes-linux-arm64`
- runnable under `qemu-aarch64-static`

The first test should at minimum validate:

- anchored window title bytes
- left-pane label bytes
- right-pane header bytes
- colour constants used by the X11 window / GC templates
- printable key translation anchors
- border drawing request anchors

Later tests can add ARM64-native behavioral smoke checks if the X11 runtime path
is stable enough under emulation.
