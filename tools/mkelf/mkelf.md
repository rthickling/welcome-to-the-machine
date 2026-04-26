# `tools/mkelf/mkelf` — Minimal ELF64 Wrapper

A 349-byte hand-hexed Linux ELF64 x86_64 executable that reads arbitrary
bytes on stdin and emits a complete, runnable ELF64 executable on stdout.
It is this repo's equivalent of a minimal linker: it eliminates the
120-byte ELF-header-plus-program-header boilerplate that every POC would
otherwise have to hand-type.

## Contract

```
mkelf < body.bin > prog
```

- **Input:** raw code + data bytes that are meant to start at virtual
  address `0x400078` and run as a flat, single-segment program.
- **Output:** a valid `ELF64` executable whose 120-byte header is
  followed verbatim by the input bytes.
- Output `p_filesz` = `0x78 + len(body)`.
- Output `p_memsz` = `p_filesz + 0x10000` (64 KiB of BSS slack for
  buffers / stacks / event reads).
- Output `p_flags` = `R|W|X` (7). Writable because every non-trivial
  program in this repo patches its own data region at runtime.
- Output entry point is fixed at `0x400078`.
- Unbounded input is streamed in 16 KiB chunks up to an internal
  ~1 MiB buffer. Anything larger will segfault the tool.

No libraries linked, no Xlib, no libc; just seven direct Linux syscalls.

## Example

Build a 12-byte `exit(42)` program:

```bash
echo 'b83c000000bf2a0000000f05' | xxd -r -p | ./mkelf > exit42
chmod +x exit42
./exit42 ; echo $?        # → 42
```

Rebuild an existing POC's body (no need to retype its header):

```bash
dd if=experiments/poc-01-greeter/test-hello bs=1 skip=120 | ./mkelf > test-hello.rebuilt
chmod +x test-hello.rebuilt                # functionally identical
```

## File layout (349 bytes)

| File offset | Size | Vaddr       | Contents                                   |
|------------:|-----:|:------------|:-------------------------------------------|
| `0x000`     | 64   | `0x400000`  | ELF64 header                               |
| `0x040`     | 56   | `0x400040`  | Program header (single `PT_LOAD`, R+W+X)   |
| `0x078`     | 109  | `0x400078`  | Executable code                            |
| `0x0E5`     | 120  | `0x4000E5`  | Output template (ELF header + phdr stub)   |

Beyond the file (`0x15d`..`0x100000` in memory) is BSS: ~1 MiB of
zero-initialised buffer at `0x401000` into which stdin is read.

## ELF64 header — bytes `0x00`–`0x3F`

Identical structure to every other POC: entry `0x400078`, phoff `0x40`,
phnum 1, no section headers.

```
7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
02 00 3e 00 01 00 00 00 78 00 40 00 00 00 00 00
40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 40 00 38 00 01 00 00 00 00 00 00 00
```

## Program header — bytes `0x40`–`0x77`

`p_flags=7` (R|W|X) because the code patches its own output template at
runtime. `p_filesz=0x15d` covers code and template. `p_memsz=0x100000`
reserves 1 MiB from `p_vaddr`, which is what gives us the ~1 MiB stdin
buffer at `0x401000`.

```
01 00 00 00  07 00 00 00                        p_type=PT_LOAD, p_flags=7
00 00 00 00 00 00 00 00                         p_offset = 0
00 00 40 00 00 00 00 00                         p_vaddr  = 0x400000
00 00 40 00 00 00 00 00                         p_paddr  = 0x400000
5d 01 00 00 00 00 00 00                         p_filesz = 0x15d
00 00 10 00 00 00 00 00                         p_memsz  = 0x100000
00 10 00 00 00 00 00 00                         p_align  = 0x1000
```

## Code — `0x78`–`0xE4`

Registers used across syscalls: `rbx` = constant buffer base
(`0x401000`), `rbp` = running total of bytes read. Both are callee-saved
so they survive every Linux syscall.

### 1. Initialise

```
78: 31 ed                   xor ebp, ebp           ; total = 0
7a: bb 00 10 40 00          mov ebx, 0x00401000    ; buffer base
```

### 2. Read loop — drain stdin into the buffer

```
7f: 31 c0                   xor eax, eax           ; __NR_read = 0
81: 31 ff                   xor edi, edi           ; fd = stdin
83: 48 89 de                mov rsi, rbx
86: 48 01 ee                add rsi, rbp           ; rsi = buf + total
89: ba 00 40 00 00          mov edx, 0x4000        ; 16 KiB per read
8e: 0f 05                   syscall
90: 48 85 c0                test rax, rax
93: 7e 05                   jle +5 → 0x9a          ; <=0 bytes → done
95: 48 01 c5                add rbp, rax           ; total += bytes read
98: eb e5                   jmp -27 → 0x7f         ; back to top
```

Short reads on stdin are totally fine — every iteration appends whatever
the kernel handed us. Either EOF (return 0) or a real error (return -1,
which is negative, and `JLE` catches both via its ≤ test) ends the loop.

### 3. Patch the output template with real sizes

```
9a: 48 8d 45 78             lea rax, [rbp+0x78]           ; filesz = total + 0x78
9e: 48 89 04 25 45 01 40 00 mov [0x00400145], rax         ; template.p_filesz
a6: 48 05 00 00 01 00       add rax, 0x10000              ; memsz = filesz + 64 KiB
ac: 48 89 04 25 4d 01 40 00 mov [0x0040014d], rax         ; template.p_memsz
```

`0x400145` and `0x40014d` are the runtime addresses of the `p_filesz` /
`p_memsz` slots inside our in-memory copy of the output template
(`0x4000e5 + 0x60` and `0x4000e5 + 0x68` respectively). Since our
`p_flags` includes `W`, these stores succeed without segfaulting.

The SIB form `48 89 04 25 <disp32>` is how x86_64 expresses "write to
absolute 32-bit address": `0x25` is the SIB byte `scale=0, index=none,
base=disp32-only`.

### 4. Emit the 120-byte header

```
b4: b8 01 00 00 00          mov eax, 1             ; __NR_write
b9: bf 01 00 00 00          mov edi, 1             ; fd = stdout
be: be e5 00 40 00          mov esi, 0x004000e5    ; &template
c3: ba 78 00 00 00          mov edx, 120
c8: 0f 05                   syscall
```

### 5. Emit the body bytes

```
ca: b8 01 00 00 00          mov eax, 1
cf: bf 01 00 00 00          mov edi, 1
d4: 48 89 de                mov rsi, rbx           ; buffer base
d7: 48 89 ea                mov rdx, rbp           ; total bytes read
da: 0f 05                   syscall
```

This assumes Linux honours the full-size write in a single call (up to
~2 GiB, per `write(2)`). For our pipeline inputs of ≤ 1 MiB this is
always true.

### 6. `exit(0)`

```
dc: b8 3c 00 00 00          mov eax, 60            ; __NR_exit
e1: 31 ff                   xor edi, edi           ; status = 0
e3: 0f 05                   syscall
```

No error path: if any `read`/`write` fails, we still fall through to
`exit(0)` because we don't check their return values once inside the
loop. A production version would propagate errors, but this POC is
intended to be fed pipeline-friendly stdin.

## Data — output template at `0x0E5` (120 bytes)

The template is a literal copy of a valid ELF64 header + single
`PT_LOAD` program header, with `p_filesz` and `p_memsz` zeroed out. Those
two fields are overwritten at runtime by the `mov [disp32], rax` stores
in step 3 before the template is written to stdout.

```
7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00     ELF ident
02 00 3e 00 01 00 00 00 78 00 40 00 00 00 00 00     e_type..e_entry
40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00     e_phoff, e_shoff
00 00 00 00 40 00 38 00 01 00 00 00 00 00 00 00     flags..e_shstrndx
01 00 00 00 07 00 00 00 00 00 00 00 00 00 00 00     p_type, p_flags, p_offset
00 00 40 00 00 00 00 00 00 00 40 00 00 00 00 00     p_vaddr, p_paddr
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00     p_filesz, p_memsz (patched)
00 10 00 00 00 00 00 00                             p_align = 0x1000
```

## Self-hosting

`mkelf` can rebuild itself:

```bash
dd if=mkelf bs=1 skip=120 | mkelf > mkelf-v2
```

`mkelf-v2` is byte-identical to `mkelf` except that its `p_memsz` is
`0x1015d` (`filesz + 0x10000`) instead of the original's `0x100000`.
Both values are sufficient for any realistic use, and `mkelf-v2` can
itself be used to build `mkelf-v3`, etc. — a genuinely self-hosting
toolchain with no external assembler or linker.

This is the strongest possible validation of correctness: the tool
transports its own source bytes through its own transformation and
produces a working copy.

## Limits and caveats

- **Input size cap.** The stdin buffer lives at `0x401000` inside a
  `0x100000`-sized memory segment. Inputs larger than ~1 MiB will overrun
  the segment and crash with `SIGSEGV`. For larger binaries, increase
  this binary's own `p_memsz` (file offset `0x68`).
- **No seeking.** The output is produced in one forward pass — safe to
  pipe into any consumer including a named pipe.
- **Fixed entry point.** Every produced binary has `e_entry = 0x400078`.
  Code that lives deeper in the body must be reached by falling through
  from offset `0x78` or via an internal jump.
- **Fixed vaddr.** Every produced binary loads at `p_vaddr = 0x400000`.
  Hard-coded absolute addresses in the body must match this base.
- **Fixed memsz formula.** `filesz + 0x10000` is enough for all the
  POCs in this repo; programs needing more BSS must patch their own
  `p_memsz` (at byte offset `0x68`) after the fact.
- **No error checking.** Bad input or write errors are silently ignored;
  exit status is always `0`.

## Linux syscalls used

| # (rax) | Name     | Reference    |
|--------:|:---------|:-------------|
| 0       | `read`   | `man 2 read` |
| 1       | `write`  | `man 2 write`|
| 60      | `exit`   | `man 2 exit` |

## Tested on

- Ubuntu 24.04.4 LTS, kernel 6.17.0-22-generic
- AMD Ryzen 7 PRO 7840U (x86_64)
