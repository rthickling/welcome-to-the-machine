# `products/notes/targets/linux/x86_64/gtk/test-notes-gtk-x86_64`

A **1081-byte** statically-linked (freestanding, no libraries) Linux ELF64
x86_64 structural verifier for the dynamically-linked GTK build
[`notes-gtk-x86_64`](notes-gtk-x86_64.md). It opens the sibling binary and
`pread64`-compares **twelve** anchored byte ranges against embedded expected
bytes, exiting `0` if all match and `1` on any mismatch or I/O error.

It is built with [`tools/mkelf`](../../../../../../tools/mkelf/mkelf.md): a
`0x3c1`-byte body is wrapped with the standard 120-byte loader header, entry
`0x400078`, load base `0x400000`.

Terminology: [pread64](../../../glossary.md#pread64),
[anchored structural test](../../../glossary.md#anchored-structural-test).

## Checked ranges

Each row is `(file offset in the product, length, meaning)`:

| # | offset | len | what it anchors |
| ---: | :--- | ---: | :--- |
| 1 | `0x000` | 8 | ELF ident `7f 45 4c 46 02 01 01 00` (ELF64, LE, SysV) |
| 2 | `0x010` | 12 | `e_type=EXEC`, `e_machine=x86-64`, `e_entry=0x40076b` |
| 3 | `0x0e8` | 28 | `.interp` = `/lib64/ld-linux-x86-64.so.2\0` (proves it is dynamically linked) |
| 4 | `0x2fa` | 26 | `.dynstr` symbol name `gtk_builder_new_from_file\0` |
| 5 | `0x41f` | 14 | `DT_NEEDED` string `libgtk-3.so.0\0` |
| 6 | `0x42d` | 20 | `DT_NEEDED` string `libgobject-2.0.so.0\0` |
| 7 | `0x76b` | 14 | entry prologue `53 41 54 31 ff 31 f6 ff 14 25 58 06 40 00` (`push rbx/r12` + `call [gtk_init]`) |
| 8 | `0x71b` | 13 | UI path literal `notes-gtk.ui\0` |
| 9 | `0x75e` | 9 | database path literal `notes.db\0` |
| 10 | `0x8c6` | 15 | `load_notes` prologue `41 55 41 56 41 57 b8 01 01 00 00 bf 9c ff ff ff` (pushes + `openat` setup; path is `[g_db_path]`) |
| 11 | `0xa07` | 11 | `cb_save` record-length store `c7 04 25 00 31 41 00 40 00 00 00` (`mov dword[rec_buf],0x40`) |
| 12 | `0x851` | 5 | `clicked` wiring `ba b2 09 40 00` (`mov edx, cb_save`) |

Checks 3, 5, and 6 are the crux of the "is this really a dynamically-linked GTK
program" question: they pin the interpreter request and both shared-library
`DT_NEEDED` strings. Checks 4 and 7 pin the first real GTK call path; 10–12 pin
the load and save behaviors and the signal that connects the Save button.

## File layout

```text
0x000..0x077   120   ELF header + PT_LOAD program header (from mkelf)
0x078..0x363   748   entry: open + 12×(pread64 + repe cmpsb) checks
0x364..0x36c    9    exit(0) success
0x36d..0x378   12    exit(1) shared fail
0x379..0x389   17    path string "notes-gtk-x86_64\0"
0x38a..0x439  175    expected byte blocks (same order as the checks)
```

Total file size: **1081** bytes.

## Overall logic

```text
fd = open("notes-gtk-x86_64", O_RDONLY)        ; js fail on error
for each (offset, len, expected):
    pread64(fd, 0x401000, len, offset)         ; jne fail if return != len
    repe cmpsb(0x401000, expected, len)        ; jne fail on mismatch
exit(0)
fail: exit(1)
```

### Prologue (`0x400078`)

```text
b8 02 00 00 00         mov eax, 2            ; __NR_open
bf 79 03 40 00         mov edi, 0x400379     ; path string
31 f6 / 31 d2          xor esi/edx           ; O_RDONLY, no mode
0f 05                  syscall
48 85 c0               test rax, rax
0f 88 dc 02 00 00      js 0x40036d           ; fail
48 89 c3               mov rbx, rax          ; keep fd
```

### Per-check template

```text
b8 11 00 00 00         mov eax, 17           ; __NR_pread64
48 89 df               mov rdi, rbx
be 00 10 40 00         mov esi, 0x401000     ; scratch buffer
ba <len>               mov edx, len
41 ba <offset>         mov r10d, file_offset
0f 05                  syscall
48 83 f8 <len>         cmp rax, len
0f 85 .. fail          jne 0x40036d          ; short read → fail

be 00 10 40 00         mov esi, 0x401000
bf <expected>          mov edi, expected_block
b9 <len>               mov ecx, len
fc                     cld
f3 a6                  repe cmpsb
0f 85 .. fail          jne 0x40036d
```

All twelve `pread64` blocks and both exits were disassembled and confirmed to
branch to the single `fail` label at `0x40036d`; the success path falls through
to `exit(0)` at `0x400364`.

## Syscalls used

- `2` = `open`
- `17` = `pread64`
- `60` = `exit`

## What this proves

It proves the committed GTK product binary still declares the dynamic-linking
metadata that makes it a GTK program (interpreter + both library `DT_NEEDED`
entries + the `gtk_builder_new_from_file` import) and still contains the
load/save/entry code bytes at their expected offsets. A single flipped byte in
any anchored range fails the test (verified by mutation: flipping the entry
byte at `0x720` yields exit `1`).

It is structural: it does not launch a display, synthesize clicks, or exercise
the GTK runtime. Live behavior is validated separately (see the app's Markdown).

## Tested on

- Ubuntu, kernel 6.17, x86_64
