# `poc-07/hello` — Linux ELF RISC-V 64 greeter

`hello` is a **169-byte** statically-linked Linux ELF64 executable for
**RISC-V 64-bit**. Under a Linux RV64 kernel, or under
`qemu-riscv64-static` on this x86_64 host, it writes:

```text
Hello, rv64!
```

and exits `0`.

## Usage

```bash
cd experiments/poc-07-riscv64
qemu-riscv64-static ./hello
```

Verified output:

```text
Hello, rv64!
```

## File layout

```text
0x000..0x03f   64   ELF64 header
0x040..0x077   56   single PT_LOAD program header
0x078..0x09b   36   executable code (9 RV64I instructions)
0x09c..0x0a8   13   data string "Hello, rv64!\n"
```

Total file size: `169` bytes.

The program header maps one segment:

- `p_offset = 0`
- `p_vaddr  = 0x400000`
- `p_filesz = 0x00a9`
- `p_memsz  = 0x2000`
- `p_flags  = 7` (`R|W|X`)
- `p_align  = 0x1000`

Entry point: `0x400078`

ELF `e_flags = 0x5`, meaning:

- RVC bit set
- double-float ABI

That matches the local toolchain's standard RV64 output format.

## ELF header

First 64 bytes:

```text
7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
02 00 f3 00 01 00 00 00 78 00 40 00 00 00 00 00
40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
05 00 00 00 40 00 38 00 01 00 00 00 00 00 00 00
```

Important fields:

- `02 00` = `ET_EXEC`
- `f3 00` = `EM_RISCV`
- entry = `0x400078`
- `e_flags = 0x00000005`

## Program header

Bytes `0x40..0x77`:

```text
01 00 00 00   ; PT_LOAD
07 00 00 00   ; PF_R | PF_W | PF_X
00 00 00 00 00 00 00 00   ; p_offset = 0
00 00 40 00 00 00 00 00   ; p_vaddr = 0x400000
00 00 40 00 00 00 00 00   ; p_paddr = 0x400000
a9 00 00 00 00 00 00 00   ; p_filesz = 169
00 20 00 00 00 00 00 00   ; p_memsz  = 0x2000
00 10 00 00 00 00 00 00   ; p_align  = 0x1000
```

## Code bytes at `0x400078`

Raw bytes:

```text
13 05 10 00
97 05 00 00
93 85 05 02
13 06 d0 00
93 08 00 04
73 00 00 00
13 05 00 00
93 08 d0 05
73 00 00 00
```

**Flat listing (hex + mnemonic):**

```text
13 05 10 00   addi  a0, zero, 1          ; stdout fd
97 05 00 00   auipc a1, 0
93 85 05 02   addi  a1, a1, 32           ; &msg (PC-relative)
13 06 d0 00   addi  a2, zero, 13        ; length
93 08 00 04   addi  a7, zero, 64        ; __NR_write
73 00 00 00   ecall
13 05 00 00   addi  a0, zero, 0         ; status 0
93 08 d0 05   addi  a7, zero, 93        ; __NR_exit
73 00 00 00   ecall
```

### Instruction-by-instruction, with encodings

RISC-V instructions here are fixed 32-bit words stored **little-endian**, so
file bytes `13 05 10 00` are the word `0x00100513`. Only three encodings are
used:

- **`ADDI rd, rs1, imm`** (I-type): `imm[31:20] rs1[19:15] 000[14:12]
  rd[11:7] 0010011[6:0]`. With `rs1 = zero` (x0, hardwired 0) this is a plain
  load-immediate; the low byte of every `addi` word here is `13` or `93`
  because opcode `0010011` = `0x13` and `rd` spills one bit into byte 1.
- **`AUIPC rd, imm20`** (U-type): `imm[31:12] rd[11:7] 0010111[6:0]`.
  Adds `imm20 << 12` to the current PC — with `imm20 = 0` it just copies PC
  into `rd`. This is how position-relative addressing is done without a
  dedicated `adr` instruction.
- **`ECALL`**: the SYSTEM word `0x00000073` — traps into the Linux kernel.

Register numbers used: `a0` = x10, `a1` = x11, `a2` = x12, `a7` = x17.

#### 1. `13 05 10 00` — `addi a0, zero, 1`

Word `0x00100513`: opcode `0x13`, `rd` (bits 11–7) = 10 (`a0`), `rs1`
(bits 19–15) = 0 (`zero`), `imm` (bits 31–20) = 1.
Sets `a0 = 1` — the stdout file descriptor (syscall arg 1).

#### 2. `97 05 00 00` — `auipc a1, 0`

Word `0x00000597`: opcode `0x17` (AUIPC), `rd` = 11 (`a1`), `imm20` = 0.
Loads the address of this instruction into `a1`:

```text
a1 = PC = 0x40007c
```

#### 3. `93 85 05 02` — `addi a1, a1, 32`

Word `0x02058593`: `rd` = 11 (`a1`), `rs1` = 11 (`a1`), `imm` = `0x020` = 32.
Completes the PC-relative address:

```text
a1 = 0x40007c + 0x20 = 0x40009c   ; address of "Hello, rv64!\n"
```

Note the offset is measured from the `auipc` at `0x40007c`, not from the
entry point. This corrected `+32` immediate is important: an earlier bad
build used `+28`, which pointed 4 bytes too early and printed part of the
final `ecall` word.

#### 4. `13 06 d0 00` — `addi a2, zero, 13`

Word `0x00d00613`: `rd` = 12 (`a2`), `rs1` = 0, `imm` = 13.
Sets `a2 = 13` — the byte length of `"Hello, rv64!\n"` (syscall arg 3).

#### 5. `93 08 00 04` — `addi a7, zero, 64`

Word `0x04000893`: `rd` = 17 (`a7`), `imm` = `0x040` = 64.
On Linux RV64 the syscall number goes in `a7`; `64 = write` (RISC-V shares
the generic Linux syscall table with AArch64, so `write`/`exit` are 64/93 on
both, unlike x86_64's 1/60).

#### 6. `73 00 00 00` — `ecall`

Traps into the kernel. With `a7 = 64`, `a0 = 1`, `a1 = 0x40009c`, `a2 = 13`
this performs:

```text
write(1, 0x40009c, 13)
```

The return value comes back in `a0` and is ignored.

#### 7. `13 05 00 00` — `addi a0, zero, 0`

Word `0x00000513`: `rd` = 10 (`a0`), `imm` = 0. Prepares exit status `0`.

#### 8. `93 08 d0 05` — `addi a7, zero, 93`

Word `0x05d00893`: `rd` = 17 (`a7`), `imm` = `0x05d` = 93 = `exit`.

#### 9. `73 00 00 00` — `ecall`

Performs:

```text
exit(0)
```

Nothing executes past this word; the string data follows immediately.

## Inline data

At file offset **`156`** / virtual address `0x40009c`:

```text
48 65 6c 6c 6f 2c 20 72 76 36 34 21 0a
```

ASCII:

```text
Hello, rv64!\n
```

## Syscalls used

Exactly two Linux RV64 syscalls:

| nr | name  | purpose |
| -- | ----- | ------- |
| 64 | write | print greeting |
| 93 | exit  | exit cleanly |

No libc, no interpreter, no dynamic linker.
