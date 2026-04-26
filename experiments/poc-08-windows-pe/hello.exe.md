# `poc-08/hello.exe` — first Windows PE64 target

`hello.exe` is a **1024-byte** `PE32+` executable for **Windows x86_64**.
It is a console-subsystem program with one `.text` section containing:

- the code
- the greeting string
- the import directory
- the import address table
- the hint/name strings

Its entry point is `0x140001000`.

The code is intended to:

1. call `GetStdHandle(STD_OUTPUT_HANDLE)`
2. call `WriteFile` to print `Hello, win64!\r\n`
3. call `ExitProcess(0)`

**Control flow (mnemonic):** `sub rsp, 0x38` reserves Windows x64 home space; `mov ecx, -11` / `call [IAT GetStdHandle]` gets stdout; `mov rcx, rax` / `lea rdx, [greeting]` / `mov r8d, 15` / `lea r9, [stack scratch]` / `call [IAT WriteFile]` prints; `xor ecx, ecx` / `call [IAT ExitProcess]` returns `0` to the loader.

## Current verification status

This PE has now been verified in three ways on the current Linux host:

- `file` recognises it as `PE32+ executable (console) x86-64`
- `objdump -x` recognises:
  - `Subsystem = Windows CUI`
  - entry point `0x140001000`
  - a valid import table
  - imported function names `GetStdHandle`, `WriteFile`, and `ExitProcess`
- `wine hello.exe` executes the binary and prints:

```text
Hello, win64!
```

Wine still prints an environment warning about missing `wine32`, but the
64-bit PE itself does run correctly and returns exit status `0`.

The companion machine-code test binary (`test-hello`) also validates the fixed
header bytes, the greeting payload, the import-descriptor name RVA, the
`KERNEL32.dll` string, and selected code bytes that previously regressed.

## File layout

```text
0x000..0x03f   64    DOS header
0x040..0x07f   64    DOS stub / padding to e_lfanew
0x080..0x187  264    PE signature + COFF header + optional header
0x188..0x1af   40    single section header (.text)
0x1b0..0x1ff   80    header padding to FileAlignment 0x200
0x200..0x3ff  512    .text raw section
```

Total file size: `1024` bytes.

## DOS header

At file offset `0`:

```text
4d 5a
```

That is the `MZ` signature.

At file offset `0x3c`:

```text
80 00 00 00
```

which sets `e_lfanew = 0x80`, pointing to the PE signature.

## PE / COFF header

At file offset `0x80`:

```text
50 45 00 00   ; "PE\0\0"
64 86         ; Machine = AMD64 (0x8664)
01 00         ; NumberOfSections = 1
...
f0 00         ; SizeOfOptionalHeader = 0xF0
22 00         ; Characteristics = executable | large address aware
```

`objdump -x` reports:

- format: `pei-x86-64`
- start address: `0x140001000`

## Optional header highlights

Important fields:

- `Magic = 0x20b` (`PE32+`)
- `AddressOfEntryPoint = 0x1000`
- `BaseOfCode = 0x1000`
- `ImageBase = 0x140000000`
- `SectionAlignment = 0x1000`
- `FileAlignment = 0x200`
- `SizeOfImage = 0x2000`
- `SizeOfHeaders = 0x200`
- `Subsystem = 3` (`Windows CUI`)
- `NumberOfRvaAndSizes = 16`

Data-directory entries used:

- Import Directory: `RVA 0x104a`, size `0x28`
- Import Address Table: `RVA 0x10a0`, size `0x20`

## Section table

One section:

```text
Name            .text
VirtualSize     0x000000ea
VirtualAddress  0x00001000
SizeOfRawData   0x00000200
PointerToRaw    0x00000200
Characteristics 0x60000020  ; CODE | EXECUTE | READ
```

So the single section is mapped at:

```text
RVA  0x1000
VMA  0x140001000
FILE 0x200
```

## Code bytes

The executable instructions begin at file offset `0x200` / RVA `0x1000`:

```text
48 83 ec 38                         ; sub rsp, 0x38
b9 f5 ff ff ff                      ; mov ecx, -11
ff 15 91 00 00 00                   ; call [rip+0x91]  -> IAT:GetStdHandle
48 89 c1                            ; mov rcx, rax
48 8d 15 22 00 00 00                ; lea rdx, [rip+0x22] -> greeting
41 b8 0f 00 00 00                   ; mov r8d, 15
4c 8d 4c 24 30                      ; lea r9, [rsp+0x30]
48 c7 44 24 20 00 00 00 00          ; mov qword [rsp+0x20], 0
ff 15 75 00 00 00                   ; call [rip+0x75]  -> IAT:WriteFile
31 c9                               ; xor ecx, ecx
ff 15 75 00 00 00                   ; call [rip+0x75]  -> IAT:ExitProcess
```

### What that does

#### Prologue

`sub rsp, 0x38` reserves:

- 32 bytes of Windows x64 shadow space
- 8 extra bytes so the stack remains suitably aligned

#### `GetStdHandle`

`mov ecx, -11` passes:

- `STD_OUTPUT_HANDLE = -11`

The first indirect call uses the IAT slot for `GetStdHandle`, which returns the
console output handle in `rax`.

#### `WriteFile`

The next setup passes:

- `rcx = handle`
- `rdx = &"Hello, win64!\r\n"`
- `r8d = 15`
- `r9  = &bytes_written`
- `[rsp+0x20] = 0` for the 5th arg (`lpOverlapped = NULL`)

Then the second indirect call uses the IAT slot for `WriteFile`.

#### `ExitProcess`

`xor ecx, ecx` sets exit status `0`, and the final indirect call goes through
the `ExitProcess` IAT slot.

## Inline data and imports inside `.text`

### Greeting payload

At file offset `0x23b` / RVA `0x103b`:

```text
48 65 6c 6c 6f 2c 20 77 69 6e 36 34 21 0d 0a
```

ASCII:

```text
Hello, win64!\r\n
```

### Import descriptor

The import directory begins at file offset `0x24a` / RVA `0x104a`.

It names one DLL:

- `KERNEL32.dll`

and one import address table at `RVA 0x10a0`.

### DLL name

The `KERNEL32.dll` bytes begin at file offset `0x272`.

### ILT / IAT and hint/name entries

The final patched import RVAs are:

- ILT entries at `RVA 0x1080`
- IAT entries at `RVA 0x10a0`
- `GetStdHandle` hint/name at `RVA 0x10c0`
- `WriteFile` hint/name at `RVA 0x10d0`
- `ExitProcess` hint/name at `RVA 0x10dc`

`objdump` recognises the imported function names from those entries.

## Why the file is exactly 1024 bytes

The PE uses:

- `FileAlignment = 0x200`
- one raw section of size `0x200`
- headers padded out to `0x200`

So:

```text
0x200 headers + 0x200 section = 0x400 bytes = 1024
```

That round number is a direct consequence of the PE alignment rules, unlike the
more size-tight ELF artifacts elsewhere in the repo.
