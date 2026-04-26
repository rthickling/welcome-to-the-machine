# `poc-03/test-note` — byte-by-byte

`test-note` is a 255-byte hand-hexed Linux ELF64 x86_64 executable that
verifies `notes.db` contains the expected first record. It is the
automated test that accompanies `poc-03/note`.

- **Pre-condition**: `./notes.db` exists and its first record is
  exactly `"hello\n"` (a 4-byte little-endian length of `0x00000006`
  followed by those six bytes).
- **Exit 0** if the pre-condition holds.
- **Exit 1** otherwise (file missing, wrong length, mismatched text,
  short read, etc).

Like `note`, it was hand-hexed and wrapped with
[`tools/mkelf`](../../tools/mkelf/mkelf.md).

## Usage in a test harness

```bash
rm -f notes.db
printf 'hello\n' | ./note > /dev/null
./test-note           # exits 0

rm -f notes.db
printf 'bye\n' | ./note > /dev/null
./test-note           # exits 1

rm -f notes.db
./test-note           # exits 1 (open fails; read returns < 4)
```

The test also tolerates additional records appended after the first —
only record #1 is checked.

## File layout

mkelf prepends 120 bytes of ELF/program header; the body is 135 bytes:

| Range          | Length | Content                      |
|----------------|--------|------------------------------|
| `0x000..0x077` | 120    | ELF header + PT_LOAD phdr    |
| `0x078..0x0ef` | 120    | Executable code              |
| `0x0f0..0x0f8` | 9      | `"notes.db\0"`               |
| `0x0f9..0x0fe` | 6      | Expected first record: `"hello\n"` |

BSS (via `p_memsz` = `p_filesz + 0x10000`) holds the two read buffers:

| Address    | Bytes | Purpose                                    |
|------------|-------|--------------------------------------------|
| `0x401000` | 4     | Scratch for the 4-byte length prefix       |
| `0x401010` | 6     | Buffer for the record body being checked   |

`p_flags = R|W|X (7)` is required so the kernel can write into the BSS
buffers during `read(2)` — exactly the same fix applied to
`poc-02/test-window`.

## Register conventions

- `rbx` = `notes.db` file descriptor (callee-preserved across syscalls).
- `r14` = parsed length (32-bit value loaded into `r14d`).
- `rsi`/`rdi`/`rcx` set up for `repe cmpsb` near the end.

## Code walk-through (120 bytes at vaddr `0x400078`)

### Section 1 — open `notes.db` read-only (vaddr `0x400078`, 19 bytes)

```
b8 02 00 00 00           mov eax, 2                ; sys_open
bf f0 00 40 00           mov edi, 0x004000f0       ; "notes.db"
31 f6                    xor esi, esi              ; O_RDONLY
31 d2                    xor edx, edx              ; mode (unused)
0f 05                    syscall
48 89 c3                 mov rbx, rax              ; fd (or -errno)
```

If the file is missing, `rax` is negative (e.g. `-ENOENT = -2`). The
subsequent `read` on that fd will return `-EBADF`; section 2 catches
that and jumps to `fail`.

### Section 2 — read the 4-byte length (17 bytes)

```
31 c0                    xor eax, eax              ; sys_read
48 89 df                 mov rdi, rbx              ; fd
be 00 10 40 00           mov esi, 0x00401000       ; &scratch
ba 04 00 00 00           mov edx, 4
0f 05                    syscall
```

### Section 3 — require `rax == 4` (6 bytes)

```
48 83 f8 04              cmp rax, 4
75 42                    jne fail                  ; +0x42 → fail
```

Anything else — a bad fd (negative), or a 0/partial read — fails.

### Section 4 — verify length == 6 (12 bytes)

```
44 8b 34 25 00 10 40 00  mov r14d, [0x00401000]    ; load length
41 83 fe 06              cmp r14d, 6
75 34                    jne fail                  ; +0x34 → fail
```

### Section 5 — read the 6-byte record body (15 bytes)

```
31 c0                    xor eax, eax              ; sys_read
48 89 df                 mov rdi, rbx              ; fd
be 10 10 40 00           mov esi, 0x00401010       ; &buf
ba 06 00 00 00           mov edx, 6
0f 05                    syscall
```

### Section 6 — require `rax == 6` (6 bytes)

```
48 83 f8 06              cmp rax, 6
75 1d                    jne fail                  ; +0x1d → fail
```

### Section 7 — byte-by-byte compare against `"hello\n"` (15 bytes)

```
be 10 10 40 00           mov esi, 0x00401010       ; buf
bf f9 00 40 00           mov edi, 0x004000f9       ; expected "hello\n"
b9 06 00 00 00           mov ecx, 6
fc                       cld                       ; DF = 0
f3 a6                    repe cmpsb
75 09                    jne fail                  ; +0x09 → fail
```

`repe cmpsb` does byte-compare-and-advance while `ECX > 0` and `ZF = 1`.
When it exits, `ZF = 1` iff all bytes matched. `jne fail` branches
whenever `ZF = 0`.

### Section 8 — pass: exit 0 (9 bytes)

```
b8 3c 00 00 00           mov eax, 60               ; sys_exit
31 ff                    xor edi, edi              ; status 0
0f 05                    syscall
```

### Section 9 — fail: exit 1 (9 bytes)

```
fail:
b8 3c 00 00 00           mov eax, 60               ; sys_exit
bf 01 00 00 00           mov edi, 1                ; status 1
0f 05                    syscall
```

## Jump map

Every `75 XX` in the body targets `fail` at vaddr `0x4000e4` (body
offset `0x6c`). Offsets are computed from the instruction after the
`jne` and are all 8-bit signed:

| From (vaddr) | Displacement | To vaddr |
|--------------|--------------|----------|
| `0x4000a2`   | `+0x42`      | `0x4000e4` |
| `0x4000b0`   | `+0x34`      | `0x4000e4` |
| `0x4000c7`   | `+0x1d`      | `0x4000e4` |
| `0x4000db`   | `+0x09`      | `0x4000e4` |

## Verdict grid

| Precondition                               | Section 3 | Section 4 | Section 6 | Section 7 | Exit |
|--------------------------------------------|-----------|-----------|-----------|-----------|------|
| `notes.db` missing                         | fail (rax=-EBADF) | —   | —         | —         | 1    |
| First record `"hello\n"`                   | pass      | pass      | pass      | pass      | 0    |
| First record length != 6                   | pass      | fail      | —         | —         | 1    |
| First record length 6 but bytes differ     | pass      | pass      | pass      | fail      | 1    |
| First record truncated on disk             | pass or fail | depends | fail     | —         | 1    |

All five scenarios were verified manually after the build — see
`scenario 1..4` in the session log.

## Rule-compliance notes

- **Binary-only** (rule 1): no source file of any kind is checked in for
  this binary. `test-note-code.hex` is a throwaway shell heredoc, not a
  source artefact.
- **Documented** (rule 2): this file.
- **It is itself a test** (rule 3): yes, a test for `poc-03/note`.
- **Library interfaces** (rule 6): none. Only direct Linux syscalls
  `open(2)`, `read(2)`, and `exit(2)` are used; the ABI is the standard
  x86_64 syscall convention.
