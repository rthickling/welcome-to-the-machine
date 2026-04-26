# `poc-07/test-hello` — runnable RISC-V 64 test for `hello`

`test-hello` is a **470-byte** statically-linked Linux ELF64 executable for
**RISC-V 64-bit**. It runs under `qemu-riscv64-static`, opens its sibling
`./hello`, reads the first 192 bytes of that file into memory at `0x401000`,
and verifies:

1. ELF magic bytes `7f 45 4c 46`
2. the greeting payload bytes `Hello, rv64!\n` at file offset `156`
3. one byte of the pointer-building `addi a1, a1, 32` instruction at file
   offset `131`, so the specific earlier pointer bug is caught too

Exit status:

- `0` = pass
- `1` = fail

## Usage

```bash
cd experiments/poc-07-riscv64
qemu-riscv64-static ./test-hello
echo $?
```

Verified result: `0`.

Also verified by corrupting file byte `131` of `hello` (the high byte of the
`addi a1, a1, 32` instruction). The test then exits `1`, and returns to `0`
after restoring the original byte.

## File layout

```text
0x000..0x03f   64   ELF header
0x040..0x077   56   PT_LOAD program header
0x078..0x1cf  344   code
0x1d0..0x1d5    6   data string "hello\0"
```

Total size: `470` bytes.

Like `hello`, it uses one loadable segment with:

- base `0x400000`
- entry `0x400078`
- `p_filesz = 0x1d6`
- `p_memsz  = 0x2000`
- `e_flags  = 0x5`

The 8 KiB segment is large enough that address `0x401000` is valid writable
memory for the file read buffer.

## High-level logic

Pseudocode:

```text
fd = openat(AT_FDCWD, "hello", O_RDONLY, 0)
read(fd, 0x401000, 192)

acc = 0
for each checked byte:
    acc |= (actual ^ expected)

exit(acc != 0)
```

Using an accumulated XOR/OR result avoids conditional branches entirely. That
keeps the code relocation-free and easy to encode by hand.

## What bytes are checked

### ELF magic

At file offsets `0..3`:

```text
7f 45 4c 46
```

### Greeting payload

At file offsets `156..168`:

```text
48 65 6c 6c 6f 2c 20 72 76 36 34 21 0a
```

ASCII:

```text
Hello, rv64!\n
```

### Code-byte guard for the pointer bug

At file offset `131`, the correct `hello` build contains byte:

```text
02
```

That is the top byte of the instruction:

```text
93 85 05 02   ; addi a1, a1, 32
```

The broken build used:

```text
93 85 c5 01   ; addi a1, a1, 28
```

so checking byte `131 == 0x02` makes this exact regression fail the test.

## Register / syscall usage

### Open sibling file

The first block performs:

```text
openat(AT_FDCWD, "hello", O_RDONLY, 0)
```

using:

- `a0 = -100`
- `a1 = &"hello\0"`
- `a2 = 0`
- `a3 = 0`
- `a7 = 56`

Linux RV64 syscall `56` is `openat`.

### Read file contents

Then:

```text
read(fd, 0x401000, 192)
```

using:

- `a0 = fd`
- `a1 = 0x401000`
- `a2 = 192`
- `a7 = 63`

Linux RV64 syscall `63` is `read`.

The buffer base `0x401000` is synthesised by:

```text
lui a1, 0x401
```

and later reloaded into `t0` with:

```text
lui t0, 0x401
```

## Byte-check loop shape

Every check uses the same 4-instruction pattern:

```text
lbu t1, OFFSET(t0)
li  t2, EXPECTED
xor t1, t1, t2
or  t3, t3, t1
```

So:

- matching byte -> XOR result `0`
- mismatching byte -> non-zero bits propagate into `t3`

At the end:

```text
sltu a0, zero, t3
li   a7, 93
ecall
```

If `t3 == 0`, `a0 = 0`. Otherwise `a0 = 1`.

Linux RV64 syscall `93` is `exit`.

## Embedded pathname

At file offset `464`:

```text
68 65 6c 6c 6f 00
```

ASCII:

```text
hello\0
```

The opening `auipc` / `addi` pair resolves `a1` to that inline string.

## Syscalls used

Exactly three Linux RV64 syscalls:

| nr | name   | purpose |
| -- | ------ | ------- |
| 56 | openat | open sibling `hello` |
| 63 | read   | read first 192 bytes of file |
| 93 | exit   | return pass/fail |

## Why this is a real test

The original RV64 test was too weak: it checked the payload bytes but not the
PC-relative pointer instruction, so a broken `hello` could still pass.

The current test is stronger because it now checks both:

- the payload itself
- one code byte inside the pointer-fixing instruction

That means the actual bug that produced:

```text
s\0\0\0Hello, rv
```

is now caught by the test binary itself.
