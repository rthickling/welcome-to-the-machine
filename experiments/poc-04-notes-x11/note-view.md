# poc-04/note-view — X11 GUI viewer of `notes.db`

`note-view` is a **1060-byte** statically-linked ELF64 binary that opens a
600×400 X11 window titled `"note-view"`, reads every length-prefixed record in
`notes.db` (the format written by `poc-03/note`), and renders each record as
one line of text inside the window using the X11 `"fixed"` font. The window
closes on the first key press, mouse click, or when the window manager kills
the client (e.g. user clicks the WM close button).

It is the direct graphical counterpart to `poc-03/note`: same storage, same
record format, same limitations.

**Terminology:** [`ImageText8`](../../products/notes/glossary.md#imagetext8), [raw
X11](../../products/notes/glossary.md#raw-x11), and related terms are in the
[product notes glossary](../../products/notes/glossary.md); PoC-04-specific pointers
are in [`glossary.md`](glossary.md).

## Usage

```bash
cd experiments/poc-04-notes-x11/
./note-view
# opens a 600×400 window. First line is at y=30, each subsequent line +16 pixels.
# press any key / click the window / close it via the WM → process exits cleanly.
```

If `notes.db` is absent or empty, the window still opens but no text is drawn.
Create entries first with `../poc-03-notes-cli/note`:

```bash
printf 'hello world\n'   | ../poc-03-notes-cli/note
printf 'second entry\n'  | ../poc-03-notes-cli/note
./note-view
```

## Session coupling (read this first)

`note-view` hard-codes three pieces of X11 session state, exactly as
`poc-02/window` did:

| Constant                        | Baked into  | Where to re-derive                  |
| ------------------------------- | ----------- | ----------------------------------- |
| Display socket `/tmp/.X11-unix/X1` | SOCKADDR   | `$DISPLAY`                          |
| MIT-MAGIC-COOKIE-1 (16 bytes)   | setup req   | `xauth list | awk '/:1 /{print $3}'`|
| Root window `0x3fd` (parent)    | CW template | `xwininfo -root`                    |

Every fresh X session invalidates these and the binary must be rebuilt. That
is the unavoidable cost of talking to the X server without linking `libxcb`
or `libX11`. See `../poc-02-x11-window/window.md` for the full discussion.

## Runtime memory map

```
  vaddr range         bytes  what
  -------------------  -----  -----------------------------
  0x400000..0x400077    120   mkelf ELF header + PT_LOAD phdr
  0x400078..0x4002ff    648   CODE (648 = 0x288 bytes)
  0x400300..0x400423    292   DATA (templates + strings)
  0x400424..0x400fff   zero   gap (inside PT_LOAD)
  0x401000..             16K  SETUP_BUF  — X11 connection-setup reply buffer
  0x404000..             32   EVENT_BUF  — current 32-byte event
  0x404100..             256  RECORD_BUF — one notes.db record (capped 64)
  0x404300..             4    SCRATCH    — length-prefix read slot
  ...end of mkelf 0x10000 BSS at 0x410423
```

The segment has `p_flags = R|W|X` (mkelf default), which is essential —
the code patches templates in the DATA section at runtime (e.g. stuffing the
freshly-allocated WID into CreateWindow / ChangeProperty / CreateGC / MapWindow
/ ImageText8 templates), so DATA must be writable, and BSS must be writable
(for SETUP_BUF, EVENT_BUF, RECORD_BUF).

## Register conventions (globals that live across syscalls)

| Register | Contents                                         |
| -------- | ------------------------------------------------ |
| `rbx`    | X11 socket fd (set once by `socket`, never changed) |
| `r12d`   | X11 resource-id-base (from setup reply); WID = `r12d \| 1`, FID = `r12d \| 2`, GID = `r12d \| 3` |
| `r14w`   | current y-coordinate during redraw (init 30, += 16 per record) |
| `r15`    | `notes.db` fd during redraw (undefined otherwise) |

`r10d` is used for Linux 4th-syscall-arg (`MSG_WAITALL` for `recvfrom`, zero
for `sendto`) and is explicitly reset before each send/recv. `r8d` and `r9d`
are zeroed once at startup and never touched again (they stay zero across the
`syscall` instruction per the Linux x86-64 ABI).

## Data section (292 bytes @ 0x400300)

Each template is stored pre-populated with every constant field, plus zero
placeholders for fields that must be patched at runtime (marked `[P]` below).

```
  vaddr     size  template                                        patched
  --------- ----  ----------------------------------------------  ----------
  0x400300  20    sockaddr_un { AF_UNIX, "/tmp/.X11-unix/X1" }    —
  0x400314  48    X11 Setup Request (byte-order 'l', 18-byte      —
                  auth name, 16-byte cookie)
  0x400344  40    CreateWindow (opcode 1): parent=root 0x3fd,     wid  [P]
                  x=0 y=0 w=600 h=400, class=InputOutput,
                  BackPixel=0x00FFFFFF,
                  EventMask = KeyPress|ButtonPress|Exposure
  0x40036c  36    ChangeProperty (opcode 18) WM_NAME=STRING       window [P]
                  data "note-view" (9 bytes + 3 pad)
  0x400390  20    OpenFont (opcode 45) name="fixed"               fid  [P]
  0x4003a4  28    CreateGC (opcode 55): fg=black, bg=white,       gc, drawable, font [P]
                  font=FID, value-mask=0x400C
  0x4003c0   8    MapWindow (opcode 8)                            wid  [P]
  0x4003c8  12    "notes.db\0" padded to 12                       —
  0x4003d4  16    ImageText8 (opcode 76) header:                  byte 1 (n), word [2] (req-len),
                  x=10                                            drawable, gc, word [14] (y) [P]
  0x4003e4  64    ImageText8 string buffer (zero-init)            filled per record
```

WID, FID, GID are derived from `resource-id-base` (r12d) by OR-ing 1, 2, 3
respectively. This only works if the server's `resource-id-mask` has at least
the low 2 bits set — which every conforming server does.

## Code walkthrough (648 bytes @ 0x400078)

The body offset column is relative to the code start (vaddr `0x400078`).

### Section A — Init (51 bytes, 0x000..0x033)

| body | bytes                                       | insn                  |
| ---- | ------------------------------------------- | --------------------- |
| 0x00 | `b8 29 00 00 00`                            | `mov eax, 41` (socket)|
| 0x05 | `bf 01 00 00 00`                            | `mov edi, 1` (AF_UNIX)|
| 0x0a | `be 01 00 00 00`                            | `mov esi, 1` (SOCK_STREAM) |
| 0x0f | `31 d2`                                     | `xor edx, edx`        |
| 0x11 | `0f 05`                                     | `syscall`             |
| 0x13 | `48 89 c3`                                  | `mov rbx, rax`        |
| 0x16 | `b8 2a 00 00 00 / 48 89 df / be 00 03 40 00 / ba 14 00 00 00 / 0f 05` | `connect(rbx, 0x400300, 20)` |
| 0x2a | `45 31 d2 / 45 31 c0 / 45 31 c9`            | zero r10d,r8d,r9d     |

### Section B — X11 handshake (74 bytes, 0x033..0x07d)

Send the 48-byte setup request from `0x400314`, receive the 8-byte reply
header into `SETUP_BUF=0x401000`, extract `additional-data-length` (u16 at
`SETUP_BUF+6`), multiply by 4, and recvfrom that many bytes into
`SETUP_BUF+8`.

| body | bytes                                        | insn / meaning        |
| ---- | -------------------------------------------- | --------------------- |
| 0x33 | `b8 2c ... be 14 03 40 00 ba 30 ... 0f 05`   | `sendto(rbx, 0x400314, 48, 0, 0, 0)` |
| 0x47 | `41 ba 00 01 00 00`                          | `mov r10d, 0x100` (MSG_WAITALL) |
| 0x4d | `b8 2d ... be 00 10 40 00 ba 08 ... 0f 05`   | `recvfrom(rbx, 0x401000, 8, MSG_WAITALL, 0, 0)` |
| 0x61 | `0f b7 04 25 06 10 40 00 / c1 e0 02`         | `eax = *(u16*)0x401006 << 2` |
| 0x6c | `89 c2 / b8 2d ... be 08 10 40 00 / 0f 05`   | `recvfrom(rbx, 0x401008, eax, MSG_WAITALL, 0, 0)` |

### Section C — Create resources (228 bytes, 0x07d..0x161)

The setup reply's `resource-id-base` is at reply offset 12 — i.e.
`SETUP_BUF+12 = 0x40100c`. `r12d` is loaded from there once (`44 8b 24 25 0c
10 40 00`) and then used repeatedly to patch template fields.

Six 13-byte blocks patch the `[P]` fields listed above:

```
44 89 e0          mov eax, r12d
83 c8 NN          or  eax, 1  | 2 | 3
89 04 25 LL LL LL LL   mov [abs32], eax
```

followed by 20-byte `sendto` wrappers (one per request template). The four
templates are sent in protocol-legal order: **CreateWindow** (40 B from
`0x400344`), **ChangeProperty WM_NAME** (36 B from `0x40036c`), **OpenFont**
(20 B from `0x400390`), **CreateGC** (28 B from `0x4003a4`), **MapWindow**
(8 B from `0x4003c0`). The ImageText8 header at `0x4003d4` gets its
`drawable` and `gc` fields patched here too so the redraw loop only has to
patch three more fields (string-length, request-length, y).

`xor r10d, r10d` is issued once before CreateWindow to switch from the
MSG_WAITALL state left over from the handshake recvfroms.

### Section D — Event loop (66 bytes, 0x161..0x1a3)

```
event_loop:
    mov r10d, 0x100              ; MSG_WAITALL
    recvfrom(rbx, 0x404000, 32, MSG_WAITALL, 0, 0)
    test rax, rax
    jle  exit_app                ; EOF or error → connection gone
    movzx al, [EVENT_BUF]
    and  al, 0x7f                ; strip SendEvent bit
    cmp  al, 12   ; Expose
    je   handle_expose
    cmp  al, 2    ; KeyPress
    je   exit_app
    cmp  al, 4    ; ButtonPress
    je   exit_app
    jmp  event_loop              ; ignore anything else (X errors etc.)
```

`jle exit_app` catches both `rax == 0` (socket closed by server, e.g. when
the WM runs `XKillClient` after the user clicks the close button) and
`rax < 0` (any recv error). Either way the window is gone, so we exit
cleanly.

### Section E — Redraw (inlined from `handle_expose`, 210 bytes, 0x1a3..0x275)

On every Expose event:

1.  `open("notes.db", O_RDONLY)`. If this fails, skip — the window still
    exists, the loop goes back to `event_loop`.
2.  Save fd in `r15`; initialise `r14w = 30` (first line's y-coord).
3.  `read_loop`: read a 4-byte length prefix into `SCRATCH=0x404300`; bail
    if less than 4 bytes come back (end-of-file).
4.  Validate: reject length ≤ 0 or > 64 (records larger than the fixed
    buffer are truncated-by-bail, not silently rendered wrong).
5.  Read that many bytes into `RECORD_BUF = 0x404100`.
6.  Strip a trailing `\n` (`poc-03/note` always writes one).
7.  If the record is empty after stripping, skip to the y-increment.
8.  Build the dynamic ImageText8 fields at `0x4003d4`:
    ```
    eax = request-units = 4 + ((n + 3) >> 2)   ; u16 at header+2
    cl  = n                                    ; u8  at header+1
    r14w = y                                   ; u16 at header+14
    ```
    then `rep movsb` copies `n` bytes from `RECORD_BUF` to
    `IT8_STRBUF = 0x4003e4`. The X server reads exactly `n` ASCII bytes
    regardless of any trailing pad bytes in the request stream.
9.  `sendto(rbx, 0x4003d4, request-units * 4, 0, 0, 0)`.
10. `r14w += 16`; jump back to `read_loop`.

When the length read returns fewer than 4 bytes (clean EOF) or validation
fails, we fall through to `redraw_close` — `close(r15)` — then
`redraw_done`'s long jump returns to `event_loop`.

### Section F — exit_app (19 bytes, 0x275..0x288)

```
close(rbx)   ; mov eax, 3 ; mov rdi, rbx ; syscall
exit(0)      ; mov eax, 60 ; xor edi, edi ; syscall
```

The X server will clean up any resources we allocated (WID, FID, GID) as
soon as our side of the socket closes; no explicit `KillClient` / `FreeGC` /
`CloseFont` / `DestroyWindow` requests are needed.

## Syscalls used

| nr | name       | where                                    |
| -- | ---------- | ---------------------------------------- |
|  0 | `read`     | E.3, E.5 (read length prefix + body)     |
|  2 | `open`     | E.1 (`notes.db`)                         |
|  3 | `close`    | redraw_close (db fd), exit_app (socket)  |
| 41 | `socket`   | A.1                                      |
| 42 | `connect`  | A.2                                      |
| 44 | `sendto`   | all X11 outbound requests                |
| 45 | `recvfrom` | handshake + event loop + body read       |
| 60 | `exit`     | exit_app                                 |

Eight syscalls total. No `libc`, no `libX11`, no dynamic linker.

## X11 opcodes and events used

| Opcode | Name            | Where          |
| ------ | --------------- | -------------- |
|  1     | CreateWindow    | C.3            |
|  8     | MapWindow       | C.11           |
| 18     | ChangeProperty  | C.5 (WM_NAME)  |
| 45     | OpenFont        | C.7            |
| 55     | CreateGC        | C.9            |
| 76     | ImageText8      | E.10/11        |

| Event code | Name         | Handling            |
| ---------- | ------------ | ------------------- |
|  0         | Error        | silently ignored    |
|  2         | KeyPress     | clean exit          |
|  4         | ButtonPress  | clean exit          |
| 12         | Expose       | redraw from notes.db |
| other      | anything     | ignored, loop       |

A closed socket (`recvfrom` returns 0) is treated identically to a key
press — this is how the WM close button works: the WM calls
`KillClient(wid)`, the server drops the connection, we see EOF, and we
`exit(0)`.

## Limitations (known, documented, intentional for this POC)

| Limitation | Rationale |
| ---------- | --------- |
| Hard-coded cookie + root WID | No Xauthority parsing, no root-window discovery — costs ~300 bytes of code we haven't written yet |
| Records > 64 bytes truncate the redraw | Fixed 64-byte `IT8_STRBUF` to keep the data section small |
| No scrolling / clipping | If you add >~22 records they'll render past the window bottom |
| No `WM_PROTOCOLS`/`WM_DELETE_WINDOW` | The WM still closes the window cleanly via `KillClient`; we just miss out on doing our own `DestroyWindow` first. No leaked resources either way. |
| No font fallback | Requires the `"fixed"` alias to exist on the X server (always true on stock Xorg + fonts packages) |
| Re-reads `notes.db` on every Expose | Minor; reopens are cheap |

## Addressing the "stray windows" concern

Previous POC-02 runs left zombie windows when the wait-on-first-event path
got interrupted. `note-view` was built with four independent exit paths that
all converge on the same `exit_app` (close fd, exit(0)):

1.  Key press inside the window
2.  Mouse click inside the window
3.  WM close button (via `KillClient` → our recvfrom returns 0 → `jle exit_app`)
4.  `recvfrom` returning a negative value (any network/server error)

No matter which path fires, the socket is closed before exit, the server
frees our WID/FID/GID automatically, and the mutter frame disappears with the
client window.
