# `poc-09/test-hello` — AArch64 verifier for the Android-style PIE target

`test-hello` is a **302-byte** statically-linked Linux ELF64 executable for
**AArch64**. It runs under `qemu-aarch64-static`, opens its sibling `./hello`,
reads the first 192 bytes of that file into memory at `0x401000`, and checks:

1. ELF magic at file bytes `0..3`
2. ELF type at file bytes `16..17` is `ET_DYN`
3. the first 8 greeting bytes at file offset `152`
4. the final 8 greeting bytes at file offset `160`

Exit status:

- `0` = pass
- `1` = fail

This makes the Android-style target testable on the current Linux host without
requiring an Android device or Android emulator image.

## Usage

```bash
cd experiments/poc-09-android-elf
qemu-aarch64-static ./test-hello
echo $?
```

Verified result: `0`.

Also verified by corrupting the target's ELF type bytes at file offset `0x10`
from `03 00` to `02 00`; the test then exits `1`, and returns to `0` after the
original bytes are restored.

## Why this test is `ET_EXEC`

The target binary is Android-style `ET_DYN` / PIE.

The test binary itself is a simpler fixed-address AArch64 Linux ELF runner. That
lets it use the same easy absolute read buffer (`0x401000`) as `poc-06` while
still validating the Android-specific property we care about: `hello` must be
`ET_DYN`, not `ET_EXEC`.

## File layout

```text
0x000..0x03f   64   ELF header
0x040..0x077   56   PT_LOAD program header
0x078..0x127  176   code
0x128..0x12d    6   data string "hello\0"
```

Total size: `302` bytes.

Like the earlier AArch64 test, it uses one loadable segment:

- base vaddr `0x400000`
- entry `0x400078`
- `p_filesz = 0x12e`
- `p_memsz  = 0x2000`
- `p_flags  = 7`

The writable load segment extends far enough to make address `0x401000`
available for the `read()` buffer.

## Overall logic

Pseudocode:

```text
fd = openat(AT_FDCWD, "hello", O_RDONLY, 0)
read(fd, 0x401000, 192)

if *(u32*)(0x401000 + 0)   != 0x464c457f: fail
if *(u16*)(0x401000 + 16)  != 0x0003: fail
if *(u64*)(0x401000 + 152) != 0x61202c6f6c6c6548: fail
if *(u64*)(0x401000 + 160) != 0x0a2164696f72646e: fail

exit(0)
fail: exit(1)
```

Those constants decode to:

- `0x464c457f` = ELF magic bytes `7f 45 4c 46`
- `0x0003` = `ET_DYN`
- `0x61202c6f6c6c6548` = `"Hello, a"`
- `0x0a2164696f72646e` = `"ndroid!\n"`

Together the last two checks verify:

```text
Hello, android!\n
```

**Control flow:** same AArch64 “openat → read(192) @ 0x401000 → constant loads + `cmp` + `b.ne fail`” shape as `poc-06/test-hello`, but the checks add **`ET_DYN`** at ELF header halfword `0x10` and split the 16-byte greeting into two 8-byte compares at offsets `152` and `160`. The fail and success epilogues are `mov x0, {0|1}` / `mov x8, #93` / `svc #0` (`exit`).

## Instruction walk-through

The code begins at `0x400078`.

### Block 1 — open sibling file

First 6 instructions:

```text
60 0c 80 92   mov x0, #-100
61 05 00 10   adr x1, path
02 00 80 d2   mov x2, #0
03 00 80 d2   mov x3, #0
08 07 80 d2   mov x8, #56
01 00 00 d4   svc #0
```

This performs:

```text
openat(AT_FDCWD, "hello", O_RDONLY, 0)
```

On AArch64 Linux:

- syscall `56` = `openat`
- `AT_FDCWD = -100`

The returned fd is saved:

```text
f3 03 00 aa   mov x19, x0
```

### Block 2 — read first 192 bytes into `0x401000`

```text
e0 03 13 aa   mov x0, x19
e1 00 82 d2   movz x1, #0x1000
01 08 a0 f2   movk x1, #0x40, lsl #16
02 18 80 d2   mov x2, #192
e8 07 80 d2   mov x8, #63
01 00 00 d4   svc #0
```

So:

```text
read(fd, 0x401000, 192)
```

The address `0x401000` is synthesized in `x1` with:

- `movz x1, #0x1000`
- `movk x1, #0x40, lsl #16`

### Block 3 — rebuild buffer base

The same two instructions appear again:

```text
e1 00 82 d2
01 08 a0 f2
```

so all later loads can use `x1 = 0x401000` as the buffer base.

### Block 4 — verify ELF magic

```text
22 00 40 b9   ldr  w2, [x1]
e3 af 88 52   mov  w3, #0x457f
83 c9 a8 72   movk w3, #0x464c, lsl #16
5f 00 03 6b   cmp  w2, w3
a1 02 00 54   b.ne fail
```

That checks:

```text
7f 45 4c 46
```

### Block 5 — verify ELF type is `ET_DYN`

```text
22 20 40 79   ldrh w2, [x1, #16]
63 00 80 52   mov  w3, #3
5f 00 03 6b   cmp  w2, w3
21 02 00 54   b.ne fail
```

This is the Android-specific check that distinguishes `poc-09/hello` from the
earlier fixed-address ARM64 `ET_EXEC` target in `poc-06/`.

### Block 6 — verify first 8 greeting bytes at offset `152`

```text
22 4c 40 f9   ldr  x2, [x1, #152]
03 a9 8c d2   mov  x3, #0x6548
83 8d ad f2   movk x3, #0x6c6c, lsl #16
e3 8d c5 f2   movk x3, #0x2c6f, lsl #32
03 24 ec f2   movk x3, #0x6120, lsl #48
5f 00 03 eb   cmp  x2, x3
41 01 00 54   b.ne fail
```

This constructs:

```text
0x61202c6f6c6c6548
```

which is the 8-byte little-endian word:

```text
48 65 6c 6c 6f 2c 20 61   ; "Hello, a"
```

### Block 7 — verify final 8 greeting bytes at offset `160`

```text
22 50 40 f9   ldr  x2, [x1, #160]
c3 8d 8c d2   mov  x3, #0x646e
43 ee ad f2   movk x3, #0x6f72, lsl #16
23 8d cc f2   movk x3, #0x6469, lsl #32
23 44 e1 f2   movk x3, #0x0a21, lsl #48
5f 00 03 eb   cmp  x2, x3
41 00 00 54   b.ne fail
```

This checks:

```text
6e 64 72 6f 69 64 21 0a   ; "ndroid!\n"
```

### Block 8 — pass / fail exits

Pass block:

```text
00 00 80 d2   mov x0, #0
a8 0b 80 d2   mov x8, #93
01 00 00 d4   svc #0
```

Fail block:

```text
20 00 80 d2   mov x0, #1
a8 0b 80 d2   mov x8, #93
01 00 00 d4   svc #0
```

Syscall `93` is `exit`.

## Embedded data

At file offset `296`:

```text
68 65 6c 6c 6f 00
```

ASCII:

```text
hello\0
```

The opening `adr x1, path` resolves to that inline pathname.

## Syscalls used

Exactly three Linux AArch64 syscalls:

| nr | name   | purpose |
| -- | ------ | ------- |
| 56 | openat | open sibling `hello` |
| 63 | read   | read first 192 bytes |
| 93 | exit   | return pass/fail |

## What this test proves

It proves that the committed Android-style target:

- starts with a real ELF header
- is `ET_DYN` rather than `ET_EXEC`
- contains the expected `Hello, android!\n` payload at the fixed offsets

Combined with the separate execution check:

```bash
qemu-aarch64-static ./hello
```

it gives both structural verification and real execution on the current host.
