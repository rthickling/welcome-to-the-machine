# `products/notes/notes-linux-x86_64`

`notes-linux-x86_64` is a **2632-byte** statically-linked Linux ELF64 x86_64
binary. It is the first product-oriented note tool in the repo and is derived
directly from the earlier raw-X11 editor documented in
[`../../../../../experiments/poc-04-notes-x11/note-edit.md`](../../../../../experiments/poc-04-notes-x11/note-edit.md).

The file keeps most of the same machine code, but appends a small border /
Shift-key helper region and patches the title, labels, draw path, and event dispatch so the UI
behaves like a two-pane note tool:

- left side: full note editor
- right side: alphabetical first-word list
- mouse click on the right list: load note into the editor
- click the per-row `Del` affordance at the far right: remove that row and
  rewrite `notes.db` so the deletion persists
- `Enter`: save the current editor contents as a note record
- normal printable ASCII keys, including shifted uppercase letters and symbols
- dark background, light text, and simple pane borders

## Terminology

This document uses **X11 protocol**, **memory layout**, and **disassembly** names
liberally. The canonical definitions are in the [**product notes
glossary**](../../../glossary.md). Start there for [**ImageText8**](../../../glossary.md#imagetext8)
(the X11 request used to draw text in the window), **IT8 buffer** / **wire
request**, **BSS**, **slot** / **NOTE_COUNT**, **INPUT_LEN**, **recvfrom** main
loop, **ChangeProperty** / **WM_NAME**, the **`fill_it8`** and **`send_it8`**
helpers, and **raw X11**. **User-visible product rules** (note pane vs list,
first-word sort, and so on) are in [`product-contract.md`](../../../contract.md),
which also [links to the glossary](../../../glossary.md) for implementation names.

## What stayed the same

Large parts of the binary are intentionally unchanged from `poc-04/note-edit`:

- ELF header and `PT_LOAD`
- X11 setup handshake and resource-id patching
- hard-coded X socket / cookie / root window coupling
- note loader and insertion sort
- input buffer limits and the save/backspace paths
- helper routines `fill_it8_spaces`, `send_it8`, and `exit_app`

For those unchanged regions, the canonical byte-level explanation is still
[`../../../../../experiments/poc-04-notes-x11/note-edit.md`](../../../../../experiments/poc-04-notes-x11/note-edit.md).

One intentional X11 template change was also made in-place: the window's event
mask now requests `ButtonPress` in addition to the earlier `KeyPress` and
`Expose` delivery, so the product's click-to-load and click-to-delete paths can
actually receive mouse events from the X server.

## On-disk note format

Like the earlier note tools, the database is:

```text
[4-byte little-endian length][length bytes of text]
```

The current Linux product build now has split persistence behavior:

- clicking a note loads it into the editor pane
- clicking `Del` rewrites `notes.db` from the current in-memory note slots
- editing changes the left-pane text buffer
- pressing `Enter` stores the current left-pane contents as a new record

The delete rewrite helper keeps the same outer framing:

```text
[4-byte little-endian length][length bytes of text]
```

but currently emits each surviving note as a 64-byte padded payload record. The
loader already accepts those fixed-width records because `64` is still within
its existing accepted length range.

## Fixed string patches

These are **data bytes** inside the `PT_LOAD` image (spliced into templates or
padding). The CPU only treats them as instructions if execution erroneously
transfers to these offsets; the normal product paths `mov`/`rep movs` them into
string buffers or wire templates instead.

Four anchored strings are now changed or populated in-place:

### Window title at file offset `0x784`

```text
6e 6f 74 65 73 2d 78 36 34
```

ASCII:

```text
notes-x64
```

This replaces the older `note-edit` title while keeping the same 9-byte payload
size inside the `ChangeProperty(WM_NAME=...)` template.

### Left-pane label at `0x824`

```text
4e 6f 74 65 3a
```

ASCII:

```text
Note:
```

This replaces the old `"New: "` label.

### Right-pane header at `0x870`

```text
57 6f 72 64 73
```

ASCII:

```text
Words
```

This is written into previously unused zero padding near the end of the old
keymap area and used by the new draw routine.

### Delete label at `0x878`

```text
44 65 6c
```

ASCII:

```text
Del
```

The draw helper copies these three bytes into the [`ImageText8`](../../../glossary.md#imagetext8) payload when it
renders the per-row delete affordance near the right edge of the list pane.

### Colour and border constants

The `CreateWindow` template now uses a 2-pixel border width and a dark
background pixel:

```text
0x758: 02 00
0x764: 20 20 20 00
```

The `CreateGC` value list now uses light foreground text/border colour and the
same dark background:

```text
0x7b4: e0 e0 e0 00 20 20 20 00
```

### Expanded printable keymap

The unshifted X keycode table still starts at `0x82a`. The printable row range
from file offset `0x83e` now includes `=`, `[`, `]`, `;`, backtick, and
backslash in addition to the earlier letters, digits, space, and punctuation:

```text
2d 3d 08 00 71 77 65 72 74 79 75 69 6f 70 5b 5d
0a 00 61 73 64 66 67 68 6a 6b 6c 3b 27 60 00 5c
```

## Control-flow patches

Five old control-flow sites now redirect into product-specific code stored in
the old padding gap or the appended end of the load image.

### Key handler redirect at `0x1de`

The old first key-translation instruction is replaced with:

```text
e9 80 07 00 00 90 90 90
```

**Execution logic:** `RIP_after = 0x4001e3`, displacement `0x780`, target
`0x400963`. The three `90` bytes are inert padding over the rest of the old
8-byte instruction. The new target performs Shift-aware printable translation,
then jumps back to the old append / save / backspace paths.

### Startup redirect at `0x1d9`

The original jump into `redraw`:

```text
e9 1b 01 00 00
```

**Previous execution logic:** `RIP_after` was the same `0x4001de`, displacement
`0x11b`, so control transferred to `0x4001de+0x11b = 0x4002f9`, the unmodified
`poc-04` `redraw` / load entry.

became:

```text
e9 5b 03 00 00
```

**Execution logic:** relative displacement `0x35b` is added to
`RIP_after_instruction = 0x4001de` (the byte after the five-byte jump), so the
next instruction executed is `0x4001de+0x35b = 0x400539`, the new startup stub
that initialises selection and then jumps into the old `redraw` path.

### Draw redirect at `0x417`

The first call in the old draw sequence was replaced with:

```text
e9 2d 01 00 00
```

**Execution logic:** `RIP_after = 0x40041c`, displacement `0x12d`, target
`0x40041c+0x12d = 0x400549`, the start of the two-pane draw routine that calls
`fill_it8` / `send_it8` as described above.

### Event dispatch redirect at `0x4d7`

The old `Expose` / `KeyPress` compare chain was replaced with:

```text
e9 44 01 00 00
```

**Execution logic:** `RIP_after = 0x4004dc`, displacement `0x144`, target
`0x4004dc+0x144 = 0x400620`, the first instruction of the new dispatcher that
classifies `Expose` / `KeyPress` / `ButtonPress` before returning to the receive
loop.

**Runtime effect of each redirect (all are 32-bit relative `jmp`):** at the
patched instruction pointer, execution continues in the padding / new routine
instead of the original `poc-04` target. The displacement in each `e9` quad is
chosen so the next instruction decoded is the first byte of the new code
region; no registers are set by the jump itself, so the new entry code must
establish its own register conventions.

### Border draw call at `0x549`

The first `call fill_it8` in the product draw routine is replaced with:

```text
e8 dc 03 00 00
```

**Execution logic:** `RIP_after = 0x40054e`, displacement `0x3dc`, target
`0x40092a`. The appended helper draws the pane borders, calls the original
`fill_it8`, and returns to `0x40054e`, so the rest of the two-pane text draw
routine continues unchanged.

## New code regions: `0x539..0x6e6`, `0x893..0x90d`, and `0x92a..0xa47`

The old binary had a long zero padding region between the code and fixed data
base, plus another unused zero pocket near the later data area.
`notes-linux-x86_64` uses both spaces for new behavior without moving the data
section.

### Region overview

| Range | Purpose |
| --- | --- |
| `0x539..0x548` | startup stub |
| `0x549..0x61f` | two-pane draw routine |
| `0x620..0x645` | event dispatcher |
| `0x646..0x6c9` | row draw helper plus click hit-testing / row action logic |
| `0x6ca..0x6e6` | tail clear helper for unused right-pane rows |
| `0x893..0x90d` | persistent delete rewrite helper |
| `0x92a..0x962` | border draw helper |
| `0x963..0x9ab` | Shift-aware key handler |
| `0x9ac..0xa2b` | 128-byte Shift translation table |
| `0xa2c..0xa47` | `PolyRectangle` border request template |

## Instruction-level logic for executable sequences

The sections below are the running instruction sequences that implement the
product behavior, as they appear in the current binary. Fixed strings above are
**data** embedded in the image; they are not a control-flow path unless
copied/used by the instructions below.

### Border draw helper (`0x40092a`)

The helper copies the already-patched drawable and GC IDs from the `ImageText8`
template into a `PolyRectangle` request at `0x400a2c`, sends the request, then
calls the original `fill_it8` helper so the existing draw routine sees the same
blank text buffer it expected before the border call was inserted.

```text
40092a: 8b 04 25 d8 07 40 00          mov     eax, [0x4007d8]         ; drawable from IT8
400931: 89 04 25 30 0a 40 00          mov     [0x400a30], eax         ; rectangle drawable
400938: 8b 04 25 dc 07 40 00          mov     eax, [0x4007dc]         ; GC from IT8
40093f: 89 04 25 34 0a 40 00          mov     [0x400a34], eax         ; rectangle GC
400946: 45 31 d2                      xor     r10d, r10d              ; sendto flags = 0
400949: b8 2c 00 00 00                mov     eax, 0x2c               ; __NR_sendto
40094e: 48 89 df                      mov     rdi, rbx                ; X socket
400951: be 2c 0a 40 00                mov     esi, 0x400a2c           ; PolyRectangle request
400956: ba 1c 00 00 00                mov     edx, 0x1c               ; 28 bytes
40095b: 0f 05                         syscall
40095d: e8 93 fb ff ff                call    0x4004f5                ; original fill_it8
400962: c3                            ret
```

The rectangle request itself is:

```text
400a2c: 43 00 07 00                   PolyRectangle, length 7
400a30: 00 00 00 00                   drawable, patched at runtime
400a34: 00 00 00 00                   GC, patched at runtime
400a38: 08 00 14 00 4a 01 34 00       left pane rectangle: x=8 y=20 w=330 h=52
400a40: 5e 01 14 00 ee 00 5e 01       right pane rectangle: x=350 y=20 w=238 h=350
```

### Shift-aware key handler (`0x400963`)

The old key handler indexed one baked table and therefore could not distinguish
Shift from unshifted key presses. The new entry keeps the old special-key
targets, tests the X11 event-state Shift bit at `EVENT_BUF+28`, and maps the
unshifted ASCII byte through the 128-byte table at `0x4009ac` before rejoining
the old append path.

```text
400963: 0f b6 04 25 01 40 40 00       movzx   eax, byte [0x404001]    ; X keycode
40096b: 0f b6 80 2a 08 40 00          movzx   eax, byte [rax+0x40082a]; unshifted byte
400972: 84 c0                         test    al, al
400974: 0f 84 3a fb ff ff             je      0x4004b4                ; unmapped: ignore
40097a: 3c 1b                         cmp     al, 0x1b
40097c: 0f 84 a4 fb ff ff             je      0x400526                ; Escape
400982: 3c 08                         cmp     al, 0x08
400984: 0f 84 aa f8 ff ff             je      0x400234                ; Backspace
40098a: 3c 0a                         cmp     al, 0x0a
40098c: 0f 84 bf f8 ff ff             je      0x400251                ; Enter
400992: f6 04 25 1c 40 40 00 01       test    byte [0x40401c], 0x01   ; ShiftMask
40099a: 0f 84 6d f8 ff ff             je      0x40020d                ; unshifted append
4009a0: 0f b6 80 ac 09 40 00          movzx   eax, byte [rax+0x4009ac]; shifted ASCII
4009a7: e9 61 f8 ff ff                jmp     0x40020d                ; old append path
```

The Shift table is an ASCII-indexed byte table. Most entries are identity
mappings; the printable entries encode digits to symbols, punctuation pairs,
and `a`..`z` to `A`..`Z`:

```text
000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
202122232425262228292a2b3c5f3e3f2921402324255e262a283a3a3c2b3e3f
404142434445464748494a4b4c4d4e4f505152535455565758595a7b7c7d5e5f
7e4142434445464748494a4b4c4d4e4f505152535455565758595a7b7c7d7e7f
```

### `fill_it8` and `send_it8` helpers (reused, `0x4f5` / `0x505`)

`fill_it8` at `0x4004f5` clears 64 bytes at `0x4007e4` to ASCII space, then
`ret`. It is the blank canvas used before any [`ImageText8`](../../../glossary.md#imagetext8) string is copied in.

`send_it8` at `0x400505` patches the 16-bit Y coordinate in the fixed template
at `0x4007e2` from `r14w`, then issues `__NR_sendto` with `esi` pointing at
`0x4007d4` (the 80-byte wire request) and `edx=0x50`, using the X socket in
`rbx`. The routine finishes with `ret`. The draw and click code calls these
routines instead of inlining the syscall bytes each time.

**Disassembly (`0x4004f5`–`0x400525`, Intel syntax, raw opcodes shown):**

```text
; --- Block: fill_it8 (0x4004f5) + send_it8 (0x400505) — shared X11 text pipeline ---
; Product requirement: the UI must render many strings (headers, editor echo,
;   per-row list, Del) through one fixed ImageText8 template in the load segment.
;   Without clearing between uses, a shorter string would leave garbage pixels
;   from the previous line; fill_it8 guarantees a clean 64-byte payload every time.
; send_it8 completes the requirement “paint this string now” by patching only Y
;   (X is patched in-line by each caller at 0x4007e0) and reusing the same 80-byte
;   prebuilt request, matching poc-04 and avoiding N copies of sendto+encode.
4004f5: bf e4 07 40 00                mov     edi, 0x4007e4          ; EDI = ImageText8 char buffer
4004fa: b9 40 00 00 00                mov     ecx, 0x40              ; clear 64 bytes
4004ff: b0 20                         mov     al, 0x20               ; fill value = ASCII space
400501: fc                            cld                            ; string ops forward
400502: f3 aa                         rep stosb                      ; blank buffer
400504: c3                            ret
400505: 66 44 89 34 25 e2 07 40 00    mov     WORD [0x4007e2], r14w  ; patch Y in X request template
40050e: 45 31 d2                      xor     r10d, r10d             ; sendto: flags = 0
400511: b8 2c 00 00 00                mov     eax, 0x2c              ; __NR_sendto
400516: 48 89 df                      mov     rdi, rbx               ; X11 socket (fd in RBX)
400519: be d4 07 40 00                mov     esi, 0x4007d4          ; buffer: full wire ImageText8 req
40051e: ba 50 00 00 00                mov     edx, 0x50              ; 80 request bytes
400523: 0f 05                         syscall                        ; send ImageText8
400525: c3                            ret
```

### Startup stub

The first bytes in the new region are:

```text
c7 04 25 04 48 40 00 ff ff ff ff
e9 b0 fd ff ff
```

Meaning:

- `mov dword [0x404804], 0xffffffff` — initialise the selected-row slot to
  `-1`
- `jmp redraw` — rejoin the old load/sort path after initialisation

**How those bytes execute:** the absolute `mov` to a fixed BSS address is a
5-byte `c7` group immediate store with a 32-bit sign-extended value. The
following `e9` is a near jump whose displacement targets the `redraw` label in
the original `poc-04` text (the `note.db` open / sort / draw entry), so
execution falls through the older loader with selection already set to “no
row”.

**Disassembly (`0x400539`–`0x400548`):**

```text
; --- Block: startup stub (0x400539) — product selection state before first draw ---
; Requirement (contract: list vs editor): click-to-load stores a row index in
;   0x404804; the product must not show a spurious “selected” row on cold start.
;   -1 means “no list row is selected” so later hit-tests and the load path
;   can tell “user never clicked the list” from “user clicked row 0”.
; Jump: must still enter the unmodified loader/sort from poc-04 so notes.db
;   and alphabetical order match the rest of the product family.
400539: c7 04 25 04 48 40 00 ff ff ff ff   mov  DWORD [0x404804], 0xffffffff
        ; 0x404804 = selected row; -1 = no row selected
400544: e9 b0 fd ff ff                    jmp  0x4002f9
        ; 0x4002f9: open notes.db, insertion-sort, then fall into draw path
```

### Two-pane draw routine

Opcode sequence (virtual `0x400549` upward; calls abbreviated as the helper
prologue/epilogue you get from a `call`):

- `call border_draw` (which finishes by calling `fill_it8`) then
  `mov [0x4007e0], 0x10` and `rep movs` 5 bytes from
  `0x400824` (`"Note:"`) into the IT8 string buffer, then set `r14d=0x1e` and
  `call send_it8` to paint the left header at `y=30`.
- `call fill_it8` again, set `x=0x10`, `rep movs` the live editor from
  `0x404100` for `INPUT_LEN` bytes, set `r14d=0x2e`, `call send_it8` for the
  editor line at `y=46`.
- `call fill_it8`, set `x=0x168`, `rep movs` 5 bytes from `0x400870` (`Words`),
  set `r14d=0x1e`, `call send_it8` for the right header.
- **Per-note loop at `0x4005d7`:** `cmp ebp, NOTE_COUNT` and exit the loop to the
  tail when `ebp >= NOTE_COUNT` (`7d` branch to the tail-clear `jmp`).
  - Inside, `call fill_it8`, set `x=0x168`, set `esi` to `slot[ebp]` at
    `0x404300+ebp*64`, copy up to 64 input bytes in a `lods` / `stos` micro-loop
    that stops at the first space so only the “first word” is expanded into the
    IT8 buffer, then `jmp` to the shared `Del` line piece.
- **At `0x40064b`:** after a row’s text, `call fill_it8`, `call send_it8` for
  that line, set `x=0x220`, `rep movs` 3 bytes from `0x400878` (`Del`), and
  `call send_it8` again. Then add `0x10` to `r14` (next row’s `y`) and `inc ebp`
  and go back to the per-note loop head.
- When the per-note count is satisfied, a near `jmp` at `0x40061b` goes to the
  tail clear helper; when that returns, the routine falls into the X11 receive
  loop (see event dispatcher below)

**Disassembly — main two-pane draw and per-note loop (`0x400549`–`0x40061b`):**

```text
; === Two-pane draw (0x400549) — contract § note pane + list pane + first-word list ===
; This routine satisfies: (1) “main editing area” shows live buffer 0x404100;
;   (2) “secondary list” is sorted in memory already — we only render it;
;   (3) first-word rule: only bytes before the first space appear in the right
;   list (micro-loop 0x400605..0x40060b); (4) fixed row pitch 16px so hit-testing
;   in the click handler can use the same geometry.
; --- Sub-block: left chrome (labels “Note:” + current editor text) ---
400549: e8 dc 03 00 00                call    0x40092a                 ; draw borders, then clear IT8
40054e: 66 c7 04 25 e0 07 40 00 10 00   mov     WORD [0x4007e0], 0x10
        ; 0x4007e0 = x in template; 0x10 = left column (product: note pane)
400558: be 24 08 40 00                mov     esi, 0x400824          ; "Note:" source
40055d: bf e4 07 40 00                mov     edi, 0x4007e4
400562: b9 05 00 00 00                mov     ecx, 5
400567: fc                            cld
400568: f3 a4                         rep movsb                      ; copy label into buffer
40056a: 41 be 1e 00 00 00             mov     r14d, 0x1e             ; y = 30 (header row)
400570: e8 90 ff ff ff                call    0x400505                 ; draw left header
400575: e8 7b ff ff ff                call    0x4004f5                 ; clear again
40057a: 66 c7 04 25 e0 07 40 00 10 00   mov   WORD [0x4007e0], 0x10
        ; same x: editor echoes under “Note:” (full text, not first-word)
400584: be 00 41 40 00                mov     esi, 0x404100            ; editor buffer
400589: bf e4 07 40 00                mov     edi, 0x4007e4
40058e: 8b 0c 25 80 41 40 00          mov     ecx, [0x404180]        ; INPUT_LEN
400595: fc                            cld
400596: f3 a4                         rep movsb                      ; current note text
400598: 41 be 2e 00 00 00             mov     r14d, 0x2e              ; y = 46 (line under "Note:")
40059e: e8 62 ff ff ff                call    0x400505                 ; draw editor line
; --- Sub-block: right header “Words” (separates list from editor visually) ---
4005a3: e8 4d ff ff ff                call    0x4004f5                 ; clear for "Words" line
4005a8: 66 c7 04 25 e0 07 40 00 68 01   mov  WORD [0x4007e0], 0x168
        ; x = 0x168 = 360, right "Words" column (list pane)
4005b2: be 70 08 40 00                mov     esi, 0x400870          ; "Words"
4005b7: bf e4 07 40 00                mov     edi, 0x4007e4
4005bc: b9 05 00 00 00                mov     ecx, 5
4005c1: fc                            cld
4005c2: f3 a4                         rep movsb                      ; "Words" into buffer
4005c4: 41 be 1e 00 00 00             mov     r14d, 0x1e              ; y = 30 for right header
4005ca: e8 36 ff ff ff                call    0x400505                 ; draw "Words" header
; --- Sub-block: for each in-memory row, draw first word then branch to Del strip ---
; Requirement: list reflects NOTE_COUNT in sort order; one ImageText8 per row
;   at x=360, then Del at x=544 on the same row — mirrors click hit-test split.
4005cf: 31 ed                         xor     ebp, ebp                ; row index = 0
4005d1: 41 be 2e 00 00 00             mov     r14d, 0x2e              ; first list row y = 46
4005d7: 3b 2c 25 00 48 40 00          cmp     ebp, [0x404800]        ; vs NOTE_COUNT
4005de: 7d 3b                         jge     0x40061b               ; all real rows drawn
4005e0: e8 10 ff ff ff                call    0x4004f5                 ; clear for list row
4005e5: 66 c7 04 25 e0 07 40 00 68 01   mov  WORD [0x4007e0], 0x168
        ; list text at x = 360
4005ef: bf e4 07 40 00                mov     edi, 0x4007e4         ; IT8 buffer again
4005f4: 89 e8                         mov     eax, ebp
4005f6: c1 e0 06                      shl     eax, 6                 ; row * 64
4005f9: 05 00 43 40 00                add     eax, 0x404300         ; -> slot[ebp] (sorted order)
4005fe: 89 c6                         mov     esi, eax               ; scan slot for first word
400600: b9 40 00 00 00                mov     ecx, 0x40
400605: ac                            lodsb                          ; first-word list rule:
400606: 3c 20                         cmp     al, 0x20               ;   stop at first ASCII space
400608: 74 03                         je      0x40060d               ;   (if no space, full slot)
40060a: aa                            stosb
40060b: e2 f8                         loop    0x400605
40060d: e9 39 00 00 00                jmp     0x40064b                ; draw row + "Del" + loop
        ; 0x400612..0x40061a: nop padding
; --- When NOTE_COUNT < 20 visible rows, tail helper clears the rest of the list column ---
40061b: e9 aa 00 00 00                jmp     0x4006ca                ; blank stale rows (after deletes)
```

**Disassembly — `Del` column and loop back (`0x40064b`–`0x40067d`):**

```text
; === Del affordance + row advance (0x40064b) — product: delete vs load by x coordinate ===
; Requirement: user can delete a row by clicking a dedicated control without
;   mistaking a load click (contract: list selection loads full text). A second
;   string at a larger x (0x220 vs 0x168) gives a machine-checkable column split
;   that matches the hit-test in 0x400460..0x400468. Same 16px vertical pitch
;   as the first-word line so “which row” stays aligned.
40064b: e8 b5 fe ff ff                call    0x400505                 ; emit list line (first word)
400650: e8 a0 fe ff ff                call    0x4004f5                 ; clear for "Del" text
400655: 66 c7 04 25 e0 07 40 00 20 02   mov  WORD [0x4007e0], 0x220
        ; x = 0x220 = 544, far right ("Del" column) — right of first-word text
40065f: be 78 08 40 00                mov     esi, 0x400878          ; "Del"
400664: bf e4 07 40 00                mov     edi, 0x4007e4
400669: b9 03 00 00 00                mov     ecx, 3
40066e: fc                            cld
40066f: f3 a4                         rep movsb                      ; copy into IT8 buffer
400671: e8 8f fe ff ff                call    0x400505                 ; draw "Del" for this row
400676: 66 41 83 c6 10                add     r14w, 0x10             ; next row y += 16
40067b: ff c5                         inc     ebp
40067d: e9 55 ff ff ff                jmp     0x4005d7                ; next note row
```

The new draw code (same behavior, stepwise):

1. clears the fixed-width `ImageText8` payload buffer
2. patches the X position field in the text template
3. draws `"Note:"` at the left pane
4. draws the current editor buffer beneath it
5. draws `"Words"` at the right pane
6. loops over the sorted slot array and copies only the first word of each note
   into the right-pane text buffer
7. sends one `ImageText8` request per visible row
8. draws a small `Del` affordance to the right of each visible row
9. blanks any now-unused lower right-pane rows left behind after deletions
10. jumps back to the existing event loop

Important absolute stores in this routine patch the `x` field at
`0x4007e0` before calling the existing `send_it8` helper.

The key immediate X coordinates are:

- `0x0010` (`16`) for the left editor pane
- `0x0168` (`360`) for the right list pane
- `0x0220` (`544`) for the per-row delete affordance

The copied Y coordinates are:

- `30` for pane headers
- `46` for the editor text line and the first list row
- then `+16` per subsequent list row

After the visible rows are drawn, a small tail helper now emits blank
right-pane rows from the current `NOTE_COUNT` up to the 20-row visual limit.
That prevents deleted rows from leaving stale text on screen that no longer
corresponds to any live note slot.

### Event dispatcher

The new dispatcher reads:

```text
EVENT_BUF[0] & 0x7f
```

and branches as follows:

- `Expose (12)` -> jump to existing `redraw`
- `KeyPress (2)` -> jump to the existing key handler
- `ButtonPress (4)` -> jump to the new click handler
- anything else -> jump back to the event loop

This is the only behavioral difference in event dispatch. The old binary simply
ignored button presses.

**Opcode sequence (`0x400620`–`0x400646`):** load a byte from `0x404000` (the
start of the 32-byte X event in the static buffer) and clear the high bit with
`and al,0x7f` so the server’s synthetic bit does not change the type enum.
Compare the event code to `12`, `2`, and `4`, jumping to the older `redraw` or
key path on match. For `4` (button press), a short near `je` chain falls
through to a `jmp` to `0x40041c` (the click handler). For anything else, jump
back to the top of the receive loop (address `0x4004b4` in the disassembly) so
unknown events are ignored.

**Disassembly (`0x400620`–`0x40064a`):**

```text
; === Event type dispatch (0x400620) — product: mouse + existing keyboard/refresh ===
; Requirement: window must request ButtonPress; once recvfrom returns, we must
;   route the same 32-byte XEvent the server sent: high bit cleared (else code
;   4 might read as 132). Without this, product could not satisfy “click list to
;   load” or “click Del to delete”. Unknown types are cheaply dropped by jumping
;   back to recvfrom (no accidental redraw on unrelated events).
400620: 8a 04 25 00 40 40 00          mov     al, [0x404000]         ; XEvent[0] = type
400627: 24 7f                         and     al, 0x7f                ; clear send_event bit
400629: 3c 0c                         cmp     al, 0x0c              ; Expose?
40062b: 0f 84 c8 fc ff ff             je      0x4002f9                ; -> redraw
400631: 3c 02                         cmp     al, 0x02              ; KeyPress?
400633: 0f 84 a5 fb ff ff             je      0x4001de                ; -> key handler
400639: 3c 04                         cmp     al, 0x04              ; ButtonPress?
40063b: 0f 84 05 00 00 00             je      0x400646                ; forward to click path
400641: e9 6e fe ff ff                jmp     0x4004b4                ; ignore: back to recvfrom
400646: e9 d1 fd ff ff                jmp     0x40041c                ; 0x40041c: click handler
```

### Click handler

The new click handler reads:

- `event_x` from `EVENT_BUF + 24` (`0x404018`)
- `event_y` from `EVENT_BUF + 26` (`0x40401a`)

**Instruction-level summary (`0x40041c`–`0x40046c`):** `movzx` loads 16-bit
`event_x` and `event_y` from fixed absolute addresses, keeping `event_x` in
`esi` for later tests. Clicks in the left pane or above the first row band
return early to the main loop (`jmp` to the receive block). Clicks in the
right-hand column walk row indices with `ebp`, starting with `mov eax,0x1e`
(30) as the Y coordinate of the first row’s band, then add `0x10` (16) per
index until the current `y` (`edx`) is inside `[eax, eax+0x10)`. That is the
“which row from the list” chooser. When a row is found, the code compares
`event_x` to `0x220` (544). If the click is left of 544, it jumps to the load
path at `0x400686`. If the click is at/after 544, it falls into the delete path.

**Load path (`0x400686`–`0x4006c3`):** store the chosen `ebp` into
`0x404804`, compute the slot pointer `0x404300+ebp*64` with `shl`/`add`, `rep
movs` 64 bytes into the editor at `0x404100`, then back-scan from `0x40413f`
to trim padding spaces and write `INPUT_LEN` at `0x404180`. Finally, jump to the
`poc-04` `redraw` / reload entry so the on-screen list matches the memory model.

**Delete path (`0x400472`–`0x4004a1` then jump to `0x400893`):** with `ebp` the
row index chosen above, the delete path compacts 64-byte slots: for `k` from
`ebp+1` through `NOTE_COUNT-1`, copy slot `k` over slot `k-1` using
overlapping `rep movs` (destination one slot below source). `NOTE_COUNT` is
decremented when finished. A near `jmp` at `0x4004a8` transfers to the disk helper
at `0x400893` (not to an immediate redraw), so deletes persist before the next
`redraw` reloads from `notes.db`.

Together, the summary above and the instruction-level paragraphs are the full
click story: narrow the event to the right pane, pick a row band, split `Del`
from load on `x`, either copy a slot into the editor or compact slots and
rewrite the database.

**Disassembly — hit test, `Del` vs load split, and slot compaction
(`0x40041c`–`0x4004a8`):**

```text
; === Click: hit test, load vs delete, in-memory compaction (0x40041c..0x4004a8) ===
; Product contract this block implements together with load/disk helpers:
;   (a) “Click list loads full note in editor” — need row index 0..NOTE_COUNT-1
;       from the same 16px bands as the draw loop (0x1e, 0x2e+16*row).
;   (b) “Del column deletes” — x>=0x220 (544) on that row triggers shift-down of
;       slots, not a load; compacted RAM must then match notes.db (handled next).
;   (c) Clicks on editor pane or off-list y return to receive loop: no spurious
;       load/delete (contract: selection only from the list region).
; --- Hit-test: right pane, vertical row band, horizontal load vs delete strip ---
40041c: 0f b7 04 25 18 40 40 00       movzx   eax, WORD [0x404018]  ; event_x
400424: 89 c6                         mov     esi, eax              ; ESI = x (Del vs load)
400426: 3d 68 01 00 00                cmp     eax, 0x168            ; list pane x >= 360
40042b: 72 40                         jb      0x40046d               ; left/editor: not a list op
40042d: 0f b7 14 25 1a 40 40 00       movzx   edx, WORD [0x40401a]  ; event_y
400435: 83 fa 1e                      cmp     edx, 0x1e              ; list starts at y=30
400438: 72 33                         jb      0x40046d               ; header/empty: ignore
40043a: 8b 0c 25 00 48 40 00          mov     ecx, [0x404800]       ; NOTE_COUNT
400441: 31 ed                         xor     ebp, ebp               ; row = 0,1,…
400443: b8 1e 00 00 00                mov     eax, 0x1e              ; top y of this band
400448: 39 cd                         cmp     ebp, ecx
40044a: 7d 21                         jge     0x40046d               ; y below last row: miss
40044c: 39 c2                         cmp     edx, eax
40044e: 72 1d                         jb      0x40046d               ; y above this band: miss
400450: 89 c7                         mov     edi, eax
400452: 83 c7 10                      add     edi, 0x10              ; [EAX, EAX+16) = row height
400455: 39 fa                         cmp     edx, edi
400457: 72 07                         jb      0x400460               ; hit: EBP = row
400459: 83 c0 10                      add     eax, 0x10
40045c: ff c5                         inc     ebp
40045e: eb e8                         jmp     0x400448
400460: 81 fe 20 02 00 00             cmp     esi, 0x220            ; x >= 544 → delete affordance
400466: 73 0a                         jae     0x400472               ; delete path: compact
400468: e9 19 02 00 00                jmp     0x400686                ; load: copy slot to editor
40046d: e9 42 00 00 00                jmp     0x4004b4                ; not actionable
; --- Delete path: shift slots down from row+1, drop last — RAM matches future file ---
; After loop: slot[ebp+1..] move down; NOTE_COUNT-- removes the deleted index so
;   in-memory order stays the single source of truth before 0x400893 rewrites
;   notes.db with the same surviving records (fixed 64B records).
400472: 8b 14 25 00 48 40 00          mov     edx, [0x404800]       ; NOTE_COUNT
400479: 8d 52 ff                      lea     edx, [rdx-0x1]         ; last index
40047c: 39 d5                         cmp     ebp, edx
40047e: 7d 21                         jge     0x4004a1               ; EBP is last: no copy loop
400480: 89 e8                         mov     eax, ebp
400482: ff c0                         inc     eax                    ; k = EBP+1
400484: c1 e0 06                      shl     eax, 6
400487: 05 00 43 40 00                add     eax, 0x404300         ; &slot[k] (source)
40048c: 89 c6                         mov     esi, eax
40048e: 89 c7                         mov     edi, eax
400490: 83 ef 40                      sub     edi, 0x40              ; &slot[k-1] (dest, overlap OK)
400493: b9 40 00 00 00                mov     ecx, 0x40
400498: fc                            cld
400499: f3 a4                         rep movsb                      ; 64B block move
40049b: ff c5                         inc     ebp
40049d: 39 d5                         cmp     ebp, edx
40049f: 7c df                         jl      0x400480
4004a1: ff 0c 25 00 48 40 00          dec     DWORD [0x404800]       ; one fewer note
4004a8: e9 e6 03 00 00                jmp     0x400893                ; persist: truncate+write db
```

The five-byte `jmp` at `0x4004a8` is unconditional, so the image bytes that follow
it in the file are not part of this control-flow sequence until some other
entry point branches there.

**Disassembly — load path (`0x400686`–`0x4006c3`):**

```text
; === Load path (0x400686) — contract: “selecting a note loads full text in editor” ===
; Implementation detail: 64B slot is copied wholesale to 0x404100, then we walk
;   backward from 0x40413f to set INPUT_LEN to the last non-space (poc-04 editor
;   model). 0x404804 holds row for UI consistency; 0x4002f9 reload path redraws
;   the two-pane list so the screen matches the in-memory model after load.
400686: 89 2c 25 04 48 40 00          mov     [0x404804], ebp         ; selected row (for product state)
40068d: 89 e8                         mov     eax, ebp
40068f: c1 e0 06                      shl     eax, 6
400692: 05 00 43 40 00                add     eax, 0x404300
400697: 89 c6                         mov     esi, eax               ; &slot[row] in sorted order
400699: bf 00 41 40 00                mov     edi, 0x404100         ; editor (note pane)
40069e: b9 40 00 00 00                mov     ecx, 0x40
4006a3: fc                            cld
4006a4: f3 a4                         rep movsb                      ; full 64B note into editor
4006a6: be 3f 41 40 00                mov     esi, 0x40413f         ; end of buffer for trim
4006ab: b9 40 00 00 00                mov     ecx, 0x40
4006b0: 8a 06                         mov     al, [rsi]              ; trim trailing spaces → len
4006b2: 3c 20                         cmp     al, 0x20
4006b4: 75 06                         jne     0x4006bc
4006b6: ff ce                         dec     esi
4006b8: ff c9                         dec     ecx
4006ba: 75 f4                         jne     0x4006b0
4006bc: 89 0c 25 80 41 40 00          mov     [0x404180], ecx         ; INPUT_LEN (editable char count)
4006c3: e9 31 fc ff ff                jmp     0x4002f9                ; redraw: list+editor in sync
```

### Tail clear helper (after the draw list, `0x4006ca` upward)

**Execution logic:** this helper runs when the draw loop has painted `NOTE_COUNT`
rows but the screen can still show up to 20 rows. It `cmp`s `ebp` to `0x14`
(20) and, while below, `call`s `fill_it8` and `send_it8` to paint another blank
right-pane line at the same `x` and advancing `r14` by 16, incrementing a row
counter in `ebp`. When `ebp` reaches 20, it jumps back to the main X11 receive
loop. The net effect is to erase any stale rows that would otherwise remain
visible after deletes.

**Disassembly (`0x4006ca`–`0x4006f0`):**

```text
; === Tail clear (0x4006ca) — requirement: UI shows up to 20 list rows; deletes leave gaps ===
; After a delete, NOTE_COUNT may shrink but pixels from old rows  N..19  would
;   still show stale glyphs until replaced. This loop repaints (NOTE_COUNT..19)
;   with blank 64B IT8 at list x so the on-screen list height always matches
;   the “up to 20 visible rows” product cap without requiring a full window clear.
; EBP was advanced during draw; here we only finish drawing empty rows to y limit.
4006ca: 83 fd 14                      cmp     ebp, 0x14              ; drawn rows vs 20
4006cd: 7d 1d                         jge     0x4006ec
4006cf: e8 21 fe ff ff                call    0x4004f5                 ; spaces in IT8 buffer
4006d4: 66 c7 04 25 e0 07 40 00 68 01   mov  WORD [0x4007e0], 0x168
        ; x = list column: blank line erases old first-word + Del for this row
4006de: e8 22 fe ff ff                call    0x400505
4006e3: 66 41 83 c6 10                add     r14w, 0x10             ; same 16px vertical pitch
4006e8: ff c5                         inc     ebp
4006ea: eb de                         jmp     0x4006ca
4006ec: e9 c3 fd ff ff                jmp     0x4004b4                ; done: wait for next X event
        ; 0x4006f1..0x4006ff: in-image padding or non-entry bytes after the jmp
```

### Persistent delete helper

The extra helper stored at `0x893..0x90d` is reached from the delete path after
the in-memory row compaction is complete.

Its logic is:

1. `open("notes.db", O_WRONLY | O_CREAT | O_TRUNC, 0644)`
2. store constant length `64` into the scratch word at `0x404184`
3. loop over the current in-memory slot array from row `0` to `NOTE_COUNT - 1`
4. `write(fd, &scratch_len, 4)`
5. `write(fd, slot, 64)`
6. `close(fd)`
7. jump back to the old reload path so the live view is rebuilt from disk

**Instruction-level form (`0x400893`–`0x400909` as assembled today):** load
`__NR_open=2` with `esi = (O_WRONLY|O_CREAT|O_TRUNC)` and `mode_t 0644` in
`edx`, then `syscall`. On failure, jump to a fallback that re-enters the draw
code without rewriting disk (so the UI can still paint). On success, keep `r13`
as the file descriptor, write the constant `64` to `0x404184` (the 4-byte
length prefix for each record in this rewrite), then for each `ebp` in
`0..NOTE_COUNT-1` issue `write(r13, 0x404184, 4)` followed by
`write(r13, slot, 0x40)` with `slot` at `0x404300+ebp*64`. Close with
`__NR_close=3` on `r13`, and finally a near `jmp` to the old `redraw` entry at
`0x4002f9` so the regular loader path rebuilds the in-memory sort from the new
file content.

This helper is intentionally compact, so it serializes each surviving note as a
fixed-width 64-byte payload. That is larger than the minimal append path used by
`Enter`, but still compatible with the loader.

**Disassembly (`0x400893`–`0x40090d`):**

```text
; === Persistent delete helper (0x400893) — contract: port shared [len][text] file format ===
; After RAM compaction, disk must list exactly the same surviving notes. This
;   helper truncates notes.db and rewrites each in-memory slot as [4B len=64][64B
;   payload] — a fixed width chosen for implementation simplicity; loader already
;   accepts length-prefixed records. O_TRUNC makes rewrite atomic from the file’s
;   point of view (single writer pass). If open fails, we still draw so the UI
;   works read-only; user sees compacted RAM but db unchanged until fixed.
;   Success path: close then 0x4002f9 re-reads file so sort order and screen match.
400893: b8 02 00 00 00                mov     eax, 0x2              ; __NR_open
400898: bf c8 07 40 00                mov     edi, 0x4007c8         ; path: "notes.db"
40089d: be 41 02 00 00                mov     esi, 0x241             ; O_WRONLY|O_CREAT|O_TRUNC
4008a2: ba a4 01 00 00                mov     edx, 0x1a4            ; 0644
4008a7: 0f 05                         syscall
4008a9: 48 85 c0                      test    rax, rax
4008ac: 78 5b                         js      0x400909                ; can’t persist — draw only
4008ae: 49 89 c5                      mov     r13, rax               ; fd for write loop
4008b1: c7 04 25 84 41 40 00 40 00 00 00   mov  [0x404184], 0x40
        ; record length 64 (little-endian) reused before each body write
4008bc: 31 ed                         xor     ebp, ebp                ; index 0..NOTE_COUNT-1
4008be: 3b 2c 25 00 48 40 00          cmp     ebp, [0x404800]
4008c5: 7d 33                         jge     0x4008fa
4008c7: b8 01 00 00 00                mov     eax, 0x1              ; __NR_write
4008cc: 4c 89 ef                      mov     rdi, r13
4008cf: be 84 41 40 00                mov     esi, 0x404184         ; &scratch len
4008d4: ba 04 00 00 00                mov     edx, 0x4
4008d9: 0f 05                         syscall                        ; [len] in file stream
4008db: 89 e8                         mov     eax, ebp
4008dd: c1 e0 06                      shl     eax, 6
4008e0: 05 00 43 40 00                add     eax, 0x404300
4008e5: 89 c6                         mov     esi, eax               ; 64B slot (sorted order)
4008e7: b8 01 00 00 00                mov     eax, 0x1
4008ec: 4c 89 ef                      mov     rdi, r13
4008ef: ba 40 00 00 00                mov     edx, 0x40
4008f4: 0f 05                         syscall                        ; [text] — fixed width
4008f6: ff c5                         inc     ebp
4008f8: eb c4                         jmp     0x4008be
4008fa: b8 03 00 00 00                mov     eax, 0x3              ; __NR_close
4008ff: 4c 89 ef                      mov     rdi, r13
400902: 0f 05                         syscall
400904: e9 f0 f9 ff ff                jmp     0x4002f9                ; load/sort from new file, redraw
400909: e9 3b fc ff ff                jmp     0x400549                ; no disk update — refresh UI
```

## Runtime memory usage

The unchanged BSS layout from `poc-04/note-edit` still applies, with one extra
product-specific slot now used:

- `0x404804` — selected row index, initialised to `-1`

## Known limitations

This first product reference binary is intentionally still constrained:

- same hard-coded X11 session coupling as `poc-04`
- keyboard input is still tied to one X11 keycode layout, but now covers normal
  printable ASCII and shifted uppercase/symbols for that layout
- same 63-character editor limit
- same 20-note in-memory display cap
- `Enter` still appends new records rather than rewriting the file
- right pane shows only the first word, but sorting still follows the full
  stored note bytes
- delete rewrites surviving notes as 64-byte fixed-width payload records rather
  than minimal-length records
- the two panes are logical drawing regions, not toolkit-managed widgets

Those limitations are acceptable for the Linux x86_64 product reference build
because the goal here is to establish the cross-platform behavior contract in a
real native GUI binary.
