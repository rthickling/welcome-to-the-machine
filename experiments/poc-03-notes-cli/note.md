# `poc-03/note` — byte-by-byte

`note` is a 505-byte hand-hexed Linux ELF64 x86_64 executable that reads
text from stdin, appends it as a length-prefixed record to a tiny
on-disk "database" (`notes.db`), then re-reads the whole database and
renders every record as a colour-bulleted list on stdout.

- **Input**: stdin, up to 2048 bytes, terminated by EOF (Ctrl-D in a
  terminal, or pipe close).
- **Storage**: `./notes.db`, a sequence of records of the form
  `<4-byte little-endian length><length bytes of text>`.
- **Output**: the prompt, a bold header, then every stored record on its
  own line preceded by a green `-` bullet.

No library is linked; all I/O is through direct Linux syscalls. The
binary was hand-written in hex and wrapped into an ELF with
[`tools/mkelf`](../../tools/mkelf/mkelf.md).

## Usage

```bash
echo "first note" | ./note
echo "second note" | ./note
./note < /dev/null    # show everything stored so far (appends an empty record)
```

Interactive:

```bash
./note
Enter note, end with Ctrl-D:
<type text, press Enter, press Ctrl-D>
```

## File layout

mkelf prepends a 120-byte ELF header + program header stub to the 385
byte body, producing a 505-byte file:

| Range          | Length | Content                                       |
|----------------|--------|-----------------------------------------------|
| `0x000..0x077` | 120    | ELF64 header + single PT_LOAD program header  |
| `0x078..0x1ae` | 311    | Executable code                               |
| `0x1af..0x1f8` | 74     | Data: prompt, header, bullet, newline, path   |

The program header sets `p_filesz = 0x1f9` and `p_memsz = 0x101f9`, i.e.
64 KiB of zero-filled BSS beyond end-of-file. BSS is where the buffers
live:

| BSS address | Purpose                                               |
|-------------|-------------------------------------------------------|
| `0x00401000` | 4-byte scratch slot for the length prefix (LE u32)   |
| `0x00402000` | 2 KiB stdin accumulation buffer                      |
| `0x00403000` | 2 KiB display buffer (one record at a time)          |

`p_flags` is `R|W|X` (=7), so the kernel permits `read(2)` to write
record data into the BSS buffers.

## Data section at vaddr `0x4001af`

Byte-exact contents:

| Vaddr        | Bytes                                                            | String                                   |
|--------------|------------------------------------------------------------------|------------------------------------------|
| `0x4001af`   | `45 6e 74 65 72 20 6e 6f 74 65 2c 20 65 6e 64 20 77 69 74 68 20 43 74 72 6c 2d 44 3a 0a` | `"Enter note, end with Ctrl-D:\n"` (29 B) |
| `0x4001cc`   | `1b 5b 31 6d 4e 6f 74 65 73 20 73 6f 20 66 61 72 3a 1b 5b 30 6d 0a` | `"\e[1mNotes so far:\e[0m\n"` (22 B)      |
| `0x4001e2`   | `20 20 1b 5b 33 32 6d 2d 1b 5b 30 6d 20`                          | `"  \e[32m-\e[0m "` (13 B)                |
| `0x4001ef`   | `0a`                                                              | `"\n"` (1 B)                             |
| `0x4001f0`   | `6e 6f 74 65 73 2e 64 62 00`                                      | `"notes.db\0"` (9 B, C string)            |

## Code walk-through (311 bytes at vaddr `0x400078`)

### Register conventions

The program uses the Linux x86_64 syscall ABI:

- Syscall number in `rax`, args in `rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9`.
- `rax` is clobbered by `syscall`; `rcx` and `r11` also clobbered.
- All other GPRs are preserved across `syscall`.

Internal long-lived state lives in callee-preserved registers so it
survives all the syscalls:

- `rbx` = `notes.db` file descriptor.
- `rbp` = number of bytes read from stdin (final record length).
- `r12` = base address of the stdin buffer (`0x00402000`).
- `r14` = current record length being displayed.

### Section 1 — print prompt (vaddr `0x400078`, 22 bytes)

```
b8 01 00 00 00           mov eax, 1                ; sys_write
bf 01 00 00 00           mov edi, 1                ; stdout
be af 01 40 00           mov esi, 0x004001af       ; &prompt
ba 1d 00 00 00           mov edx, 29               ; prompt length
0f 05                    syscall
```

Writes `"Enter note, end with Ctrl-D:\n"` to stdout.

### Section 2 — initialise the read accumulator (vaddr `0x40008e`, 8 bytes)

```
31 ed                    xor ebp, ebp              ; total_read = 0
41 bc 00 20 40 00        mov r12d, 0x00402000      ; stdin buffer base
```

`rbp` is zero-extended from `ebp`; `r12` is zero-extended from `r12d`.

### Section 3 — read-loop (vaddr `0x400096`, 29 bytes)

```
read_loop:
31 c0                    xor eax, eax              ; sys_read
31 ff                    xor edi, edi              ; stdin
4c 89 e6                 mov rsi, r12              ; buffer base
48 01 ee                 add rsi, rbp              ; ... + already-read
ba 00 08 00 00           mov edx, 2048             ; max allowed
29 ea                    sub edx, ebp              ; ... - already-read
0f 05                    syscall
48 85 c0                 test rax, rax
7e 05                    jle read_done             ; EOF or error → done
48 01 c5                 add rbp, rax              ; accumulate
eb e3                    jmp read_loop
read_done:
```

A classic partial-read loop. The branch `jle read_done` treats both
`rax == 0` (EOF) and `rax < 0` (error, e.g. `EINTR`) as "done". Maximum
input size is hard-capped at 2048 bytes; further bytes from stdin would
be silently discarded in a subsequent `read` that returns 0.

### Section 4 — open the database (vaddr `0x4000b3`, 25 bytes)

```
b8 02 00 00 00           mov eax, 2                ; sys_open
bf f0 01 40 00           mov edi, 0x004001f0       ; "notes.db"
be 42 00 00 00           mov esi, 0x42             ; O_RDWR | O_CREAT
ba a4 01 00 00           mov edx, 0x1a4            ; mode 0644
0f 05                    syscall
48 89 c3                 mov rbx, rax              ; save fd
```

`O_RDWR = 2`, `O_CREAT = 0x40`, combined = `0x42`. Mode `0x1a4 = 0o644`.
The return value (fd) is stashed in `rbx` and kept for the rest of the
program.

### Section 5 — seek to end for append (vaddr `0x4000cc`, 17 bytes)

```
b8 08 00 00 00           mov eax, 8                ; sys_lseek
48 89 df                 mov rdi, rbx              ; fd
31 f6                    xor esi, esi              ; offset 0
ba 02 00 00 00           mov edx, 2                ; SEEK_END
0f 05                    syscall
```

Appends are done by seeking to EOF before writing. `O_APPEND` was not
used so we can seek freely in section 9 below.

### Section 6 — stash length in BSS scratch (vaddr `0x4000dd`, 7 bytes)

```
89 2c 25 00 10 40 00     mov [0x00401000], ebp
```

Writes the 32-bit length (= bytes read from stdin) into the BSS scratch
word. Encoding `89 2c 25 disp32` is `MOV r/m32, r32` with a SIB-only
(no base, no index) memory form. Since `ebp <= 2048`, the upper bits
don't matter, but storing as a full 32-bit LE integer matches the
on-disk record layout.

### Section 7 — write the 4-byte length prefix (vaddr `0x4000e4`, 20 bytes)

```
b8 01 00 00 00           mov eax, 1                ; sys_write
48 89 df                 mov rdi, rbx              ; db fd
be 00 10 40 00           mov esi, 0x00401000       ; &scratch
ba 04 00 00 00           mov edx, 4                ; 4 bytes
0f 05                    syscall
```

This is the only place the length field hits disk.

### Section 8 — write the record body (vaddr `0x4000f8`, 16 bytes)

```
b8 01 00 00 00           mov eax, 1                ; sys_write
48 89 df                 mov rdi, rbx              ; db fd
4c 89 e6                 mov rsi, r12              ; stdin buffer
48 89 ea                 mov rdx, rbp              ; length
0f 05                    syscall
```

Appends exactly the bytes that came in from stdin, verbatim, including
any trailing newline. No encoding or escaping.

### Section 9 — seek back to start (vaddr `0x400108`, 14 bytes)

```
b8 08 00 00 00           mov eax, 8                ; sys_lseek
48 89 df                 mov rdi, rbx              ; fd
31 f6                    xor esi, esi              ; offset 0
31 d2                    xor edx, edx              ; SEEK_SET
0f 05                    syscall
```

Both offset and whence are zeroed with `xor`, saving two bytes versus
`mov edx, 0`.

### Section 10 — print the list header (vaddr `0x400116`, 22 bytes)

```
b8 01 00 00 00           mov eax, 1                ; sys_write
bf 01 00 00 00           mov edi, 1                ; stdout
be cc 01 40 00           mov esi, 0x004001cc       ; &header
ba 16 00 00 00           mov edx, 22
0f 05                    syscall
```

Writes `"\e[1mNotes so far:\e[0m\n"` (22 bytes), making the header
bold via ANSI SGR 1 and resetting with SGR 0.

### Section 11 — display-loop (vaddr `0x40012c`, 112 bytes)

The loop reads one record per iteration and prints it. It exits when
the next `read` returns anything other than a full 4-byte length.

**11a. Read 4-byte length** (17 bytes)

```
disp_top:
31 c0                    xor eax, eax              ; sys_read
48 89 df                 mov rdi, rbx              ; db fd
be 00 10 40 00           mov esi, 0x00401000       ; &scratch
ba 04 00 00 00           mov edx, 4
0f 05                    syscall
```

**11b. Check it was 4 bytes** (6 bytes)

```
48 83 f8 04              cmp rax, 4
75 59                    jne disp_end              ; EOF or short read
```

**11c. Load the length into r14d** (8 bytes)

```
44 8b 34 25 00 10 40 00  mov r14d, [0x00401000]
```

Encoding `44 8b 34 25 disp32` is `MOV r32, r/m32` with REX.R set so the
destination is `r14d` (the high-bank register 14). `r14d` is
zero-extended into `r14`.

**11d. Read the record body into the display buffer** (15 bytes)

```
31 c0                    xor eax, eax              ; sys_read
48 89 df                 mov rdi, rbx              ; db fd
be 00 30 40 00           mov esi, 0x00403000       ; display buffer
44 89 f2                 mov edx, r14d             ; length
0f 05                    syscall
```

For a regular local file with a small request size, Linux `read(2)`
returns the full amount in one call, so there is no second-phase loop
here (unlike POC-02's `MSG_WAITALL` on a stream socket). If this
assumption ever breaks, the worst case is that a record would display
truncated; the record format on disk is unaffected.

**11e. Print the bullet** (22 bytes)

```
b8 01 00 00 00           mov eax, 1                ; sys_write
bf 01 00 00 00           mov edi, 1                ; stdout
be e2 01 40 00           mov esi, 0x004001e2       ; &bullet
ba 0d 00 00 00           mov edx, 13
0f 05                    syscall
```

Writes `"  \e[32m-\e[0m "` — two spaces, a green dash, a trailing space.

**11f. Print the record contents** (20 bytes)

```
b8 01 00 00 00           mov eax, 1                ; sys_write
bf 01 00 00 00           mov edi, 1                ; stdout
be 00 30 40 00           mov esi, 0x00403000       ; &display buffer
44 89 f2                 mov edx, r14d             ; length
0f 05                    syscall
```

**11g. Print a trailing newline** (22 bytes)

```
b8 01 00 00 00           mov eax, 1                ; sys_write
bf 01 00 00 00           mov edi, 1                ; stdout
be ef 01 40 00           mov esi, 0x004001ef       ; &newline
ba 01 00 00 00           mov edx, 1
0f 05                    syscall
```

If the record already ends in `\n` (the common case for interactive
input) this yields a double newline and visually separates entries. If
it doesn't end in `\n`, the newline ensures the next bullet starts on
its own line.

**11h. Loop back** (2 bytes)

```
eb 90                    jmp disp_top              ; -112 bytes
```

### Section 12 — close + exit (vaddr `0x40019c`, 19 bytes)

```
b8 03 00 00 00           mov eax, 3                ; sys_close
48 89 df                 mov rdi, rbx              ; fd
0f 05                    syscall

b8 3c 00 00 00           mov eax, 60               ; sys_exit
31 ff                    xor edi, edi              ; status 0
0f 05                    syscall
```

## Syscalls used

Seven direct Linux syscalls, no library code:

| #  | Name     | Purpose in this binary                                |
|----|----------|-------------------------------------------------------|
| 0  | `read`   | Drain stdin; fetch record length; fetch record body   |
| 1  | `write`  | Prompt; length prefix; record body; header; bullet… |
| 2  | `open`   | Open `notes.db` for RW, create if absent             |
| 3  | `close`  | Close the db fd on exit                              |
| 8  | `lseek`  | Seek to EOF (append) and back to 0 (read for display)|
| 60 | `exit`   | Clean exit 0                                         |

No `libc`, no `ld-linux`, no dynamic loader. The binary is fully static.

## On-disk format ("the database")

A `notes.db` file is simply the concatenation of records, each being:

```
+--------------------+------------------------+
|  length: u32 LE    |  text: length bytes    |
+--------------------+------------------------+
```

There is no schema, no index, no header — the whole file is one
append-only log. Reading from offset 0 and consuming `4 + length` bytes
at a time walks the records in order. EOF terminates the walk. This is
the smallest thing that can honestly be called "a database of some
sort".

Example: after

```bash
echo "hello"            | ./note
echo "second note here" | ./note
```

`notes.db` is exactly 31 bytes:

```
06 00 00 00  68 65 6c 6c 6f 0a
11 00 00 00  73 65 63 6f 6e 64 20 6e 6f 74 65 20 68 65 72 65 0a
```

## Known limitations (documented, not fixed)

- **2 KiB input cap.** Input beyond 2048 bytes is silently dropped; a
  future `note-v2` could grow the buffer or stream-append.
- **No record deletion / update.** Append-only. Deleting would require a
  compaction pass or a tombstone field in the length prefix.
- **No concurrency safety.** Two `note` processes running at once could
  interleave writes. `fcntl(F_SETLK)` would fix it.
- **Trailing-newline cosmetic.** Records that end with `\n` render with a
  blank line between entries; records without `\n` render tight. This is
  consistent with whatever the user typed.
- **Fixed path.** `notes.db` is resolved against the current working
  directory. Run from the same directory every time to see the same
  history.
