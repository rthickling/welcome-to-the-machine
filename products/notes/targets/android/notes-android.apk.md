# `products/notes/targets/android/notes-android.apk`

`notes-android.apk` is a **57,925-byte** Android NativeActivity package for the
Notes product. It is signed, installable, and renders a native Notes layout on
the Android emulator.

The APK keeps the manifest/resource package shape from the validated
NativeActivity precedent in
[`../../../../experiments/poc-10-android-apk/hello.apk`](../../../../experiments/poc-10-android-apk/hello.apk.md),
but replaces the old one-instruction native libraries with real machine-code
payloads for both emulator/device ABIs.

## APK contents

```text
AndroidManifest.xml
resources.arsc
lib/x86_64/libhello.so
lib/arm64-v8a/libhello.so
META-INF/ANDROIDD.SF
META-INF/ANDROIDD.RSA
META-INF/MANIFEST.MF
```

Native library sizes:

```text
lib/x86_64/libhello.so       13080 bytes
lib/arm64-v8a/libhello.so    14232 bytes
```

The manifest still launches:

```text
com.richard.machinewelcome.poc10/android.app.NativeActivity
```

and still names the native library `hello`, so Android loads the ABI-specific
`libhello.so`.

## Native implementation

Both native libraries export:

```text
ANativeActivity_onCreate
```

`ANativeActivity_onCreate` no longer returns immediately. It:

1. reads `activity->callbacks`
2. installs one machine-code callback for:
   - `onNativeWindowCreated`
   - `onNativeWindowResized`
   - `onNativeWindowRedrawNeeded`
   - `onInputQueueCreated`
   - `onInputQueueDestroyed`
3. calls `ANativeActivity_setWindowFormat(activity, 1)`

The draw callback imports and calls:

```text
ANativeWindow_lock
ANativeWindow_unlockAndPost
```

It locks the `ANativeWindow_Buffer`, reads `width`, `height`, `stride`, and
`bits`, then writes 32-bit pixels directly into the framebuffer.

The input callback path imports and calls:

```text
pthread_create
ALooper_prepare
ALooper_pollOnce
AInputQueue_attachLooper
AInputQueue_detachLooper
AInputQueue_getEvent
AInputQueue_finishEvent
AInputEvent_getType
AKeyEvent_getAction
AKeyEvent_getKeyCode
AMotionEvent_getX
AMotionEvent_getY
ANativeActivity_showSoftInput
open
read
write
close
```

`onInputQueueCreated` starts a small looper thread and attaches the Android input
queue to it. The callback drains every pending event and finishes it as handled,
which prevents touch input from timing out the activity. It also asks Android to
show the soft keyboard when input arrives.

The input callback handles both key and touch events. Hardware/ADB key events
for `A`..`Z`, `0`..`9`, space, backspace, and Enter are accepted. Touch events
drive the app-drawn keyboard, the app-drawn `ENT` key, the raised visible
`ENTER` save region, and the right-pane `DEL` buttons. The raised `ENTER` and
`DEL` regions sit above the keyboard rows so their hit boxes do not overlap
normal character keys.

Accepted text is appended to a small native editor buffer and redrawn through a
tiny 5x7 bitmap font. `ENT` saves the current editor buffer, sorts the in-memory
note rows in ascending byte order, and clears the editor. A right-pane `DEL`
button deletes that saved row.

Tapping the body of a saved note row copies that note into the left editor and
highlights the row. The next `ENT` replaces the tapped row, re-sorts the notes,
and exits edit mode.

Saved rows are persisted in the activity's app-private data directory as
`notes.bin`. The native code reads that file during `ANativeActivity_onCreate`
and rewrites it after every add, edit, or delete.

## Rendered UI

The framebuffer renderer draws the visible Notes product shape:

- dark app background
- bordered left editor pane
- bordered right notes pane
- highlighted list rows
- app-drawn on-screen keyboard
- app-drawn `DEL` and `ENT` keys
- right-pane `DEL` buttons for saved notes

The native payload also embeds this verifier anchor:

```text
Notes Android native framebuffer panes Add Delete
GlyphFont
OnScreenKeyboard
EnterSave
DeleteButtons
TopEnterKey
RaisedEnterButton
NonOverlappingHit
SortedNotes
EditNote
ZeroEditState
PersistNotes
```

This Android implementation currently renders the product layout, launches
cleanly, drains touch input without an ANR, accepts app-drawn on-screen keyboard
taps, saves text into the right pane with the top-row `ENT` key or visible
bottom `ENTER` button, keeps the right-pane rows sorted, supports tap-to-edit
for saved rows, deletes right-pane rows with their `DEL` buttons, and reloads
saved rows after app restart.

## Verification

`test-notes-android` checks the APK ZIP signature, both ABI library filenames,
`ANativeActivity_setWindowFormat`, input queue imports, x86_64 key-event imports,
motion-event imports, `ANativeActivity_onCreate`, `libc.so`, `libandroid.so`,
and the full Notes interaction anchor in both native libraries.

Run:

```bash
cd products/notes/targets/android
./test-notes-android
```

Install and launch on an emulator:

```bash
adb install -r notes-android.apk
adb shell am start -n com.richard.machinewelcome.poc10/android.app.NativeActivity
```

If an older copy was installed with a different signing key, uninstall first:

```bash
adb uninstall com.richard.machinewelcome.poc10
adb install notes-android.apk
```
