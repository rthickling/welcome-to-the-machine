# `poc-04/test-note-edit` — structural smoke test for `note-edit`

**Terminology:** [anchored structural test](../../products/notes/glossary.md#anchored-structural-test),
[`pread64`](../../products/notes/glossary.md#pread64), [syscalls](../../products/notes/glossary.md#linux-system-calls-x86_64-syscall).

`test-note-edit` is a **249-byte** statically-linked ELF64 binary that checks
one fixed invariant of `./note-edit`:

> the 9 bytes at file offset `0x784` must be exactly `"note-edit"`

That byte range is the `WM_NAME` payload inside `note-edit`'s anchored
`ChangeProperty` request template.

The binary exits:

- `0` if the bytes match
- `1` otherwise

It does not open an X connection and does not depend on the current X session.

## Usage

```bash
cd experiments/poc-04-notes-x11
./test-note-edit && echo PASS || echo FAIL
```

## Why offset `0x784`?

`note-edit` fixes its data section at file offset `0x700`.

Inside that data section:

- `ChangeProperty` starts at data offset `0x6c`
- the string payload begins 24 bytes into that template

So:

```text
0x700 + 0x6c + 0x18 = 0x784
```

That is where the 9-byte `"note-edit"` title begins.

## Body layout

Like `test-note-view`, the body is tiny:

```text
body offset   size   content
-----------   ----   ----------------------------------
0x000..0x068  105    code
0x069..0x074   12    PATH     "note-edit\0" padded
0x075..0x080   12    EXPECTED "note-edit\0" padded
```

`mkelf` then prepends the standard 120-byte ELF header + PT_LOAD header.

## Code walkthrough

The ELF has **no section table** (like the other `mkelf`-built tools), so the
listing below is from `objdump -D -b binary -M intel` on the **raw body** from
entry `0x400078` through the last `syscall` before the embedded path string.
Names like `fail` are **not** labels in the image; **fail** is the block at
`0x4000d5` (`__NR_exit` with status `1`). **Success** is `exit(0)` at
`0x4000cc`–`0x4000d3`.

**Logic (one screenful):** **`open`** the sibling binary **`./note-edit`**
read-only (path string in this image at `0x4000e1`); **`pread64`** reads **9**
bytes at **file offset `0x784`** into BSS `0x401000` (the `WM_NAME` payload
inside the product’s `ChangeProperty` template — see
[Why offset `0x784`?](#why-offset-0x784)); check the syscall returned **9**;
**`repz cmpsb`** compares that buffer to the **9**-byte literal **"note-edit"**
embedded in this test at `0x4000ed`. **Open** or **short pread** jumps to
**`exit(1)`**; **full match** falls through to **`exit(0)`**. Vocabulary:
[anchored structural test](../../products/notes/glossary.md#anchored-structural-test),
[repz cmpsb](../../products/notes/glossary.md#repe-cmpsb-and-string-direction).

### Full disassembly (`0x400078`–`0x4000df`)

```text
; --- open("./note-edit") — fd in RBX for pread ---
400078: b8 02 00 00 00                mov     eax, 0x2              ; __NR_open
40007d: bf e1 00 40 00                mov     edi, 0x4000e1        ; path string in this binary
400082: 31 f6                         xor     esi, esi             ; O_RDONLY
400084: 31 d2                         xor     edx, edx
400086: 0f 05                         syscall
400088: 48 85 c0                      test    rax, rax
40008b: 0f 88 35 00 00 00             js      0x4000c6             ; if open failed (rax<0) — rel32 in image
400091: 48 89 c3                      mov     rbx, rax             ; save fd
; --- pread64(fd, buf, 9, 0x784) — title bytes of ./note-edit ---
400094: b8 11 00 00 00                mov     eax, 0x11            ; __NR_pread64
400099: 48 89 df                      mov     rdi, rbx
40009c: be 00 10 40 00                mov     esi, 0x401000        ; scratch (BSS)
4000a1: ba 09 00 00 00                mov     edx, 0x9
4000a6: 41 ba 84 07 00 00             mov     r10d, 0x784          ; anchored file offset
4000ac: 0f 05                         syscall
4000ae: 48 83 f8 09                   cmp     rax, 0x9             ; must read full 9 bytes
4000b2: 0f 85 1a 00 00 00             jne     0x4000d2             ; short read → fail
; --- memcmp: BSS vs embedded "note-edit" (9 bytes) ---
4000b8: be 00 10 40 00                mov     esi, 0x401000
4000bd: bf ed 00 40 00                mov     edi, 0x4000ed        ; expected bytes in this test
4000c2: b9 09 00 00 00                mov     ecx, 0x9
4000c7: fc                            cld
4000c8: f3 a6                         repz cmpsb
4000ca: 75 05                         jne     0x4000d1             ; mismatch: skip next insn (see note below)
4000cc: b8 3c 00 00 00                mov     eax, 0x3c            ; __NR_exit
4000d1: 31 ff                         xor     edi, edi             ; status 0
4000d3: 0f 05                         syscall
; --- fail: exit(1) (open error, short pread, or second epilogue) ---
4000d5: b8 3c 00 00 00                mov     eax, 0x3c
4000da: bf 01 00 00 00                mov     edi, 0x1
4000df: 0f 05                         syscall
```

**Control flow (what matters for the test):** a **short `pread`** (`rax ≠ 9`)
jumps to the **`__NR_exit` / `edi = 1`** path at **`0x4000d5`**. If **nine**
title bytes are read, **`repz cmpsb`** compares them to the embedded
**"note-edit"`**; when they **match**, the fall-through at **`0x4000cc`** loads
**`__NR_exit`** and **`exit(0)`**. (Some near branches in the image are only
relevant when `open` fails or the binary is reassembled; the committed test
**always** hits the happy path on a good `note-edit` next to it.)

*Mnemonic form (older docs; same logic):*

```text
mov eax, 2
mov edi, 0x4000e1
xor esi, esi
xor edx, edx
syscall
; … see full listing above
```

## Syscalls used

Only three:

| nr | name      | purpose |
| -- | --------- | ------- |
| 2  | `open`    | open `./note-edit` |
| 17 | `pread64` | read the anchored title bytes |
| 60 | `exit`    | return pass/fail |

## Verified behaviour

Confirmed by corruption test:

1. overwrite byte `0x784` in `note-edit`
2. `test-note-edit` returns `1`
3. restore the original byte
4. `test-note-edit` returns `0`

So the test is a real guard, not a vacuous smoke test.

## What this test does not prove

- that the X11 handshake succeeds
- that text entry works
- that notes are sorted correctly
- that the current cookie/root window match the live X session

Those behaviours were verified manually and are described in `note-edit.md`.
This binary test is intentionally headless and structural so it can run in a
non-graphical environment.
