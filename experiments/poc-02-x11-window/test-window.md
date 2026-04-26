# `poc-02/test-window` — Test Binary for `window`

A 220-byte Linux ELF64 x86_64 executable that verifies `poc-02/window` ran
correctly. It reads the first 7 bytes of `status.log` and compares them
to the literal string `"opened\n"`.

- Exit `0` — file exists, is readable, and its first 7 bytes are exactly
  `"opened\n"`. The `window` binary did run and wrote its "opened"
  breadcrumb.
- Exit `1` — file is missing, unreadable, shorter than 7 bytes, or begins
  with different bytes.

Hand-hexed, no libraries, four Linux syscalls (`open`, `read`, `exit`, plus
a `repe cmpsb` loop — no syscall).

## Usage

```bash
./window            # opens a window, logs "opened" to status.log, waits for click
./test-window       # exits 0 if "opened\n" is the first line of status.log
echo $?             # → 0 on pass, 1 on fail
```

A successful end-to-end run leaves `status.log` containing
`"opened\nevent\n"` — the test checks only the first 7 bytes, so clicking
(or not) does not affect the result.

## File layout (220 bytes)

| File offset | Size | Vaddr        | Contents                        |
|------------:|-----:|:-------------|:--------------------------------|
| `0x00`      | 64   | `0x400000`   | ELF64 header                    |
| `0x40`      | 56   | `0x400040`   | Program header (R+W+X `PT_LOAD`)|
| `0x78`      | 82   | `0x400078`   | Executable code                 |
| `0xca`      | 11   | `0x4000ca`   | `"status.log\0"`                |
| `0xd5`      | 7    | `0x4000d5`   | `"opened\n"`                    |
| `0xdc`      | 7    | `0x4000dc`   | read buffer (BSS, zero-filled)  |

`p_memsz` rounds up to `0x100` so the 7-byte read buffer beyond the file
end is zero-initialised by the kernel.

`p_flags` is **`R|W|X = 7`**, not the bare `R|X` we used for `hello` and
`test-hello`. Without the `W` bit the `read()` syscall fails with
`EFAULT` because the BSS buffer overlaps the code page. This was learnt
the hard way — the first build of this binary used `p_flags=5` and
strace showed `read(5, 0x4000dc, 7) = -1 EFAULT (Bad address)`.

## ELF64 header — bytes `0x00`–`0x3F`

Same shape as `hello`/`test-hello`, entry point `0x400078`:

```
7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
02 00 3e 00 01 00 00 00 78 00 40 00 00 00 00 00
40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 40 00 38 00 01 00 00 00 00 00 00 00
```

`e_type=ET_EXEC`, `e_machine=EM_X86_64`, `e_phoff=64`, `e_phentsize=56`,
`e_phnum=1`, no section headers.

## Program header — bytes `0x40`–`0x77`

```
01 00 00 00  p_type    PT_LOAD
07 00 00 00  p_flags   R | W | X
00 00 00 00 00 00 00 00           p_offset = 0
00 00 40 00 00 00 00 00           p_vaddr  = 0x400000
00 00 40 00 00 00 00 00           p_paddr  = 0x400000
dc 00 00 00 00 00 00 00           p_filesz = 0xdc
00 01 00 00 00 00 00 00           p_memsz  = 0x100
00 10 00 00 00 00 00 00           p_align  = 0x1000
```

## Code — `0x78`–`0xC9`

### 1. `open("status.log", O_RDONLY, 0)` — syscall 2

```
78: b8 02 00 00 00          mov eax, 2            ; __NR_open
7d: bf ca 00 40 00          mov edi, 0x004000ca   ; path pointer
82: 31 f6                   xor esi, esi          ; O_RDONLY = 0
84: 31 d2                   xor edx, edx          ; mode unused
86: 0f 05                   syscall
88: 48 89 c3                mov rbx, rax          ; save fd in callee-saved rbx
```

### 2. Check for open failure

```
8b: 48 85 db                test rbx, rbx
8e: 78 2e                   js  +0x2e  → 0xbe     ; fd < 0 → fail path
```

`JS` (jump if sign) is the idiomatic Linux-syscall error check: failure is
returned as a negative `errno`, which has the sign bit set in a 64-bit
register.

### 3. `read(fd, &buf, 7)` — syscall 0

```
90: 31 c0                   xor eax, eax          ; __NR_read
92: 48 89 df                mov rdi, rbx          ; fd
95: be dc 00 40 00          mov esi, 0x004000dc   ; &buf
9a: ba 07 00 00 00          mov edx, 7
9f: 0f 05                   syscall
```

### 4. Reject short reads

```
a1: 48 83 f8 07             cmp rax, 7
a5: 75 17                   jne +0x17 → 0xbe      ; got fewer than 7 bytes → fail
```

Any result other than exactly 7 (fewer bytes, or a negative errno) sends
us to the fail path. Because of this strict `== 7` check, a file like
`"opened"` (6 bytes, no newline) fails even though its bytes match the
expected prefix.

### 5. Compare `buf` against `"opened\n"` with `REPE CMPSB`

```
a7: bf dc 00 40 00          mov edi, 0x004000dc   ; &buf
ac: be d5 00 40 00          mov esi, 0x004000d5   ; &"opened\n"
b1: b9 07 00 00 00          mov ecx, 7            ; 7 bytes
b6: f3 a6                   repe cmpsb
```

`REPE CMPSB` decrements `rcx` and compares `[rdi++]` with `[rsi++]`, looping
while `ZF=1` (bytes equal) and `rcx > 0`. On exit `ZF=1` iff all 7 bytes
matched.

### 6. Branch on compare result and exit

```
b8: 75 04                   jne +4  → 0xbe        ; mismatch → fail path
ba: 31 ff                   xor edi, edi          ; exit code = 0 (pass)
bc: eb 05                   jmp +5  → 0xc3        ; skip to exit syscall
be: bf 01 00 00 00          mov edi, 1            ; exit code = 1 (fail)
c3: b8 3c 00 00 00          mov eax, 60           ; __NR_exit
c8: 0f 05                   syscall
```

Three paths converge on the single `exit(edi)` at `0xc3`:

- **Fall-through (success)** — all checks passed, `edi = 0`.
- **Direct jump from `0x8e` or `0xa5`** — open failed or read was short,
  control lands at `0xbe` with `edi = 1`.
- **Mismatch from `0xb8`** — bytes differ, same fail landing at `0xbe`.

`close()` is intentionally omitted; the kernel reclaims the fd on exit.

## Data — `0xca`–`0xdb`

```
ca: 73 74 61 74 75 73 2e 6c 6f 67 00   "status.log\0"
d5: 6f 70 65 6e 65 64 0a                "opened\n"
```

## BSS — read buffer at `0x4000dc`

Not stored on disk. `p_memsz = 0x100` extends the loaded segment to
`0x400100`, leaving `[0x4000dc, 0x400100)` = 36 bytes of zeroed memory. We
only use the first 7 for the `read()` destination.

Because BSS shares the same page as the code (due to `p_align=0x1000`), we
must grant `W` in `p_flags` — otherwise the kernel refuses to let the
kernel itself write the bytes from `read()` into that page, returning
`EFAULT`.

## Test verdict grid

Manually verified with the built binary:

| `status.log` state              | `test-window` exit |
|:--------------------------------|:------------------:|
| file does not exist             | 1                  |
| empty file                      | 1                  |
| `"XYZZY\n\n"`                   | 1                  |
| `"opene"` (5 bytes)             | 1                  |
| `"opened\n"` (7 bytes)          | 0                  |
| `"opened\nevent\n"` (13 bytes)  | 0                  |

The last row is the real end-to-end case: after `./window` opens and the
user clicks (or kills the program), `status.log` contains the full
`"opened\nevent\n"` and the test still passes because only the first 7
bytes are inspected.

## Linux syscalls used

| # (rax) | Name     | Reference      |
|--------:|:---------|:---------------|
| 0       | `read`   | `man 2 read`   |
| 2       | `open`   | `man 2 open`   |
| 60      | `exit`   | `man 2 exit`   |

No external libraries are linked.

## Why `REPE CMPSB` and not `cmp` on a qword?

A single `mov rax, [buf]` / `cmp rax, [expected]` would read 8 bytes from
each address. Because `"opened\n"` is only 7 bytes, the 8th byte would be
whatever follows in the data section (in our case byte `0xdc` of the
file — which happens to be zero in BSS, but we also store nothing
guaranteed at offset `0xdc` of `"opened\n"`). Using `REPE CMPSB` with an
explicit count of 7 sidesteps that subtlety and keeps the code honest.

## Tested on

- Ubuntu 24.04.4 LTS, kernel 6.17.0-22-generic
- AMD Ryzen 7 PRO 7840U (x86_64)
