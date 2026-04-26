# `poc-11/test-hello-macos` — Linux x86_64 verifier for `hello-macos`

`test-hello-macos` is a **288-byte** statically-linked Linux ELF64 x86_64
binary. It does **not** execute the Mach-O target. Instead it opens
`./hello-macos`, reads the whole file into memory at `0x401000`, and checks the
fixed bytes that matter for this POC:

- Mach-O 64-bit magic at offset `0x000`
- `arm64` CPU type at offset `0x004`
- `MH_EXECUTE` file type at offset `0x00c`
- `LC_BUILD_VERSION` platform word `macOS` at offset `0x070`
- `Hello, macOS!\n` payload at offset `0x09c`

Exit status:

- `0` = pass
- `1` = fail

Verified behavior on this host:

- `./test-hello-macos` exits `0` on the committed `hello-macos`
- changing the byte at offset `0x70` from `01` to `02` makes it exit `1`
- restoring the original byte makes it return to `0`

## Why this test is Linux ELF

The target is an Apple Mach-O binary, but the repo rules still require a
machine-code test that runs on the current host. So this verifier is a Linux
x86_64 executable that checks the committed Mach-O bytes directly.

That gives us:

- a real machine-code test binary
- fast feedback on Linux
- deterministic regression coverage for the important Apple metadata bytes

## File layout

`tools/mkelf` wraps a `168`-byte body:

```text
0x000..0x077   120   ELF header + PT_LOAD program header
0x078..0x105   142   verifier code
0x106..0x111    12   path string "hello-macos\0"
0x112..0x11f    14   expected greeting
```

Total file size: `288` bytes.

## Overall logic

Pseudocode:

```text
fd = open("hello-macos", O_RDONLY)
read(fd, 0x401000, 256)

if bytes_read != 170: fail
if *(u32*)(0x401000 + 0x000) != 0xfeedfacf: fail
if *(u32*)(0x401000 + 0x004) != 0x0100000c: fail
if *(u32*)(0x401000 + 0x00c) != 0x00000002: fail
if *(u32*)(0x401000 + 0x070) != 0x00000001: fail
if memcmp(0x40109c, "Hello, macOS!\n", 14) != 0: fail

exit(0)
fail: exit(1)
```

**Control flow:** standard **`open` → `read` → `cmp` / `repe cmpsb` → `exit`** pattern on x86_64 Linux syscalls: `test-hello-macos` never runs the Mach-O; it only byte-matches the committed file after mapping it at `0x401000`. Success uses `sys_exit` with `edi = 0`; any failed check shares the `fail` path with `edi = 1`.

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
open("hello-macos", O_RDONLY, 0)
```

The pathname bytes live at virtual address `0x400106`.

### Block 2 — read target bytes

```text
31 c0                xor eax, eax
48 89 df             mov rdi, rbx
be 00 10 40 00       mov esi, 0x401000
ba 00 01 00 00       mov edx, 256
0f 05                syscall
48 3d aa 00 00 00    cmp rax, 170
75 51                jne fail
```

So:

```text
read(fd, 0x401000, 256)
```

and then require that exactly `170` bytes were read, matching the committed
file size.

### Block 3 — verify Mach-O magic

```text
81 3c 25 00 10 40 00 cf fa ed fe    cmp dword [0x401000], 0xfeedfacf
75 44                               jne fail
```

This checks the first four bytes:

```text
cf fa ed fe
```

which is `MH_MAGIC_64`.

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

This checks that the target is `MH_EXECUTE`.

### Block 6 — verify platform word

```text
81 3c 25 70 10 40 00 01 00 00 00    cmp dword [0x401070], 0x00000001
75 1d                               jne fail
```

Offset `0x70` is the `platform` field inside `LC_BUILD_VERSION`. Value `1`
means `macOS`.

### Block 7 — compare greeting payload

```text
be 9c 10 40 00       mov esi, 0x40109c
bf 12 01 40 00       mov edi, 0x400112
b9 0e 00 00 00       mov ecx, 14
fc                   cld
f3 a6                repe cmpsb
75 09                jne fail
```

This compares the 14 bytes at target offset `0x9c` against the embedded string:

```text
Hello, macOS!
```

plus the trailing newline byte.

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
68 65 6c 6c 6f 2d 6d 61 63 6f 73 00
```

ASCII:

```text
hello-macos
```

followed by a terminating `00`.

### Expected greeting at `0x400112`

```text
48 65 6c 6c 6f 2c 20 6d 61 63 4f 53 21 0a
```

## Syscalls used

Exactly three Linux x86_64 syscalls:

- `2` = `open`
- `0` = `read`
- `60` = `exit`

## What this test proves

It proves that the committed macOS-target Mach-O artifact:

- starts with the correct 64-bit Mach-O magic
- advertises `arm64`
- advertises `MH_EXECUTE`
- carries `LC_BUILD_VERSION platform = macOS`
- still contains the expected greeting payload

It does **not** prove full execution on macOS. That later runtime step will
need Apple-host tooling or hardware.
