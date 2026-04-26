# `poc-06/test-hello` — runnable AArch64 test for `hello`

`test-hello` is a **294-byte** statically-linked Linux ELF64 executable for
**AArch64**. It runs under `qemu-aarch64-static`, opens its sibling `./hello`,
reads the first 192 bytes of that file into memory at `0x401000`, and checks:

1. ELF magic at file bytes `0..3`
2. the first 8 bytes of the greeting payload at file offset `152`
3. the next 4 bytes of the greeting payload at file offset `160`
4. the final 2 bytes of the greeting payload at file offset `164`

Exit status:

- `0` = pass
- `1` = fail

## Usage

```bash
cd experiments/poc-06-linux-arm64
qemu-aarch64-static ./test-hello
echo $?
```

Verified result: `0`.

Also verified by corrupting byte `152` of `hello`; the test then exits `1`,
and returns to `0` after restoring the file.

## File layout

```text
0x000..0x03f   64   ELF header
0x040..0x077   56   PT_LOAD program header
0x078..0x11f  168   code
0x120..0x125    6   data string "hello\0"
```

Total size: `294` bytes.

Like `hello`, it uses one loadable segment:

- base vaddr `0x400000`
- entry `0x400078`
- `p_filesz = 0x126`
- `p_memsz  = 0x2000`
- `p_flags  = 7`

The important design choice here is that `p_memsz` extends far enough to make
address `0x401000` writable, so the test can use that address as its read
buffer.

## Overall logic

Pseudocode:

```text
fd = openat(AT_FDCWD, "hello", O_RDONLY, 0)
read(fd, 0x401000, 192)

if *(u32*)(0x401000 + 0)   != 0x464c457f: fail
if *(u64*)(0x401000 + 152) != 0x61202c6f6c6c6548: fail
if *(u32*)(0x401000 + 160) != 0x34366d72: fail
if *(u16*)(0x401000 + 164) != 0x0a21: fail

exit(0)
fail: exit(1)
```

Those constants decode to:

- `0x464c457f` = ELF magic bytes `7f 45 4c 46`
- `0x61202c6f6c6c6548` = `"Hello, a"`
- `0x34366d72` = `"rm64"`
- `0x0a21` = `"!\n"`

Together they verify the exact greeting bytes:

```text
Hello, arm64!\n
```

## Instruction walk-through

The code begins at `0x400078`.

### Block 1 — open sibling file

First 6 instructions:

```text
60 0c 80 92   mov x0, #-100
21 05 00 10   adr x1, path
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

The result fd is saved:

```text
f3 03 00 aa   mov x19, x0
```

### Block 2 — read first 192 bytes into `0x401000`

```text
e0 03 13 aa   mov x0, x19
01 00 82 d2   movz x1, #0x1000
01 08 a0 f2   movk x1, #0x40, lsl #16
02 18 80 d2   mov x2, #192
e8 07 80 d2   mov x8, #63
01 00 00 d4   svc #0
```

So:

```text
read(fd, 0x401000, 192)
```

The address `0x401000` is synthesised in `x1` with:

- `movz x1, #0x1000`
- `movk x1, #0x40, lsl #16`

which yields exactly `0x0000000000401000`.

### Block 3 — reload buffer base

The test then rebuilds `x1 = 0x401000` again so all later loads use the same
base register.

### Block 4 — verify ELF magic

```text
22 00 40 b9   ldr w2, [x1]
e3 af 88 52   mov w3, #0x457f
83 c9 a8 72   movk w3, #0x464c, lsl #16
5f 00 03 6b   cmp w2, w3
81 02 00 54   b.ne fail
```

`w3` becomes `0x464c457f`, which is the little-endian 32-bit view of:

```text
7f 45 4c 46
```

### Block 5 — verify first 8 greeting bytes at offset `152`

```text
22 4c 40 f9   ldr x2, [x1, #152]
03 a9 8c d2   mov x3, #0x6548
83 8d ad f2   movk x3, #0x6c6c, lsl #16
e3 8d c5 f2   movk x3, #0x2c6f, lsl #32
03 24 ec f2   movk x3, #0x6120, lsl #48
5f 00 03 eb   cmp x2, x3
a1 01 00 54   b.ne fail
```

This constructs:

```text
0x61202c6f6c6c6548
```

which is the 8-byte little-endian word:

```text
48 65 6c 6c 6f 2c 20 61   ; "Hello, a"
```

### Block 6 — verify next 4 bytes at offset `160`

```text
22 a0 40 b9   ldr w2, [x1, #160]
43 ae 8d 52   mov w3, #0x6d72
c3 86 a6 72   movk w3, #0x3436, lsl #16
5f 00 03 6b   cmp w2, w3
01 01 00 54   b.ne fail
```

This checks:

```text
72 6d 36 34   ; "rm64"
```

### Block 7 — verify final 2 bytes at offset `164`

```text
22 48 41 79   ldrh w2, [x1, #164]
23 44 81 52   mov w3, #0x0a21
5f 00 03 6b   cmp w2, w3
81 00 00 54   b.ne fail
```

This checks:

```text
21 0a         ; "!\n"
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

At file offset `288`:

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
| 63 | read   | read first 192 bytes of file |
| 93 | exit   | return pass/fail |

## Why this is a real test

It is not just checking “does a file named `hello` exist?”.

It verifies:

1. the file begins with a real ELF64 header
2. the greeting payload is present at the expected fixed offset
3. the payload bytes themselves are correct

The manual corruption run proved it:

- overwrite file byte `152`
- test exits `1`
- restore byte
- test exits `0`

That makes it a genuine machine-code regression test for the ARM64 target.
