# `products/notes/targets/linux/x86_64/gtk/notes-gtk-x86_64`

A **2751-byte** hand-authored Linux ELF64 x86_64 **dynamically-linked** GUI
executable. Unlike the flagship `../notes-linux-x86_64` (which speaks the raw
X11 wire protocol from freestanding machine code), this build **dynamically
links GTK 3** and drives real native widgets: a titled top-level window, a
scrollable multi-line text editor, a scrollable selectable list, and a push
button — all themed by the desktop's GTK theme.

Every byte of the executable is hand-written machine code (`xxd -r -p` fed with
literal hex — the hex *is* the source). No compiler, assembler, or high-level
language was used to produce it. Per [`docs/rules.md`](../../../../../../docs/rules.md)
rule 7 it links pre-existing distribution libraries (`libgtk-3.so.0`,
`libgobject-2.0.so.0`) through the standard dynamic loader, and per the product
owner's allowance it consumes a human-readable GTK Builder XML file
([`notes-gtk.ui`](notes-gtk.ui)) which GTK itself parses.

Terminology: [product notes glossary](../../../glossary.md).

## What it does

- Loads its widget tree from `notes-gtk.ui` via `GtkBuilder`.
- On startup, reads `notes.db` from the current directory and inserts one list
  row per note (the row label is the note's **first word**, matching the
  product contract).
- **Click a list row** → the full note text is loaded into the editor pane
  (`row-activated` → `gtk_text_buffer_set_text`).
- **Click `Save note`** → the editor's text is appended to `notes.db` as a new
  fixed-format record and a new row is added to the list live
  (`clicked` → append + `gtk_list_box_insert` + `gtk_widget_show`).
- **Close the window** → `destroy` → `gtk_main_quit`, clean exit.

On-disk format is the repo's existing record layout, so `notes.db` is shared
with the raw-X11 build: each record is a little-endian `u32` length (always
`0x40`) followed by a 64-byte space-padded text field (68 bytes/record).

## Runtime dependency contract (dynamic linking)

The ELF requests interpreter `/lib64/ld-linux-x86-64.so.2` and declares two
`DT_NEEDED` libraries. All external functions are bound eagerly at load
(`DT_FLAGS = BIND_NOW`) through `R_X86_64_GLOB_DAT` relocations into a private
15-slot global-offset table; the code then calls each import indirectly with
`call qword [abs_got_slot]` (`ff 14 25 <disp32>`).

| GOT slot | vaddr    | Symbol | Library | Signature used |
| ---: | :--- | :--- | :--- | :--- |
| 0 | `0x400658` | `gtk_init` | gtk-3 | `(int*, char***)` — called `(NULL,NULL)` |
| 1 | `0x400660` | `gtk_builder_new_from_file` | gtk-3 | `(const char*) -> GtkBuilder*` |
| 2 | `0x400668` | `gtk_builder_get_object` | gtk-3 | `(GtkBuilder*, const char*) -> GObject*` |
| 3 | `0x400670` | `gtk_text_view_get_buffer` | gtk-3 | `(GtkTextView*) -> GtkTextBuffer*` |
| 4 | `0x400678` | `gtk_text_buffer_set_text` | gtk-3 | `(GtkTextBuffer*, const char*, gint)` |
| 5 | `0x400680` | `gtk_text_buffer_get_text` | gtk-3 | `(buf, GtkTextIter*, GtkTextIter*, gboolean) -> gchar*` |
| 6 | `0x400688` | `gtk_text_buffer_get_bounds` | gtk-3 | `(buf, GtkTextIter* start, GtkTextIter* end)` |
| 7 | `0x400690` | `gtk_list_box_insert` | gtk-3 | `(GtkListBox*, GtkWidget*, gint pos)` |
| 8 | `0x400698` | `gtk_label_new` | gtk-3 | `(const char*) -> GtkWidget*` |
| 9 | `0x4006a0` | `gtk_widget_show` | gtk-3 | `(GtkWidget*)` |
| 10 | `0x4006a8` | `gtk_widget_show_all` | gtk-3 | `(GtkWidget*)` |
| 11 | `0x4006b0` | `gtk_list_box_row_get_index` | gtk-3 | `(GtkListBoxRow*) -> gint` |
| 12 | `0x4006b8` | `g_signal_connect_data` | gobject-2.0 | `(instance, signal, GCallback, data, destroy, flags)` |
| 13 | `0x4006c0` | `gtk_main` | gtk-3 | `(void)` |
| 14 | `0x4006c8` | `gtk_main_quit` | gtk-3 | `(void)` |

`g_signal_connect` is a macro; the real exported symbol is
`g_signal_connect_data`, called with `data=NULL`, `destroy_data=NULL`,
`flags=0`.

## File / memory layout

The single `PT_LOAD` maps the whole file `R+W+X` at `0x400000`; `p_memsz` is
`0x40000` so everything from `p_filesz` (`0xabf`) up to `0x440000` is
zero-filled BSS used for globals and buffers.

```text
0x000..0x040   ELF64 header (entry = 0x400720)
0x040..0x0e8   3 program headers: PT_LOAD, PT_INTERP, PT_DYNAMIC
0x0e8..0x104   .interp  "/lib64/ld-linux-x86-64.so.2\0"
0x108..0x158   .hash    (minimal: nbucket=1, nchain=16)
0x158..0x2d8   .dynsym  (16 entries × 24 bytes; entry 0 null + 15 imports)
0x2d8..0x429   .dynstr  (symbol + library name strings)
0x430..0x598   .rela.dyn (15 × R_X86_64_GLOB_DAT, 24 bytes each)
0x598..0x658   .dynamic (12 entries)
0x658..0x6d0   .got     (15 × 8-byte slots, filled by the loader)
0x6d0..0x720   rodata   (UI path, widget ids, signal names, "notes.db")
0x720..0x83b   entry / main
0x83b..0x91f   load_notes
0x91f..0xa90   cb_save   (Save-note handler)
0xa90..0xabf   cb_row    (row-activated handler)
```

### rodata strings (`0x6d0`)

| vaddr | bytes | string |
| :--- | :--- | :--- |
| `0x4006d0` | `6e6f7465732d67746b2e756900` | `notes-gtk.ui` |
| `0x4006dd` | `77696e00` | `win` |
| `0x4006e1` | `65646974 6f7200` | `editor` |
| `0x4006e8` | `6c69737400` | `list` |
| `0x4006ed` | `73617665 62746e00` | `savebtn` |
| `0x4006f5` | `64657374 726f7900` | `destroy` |
| `0x4006fd` | `636c6963 6b656400` | `clicked` |
| `0x400705` | `726f772d 61637469 7661746564 00` | `row-activated` |
| `0x400713` | `6e6f7465 732e6462 00` | `notes.db` |

### BSS globals / buffers (zero-filled)

| vaddr | use |
| :--- | :--- |
| `0x410000` | `g_builder` |
| `0x410008` | `g_win` |
| `0x410010` | `g_editor` |
| `0x410018` | `g_list` |
| `0x410020` | `g_savebtn` |
| `0x410028` | `g_buf` (editor `GtkTextBuffer*`) |
| `0x410030` | `g_count` (u64 note count) |
| `0x410038` | `g_store_next` (bump pointer for saved-note text, inits to `0x433000`) |
| `0x411000` | `note_tab_ptr[]` (per-row full-text pointer) |
| `0x412000` | `note_tab_len[]` (per-row text length) |
| `0x413000` | `label_tmp` (first-word, NUL-terminated) |
| `0x413100` | `rec_buf` (68-byte record staged for `write`) |
| `0x413200` / `0x413280` | `GtkTextIter start` / `end` scratch |
| `0x420000` | `db_read` (raw `notes.db` contents; loaded rows point in here) |
| `0x433000`+ | bump area holding NUL-terminated copies of newly saved notes |

## Code walk-through

### `entry` / `main` (`0x400720`)

```text
53                     push rbx                 ; rbx = builder (also stack align)
41 54                  push r12                 ; r12 = window  (2 pushes → 16-aligned)
31 ff / 31 f6          xor edi,edi / xor esi,esi ; gtk_init(NULL,NULL)
ff 14 25 58 06 40 00   call [gtk_init]
bf d0 06 40 00         mov edi, 0x4006d0        ; "notes-gtk.ui"
ff 14 25 60 06 40 00   call [gtk_builder_new_from_file]
48 89 c3               mov rbx, rax             ; builder
48 89 04 25 00 00 41 00 mov [g_builder], rax
```

Then four `gtk_builder_get_object` calls fetch `win`, `editor`, `list`,
`savebtn` (each: `mov rdi,rbx; mov esi,<id string>; call [get_object]; store`),
and `gtk_text_view_get_buffer(editor)` is cached into `g_buf`.

Signal wiring (all via `g_signal_connect_data` with the extra three args
cleared):

```text
mov rdi,r12 ; mov esi,0x4006f5("destroy") ; mov rdx,[gtk_main_quit] ; ... ; call [g_signal_connect_data]
mov rdi,[g_savebtn] ; mov esi,0x4006fd("clicked") ; mov edx,0x40091f(cb_save) ; ... ; call [...]
mov rdi,[g_list] ; mov esi,0x400705("row-activated") ; mov edx,0x400a90(cb_row) ; ... ; call [...]
```

The `destroy` handler is the imported `gtk_main_quit` itself (its resolved
address is read from its GOT slot). `cb_save`/`cb_row` are this binary's own
routines, passed by absolute address (`mov edx, imm32`).

Finally:

```text
e8 1a 00 00 00         call load_notes
4c 89 e7               mov rdi,r12
ff 14 25 a8 06 40 00   call [gtk_widget_show_all]
ff 14 25 c0 06 40 00   call [gtk_main]
b8 e7 00 00 00 / 31 ff / 0f 05   exit_group(0)   ; reached if gtk_main returns
```

### `load_notes` (`0x40083b`)

Saves `r13/r14/r15`, then `openat(AT_FDCWD, "notes.db", O_RDONLY)`. A negative
result jumps to the epilogue (no file → empty list). Otherwise it `read`s up to
`0x10000` bytes into `db_read` (`0x420000`), `close`s the fd, and sets
`r13 = cursor = 0x420000`, `r15 = end = 0x420000 + nread`, `g_count = 0`.

Loop body per record while `cursor < end`:

```text
41 8b 45 00            mov eax,[r13]            ; len = u32 at cursor
mov rcx,[g_count]
mov [note_tab_len + rcx*8], rax                 ; remember length
lea rdx,[r13+4]                                 ; textptr = cursor+4
mov [note_tab_ptr + rcx*8], rdx                 ; remember full-text pointer
xor ecx,ecx                                     ; scan for first space → wlen
  cmp ecx,eax ; jae done ; cmpb [rdx+rcx],0x20 ; je done ; inc ecx ; jmp
rep movsb  (rsi=textptr, rdi=label_tmp, rcx=wlen) ; mov byte[rdi],0
mov edi, 0x413000 ; call [gtk_label_new]        ; label = first word
mov rsi,rax ; mov rdi,[g_list] ; mov edx,-1 ; call [gtk_list_box_insert]
inc qword [g_count]
mov eax,[r13] ; lea r13,[r13+rax+4]             ; advance cursor past record
```

Rows added here are shown later by `gtk_widget_show_all(win)`.

### `cb_save` (`0x40091f`) — `clicked` handler

Saves `rbx/r12/r13`. Lazily initialises `g_store_next` to `0x433000` on first
use. Then:

1. `gtk_text_buffer_get_bounds(g_buf, &start, &end)` and
   `gtk_text_buffer_get_text(g_buf, &start, &end, FALSE)` → `rbx` = editor text.
2. Stage a record in `rec_buf`: `mov dword[0x413100], 0x40` (length), fill 64
   bytes at `0x413104` with `0x20` (spaces) via `rep stosb`, then copy the text
   over (stopping at NUL or 64 bytes) so the field is space-padded.
3. `openat(AT_FDCWD, "notes.db", O_WRONLY|O_CREAT|O_APPEND, 0644)`
   (`edx=0x441`, `r10d=0x1a4`), then `write(fd, rec_buf, 68)` and `close(fd)`.
   A negative open skips the I/O but still updates the UI.
4. Copy the 64-byte field into the bump area (`g_store_next`), NUL-terminate,
   record `note_tab_ptr[count]`/`note_tab_len[count]=64`, so a later click on
   the new row reloads it.
5. Build the first-word label (same scan as `load_notes`),
   `gtk_list_box_insert(list, label, -1)`, `gtk_widget_show(label)` (needed
   because the main loop is already running), `inc g_count`.

### `cb_row` (`0x400a90`) — `row-activated` handler

```text
53                     push rbx                 ; align
48 89 f7               mov rdi,rsi              ; rsi = the activated GtkListBoxRow
ff 14 25 b0 06 40 00   call [gtk_list_box_row_get_index]  ; eax = row index
48 63 c8               movslq rcx,eax
mov rdi,[g_buf]
mov rsi,[note_tab_ptr + rcx*8]                  ; full text pointer
mov rdx,[note_tab_len + rcx*8]                  ; length
ff 14 25 78 06 40 00   call [gtk_text_buffer_set_text]    ; load into editor
5b / c3                pop rbx / ret
```

## Running

```bash
cd products/notes/targets/linux/x86_64/gtk
DISPLAY=:0 ./notes-gtk-x86_64      # requires notes-gtk.ui and (optionally) notes.db in cwd
```

The window title is `Notes (GTK)`. `notes-gtk.ui` must be in the working
directory (it is loaded by relative path); `notes.db` is optional (absent → an
empty list that the Save button will create).

## Verification

- [`test-notes-gtk-x86_64`](test-notes-gtk-x86_64.md) — a `mkelf`-wrapped
  structural verifier that anchors the dynamic-linking metadata (ELF ident,
  `.interp`, the `libgtk-3`/`libgobject-2.0` `DT_NEEDED` strings, the
  `gtk_builder_new_from_file` import name) and the load/save code bytes.
- Behaviorally validated on a live X server (`DISPLAY=:1`): the window renders
  with native GTK widgets, `notes.db` populates the list (`234`, `hello`,
  `hello`), and the Save path was confirmed to append a well-formed 68-byte
  record (database grew `204 → 272` bytes with the `40 00 00 00` length header
  and 64-byte padded field).

## Rule compliance

- **Rule 1 (binaries only):** the executable is hand-written machine code; the
  hex is the source of truth. `notes-gtk.ui` is a data file consumed by GTK
  (explicitly permitted), not agent-authored program source.
- **Rule 3 (documentation):** this file.
- **Rule 4 (tests):** `test-notes-gtk-x86_64`.
- **Rule 7 (linking):** GTK/GObject are linked dynamically; the exact symbols,
  calling conventions, and struct usage are documented above.

## Tested on

- Ubuntu, kernel 6.17, GTK `3.24.x`, `libgobject-2.0.so.0`
- AMD Ryzen (x86_64), X server on `DISPLAY=:1`
