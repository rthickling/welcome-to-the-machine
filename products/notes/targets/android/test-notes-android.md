# `products/notes/targets/android/test-notes-android`

`test-notes-android` is a **1064-byte** Linux x86_64 ELF structural verifier for
`./notes-android.apk`.

It performs nineteen fixed-offset `pread64` checks:

```text
0x0000, length 0x04   APK local-file ZIP signature
0x001e, length 0x16   lib/x86_64/libhello.so
0x4521, length 0x12   ANativeWindow_lock
0x4534, length 0x19   AInputQueue_attachLooper
0x4579, length 0x14   AInputQueue_getEvent
0x459f, length 0x13   AInputEvent_getType
0x45b3, length 0x13   AKeyEvent_getAction
0x45fd, length 0x15   AKeyEvent_getKeyCode
0x4612, length 0x11   AMotionEvent_getX
0x4624, length 0x11   AMotionEvent_getY
0x465b, length 0x18   ANativeActivity_onCreate
0x4674, length 0x07   libc.so
0x4681, length 0x0d   libandroid.so
0x4890, length 0x60   Notes interaction anchor prefix
0x7336, length 0x19   lib/arm64-v8a/libhello.so
0x8534, length 0x19   ARM64 AInputQueue_attachLooper
0x8612, length 0x11   ARM64 AMotionEvent_getX
0x865b, length 0x18   ARM64 ANativeActivity_onCreate
0x8888, length 0x60   ARM64 Notes interaction anchor prefix
```

The checked interaction anchor prefix is:

```text
Notes Android native framebuffer panes Add Delete GlyphFont OnScreenKeyboard EnterSave DeleteButtons TopEnterKey
```

The APK also embeds the raised, non-overlapping Enter hit-region, sorted Notes,
zero-initialized note-editing, and persistence anchors documented in
`notes-android.apk.md`.

For each descriptor, the verifier reads the target range from the APK into a
stack buffer, compares it with the embedded expected bytes using `repe cmpsb`,
and exits non-zero on open, read, or compare failure.

Run:

```bash
cd products/notes/targets/android
./test-notes-android
```
