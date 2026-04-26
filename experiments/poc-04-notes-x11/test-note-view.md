# poc-04/test-note-view — smoke test for `note-view`

**Terminology:** [anchored structural test](../../products/notes/glossary.md#anchored-structural-test), [pread64](../../products/notes/glossary.md#pread64), [ChangeProperty / WM_NAME](../../products/notes/glossary.md#changeproperty-and-wm_name).

`test-note-view` is a **249-byte** statically-linked ELF64 binary that asserts
a single structural invariant of the sibling binary: the bytes
`"note-view"` (the X11 `WM_NAME` payload) live at file offset `0x384` of
`./note-view`.

Exits `0` if the invariant holds, `1` otherwise.

## Usage

```bash
cd experiments/poc-04-notes-x11/
./test-note-view && echo OK || echo FAIL
```

It does **not** open an X11 connection — it only does three filesystem
syscalls plus the in-memory `repe cmpsb`. So it runs without `$DISPLAY`
set and without the X session being alive, making it safe to run in CI on a
headless VM (the planned cross-architecture tests will need exactly this
property).

## Why file offset 0x384?

From `note-view.md`:

| region              | file offset | vaddr      |
| ------------------- | ----------- | ---------- |
| mkelf header + phdr | `0x000`     | `0x400000` |
| code                | `0x078`     | `0x400078` |
| data                | `0x300`     | `0x400300` |

Inside data, the `ChangeProperty WM_NAME` template starts at body offset
`0x6c` (file offset `0x300 + 0x6c = 0x36c`, vaddr `0x40036c`), and the
9-byte `"note-view"` string sits at template-offset `+24`, i.e. file offset
`0x36c + 24 = 0x384`.

If anyone ever shifts the code size or the data layout, this offset shifts
with it and `test-note-view` fires. That's the whole point.

## ELF layout (129-byte body, 249-byte binary)

```
  file offset   size  content
  -----------   ----  -------
  0x000..0x077  120   mkelf ELF header + PT_LOAD phdr
  0x078..0x0e0  105   code
  0x0e1..0x0ec   12   PATH     "note-view\0" padded to 12
  0x0ed..0x0f8   12   EXPECTED "note-view\0" padded to 12
  (mkelf memsz extends 0x10000 of writable BSS past file end)
```

PATH and EXPECTED carry identical bytes by happy coincidence — PATH is the
pathname passed to `open`, EXPECTED is the golden string compared against the
bytes pread from inside the opened file.

## Code walkthrough (105 bytes)

Register conventions:
- `rbx` holds the fd for `./note-view` (zero otherwise)
- Every other register is scratch within its block

### Block 1 — open `./note-view` (28 bytes, body 0x00..0x1c)

```
b8 02 00 00 00       mov eax, 2          ; sys_open
bf e1 00 40 00       mov edi, 0x4000e1   ; PATH = "note-view\0..."
31 f6                xor esi, esi        ; O_RDONLY
31 d2                xor edx, edx        ; mode = 0
0f 05                syscall
48 85 c0             test rax, rax
0f 88 35 00 00 00    js fail             ; rax<0 → fail
48 89 c3             mov rbx, rax
```

A path relative to `cwd` is used deliberately: the binary has to be run
from `poc-04/` so that it's testing the sibling `note-view` rather than some
unrelated file.

### Block 2 — pread 9 bytes at offset 0x384 (36 bytes, body 0x1c..0x40)

```
b8 11 00 00 00       mov eax, 17         ; sys_pread64
48 89 df             mov rdi, rbx
be 00 10 40 00       mov esi, 0x401000   ; BUF (BSS)
ba 09 00 00 00       mov edx, 9          ; count
41 ba 84 03 00 00    mov r10d, 0x384     ; offset
0f 05                syscall
48 83 f8 09          cmp rax, 9
0f 85 1a 00 00 00    jne fail            ; didn't get exactly 9 bytes
```

`pread` avoids the need for a separate `lseek` — fewer syscalls, smaller
binary. The offset lives in `r10` because Linux x86-64 syscall conv uses
`rdi, rsi, rdx, r10, r8, r9`.

### Block 3 — compare BUF vs EXPECTED (20 bytes, body 0x40..0x54)

```
be 00 10 40 00       mov esi, 0x401000   ; BUF
bf ed 00 40 00       mov edi, 0x4000ed   ; EXPECTED
b9 09 00 00 00       mov ecx, 9
fc                   cld                 ; rsi/rdi advance +1 per cmpsb
f3 a6                repe cmpsb          ; while bytes equal, decrement ecx
75 05                jne fail            ; if any pair differed, fail
```

`repe cmpsb` is the classic pattern for "strings equal?": it keeps going
while pairs are equal and `rcx` is non-zero. On exit `ZF=1` means the whole
prefix matched.

### Block 4 — exit 0 (success, 9 bytes, body 0x54..0x5d)

```
b8 3c 00 00 00       mov eax, 60         ; sys_exit
31 ff                xor edi, edi        ; status = 0
0f 05                syscall
```

No explicit `close` — the kernel reaps the fd at process exit.

### Block 5 — fail: exit 1 (12 bytes, body 0x5d..0x69)

```
b8 3c 00 00 00       mov eax, 60
bf 01 00 00 00       mov edi, 1
0f 05                syscall
```

The `js fail` and `jne fail` jumps all target this block.

## Syscalls used

| nr | name   | where   |
| -- | ------ | ------- |
|  2 | open   | Block 1 |
| 17 | pread  | Block 2 |
| 60 | exit   | Blocks 4 & 5 |

Three syscalls total — strictly fewer than `poc-03/test-note` (which also
uses `read`, `lseek`-equivalent `read`-based positioning, and `close`).

## Verdict grid

| condition                                              | exit |
| ------------------------------------------------------ | ---- |
| `./note-view` missing or unreadable                    | 1 (via `js fail` after `open`) |
| `./note-view` too short (pread returns <9)             | 1 |
| bytes at offset 0x384 are not `"note-view"` byte-for-byte | 1 |
| bytes match exactly                                    | 0 |

Verified by flipping byte `0x384` of `note-view` and re-running — exit
code becomes 1 as expected, and reverts to 0 after restore.

## Not tested here (intentional)

- X11 handshake (costs a live display + cookie, deferred to the future
  cross-architecture VM suite)
- Rendering correctness (no easy headless X framebuffer yet — see README
  "future work" section)
- `notes.db` interaction (already covered by `poc-03/test-note`)

This test is the minimal structural guard: it breaks iff the binary gets
rebuilt with a different layout or a different window title, both of which
should force a conscious code update.
