# `poc-11/test-hello-ios` — Linux x86_64 verifier for `hello-ios`

`test-hello-ios` is a **284-byte** statically-linked Linux ELF64 x86_64
binary. It structurally tests `./hello-ios` by reading the target bytes into
memory and checking the fixed fields that distinguish the iOS Mach-O artifact:

- Mach-O 64-bit magic at offset `0x000`
- `arm64` CPU type at offset `0x004`
- `MH_EXECUTE` file type at offset `0x00c`
- `LC_BUILD_VERSION` platform word `iOS` at offset `0x070`
- `Hello, iOS!\n` payload at offset `0x09c`

Exit status:

- `0` = pass
- `1` = fail

Verified behavior on this host:

- `./test-hello-ios` exits `0` on the committed `hello-ios`
- changing the platform byte at offset `0x70` from `02` to `01` makes it exit `1`
- restoring the byte returns the result to `0`

## Why this test is Linux ELF

The target itself is an iOS-flavored Mach-O executable, which this Linux host
cannot run directly. Under the repo rules we still need a committed binary
test, so this verifier is a Linux x86_64 machine-code executable that checks the
final file bytes directly.

This is the same strategy already used for other non-Linux artifacts in the
repo, such as the Windows PE and Android APK steps.

## File layout

`tools/mkelf` wraps a `164`-byte body:

```text
0x000..0x077   120   ELF header + PT_LOAD program header
0x078..0x105   142   verifier code
0x106..0x10f    10   path string "hello-ios\0"
0x110..0x11b    12   expected greeting
```

Total file size: `284` bytes.

## Overall logic

Pseudocode:

```text
fd = open("hello-ios", O_RDONLY)
read(fd, 0x401000, 256)

if bytes_read != 168: fail
if *(u32*)(0x401000 + 0x000) != 0xfeedfacf: fail
if *(u32*)(0x401000 + 0x004) != 0x0100000c: fail
if *(u32*)(0x401000 + 0x00c) != 0x00000002: fail
if *(u32*)(0x401000 + 0x070) != 0x00000002: fail
if memcmp(0x40109c, "Hello, iOS!\n", 12) != 0: fail

exit(0)
fail: exit(1)
```

**Control flow:** identical strategy to `test-hello-macos` (Linux ELF opens `./hello-ios`, `read` into `0x401000`, compare magic/header/platform/greeting) but the expected `LC_BUILD_VERSION` platform word and greeting length match the iOS artifact (`12` bytes for `Hello, iOS!\n`).

## Code walkthrough

### Block 1 — open sibling Mach-O

```text
b8 02 00 00 00       mov eax, 2
bf 06 01 40 00       mov edi, 0x400106
31 f6                xor esi, esi
31 d2                xor edx, edx
0f 05                syscall
48 85 c0             test rax, rax
78 6d                js fail
48 89 c3             mov rbx, rax
```

This performs:

```text
open("hello-ios", O_RDONLY, 0)
```

The pathname bytes begin at virtual address `0x400106`.

### Block 2 — read target bytes

```text
31 c0                xor eax, eax
48 89 df             mov rdi, rbx
be 00 10 40 00       mov esi, 0x401000
ba 00 01 00 00       mov edx, 256
0f 05                syscall
48 3d a8 00 00 00    cmp rax, 168
75 51                jne fail
```

So:

```text
read(fd, 0x401000, 256)
```

and then require the exact committed file size `168`.

### Block 3 — verify Mach-O magic

```text
81 3c 25 00 10 40 00 cf fa ed fe    cmp dword [0x401000], 0xfeedfacf
75 44                               jne fail
```

This checks for `MH_MAGIC_64`.

### Block 4 — verify CPU type

```text
81 3c 25 04 10 40 00 0c 00 00 01    cmp dword [0x401004], 0x0100000c
75 37                               jne fail
```

That constant is the Mach-O CPU type for `arm64`.

### Block 5 — verify file type

```text
81 3c 25 0c 10 40 00 02 00 00 00    cmp dword [0x40100c], 0x00000002
75 2a                               jne fail
```

This confirms `MH_EXECUTE`.

### Block 6 — verify platform word

```text
81 3c 25 70 10 40 00 02 00 00 00    cmp dword [0x401070], 0x00000002
75 1d                               jne fail
```

Offset `0x70` is the `platform` field in `LC_BUILD_VERSION`. Value `2` means
`iOS`.

### Block 7 — compare greeting payload

```text
be 9c 10 40 00       mov esi, 0x40109c
bf 10 01 40 00       mov edi, 0x400110
b9 0c 00 00 00       mov ecx, 12
fc                   cld
f3 a6                repe cmpsb
75 09                jne fail
```

This checks the target bytes at file offset `0x9c` against:

```text
Hello, iOS!
```

plus the newline byte.

### Block 8 — success / fail exits

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

### Path at `0x400106`

```text
68 65 6c 6c 6f 2d 69 6f 73 00
```

ASCII:

```text
hello-ios
```

with the terminating zero byte.

### Expected greeting at `0x400110`

```text
48 65 6c 6c 6f 2c 20 69 4f 53 21 0a
```

## Syscalls used

Exactly three Linux x86_64 syscalls:

- `2` = `open`
- `0` = `read`
- `60` = `exit`

## What this test proves

It proves that the committed iOS-target Mach-O artifact:

- uses the 64-bit Mach-O header
- advertises `arm64`
- advertises `MH_EXECUTE`
- carries `LC_BUILD_VERSION platform = iOS`
- still contains the expected greeting payload

It does **not** prove launchability on real iOS devices or simulators. That
will require later Apple-host packaging and signing work.
