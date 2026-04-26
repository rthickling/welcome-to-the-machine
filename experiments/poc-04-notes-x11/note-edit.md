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

`mkelf` prepends the usual 120-byte ELF header + PT_LOAD header.

The body is intentionally split into a **fixed-size code region** and a
**fixed-address data region**:

```text
body offset   vaddr       size    content
-----------   ---------   -----   -----------------------------------------
0x000..0x4c0  0x400078    1217    executable code
0x4c1..0x687  0x400539     455    zero padding
0x688..0x8b1  0x400700     554    data templates / strings / keymap
```

That fixed `0x400700` data base is deliberate:

1. It makes the code easier to hand-address.
2. It gives `test-note-edit` a stable file offset for the WM title string.

`mkelf` also provides 64 KiB of zero-filled writable memory beyond EOF. The
binary uses that BSS area for all runtime state.

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

### Section A — connect to X and fetch setup reply

The first 125 bytes are the same shape as `note-view`:

1. `socket(AF_UNIX, SOCK_STREAM, 0)`
2. `connect` to `/tmp/.X11-unix/X1`
3. `sendto` the 48-byte setup request
4. `recvfrom` the 8-byte setup header
5. read `additional-data-length`
6. `recvfrom` the rest of the setup reply
7. load `resource-id-base` from `SETUP_BUF+12`

The code then patches the request templates exactly once:

- window id = `rid | 1`
- font id = `rid | 2`
- gc id = `rid | 3`

Then it sends:

1. `CreateWindow`
2. `ChangeProperty(WM_NAME="note-edit")`
3. `OpenFont("fixed")`
4. `CreateGC`
5. `MapWindow`

Finally it jumps directly to `redraw`, so the prompt appears immediately
without waiting for the first `Expose`.

### Section B — key handler

`handle_key` does:

1. read keycode from `EVENT_BUF+1`
2. translate through the lookup table
3. branch by translated byte

Branches:

- `0x00` -> ignore
- `0x1b` -> `exit_app`
- `0x08` -> `backspace`
- `0x0a` -> `save_if_any`
- otherwise -> append printable byte to `INPUT_BUF`

The input length is capped at **63 characters** so the saved record length is
at most 64 bytes including the final newline.

### Section C — backspace

`backspace` is tiny:

1. load `INPUT_LEN`
2. if zero, ignore
3. decrement it
4. jump to `redraw`

The bytes already sitting in `INPUT_BUF` are not cleared; only the length
matters, and the fixed-width redraw overwrites the whole input line with
spaces anyway.

### Section D — save current input

`save_if_any` runs on Enter:

1. if `INPUT_LEN == 0`, just redraw
2. `open("notes.db", O_RDWR|O_CREAT, 0644)`
3. `lseek(fd, 0, SEEK_END)`
4. store `INPUT_LEN + 1` into the scratch word
5. `write` the 4-byte length
6. `write` the typed bytes from `INPUT_BUF`
7. `write` one newline byte
8. `close(fd)`
9. zero `INPUT_LEN`
10. jump to `redraw`

So the file stays append-only and fully compatible with `poc-03/note` and
`poc-04/note-view`.

### Section E — load and sort notes

`redraw` begins by zeroing `NOTE_COUNT`, then tries to open `notes.db`
read-only.

If the open succeeds, it loops:

1. `read(fd, &SCRATCH, 4)` for the length prefix
2. stop on EOF or short read
3. reject lengths `<= 0` or `> 64`
4. `read(fd, RECORD_BUF, len)`
5. strip a trailing newline if present
6. build a 64-byte fixed-width temporary note:
   - fill `TEMPNOTE` with spaces
   - copy the record bytes into the front
7. insertion-sort that 64-byte block into the slot array

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

### Section F — draw prompt and sorted list

After loading closes the db fd, `draw_screen` emits:

1. prompt line at `y = 30`
2. a blank separator line at `y = 46`
3. up to 20 note lines starting at `y = 62`, step `16`

Every line draw uses the same helper path:

1. fill the 64-byte text payload buffer with spaces
2. optionally copy prompt/input or one note slot into the front
3. patch the `y` field inside the `ImageText8` template
4. `sendto` the 80-byte request

Because every line is always redrawn as 64 characters, old text is erased
simply by drawing spaces over it.

### Section G — event loop

The main loop is:

```text
recvfrom(rbx, EVENT_BUF, 32, MSG_WAITALL, 0, 0)
if rax <= 0: exit
type = EVENT_BUF[0] & 0x7f
if type == Expose:   redraw
if type == KeyPress: handle_key
else:                loop
```

**How this implements the editor:** each iteration waits for the next **X
event** (see [X11 events in the glossary](../../products/notes/glossary.md#x11-events-relevant-to-this-product);
[`recvfrom` / main loop](../../products/notes/glossary.md#recvfrom-loop)). The socket
`rbx` is the [X11 session coupling](#session-coupling). **`EVENT_BUF`** is
`0x404000` (32 bytes — enough for a core **KeyPress** / **Expose**). Masking
`& 0x7f` matches the [event dispatcher pattern](../../products/notes/notes-linux-x86_64.md#event-dispatcher) in
the product build. **`Expose`** means “repaint” → full **`redraw`** (reload from
disk, sort, [`ImageText8`](../../products/notes/glossary.md#imagetext8) for every
line). **`KeyPress`** routes through [Section B](#section-b--key-handler). Any
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
  [Section I — exit](#section-i--exit).

### Section H — helper routines

Two small internal subroutines are used:

#### `fill_it8_spaces`

Writes 64 copies of `0x20` into `IT8_STR` using `rep stosb`.

#### `send_it8`

1. stores `r14w` into `IT8+14` (the `y` field)
2. clears `r10d`
3. `sendto(rbx, IT8, 80, 0, 0, 0)`
4. returns

### Section I — exit

`exit_app` is the same pattern as the earlier X11 POCs:

1. `close(rbx)`
2. `exit(0)`

Closing the X socket is enough for the server to clean up the window, font and
GC resources.

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
