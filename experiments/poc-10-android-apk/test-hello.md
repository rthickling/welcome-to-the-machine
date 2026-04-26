# `poc-10/test-hello` — Linux x86_64 verifier for `hello.apk`

`test-hello` is a **539-byte** statically-linked Linux ELF64 x86_64 binary.
It opens its sibling `./hello.apk`, reads up to `65536` bytes into memory at
`0x401000`, and checks fixed bytes in the final committed APK.

Exit status:

- `0` = pass
- `1` = fail

Verified behavior:

- `./test-hello` exits `0` on the committed `hello.apk`
- corrupting the first byte of the `APK Sig Block 42` string at file offset
  `0x9ff0` makes the test exit `1`
- restoring the original byte makes the test return to `0`

## What it checks

The verifier checks all of the following:

1. ZIP local-header magic `PK\x03\x04` at file offset `0x0000`
2. `AndroidManifest.xml` at file offset `0x001e`
3. `resources.arsc` at file offset `0x0379`
4. `lib/x86_64/libhello.so` at file offset `0x03d6`
5. `ANativeActivity_onCreate` at file offset `0x4251`
6. `lib/arm64-v8a/libhello.so` at file offset `0x4596`
7. a second `ANativeActivity_onCreate` at file offset `0x8251`
8. `APK Sig Block 42` at file offset `0x9ff0`

That makes it a deterministic structural test for:

- ZIP/APK container shape
- binary manifest/resource presence
- both embedded native ABI payloads
- exported NativeActivity entrypoint symbol text in both `.so` files
- presence of the APK signing block

## Why this test is Linux x86_64

The APK itself is an Android package, so it cannot run directly as a normal
Linux executable. Under the repo rules we still need a committed binary test,
so the test is a Linux x86_64 verifier that checks the final APK bytes
directly.

This mirrors the approach used in `poc-08/`, where a host-side verifier checks
the committed bytes of a non-ELF/non-Linux artifact.

The Android runtime proof is separate and is provided by:

```bash
adb install hello.apk
adb shell am start -W -n com.${USER}.machinewelcome.poc10/android.app.NativeActivity
```

## File layout

`tools/mkelf` wraps a `419`-byte body in its normal 120-byte ELF shell:

```text
0x000..0x077   120   ELF header + PT_LOAD program header
0x078..0x17e   263   code
0x17f..0x18a    12   path string "hello.apk\0\0\0"
0x18b..0x19d    19   "AndroidManifest.xml"
0x19e..0x1ab    14   "resources.arsc"
0x1ac..0x1c1    22   "lib/x86_64/libhello.so"
0x1c2..0x1d9    24   "ANativeActivity_onCreate"
0x1da..0x1f2    25   "lib/arm64-v8a/libhello.so"
0x1f3..0x20a    24   "ANativeActivity_onCreate"
0x20b..0x21a    16   "APK Sig Block 42"
```

Total file size:

```text
120 + 419 = 539 bytes
```

`readelf -h -l` reports:

- ELF type `EXEC`
- machine `x86-64`
- entry `0x400078`
- one load segment
- `p_filesz = 0x21b`
- `p_memsz  = 0x1021b`

The oversized `p_memsz` allows the verifier to use buffer address `0x401000`.

## Overall logic

Pseudocode:

```text
fd = open("hello.apk", O_RDONLY)
read(fd, 0x401000, 65536)

if bytes_read < 0xa000: fail
if *(u32*)(0x401000 + 0x0000) != 0x04034b50: fail

if memcmp(0x40101e, "AndroidManifest.xml", 19) != 0: fail
if memcmp(0x401379, "resources.arsc", 14) != 0: fail
if memcmp(0x4013d6, "lib/x86_64/libhello.so", 22) != 0: fail
if memcmp(0x405251, "ANativeActivity_onCreate", 24) != 0: fail
if memcmp(0x405596, "lib/arm64-v8a/libhello.so", 25) != 0: fail
if memcmp(0x409251, "ANativeActivity_onCreate", 24) != 0: fail
if memcmp(0x40aff0, "APK Sig Block 42", 16) != 0: fail

exit(0)
fail: exit(1)
```

**Control flow:** `syscall` with `open(2)` opens `hello.apk` from the embedded path; `read(2)` fills `0x401000..` and the test requires at least `0xa000` bytes so offset `0x9ff0` is valid. The x86_64 code then does one `cmp` on the ZIP magic and seven **`mov esi/edi; mov ecx; cld; repe cmpsb`** memcmp blocks against embedded expected strings, each **`jne fail`**. The epilogue is **`mov eax, 60` / `xor edi, edi` / `syscall`** (success) or **`mov edi, 1`** (failure) for `exit(2)`.

## Instruction walk-through

### Block 1 — open sibling APK

```text
b8 02 00 00 00       mov eax, 2
bf 7f 01 40 00       mov edi, 0x40017f
31 f6                xor esi, esi
31 d2                xor edx, edx
0f 05                syscall
48 85 c0             test rax, rax
0f 88 e2 00 00 00    js fail
48 89 c3             mov rbx, rax
```

This performs:

```text
open("hello.apk", O_RDONLY, 0)
```

The pathname string starts at virtual address `0x40017f`.

### Block 2 — read the APK into memory

```text
31 c0                xor eax, eax
48 89 df             mov rdi, rbx
be 00 10 40 00       mov esi, 0x401000
ba 00 00 01 00       mov edx, 65536
0f 05                syscall
48 3d 00 a0 00 00    cmp rax, 0xa000
0f 82 c2 00 00 00    jb fail
```

So:

```text
read(fd, 0x401000, 65536)
```

The test requires at least `0xa000` bytes because the latest checked marker,
`APK Sig Block 42`, begins at file offset `0x9ff0`.

### Block 3 — verify ZIP magic

```text
81 3c 25 00 10 40 00 50 4b 03 04    cmp dword [0x401000], 0x04034b50
0f 85 b1 00 00 00                   jne fail
```

This checks:

```text
50 4b 03 04
```

which is the ZIP local file header magic.

### Blocks 4–10 — fixed-string comparisons

Each block follows the same structure:

```text
be <buffer-offset-address>
bf <embedded-string-address>
b9 <length>
fc
f3 a6
0f 85 <fail-rel32>
```

That sequence means:

- load the APK buffer address in `esi`
- load the embedded expected string address in `edi`
- load the exact byte count in `ecx`
- `cld`
- `repe cmpsb`
- fail if any byte differs

The seven fixed comparisons are:

#### Block 4 — manifest entry name

```text
memcmp(0x40101e, "AndroidManifest.xml", 19)
```

#### Block 5 — resources entry name

```text
memcmp(0x401379, "resources.arsc", 14)
```

#### Block 6 — x86_64 library entry name

```text
memcmp(0x4013d6, "lib/x86_64/libhello.so", 22)
```

#### Block 7 — first exported NativeActivity symbol string

```text
memcmp(0x405251, "ANativeActivity_onCreate", 24)
```

#### Block 8 — ARM64 library entry name

```text
memcmp(0x405596, "lib/arm64-v8a/libhello.so", 25)
```

#### Block 9 — second exported NativeActivity symbol string

```text
memcmp(0x409251, "ANativeActivity_onCreate", 24)
```

#### Block 10 — APK signing block marker

```text
memcmp(0x40aff0, "APK Sig Block 42", 16)
```

### Block 11 — success / fail exits

Success:

```text
b8 3c 00 00 00       mov eax, 60
31 ff                xor edi, edi
0f 05                syscall
```

Fail:

```text
b8 3c 00 00 00       mov eax, 60
bf 01 00 00 00       mov edi, 1
0f 05                syscall
```

Linux syscall `60` is `exit`.

## Embedded literals

Packed after the code are the eight expected byte sequences:

### Path at `0x40017f`

```text
68 65 6c 6c 6f 2e 61 70 6b 00 00 00
```

ASCII:

```text
hello.apk\0\0\0
```

### Expected strings

At:

- `0x40018b` — `AndroidManifest.xml`
- `0x40019e` — `resources.arsc`
- `0x4001ac` — `lib/x86_64/libhello.so`
- `0x4001c2` — `ANativeActivity_onCreate`
- `0x4001da` — `lib/arm64-v8a/libhello.so`
- `0x4001f3` — `ANativeActivity_onCreate`
- `0x40020b` — `APK Sig Block 42`

## Syscalls used

Exactly three Linux x86_64 syscalls:

| nr | name | purpose |
| -- | ---- | ------- |
| 2  | open | open sibling `hello.apk` |
| 0  | read | read the APK bytes |
| 60 | exit | return pass/fail |

## What this test proves

It proves that the committed APK:

- starts with a ZIP/APK local-file header
- contains the binary manifest and `resources.arsc`
- contains both `x86_64` and `arm64-v8a` native library entries
- contains the exported `ANativeActivity_onCreate` symbol text in both native
  libraries
- contains an APK signing block

It does **not** by itself prove runtime behavior on Android. That separate proof
comes from the emulator run, which successfully installed, launched, and focused
the app.
