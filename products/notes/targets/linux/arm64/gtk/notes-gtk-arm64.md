# `products/notes/targets/linux/arm64/gtk/notes-gtk-arm64`

A **4288-byte** hand-authored Linux ELF64 **AArch64** **dynamically-linked** GUI
executable. Behaviour matches
[`notes-gtk-x86_64`](../../x86_64/gtk/notes-gtk-x86_64.md): GTK 3 via GtkBuilder,
68-byte `notes.db` records, sorted first-word list, click-to-load, Save append,
Delete rewrite.

**The executable is the solution.** Every control-flow and data path for the
notes UI lives as AArch64 opcodes inside this ELF. Per
[`docs/rules.md`](../../../../../../docs/rules.md) there is no shell emitter,
assembler source, or other interpreted builder committed for this target. The
matching Markdown documents those opcodes; it does not generate them.

The UI description [`notes-gtk.ui`](notes-gtk.ui) is consumed at runtime by GTK
(allowed human-readable Builder XML, same as the x86_64 GTK twin).

## What the opcodes do

- `resolve_paths` — store cwd-relative `notes-gtk.ui` / `notes.db` basenames into
  `g_ui_path` / `g_db_path`.
- `load_notes` — `openat`/`read`/`close` of `notes.db`, walk 68-byte records,
  `note_sorted_insert` for each.
- `note_sorted_insert` / `first_word_cmp` — alphabetical first-word insert into
  `note_tab_*` + `gtk_list_box_insert` of a first-word label.
- `cb_save` — editor text → space-padded 68-byte append → bump copy → sorted
  insert.
- `cb_row` — remember `g_sel_row`, `gtk_text_buffer_set_text` from tables.
- `cb_delete` — null-safe; compact tables; `gtk_widget_destroy`; `rewrite_db`;
  clear editor.
- `rewrite_db` — truncate/rewrite all records from the in-memory tables.
- `main` — `gtk_init`, builder, widgets, signal wiring, `load_notes`,
  `gtk_main`.

## Dynamic linking

| Field | Value |
| --- | --- |
| Size | 4288 (`0x10c0`) |
| `e_machine` | `0xb7` (`EM_AARCH64`) |
| `e_entry` | `0x400780` |
| Interpreter | `/lib/ld-linux-aarch64.so.1` |
| Relocs | 16 × `R_AARCH64_GLOB_DAT` (`0x401`) |

GOT slots `0x400658`…`0x4006d8` (destroy); `"delbtn"` at `0x4006d0`.

## Code map (vaddr)

```text
0x400780  b main
0x400784  resolve_paths
0x4007c0  first_word_cmp
0x4007fc  note_sorted_insert
0x400970  load_notes
0x400a2c  rewrite_db
0x400af0  cb_save
0x400ca0  cb_row
0x400d2c  cb_delete
0x400e30  main
```

`note_sorted_insert` find loop at `0x400848`: after `first_word_cmp`, use
`cmp w0, #0` / `b.gt` (encoding `7100001f`). A 64-bit `cmp x0, #0` mis-reads
negative `w0` results as large positives and breaks sort order.

BSS layout matches the x86_64 GTK build (`g_sel_row` `0x410040`, tables at
`0x411000`/`0x412000`, `db_read` `0x420000`, bump `0x433000`, …).

## Syscalls

| nr | name | use |
| ---: | --- | --- |
| 56 | `openat` | load / append / rewrite |
| 63 | `read` | load `notes.db` |
| 64 | `write` | append / rewrite |
| 57 | `close` | after I/O |
| 94 | `exit_group` | after `gtk_main` |

GTK imports: `movz`/`movk` GOT → `ldr x16,[x17]` → `blr x16`.

## Signal wiring (absolute handler addresses)

```text
clicked  save → 0x400af0  (cb_save)
clicked  del  → 0x400d2c  (cb_delete)
row-activated → 0x400ca0  (cb_row)
destroy       → gtk_main_quit via GOT 0x4006c8
```

## Running

```bash
cd products/notes/targets/linux/arm64/gtk
mkdir -p /tmp/a64root/lib
ln -sf /usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1 \
       /tmp/a64root/lib/ld-linux-aarch64.so.1

DISPLAY=$DISPLAY GDK_BACKEND=x11 \
  qemu-aarch64-static -cpu cortex-a53 -L /tmp/a64root ./notes-gtk-arm64
```

Use `-cpu cortex-a53` (or `cortex-a57`). Inherit `DISPLAY` from the shell.
Keep `notes-gtk.ui` and `notes.db` beside the binary.

## Editing

Change behaviour only by patching **literal opcode bytes** in
`notes-gtk-arm64` (and updating this Markdown +
[`test-notes-gtk-arm64`](test-notes-gtk-arm64) anchors). Do not reintroduce a
shell/`printf`-arithmetic emitter.

## Verification

```bash
./test-notes-gtk-arm64    # exit 0
```

## Tested on

- Ubuntu, kernel 6.17, x86_64 host, `qemu-aarch64-static -cpu cortex-a53`
- Structural verifier exit `0`
