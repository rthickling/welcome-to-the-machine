# `poc-05/hello.wasm` — first WebAssembly target

`hello.wasm` is a **139-byte** WebAssembly MVP module that runs as a WASI
command under `wasmtime` and prints:

```text
Hello, wasm!
```

This is the repo's first non-ELF target: still machine code only, but now in
the WebAssembly binary format instead of ELF.

## How it works

The module is a static WASI command: it exports one page of **memory** and an exported function **`_start`**. The code section pushes four `i32` operands (stdout `fd`, pointer to a single `iovec` in linear memory, `iovs` count `1`, and a scratch pointer for the byte count), then `call`’s the imported `fd_write`. On success, `fd_write` returns `0`; `drop` discards that `i32` and the function `end`’s, which exits normally. The data segment at file offset `122` contains the `Hello, wasm!\n` bytes; `fd_write` copies from that `iovec` to the host. There are no local variables and no control flow other than the single import call.

## Runtime

Verified with:

```bash
~/.wasmtime/bin/wasmtime run hello.wasm
```

The module imports WASI Preview 1 from `wasi_snapshot_preview1`.

## Whole-file hex

```text
00 61 73 6d 01 00 00 00
01 0c 02 60 04 7f 7f 7f 7f 01 7f 60 00 00
02 23 01 16 77 61 73 69 5f 73 6e 61 70 73 68 6f 74 5f 70 72 65 76 69 65 77 31 08 66 64 5f 77 72 69 74 65 00 00
03 02 01 01
05 03 01 00 01
07 13 02 06 6d 65 6d 6f 72 79 02 00 06 5f 73 74 61 72 74 00 01
0a 0f 01 0d 00 41 01 41 00 41 01 41 18 10 00 1a 0b
0b 1f 01 00 41 00 0b 19 08 00 00 00 0d 00 00 00 48 65 6c 6c 6f 2c 20 77 61 73 6d 21 0a 00 00 00 00
```

## Encoding conventions (read this once)

Every integer in the WebAssembly binary format — section lengths, counts,
indices, and the immediates of `i32.const` — is **LEB128** (little-endian
base-128) encoded: 7 value bits per byte, high bit set on all but the last
byte. Every integer in this module is below 128, so each is a single byte
whose value can be read directly. Value types are single bytes too: `0x7f` =
`i32`. A function signature starts with `0x60`. The opcodes used are:

| Byte | Opcode      | Immediate            |
| ---- | ----------- | -------------------- |
| `41` | `i32.const` | LEB128 signed value  |
| `10` | `call`      | LEB128 function index |
| `1a` | `drop`      | —                    |
| `0b` | `end`       | —                    |

## Section-by-section layout

File offsets of every section (each is `id byte + LEB128 payload length +
payload`):

```text
0x00..0x07  magic + version
0x08..0x15  Type      (id 0x01)
0x16..0x3a  Import    (id 0x02)
0x3b..0x3e  Function  (id 0x03)
0x3f..0x43  Memory    (id 0x05)
0x44..0x58  Export    (id 0x07)
0x59..0x69  Code      (id 0x0a)
0x6a..0x8a  Data      (id 0x0b)
```

`0x8b` = 139 bytes total.

### Magic + version (8 bytes, `0x00`)

```text
00 61 73 6d    ; "\0asm"
01 00 00 00    ; version 1 (fixed u32, not LEB128)
```

### Type section `0x01` (`0x08`, 12-byte payload)

Two function signatures:

```text
01                ; section id = Type
0c                ; payload length = 12
02                ; 2 entries
60 04 7f 7f 7f 7f 01 7f   ; type 0: 0x60 func, 4 params (i32 ×4), 1 result (i32)
60 00 00                   ; type 1: 0x60 func, 0 params, 0 results
```

Type 0 is `(i32, i32, i32, i32) -> i32` for the imported `fd_write`; type 1
is `() -> ()` for `_start`.

### Import section `0x02` (`0x16`, 35-byte payload)

One imported function — the only host interface used:

```text
02                ; section id = Import
23                ; payload length = 35
01                ; 1 import
16                ; module name length = 22
77 61 73 69 5f 73 6e 61 70 73 68 6f 74 5f 70 72 65 76 69 65 77 31
                  ; "wasi_snapshot_preview1"
08                ; field name length = 8
66 64 5f 77 72 69 74 65   ; "fd_write"
00                ; import kind = function
00                ; type index = 0
```

Imported functions occupy the low function indices, so `fd_write` is
**function 0** and the module's own function becomes function 1.

### Function section `0x03` (`0x3b`, 2-byte payload)

```text
03 02             ; section id, payload length = 2
01                ; 1 defined function
01                ; its type index = 1, i.e. () -> ()
```

This declares `_start`'s signature; its body comes in the Code section.

### Memory section `0x05` (`0x3f`, 3-byte payload)

```text
05 03             ; section id, payload length = 3
01                ; 1 linear memory
00 01             ; limits: flag 0 = min only, min = 1 page (64 KiB)
```

### Export section `0x07` (`0x44`, 19-byte payload)

```text
07 13             ; section id, payload length = 19
02                ; 2 exports
06 6d 65 6d 6f 72 79      ; name "memory" (length 6)
02 00                     ; kind 0x02 = memory, index 0
06 5f 73 74 61 72 74      ; name "_start" (length 6)
00 01                     ; kind 0x00 = function, index 1
```

`wasmtime` requires the `memory` export for this style of WASI command module.

Fixed offsets in the built file:

- `memory` export string starts at file offset `72` (`0x48`)
- `_start` export string starts at file offset `81` (`0x51`)

### Code section `0x0a` (`0x59`, 15-byte payload)

```text
0a 0f             ; section id, payload length = 15
01                ; 1 function body
0d                ; body size = 13 bytes
```

Function body (13 bytes — this is the entirety of the program's executable
logic):

```text
00          ; local decl count = 0 (no locals)
41 01       ; i32.const 1   -> arg 1: fd = stdout
41 00       ; i32.const 0   -> arg 2: iovs ptr (linear address 0)
41 01       ; i32.const 1   -> arg 3: iovs count = 1
41 18       ; i32.const 24  -> arg 4: nwritten ptr (linear address 24)
10 00       ; call function 0 = imported fd_write
1a          ; drop the returned errno
0b          ; end -> _start returns -> normal exit
```

WebAssembly is a stack machine: the four `i32.const` instructions push the
call's arguments in order, `call 0` pops all four and pushes the `i32`
result, `drop` pops it, leaving the stack empty as required at `end`. So
`_start` performs exactly one host call:

```text
fd_write(1, 0, 1, 24)
```

There is no explicit exit call; returning from `_start` with an empty stack
is a normal WASI command exit with status 0.

## Data section `0x0b` (`0x6a`, 31-byte payload)

```text
0b 1f             ; section id, payload length = 31
01                ; 1 data segment
00                ; memory index 0
41 00 0b          ; offset expression: i32.const 0; end
19                ; payload size = 25 bytes
08 00 00 00       ; linear 0x00: iovec.buf = 8   (little-endian u32)
0d 00 00 00       ; linear 0x04: iovec.len = 13
48 65 6c 6c 6f 2c 20 77 61 73 6d 21 0a
                  ; linear 0x08..0x14: "Hello, wasm!\n"
00 00 00 00       ; linear 0x15..0x18: pad + first byte of nwritten scratch
```

The segment is *active*: the runtime copies these 25 bytes into linear memory
at offset 0 before `_start` runs. The `fd_write` call reads the `ciovec`
struct at address 0 — buffer pointer `8`, length `13` — and writes those 13
bytes to stdout. The scratch dword at linear address `24` (`0x18`) receives
the written-byte count; only its first byte is inside the segment, but the
rest of the fresh 64 KiB memory page is guaranteed zero anyway.

The greeting payload begins at **file offset `122`** (`0x7a`) in the built
binary.

## Interfaces used

### WASI import

Imported function:

```text
wasi_snapshot_preview1.fd_write
type: (i32 fd, i32 iovs, i32 iovs_len, i32 nwritten_ptr) -> i32 errno
```

The module assumes standard WASI `fd_write` semantics:

- `fd = 1` is stdout
- `iovs` points at an array of `ciovec { ptr: u32, len: u32 }`
- return value `0` means success

## Why this module is useful

It proves the repo can target:

- a different binary format
- a different execution environment
- still with a runnable machine-code test flow

without introducing any human-readable source into the repo.
