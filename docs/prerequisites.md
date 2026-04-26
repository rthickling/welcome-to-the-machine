# Host Prerequisites

The repo is intentionally light on dependencies, but a few non-base tools are
needed to run every current target or inspect binaries comfortably.

| Tool / Package | Purpose |
| --- | --- |
| `binutils` | Provides `objdump` and related binary-inspection tools used throughout the docs. |
| `file` | Identifies generated binaries by container and architecture. |
| `xxd` | Converts literal hex bytes to binaries and helps inspect raw output; on some distros it comes from `vim-common`. |
| `wget` | Downloads the Android command-line tools archive in the setup example below. |
| `unzip` | Extracts the Android command-line tools archive in the setup example below. |
| `qemu-user-static` | Runs committed non-x86 native targets in `experiments/poc-06-linux-arm64/`, `experiments/poc-07-riscv64/`, and `experiments/poc-09-android-elf/`. |
| `wasmtime` | Runs the WebAssembly / WASI targets in `experiments/poc-05-wasm-wasi/`. |
| `wine64` | Lets you directly execute Windows PE binaries on Linux. |
| Android SDK / NDK binaries | Required for the APK packaging and emulator demo in `experiments/poc-10-android-apk/`. |

For Ubuntu/Debian, the practical install set is:

```bash
sudo apt install binutils file xxd wget unzip qemu-user-static wine64
```

`wasmtime` is usually installed separately as a prebuilt binary runtime rather
than from the base distro image. Under rule 2, it should be installed as an
existing binary artifact, not via a temporary helper script written in the
workflow.

One way to install it is:

```bash
curl https://wasmtime.dev/install.sh -sSf | bash
```

For the Android APK work, the practical requirement is the official prebuilt
Android SDK / NDK package set, installed under an SDK root such as
`$HOME/android-sdk`.

```bash
mkdir -p "$HOME/android-sdk/cmdline-tools"
cd /tmp
cmdline_tools_zip="commandlinetools-linux-14742923_latest.zip"
wget "https://dl.google.com/android/repository/${cmdline_tools_zip}"
unzip "$cmdline_tools_zip"
mv cmdline-tools "$HOME/android-sdk/cmdline-tools/latest"
export ANDROID_SDK_ROOT="$HOME/android-sdk"
export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$PATH"
```

Then install the packages:

```bash
yes | sdkmanager --licenses
sdkmanager "platform-tools" \
           "platforms;android-35" \
           "build-tools;35.0.0" \
           "emulator" \
           "system-images;android-35;default;x86_64" \
           "ndk;27.2.12479018"
```

Those provide `adb`, `aapt` / `aapt2`, `zipalign`, `apksigner`, the Android
emulator and x86_64 system image, and NDK LLVM tools such as `llvm-objcopy` and
target `clang`.

## Target Runtime Notes

| Target | What you need |
| --- | --- |
| Linux x86_64 command-line experiments | Normal x86_64 Linux system. |
| X11 experiments and `products/notes/targets/linux/x86_64` | Live X11 session with matching X server socket and Xauthority details. |
| WebAssembly / WASI experiments | `wasmtime`. |
| Linux ARM64, RISC-V, Android-style ELF experiments | `qemu-user-static`. |
| Windows PE experiments and product targets | Windows loader, typically `wine64` on Linux. |
| Android APK experiments and product targets | Android SDK / NDK binaries above, plus either the Android emulator or a real `adb`-connected device. |
| Apple runtime execution | Not yet demonstrated; current Apple verification is structural on Linux only. |

No compiler, assembler, linker, or interpreter is required to use the committed
artifacts in this repo.
