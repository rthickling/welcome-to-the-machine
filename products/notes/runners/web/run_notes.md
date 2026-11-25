# `products/notes/runners/web/run_notes`

`run_notes` is a **2816-byte** statically linked Linux ELF64 x86_64 helper that
serves the Notes tree on `127.0.0.1:8765` and opens the browser **test harness**
[`notes-web-runner.html`](notes-web-runner.html) so you can interactively
exercise `notes-web.wasm`. It is not a development or build tool.

This binary is host glue (outside the Notes product ISA targets), but it is
still machine code — no interpreter — so it stays on the right side of
[`docs/rules.md`](../../../../docs/rules.md). See
[`notes-web-runner.html.md`](notes-web-runner.html.md).

## Usage

```bash
./products/notes/runners/web/run_notes
```

Requirements:

- the executable must live in `products/notes/runners/web/` (it resolves its
  own path via `readlink("/proc/self/exe")`, strips the filename, then
  `chdir("../..")` into `products/notes/`)
- `/usr/bin/xdg-open` available to launch the default browser

Then browse (or let `xdg-open` open):

`http://127.0.0.1:8765/runners/web/notes-web-runner.html`

## Behaviour

1. Resolve install directory and `chdir` to `products/notes`.
2. `socket` / `setsockopt(SO_REUSEADDR)` / `bind(127.0.0.1:8765)` / `listen`.
3. Print the banner URL to stdout.
4. `fork` + `execve("/usr/bin/xdg-open", [xdg-open, url, NULL], NULL)`.
5. Accept loop:
   - `read` one HTTP request
   - require leading `GET `
   - copy path (strip leading `/`; stop at space / `?` / CR / NUL)
   - reject any `..` substring
   - `open` + `fstat` + pick `Content-Type` by suffix (`.wasm` /
     `.html` / else octet-stream)
   - write an `HTTP/1.0 200` header with `Cache-Control: no-store`, then
     `sendfile` the body; on failure write a fixed `404` page

## File layout (2816 bytes)

`mkelf` wraps a 2696-byte body at entry `0x400078`:

```text
file 0x000..0x077   120   ELF header + PT_LOAD (from mkelf)
file 0x078..0x2fe   663   code
file 0x2ff..0x7ff  1265   zero pad so data starts at body off 0x788
file 0x800..0xaff   768   literals + sockaddr + HTTP headers
BSS   0x400b00..    64KiB from mkelf (buffers below)
```

Virtual addresses:

| Vaddr        | Use                                                |
|:-------------|:---------------------------------------------------|
| `0x400078`   | code entry                                         |
| `0x400800`   | data (strings / sockaddr / headers)                |
| `0x401000`   | `readlink` path buffer                             |
| `0x401800`   | HTTP request buffer (8 KiB)                        |
| `0x403800`   | decoded relative file path                         |
| `0x403e00`   | `struct stat` (`st_size` at `+48` → `0x403e30`)    |
| `0x403f00`   | `int` one for `SO_REUSEADDR`                       |

## Data table (`0x400800`)

| Vaddr      | Contents |
|:-----------|:---------|
| `0x400800` | `/proc/self/exe\0` |
| `0x40080f` | `../..\0` |
| `0x400815` | banner (114 bytes + NUL) |
| `0x4008b0` | `sockaddr_in`: family `2`, port `htons(8765)=0x223d` → bytes `22 3d`, addr `127.0.0.1` |
| `0x4008c0` | runner URL |
| `0x400910` | `/usr/bin/xdg-open\0` |
| `0x400928` | HTTP/1.0 200 wasm header (95 bytes) |
| `0x400990` | HTTP/1.0 200 html header (88 bytes) |
| `0x4009f0` | HTTP/1.0 200 octet-stream header (103 bytes) |
| `0x400a60` | HTTP/1.0 404 + `Not Found` (98 bytes) |

## Registers in the accept loop

| Reg  | Role |
|:-----|:-----|
| `r12` | listen fd |
| `r13` | client fd |
| `r14` | file fd |
| `r15` | `st_size` for `sendfile` |
| `r8`/`r9` | header pointer / length around `write` |

## Syscalls

`readlink` (89), `chdir` (80), `socket` (41), `setsockopt` (54), `bind` (49),
`listen` (50), `write` (1), `fork` (57), `execve` (59), `exit` (60),
`accept` (43), `read` (0), `open` (2), `fstat` (5), `sendfile` (40),
`close` (3).

## Opcode walk-through (code body)

Addresses are virtual. The listing mirrors `objdump` on the raw code
region (body offset `0` = `0x400078`).

### Resolve cwd

```
400078  mov eax, 89                 ; readlink
40007d  mov edi, 0x400800           ; "/proc/self/exe"
400082  mov esi, 0x401000
400087  mov edx, 511
40008c  syscall
40008e  test rax, rax
400091  js fail                     ; → 0x400303
; strip trailing filename at last '/'
400097..4000af  scan back, write NUL at '/'
4000b2  mov eax, 80 / chdir(dirname)
4000be  mov eax, 80 / chdir("../..")
```

### Listen on 127.0.0.1:8765

```
4000ca  socket(AF_INET, SOCK_STREAM, 0) → r12
4000e0  dword [0x403f00] = 1
4000eb  setsockopt(r12, SOL_SOCKET, SO_REUSEADDR, &one, 4)
40010b  bind(r12, 0x4008b0, 16)
40011f  listen(r12, 16)
40012e  write(1, banner, 114)
```

### Fork browser

```
400144  fork
40014e  jnz accept_loop             ; parent → 0x400185
; child:
400150  push NULL / url / xdg-open
400168  execve("/usr/bin/xdg-open", argv, NULL)
400179  exit(1) if execve returns
```

### Accept / parse / serve

```
400185  accept_loop:
        accept(r12, NULL, NULL) → r13
        read(r13, 0x401800, 8192)
        js close_client
        cmp dword [0x401800], 'GET '
        jne close_client
        ; copy path to 0x403800 (skip leading '/')
        ; reject ".."
        open(path, O_RDONLY) → r14
        js send_404
        fstat(r14, 0x403e00)
        r15 = [0x403e30]            ; st_size
        ; suffix: .wasm / .html / else → header ptr + len
        write(r13, header, len)
        sendfile(r13, r14, NULL, r15)
        close(r14)
        jmp close_client
send_404:
        write(r13, 0x400a60, 98)
close_client:
        close(r13)
        jmp accept_loop
fail:
        exit(1)
```

MIME selection jumps must land on instruction starts:

- `.wasm` match → header `0x400928` / len `0x5f`, then write path
- `.html` match → header `0x400990` / len `0x58`
- else → header `0x4009f0` / len `0x67`

## Source of truth

The runnable file [`run_notes`](run_notes) **is** the source. Edit it in place
(for example with `xxd` / `dd` / a hex editor). There is no separate `.hex`
source, and no compile step that produces this binary from text.

To inspect: `xxd run_notes`, `objdump -d -b binary -m i386:x86-64` on the
load body (skip the 120-byte `mkelf` header), or single-step from the walk-
through above. Optional re-wrap of a modified body: pipe raw body bytes
through [`tools/mkelf/mkelf`](../../../../tools/mkelf/mkelf.md).

## Relationship to the product

- Product target: [`notes-web.wasm`](../../targets/wasm/notes-web.wasm.md)
- Browser page: [`notes-web-runner.html`](notes-web-runner.html)
- This helper only hosts those files; it does not participate in the Notes
  UI/ISA contract beyond serving bytes with the right MIME type.
