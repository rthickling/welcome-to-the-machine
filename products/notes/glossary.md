# Product notes — glossary

Canonical definitions for **implementation and protocol terms** used across this
repo: [`targets/linux/x86_64/notes-linux-x86_64.md`](targets/linux/x86_64/notes-linux-x86_64.md), [`poc-04`](../../experiments/poc-04-notes-x11/note-edit.md), structural
test binaries, [`mkelf`](../../tools/mkelf/mkelf.md), and the platform plan docs. The
**shared user-visible behavior** is specified separately in
[`product-contract.md`](product-contract.md).

- **PoC-04**-specific walkthroughs (register roles, `TEMPNOTE`, keymap address) also
  live in [`poc-04/glossary.md`](../../experiments/poc-04-notes-x11/glossary.md) (short index + pointers here).

## ImageText8

**ImageText8** is an [X11 core protocol](https://www.x.org/releases/X11R7.7/doc/xproto/x11protocol.html#requests:drawing)
request: the client sends a small fixed header (request length, opcode, drawable
ID, graphics-context ID, x, y) followed by a **byte string** of text. The
server draws that string in the window using the given GC. The Linux reference
build does **not** use a widget toolkit: it fills a preallocated **wire
request** in memory (length `0x50` = 80 bytes in this binary) and issues
[`sendto(2)`](https://man7.org/linux/man-pages/man2/sendto.2.html) on the X11
socket, one send per line of on-screen text.

In these docs, **IT8** and **IT8 buffer** usually mean the **8-bit text
payload** copied into the same request template (a 64-byte string region in the
`PT_LOAD` image), not a separate X11 type.

## IT8 buffer and wire request

- **IT8 buffer** (informal; “ImageText8 text buffer”): the 64-byte region where
  the program writes characters before a draw (e.g. `0x4007e4` in the
  reference build). It must be cleared or overwritten so a shorter line
  does not leave old glyphs visible.
- **Wire request** (or “X request”): the full byte sequence sent on the X11
  socket, including the X11 request header and the `ImageText8` string. The
  helper at `send_it8` patches **y** in the template and sends this buffer.

## Raw X11

**Raw X11** (or “raw-X11”): the client speaks the X11 **binary protocol**
directly (socket, `send`/`sendto`/`recvfrom`), without Xlib, xcb, or a toolkit.
Resource IDs, event masks, and request layouts are **baked into** the
reference binary, as in [`poc-04`](../../experiments/poc-04-notes-x11/note-edit.md).

## BSS

**BSS** (Block Started by Symbol): the ELF **uninitialized data** segment, or
by extension the in-memory **writable** variables at fixed **virtual
addresses** used in the docs (`0x404xxx`). The program treats these as global
state (editor buffer, counts, X event buffer).

## Note slot, NOTE_COUNT, and slot array

- **Note slot** (or **slot**): one **64-byte** in-memory record holding a
  stored note’s text (padded with spaces in this implementation). The **slot
  array** starts at **`0x404300`**. Index `i` is at `0x404300 + i * 0x40`.
- **`NOTE_COUNT`**: the number of in-memory note slots in use, stored in the
  **global word** at **`0x404800`**. The UI draws the first `NOTE_COUNT` list
  rows; delete logic compacts slots and decrements this count.
- The list order matches the **insertion-sorted** order established when notes
  are loaded (see [product contract — sorting](product-contract.md#sorting-rule)).

## INPUT_LEN and editor buffer

- **Editor buffer**: the 64-byte **left-pane** text at **`0x404100`**, holding
  the line the user is editing. Load-from-list copies a full **slot** here.
- **`INPUT_LEN`**: the number of **meaningful** bytes in the editor buffer
  (for trimming, redraw length), stored in the **global** at **`0x404180`** in
  the `poc-04` / product layout. It is not the C `strlen` of a C string; it
  matches the `poc-04` key-handling model (see
  [`poc-04`](../../experiments/poc-04-notes-x11/note-edit.md)).

## Selected row

**Selected row** (product state): which list row is considered **selected**,
stored as a 32-bit index at **`0x404804`**, or `0xffffffff` (**−1**) if **no**
row is selected. This affects load semantics and the startup stub
(initialises to `−1`).

## Recvfrom loop

The **X11 main loop** in this program blocks on
[`recvfrom(2)`](https://man7.org/linux/man-pages/man2/recvfrom.2.html) (or
equivalent) to read **X events** and replies into a static buffer. **Unknown**
or irrelevant events jump back to this loop; **ButtonPress** is dispatched to
the click handler. (Exact syscall usage is documented in `poc-04`.)

## X11 events (relevant to this product)

- **`Expose` (`0x0c`)**: the server says part of the window must be redrawn; the
  app calls its **redraw** path.
- **`KeyPress` (`0x02`)**: keyboard; handled by the existing `poc-04` key table.
- **`ButtonPress` (`0x04`)**: mouse button down; the product’s **event mask**
  was patched so these are **delivered**; used for list hit-testing and
  **Del**.

The first byte of the 32-byte **XEvent** in the buffer (after any bytes read by
`recvfrom`) is the **event type**; the reference code may mask with `0x7f` to
clear the **send_event** bit per X11 encoding.

## ChangeProperty and WM_NAME

**`ChangeProperty`** is an X11 request that sets a **property** (e.g. **window
title**). The **WM_NAME** property holds the string shown as the title bar.
`notes-linux-x86_64` **patches the literal** embedded in the request template
(e.g. file offset `0x784` for the title bytes). Structural tests `pread` those
offsets to verify the build.

## PT_LOAD

**`PT_LOAD`**: an ELF **program header** entry describing a **segment** of the
file mapped into memory (code + data). The single-load layout of these
binaries is described in the `poc-04` and product docs.

## fill_it8 and send_it8

These are **function names in the disassembly** (addresses `0x4004f5` and
`0x400505` in the product build): clear the 64-byte IT8 buffer, then **patch y**
and `sendto` the wire `ImageText8` request. `poc-04` may label them slightly
differently in prose.

## First-word list and Del affordance

Defined in the [product contract](product-contract.md#first-word-list-rule) and
[README](README.md#current-linux-x86-64-behavior). **First-word** is the
alphabetical list column; **Del** is a per-row **click target** to delete,
implemented as a second **ImageText8** at a **larger x** so **x** separates
*load* from *delete* in the same row band.

## notes.db and delete rewrite

- **`notes.db`**: the on-disk file holding note records. Format:
  [length-prefixed](product-contract.md#shared-storage-format) text.
- **Rewrite on delete** (v1 product): after **compacting** in-memory slots, the
  helper **truncates** the file and **writes** each surviving slot (here as
  **fixed 64-byte** payloads) so persistence matches RAM.

## mkelf

**mkelf** is the repo’s [minimal ELF64 wrapper tool](../../tools/mkelf/mkelf.md). It
prepends a **120-byte** ELF + `PT_LOAD` header to a **body** that starts at
virtual address **`0x400078`**, and reserves **64 KiB** of zeroed **BSS** after
the file for runtime buffers. Most POC and product static binaries in this
repository are built with it.

<a id="linux-syscalls-x86-64-syscall"></a>

## Linux system calls (x86_64 `syscall`)

In **64-bit** code, the convention is: syscall number in **`eax`**, arguments in
`rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9` (as used in these sources), then the
`syscall` instruction. Common numbers referenced in the docs (see
[`syscalls(2)`](https://man7.org/linux/man-pages/man2/syscalls.2.html)):

| `eax` | Name | Role in these apps |
| ---: | --- | --- |
| 0 | `read` | read `notes.db` records |
| 1 | `write` | append records, `ImageText8` via socket |
| 2 | `open` | open `notes.db` or a sibling test binary (structural tests) |
| 3 | `close` | close fd |
| 8 | `lseek` | seek to end before append |
| 17 | `pread64` | read at a **fixed file offset** without changing fd position (structural tests) |
| 41 | `socket` | create Unix stream socket to X11 |
| 42 | `connect` | connect to `/tmp/.X11-unix/...` |
| 44 | `send` / `sendto` | send X11 wire bytes |
| 45 | `recv` / `recvfrom` | receive setup reply and events |
| 60 | `exit` | process exit with status in `edi` |

<a id="pread64"></a>

## Pread64

**pread64** (syscall **17**): `pread(fd, buf, count, pos)` — read exactly from
**absolute** offset `pos` in the file. Structural tests use it to **anchor**
checks: open the target binary, read a few bytes at a known *file offset* (e.g.
`0x784` for a title string) without a separate `lseek`, then compare. See
[anchored structural test](#anchored-structural-test).

<a id="anchored-structural-test"></a>

## Anchored structural test

An **anchored** (or **structural**) **test** binary opens a **sibling** ELF
(usually the same size family as the product) and verifies **fixed offsets**
(Unicode/patch points: title, labels, or machine-code bytes). It is **headless**:
no X server required. Failing any check exits non-zero; all match exits `0`.

## Resource ID and X11 setup

The X11 **connection setup** reply includes a **resource-id base** and mask; the
client **OR**s small integers onto that base to form **drawable** (window), **GC**,
**font** IDs sent in `CreateWindow`, `CreateGC`, etc. (See `r12` / **rid** in
[`note-edit` register table](../../experiments/poc-04-notes-x11/note-edit.md#register-conventions).)

## CreateWindow, MapWindow, OpenFont, CreateGC

Standard **X11 core requests** used after setup: create the window, set **WM_NAME**
with `ChangeProperty`, load the **"fixed"** font, create a **graphics context**
(GC) for drawing, map the window. Exact wire layouts are **template bytes** in
the data section; the binary patches in resource IDs and sends them with
`sendto`. See
[`poc-04` Section A — connect](../../experiments/poc-04-notes-x11/note-edit.md#section-a--connect-to-x-and-fetch-setup-reply).

## Graphics context (GC)

A **graphics context (GC)** holds drawing parameters (foreground, font, line style).
`ImageText8` is sent with both a **drawable** (window) id and a **GC** id; the
server uses the GC’s font to render the 8-bit text.

<a id="repe-cmpsb-and-string-direction"></a>

## `rep(e) cmpsb` and string direction

**`repe` / `repz` `cmpsb`** (prefix `F3` + `A6`): compare bytes at **`ds:rsi`**
and **`es:rdi`**, count `ecx`, stop early on **mismatch**; **`cld`** (clear
direction) means forward. Used after **`pread64`** in structural tests to match
an expected string in the test image to bytes read from the product binary, and
during **`note-edit`** insertion sort when moving **64-byte slots**.

## Session coupling (X11)

**Session coupling**: `note-edit` / the product build embed the **X socket path**,
**MIT-MAGIC-COOKIE-1** value, and sometimes **root window id** from a **specific
developer machine**. A different X session **requires a rebuild**; structural
tests avoid this by not opening X.

## MSG_WAITALL

**`MSG_WAITALL`** (if used on `recvfrom`): block until the requested byte count
is read or an error. The `poc-04` event loop reads a **32-byte** X event; the
exact flags depend on the binary’s `recvfrom` arguments.

## Insertion sort (in-memory notes)

**Insertion sort** on **64-byte space-padded slots** (see
[`note-edit` — Section E — load and sort notes](../../experiments/poc-04-notes-x11/note-edit.md#section-e--load-and-sort-notes):
each new note is compared with existing slots with **`repe cmpsb`** and shifted
up until the correct position, then the count is increased. The **right-pane**
**first-word** order in the product follows the same bytewise order (see
[product contract — sorting](product-contract.md#sorting-rule)).

## Cross-reference index

| Term | Primary doc |
| --- | --- |
| ImageText8, IT8, wire request | this file, [`targets/linux/x86_64/notes-linux-x86_64.md`](targets/linux/x86_64/notes-linux-x86_64.md) |
| User-visible product rules | [`product-contract.md`](product-contract.md) |
| `poc-04` base binary | [`poc-04/note-edit.md`](../../experiments/poc-04-notes-x11/note-edit.md), [`poc-04/glossary.md`](../../experiments/poc-04-notes-x11/glossary.md) |
| `mkelf` | [`mkelf.md`](../../tools/mkelf/mkelf.md) |
| Syscall numbers, `pread64` | this file, structural `test-*.md` |
| Structural tests | [`test-targets/linux/x86_64/notes-linux-x86_64.md`](test-targets/linux/x86_64/notes-linux-x86_64.md) |

When this glossary uses a **term in bold** on first mention in a section, later
uses in the same file refer back to that definition.
