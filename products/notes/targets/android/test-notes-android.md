# `products/notes/targets/android/test-notes-android`

`test-notes-android` is a **1064-byte** Linux x86_64 ELF structural verifier
for `./notes-android.apk`. It opens the APK, reads nineteen fixed byte ranges
with `pread64`, compares each against embedded expected bytes with
`repe cmpsb`, and exits non-zero on any open, read, or compare failure.

## Machine code

The executable code (`0x400078..0x4000fc`) is the shared descriptor-driven
verifier documented opcode-by-opcode in
[`../linux/x86_64/test-notes-linux-x86_64.md`](../linux/x86_64/test-notes-linux-x86_64.md#code-walk-through).
Per-target values only:

| Register | Value | Meaning |
| -------- | ----- | ------- |
| `edi` at `0x40007d` | `0x400100` | path string `"notes-android.apk\0"` |
| `r12d` at `0x400094` | `0x400114` | descriptor-table base |
| `r13d` at `0x40009a` | `0x13` | descriptor count (19) |

## Descriptor table (19 × 12 bytes @ `0x400114`)

Each row is `{u32 file_offset, u32 length, u32 expected_VA}`. The expected bytes
live contiguously from `0x4001f8` onward (the `expected_VA` column below):

```text
 # file_off  len   exp_VA    what
 0  0x0000   0x04  0x4001f8  APK local-file ZIP signature (PK\3\4)
 1  0x001e   0x16  0x4001fc  "lib/x86_64/libhello.so"
 2  0x4521   0x12  0x400214  ANativeWindow_lock
 3  0x4534   0x18  0x400228  AInputQueue_attachLooper
 4  0x4579   0x14  0x400240  AInputQueue_getEvent
 5  0x459f   0x13  0x400254  AInputEvent_getType
 6  0x45b3   0x13  0x400268  AKeyEvent_getAction
 7  0x45fd   0x14  0x40027c  AKeyEvent_getKeyCode
 8  0x4612   0x11  0x400290  AMotionEvent_getX
 9  0x4624   0x11  0x4002a4  AMotionEvent_getY
10  0x465b   0x18  0x4002b8  ANativeActivity_onCreate
11  0x4674   0x07  0x4002d0  libc.so
12  0x4681   0x0d  0x4002d8  libandroid.so
13  0x4890   0x70  0x4002e8  Notes interaction anchor prefix (x86_64 .so)
14  0x7336   0x19  0x400358  "lib/arm64-v8a/libhello.so"
15  0x8534   0x18  0x400374  ARM64 AInputQueue_attachLooper
16  0x8612   0x11  0x40038c  ARM64 AMotionEvent_getX
17  0x865b   0x18  0x4003a0  ARM64 ANativeActivity_onCreate
18  0x8888   0x70  0x4003b8  ARM64 Notes interaction anchor prefix
```

## Interaction anchor prefix

Descriptors 13 and 18 each compare a 0x70-byte (112-byte) block naming the
native-side behaviours, present once per ABI (`x86_64` and `arm64-v8a`):

```text
Notes Android native framebuffer panes Add Delete GlyphFont OnScreenKeyboard EnterSave DeleteButtons TopEnterKey
```

The APK also embeds the raised, non-overlapping Enter hit-region, sorted notes,
zero-initialized note-editing, and persistence anchors described in
[`notes-android.apk.md`](notes-android.apk.md).

## What the checks prove

Because the APK is a ZIP container, the verifier reads raw file offsets rather
than parsing ZIP structures: descriptor 0 confirms the ZIP magic, descriptors
1 and 14 confirm both native libraries are stored at their expected offsets for
both ABIs, and descriptors 2–12 / 15–17 confirm each `libhello.so` imports the
exact NDK entry points (`ANativeActivity_onCreate`, the `AInputQueue` /
`AKeyEvent` / `AMotionEvent` families) that a native-activity Notes app needs.

## Run

```bash
cd products/notes/targets/android
./test-notes-android
```
