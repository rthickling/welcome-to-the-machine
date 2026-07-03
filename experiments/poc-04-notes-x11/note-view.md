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

Every instruction is listed with its virtual address, raw bytes, and Intel
mnemonic (file offset = `vaddr − 0x400000`). `note-view` shares the connect /
handshake / resource-patch shape with `poc-04/note-edit`
([Section A there](note-edit.md#section-a--connect-to-x-and-fetch-setup-reply-0x0780x1d8)),
but its data base is `0x400300` (not `0x400700`) because the code is smaller,
and it is a **read-only viewer**: it waits for an `Expose`, then re-reads and
redraws `notes.db` with a **variable-length** `ImageText8` request per record.

### Section A — connect to the X server (`0x078..0x0a1`)

```text
400078: b8 29 00 00 00        mov  eax, 0x29           ; __NR_socket (41)
40007d: bf 01 00 00 00        mov  edi, 0x1            ; AF_UNIX
400082: be 01 00 00 00        mov  esi, 0x1            ; SOCK_STREAM
400087: 31 d2                 xor  edx, edx            ; protocol 0
400089: 0f 05                 syscall
40008b: 48 89 c3              mov  rbx, rax            ; rbx = X socket fd (held for life of process)
40008e: b8 2a 00 00 00        mov  eax, 0x2a           ; __NR_connect (42)
400093: 48 89 df              mov  rdi, rbx
400096: be 00 03 40 00        mov  esi, 0x400300       ; sockaddr_un "/tmp/.X11-unix/X1"
40009b: ba 14 00 00 00        mov  edx, 0x14           ; addrlen 20
4000a0: 0f 05                 syscall
```

### Section B — X11 setup handshake (`0x0a2..0x0f4`)

Send the 48-byte setup request, read the 8-byte reply header, then read the
variable remainder whose length (in 4-byte units) sits at `SETUP_BUF+6`.

```text
4000a2: 45 31 d2              xor  r10d, r10d          ; sendto flags = 0
4000a5: 45 31 c0              xor  r8d, r8d            ; dest addr NULL (stays 0 for the whole run)
4000a8: 45 31 c9              xor  r9d, r9d            ; addrlen 0
4000ab: b8 2c 00 00 00        mov  eax, 0x2c           ; __NR_sendto (44)
4000b0: 48 89 df              mov  rdi, rbx
4000b3: be 14 03 40 00        mov  esi, 0x400314       ; setup request template
4000b8: ba 30 00 00 00        mov  edx, 0x30           ; 48 bytes
4000bd: 0f 05                 syscall
4000bf: 41 ba 00 01 00 00     mov  r10d, 0x100         ; recvfrom flags = MSG_WAITALL
4000c5: b8 2d 00 00 00        mov  eax, 0x2d           ; __NR_recvfrom (45)
4000ca: 48 89 df              mov  rdi, rbx
4000cd: be 00 10 40 00        mov  esi, 0x401000       ; SETUP_BUF
4000d2: ba 08 00 00 00        mov  edx, 0x8            ; first 8 bytes
4000d7: 0f 05                 syscall
4000d9: 0f b7 04 25 06 10 40 00  movzx eax, WORD [0x401006] ; additional-data length (4-byte units)
4000e1: c1 e0 02              shl  eax, 0x2            ; × 4 = remaining byte count
4000e4: 89 c2                 mov  edx, eax
4000e6: b8 2d 00 00 00        mov  eax, 0x2d           ; __NR_recvfrom
4000eb: 48 89 df              mov  rdi, rbx
4000ee: be 08 10 40 00        mov  esi, 0x401008       ; continue after the header
4000f3: 0f 05                 syscall
```

### Section C — patch resource ids and create the window (`0x0f5..0x1d8`)

`r12d` takes the resource-id base from `SETUP_BUF+12`. Each template field is
patched with `base | 1/2/3` (window/font/gc), then the five bring-up requests
are sent in protocol order. The `ImageText8` header's `drawable`/`gc` are
pre-patched here so the redraw loop only fills in length and `y`.

```text
4000f5: 44 8b 24 25 0c 10 40 00  mov r12d, DWORD [0x40100c]  ; resource-id base
4000fd: 44 89 e0              mov  eax, r12d
400100: 83 c8 01              or   eax, 0x1            ; window id = base | 1
400103: 89 04 25 48 03 40 00  mov  DWORD [0x400348], eax   ; CreateWindow.wid
40010a: 45 31 d2              xor  r10d, r10d          ; sendto flags = 0 (leave MSG_WAITALL state)
40010d: b8 2c 00 00 00        mov  eax, 0x2c
400112: 48 89 df              mov  rdi, rbx
400115: be 44 03 40 00        mov  esi, 0x400344       ; CreateWindow
40011a: ba 28 00 00 00        mov  edx, 0x28           ; 40 bytes
40011f: 0f 05                 syscall
400121: 44 89 e0              mov  eax, r12d
400124: 83 c8 01              or   eax, 0x1            ; window id | 1
400127: 89 04 25 70 03 40 00  mov  DWORD [0x400370], eax   ; ChangeProperty.window
40012e: b8 2c 00 00 00        mov  eax, 0x2c
400133: 48 89 df              mov  rdi, rbx
400136: be 6c 03 40 00        mov  esi, 0x40036c       ; ChangeProperty(WM_NAME="note-view")
40013b: ba 24 00 00 00        mov  edx, 0x24           ; 36 bytes
400140: 0f 05                 syscall
400142: 44 89 e0              mov  eax, r12d
400145: 83 c8 02              or   eax, 0x2            ; font id = base | 2
400148: 89 04 25 94 03 40 00  mov  DWORD [0x400394], eax   ; OpenFont.fid
40014f: b8 2c 00 00 00        mov  eax, 0x2c
400154: 48 89 df              mov  rdi, rbx
400157: be 90 03 40 00        mov  esi, 0x400390       ; OpenFont("fixed")
40015c: ba 14 00 00 00        mov  edx, 0x14           ; 20 bytes
400161: 0f 05                 syscall
400163: 44 89 e0              mov  eax, r12d
400166: 83 c8 03              or   eax, 0x3            ; gc id = base | 3
400169: 89 04 25 a8 03 40 00  mov  DWORD [0x4003a8], eax   ; CreateGC.gc
400170: 44 89 e0              mov  eax, r12d
400173: 83 c8 01              or   eax, 0x1            ; window id | 1
400176: 89 04 25 ac 03 40 00  mov  DWORD [0x4003ac], eax   ; CreateGC.drawable (the window)
40017d: 44 89 e0              mov  eax, r12d
400180: 83 c8 02              or   eax, 0x2            ; font id | 2
400183: 89 04 25 bc 03 40 00  mov  DWORD [0x4003bc], eax   ; CreateGC.font value
40018a: b8 2c 00 00 00        mov  eax, 0x2c
40018f: 48 89 df              mov  rdi, rbx
400192: be a4 03 40 00        mov  esi, 0x4003a4       ; CreateGC
400197: ba 1c 00 00 00        mov  edx, 0x1c           ; 28 bytes
40019c: 0f 05                 syscall
40019e: 44 89 e0              mov  eax, r12d
4001a1: 83 c8 01              or   eax, 0x1            ; window id | 1
4001a4: 89 04 25 c4 03 40 00  mov  DWORD [0x4003c4], eax   ; MapWindow.window
4001ab: b8 2c 00 00 00        mov  eax, 0x2c
4001b0: 48 89 df              mov  rdi, rbx
4001b3: be c0 03 40 00        mov  esi, 0x4003c0       ; MapWindow
4001b8: ba 08 00 00 00        mov  edx, 0x8            ; 8 bytes
4001bd: 0f 05                 syscall
4001bf: 44 89 e0              mov  eax, r12d
4001c2: 83 c8 01              or   eax, 0x1            ; window id | 1
4001c5: 89 04 25 d8 03 40 00  mov  DWORD [0x4003d8], eax   ; ImageText8.drawable
4001cc: 44 89 e0              mov  eax, r12d
4001cf: 83 c8 03              or   eax, 0x3            ; gc id | 3
4001d2: 89 04 25 dc 03 40 00  mov  DWORD [0x4003dc], eax   ; ImageText8.gc
```

### Section D — event loop (`0x1d9..0x21a`)

Unlike `note-edit`, `note-view` does **not** draw immediately; it blocks for
events and only redraws on `Expose`. A key press, button press, or closed
socket exits.

```text
4001d9: 41 ba 00 01 00 00     mov  r10d, 0x100         ; MSG_WAITALL
4001df: b8 2d 00 00 00        mov  eax, 0x2d           ; __NR_recvfrom
4001e4: 48 89 df              mov  rdi, rbx
4001e7: be 00 40 40 00        mov  esi, 0x404000       ; EVENT_BUF
4001ec: ba 20 00 00 00        mov  edx, 0x20           ; 32-byte event
4001f1: 0f 05                 syscall
4001f3: 48 85 c0              test rax, rax
4001f6: 0f 8e f1 00 00 00     jle  0x4002ed           ; <=0 (closed/error) → exit_app
4001fc: 8a 04 25 00 40 40 00  mov  al, [0x404000]      ; EVENT_BUF[0] = type
400203: 24 7f                 and  al, 0x7f            ; strip send_event bit
400205: 3c 0c                 cmp  al, 0x0c
400207: 74 12                 je   0x40021b           ; Expose (12) → redraw
400209: 3c 02                 cmp  al, 0x02
40020b: 0f 84 dc 00 00 00     je   0x4002ed           ; KeyPress (2) → exit
400211: 3c 04                 cmp  al, 0x04
400213: 0f 84 d4 00 00 00     je   0x4002ed           ; ButtonPress (4) → exit
400219: eb be                 jmp  0x4001d9           ; ignore anything else
```

`jle` at `0x4001f6` handles both `rax == 0` (WM closed the window via
`KillClient` → socket EOF) and `rax < 0` (any error): either way the window is
gone, so we exit.

### Section E — redraw on Expose (`0x21b..0x2ec`)

Opens `notes.db`, then for each length-prefixed record builds a
**variable-length** `ImageText8` request sized to that record and sends it at
the next `y`. This is the key contrast with `note-edit`, which always sends a
fixed 80-byte (64-char) request.

```text
40021b: b8 02 00 00 00        mov  eax, 0x2           ; __NR_open
400220: bf c8 03 40 00        mov  edi, 0x4003c8       ; "notes.db"
400225: 31 f6                 xor  esi, esi            ; O_RDONLY
400227: 31 d2                 xor  edx, edx
400229: 0f 05                 syscall
40022b: 48 85 c0              test rax, rax
40022e: 0f 88 b4 00 00 00     js   0x4002e8           ; open failed → back to event loop
400234: 49 89 c7              mov  r15, rax            ; r15 = db fd
400237: 41 be 1e 00 00 00     mov  r14d, 0x1e         ; y = 30 (first line)
; --- read the 4-byte length prefix ---
40023d: 31 c0                 xor  eax, eax           ; __NR_read (0)
40023f: 4c 89 ff              mov  rdi, r15
400242: be 00 43 40 00        mov  esi, 0x404300       ; SCRATCH (length word)
400247: ba 04 00 00 00        mov  edx, 0x4
40024c: 0f 05                 syscall
40024e: 48 83 f8 04           cmp  rax, 0x4            ; full prefix?
400252: 0f 85 86 00 00 00     jne  0x4002de           ; EOF / short read → close
400258: 8b 0c 25 00 43 40 00  mov  ecx, [0x404300]    ; record length
40025f: 83 f9 00              cmp  ecx, 0x0
400262: 7e 7a                 jle  0x4002de           ; length <= 0 → close
400264: 83 f9 40              cmp  ecx, 0x40
400267: 7f 75                 jg   0x4002de           ; length > 64 → close (buffer cap)
; --- read the record body ---
400269: 89 ca                 mov  edx, ecx
40026b: 31 c0                 xor  eax, eax           ; __NR_read
40026d: 4c 89 ff              mov  rdi, r15
400270: be 00 41 40 00        mov  esi, 0x404100       ; RECORD_BUF
400275: 0f 05                 syscall
400277: 48 85 c0              test rax, rax
40027a: 7e 62                 jle  0x4002de           ; error/EOF → close
40027c: 89 c1                 mov  ecx, eax            ; ecx = bytes read
40027e: 8a 81 ff 40 40 00     mov  al, [rcx+0x4040ff] ; last byte (RECORD_BUF+len-1)
400284: 3c 0a                 cmp  al, 0xa
400286: 75 03                 jne  0x40028b
400288: 83 e9 01              sub  ecx, 0x1            ; strip trailing newline
40028b: 83 f9 00              cmp  ecx, 0x0
40028e: 7e 44                 jle  0x4002d4           ; empty after strip → just advance y
; --- build the variable-length ImageText8 request ---
400290: 8d 41 03              lea  eax, [rcx+0x3]
400293: c1 e8 02              shr  eax, 0x2           ; (n+3) >> 2  = string words
400296: 83 c0 04              add  eax, 0x4           ; + 4 header words = request length (units)
400299: 88 0c 25 d5 03 40 00  mov  [0x4003d5], cl     ; header byte 1 = string length n
4002a0: 66 89 04 25 d6 03 40 00  mov WORD [0x4003d6], ax ; header word 2 = request length (units)
4002a8: 66 44 89 34 25 e2 03 40 00  mov WORD [0x4003e2], r14w ; header word 14 = y
4002b1: be 00 41 40 00        mov  esi, 0x404100       ; RECORD_BUF
4002b6: bf e4 03 40 00        mov  edi, 0x4003e4       ; ImageText8 string buffer
4002bb: f3 a4                 rep movsb                ; copy n bytes (ecx = n)
4002bd: c1 e0 02              shl  eax, 0x2           ; request length × 4 = byte count
4002c0: 89 c2                 mov  edx, eax
4002c2: 45 31 d2              xor  r10d, r10d          ; sendto flags = 0
4002c5: b8 2c 00 00 00        mov  eax, 0x2c           ; __NR_sendto
4002ca: 48 89 df              mov  rdi, rbx
4002cd: be d4 03 40 00        mov  esi, 0x4003d4       ; ImageText8 request
4002d2: 0f 05                 syscall
4002d4: 66 41 83 c6 10        add  r14w, 0x10         ; next line y += 16
4002d9: e9 5f ff ff ff        jmp  0x40023d           ; next record
; --- done: close db, return to event loop ---
4002de: b8 03 00 00 00        mov  eax, 0x3           ; __NR_close
4002e3: 4c 89 ff              mov  rdi, r15
4002e6: 0f 05                 syscall
4002e8: e9 ec fe ff ff        jmp  0x4001d9           ; back to the event loop
```

The request-length arithmetic `4 + ((n+3) >> 2)` rounds the `n`-byte string up
to whole 4-byte units and adds the four header words, so the `sendto` byte
count (`× 4`) is always a legal X11 request length with no padding sent beyond
what the string needs.

### Section F — exit_app (`0x2ed..0x2ff`)

```text
4002ed: b8 03 00 00 00        mov  eax, 0x3           ; __NR_close
4002f2: 48 89 df              mov  rdi, rbx            ; X socket
4002f5: 0f 05                 syscall
4002f7: b8 3c 00 00 00        mov  eax, 0x3c          ; __NR_exit (60)
4002fc: 31 ff                 xor  edi, edi           ; status 0
4002fe: 0f 05                 syscall
```

Closing the socket makes the server free the window, font, and GC — no explicit
`KillClient` / `FreeGC` / `CloseFont` / `DestroyWindow` is needed.

## Syscalls used

| nr | name       | where                                                    |
| -- | ---------- | -------------------------------------------------------- |
|  0 | `read`     | `0x40023d`, `0x40026b` (length prefix + record body)      |
|  2 | `open`     | `0x40021b` (`notes.db`)                                   |
|  3 | `close`    | `0x4002de` (db fd), `0x4002ed` (socket)                   |
| 41 | `socket`   | `0x400078`                                                |
| 42 | `connect`  | `0x40008e`                                                |
| 44 | `sendto`   | all X11 outbound requests (setup, bring-up, `ImageText8`) |
| 45 | `recvfrom` | handshake (`0x4000c5`, `0x4000e6`) + event loop (`0x4001df`) |
| 60 | `exit`     | `0x4002f7`                                                |

Eight syscalls total. No `libc`, no `libX11`, no dynamic linker.

## X11 opcodes and events used

| Opcode | Name            | Sent from (`sendto` at)   |
| ------ | --------------- | ------------------------- |
|  1     | CreateWindow    | `0x40010d`                |
|  8     | MapWindow       | `0x4001ab`                |
| 18     | ChangeProperty  | `0x40012e` (WM_NAME)      |
| 45     | OpenFont        | `0x40014f`                |
| 55     | CreateGC        | `0x40018a`                |
| 76     | ImageText8      | `0x4002c5` (per record)   |

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
