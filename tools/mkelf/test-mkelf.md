# `tools/test-mkelf` — Test Binary for `mkelf`

A 288-byte hand-hexed Linux ELF64 x86_64 executable that verifies the
first 96 bytes produced by `mkelf` match the expected ELF header + partial
program header stub (everything except `p_filesz`, `p_memsz`, `p_align`).

- Exit `0` — first 96 bytes on stdin match the expected prefix.
- Exit `1` — stdin was shorter than 96 bytes, or any byte differs.

Most interestingly, **this binary was built using `mkelf` itself** — it is
the first POC in this repo that was not hand-hexed in its entirety. Only
the 168-byte body was hand-hexed; `mkelf` materialised the ELF64 wrapper
around it. See `tools/mkelf/mkelf.md` §"Self-hosting".

## Usage

```bash
# positive: mkelf's header must match
./mkelf < /dev/null | ./test-mkelf ; echo $?        # → 0

# also positive: first 96 bytes are independent of the body
echo 'b83c000000bf0000000 00f05' | xxd -r -p | ./mkelf | ./test-mkelf    # → 0

# negative: junk input
head -c 96 /dev/urandom | ./test-mkelf ; echo $?    # → 1

# negative: short read
printf 'tiny' | ./test-mkelf ; echo $?              # → 1
```

The test only inspects the **first 96 bytes** of the stream — everything
up to and including `p_vaddr` and `p_paddr`, but stopping just before
`p_filesz`. That means the same `test-mkelf` invocation passes regardless
of what body was fed into `mkelf`, because those 96 bytes are constant
across all possible inputs.

## File layout (288 bytes = 120 header + 168 body)

The first 120 bytes are the `mkelf`-produced ELF64 header; the remaining
168 bytes are the body we hand-hexed. The body itself is:

| Body offset | Size | Vaddr       | Contents                       |
|------------:|-----:|:------------|:-------------------------------|
| `0x00`      | 72   | `0x400078`  | Executable code                |
| `0x48`      | 96   | `0x4000C0`  | Expected 96-byte prefix        |

Beyond file end, `mkelf` reserved 64 KiB of BSS (at `p_memsz - p_filesz`
= 65536 bytes). The input buffer lives at `0x400120` inside that BSS.

## ELF64 header and program header (bytes `0x00`–`0x77`)

Supplied verbatim by `mkelf` when the body was piped through it.
Unremarkable: `p_filesz = 0x120 (= 0x78 + 168)`, `p_memsz = 0x10120`.

## Code — body bytes `0x00`–`0x47` / file `0x78`–`0xBF`

All addresses below are virtual addresses (vaddr = body offset + 0x78 +
0x400000).

### 1. Initialise the read counter

```
78: 31 ed                   xor ebp, ebp           ; total = 0
```

`rbp` is callee-saved and holds the running count of bytes read across
every iteration of the read loop.

### 2. Read loop — drain stdin until we have 96 bytes

```
7a: 31 c0                   xor eax, eax           ; __NR_read = 0
7c: 31 ff                   xor edi, edi           ; fd = stdin
7e: be 20 01 40 00          mov esi, 0x00400120    ; &buf
83: 48 01 ee                add rsi, rbp           ; rsi = buf + total
86: ba 60 00 00 00          mov edx, 96            ; max we ever need
8b: 29 ea                   sub edx, ebp           ; edx = 96 - total (remaining)
8d: 0f 05                   syscall
8f: 48 85 c0                test rax, rax
92: 7e 20                   jle +0x20 → 0xb4       ; EOF or error → fail
94: 48 01 c5                add rbp, rax           ; total += bytes read
97: 48 83 fd 60             cmp rbp, 96
9b: 7c dd                   jl  -0x23 → 0x7a       ; need more → loop
```

This robustly accumulates exactly 96 bytes even when the kernel returns
short reads (pipes, sockets, slow terminals). If EOF arrives before we
reach 96 bytes (`rax == 0`) or any error (`rax < 0`), `JLE` sends us to
the fail path.

### 3. Compare buffer against embedded expected bytes

```
9d: bf 20 01 40 00          mov edi, 0x00400120    ; &buf
a2: be c0 00 40 00          mov esi, 0x004000c0    ; &expected
a7: b9 60 00 00 00          mov ecx, 96
ac: f3 a6                   repe cmpsb
ae: 75 04                   jne +4 → 0xb4          ; mismatch → fail
```

`REPE CMPSB` is the terse, canonical way to compare two byte ranges: it
increments both `rdi` and `rsi`, decrements `rcx`, and re-loops while
`ZF=1` and `rcx > 0`. On exit, `ZF=1` iff all 96 bytes matched.

### 4. Exit paths

```
b0: 31 ff                   xor edi, edi           ; status = 0 (pass)
b2: eb 05                   jmp +5 → 0xb9
b4: bf 01 00 00 00          mov edi, 1             ; status = 1 (fail)
b9: b8 3c 00 00 00          mov eax, 60            ; __NR_exit
be: 0f 05                   syscall
```

Three entry points converge on the single `exit` at `0xb9`:
- `0xb0` fall-through for success.
- `0xb4` from the early `jle` in the read loop.
- `0xb4` from the `jne` after `REPE CMPSB`.

## Data — expected 96-byte prefix at `0xC0` / vaddr `0x4000C0`

These are precisely the first 96 bytes that `mkelf` emits for **any**
input: the full ELF header, plus the first four fields of the program
header (`p_type`, `p_flags`, `p_offset`, `p_vaddr`, `p_paddr`). The
patched fields (`p_filesz`, `p_memsz`) live at byte 96 onward and are
deliberately excluded from the comparison.

```
7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
02 00 3e 00 01 00 00 00 78 00 40 00 00 00 00 00
40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 40 00 38 00 01 00 00 00 00 00 00 00
01 00 00 00 07 00 00 00 00 00 00 00 00 00 00 00
00 00 40 00 00 00 00 00 00 00 40 00 00 00 00 00
```

## BSS — input buffer at `0x400120`

Not on disk. The `mkelf`-produced `p_memsz = 0x10120` extends the
segment to `0x410120`, giving us ~64 KiB of zeroed BSS. We only use 96
bytes starting at `0x400120`.

## Verified scenarios

The `README.md` section for `tools/` lists the canonical one-liners. All
of these have been run during development:

| Input to `test-mkelf`'s stdin                         | exit |
|:------------------------------------------------------|:----:|
| `mkelf < /dev/null`  (empty body, 120 B header only)  | 0    |
| `mkelf < body.bin`   (any body, header is still first)| 0    |
| `mkelf < mkelf-body` (self-rebuild, works too)        | 0    |
| `head -c 96 /dev/urandom`                             | 1    |
| `head -c 96 /etc/passwd`                              | 1    |
| `printf 'short'`                                      | 1    |
| nothing at all (immediate EOF)                        | 1    |

## Linux syscalls used

| # (rax) | Name     | Reference    |
|--------:|:---------|:-------------|
| 0       | `read`   | `man 2 read` |
| 60      | `exit`   | `man 2 exit` |

## Tested on

- Ubuntu 24.04.4 LTS, kernel 6.17.0-22-generic
- AMD Ryzen 7 PRO 7840U (x86_64)
