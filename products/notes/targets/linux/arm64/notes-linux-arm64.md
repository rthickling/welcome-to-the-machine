# `products/notes/notes-linux-arm64`

`notes-linux-arm64` is a **4736-byte** Linux ELF64 **AArch64** executable: a full
raw-X11 port of the Linux x86_64 flagship
([`notes-linux-x86_64.md`](../x86_64/notes-linux-x86_64.md)). It is a genuine
two-pane Notes GUI hand-authored as fixed-width 32-bit AArch64 instruction words
— no assembler, no libc, no Xlib — that talks the X11 wire protocol directly
over a Unix-domain socket. It runs under `qemu-aarch64-static`, which passes the
X socket syscalls through to the host X server.

Terminology for [BSS](../../../glossary.md#bss), syscalls, and the X11 handshake:
[product notes glossary](../../../glossary.md).

## What it does (verified under qemu against a live X server)

- Discovers the session at runtime: parses `DISPLAY` and `XAUTHORITY`/`HOME`
  from the initial-stack environment, builds `/tmp/.X11-unix/X<n>`, reads the
  `MIT-MAGIC-COOKIE-1` cookie out of the Xauthority file, and connects.
- Parses the setup reply for the resource-id base and the **root window id**
  (from the first SCREEN record) — nothing about the session is baked in.
- Creates a 600×400 window, a graphics context, sets `WM_NAME` to `notes-arm`,
  maps the window, and interns `WM_PROTOCOLS`/`WM_DELETE_WINDOW` so the window
  manager close button exits cleanly.
- Loads `notes.db` (the shared `[u32 len][bytes]` record format), renders a
  two-pane layout: a left editor pane labelled `Note:` and a right list pane
  labelled `Words`, one first-word row per note.
- Handles `Expose` (redraw), `KeyPress` (printable append, Backspace, Enter to
  save a new record and reload), `ButtonPress` (click a list row to load that
  note into the editor), and `ClientMessage` (`WM_DELETE_WINDOW` → clean exit).

## File layout

`mkelf` wraps the body at the fixed entry `0x400078`; a single R/W/X `PT_LOAD`
maps the whole file at vaddr `0x400000`, and `p_memsz` is patched to `0x40000`
to reserve BSS scratch above the file image.

```text
0x000..0x03f     64   ELF64 header (e_machine patched to 0xb7 = EM_AARCH64)
0x040..0x077     56   single PT_LOAD program header (R|W|X, memsz 0x40000)
0x078..0x083c    ~    AArch64 code (entry branch + helpers + _start)
0x0840..0x0fff        zero padding
0x1000..0x125f        data: X11 request templates, UI strings, env strings, keymap
0x1260..            (in memory) BSS scratch: reply, events, editor, slots, auth
```

Code offsets below are given relative to the entry point `0x400078`
(vaddr = `0x400078 + offset`). Data lives at vaddr `0x401000` (file `0x1000`).

## AArch64 conventions used

- Syscall via `svc #0` with the number in `x8`: `socket`=198, `connect`=203,
  `openat`=56, `read`=63, `write`=64, `close`=57, `exit`=93.
- Absolute addresses are built with `MOVZ`/`MOVK` (e.g. `0x413100` =
  `mov x,#0x3100 ; movk x,#65,lsl#16`); the data base `0x401000` is kept in
  `x23` for the whole program and templates are addressed as `x23 + disp`.
- Persistent registers: `x19` = X socket fd, `x23` = data base `0x401000`.
- Global cells live in BSS: editor length at `0x413040`, note count at
  `0x413044`, saved `WM_DELETE_WINDOW` atom at `0x413048`.

## Memory map (BSS scratch, vaddr)

```text
0x410000   setup-reply / connection buffer (read target, ~6–8 KiB)
0x412000   32-byte X event buffer (event-loop read target)
0x412100   32-byte InternAtom reply buffer
0x413000   editor input buffer (up to 63 bytes + the live edit text)
0x413040   editor length (u32 global)
0x413044   note count (u32 global)
0x413048   saved WM_DELETE_WINDOW atom (u32 global)
0x413100   note-slot table: 128 bytes/slot, [u32 len][text...] per note
0x414000   Xauthority file read buffer
0x415000   notes.db read buffer / rewrite staging
0x416000   assembled Xauthority/notes.db path scratch
```

## Code walk-through

### Entry and helpers (`0x000..0x07b`)

```text
0x000  b _start                         ; jump over the helper block
0x004  SEND(x1=ptr, x2=len):            ; write(x19, ptr, len)
       mov x0,x19 ; mov x8,#64 ; svc #0 ; ret
0x014  READ_REPLY:                      ; read(x19, x1, x2) helper
       mov x0,x19 ; mov x8,#63 ; svc #0 ; ret
0x024  drawstr(w3=x, w4=y, x5=src, w6=len):
       ; patch ImageText8 x/y, fill 64-byte payload with spaces, copy len bytes,
       ; then SEND the 80-byte ImageText8 request.
       strh w3,[x23,#192] ; strh w4,[x23,#194]   ; x=disp 0xc0, y=0xc2 in template
       ...
```

`drawstr` is the single text primitive: every label, the editor line, and each
list row goes through the one `ImageText8` template at `0x4010b4`, patching the
16-bit `x`/`y` and the 64-byte string payload in place before writing.

### `draw` (`0x07c..0x13b`)

Redraws the whole UI. It sends the `PolyRectangle` request (the two pane
borders), then calls `drawstr` for `Note:` (16,30), the current editor text
(16,46), `Words` (360,30), and one row per note at `x=360, y=46+16*i` whose
text is the note's first word (scan to the first space). The note count is read
from the global at `0x413044` and each row's text from its slot at
`0x413100 + i*128`.

### `load_db` (`0x13c..0x217`)

```text
0x13c  openat(AT_FDCWD, "notes.db", O_RDONLY)     ; x1 = 0x401130
0x158  b.lt open-fail -> set count 0
0x15c  mov x15,x0 ; read into 0x415000 ; close(x15)
0x184  parse loop: for each [u32 len][bytes] record,
       ; clamp copy length to 63, store [len][text] into slot 0x413100+i*128,
       ; advance the cursor by the record length (x7), stop after 16 notes.
0x208  str <count> at 0x413044 ; ret
```

The cursor advance at `0x1f8` is `add x13, x13, x7` — it skips the record's
declared length, not the last byte copied.

### `save_note` (`0x218..0x2ab`)

Reached from Enter. If the editor length is non-zero it opens `notes.db` with
`O_WRONLY|O_CREAT|O_APPEND` (flags `0x441`), writes a `[u32 len][bytes]` record
built in the `0x415000` staging buffer, closes, and returns so the caller can
reload and repaint.

### `find_env` (`0x2ac..0x2e3`)

`find_env(x1=envp, x2=name, x3=len)` walks the `NULL`-terminated `envp` array,
`memcmp`s each entry's prefix against `name`, and returns a pointer just past
the match (or 0). Used for `DISPLAY=`, `XAUTHORITY=`, and `HOME=`.

### `_start` (`0x2ec..end`)

```text
0x2ec  mov x23,#0x1000 ; movk x23,#64,lsl#16      ; x23 = data base 0x401000
0x2f4  ldr x0,[sp] ; compute envp = sp + (argc+2)*8 -> x27
0x304  find_env(envp, "DISPLAY=", 8)              ; digit after ':' -> sockaddr path[0x12]
0x328  find_env(envp, "XAUTHORITY=", 11)          ; else HOME + "/.Xauthority"
       ; open + read the Xauthority file, scan for "MIT-MAGIC-COOKIE-1",
       ; copy its 16-byte cookie into the setup request at 0x401034.
       socket(AF_UNIX,SOCK_STREAM,0) -> x19
       connect(x19, sockaddr@0x401000, 20)
       SEND setup request (48 bytes) ; READ reply into 0x410000
       ; parse: resource base at reply+12; SCREEN root at
       ;   reply+40 + pad(vendor_len) + n_formats*8 ; wid=base, gc=base+2
       ; patch wid/gc/root into every request template
       SEND CreateWindow, CreateGC, WM_NAME, MapWindow
       ; intern WM_PROTOCOLS + WM_DELETE_WINDOW, ChangeProperty on the window
       load_db ; editor length = 0
       event loop:
         READ 32-byte event from x19
         type & 0x7f: 12=Expose->draw ; 2=KeyPress->key ; 4=ButtonPress->click ;
                      33=ClientMessage-> if data.l[0]==WM_DELETE atom exit(0)
```

### KeyPress handler

Reads keycode `[event+1]` and state `[event+28]`, indexes the keymap at
`0x401200`. `Escape` (0x1b) → `exit(0)`. `Backspace` decrements the editor
length. `Enter` calls `save_note`, clears the editor length, reloads, and
redraws. Printable bytes (0x20..0x7e) are appended to the editor buffer up to 63
chars; if `Shift` (state bit 0) is set and the byte is `a`..`z` it is
upper-cased. The bounds check uses proper `cmp`/`b.hs` — no signed-`-1` quirk.

### ButtonPress handler

Reads `event_x` at `[event+24]` and `event_y` at `[event+26]`. A click with
`x>=360, y>=34` maps to row `(y-34)/16`; if that row is `< count` the note's
text is copied from its slot into the editor buffer, the editor length is set,
and the UI repaints.

## Data templates (`0x401000..0x4011ff`)

All X11 request templates are architecture-independent wire bytes, identical in
shape to the x86_64 flagship; only the runtime-patched id/cookie/root fields
differ. Key anchored offsets (file offset = vaddr − `0x400000`):

```text
0x401000  01 00 /tmp/.X11-unix/X1 00        ; AF_UNIX sockaddr (path digit @0x12)
0x401014  6c 00 0b 00 ...                   ; setup request; cookie @0x401034
0x401044  01 00 0a 00 ...                   ; CreateWindow (wid @0x48, parent @0x4c)
0x401054  58 02 90 01                       ; width 600, height 400
0x401064  20 20 20 00                       ; background pixel 0x202020
0x401068  05 80 00 00                       ; event mask (Expose|Key|Button...)
0x40106c  12 00 09 00 ...                   ; ChangeProperty WM_NAME
0x401084  6e 6f 74 65 73 2d 61 72 6d        ; "notes-arm"
0x401090  37 00 06 00 ...                   ; CreateGC (mask 0x0c: fg+bg)
0x4010a0  e0 e0 e0 00 20 20 20 00           ; GC foreground 0xe0e0e0, background 0x202020
0x4010ac  08 00 02 00 ...                   ; MapWindow
0x4010b4  4c 40 14 00 ...                   ; ImageText8 (string-len 64; x @0xc0, y @0xc2)
0x401104  43 00 07 00 ... rects             ; PolyRectangle (two pane borders)
0x401120  4e 6f 74 65 3a                    ; "Note:"
0x401128  57 6f 72 64 73                    ; "Words"
0x401130  6e 6f 74 65 73 2e 64 62 00        ; "notes.db"
0x40113c  10 00 05 00 ... WM_PROTOCOLS      ; InternAtom
0x401150  10 00 06 00 ... WM_DELETE_WINDOW  ; InternAtom
0x401168  12 00 07 00 ...                   ; ChangeProperty (WM_PROTOCOLS list)
0x401188  DISPLAY= / XAUTHORITY= / HOME= / /.Xauthority / MIT-MAGIC-COOKIE-1
0x401200  keymap: keycode->ASCII table (unshifted), copied from the x86_64 build
```

## Verification

`test-notes-linux-arm64` ([doc](test-notes-linux-arm64.md)) is a Linux x86_64
structural verifier that anchors 17 behavioral byte ranges: the ELF magic and
`EM_AARCH64` machine type, the entry branch, the socket path, the `CreateWindow`
geometry and colour constants, the `notes-arm` title, the `Note:`/`Words`
labels, the `CreateGC`/`ImageText8`/`PolyRectangle` opcodes, the `notes.db`
string, the `WM_DELETE_WINDOW` atom name, and a printable keymap row.

Live behavior was verified under `qemu-aarch64-static` against a running X
server: connect + authenticate, window with borders and pane labels, list
loaded and rendered from `notes.db`, keyboard entry, Enter-save (a new
`[u32 len][bytes]` record was appended and the list reloaded), click-to-load
(clicking a row loaded that note into the editor), and the `WM_DELETE_WINDOW`
close button exiting the process cleanly.

## Known limitations

- Shift only upper-cases `a`..`z`; shifted symbol keys fall through to their
  unshifted glyphs (documented; the x86_64 build carries a fuller keymap).
- There is no per-row delete affordance in this port; Enter-save and
  click-to-load cover the core editing loop. Delete-by-rewrite remains a
  candidate for a follow-up revision.
- Like the x86_64 flagship, the GUI requires a live X server; the always-run
  regression check is the structural verifier above.
