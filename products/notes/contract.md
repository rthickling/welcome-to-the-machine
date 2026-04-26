# Cross-Platform Notes Product Contract

This file defines the product behavior that the platform-specific binaries are
meant to converge on.

**Implementation vocabulary** (X11 request names, syscall-level phrases, in-memory
labels like *slot* or *NOTE_COUNT*) is in the
[**product notes glossary**](glossary.md) so it does not need to be redefined
here. This file states *what* the product does; the glossary states *how the Linux
reference names those pieces* in code and disassembly.

## Shared storage format

The product reuses the existing on-disk note framing already documented in
[`../../experiments/poc-03-notes-cli/note.md`](../../experiments/poc-03-notes-cli/note.md):

```text
[4-byte little-endian length][length bytes of note text]
```

Each note is one record in `notes.db`.

The format stays intentionally tiny and portable:

- little-endian `u32` byte length
- raw note bytes, no schema header
- file is a simple sequence of records

## Shared user-visible behavior

Every target should aim to preserve these behaviors as closely as the native
GUI stack physically allows:

1. The main editing area is the **note pane**.
2. The secondary area is a **note list pane**.
3. The note list is sorted alphabetically by the **first word** of each note.
4. Selecting or clicking a note in the list loads the full note text into the
   editor pane.
5. Pressing `Enter` stores the current editor contents as a note.
6. The editor accepts normal printable ASCII characters, including uppercase
   letters where the platform keyboard state exposes a Shift modifier.
7. The note and list panes should be visually separated with simple borders and
   readable foreground/background colours.

## Product v1 save semantics

The first committed reference build keeps the repo's existing append-only note
philosophy:

- pressing `Enter` stores the current editor contents as a new note record
- selecting a note loads it as editable text
- altering that text and pressing `Enter` stores the altered text as a new
  record

This matches the user-visible requirement that `Enter` "adds the note" while
still supporting click-to-load-and-alter behavior.

## Sorting rule

The right pane is derived from the stored notes and sorted by the same bytewise
order used by the Linux reference build:

1. compare notes from byte `0`
2. sorting is driven by the leading bytes, which naturally sorts by first word
3. later bytes act as deterministic tie-breakers

This keeps the implementation tiny and portable across the product targets.

## First-word list rule

The right pane shows only the first word of each stored note:

- copy note bytes from the beginning
- stop at the first ASCII space
- render that prefix as the list entry

If a note contains no spaces, the whole note is its "first word" for list
display.

## Portability goal

The same note file should be readable by every platform implementation in the
product family, even if the native GUI stack differs.
