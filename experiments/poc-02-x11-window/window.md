# `poc-02/window` — Hand-Hexed X11 Window

A 696-byte statically-linked Linux ELF64 x86_64 executable. No `libc`, no
assembler, no linker: every byte was typed into a hex string and materialised
with `xxd -r -p`. The program:

1. Opens a Unix-domain stream socket.
2. Connects to the X server at `/tmp/.X11-unix/X1` (the user's `DISPLAY=:1`).
3. Performs the X11 handshake using a hard-coded MIT-MAGIC-COOKIE-1.
4. Reads the setup response in two `recvfrom(MSG_WAITALL)` calls to drain the
   full ~6.7 KiB reply reliably.
5. Parses `resource-id-base`, `root` window id and `root_visual` out of the
   response.
6. Sends `CreateWindow` (400x300, dark-blue background, ButtonPress events
   enabled).
7. Sends `MapWindow` (makes it visible).
8. Opens/creates `status.log` (append mode, 0644), writes `opened\n`.
9. Blocks on `read()` of the X socket until one 32-byte event arrives
   (e.g. the user clicks inside the window).
10. Writes `event\n` to `status.log` and exits.

No dynamic libraries are linked; everything is raw Linux syscalls. Five
templates live in the data section and are patched at runtime with
server-supplied ids.

## Usage

```bash
./window          # opens the window, blocks until a click
cat status.log    # → "opened\nevent\n"
```

`DISPLAY` must be `:1` and the `MIT-MAGIC-COOKIE-1` for that display must
match the cookie hard-coded into this binary. Rebuild is needed whenever the
cookie rotates (i.e. typically on every login).

## File layout (696 bytes)

| File offset | Size | Vaddr | Contents                                    |
|------------:|-----:|:------|:--------------------------------------------|
| `0x000`     | 64   | `0x400000` | ELF64 header                           |
| `0x040`     | 56   | `0x400040` | Program header (single `PT_LOAD`, R+X) |
| `0x078`     | 328  | `0x400078` | Executable code — success path         |
| `0x1c0`     | 12   | `0x4001c0` | Executable code — failure path `exit(1)` |
| `0x1cc`     | 18   | `0x4001cc` | `sockaddr_un` (AF_UNIX + path)         |
| `0x1de`     | 92   | `0x4001de` | zero padding (sockaddr_un is 110 bytes)|
| `0x23a`     | 48   | `0x40023a` | X11 setup request + cookie             |
| `0x26a`     | 40   | `0x40026a` | `CreateWindow` request template        |
| `0x292`     | 8    | `0x400292` | `MapWindow` request template           |
| `0x29a`     | 24   | `0x40029a` | strings `"status.log\0opened\nevent\n"`|

Beyond the file (`0x2b8` .. `0x3000` in memory) lies BSS: a 9.4 KiB
zero-filled buffer for the X11 setup response and later for event reads.
This is what makes `p_memsz > p_filesz` in the program header.

## ELF64 header — bytes `0x00`–`0x3F`

```
7f 45 4c 46   e_ident[MAG]       "\x7fELF"
02            EI_CLASS           ELFCLASS64
01            EI_DATA            little-endian
01            EI_VERSION         1
00            EI_OSABI           System V
00            EI_ABIVERSION
00 00 00 00 00 00 00             padding
02 00         e_type             ET_EXEC
3e 00         e_machine          EM_X86_64
01 00 00 00   e_version          1
78 00 40 00 00 00 00 00          e_entry   = 0x0000000000400078
40 00 00 00 00 00 00 00          e_phoff   = 64
00 00 00 00 00 00 00 00          e_shoff   = 0 (no sections)
00 00 00 00   e_flags
40 00         e_ehsize   = 64
38 00         e_phentsize= 56
01 00         e_phnum    = 1
00 00         e_shentsize= 0
00 00         e_shnum    = 0
00 00         e_shstrndx = 0
```

## Program header — bytes `0x40`–`0x77`

```
01 00 00 00   p_type    PT_LOAD
07 00 00 00   p_flags   R | W | X (0x7 — we write into data templates)
00 00 00 00 00 00 00 00          p_offset = 0
00 00 40 00 00 00 00 00          p_vaddr  = 0x400000
00 00 40 00 00 00 00 00          p_paddr  = 0x400000
b8 02 00 00 00 00 00 00          p_filesz = 0x2b8  (up to end of strings)
00 30 00 00 00 00 00 00          p_memsz  = 0x3000 (12 KiB, BSS extension)
00 10 00 00 00 00 00 00          p_align  = 0x1000
```

`p_memsz - p_filesz` = 0x2d48 bytes of zero-filled memory at
`[0x4002b8, 0x403000)` used as the recv buffer. `W` is set in `p_flags`
because the code patches the `CreateWindow`/`MapWindow` templates at runtime
(the wid, parent, and visual fields) before sending them.

## Code — success path (`0x078`–`0x1BF`)

All numeric values below are little-endian in memory; operand lengths match
the AMD64 encoding tables.

### 1. Pre-load `MSG_WAITALL` into `r10d`

```
78:  41 ba 00 01 00 00         mov r10d, 0x00000100   ; MSG_WAITALL
```

Syscall ABI on Linux/x86_64 places the 4th argument in `r10` (not `rcx`, which
`syscall` itself clobbers). We set this once and rely on it being preserved
across every later syscall (the kernel doesn't touch callee-save registers).

### 2. `socket(AF_UNIX, SOCK_STREAM, 0)` — syscall 41

```
7e:  b8 29 00 00 00            mov eax, 41           ; __NR_socket
83:  bf 01 00 00 00            mov edi, 1            ; AF_UNIX
88:  be 01 00 00 00            mov esi, 1            ; SOCK_STREAM
8d:  31 d2                     xor edx, edx          ; protocol = 0
8f:  0f 05                     syscall
91:  48 89 c3                  mov rbx, rax          ; save sockfd in rbx
```

`rbx` is callee-preserved and holds the sockfd from here on. No error check:
if it fails, subsequent syscalls fail and the process ultimately crashes or
exits. This is a POC, not production code.

### 3. `connect(sockfd, &sockaddr, 110)` — syscall 42

```
94:  b8 2a 00 00 00            mov eax, 42           ; __NR_connect
99:  48 89 df                  mov rdi, rbx          ; sockfd
9c:  be cc 01 40 00            mov esi, 0x004001cc   ; &sockaddr_un
a1:  ba 6e 00 00 00            mov edx, 110          ; sizeof(sockaddr_un)
a6:  0f 05                     syscall
```

The sockaddr_un at `0x4001cc` is `0x0001` (AF_UNIX) followed by the null-
terminated path `/tmp/.X11-unix/X1`, then zero-padded up to the full 110
bytes that `sockaddr_un` requires.

### 4. `write(sockfd, &setup_req, 48)` — syscall 1

```
a8:  b8 01 00 00 00            mov eax, 1            ; __NR_write
ad:  48 89 df                  mov rdi, rbx
b0:  be 3a 02 40 00            mov esi, 0x0040023a   ; setup request template
b5:  ba 30 00 00 00            mov edx, 48           ; 12 + 20 + 16
ba:  0f 05                     syscall
```

Sends the handshake (byte-order, protocol version, auth name, cookie). The
template is described in the data section below.

### 5. `recvfrom(sockfd, &buf, 8, MSG_WAITALL, 0, 0)` — syscall 45

This reads **only the 8-byte response header**. Stream sockets can return
short reads; `MSG_WAITALL` forces the kernel to wait until all 8 bytes are
available.

```
bc:  b8 2d 00 00 00            mov eax, 45           ; __NR_recvfrom
c1:  48 89 df                  mov rdi, rbx
c4:  be b8 02 40 00            mov esi, 0x004002b8   ; header buffer (BSS)
c9:  ba 08 00 00 00            mov edx, 8
ce:  0f 05                     syscall
                               ; r10 = MSG_WAITALL (preserved from step 1)
                               ; r8, r9 = 0 (inherited, fine for NULL addr/len)
```

### 6. Check `status` byte

```
d0:  80 3e 01                  cmp byte [rsi], 1     ; 1 = success
d3:  0f 85 e7 00 00 00         jne rel32 → 0x001c0   ; fail → exit(1)
```

If the X server rejected auth or protocol, byte 0 of the response is either
`0` (failure) or `2` (authenticate required); only `1` is "success".

### 7. Compute remaining length and read the body

Bytes 6–7 of the X11 setup response are the "additional data length" in
4-byte units. We multiply by 4 and issue a second `recvfrom`:

```
d9:  0f b7 56 06               movzx edx, word [rsi+6]
dd:  c1 e2 02                  shl edx, 2            ; * 4
e0:  b8 2d 00 00 00            mov eax, 45           ; __NR_recvfrom
e5:  48 89 df                  mov rdi, rbx
e8:  be c0 02 40 00            mov esi, 0x004002c0   ; body buffer (BSS)
ed:  0f 05                     syscall
```

On the test machine this returns exactly **6732 bytes**, completing the
~6740-byte setup response. The sanity of the socket state is critical: any
leftover bytes would be misinterpreted as a 32-byte X11 event later.

### 8. Parse `resource-id-base`, locate the screens array

The body layout starts at offset 0 with 24 fields documented in
[X11 Protocol §8](https://www.x.org/releases/X11R7.7/doc/xproto/x11protocol.html#Connection_Setup):

```
e.f:  44 8b 66 04              mov r12d, [rsi+4]     ; resource-id-base
f3:  0f b7 46 10               movzx eax, word [rsi+16]  ; vendor length
f7:  0f b6 4e 15               movzx ecx, byte [rsi+21]  ; num pixmap formats
fb:  83 c0 03                  add eax, 3
fe:  83 e0 fc                  and eax, ~3           ; round up vendor len
101: c1 e1 03                  shl ecx, 3            ; formats * 8 bytes each
104: 01 c8                     add eax, ecx
106: 83 c0 20                  add eax, 32           ; fixed-size prefix
109: 48 01 c6                  add rsi, rax          ; rsi → screens[0]
10c: 44 8b 2e                  mov r13d, [rsi]       ; screen.root
10f: 44 8b 76 20                mov r14d, [rsi+32]   ; screen.root_visual
```

- `r12` = resource-id-base (e.g. `0x04000000`): we OR `1` into it to get our
  window id `0x04000001`.
- `r13` = root window id (e.g. `0x000003fd`): the parent of our new window.
- `r14` = root visual id (e.g. `0x00000021`): the visual we inherit.

All three are callee-preserved, so they survive the upcoming syscalls.

### 9. Patch the `CreateWindow` template in place

```
113: 44 89 e0                  mov eax, r12d
116: 83 c8 01                  or eax, 1             ; wid = base | 1
119: 89 04 25 6e 02 40 00      mov [0x40026e], eax   ; CreateWindow.wid
120: 44 89 2c 25 72 02 40 00   mov [0x400272], r13d  ; CreateWindow.parent
128: 44 89 34 25 82 02 40 00   mov [0x400282], r14d  ; CreateWindow.visual
```

The addressing mode `[disp32]` requires the SIB byte `0x25` (no base, no
index, scale 1) — that's why each store is 7–8 bytes long. This is the
whole reason `p_flags` includes `W`: these stores hit the read-only part of
our own binary.

### 10. `write(sockfd, &create_window, 40)`

```
130: b8 01 00 00 00            mov eax, 1
135: 48 89 df                  mov rdi, rbx
138: be 6a 02 40 00            mov esi, 0x0040026a
13d: ba 28 00 00 00            mov edx, 40
142: 0f 05                     syscall
```

### 11. Patch and send `MapWindow`

```
144: 44 89 e0                  mov eax, r12d
147: 83 c8 01                  or eax, 1             ; same wid
14a: 89 04 25 96 02 40 00      mov [0x400296], eax   ; MapWindow.wid
151: b8 01 00 00 00            mov eax, 1
156: 48 89 df                  mov rdi, rbx
159: be 92 02 40 00            mov esi, 0x00400292
15e: ba 08 00 00 00            mov edx, 8
163: 0f 05                     syscall
```

At this point the X server displays the window.

### 12. `open("status.log", O_WRONLY|O_CREAT|O_APPEND, 0644)` — syscall 2

```
165: b8 02 00 00 00            mov eax, 2            ; __NR_open
16a: bf 9a 02 40 00             mov edi, 0x0040029a  ; "status.log"
16f: be 41 04 00 00             mov esi, 0x00000441  ; O_WRONLY|O_CREAT|O_APPEND
174: ba a4 01 00 00             mov edx, 0x000001a4  ; mode 0644
179: 0f 05                     syscall
17b: 48 89 c5                  mov rbp, rax          ; status.log fd → rbp
```

`rbp` is callee-preserved and holds the log fd for the rest of the program.

### 13. `write(logfd, "opened\n", 7)`

```
17e: b8 01 00 00 00            mov eax, 1
183: 48 89 ef                  mov rdi, rbp
186: be a5 02 40 00            mov esi, 0x004002a5   ; "opened\n"
18b: ba 07 00 00 00            mov edx, 7
190: 0f 05                     syscall
```

### 14. `read(sockfd, &buf, 32)` — wait for one X11 event

```
192: 31 c0                     xor eax, eax          ; __NR_read = 0
194: 48 89 df                  mov rdi, rbx
197: be b8 22 40 00            mov esi, 0x004022b8   ; distinct 32-byte slot
19c: ba 20 00 00 00            mov edx, 32           ; one event is 32 bytes
1a1: 0f 05                     syscall
```

The event buffer lives at `0x4022b8`, offset `+0x2000` from the setup-response
buffer, so that the parsed setup response at `0x4002c0` cannot be corrupted
by this read. Both addresses are inside the BSS region that the program
header pre-allocated.

Every X11 event (KeyPress, ButtonPress, Expose, MappingNotify, Error, …) is
exactly 32 bytes. We accept any of them; the first event to arrive unblocks
us. In practice, because our `CreateWindow` event-mask is `0x00000004`
(ButtonPress only), we wake up on the first click the user makes inside the
window.

### 15. `write(logfd, "event\n", 6)` and `exit(0)`

```
1a3: b8 01 00 00 00            mov eax, 1
1a8: 48 89 ef                  mov rdi, rbp
1ab: be ac 02 40 00            mov esi, 0x004002ac   ; "event\n"
1b0: ba 06 00 00 00            mov edx, 6
1b5: 0f 05                     syscall
1b7: b8 3c 00 00 00            mov eax, 60           ; __NR_exit
1bc: 31 ff                     xor edi, edi          ; status = 0
1be: 0f 05                     syscall
```

`close()` is intentionally omitted — Linux releases all fds on process exit.

## Code — failure path (`0x1C0`–`0x1CB`)

Reached only when the X server's handshake status byte is not `1`.

```
1c0: b8 3c 00 00 00            mov eax, 60           ; __NR_exit
1c5: bf 01 00 00 00            mov edi, 1            ; status = 1
1ca: 0f 05                     syscall
```

## Data — `sockaddr_un` at `0x1CC`

```
1cc: 01 00                                           ; sa_family = AF_UNIX
1ce: 2f 74 6d 70 2f 2e 58 31 31 2d 75 6e 69 78 2f 58 31 00   ; "/tmp/.X11-unix/X1\0"
1e0: 00 … 00                                        ; zero padding to 110 bytes
```

## Data — X11 setup request at `0x23A`

The handshake message (see X11 §8.1):

```
23a: 6c                                              ; byte-order = 'l' (LSB first)
23b: 00                                              ; unused
23c: 0b 00                                           ; protocol major = 11
23e: 00 00                                           ; protocol minor = 0
240: 12 00                                           ; authorization-protocol-name length = 18
242: 10 00                                           ; authorization-protocol-data length = 16
244: 00 00                                           ; unused
246: 4d 49 54 2d 4d 41 47 49 43 2d 43 4f 4f 4b 49 45 2d 31    ; "MIT-MAGIC-COOKIE-1"
258: 00 00                                           ; pad to 4 bytes
25a: 66 cb 9f 93 04 50 c3 25 c0 b8 d5 ff ad c9 34 86 ; hard-coded cookie (16 bytes)
```

Total 48 bytes. The cookie is captured at build time from
`~/.Xauthority` (or `/run/user/$UID/gdm/Xauthority` under GDM). It is
session-bound: on reboot / re-login the X server rotates the cookie and
this binary must be rebuilt.

## Data — `CreateWindow` template at `0x26A`

```
26a: 01                                              ; opcode = CreateWindow
26b: 00                                              ; depth = CopyFromParent
26c: 0a 00                                           ; request length = 10 (×4 = 40 bytes)
26e: 00 00 00 00                                     ; wid      — patched → r12|1
272: 00 00 00 00                                     ; parent   — patched → r13 (root)
276: 00 00                                           ; x = 0
278: 00 00                                           ; y = 0
27a: 90 01                                           ; width  = 400
27c: 2c 01                                           ; height = 300
27e: 00 00                                           ; border-width = 0
280: 01 00                                           ; class = InputOutput
282: 00 00 00 00                                     ; visual — patched → r14
286: 02 08 00 00                                     ; value-mask = CWBackPixel|CWEventMask
28a: 88 00 00 00                                     ; background-pixel = 0x88 (dark blue-ish)
28e: 04 00 00 00                                     ; event-mask = ButtonPress
```

Value-mask bits: `0x00000002` = `CWBackPixel`, `0x00000800` = `CWEventMask`.
Values follow in ascending bit order. Because `CWEventMask` is the *only*
event bit selected, only `ButtonPress` events reach us — no `Expose`, no
`KeyPress`, no `MotionNotify`. That's enough for this POC.

Background pixel `0x88` is a raw pixel value, not RGB: it gets interpreted
by the root visual. On the test machine the visual is TrueColor with red
mask `0xff0000`, green `0xff00`, blue `0xff` — so `0x88` is a dark blue.

## Data — `MapWindow` template at `0x292`

```
292: 08                                              ; opcode = MapWindow
293: 00                                              ; unused
294: 02 00                                           ; request length = 2 (×4 = 8 bytes)
296: 00 00 00 00                                     ; wid — patched → r12|1
```

## Data — strings at `0x29A`

```
29a: 73 74 61 74 75 73 2e 6c 6f 67 00       ; "status.log\0"
2a5: 6f 70 65 6e 65 64 0a                    ; "opened\n"
2ac: 65 76 65 6e 74 0a                       ; "event\n"
```

## BSS — response buffer at `0x4002B8`

Not on disk. The program header's `p_memsz = 0x3000` extends the loaded
segment to `0x403000`, leaving `[0x4002b8, 0x403000)` = 11.3 KiB of
zero-initialised memory. The first 8 bytes hold the X11 setup-response
header; bytes 8..(8+6732) hold the body (the screens/visuals/formats table
that tells us the root window and root visual).

The event read at step 14 uses a distinct address (`0x4022b8`, still inside
the BSS region) so that the parsed setup response in `[0x4002c0, 0x401d2c)`
is left untouched — even though the code no longer references it, the
separation is cheap and makes debugging easier.

## Linux x86_64 syscall interface

No libraries are linked. All kernel calls use the documented
[x86_64 syscall ABI](https://chromium.googlesource.com/chromiumos/docs/+/HEAD/constants/syscalls.md):

| Register | Meaning          |
|:--------:|:-----------------|
| `rax`    | syscall number, then return value |
| `rdi`    | arg 1            |
| `rsi`    | arg 2            |
| `rdx`    | arg 3            |
| `r10`    | arg 4            |
| `r8`     | arg 5            |
| `r9`     | arg 6            |
| `rcx`, `r11` | **clobbered** by the `syscall` instruction itself |

Calls used and their man pages:

| # (rax) | Name       | Reference         |
|--------:|:-----------|:------------------|
| 0       | `read`     | `man 2 read`      |
| 1       | `write`    | `man 2 write`     |
| 2       | `open`     | `man 2 open`      |
| 41      | `socket`   | `man 2 socket`    |
| 42      | `connect`  | `man 2 connect`   |
| 45      | `recvfrom` | `man 2 recvfrom`  |
| 60      | `exit`     | `man 2 exit`      |

## X11 wire protocol references

- Overall: <https://www.x.org/releases/X11R7.7/doc/xproto/x11protocol.html>
- Connection setup (§8): handshake format and response layout.
- `CreateWindow` (§9): opcode 1, 32 + 4*n bytes.
- `MapWindow`  (§9): opcode 8, 8 bytes fixed.
- Events (§11): 32-byte fixed record; byte 0 is the event code (2 =
  KeyPress, 4 = ButtonPress, 12 = Expose, …).

The cookie authentication is MIT-MAGIC-COOKIE-1 (see `man Xsecurity`): the
server compares the 16-byte value in the setup request against the cookie
in its `~/.Xauthority`-equivalent file.

## Why two `recvfrom` calls with `MSG_WAITALL`?

Unix-domain stream sockets do **not** guarantee message boundaries. A single
`read()` for the entire ~6.7 KiB setup response would routinely return a
short read (often exactly 4096 bytes on this kernel), leaving 2644 bytes
buffered. The next `read()` — intended to receive a 32-byte event — would
instead return the leftover setup bytes, which the binary would parse as a
garbage event.

`MSG_WAITALL` tells `recvfrom` to block until the requested number of bytes
has been delivered (or EOF). Splitting into a fixed 8-byte header read and
a length-parameterised body read lets us drain the entire response in
exactly two syscalls without ever knowing the total size up front.

## Building

The binary is produced directly from the hex string in this directory's
build log (not included here; regenerate with `xxd -r -p`). No compiler, no
assembler, no linker. The only build-time tool is `xxd`.

## Tested on

- Ubuntu 24.04.4 LTS, kernel 6.17.0-22-generic
- X.Org server running on `DISPLAY=:1`
- AMD Ryzen 7 PRO 7840U (x86_64)
