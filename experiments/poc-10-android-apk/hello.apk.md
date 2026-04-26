# `poc-10/hello.apk` — minimal NativeActivity Android APK

`hello.apk` is a **41,493-byte** Android package that launches a real
`android.app.NativeActivity` on Android and loads a machine-code-only native
library named `libhello.so`.

This is the repo's first **actual APK** target. Unlike `poc-09/`, which proved
an Android-relevant native PIE executable format, `poc-10/hello.apk` is a
complete Android package with:

- binary `AndroidManifest.xml`
- `resources.arsc`
- `lib/x86_64/libhello.so`
- `lib/arm64-v8a/libhello.so`
- APK signing metadata

No `classes.dex` is present. The manifest uses `android:hasCode="false"` and
declares `android.app.NativeActivity`, so the app starts entirely from the
native shared library.

## Current verification status

This APK has been verified in four ways:

- `aapt dump badging` reports:
  - package `com.${USER}.machinewelcome.poc10`
  - `sdkVersion:'30'`
  - `targetSdkVersion:'35'`
  - launchable activity `android.app.NativeActivity`
  - native-code ABIs `arm64-v8a` and `x86_64`
- `apksigner verify` accepts the final signed APK
- `adb install -r hello.apk` succeeds on an Android 15 x86_64 emulator
- launching it with:

```text
adb shell am start -W -n com.${USER}.machinewelcome.poc10/android.app.NativeActivity
```

returns:

```text
Status: ok
LaunchState: COLD
Activity: com.${USER}.machinewelcome.poc10/android.app.NativeActivity
TotalTime: 192
WaitTime: 194
Complete
```

The emulator log then records:

```text
nativeloader: Load ... /lib/x86_64/libhello.so ... ok
ActivityTaskManager: Displayed com.${USER}.machinewelcome.poc10/android.app.NativeActivity
```

So the APK is not just structurally valid; it is installed, launched, and the
native library is actually loaded on Android.

## APK contents

`unzip -l hello.apk` shows:

```text
AndroidManifest.xml
resources.arsc
lib/x86_64/libhello.so
lib/arm64-v8a/libhello.so
META-INF/ANDROIDD.SF
META-INF/ANDROIDD.RSA
META-INF/MANIFEST.MF
```

The first local-file header begins with:

```text
50 4b 03 04
```

which is the ZIP signature `PK\x03\x04`.

Important visible offsets in the committed APK:

- file offset `0x001e` — `AndroidManifest.xml`
- file offset `0x0379` — `resources.arsc`
- file offset `0x03d6` — `lib/x86_64/libhello.so`
- file offset `0x4251` — first `ANativeActivity_onCreate` export string
- file offset `0x4596` — `lib/arm64-v8a/libhello.so`
- file offset `0x8251` — second `ANativeActivity_onCreate` export string
- file offset `0x9ff0` — `APK Sig Block 42`

Those are the fixed bytes the companion verifier checks.

## Manifest meaning

The binary manifest encodes the following key choices:

- package name: `com.${USER}.machinewelcome.poc10`
- min SDK: `30`
- target SDK: `35`
- application has no dex bytecode: `android:hasCode="false"`
- app is debuggable
- activity class: `android.app.NativeActivity`
- activity is launcher-exported
- metadata `android.app.lib_name = "hello"`

That metadata is the Android-side interface that matters most here:
`NativeActivity` uses the library name to load `libhello.so` for the current
ABI and resolves the exported symbol:

```text
ANativeActivity_onCreate(ANativeActivity* activity, void* savedState, size_t savedStateSize)
```

## Embedded native libraries

The APK contains **two** ABI-specific native payloads:

### `lib/x86_64/libhello.so`

Used by the x86_64 emulator on this host.

`llvm-readelf -h -l -d -s` reports:

- ELF type `DYN`
- machine `x86-64`
- no entry point (`0`)
- one executable `.text` load segment
- dynamic symbol `ANativeActivity_onCreate`
- no imported shared-library dependencies (`DT_NEEDED` is absent)

The single instruction at file offset `0x2a9` is:

```text
c3
```

which is:

```text
ret
```

So `ANativeActivity_onCreate` immediately returns.

### `lib/arm64-v8a/libhello.so`

Included for real ARM64 Android devices.

`llvm-readelf -h -l -d -s` reports:

- ELF type `DYN`
- machine `AArch64`
- no entry point (`0`)
- dynamic symbol `ANativeActivity_onCreate`
- no imported shared-library dependencies

The first instruction at file offset `0x2ad` is:

```text
c0 03 5f d6
```

which is:

```text
ret
```

So the ARM64 payload implements the same minimal entrypoint behavior as the
x86_64 payload.

## Why the native code is so small

The goal of `poc-10` is to prove the full Android packaging and deployment path,
not to build a UI framework yet.

The APK therefore relies on Android's built-in `NativeActivity` app-layer code
to:

- start the process
- load the correct `libhello.so` for the current ABI
- resolve `ANativeActivity_onCreate`

Our own machine code does the minimum possible work for that interface:

- export the required symbol
- return immediately

That is enough for the activity to launch successfully, which the emulator demo
proved.

## External binary tooling used

Per repo rule 6, the APK was packaged and demonstrated using external prebuilt
binary tools that are **not** committed:

- Android SDK `aapt2`
- Android SDK `zipalign`
- Android SDK `apksigner`
- Android SDK `adb`
- Android Emulator
- Android NDK `llvm-objcopy`
- Android NDK target `clang` drivers
- JDK `keytool`

The machine-code source of truth for the native payloads is still the literal
opcode bytes:

- x86_64: `c3`
- AArch64: `c0 03 5f d6`

The external toolchain only wrapped those bytes into shared-library and APK
container formats.
