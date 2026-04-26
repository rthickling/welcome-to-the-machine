# `products/notes/test-notes-linux-x86_64-clicks`

`test-notes-linux-x86_64-clicks` is a **943-byte** statically-linked Linux
ELF64 x86_64 binary. It is a second structural verifier for
`./notes-linux-x86_64`, focused specifically on the click-routing and redraw
logic that was changed while adding per-row delete buttons.

Terminology (*slot*, *NOTE_COUNT*, hit-test, …): [product notes glossary](../../../glossary.md) (e.g. [ImageText8](../../../glossary.md#imagetext8)).

Unlike `test-notes-linux-x86_64`, which checks the visible product strings,
colour constants, printable keymap, and border entry point, this verifier checks
the byte ranges that anchor the current click behavior.

## Checked ranges

It validates nine machine-code or literal ranges in `notes-linux-x86_64`:

1. `0x435` — `83 fa 1e 72 33`
   - right-pane row-band Y compare
   - also proves the `jb` opcode after the compare is still intact
2. `0x443` — `b8 1e 00 00 00`
   - row-band origin immediate, aligning the first hit band with `y = 30`
3. `0x460` — `81 fe 20 02 00 00 73 0a e9 19 02 00 00`
   - split between normal row clicks and far-right `Del` clicks
4. `0x4a8` — `e9 e6 03 00 00`
   - delete path jumps into the persistent delete rewrite helper
5. `0x61b` — `e9 aa 00 00 00`
   - draw loop tail jumps into the stale-row clear helper
6. `0x686` — `89 2c 25 04 48 40 00 89 e8 c1 e0 06 05 00 43 40 00`
   - normal click path still stores the selected row and computes the slot base
7. `0x6ca` — `83 fd 14 7d 1d e8 21 fe ff ff 66 c7 04 25 e0 07 40 00 68 01 e8 22 fe ff ff 66 41 83 c6 10 ff c5 eb de e9 c3 fd ff ff`
   - tail-clear helper body for blanking unused right-pane rows after deletions
8. `0x878` — `44 65 6c`
   - `Del` label literal
9. `0x893` — `b8 02 00 00 00 bf c8 07 40 00 ... e9 3b fc ff ff`
   - persistent delete helper that truncates and rewrites `notes.db`

**What each check enforces in the product (in execution terms):** (1) the
lower bound on `event_y` is still the small immediate `0x1e` and the short `jb`
after it is still a real forward branch, not an accidental `0x1e` opcode; (2)
the row-walk start immediate is `0x1e` so row index `0` is aligned to `y=30`;
(3) the `cmp esi,0x220` / `jae` / `jmp` prologue to split `Del` from load is
intact; (4) the post-delete path still jumps to the on-disk helper at `0x400893`;
(5) the draw loop’s exit still jumps into the tail-clear subsequence; (6) the
load path still records `0x404804` and forms `0x404300+row*64`; (7) the tail-clear
helper’s compare/call/loop form is still present; (8) the visible `Del` literal
is still embedded; (9) the `open`/`write` loop that rewrites the database is
unchanged, so a regression in persistence is caught even when the UI still
starts.

Exit status:

- `0` = pass
- `1` = fail

## Why this test exists

The recent regressions were not in the stable ELF header or the obvious title
strings. They were in short, easy-to-break click-handler bytes:

- a row-band compare immediate
- the row-band origin immediate itself
- a branch opcode beside that compare
- the split between load clicks and delete clicks
- the jump target used after a delete
- the redraw helper that clears stale rows
- the helper that persists deletions to disk

This verifier gives those paths a stable, always-runnable regression check on
the Linux host.

## File layout

`mkelf` wraps an `823`-byte body of code plus literals; the on-disk file also
includes the `120`-byte loader header at `0x0..0x77`, so the executable slice is
`0x78` through the last `exit` `syscall` before the path string at `0x2c5`.

```text
0x000..0x077   120   ELF header + PT_LOAD program header
0x078..0x2c4   589   entry: open, nine pread64+compare blocks, success/fail exits
0x2c5..0x3ae   354   path string and expected byte literals
```

Total file size: `943` bytes.

## Overall logic

Pseudocode:

```text
fd = open("notes-linux-x86_64", O_RDONLY)

for each (offset, expected_bytes):
    pread64(fd, buf, len(expected_bytes), offset)
    compare buf against expected_bytes

exit(0) on success, else exit(1)
```

## Code walk-through

### Block 1 — open sibling binary

The opening sequence is the same shape as the earlier structural verifier.
**Disassembly** (from `objdump` on the code slice, Intel syntax; the shared
failure target is at `0x4002b9`):

```text
400078:  b8 02 00 00 00         mov     eax, 0x2
40007d:  bf c5 02 40 00         mov     edi, 0x4002c5
400082:  31 f6                  xor     esi, esi
400084:  31 d2                  xor     edx, edx
400086:  0f 05                  syscall
400088:  48 85 c0               test    rax, rax
40008b:  0f 88 28 02 00 00      js      0x4002b9
400091:  48 89 c3               mov     rbx, rax
```

(Commented form without vaddrs, as in earlier revisions:)

```text
b8 02 00 00 00       mov eax, 2
bf c5 02 40 00       mov edi, 0x4002c5
31 f6                xor esi, esi
31 d2                xor edx, edx
0f 05                syscall
48 85 c0             test rax, rax
0f 88 ...            js fail
48 89 c3             mov rbx, rax
```

**Execution logic (this sequence only):** load `__NR_open` into `eax`, set `edi`
to the address of the embedded path string, clear `esi` and `edx` for
`O_RDONLY` with no mode bits, and execute the syscall. If `rax` is negative, the
open failed, so a signed 32-bit relative branch skips forward to the failure
exit. Otherwise save `rax` in `rbx` for every later `pread64`, because
`pread64` will need the live fd in `rdi`.
This opens `notes-linux-x86_64` read-only and keeps the fd in `rbx`. In the
current rebuilt verifier the embedded path begins at `0x4002c5`.

### Block 2 — repeated `pread64` checks

Each check uses the same template:

```text
b8 11 00 00 00       mov eax, 17
48 89 df             mov rdi, rbx
be 00 10 40 00       mov esi, 0x401000
ba <len>             mov edx, len
41 ba <offset>       mov r10d, file_offset
0f 05                syscall
48 83 f8 <len>       cmp rax, len
0f 85 ...            jne fail

be 00 10 40 00       mov esi, 0x401000
bf <expected>        mov edi, expected_literal
b9 <len>             mov ecx, len
fc                   cld
f3 a6                repe cmpsb
0f 85 ...            jne fail
```

**Execution logic (each check pair):** the first block issues `pread64` with
`r10d` equal to a fixed in-file offset, reading exactly `len` bytes into
`0x401000`, then verifies the syscall return equals `len` so a short read
counts as failure. The second block sets `esi` to the same buffer, `edi` to
immutable expected bytes in the test binary, sets `DF=0` with `cld`, and uses
`repe cmpsb` to compare the read bytes to the expected pattern byte-for-byte. Any
mismatch or length error jumps to the shared failure exit, so a single flipped
bit in the product binary is detected.
Linux x86_64 syscall `17` is `pread64`, so the verifier can read anchored byte
ranges without needing to seek.
For longer product patterns (the persistent-delete helper is more than 127
bytes), the live binary uses a `cmp rax, imm32` form instead of `cmp rax, r8` for
the return check; the test generator mirrors that, but the surrounding logic
is the same: confirm a full read, then compare to expected bytes.

### Full disassembly of executable code (`0x400078`–`0x4002c3`)

The ELF has no section table, so the listing below is from `objdump` on the raw
load segment bytes from the entry `0x400078` through the end of the failure
`exit` (before the path string at `0x4002c5`). Jumps to `0x4002b9` are the
shared `fail` path; `repz cmps` is how `objdump` spells `f3 a6` here.
Vocabulary for [pread64](../../../glossary.md#pread64), [anchored structural test](../../../glossary.md#anchored-structural-test), and [syscalls](../../../glossary.md#linux-syscalls-x86-64-syscall): [glossary](../../../glossary.md).

```text
; --- Full verifier: open + nine (offset, expected) checks + exit(0)/exit(1) ---
  400078:  b8 02 00 00 00         mov     eax, 0x2
  40007d:  bf c5 02 40 00         mov     edi, 0x4002c5
  400082:  31 f6                  xor     esi, esi
  400084:  31 d2                  xor     edx, edx
  400086:  0f 05                  syscall
  400088:  48 85 c0               test    rax, rax
  40008b:  0f 88 28 02 00 00      js      0x4002b9
  400091:  48 89 c3               mov     rbx, rax
  400094:  b8 11 00 00 00         mov     eax, 0x11
  400099:  48 89 df               mov     rdi, rbx
  40009c:  be 00 10 40 00         mov     esi, 0x401000
  4000a1:  ba 05 00 00 00         mov     edx, 0x5
  4000a6:  41 ba 35 04 00 00      mov     r10d, 0x435
  4000ac:  0f 05                  syscall
  4000ae:  48 83 f8 05            cmp     rax, 0x5
  4000b2:  0f 85 01 02 00 00      jne     0x4002b9
  4000b8:  be 00 10 40 00         mov     esi, 0x401000
  4000bd:  bf d8 02 40 00         mov     edi, 0x4002d8
  4000c2:  b9 05 00 00 00         mov     ecx, 0x5
  4000c7:  fc                     cld
  4000c8:  f3 a6                  repz cmps BYTE PTR [rsi], BYTE PTR [rdi]
  4000ca:  0f 85 e9 01 00 00      jne     0x4002b9
  4000d0:  b8 11 00 00 00         mov     eax, 0x11
  4000d5:  48 89 df               mov     rdi, rbx
  4000d8:  be 00 10 40 00         mov     esi, 0x401000
  4000dd:  ba 05 00 00 00         mov     edx, 0x5
  4000e2:  41 ba 43 04 00 00      mov     r10d, 0x443
  4000e8:  0f 05                  syscall
  4000ea:  48 83 f8 05            cmp     rax, 0x5
  4000ee:  0f 85 c5 01 00 00      jne     0x4002b9
  4000f4:  be 00 10 40 00         mov     esi, 0x401000
  4000f9:  bf dd 02 40 00         mov     edi, 0x4002dd
  4000fe:  b9 05 00 00 00         mov     ecx, 0x5
  400103:  fc                     cld
  400104:  f3 a6                  repz cmps BYTE PTR [rsi], BYTE PTR [rdi]
  400106:  0f 85 ad 01 00 00      jne     0x4002b9
  40010c:  b8 11 00 00 00         mov     eax, 0x11
  400111:  48 89 df               mov     rdi, rbx
  400114:  be 00 10 40 00         mov     esi, 0x401000
  400119:  ba 0d 00 00 00         mov     edx, 0xd
  40011e:  41 ba 60 04 00 00      mov     r10d, 0x460
  400124:  0f 05                  syscall
  400126:  48 83 f8 0d            cmp     rax, 0xd
  40012a:  0f 85 89 01 00 00      jne     0x4002b9
  400130:  be 00 10 40 00         mov     esi, 0x401000
  400135:  bf e2 02 40 00         mov     edi, 0x4002e2
  40013a:  b9 0d 00 00 00         mov     ecx, 0xd
  40013f:  fc                     cld
  400140:  f3 a6                  repz cmps BYTE PTR [rsi], BYTE PTR [rdi]
  400142:  0f 85 71 01 00 00      jne     0x4002b9
  400148:  b8 11 00 00 00         mov     eax, 0x11
  40014d:  48 89 df               mov     rdi, rbx
  400150:  be 00 10 40 00         mov     esi, 0x401000
  400155:  ba 05 00 00 00         mov     edx, 0x5
  40015a:  41 ba a8 04 00 00      mov     r10d, 0x4a8
  400160:  0f 05                  syscall
  400162:  48 83 f8 05            cmp     rax, 0x5
  400166:  0f 85 4d 01 00 00      jne     0x4002b9
  40016c:  be 00 10 40 00         mov     esi, 0x401000
  400171:  bf ef 02 40 00         mov     edi, 0x4002ef
  400176:  b9 05 00 00 00         mov     ecx, 0x5
  40017b:  fc                     cld
  40017c:  f3 a6                  repz cmps BYTE PTR [rsi], BYTE PTR [rdi]
  40017e:  0f 85 35 01 00 00      jne     0x4002b9
  400184:  b8 11 00 00 00         mov     eax, 0x11
  400189:  48 89 df               mov     rdi, rbx
  40018c:  be 00 10 40 00         mov     esi, 0x401000
  400191:  ba 05 00 00 00         mov     edx, 0x5
  400196:  41 ba 1b 06 00 00      mov     r10d, 0x61b
  40019c:  0f 05                  syscall
  40019e:  48 83 f8 05            cmp     rax, 0x5
  4001a2:  0f 85 11 01 00 00      jne     0x4002b9
  4001a8:  be 00 10 40 00         mov     esi, 0x401000
  4001ad:  bf f4 02 40 00         mov     edi, 0x4002f4
  4001b2:  b9 05 00 00 00         mov     ecx, 0x5
  4001b7:  fc                     cld
  4001b8:  f3 a6                  repz cmps BYTE PTR [rsi], BYTE PTR [rdi]
  4001ba:  0f 85 f9 00 00 00      jne     0x4002b9
  4001c0:  b8 11 00 00 00         mov     eax, 0x11
  4001c5:  48 89 df               mov     rdi, rbx
  4001c8:  be 00 10 40 00         mov     esi, 0x401000
  4001cd:  ba 11 00 00 00         mov     edx, 0x11
  4001d2:  41 ba 86 06 00 00      mov     r10d, 0x686
  4001d8:  0f 05                  syscall
  4001da:  48 83 f8 11            cmp     rax, 0x11
  4001de:  0f 85 d5 00 00 00      jne     0x4002b9
  4001e4:  be 00 10 40 00         mov     esi, 0x401000
  4001e9:  bf f9 02 40 00         mov     edi, 0x4002f9
  4001ee:  b9 11 00 00 00         mov     ecx, 0x11
  4001f3:  fc                     cld
  4001f4:  f3 a6                  repz cmps BYTE PTR [rsi], BYTE PTR [rdi]
  4001f6:  0f 85 bd 00 00 00      jne     0x4002b9
  4001fc:  b8 11 00 00 00         mov     eax, 0x11
  400201:  48 89 df               mov     rdi, rbx
  400204:  be 00 10 40 00         mov     esi, 0x401000
  400209:  ba 27 00 00 00         mov     edx, 0x27
  40020e:  41 ba ca 06 00 00      mov     r10d, 0x6ca
  400214:  0f 05                  syscall
  400216:  48 83 f8 27            cmp     rax, 0x27
  40021a:  0f 85 99 00 00 00      jne     0x4002b9
  400220:  be 00 10 40 00         mov     esi, 0x401000
  400225:  bf 0a 03 40 00         mov     edi, 0x40030a
  40022a:  b9 27 00 00 00         mov     ecx, 0x27
  40022f:  fc                     cld
  400230:  f3 a6                  repz cmps BYTE PTR [rsi], BYTE PTR [rdi]
  400232:  0f 85 81 00 00 00      jne     0x4002b9
  400238:  b8 11 00 00 00         mov     eax, 0x11
  40023d:  48 89 df               mov     rdi, rbx
  400240:  be 00 10 40 00         mov     esi, 0x401000
  400245:  ba 03 00 00 00         mov     edx, 0x3
  40024a:  41 ba 78 08 00 00      mov     r10d, 0x878
  400250:  0f 05                  syscall
  400252:  48 83 f8 03            cmp     rax, 0x3
  400256:  0f 85 5d 00 00 00      jne     0x4002b9
  40025c:  be 00 10 40 00         mov     esi, 0x401000
  400261:  bf 31 03 40 00         mov     edi, 0x400331
  400266:  b9 03 00 00 00         mov     ecx, 0x3
  40026b:  fc                     cld
  40026c:  f3 a6                  repz cmps BYTE PTR [rsi], BYTE PTR [rdi]
  40026e:  0f 85 45 00 00 00      jne     0x4002b9
  400274:  b8 11 00 00 00         mov     eax, 0x11
  400279:  48 89 df               mov     rdi, rbx
  40027c:  be 00 10 40 00         mov     esi, 0x401000
  400281:  ba 7b 00 00 00         mov     edx, 0x7b
  400286:  41 ba 93 08 00 00      mov     r10d, 0x893
  40028c:  0f 05                  syscall
  40028e:  48 83 f8 7b            cmp     rax, 0x7b
  400292:  0f 85 21 00 00 00      jne     0x4002b9
  400298:  be 00 10 40 00         mov     esi, 0x401000
  40029d:  bf 34 03 40 00         mov     edi, 0x400334
  4002a2:  b9 7b 00 00 00         mov     ecx, 0x7b
  4002a7:  fc                     cld
  4002a8:  f3 a6                  repz cmps BYTE PTR [rsi], BYTE PTR [rdi]
  4002aa:  0f 85 09 00 00 00      jne     0x4002b9
  4002b0:  b8 3c 00 00 00         mov     eax, 0x3c
  4002b5:  31 ff                  xor     edi, edi
  4002b7:  0f 05                  syscall
  4002b9:  b8 3c 00 00 00         mov     eax, 0x3c
  4002be:  bf 01 00 00 00         mov     edi, 0x1
  4002c3:  0f 05                  syscall
```

### Block 3 — success and failure exits

Success (falls through after the last `repz compare` in the full listing):

```text
  4002b0:  b8 3c 00 00 00         mov     eax, 0x3c
  4002b5:  31 ff                  xor     edi, edi
  4002b7:  0f 05                  syscall
```

(Short form:)

```text
b8 3c 00 00 00
31 ff
0f 05
```

**Execution logic:** load `__NR_exit` and clear `edi`, so the process exits with
status `0` after every anchored pattern matched.

Failure (shared `fail` label; all error branches in the full listing `jmp` to
`0x4002b9` first):

```text
  4002b9:  b8 3c 00 00 00         mov     eax, 0x3c
  4002be:  bf 01 00 00 00         mov     edi, 0x1
  4002c3:  0f 05                  syscall
```

(Short form:)

```text
b8 3c 00 00 00
bf 01 00 00 00
0f 05
```

**Execution logic:** load `__NR_exit` and set `edi` to `1`, so any mismatch or
I/O error terminates with a non-zero status. This is the only difference from
the success path.

Linux syscall `60` is `exit`.

## Embedded literals

### Path at `0x4002c5`

```text
6e 6f 74 65 73 2d 6c 69 6e 75 78 2d 78 38 36 5f 36 34 00
```

ASCII:

```text
notes-linux-x86_64
```

### Expected byte blocks

Embedded expected ranges begin at `0x4002d8` and are laid out in the same order
as the checks listed above.

## Syscalls used

Exactly three Linux x86_64 syscalls:

- `2` = `open`
- `17` = `pread64`
- `60` = `exit`

## What this test proves

It proves that the committed Linux product reference binary still contains the
current click-routing, delete-routing, normal-load, stale-row-clear, and
persistent-delete rewrite byte sequences at the expected file offsets.

It does **not** prove full runtime X11 behavior, and it does not synthesize
real repeated pointer clicks. It is still structural. Its value is that it
catches the exact class of byte-level regressions that recently broke repeated
click handling.
