# PoC-04 — terminology index

Implementation terms for **`note-edit`**, **`note-view`**, and their **test**
binaries are defined in the central
[**product notes glossary**](../../products/notes/glossary.md) (ImageText8, `pread64`,
`mkelf`, syscalls, insertion sort, …). This file only lists **where** to look in
the long-form walkthroughs.

| Term / area | Where it is explained |
| --- | --- |
| Register roles (`rbx`, `r12`, `r14`, `r15`) | [`note-edit.md` — Register conventions](note-edit.md#register-conventions) |
| **TEMPNOTE**, **RECORD_BUF**, slot array `0x404300` | [`note-edit.md` — Section E — load and sort](note-edit.md#section-e--load-and-sort-notes) |
| Keycode → ASCII table at `0x40082a` | [`note-edit.md` — Key handling model](note-edit.md#key-handling-model) |
| Fixed-width `ImageText8` / 64-byte lines | [`note-edit.md` — The fixed-width ImageText8 trick](note-edit.md#the-fixed-width-imagetext8-trick) |
| `fill_it8_spaces` / `send_it8` | [`note-edit.md` — Section H — helper routines](note-edit.md#section-h--helper-routines); [glossary: fill_it8 and send_it8](../../products/notes/glossary.md#fill_it8-and-send_it8) |
| Event loop (`recvfrom`, Expose / KeyPress) | [`note-edit.md` — Section G — event loop](note-edit.md#section-g--event-loop) |
| Title string offset `0x784` (structural test) | [`test-note-edit.md` — Why offset `0x784`?](test-note-edit.md#why-offset-0x784) |
| `test-note-view` (offset `0x384`) | [`test-note-view.md`](test-note-view.md) |
| `test-note-edit` (disassembly) | [`test-note-edit.md` — Code walkthrough](test-note-edit.md#code-walkthrough) |
| Product Linux structural tests | [`../../products/notes/test-notes-linux-x86_64.md`](../../products/notes/test-notes-linux-x86_64.md) |

When a plan or product doc says “same as `poc-04`”, the **byte layout** and
**syscall set** are authoritative in `note-edit.md` and `note-view.md`.
