# `poc-06/hello` — Linux ELF AArch64 greeter

`hello` is a **166-byte** statically-linked Linux ELF64 executable for
**AArch64**. When run under a Linux ARM64 kernel, or under
`qemu-aarch64-static` on this x86_64 host, it writes:

```text
Hello, arm64!
```

and exits `0`.

This is the repo's first runnable non-x86 ELF target.

## Usage

```bash
cd experiments/poc-06-linux-arm64
qemu-aarch64-static ./hello
```

Verified output:

```text
Hello, arm64!
```

## File layout

The file is:

```text
0x000..0x03f   64   ELF64 header
0x040..0x077   56   single PT_LOAD program header
0x078..0x097   32   executable code (8 instructions)
0x098..0x0a5   14   data string "Hello, arm64!\n"
```

Total size: `64 + 56 + 32 + 14 = 166` bytes.

The program header maps one segment:

- `p_offset = 0`
- `p_vaddr  = 0x400000`
- `p_filesz = 0x00a6`
- `p_memsz  = 0x2000`
- `p_flags  = R|W|X = 7`
- `p_align  = 0x1000`

Entry point: `0x400078`.

The larger `p_memsz` is not needed by this tiny binary itself, but keeping one
simple 8 KiB loadable segment matches the pattern used by the later ARM64 test.

## ELF header bytes

From the built file:

```text
7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
02 00 b7 00 01 00 00 00 78 00 40 00 00 00 00 00
40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 40 00 38 00 01 00 00 00 00 00 00 00
```

Key fields:

- `02 00` = `ET_EXEC`
- `b7 00` = `EM_AARCH64`
- entry = `0x400078`
- program header offset = `0x40`
- ELF header size = `0x40`
- program header entry size = `0x38`
- program header count = `1`

## Program header bytes

```text
01 00 00 00   ; PT_LOAD
07 00 00 00   ; PF_R | PF_W | PF_X
00 00 00 00 00 00 00 00   ; p_offset = 0
00 00 40 00 00 00 00 00   ; p_vaddr  = 0x400000
00 00 40 00 00 00 00 00   ; p_paddr  = 0x400000
a6 00 00 00 00 00 00 00   ; p_filesz = 166
00 20 00 00 00 00 00 00   ; p_memsz  = 0x2000
00 10 00 00 00 00 00 00   ; p_align  = 0x1000
```

## Code bytes at `0x400078`

The body bytes are:

```text
01 01 00 10
20 00 80 d2
c2 01 80 d2
08 08 80 d2
01 00 00 d4
00 00 80 d2
a8 0b 80 d2
01 00 00 d4
```

That is exactly 8 AArch64 instructions.

**Flat listing (hex + mnemonic):**

```text
01 01 00 10   adr   x1, msg
20 00 80 d2   mov   x0, #1
c2 01 80 d2   mov   x2, #14
08 08 80 d2   mov   x8, #64
01 00 00 d4   svc   #0                    ; write(1, msg, 14)
00 00 80 d2   mov   x0, #0
a8 0b 80 d2   mov   x8, #93
01 00 00 d4   svc   #0                    ; exit(0)
```

### Instruction-by-instruction

#### 1. `01 01 00 10` — `adr x1, msg`

Loads the address of the inline string into `x1`.

`msg` is 32 bytes after the entry point, so the resolved address is:

```text
0x400078 + 0x20 = 0x400098
```

#### 2. `20 00 80 d2` — `mov x0, #1`

Sets:

- `x0 = 1` (stdout fd)

#### 3. `c2 01 80 d2` — `mov x2, #14`

Sets:

- `x2 = 14` (string length)

#### 4. `08 08 80 d2` — `mov x8, #64`

Linux AArch64 syscall number:

- `64 = write`

#### 5. `01 00 00 d4` — `svc #0`

Performs:

```text
write(1, 0x400098, 14)
```

On Linux AArch64:

- syscall number is in `x8`
- arguments are in `x0`, `x1`, `x2`, ...

#### 6. `00 00 80 d2` — `mov x0, #0`

Prepares exit status `0`.

#### 7. `a8 0b 80 d2` — `mov x8, #93`

Linux AArch64 syscall number:

- `93 = exit`

#### 8. `01 00 00 d4` — `svc #0`

Performs:

```text
exit(0)
```

## Inline data

At file offset `152` / virtual address `0x400098`:

```text
48 65 6c 6c 6f 2c 20 61 72 6d 36 34 21 0a
```

ASCII:

```text
Hello, arm64!\n
```

The greeting begins at file offset **`152`**, which is the fixed value the
binary test uses later.

## Syscalls used

Exactly two Linux syscalls:

| nr | name   | purpose |
| -- | ------ | ------- |
| 64 | write  | print greeting |
| 93 | exit   | exit cleanly |

No libc, no dynamic loader, no interpreter segment.

## Why this target matters

It proves all of the following are now real in the repo:

- non-x86 machine code
- non-x86 ELF generation
- user-mode emulated execution on the current host
- binary tests that are themselves native to the target architecture
