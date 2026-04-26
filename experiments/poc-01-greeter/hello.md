# `poc-01/hello` - Byte-by-Byte Explanation

## What it does

`hello` is a 429-byte statically-linked Linux ELF64 executable for x86_64. It:

1. **Takes user input** - reads a line from `stdin` (syscall `read`).
2. **Shows graphical output** - writes coloured ANSI escape sequences to `stdout`, drawing a yellow `+===...+` banner around a green `Hello, <name>!` line. This is the "graphical" output for this POC (coloured terminal rendering); future POCs on this platform will target X11 / framebuffer directly.
3. **Stores data** - opens `greeting.txt` in the current working directory with `O_WRONLY | O_CREAT | O_TRUNC` mode `0644`, writes the raw input to it, and closes it.

It makes 7 direct Linux x86_64 syscalls: `write`, `read`, `open`, `write`, `close`, `write`, `write`, `exit`. It is **not** linked against libc - no shared libraries, no dynamic loader, no interpreter. It contains no section headers (the kernel does not need them to run an executable), only one `PT_LOAD` program header.

## Target platform and ABI

| Property | Value |
|---|---|
| Format | ELF64 (little-endian) |
| Machine | x86_64 (EM_X86_64 = 0x3E) |
| Type | `ET_EXEC` (statically linked, fixed load address) |
| OS/ABI | System V (0x00) |
| Load address | `0x400000` |
| Entry point | `0x400078` |
| Page size assumed | 4096 (`p_align = 0x1000`) |

### x86_64 Linux syscall convention (used throughout)

| Register | Role |
|---|---|
| `rax` | syscall number (and return value) |
| `rdi` | arg 1 |
| `rsi` | arg 2 |
| `rdx` | arg 3 |
| `r10` | arg 4 |
| `r8`  | arg 5 |
| `r9`  | arg 6 |
| `rcx`, `r11` | **clobbered** by `syscall` |
| everything else | **preserved** across `syscall` |

The syscall instruction is `0F 05` (2 bytes). Syscall numbers used here:

| Name | # | Description |
|---|---|---|
| `read`  |  0 | `ssize_t read(int fd, void *buf, size_t count)` |
| `write` |  1 | `ssize_t write(int fd, const void *buf, size_t count)` |
| `open`  |  2 | `int open(const char *pathname, int flags, mode_t mode)` |
| `close` |  3 | `int close(int fd)` |
| `exit`  | 60 | `_Noreturn void _exit(int status)` (low byte of `rdi`) |

Because this executable is not linked against any library, there are no external interfaces to document other than the kernel syscall ABI above.

## File layout (429 bytes = `0x1AD`)

```
Offset      Size  Contents
0x000..0x03F  64  ELF64 file header
0x040..0x077  56  Program header (single PT_LOAD, R+W+X)
0x078..0x120 169  Executable code (entry point = 0x078 / VA 0x400078)
0x121..0x13C  28  prompt string     ("\x1b[1;36mEnter your name: \x1b[0m")
0x13D..0x149  13  filename string   ("greeting.txt\0")
0x14A..0x17F  54  greet1 string     (top banner + "\x1b[1;32mHello, ")
0x180..0x1AC  45  greet2 string     ("!\x1b[0m" + bottom banner)
```

The program header asks the kernel to map 557 bytes (`p_memsz = 0x22D`) while the file is only 429 bytes (`p_filesz = 0x1AD`). The extra 128 bytes past end-of-file are zero-filled by the kernel and used as the writable input buffer at virtual address `0x4001AD`.

---

## 1. ELF64 file header - 64 bytes at offset `0x00`

Raw bytes:

```
0x00: 7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
0x10: 02 00 3e 00 01 00 00 00 78 00 40 00 00 00 00 00
0x20: 40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
0x30: 00 00 00 00 40 00 38 00 01 00 00 00 00 00 00 00
```

Decoded:

| Offset | Bytes | Field | Meaning |
|---|---|---|---|
| 0x00 | `7f 45 4c 46` | `e_ident[0..3]` | Magic `\x7FELF` |
| 0x04 | `02` | `EI_CLASS`    | `ELFCLASS64` |
| 0x05 | `01` | `EI_DATA`     | `ELFDATA2LSB` (little-endian) |
| 0x06 | `01` | `EI_VERSION`  | `EV_CURRENT` |
| 0x07 | `00` | `EI_OSABI`    | System V |
| 0x08 | `00` | `EI_ABIVERSION` | 0 |
| 0x09..0x0F | zeros | padding | reserved |
| 0x10 | `02 00` | `e_type` | `ET_EXEC` (executable) |
| 0x12 | `3e 00` | `e_machine` | `EM_X86_64` (62) |
| 0x14 | `01 00 00 00` | `e_version` | 1 |
| 0x18 | `78 00 40 00 00 00 00 00` | `e_entry` | `0x0000000000400078` - entry point |
| 0x20 | `40 00 00 00 00 00 00 00` | `e_phoff` | program headers at file offset `0x40` |
| 0x28 | `00 00 00 00 00 00 00 00` | `e_shoff` | no section headers |
| 0x30 | `00 00 00 00` | `e_flags` | 0 |
| 0x34 | `40 00` | `e_ehsize` | 64 |
| 0x36 | `38 00` | `e_phentsize` | 56 |
| 0x38 | `01 00` | `e_phnum` | 1 program header |
| 0x3A | `00 00` | `e_shentsize` | 0 |
| 0x3C | `00 00` | `e_shnum` | 0 |
| 0x3E | `00 00` | `e_shstrndx` | 0 |

## 2. Program header - 56 bytes at offset `0x40`

Raw bytes:

```
0x40: 01 00 00 00 07 00 00 00 00 00 00 00 00 00 00 00
0x50: 00 00 40 00 00 00 00 00 00 00 40 00 00 00 00 00
0x60: ad 01 00 00 00 00 00 00 2d 02 00 00 00 00 00 00
0x70: 00 10 00 00 00 00 00 00
```

Decoded:

| Offset | Bytes | Field | Meaning |
|---|---|---|---|
| 0x40 | `01 00 00 00` | `p_type`   | `PT_LOAD` |
| 0x44 | `07 00 00 00` | `p_flags`  | `PF_R \| PF_W \| PF_X` (readable, writable, executable) |
| 0x48 | `00..00`      | `p_offset` | map from file offset 0 |
| 0x50 | `00 00 40 00 00 00 00 00` | `p_vaddr` | to virtual address `0x400000` |
| 0x58 | `00 00 40 00 00 00 00 00` | `p_paddr` | (unused on Linux, set same as vaddr) |
| 0x60 | `ad 01 00 00 00 00 00 00` | `p_filesz` | 429 bytes from file |
| 0x68 | `2d 02 00 00 00 00 00 00` | `p_memsz`  | 557 bytes in memory (extra 128 zeroed by kernel = our scratch buffer) |
| 0x70 | `00 10 00 00 00 00 00 00` | `p_align`  | `0x1000` (4 KiB) |

Kernel constraint satisfied: `p_vaddr % p_align == p_offset % p_align` (both `0`).

Because the single segment is R+W+X, the entire loaded image (code and data alike) is writable and executable. That is fine for a minimal POC; a production build would split into separate PT_LOAD segments.

## 3. Executable code - 169 bytes at offset `0x78` (VA `0x400078`)

The entry point is `0x400078`. Execution begins with the first `mov` below. Across the whole program we use two registers for state that are preserved across `syscall`:

- `rbx` - number of bytes that were read from `stdin` (so we know how many to write to the file and echo back).
- `rbp` - file descriptor returned by `open("greeting.txt", ...)`.

All five `mov r32, imm32` opcodes (`B8`/`BF`/`BE`/`BA`...) **zero-extend to the full 64-bit register**, so loading a 32-bit value suffices whenever the target is `<= 0x7FFFFFFF`. This keeps the code 2 bytes shorter per move than a full `REX.W + mov imm64` would.

### 3.1 Write the prompt - `0x078..0x08D` (22 bytes)

Call: `write(1, 0x400121, 28)`.

| VA | Bytes | Mnemonic | Notes |
|---|---|---|---|
| 0x400078 | `b8 01 00 00 00` | `mov eax, 1`          | syscall nr = `write` |
| 0x40007D | `bf 01 00 00 00` | `mov edi, 1`          | fd = `stdout` |
| 0x400082 | `be 21 01 40 00` | `mov esi, 0x00400121` | buf = prompt string |
| 0x400087 | `ba 1c 00 00 00` | `mov edx, 28`         | count = 28 bytes |
| 0x40008C | `0f 05`          | `syscall`             | returns 28 in `rax` |

The string at `0x400121` is `\x1b[1;36mEnter your name: \x1b[0m` - ANSI "bold cyan" around the prompt text, then reset. If stdout is a terminal this renders as bold cyan; if piped elsewhere the escape codes pass through as literal bytes.

### 3.2 Read input from stdin - `0x08E..0x0A0` (19 bytes)

Call: `read(0, 0x4001AD, 128)`.

| VA | Bytes | Mnemonic | Notes |
|---|---|---|---|
| 0x40008E | `31 c0`          | `xor eax, eax`         | syscall nr = 0 (`read`) |
| 0x400090 | `31 ff`          | `xor edi, edi`         | fd = 0 (`stdin`) |
| 0x400092 | `be ad 01 40 00` | `mov esi, 0x004001AD`  | buf = input buffer (kernel-zeroed memory past file end) |
| 0x400097 | `ba 80 00 00 00` | `mov edx, 128`         | max 128 bytes |
| 0x40009C | `0f 05`          | `syscall`              | `rax` = bytes read (including trailing `\n`) |
| 0x40009E | `48 89 c3`       | `mov rbx, rax`         | save count in `rbx` (preserved across all later syscalls) |

`xor REG, REG` is a 2-byte idiom that clears the whole 64-bit register (equivalent to `mov reg, 0` but shorter).

### 3.3 Open `greeting.txt` for writing - `0x0A1..0x0B9` (25 bytes)

Call: `open("greeting.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644)`.

| VA | Bytes | Mnemonic | Notes |
|---|---|---|---|
| 0x4000A1 | `b8 02 00 00 00` | `mov eax, 2`          | syscall nr = `open` |
| 0x4000A6 | `bf 3d 01 40 00` | `mov edi, 0x0040013D` | pathname = "greeting.txt\0" |
| 0x4000AB | `be 41 02 00 00` | `mov esi, 0x241`      | flags: `O_WRONLY(1) \| O_CREAT(0x40) \| O_TRUNC(0x200)` |
| 0x4000B0 | `ba a4 01 00 00` | `mov edx, 0x1A4`      | mode = `0644` octal = 420 decimal |
| 0x4000B5 | `0f 05`          | `syscall`             | `rax` = fd on success, negative errno on failure |
| 0x4000B7 | `48 89 c5`       | `mov rbp, rax`        | save fd in `rbp` |

For a first POC we do not branch on error. If `open` fails, the subsequent `write(-errno, ...)` and `close(-errno)` will themselves return errors and be ignored; the banner still prints.

### 3.4 Write the input to the file - `0x0BA..0x0CB` (18 bytes)

Call: `write(fd, 0x4001AD, bytes_read)`.

| VA | Bytes | Mnemonic | Notes |
|---|---|---|---|
| 0x4000BA | `b8 01 00 00 00` | `mov eax, 1`          | syscall nr = `write` |
| 0x4000BF | `48 89 ef`       | `mov rdi, rbp`        | fd = saved file descriptor |
| 0x4000C2 | `be ad 01 40 00` | `mov esi, 0x004001AD` | same input buffer |
| 0x4000C7 | `48 89 da`       | `mov rdx, rbx`        | length = saved read count |
| 0x4000CA | `0f 05`          | `syscall`             | file now contains the input verbatim |

### 3.5 Close the file - `0x0CC..0x0D5` (10 bytes)

Call: `close(fd)`.

| VA | Bytes | Mnemonic | Notes |
|---|---|---|---|
| 0x4000CC | `b8 03 00 00 00` | `mov eax, 3`   | syscall nr = `close` |
| 0x4000D1 | `48 89 ef`       | `mov rdi, rbp` | fd |
| 0x4000D4 | `0f 05`          | `syscall`      | |

### 3.6 Write the banner top + "Hello, " - `0x0D6..0x0EB` (22 bytes)

Call: `write(1, 0x40014A, 54)`.

| VA | Bytes | Mnemonic | Notes |
|---|---|---|---|
| 0x4000D6 | `b8 01 00 00 00` | `mov eax, 1`          | `write` |
| 0x4000DB | `bf 01 00 00 00` | `mov edi, 1`          | stdout |
| 0x4000E0 | `be 4a 01 40 00` | `mov esi, 0x0040014A` | greet1 buffer |
| 0x4000E5 | `ba 36 00 00 00` | `mov edx, 54`         | 54 bytes |
| 0x4000EA | `0f 05`          | `syscall`             | |

The string is `"\n" + "\x1b[1;33m+=========================+\x1b[0m" + "\n" + "\x1b[1;32mHello, "` - bold yellow banner, reset, newline, then switch to bold green and start the greeting.

### 3.7 Echo the name (without trailing newline) - `0x0EC..0x101` (22 bytes)

Call: `write(1, 0x4001AD, bytes_read - 1)`.

| VA | Bytes | Mnemonic | Notes |
|---|---|---|---|
| 0x4000EC | `ff cb`          | `dec ebx`             | strip the `\n` that `read` captured |
| 0x4000EE | `b8 01 00 00 00` | `mov eax, 1`          | `write` |
| 0x4000F3 | `bf 01 00 00 00` | `mov edi, 1`          | stdout |
| 0x4000F8 | `be ad 01 40 00` | `mov esi, 0x004001AD` | the input buffer |
| 0x4000FD | `48 89 da`       | `mov rdx, rbx`        | length = (bytes_read - 1) |
| 0x400100 | `0f 05`          | `syscall`             | |

Edge case: if the user presses `Ctrl-D` immediately (`bytes_read == 0`) then `dec ebx` wraps `rbx` to `0xFFFFFFFF`, which will make this `write` fail (or truncate). Future versions will add a `test rbx, rbx / jz` guard.

### 3.8 Write `!` + bottom banner - `0x102..0x117` (22 bytes)

Call: `write(1, 0x400180, 45)`.

| VA | Bytes | Mnemonic | Notes |
|---|---|---|---|
| 0x400102 | `b8 01 00 00 00` | `mov eax, 1`          | `write` |
| 0x400107 | `bf 01 00 00 00` | `mov edi, 1`          | stdout |
| 0x40010C | `be 80 01 40 00` | `mov esi, 0x00400180` | greet2 buffer |
| 0x400111 | `ba 2d 00 00 00` | `mov edx, 45`         | 45 bytes |
| 0x400116 | `0f 05`          | `syscall`             | |

The string is `"!" + "\x1b[0m" + "\n" + "\x1b[1;33m+=========================+\x1b[0m" + "\n"` - closes the greeting with `!`, resets colour, newline, bottom banner, newline.

### 3.9 Exit - `0x118..0x120` (9 bytes)

Call: `_exit(0)`.

| VA | Bytes | Mnemonic | Notes |
|---|---|---|---|
| 0x400118 | `b8 3c 00 00 00` | `mov eax, 60`  | syscall nr = `exit` |
| 0x40011D | `31 ff`          | `xor edi, edi` | status = 0 |
| 0x40011F | `0f 05`          | `syscall`      | does not return |

## 4. Data section - 140 bytes at `0x121..0x1AC`

All strings are raw UTF-8/ASCII; the ANSI colour sequences are embedded literally.

### `prompt` at `0x400121`, 28 bytes

```
1b 5b 31 3b 33 36 6d                                 ESC [ 1 ; 3 6 m  (bold cyan)
45 6e 74 65 72 20 79 6f 75 72 20 6e 61 6d 65 3a 20   "Enter your name: "
1b 5b 30 6d                                          ESC [ 0 m        (reset)
```

### `filename` at `0x40013D`, 13 bytes

```
67 72 65 65 74 69 6e 67 2e 74 78 74 00    "greeting.txt\0"
```

The trailing NUL is required by the `open` syscall.

### `greet1` at `0x40014A`, 54 bytes

```
0a                                     "\n"
1b 5b 31 3b 33 33 6d                   bold yellow
2b (3d x25) 2b                         "+=========================+"
1b 5b 30 6d                            reset
0a                                     "\n"
1b 5b 31 3b 33 32 6d                   bold green
48 65 6c 6c 6f 2c 20                   "Hello, "
```

### `greet2` at `0x400180`, 45 bytes

```
21                                     "!"
1b 5b 30 6d                            reset
0a                                     "\n"
1b 5b 31 3b 33 33 6d                   bold yellow
2b (3d x25) 2b                         "+=========================+"
1b 5b 30 6d                            reset
0a                                     "\n"
```

## 5. Input buffer at `0x4001AD`

Not in the file. Provided by the kernel as part of the `PT_LOAD` segment because `p_memsz (0x22D) > p_filesz (0x1AD)` by 128 bytes. Guaranteed zeroed on process start, and the segment is writable (`p_flags = 0x7` includes `PF_W`).

## 6. How it was produced

Using `xxd -r -p` fed from a here-doc containing the literal hex bytes. No compiler, assembler, or source file was used. The entire executable is reproducible byte-for-byte by piping the exact hex in sections 1-4 above through `xxd -r -p`.

## 7. How to run

```
cd experiments/poc-01-greeter
./hello          # interactive: type a name and press Enter
cat greeting.txt # see the stored data
./test-hello     # exits 0 iff greeting.txt exists (see test-hello.md)
```

## 8. Limitations / follow-up POCs

- Graphical output is ANSI-in-terminal. Future POCs will open an X11 connection (over `/tmp/.X11-unix/X0`) directly in machine code and draw pixels, or use `/dev/fb0` when available.
- No error handling on `open`/`read`/`write`.
- Fixed 128-byte input cap.
- Only x86_64 Linux. Ports to ARM64 Linux, WebAssembly, RISC-V, and Windows PE are planned, with test binaries running each target under a VM / emulator.
