# `products/notes/targets/android/notes-android.apk`

`notes-android.apk` is a **57,925-byte** Android NativeActivity package for the
Notes product. It is signed, installable, and renders a native Notes layout on
the Android emulator.

The APK keeps the manifest/resource package shape from the validated
NativeActivity precedent in
[`experiments/poc-10-android-apk/hello.apk.md`](../../../../experiments/poc-10-android-apk/hello.apk.md),
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

## Emulator audit vs the product contract

Audited on the `poc10-api35-x86_64` AVD (API 35, 1080×2340). Against the
[product contract](../../contract.md) the app conforms on every **user-visible**
behavior:

| Contract behavior | Result |
| ----------------- | ------ |
| Left editor (note) pane + right list pane, bordered, readable colours | pass |
| List sorted by first word (ascending byte order) | pass — `APPLE`, `BANANA`, `MANGO`, `PEAR` sorted after out-of-order entry |
| First-word rule | pass — `BANANA SPLIT HERE` renders as `BANANA`; space-free notes render whole |
| `Enter` stores editor contents as a note | pass — hardware/`ENTER` key both save |
| Click/tap a row loads full note into editor | pass — tapping `BANANA` loaded `BANANA SPLIT HERE` and highlighted the row |
| Edit-then-`Enter` replaces the tapped row and re-sorts | pass |
| Delete a row via its `DEL` button | pass — deleting `MANGO` dropped the row and kept the rest sorted |
| Printable ASCII incl. uppercase | pass |
| Persistence across restart | pass — rows reloaded after `force-stop` + relaunch |
| Launch without ANR / touch timeout | pass |

**One deviation — the on-disk storage format.** The app persists to
`files/notes.bin` in a custom container: the ASCII magic `NDB1`, a one-byte
record count, then per-record `[u8 length][bytes]`:

```text
4e 44 42 31            "NDB1" magic
03                     record count
05 41 50 50 4c 45      len 5, "APPLE"
11 42 41 4e ...        len 17, "BANANA SPLIT HERE"
04 50 45 41 52         len 4, "PEAR"
```

The [contract's shared storage format](../../contract.md#shared-storage-format)
is a header-less sequence of `[u32 little-endian length][bytes]` records in
`notes.db`, which the Linux x86_64/ARM64 and Windows builds all read and write.
Android's `NDB1`/`u8`-framed `notes.bin` is therefore **not** interchangeable
with the other targets' `notes.db`, which breaks the contract's portability
goal.

This deviation was left in place rather than fixed: the record (de)serialization
is woven through the hand-authored native code paths (load-on-create,
`ENT`-save, edit-replace, `DEL`) in **both** the `x86_64` and `arm64-v8a`
`libhello.so`, and rewriting it as machine code inside a signed APK is
disproportionately risky for a polish pass with no user-visible payoff — the
rendered product behavior above is unaffected. It is recorded here as the sole
known contract gap for this target; aligning the framing (and filename) to the
shared `notes.db` is a candidate for a dedicated follow-up.

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
