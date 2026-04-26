# `poc-05/test-hello.wasm` — runnable WASI test for `hello.wasm`

`test-hello.wasm` is a **364-byte** WebAssembly MVP module that runs under
WASI and structurally tests its sibling `hello.wasm`.

It opens `./hello.wasm` through a preopened directory, reads the first chunk of
the file, and checks five fixed 32-bit values:

1. wasm magic `00 61 73 6d`
2. version `01 00 00 00`
3. `Hell`
4. `o, w`
5. `asm!`

The last three words come from the known greeting payload inside
`hello.wasm`, so this is stronger than merely checking “is it any wasm file?”.

Exit code:

- `0` = pass
- `1` = fail

## How it works

`_start` is compiled WebAssembly: it first `call`s `path_open` (preopen fd `3` = current directory) to obtain a real `fd` for `hello.wasm` and store it in linear memory, then `fd_read`’s up to 192 bytes into a fixed buffer. The rest of the body is a straight-line sequence of five `i32.load` / `i32.const` / `i32.ne` / `if` … `call proc_exit(1)` … `end` checks for magic, version, and three 32-bit slices of the greeting. If every comparison is false (values match), control falls off the end of `_start` with exit status `0`. Operationally it is the same stack machine as **`hello.wasm`**: push addresses and expected words, compare, and **branch to `proc_exit(1)`** on inequality; see the `_start` opcode walk-through in `hello.wasm.md` for the base mnemonics (`i32.const`, `i32.load`, `call`, etc.).

## Usage

Because the test opens `hello.wasm` as a file, the current directory must be
preopened into WASI:

```bash
cd experiments/poc-05-wasm-wasi
~/.wasmtime/bin/wasmtime run --dir=. test-hello.wasm
echo $?
```

Verified result: `0`.

## Whole-file hex

```text
00 61 73 6d 01 00 00 00
01 1d 04 60 09 7f 7f 7f 7f 7f 7e 7e 7f 7f 01 7f 60 04 7f 7f 7f 7f 01 7f 60 01 7f 00 60 00 00
02 68 03
16 77 61 73 69 5f 73 6e 61 70 73 68 6f 74 5f 70 72 65 76 69 65 77 31 09 70 61 74 68 5f 6f 70 65 6e 00 00
16 77 61 73 69 5f 73 6e 61 70 73 68 6f 74 5f 70 72 65 76 69 65 77 31 07 66 64 5f 72 65 61 64 00 01
16 77 61 73 69 5f 73 6e 61 70 73 68 6f 74 5f 70 72 65 76 69 65 77 31 09 70 72 6f 63 5f 65 78 69 74 00 02
03 02 01 03
05 03 01 00 01
07 13 02 06 6d 65 6d 6f 72 79 02 00 06 5f 73 74 61 72 74 00 03
0a 92 01 01 8f 01 00
41 03 41 00 41 00 41 0a 41 00 42 02 42 00 41 00 41 10 10 00 04 40 41 01 10 02 0b
41 10 28 02 00 41 14 41 01 41 1c 10 01 04 40 41 01 10 02 0b
41 20 28 02 00 41 80 c2 cd eb 06 47 04 40 41 01 10 02 0b
41 24 28 02 00 41 01 47 04 40 41 01 10 02 0b
41 9a 01 28 02 00 41 c8 ca b1 e3 06 47 04 40 41 01 10 02 0b
41 9e 01 28 02 00 41 ef d8 80 b9 07 47 04 40 41 01 10 02 0b
41 a2 01 28 02 00 41 e1 e6 b5 8b 02 47 04 40 41 01 10 02 0b 0b
0b 26 01 00 41 00 0b
20 68 65 6c 6c 6f 2e 77 61 73 6d 00 00 00 00 00 00 00 00 00
20 00 00 00 c0 00 00 00 00 00 00 00
```

## Type section

Four signatures:

1. `path_open`
   `(i32, i32, i32, i32, i32, i64, i64, i32, i32) -> i32`
2. `fd_read`
   `(i32, i32, i32, i32) -> i32`
3. `proc_exit`
   `(i32) -> ()`
4. `_start`
   `() -> ()`

## Imports

Three WASI Preview 1 imports from `wasi_snapshot_preview1`:

1. `path_open`
2. `fd_read`
3. `proc_exit`

`proc_exit` is used to report failure with status `1`.

## Exports

Like `hello.wasm`, this test exports:

1. `memory`
2. `_start`

Fixed offsets in the built file:

- `memory` export string starts at file offset `158`
- `_start` export string starts at file offset `167`
- embedded path string `"hello.wasm"` starts at file offset `332`

## Linear memory layout

The data segment seeds the following memory:

| Offset | Meaning |
| ------ | ------- |
| `0x00` | path string `"hello.wasm"` |
| `0x10` | opened file descriptor slot |
| `0x14` | `iovec.buf = 32` |
| `0x18` | `iovec.len = 192` |
| `0x1c` | `nread` scratch |
| `0x20` | file read buffer |

So the test reads up to 192 bytes of `hello.wasm` into memory starting at
offset `32`.

## `_start` logic

### Step 1 — open `hello.wasm`

The test calls:

```text
path_open(
  fd = 3,              ; preopened current directory
  dirflags = 0,
  path_ptr = 0,
  path_len = 10,
  oflags = 0,
  rights_base = 2,     ; FD_READ
  rights_inheriting = 0,
  fdflags = 0,
  opened_fd_ptr = 16
)
```

If the returned errno is non-zero, it immediately calls `proc_exit(1)`.

### Step 2 — read the sibling file

Then it loads the just-opened fd from memory and calls:

```text
fd_read(fd, iovs=20, iovs_len=1, nread_ptr=28)
```

Again, any non-zero errno causes `proc_exit(1)`.

### Step 3 — fixed 32-bit comparisons

The remaining code performs five checks. Each check has the pattern:

```text
i32.const <address>
i32.load
i32.const <expected>
i32.ne
if
  i32.const 1
  call proc_exit
end
```

The addresses and expected values are:

| Address in test memory | Meaning | Expected |
| ---------------------- | ------- | -------- |
| `32 + 0`   | bytes `0..3` of file | `0x6d736100` (`00 61 73 6d`) |
| `32 + 4`   | bytes `4..7` of file | `0x00000001` |
| `32 + 122` | `Hell` from payload | `0x6c6c6548` |
| `32 + 126` | `o, w` from payload | `0x77202c6f` |
| `32 + 130` | `asm!` from payload | `0x216d7361` |

Those payload offsets match the built `hello.wasm`, whose greeting begins at
file offset `122`.

If all five comparisons pass, `_start` simply reaches `end` and the process
returns success.

## Interfaces used

### `wasi_snapshot_preview1.path_open`

Used with a preopened directory fd (`3`) supplied by:

```bash
wasmtime run --dir=. test-hello.wasm
```

### `wasi_snapshot_preview1.fd_read`

Used to read the sibling wasm file into linear memory.

### `wasi_snapshot_preview1.proc_exit`

Used only for failure reporting (`proc_exit(1)`).

## Why this is a good first cross-architecture test

It is:

- a real machine-code test binary
- runnable under the target runtime
- independent of x86 Linux syscalls
- strong enough to catch layout drift in `hello.wasm`

It also establishes the pattern we can reuse for future wasm targets:
target module + runnable wasm test module + Markdown explaining the exact
binary format and host imports.
