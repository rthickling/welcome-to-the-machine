# `poc-04/note-edit` — interactive X11 note editor

`note-edit` is a **2346-byte** statically-linked ELF64 binary that opens a
real X11 window titled `"note-edit"`, accepts keyboard input directly via raw
X11 `KeyPress` events, appends the entered text to `notes.db` on Enter, and
re-renders the whole note list in **sorted order** on every redraw.

It stays within the repo rules:

- binary only
- no `libc`
- no Xlib / libxcb linkage
- direct Linux syscalls
- raw X11 wire protocol
- matching binary test and Markdown companion

**Terminology:** names like [`ImageText8`](../../products/notes/glossary.md#imagetext8),
[raw X11](../../products/notes/glossary.md#raw-x11), [BSS](../../products/notes/glossary.md#bss),
[mkelf](../../products/notes/glossary.md#mkelf), and **syscall** numbers are defined in
the [product notes glossary](../../products/notes/glossary.md). A **PoC-04 table of
Contents / pointers** is in [`glossary.md`](glossary.md) in this directory.

Like `poc-03/note` and `poc-04/note-view`, the on-disk database is still the
same append-only format:

```text
[4-byte little-endian length][length bytes of text]
```

For records created by `note-edit`, `length = typed_bytes + 1` because the
binary appends a trailing `'\n'` byte before storing.

## Usage

```bash
cd experiments/poc-04-notes-x11
./note-edit
```

Inside the window:

- type lowercase letters, digits, space, `-`, `,`, `.`, `'`, `/`
- `Backspace` deletes one character
- `Enter` appends the current line to `notes.db`
- `Escape` exits

The next launch re-reads `notes.db`, sorts the notes in memory, and draws the
sorted list again.

## Session coupling

Exactly like `note-view`, this binary hard-codes:

- the X socket path `/tmp/.X11-unix/X1`
- the current `MIT-MAGIC-COOKIE-1`
- the current root window id `0x3fd`

So it must be rebuilt whenever the X session changes.

## File / memory layout

`mkelf` prepends the usual 120-byte ELF header + PT_LOAD header. Because the
single `PT_LOAD` maps file offset `0` at virtual address `0x400000`, the file
offset of any byte is simply `vaddr − 0x400000` (entry `0x400078` is file byte
`0x78`).

The body is intentionally split into a **fixed-size code region** and a
**fixed-address data region**:

```text
file offset    vaddr       size    content
------------   ---------   -----   -----------------------------------------
0x000..0x077   0x400000     120    ELF64 header + one PT_LOAD program header
0x078..0x537   0x400078    1216    executable code (entry → exit_app)
0x538..0x6ff   0x400538     456    zero padding
0x700..0x929   0x400700     554    data templates / strings / keymap
```

That fixed `0x400700` data base is deliberate:

1. It makes the code easier to hand-address.
2. It gives `test-note-edit` a stable file offset for the WM title string.

`mkelf` also provides 64 KiB of zero-filled writable memory beyond EOF. The
binary uses that BSS area for all runtime state.

### ELF header and load segment (`0x000..0x077`)

The first 120 bytes are the container `mkelf` writes: a 64-byte ELF64 header
and one 56-byte program header. Every field a reader needs to single-step from
the entry point is decoded here.

```text
; --- ELF64 header (0x000..0x03f) ---
000: 7f 45 4c 46   e_ident magic "\x7fELF"
004: 02            EI_CLASS   = 2  (ELFCLASS64)
005: 01            EI_DATA    = 1  (little-endian)
006: 01            EI_VERSION = 1
007: 00 ...        EI_OSABI = 0 (System V) + 8 padding bytes
010: 02 00         e_type    = 2      (ET_EXEC)
012: 3e 00         e_machine = 0x3e   (AMD x86-64)
014: 01 00 00 00   e_version = 1
018: 78 00 40 00 00 00 00 00   e_entry = 0x400078  (first instruction)
020: 40 00 00 00 00 00 00 00   e_phoff = 0x40      (program header at file 0x40)
028: 00 00 00 00 00 00 00 00   e_shoff = 0        (no section headers)
030: 00 00 00 00   e_flags     = 0
034: 40 00         e_ehsize    = 64
036: 38 00         e_phentsize = 56
038: 01 00         e_phnum     = 1
03a: 00 00 / 00 00 / 00 00   e_shentsize / e_shnum / e_shstrndx = 0
; --- Program header (0x040..0x077): one PT_LOAD ---
040: 01 00 00 00   p_type   = 1        (PT_LOAD)
044: 07 00 00 00   p_flags  = 7        (Read | Write | Execute)
048: 00 00 00 00 00 00 00 00   p_offset = 0
050: 00 00 40 00 00 00 00 00   p_vaddr  = 0x400000
058: 00 00 40 00 00 00 00 00   p_paddr  = 0x400000
060: 2a 09 00 00 00 00 00 00   p_filesz = 0x092a   (2346 bytes on disk)
068: 2a 09 01 00 00 00 00 00   p_memsz  = 0x1092a  (file + 0x10000 zeroed BSS)
070: 00 10 00 00 00 00 00 00   p_align  = 0x1000
```

The segment is `RWE`, so the same mapping holds executable code, the writable
data templates that get patched at runtime, and — because `p_memsz` exceeds
`p_filesz` by exactly `0x10000` — a trailing 64 KiB of demand-zero memory that
serves as the BSS tabulated below.

### BSS map

| Address     | Size | Purpose |
| ----------- | ---- | ------- |
| `0x401000`  | 16K  | X11 setup reply buffer |
| `0x404000`  | 32   | current X event |
| `0x404100`  | 128  | input buffer (only first 63 bytes used) |
| `0x404180`  | 4    | current input length |
| `0x404184`  | 4    | scratch word for record length / write length |
| `0x404188`  | 64   | one raw record body from disk |
| `0x4041d0`  | 64   | temporary sortable note slot |
| `0x404300`  | 1280 | 20 fixed 64-byte note slots (`20 * 64`) |
| `0x404800`  | 4    | current loaded note count |

## Data section at `0x400700`

| Vaddr        | Size | Purpose |
| ------------ | ---- | ------- |
| `0x400700`   | 20   | `sockaddr_un` for `/tmp/.X11-unix/X1` |
| `0x400714`   | 48   | X11 setup request with hard-coded cookie |
| `0x400744`   | 40   | `CreateWindow` template |
| `0x40076c`   | 36   | `ChangeProperty(WM_NAME="note-edit")` template |
| `0x400790`   | 20   | `OpenFont("fixed")` template |
| `0x4007a4`   | 28   | `CreateGC` template |
| `0x4007c0`   | 8    | `MapWindow` template |
| `0x4007c8`   | 12   | `"notes.db\0"` |
| `0x4007d4`   | 16   | `ImageText8` header template |
| `0x4007e4`   | 64   | `ImageText8` string payload buffer |
| `0x400824`   | 5    | `"New: "` |
| `0x400829`   | 1    | newline byte (`0x0a`) |
| `0x40082a`   | 256  | keycode-to-byte lookup table |

### The fixed-width `ImageText8` trick

Unlike `note-view`, which computed a variable request length for each record,
`note-edit` uses a constant-size text request:

- string length = 64
- request length = 20 4-byte units
- total request bytes = 80

Each line is always padded with spaces out to 64 bytes before drawing. That
means every redraw automatically erases old shorter text without requiring a
separate `ClearArea` request.

## Register conventions

| Register | Meaning |
| -------- | ------- |
| `rbx`    | X11 socket fd for the life of the process |
| `r12d`   | X11 resource-id-base from the setup reply |
| `r14w`   | current Y coordinate while drawing |
| `r15`    | `notes.db` file descriptor during load/save |

Everything else is scratch.

## Key handling model

The event loop reads 32-byte X11 events into `0x404000`.

For `KeyPress` (`event type 2`), byte 1 is the X keycode. `note-edit` does
not ask the server to translate it. Instead it indexes the 256-byte lookup
table at `0x40082a`:

- unmapped keycode -> `0`
- printable supported key -> ASCII byte
- Backspace -> `0x08`
- Enter / keypad Enter -> `0x0a`
- Escape -> `0x1b`

Supported printable keys in the current hard-coded map:

- `a`..`z`
- `0`..`9`
- `space`
- `-`
- `,`
- `.`
- `'`
- `/`

The map matches the current X layout on the author's machine and is therefore
session/layout-coupled just like the cookie.

## Code walkthrough

### Section A — connect to X and fetch setup reply (`0x078..0x1d8`)

Execution starts at `0x400078`. This block creates the Unix socket, connects to
the X server, performs the setup handshake, reads the resource-id base out of
the reply, patches that id into every request template, and sends the five
window-bring-up requests.

```text
; --- socket(AF_UNIX, SOCK_STREAM, 0) ---
400078: b8 29 00 00 00        mov  eax, 0x29           ; __NR_socket (41)
40007d: bf 01 00 00 00        mov  edi, 0x1            ; AF_UNIX
400082: be 01 00 00 00        mov  esi, 0x1            ; SOCK_STREAM
400087: 31 d2                 xor  edx, edx            ; protocol 0
400089: 0f 05                 syscall
40008b: 48 89 c3              mov  rbx, rax            ; rbx = X socket fd (held for the whole run)
; --- connect(rbx, "/tmp/.X11-unix/X1", 20) ---
40008e: b8 2a 00 00 00        mov  eax, 0x2a           ; __NR_connect (42)
400093: 48 89 df              mov  rdi, rbx
400096: be 00 07 40 00        mov  esi, 0x400700       ; sockaddr_un
40009b: ba 14 00 00 00        mov  edx, 0x14           ; addrlen 20
4000a0: 0f 05                 syscall
; --- sendto the 48-byte setup request (carries the MIT magic cookie) ---
4000a2: 45 31 d2              xor  r10d, r10d          ; flags 0
4000a5: 45 31 c0              xor  r8d, r8d            ; dest addr NULL
4000a8: 45 31 c9              xor  r9d, r9d            ; addrlen 0
4000ab: b8 2c 00 00 00        mov  eax, 0x2c           ; __NR_sendto (44)
4000b0: 48 89 df              mov  rdi, rbx
4000b3: be 14 07 40 00        mov  esi, 0x400714       ; setup request template
4000b8: ba 30 00 00 00        mov  edx, 0x30           ; 48 bytes
4000bd: 0f 05                 syscall
; --- recvfrom the 8-byte setup header, then the remainder ---
4000bf: 41 ba 00 01 00 00     mov  r10d, 0x100         ; MSG_WAITALL
4000c5: b8 2d 00 00 00        mov  eax, 0x2d           ; __NR_recvfrom (45)
4000ca: 48 89 df              mov  rdi, rbx
4000cd: be 00 10 40 00        mov  esi, 0x401000       ; setup-reply buffer
4000d2: ba 08 00 00 00        mov  edx, 0x8            ; first 8 bytes
4000d7: 0f 05                 syscall
4000d9: 0f b7 04 25 06 10 40 00  movzx eax, WORD [0x401006] ; additional-data length (4-byte units)
4000e1: c1 e0 02              shl  eax, 0x2            ; × 4 = remaining byte count
4000e4: 89 c2                 mov  edx, eax
4000e6: b8 2d 00 00 00        mov  eax, 0x2d           ; __NR_recvfrom
4000eb: 48 89 df              mov  rdi, rbx
4000ee: be 08 10 40 00        mov  esi, 0x401008       ; continue after the header
4000f3: 0f 05                 syscall
; --- capture resource-id base and patch every template that needs an id ---
4000f5: 44 8b 24 25 0c 10 40 00  mov r12d, DWORD [0x40100c]  ; resource-id-base
4000fd: 44 89 e0              mov  eax, r12d
400100: 83 c8 01              or   eax, 0x1            ; window id = base | 1
400103: 89 04 25 48 07 40 00  mov  DWORD [0x400748], eax    ; CreateWindow.wid
40010a: 45 31 d2              xor  r10d, r10d          ; sendto flags 0
40010d: b8 2c 00 00 00        mov  eax, 0x2c           ; __NR_sendto
400112: 48 89 df              mov  rdi, rbx
400115: be 44 07 40 00        mov  esi, 0x400744       ; CreateWindow
40011a: ba 28 00 00 00        mov  edx, 0x28           ; 40 bytes
40011f: 0f 05                 syscall
400121: 44 89 e0              mov  eax, r12d
400124: 83 c8 01              or   eax, 0x1            ; window id | 1
400127: 89 04 25 70 07 40 00  mov  DWORD [0x400770], eax    ; ChangeProperty.window
40012e: b8 2c 00 00 00        mov  eax, 0x2c
400133: 48 89 df              mov  rdi, rbx
400136: be 6c 07 40 00        mov  esi, 0x40076c       ; ChangeProperty(WM_NAME="note-edit")
40013b: ba 24 00 00 00        mov  edx, 0x24           ; 36 bytes
400140: 0f 05                 syscall
400142: 44 89 e0              mov  eax, r12d
400145: 83 c8 02              or   eax, 0x2            ; font id = base | 2
400148: 89 04 25 94 07 40 00  mov  DWORD [0x400794], eax    ; OpenFont.fid
40014f: b8 2c 00 00 00        mov  eax, 0x2c
400154: 48 89 df              mov  rdi, rbx
400157: be 90 07 40 00        mov  esi, 0x400790       ; OpenFont("fixed")
40015c: ba 14 00 00 00        mov  edx, 0x14           ; 20 bytes
400161: 0f 05                 syscall
400163: 44 89 e0              mov  eax, r12d
400166: 83 c8 03              or   eax, 0x3            ; gc id = base | 3
400169: 89 04 25 a8 07 40 00  mov  DWORD [0x4007a8], eax    ; CreateGC.gc
400170: 44 89 e0              mov  eax, r12d
400173: 83 c8 01              or   eax, 0x1            ; window id | 1
400176: 89 04 25 ac 07 40 00  mov  DWORD [0x4007ac], eax    ; CreateGC.drawable (the window)
40017d: 44 89 e0              mov  eax, r12d
400180: 83 c8 02              or   eax, 0x2            ; font id | 2
400183: 89 04 25 bc 07 40 00  mov  DWORD [0x4007bc], eax    ; CreateGC.font value
40018a: b8 2c 00 00 00        mov  eax, 0x2c
40018f: 48 89 df              mov  rdi, rbx
400192: be a4 07 40 00        mov  esi, 0x4007a4       ; CreateGC
400197: ba 1c 00 00 00        mov  edx, 0x1c           ; 28 bytes
40019c: 0f 05                 syscall
40019e: 44 89 e0              mov  eax, r12d
4001a1: 83 c8 01              or   eax, 0x1            ; window id | 1
4001a4: 89 04 25 c4 07 40 00  mov  DWORD [0x4007c4], eax    ; MapWindow.window
4001ab: b8 2c 00 00 00        mov  eax, 0x2c
4001b0: 48 89 df              mov  rdi, rbx
4001b3: be c0 07 40 00        mov  esi, 0x4007c0       ; MapWindow
4001b8: ba 08 00 00 00        mov  edx, 0x8            ; 8 bytes
4001bd: 0f 05                 syscall
; --- pre-patch the ImageText8 request so every later draw can reuse it ---
4001bf: 44 89 e0              mov  eax, r12d
4001c2: 83 c8 01              or   eax, 0x1            ; window id | 1
4001c5: 89 04 25 d8 07 40 00  mov  DWORD [0x4007d8], eax    ; ImageText8.drawable
4001cc: 44 89 e0              mov  eax, r12d
4001cf: 83 c8 03              or   eax, 0x3            ; gc id | 3
4001d2: 89 04 25 dc 07 40 00  mov  DWORD [0x4007dc], eax    ; ImageText8.gc
; --- jump straight into redraw so the prompt appears before the first Expose ---
4001d9: e9 1b 01 00 00        jmp  0x4002f9           ; redraw entry (Section E)
```

The resource ids all come from one `r12d` base: window = `base | 1`,
font = `base | 2`, gc = `base | 3`. That is why each template is patched with an
`or eax, 1/2/3` before the `mov`. After `MapWindow`, the final jump enters
`redraw` (Section E) directly, so the sorted list is painted immediately without
waiting for the server's first `Expose`.

> The product build `notes-linux-x86_64` reuses this exact block, except the
> `0x4001d9` jump is repointed to a startup stub (which zeroes the selected-row
> slot) and the `WM_NAME` string / event-mask bytes in the templates differ.

### Section B — key handler (`0x1de..0x233`)

Reached from the event loop for a `KeyPress`. It reads the keycode, translates
it through the 256-byte table at `0x40082a`, and dispatches. The default case
(any printable byte) is the append tail at `0x20d`, which enforces the
63-character cap.

```text
; --- translate keycode → ASCII, then branch on the special bytes ---
4001de: 0f b6 04 25 01 40 40 00  movzx eax, BYTE [0x404001]  ; EVENT_BUF+1 = X keycode
4001e6: 0f b6 80 2a 08 40 00  movzx eax, BYTE [rax+0x40082a] ; table lookup → ASCII
4001ed: 84 c0                 test al, al
4001ef: 0f 84 bf 02 00 00     je   0x4004b4          ; 0 = unmapped → ignore, back to recv loop
4001f5: 3c 1b                 cmp  al, 0x1b
4001f7: 0f 84 29 03 00 00     je   0x400526          ; Escape → exit_app
4001fd: 3c 08                 cmp  al, 0x8
4001ff: 0f 84 2f 00 00 00     je   0x400234          ; Backspace (Section C)
400205: 3c 0a                 cmp  al, 0xa
400207: 0f 84 44 00 00 00     je   0x400251          ; Enter → save (Section D)
; --- default: append the printable byte to INPUT_BUF ---
40020d: 8b 0c 25 80 41 40 00  mov  ecx, [0x404180]   ; INPUT_LEN
400214: 83 f9 3f              cmp  ecx, 0x3f          ; already 63 chars?
400217: 0f 83 97 02 00 00     jae  0x4004b4          ; full → ignore
40021d: bf 00 41 40 00        mov  edi, 0x404100      ; input buffer base
400222: 01 cf                 add  edi, ecx           ; &input[INPUT_LEN]
400224: 88 07                 mov  [rdi], al          ; store the byte
400226: ff c1                 inc  ecx
400228: 89 0c 25 80 41 40 00  mov  [0x404180], ecx   ; INPUT_LEN += 1
40022f: e9 c5 00 00 00        jmp  0x4002f9          ; redraw
```

The 63-character cap guarantees the saved record is at most 64 bytes including
the trailing newline, which keeps every note within one fixed-width slot.

> In the product build this entry is repointed: the first instruction at
> `0x4001de` becomes `jmp 0x400963` into a Shift-aware handler, which still falls
> back into this same append tail at `0x40020d`.

### Section C — backspace (`0x234..0x250`)

```text
400234: 8b 0c 25 80 41 40 00  mov  ecx, [0x404180]   ; INPUT_LEN
40023b: 85 c9                 test ecx, ecx
40023d: 0f 84 71 02 00 00     je   0x4004b4          ; already empty → ignore
400243: ff c9                 dec  ecx                ; drop one character
400245: 89 0c 25 80 41 40 00  mov  [0x404180], ecx   ; store shortened length
40024c: e9 a8 00 00 00        jmp  0x4002f9          ; redraw
```

Only `INPUT_LEN` shrinks; the stale byte stays in `INPUT_BUF` but the
fixed-width redraw paints spaces over the whole input line, so the removed glyph
disappears.

### Section D — save current input (`0x251..0x2f8`)

`Enter` appends `[len+1][text][\n]` to the end of `notes.db`, keeping the
append-only format shared with `poc-03/note` and `poc-04/note-view`.

```text
400251: 8b 0c 25 80 41 40 00  mov  ecx, [0x404180]   ; INPUT_LEN
400258: 85 c9                 test ecx, ecx
40025a: 0f 84 99 00 00 00     je   0x4002f9          ; nothing typed → just redraw
400260: b8 02 00 00 00        mov  eax, 0x2          ; __NR_open (2)
400265: bf c8 07 40 00        mov  edi, 0x4007c8      ; "notes.db"
40026a: be 42 00 00 00        mov  esi, 0x42         ; O_RDWR | O_CREAT
40026f: ba a4 01 00 00        mov  edx, 0x1a4        ; mode 0644
400274: 0f 05                 syscall
400276: 48 85 c0              test rax, rax
400279: 0f 88 7a 00 00 00     js   0x4002f9          ; open failed → redraw anyway
40027f: 49 89 c7              mov  r15, rax           ; r15 = db fd
400282: b8 08 00 00 00        mov  eax, 0x8          ; __NR_lseek (8)
400287: 4c 89 ff              mov  rdi, r15
40028a: 31 f6                 xor  esi, esi           ; offset 0
40028c: ba 02 00 00 00        mov  edx, 0x2          ; SEEK_END (append point)
400291: 0f 05                 syscall
400293: 8b 04 25 80 41 40 00  mov  eax, [0x404180]   ; INPUT_LEN
40029a: ff c0                 inc  eax                ; +1 for the trailing newline
40029c: 89 04 25 84 41 40 00  mov  [0x404184], eax   ; scratch length prefix
4002a3: b8 01 00 00 00        mov  eax, 0x1          ; __NR_write (1)
4002a8: 4c 89 ff              mov  rdi, r15
4002ab: be 84 41 40 00        mov  esi, 0x404184      ; &length prefix
4002b0: ba 04 00 00 00        mov  edx, 0x4          ; 4 bytes
4002b5: 0f 05                 syscall                 ; write [len+1]
4002b7: b8 01 00 00 00        mov  eax, 0x1
4002bc: 4c 89 ff              mov  rdi, r15
4002bf: be 00 41 40 00        mov  esi, 0x404100      ; INPUT_BUF
4002c4: 8b 14 25 80 41 40 00  mov  edx, [0x404180]   ; INPUT_LEN bytes
4002cb: 0f 05                 syscall                 ; write [text]
4002cd: b8 01 00 00 00        mov  eax, 0x1
4002d2: 4c 89 ff              mov  rdi, r15
4002d5: be 29 08 40 00        mov  esi, 0x400829      ; newline byte 0x0a
4002da: ba 01 00 00 00        mov  edx, 0x1
4002df: 0f 05                 syscall                 ; write [\n]
4002e1: b8 03 00 00 00        mov  eax, 0x3          ; __NR_close (3)
4002e6: 4c 89 ff              mov  rdi, r15
4002e9: 0f 05                 syscall
4002eb: 31 c0                 xor  eax, eax
4002ed: 89 04 25 80 41 40 00  mov  [0x404180], eax   ; INPUT_LEN = 0 (clear editor)
4002f4: e9 00 00 00 00        jmp  0x4002f9          ; fall into redraw
```

The `length = typed_bytes + 1` accounts for the appended newline, so records
written here round-trip through the loader in Section E.

### Section E — load and sort notes — the `redraw` entry (`0x2f9..0x416`)

`0x4002f9` is the reload/redraw entry that every edit path jumps back to. It
zeroes `NOTE_COUNT`, opens `notes.db` read-only, and for each length-prefixed
record space-pads it into a 64-byte slot and insertion-sorts it into the array
at `0x404300`. When the file is exhausted it closes the fd and falls through
into the draw routine at `0x417` (Section F).

```text
; --- reset the count and open the database read-only ---
4002f9: 31 c0                 xor  eax, eax
4002fb: 89 04 25 00 48 40 00  mov  [0x404800], eax   ; NOTE_COUNT = 0
400302: b8 02 00 00 00        mov  eax, 0x2          ; __NR_open
400307: bf c8 07 40 00        mov  edi, 0x4007c8      ; "notes.db"
40030c: 31 f6                 xor  esi, esi           ; O_RDONLY
40030e: 31 d2                 xor  edx, edx           ; mode ignored
400310: 0f 05                 syscall
400312: 48 85 c0              test rax, rax
400315: 0f 88 fc 00 00 00     js   0x400417          ; no db yet → straight to draw
40031b: 49 89 c7              mov  r15, rax           ; r15 = db fd
; --- per-record loop: read the 4-byte length prefix ---
40031e: 31 c0                 xor  eax, eax           ; __NR_read (0)
400320: 4c 89 ff              mov  rdi, r15
400323: be 84 41 40 00        mov  esi, 0x404184      ; scratch length word
400328: ba 04 00 00 00        mov  edx, 0x4
40032d: 0f 05                 syscall
40032f: 48 83 f8 04           cmp  rax, 0x4           ; full prefix read?
400333: 0f 85 d4 00 00 00     jne  0x40040d          ; EOF / short read → done
400339: 8b 0c 25 84 41 40 00  mov  ecx, [0x404184]   ; record length
400340: 83 f9 00              cmp  ecx, 0x0
400343: 0f 8e c4 00 00 00     jle  0x40040d          ; length <= 0 → done
400349: 83 f9 40              cmp  ecx, 0x40
40034c: 0f 8f bb 00 00 00     jg   0x40040d          ; length > 64 → done (loader cap)
; --- read the record body into RECORD_BUF ---
400352: 89 ca                 mov  edx, ecx           ; read `len` bytes
400354: 31 c0                 xor  eax, eax
400356: 4c 89 ff              mov  rdi, r15
400359: be 88 41 40 00        mov  esi, 0x404188      ; RECORD_BUF
40035e: 0f 05                 syscall
400360: 48 85 c0              test rax, rax
400363: 0f 8e a4 00 00 00     jle  0x40040d          ; error/EOF → done
400369: 89 c1                 mov  ecx, eax           ; ecx = bytes read
40036b: 8a 81 87 41 40 00     mov  al, [rcx+0x404187] ; last byte of the record
400371: 3c 0a                 cmp  al, 0xa
400373: 0f 85 02 00 00 00     jne  0x40037b
400379: ff c9                 dec  ecx                ; strip one trailing newline
; --- build the 64-byte space-padded sortable slot (TEMPNOTE) ---
40037b: 89 ca                 mov  edx, ecx           ; edx = payload length
40037d: bf d0 41 40 00        mov  edi, 0x4041d0      ; TEMPNOTE
400382: b9 40 00 00 00        mov  ecx, 0x40          ; 64 bytes
400387: b0 20                 mov  al, 0x20           ; ASCII space
400389: fc                    cld
40038a: f3 aa                 rep stosb               ; blank the slot
40038c: 89 d1                 mov  ecx, edx
40038e: be 88 41 40 00        mov  esi, 0x404188      ; RECORD_BUF
400393: bf d0 41 40 00        mov  edi, 0x4041d0      ; TEMPNOTE front
400398: fc                    cld
400399: f3 a4                 rep movsb               ; copy payload into the padded slot
; --- insertion sort TEMPNOTE into the slot array ---
40039b: 8b 14 25 00 48 40 00  mov  edx, [0x404800]   ; edx = NOTE_COUNT (insert index)
4003a2: 85 d2                 test edx, edx
4003a4: 0f 84 3e 00 00 00     je   0x4003e8          ; first note → just store
4003aa: 89 d0                 mov  eax, edx
4003ac: ff c8                 dec  eax
4003ae: c1 e0 06              shl  eax, 0x6           ; (edx-1) * 64
4003b1: 05 00 43 40 00        add  eax, 0x404300      ; &slot[edx-1]
4003b6: be d0 41 40 00        mov  esi, 0x4041d0      ; TEMPNOTE
4003bb: 89 c7                 mov  edi, eax
4003bd: b9 40 00 00 00        mov  ecx, 0x40
4003c2: fc                    cld
4003c3: f3 a6                 repz cmpsb              ; compare TEMPNOTE vs slot[edx-1]
4003c5: 0f 83 1d 00 00 00     jae  0x4003e8          ; TEMPNOTE >= slot[edx-1] → position found
4003cb: 89 c6                 mov  esi, eax           ; else shift slot[edx-1] up
4003cd: 89 d0                 mov  eax, edx
4003cf: c1 e0 06              shl  eax, 0x6
4003d2: 05 00 43 40 00        add  eax, 0x404300      ; &slot[edx]
4003d7: 89 c7                 mov  edi, eax
4003d9: b9 40 00 00 00        mov  ecx, 0x40
4003de: fc                    cld
4003df: f3 a4                 rep movsb               ; move the bigger note up one slot
4003e1: ff ca                 dec  edx
4003e3: e9 ba ff ff ff        jmp  0x4003a2          ; keep scanning downward
; --- store TEMPNOTE at the found index and advance ---
4003e8: 89 d0                 mov  eax, edx
4003ea: c1 e0 06              shl  eax, 0x6
4003ed: 05 00 43 40 00        add  eax, 0x404300      ; &slot[edx]
4003f2: 89 c7                 mov  edi, eax
4003f4: be d0 41 40 00        mov  esi, 0x4041d0      ; TEMPNOTE
4003f9: b9 40 00 00 00        mov  ecx, 0x40
4003fe: fc                    cld
4003ff: f3 a4                 rep movsb               ; write the sorted slot
400401: ff 04 25 00 48 40 00  inc  DWORD [0x404800]  ; NOTE_COUNT += 1
400408: e9 11 ff ff ff        jmp  0x40031e          ; next record
; --- done: close the db and fall into the draw routine at 0x417 ---
40040d: b8 03 00 00 00        mov  eax, 0x3          ; __NR_close
400412: 4c 89 ff              mov  rdi, r15
400415: 0f 05                 syscall
```

The loop reads at most 20 notes into the slots; the `cmp ecx,0x40` guard makes a
record longer than 64 bytes terminate the load early, matching the fixed slot
width.

#### Why fixed 64-byte padded slots?

That design avoids storing per-record lengths in memory. Sorting can compare
two slots as raw 64-byte strings:

- shorter prefix records naturally sort earlier because their trailing spaces
  (`0x20`) compare smaller than printable continuation characters
- equal prefixes stay stable enough for this POC

#### Insertion sort details

The live slot array starts at `0x404300`.

For each loaded note:

1. `edx = NOTE_COUNT`
2. while `edx > 0`:
   - compare `TEMPNOTE` against slot `edx - 1` with `repe cmpsb`
   - if `TEMPNOTE >= slot[edx-1]`, stop shifting
   - otherwise copy slot `edx - 1` upward into slot `edx`, then decrement
3. copy `TEMPNOTE` into slot `edx`
4. increment `NOTE_COUNT`

There are at most **20** in-memory slots. Extra records on disk after the
20th are ignored by design.

### Section F — draw prompt and sorted list (`0x417..0x4b3`)

Section E falls straight into this routine (it is also the target when the db
open fails). It draws one prompt line built from `"New: "` plus the live input,
a blank separator, then up to 20 sorted note lines, each through the
`fill_it8_spaces` / `send_it8` helper pair.

```text
; --- prompt line: "New: " + current input text ---
400417: e8 d9 00 00 00        call 0x4004f5          ; fill_it8_spaces (blank the 64-byte buffer)
40041c: be 24 08 40 00        mov  esi, 0x400824      ; "New: "
400421: bf e4 07 40 00        mov  edi, 0x4007e4      ; IT8 string buffer
400426: b9 05 00 00 00        mov  ecx, 0x5
40042b: fc                    cld
40042c: f3 a4                 rep movsb               ; copy the 5-byte prompt
40042e: 8b 0c 25 80 41 40 00  mov  ecx, [0x404180]   ; INPUT_LEN
400435: 85 c9                 test ecx, ecx
400437: 0f 84 0d 00 00 00     je   0x40044a          ; empty input → prompt only
40043d: be 00 41 40 00        mov  esi, 0x404100      ; INPUT_BUF
400442: bf e9 07 40 00        mov  edi, 0x4007e9      ; just past "New: " in the buffer
400447: fc                    cld
400448: f3 a4                 rep movsb               ; append the typed text
40044a: 41 be 1e 00 00 00     mov  r14d, 0x1e        ; y = 30 (prompt row)
400450: e8 b0 00 00 00        call 0x400505          ; send_it8 → draw prompt line
; --- blank separator line at y = 46 ---
400455: e8 9b 00 00 00        call 0x4004f5          ; blank buffer
40045a: 41 be 2e 00 00 00     mov  r14d, 0x2e        ; y = 46
400460: e8 a0 00 00 00        call 0x400505          ; draw empty line
; --- up to 20 sorted notes starting at y = 62, step 16 ---
400465: 31 ed                 xor  ebp, ebp           ; row index = 0
400467: 41 be 3e 00 00 00     mov  r14d, 0x3e        ; y = 62 (first note row)
40046d: 83 fd 14              cmp  ebp, 0x14          ; drawn 20 rows?
400470: 0f 8d 3e 00 00 00     jge  0x4004b4          ; yes → back to event loop
400476: e8 7a 00 00 00        call 0x4004f5          ; blank buffer for this row
40047b: 8b 04 25 00 48 40 00  mov  eax, [0x404800]   ; NOTE_COUNT
400482: 39 c5                 cmp  ebp, eax
400484: 0f 8d 19 00 00 00     jge  0x4004a3          ; past the last real note → blank row
40048a: 89 e8                 mov  eax, ebp
40048c: c1 e0 06              shl  eax, 0x6           ; row * 64
40048f: 05 00 43 40 00        add  eax, 0x404300      ; &slot[row] (sorted order)
400494: 89 c6                 mov  esi, eax
400496: bf e4 07 40 00        mov  edi, 0x4007e4      ; IT8 string buffer
40049b: b9 40 00 00 00        mov  ecx, 0x40          ; 64 bytes
4004a0: fc                    cld
4004a1: f3 a4                 rep movsb               ; copy the whole slot into the buffer
4004a3: e8 5d 00 00 00        call 0x400505          ; draw this row
4004a8: 66 41 83 c6 10        add  r14w, 0x10        ; next row y += 16
4004ad: ff c5                 inc  ebp
4004af: e9 b9 ff ff ff        jmp  0x40046d          ; next row
```

Because every line is drawn as a full 64 characters (a note slot, or spaces for
rows past `NOTE_COUNT`), old text is erased simply by overdrawing spaces — no
`ClearArea` request is needed. When 20 rows are drawn the routine jumps to the
event loop at `0x4004b4`.

> The product build repoints `0x417` to a two-pane draw routine: it splits the
> screen into an editor pane and a first-word list with per-row `Del`
> affordances, but reuses these same `fill_it8_spaces` / `send_it8` helpers.

### Section G — event loop (`0x4b4..0x4f4`)

The main loop blocks in `recvfrom` for the next 32-byte X event, then dispatches
on the low 7 bits of the event type.

```text
4004b4: 41 ba 00 01 00 00     mov  r10d, 0x100        ; MSG_WAITALL
4004ba: b8 2d 00 00 00        mov  eax, 0x2d          ; __NR_recvfrom (45)
4004bf: 48 89 df              mov  rdi, rbx            ; X socket
4004c2: be 00 40 40 00        mov  esi, 0x404000       ; EVENT_BUF
4004c7: ba 20 00 00 00        mov  edx, 0x20          ; 32-byte event
4004cc: 0f 05                 syscall
4004ce: 48 85 c0              test rax, rax
4004d1: 0f 8e 4f 00 00 00     jle  0x400526          ; <=0 (closed/error) → exit_app
4004d7: 8a 04 25 00 40 40 00  mov  al, [0x404000]     ; EVENT_BUF[0] = type
4004de: 24 7f                 and  al, 0x7f           ; clear the send_event high bit
4004e0: 3c 0c                 cmp  al, 0x0c
4004e2: 0f 84 11 fe ff ff     je   0x4002f9          ; Expose (12) → redraw
4004e8: 3c 02                 cmp  al, 0x02
4004ea: 0f 84 ee fc ff ff     je   0x4001de          ; KeyPress (2) → key handler
4004f0: e9 bf ff ff ff        jmp  0x4004b4          ; anything else → ignore, keep waiting
```

**How this implements the editor:** each iteration waits for the next **X
event** (see [X11 events in the glossary](../../products/notes/glossary.md#x11-events-relevant-to-this-product);
[`recvfrom` / main loop](../../products/notes/glossary.md#recvfrom-loop)). The socket
`rbx` is the [X11 session coupling](#session-coupling). **`EVENT_BUF`** is
`0x404000` (32 bytes — enough for a core **KeyPress** / **Expose**). Masking
`& 0x7f` matches the [event dispatcher pattern](../../products/notes/targets/linux/x86_64/notes-linux-x86_64.md#event-dispatcher) in
the product build. **`Expose`** means “repaint” → full **`redraw`** (reload from
disk, sort, [`ImageText8`](../../products/notes/glossary.md#imagetext8) for every
line). **`KeyPress`** routes through [Section B](#section-b--key-handler-0x1de0x233). Any
other type (e.g. an unrequested event) is ignored by jumping back to
`recvfrom` — so spurious input does not corrupt state.

**How this stays compatible with a later `ButtonPress` product:** the product
build patches the same loop so **`ButtonPress` (`4`)** is recognized; the
`poc-04` source shown here [ignores](#limitations) non-key events.

Notably:

- In **`note-edit`**, **button** events are not handled (ignored by the
  fall-through to `loop`); the window is not expected to be clicked for
  editing.
- Forced exit when the X connection closes: the server may tear down the
  client; `recvfrom` can return `0` or an error, and the `rax <= 0` (or
  branch-equivalent) path **exits** the process. See
  [Section I — exit](#section-i--exit-0x5260x537).

### Section H — helper routines (`0x4f5..0x525`)

Two small subroutines shared by every draw.

#### `fill_it8_spaces` (`0x4004f5`)

Writes 64 copies of `0x20` into the `ImageText8` string buffer, then returns —
the blank canvas each line starts from.

```text
4004f5: bf e4 07 40 00        mov  edi, 0x4007e4      ; IT8 string buffer
4004fa: b9 40 00 00 00        mov  ecx, 0x40          ; 64 bytes
4004ff: b0 20                 mov  al, 0x20           ; ASCII space
400501: fc                    cld
400502: f3 aa                 rep stosb               ; blank the buffer
400504: c3                    ret
```

#### `send_it8` (`0x400505`)

Patches the current `y` (`r14w`) into the request template, then sends the fixed
80-byte `ImageText8` request over the X socket.

```text
400505: 66 44 89 34 25 e2 07 40 00  mov WORD [0x4007e2], r14w ; patch y field
40050e: 45 31 d2              xor  r10d, r10d          ; sendto flags 0
400511: b8 2c 00 00 00        mov  eax, 0x2c          ; __NR_sendto (44)
400516: 48 89 df              mov  rdi, rbx            ; X socket
400519: be d4 07 40 00        mov  esi, 0x4007d4       ; ImageText8 request (80 bytes)
40051e: ba 50 00 00 00        mov  edx, 0x50          ; 80 bytes
400523: 0f 05                 syscall
400525: c3                    ret
```

The `x` field at `0x4007e0` is left as the template default here; the product
build patches it per pane. Both binaries share these two routines byte for byte.

### Section I — exit (`0x526..0x537`)

`exit_app` closes the X socket (which makes the server tear down the window,
font, and GC) and exits cleanly.

```text
400526: b8 03 00 00 00        mov  eax, 0x3          ; __NR_close (3)
40052b: 48 89 df              mov  rdi, rbx           ; X socket
40052e: 0f 05                 syscall
400530: b8 3c 00 00 00        mov  eax, 0x3c         ; __NR_exit (60)
400535: 31 ff                 xor  edi, edi           ; status 0
400537: 0f 05                 syscall
```

## Syscalls used

| nr | name       | purpose |
| -- | ---------- | ------- |
| 0  | `read`     | load `notes.db` |
| 1  | `write`    | append records to `notes.db` |
| 2  | `open`     | open database |
| 3  | `close`    | close db fd and X socket |
| 8  | `lseek`    | seek to EOF before append |
| 41 | `socket`   | create Unix socket to X server |
| 42 | `connect`  | connect to X socket |
| 44 | `sendto`   | send X11 requests |
| 45 | `recvfrom` | receive X11 setup reply and events |
| 60 | `exit`     | exit process |

Ten syscalls total.

## X11 requests / events used

### Requests

- `CreateWindow`
- `ChangeProperty` (`WM_NAME`)
- `OpenFont`
- `CreateGC`
- `MapWindow`
- `ImageText8`

### Events

- `Expose` -> redraw everything
- `KeyPress` -> edit / save / exit
- connection EOF/error -> exit

## Supported behaviour verified

Verified manually and with existing external binary tooling available on the
host:

1. launch `note-edit`
2. stored notes are drawn
3. synthetic key presses for `a r b r 1 Enter Escape` append a new record
4. `notes.db` gains:

```text
06 00 00 00 61 72 62 72 31 0a
```

5. next launch shows:

```text
arbr1
hello world
second entry
```

which proves the list is being reloaded from disk and sorted before display.

## Limitations

- hard-coded X session cookie / root window / socket path
- only one keyboard layout is supported, via the baked keycode map
- only lowercase and a small punctuation set are accepted
- max input length is 63 characters
- max displayed/sorted notes is 20
- records longer than 64 bytes on disk terminate the loader early
- sorting is ASCII bytewise on 64-byte space-padded slots, not locale-aware
- no scrolling

Those are intentional constraints for a first interactive GUI that still fits
comfortably inside a hand-authored machine-code body.
