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

## Section-by-section layout

### Magic + version (8 bytes)

```text
00 61 73 6d    ; "\0asm"
01 00 00 00    ; version 1
```

### Type section `0x01` (14 bytes payload)

Two function signatures:

1. `(i32, i32, i32, i32) -> i32` for imported `fd_write`
2. `() -> ()` for exported `_start`

Bytes:

```text
01                ; section id = Type
0c                ; payload length = 12
02                ; 2 entries
60 04 7f 7f 7f 7f 01 7f   ; type 0
60 00 00                   ; type 1
```

### Import section `0x02`

One imported function:

- module: `wasi_snapshot_preview1`
- name: `fd_write`
- kind: function
- type index: `0`

This is the only host interface used.

### Function section `0x03`

One defined function of type index `1`, i.e. `_start`.

### Memory section `0x05`

One linear memory:

- minimum = 1 page (64 KiB)

### Export section `0x07`

Two exports:

1. `memory` (kind `0x02`, memory index `0`)
2. `_start` (kind `0x00`, function index `1`)

`wasmtime` requires the `memory` export for this style of WASI command module.

Fixed offsets in the built file:

- `memory` export string starts at file offset `72`
- `_start` export string starts at file offset `81`

### Code section `0x0a`

One body, 13 bytes long including the local decl count and `end`.

Function body bytes:

```text
00          ; local decl count = 0
41 01       ; i32.const 1   -> fd = stdout
41 00       ; i32.const 0   -> iovs ptr
41 01       ; i32.const 1   -> iovs len
41 18       ; i32.const 24  -> nwritten ptr
10 00       ; call import 0 = fd_write
1a          ; drop errno
0b          ; end
```

So `_start` performs exactly one host call:

```text
fd_write(1, 0, 1, 24)
```

## Data section `0x0b`

One active data segment for memory index 0, offset 0.

Payload layout in linear memory:

```text
offset 0x00: 08 00 00 00   ; iovec.buf = 8
offset 0x04: 0d 00 00 00   ; iovec.len = 13
offset 0x08: 48 65 6c 6c 6f 2c 20 77 61 73 6d 21 0a
offset 0x18: 00 00 00 00   ; nwritten scratch
```

That means the `fd_write` call writes exactly 13 bytes from address `8`.

The greeting payload begins at **file offset `122`** in the built binary.

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
