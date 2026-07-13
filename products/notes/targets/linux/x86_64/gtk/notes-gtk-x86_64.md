# `products/notes/targets/linux/x86_64/gtk/notes-gtk-x86_64`

A **3819-byte** hand-authored Linux ELF64 x86_64 **dynamically-linked** GUI
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
- On startup, resolves `notes-gtk.ui` and `notes.db` beside the executable
  (via `readlink("/proc/self/exe", …)`), then reads `notes.db` and inserts one list
  row per note in **alphabetical order by first word** (the row label is the note's
  **first word**, matching the product contract).
- **Click a list row** → the full note text is loaded into the editor pane
  (`row-activated` → `gtk_text_buffer_set_text`).
- **Click `Save note`** → the editor's text is appended to `notes.db` as a new
  fixed-format record and a new row is inserted into the list at the sorted
  position live (`clicked` → append + `note_sorted_insert`).
- **Click `Delete note`** → deletes the last list row you activated (tracked in
  `g_sel_row`), compacts the in-memory note tables, calls `gtk_widget_destroy`
  on that row, rewrites `notes.db` from memory (`rewrite_db`), and clears the
  editor (`delbtn` `clicked` → `cb_delete`).
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
| 15 | `0x4006d8` | `gtk_widget_destroy` | gtk-3 | `(GtkWidget*)` |

`g_signal_connect` is a macro; the real exported symbol is
`g_signal_connect_data`, called with `data=NULL`, `destroy_data=NULL`,
`flags=0`.

## File / memory layout

The single `PT_LOAD` maps the whole file `R+W+X` at `0x400000`; `p_memsz` is
`0x40000` so everything from `p_filesz` (`0xeeb`) up to `0x440000` is
zero-filled BSS used for globals and buffers.

```text
0x000..0x040   ELF64 header (entry = 0x40076b)
0x040..0x0e8   3 program headers: PT_LOAD, PT_INTERP, PT_DYNAMIC
0x0e8..0x104   .interp  "/lib64/ld-linux-x86-64.so.2\0"
0x108..0x158   .hash    (minimal: nbucket=1, nchain=16)
0x158..0x2d8   .dynsym  (16 entries × 24 bytes; entry 0 null + 15 imports)
0x2d8..0x429   .dynstr  (symbol + library name strings)
0x430..0x598   .rela.dyn (15 × R_X86_64_GLOB_DAT, 24 bytes each)
0x598..0x658   .dynamic (12 entries)
0x658..0x6d0   .got     (slots 0–14, filled by the loader)
0x6d0..0x6d7   rodata   ("delbtn")
0x6d8..0x6e0   .got     (slot 15: gtk_widget_destroy)
0x6e0..0x6ef   rodata   ("/proc/self/exe")
0x71b..0x767   rodata   (fallback UI/DB basenames, widget ids, signal names)
0x76b..0x8c5   entry / main
0x8c6..0x9b1   load_notes
0x9b2..0xb25   cb_save   (Save-note handler)
0xb26..0xb9c   cb_row    (`row-activated` handler)
0xb9d..0xc34   rewrite_db
0xc35..0xcd7   cb_delete (`delbtn` `clicked` handler)
0xcd8..0xdb8   resolve_paths (exe-dir UI/DB path resolution)
0xdb9..0xdf7   first_word_cmp (ASCII first-word compare, space-terminated)
0xdf8..0xeea   note_sorted_insert (shift tables + gtk_list_box_insert at pos)
```

### rodata strings

| vaddr | string |
| :--- | :--- |
| `0x4006d0` | `delbtn` (8-byte padding between GOT slots 14 and 15) |
| `0x4006e0` | `/proc/self/exe` (passed to `readlink`) |
| `0x40071b` | `notes-gtk.ui` (fallback basename when `readlink` fails) |
| `0x400728` | `win` |
| `0x40072c` | `editor` |
| `0x400733` | `list` |
| `0x400738` | `savebtn` |
| `0x400740` | `destroy` |
| `0x400748` | `clicked` |
| `0x400750` | `row-activated` |
| `0x40075e` | `notes.db` (fallback basename when `readlink` fails) |

### BSS globals / buffers (zero-filled)

| vaddr | use |
| :--- | :--- |
| `0x410050` | `g_ui_path` → resolved `notes-gtk.ui` path (or `0x40071b` on failure) |
| `0x410058` | `g_db_path` → resolved `notes.db` path (or `0x40075e` on failure) |
| `0x414000` | scratch: exe path truncated to directory, then `…/notes-gtk.ui` |
| `0x414200` | scratch: copy of directory, then `…/notes.db` |
| `0x410000` | `g_builder` |
| `0x410008` | `g_win` |
| `0x410010` | `g_editor` |
| `0x410018` | `g_list` |
| `0x410020` | `g_savebtn` |
| `0x410028` | `g_buf` (editor `GtkTextBuffer*`) |
| `0x410040` | `g_sel_row` (last `row-activated` `GtkListBoxRow*`, or NULL) |
| `0x410048` | `g_delbtn` |
| `0x410060` | `g_ins_len` scratch (`u32` length during `note_sorted_insert`) |
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

### `entry` / `main` (`0x40076b`)

```text
53                     push rbx                 ; rbx = builder (also stack align)
41 54                  push r12                 ; r12 = window  (2 pushes → 16-aligned)
31 ff / 31 f6          xor edi,edi / xor esi,esi ; gtk_init(NULL,NULL)
ff 14 25 58 06 40 00   call [gtk_init]
e8 <rel32>             call resolve_paths       ; fills g_ui_path / g_db_path
48 8b 3c 25 50 00 41 00 mov rdi, [g_ui_path]
ff 14 25 60 06 40 00   call [gtk_builder_new_from_file]
48 89 c3               mov rbx, rax             ; builder
48 89 04 25 00 00 41 00 mov [g_builder], rax
```

Then five `gtk_builder_get_object` calls fetch `win`, `editor`, `list`,
`savebtn`, `delbtn` (each: `mov rdi,rbx; mov esi,<id string>; call [get_object]; store`),
and `gtk_text_view_get_buffer(editor)` is cached into `g_buf`.

Signal wiring (all via `g_signal_connect_data` with the extra three args
cleared):

```text
mov rdi,r12 ; mov esi,0x400740("destroy") ; mov rdx,[gtk_main_quit] ; ... ; call [g_signal_connect_data]
mov rdi,[g_savebtn] ; mov esi,0x400748("clicked") ; mov edx,0x4009b2(cb_save) ; ... ; call [...]
mov rdi,[g_delbtn] ; mov esi,0x400748("clicked") ; mov edx,0x400c35(cb_delete) ; ... ; call [...]
mov rdi,[g_list] ; mov esi,0x400750("row-activated") ; mov edx,0x400b26(cb_row) ; ... ; call [...]
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

### `resolve_paths` (`0x400c90`)

Calls `readlink("/proc/self/exe", buf=0x414000, len=255)`. On success, scans
backward for the final `/`, NUL-terminates after it (leaving a trailing slash),
copies that directory prefix into `0x414200`, appends `notes-gtk.ui` onto
`0x414000` and `notes.db` onto `0x414200`, then stores `g_ui_path=0x414000` and
`g_db_path=0x414200`. On `readlink` failure, falls back to the rodata basenames
`0x40071b` / `0x40075e` (cwd-relative).

### `load_notes` (`0x4008c6`)

Saves `r13/r14/r15`, then `openat(AT_FDCWD, [g_db_path], O_RDONLY)`. A negative
result jumps to the epilogue (no file → empty list). Otherwise it `read`s up to
`0x10000` bytes into `db_read` (`0x420000`), `close`s the fd, and sets
`r13 = cursor = 0x420000`, `r15 = end = 0x420000 + nread`, `g_count = 0`.

Loop body per record while `cursor < end`:

```text
41 8b 45 00            mov eax,[r13]            ; len = u32 at cursor
83 f8 40               cmp eax,64               ; reject non-fixed records
75 ..                  jne epilogue             ; (padding after valid rows is not a record)
lea rdx,[r13+4]                                 ; textptr = cursor+4
mov eax,64                                      ; fixed field length for insert
call note_sorted_insert                         ; sorted insert (see below)
mov eax,[r13] ; lea r13,[r13+rax+4]             ; advance cursor past record
```

`note_sorted_insert(rdx=text, eax=len)` finds the sorted index `k` by calling
`first_word_cmp` against each existing row's first word, shifts
`note_tab_ptr[]`/`note_tab_len[]` right from `k`, stores the new pointer/length,
builds the first-word label into `label_tmp`, and calls
`gtk_list_box_insert(list, label, k)` followed by `gtk_widget_show(label)`.
Rows added here are shown later by `gtk_widget_show_all(win)`.

### `first_word_cmp` (`0x400db9`)

Compares two NUL- or space-terminated ASCII strings byte-by-byte (sign-extended
`char` subtraction). Returns negative/positive/zero like `strcmp` on the first
word only.

### `note_sorted_insert` (`0x400df8`)

```text
; rdx = text pointer, eax = length (64 for save, or from record for load)
; length saved to g_ins_len (0x410060); prologue uses 3 pushes so the stack
; stays 16-byte aligned before GTK calls (required for SSE movaps in glib)
; find_k scans k=0..count-1 comparing first words; jg store when
;     first_word_cmp(existing[k], new) > 0 (insert before larger entry)
; shift note_tab_ptr/note_tab_len entries [k..count-1] → [k+1..count]
; note_tab_ptr[k]=rdx, note_tab_len[k]=len, build label, gtk_list_box_insert(...,k)
inc g_count
```

### `cb_save` (`0x4009b2`) — `clicked` handler

Saves `rbx/r12/r13`. Lazily initialises `g_store_next` to `0x433000` on first
use. Then:

1. `gtk_text_buffer_get_bounds(g_buf, &start, &end)` and
   `gtk_text_buffer_get_text(g_buf, &start, &end, FALSE)` → `rbx` = editor text.
2. Stage a record in `rec_buf`: `mov dword[0x413100], 0x40` (length), fill 64
   bytes at `0x413104` with `0x20` (spaces) via `rep stosb`, then copy the text
   over (stopping at NUL or 64 bytes) so the field is space-padded.
3. `openat(AT_FDCWD, [g_db_path], O_WRONLY|O_CREAT|O_APPEND, 0644)`
   (`edx=0x441`, `r10d=0x1a4`), then `write(fd, rec_buf, 68)` and `close(fd)`.
   A negative open skips the I/O but still updates the UI.
4. Copy the 64-byte field into the bump area (`g_store_next`), NUL-terminate,
   set `rdx` to that copy, `mov eax,64`, `call note_sorted_insert` (sorted list
   row + table slot).

### `cb_row` (`0x400b26`) — `row-activated` handler

```text
53                     push rbx
48 89 f0               mov rax,rsi              ; GtkListBoxRow* (NULL on deselect)
48 85 c0               test rax,rax
je epilogue
48 89 04 25 40 00 41 00 mov [g_sel_row],rax
48 89 c7               mov rdi,rax
ff 14 25 b0 06 40 00   call [gtk_list_box_row_get_index]  ; rcx = row index
; bounds-check index against g_count
48 8b 3c 25 28 00 41 00 mov rdi,[g_buf]
48 8b 34 cd 00 10 41 00 mov rsi,[note_tab_ptr + rcx*8]
48 8b 14 cd 00 20 41 00 mov rdx,[note_tab_len + rcx*8]
; trim trailing spaces from length, then:
ff 14 25 78 06 40 00   call [gtk_text_buffer_set_text](buf, text, len)
5b / c3                pop rbx / ret
```

### `cb_delete` (`0x400c35`) — `delbtn` `clicked` handler

Uses `g_sel_row` (set by `cb_row`). If NULL, `jne +6` skips a six-byte stub that
`pop`s `r13`/`r12`/`rbx` and `ret`s. Otherwise:

1. `mov rbx, rdi` — save the selected `GtkListBoxRow*`.
2. `gtk_list_box_row_get_index(row)` → index for table compaction.
3. Shift `note_tab_ptr[]` / `note_tab_len[]` entries down over the deleted index;
   `dec g_count`.
4. `gtk_widget_destroy(row)` via GOT slot `0x4006d8` (not `0x4006d0`, which
   holds the `delbtn` id string).
5. `call rewrite_db` at `0x400b9d` (full prologue: open truncate + rewrite loop) —
   truncate and rewrite `notes.db` from the in-memory tables.
6. Clear `g_sel_row`, then `gtk_text_buffer_set_text(g_buf, "", -1)` using the
   empty string at `0x40075d`.

### `rewrite_db` (`0x400b9d`)

Rewrites `notes.db` from scratch after a delete. Opens `notes.db` with
`O_RDWR|O_CREAT|O_TRUNC`, loops `rbx = 0 .. g_count-1` staging each
`note_tab_ptr[i]` into `rec_buf` and `write`s 68 bytes, then `close`s the fd.

Loop termination uses `cmp g_count, rbx` / `jae +0x54` to the `close` block at
`0x400bd4` (displacement byte at file offset `0xb7f`; the `jae` opcode is at
`0xb7e`). A corrupted byte pair (`55 54` = `push rbp` / `push rsp`) in place of
`73 54` was one prior crash source.

Epilogue: `pop r13`, `pop r12`, `pop rbx`, `ret` (matching the prologue).

## Running

```bash
DISPLAY=:0 ./products/notes/targets/linux/x86_64/gtk/notes-gtk-x86_64
```

`notes-gtk.ui` must sit beside the executable (resolved via `/proc/self/exe`).
`notes.db` is read/written beside the executable as well and is optional on first
launch. If `readlink` fails, both paths fall back to cwd-relative basenames.

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
