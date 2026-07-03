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

The executable instructions begin at file offset `0x200` / RVA `0x1000` /
VA `0x140001000` (file offset of any VA below = `VA − 0x140000000 − 0xE00`,
because RVA `0x1000` maps to file `0x200`). Full disassembly:

```text
140001000: 48 83 ec 38               sub  rsp, 0x38            ; 32B home space + 8B alignment
140001004: b9 f5 ff ff ff            mov  ecx, 0xfffffff5      ; -11 = STD_OUTPUT_HANDLE
140001009: ff 15 91 00 00 00         call QWORD [rip+0x91]     ; [0x1400010a0] = IAT:GetStdHandle
14000100f: 48 89 c1                  mov  rcx, rax             ; arg1 = console handle
140001012: 48 8d 15 22 00 00 00      lea  rdx, [rip+0x22]      ; 0x14000103b = greeting
140001019: 41 b8 0f 00 00 00         mov  r8d, 0xf             ; arg3 = 15 bytes
14000101f: 4c 8d 4c 24 30            lea  r9, [rsp+0x30]       ; arg4 = &bytes_written (scratch)
140001024: 48 c7 44 24 20 00 00 00 00  mov QWORD [rsp+0x20], 0 ; arg5 (stack) = lpOverlapped NULL
14000102d: ff 15 75 00 00 00         call QWORD [rip+0x75]     ; [0x1400010a8] = IAT:WriteFile
140001033: 31 c9                     xor  ecx, ecx             ; arg1 = exit code 0
140001035: ff 15 75 00 00 00         call QWORD [rip+0x75]     ; [0x1400010b0] = IAT:ExitProcess
```

That is 59 bytes of code (`0x1000..0x103a`); the greeting string starts
immediately after at `0x103b`.

### How the indirect calls resolve

`ff 15 disp32` is `call qword [rip + disp32]` — an **indirect** call through a
64-bit pointer in memory. `rip` at that point is the address of the *next*
instruction, so:

| call at | next insn | disp32 | slot address | IAT entry |
| ------- | --------- | ------ | ------------ | --------- |
| `0x140001009` | `0x14000100f` | `0x91` | `0x1400010a0` | `GetStdHandle` |
| `0x14000102d` | `0x140001033` | `0x75` | `0x1400010a8` | `WriteFile` |
| `0x140001035` | `0x14000103b` | `0x75` | `0x1400010b0` | `ExitProcess` |

At load time the Windows loader reads the import directory, loads
`KERNEL32.dll`, and overwrites the three 8-byte IAT slots at RVA
`0x10a0/0x10a8/0x10b0` with the real function addresses — the code itself
never needs relocating, because it only ever references the slots
RIP-relatively. (In the file, those slots hold copies of the hint/name RVAs;
they are dead values that the loader replaces.)

### Calling convention

All three calls follow the Windows x64 convention: integer args in `rcx`,
`rdx`, `r8`, `r9`, further args on the stack at `[rsp+0x20]` and up, and the
caller must reserve 32 bytes of "home space" at `[rsp]..[rsp+0x1f]` for the
callee. That is what the prologue provides:

- `sub rsp, 0x38` = 32 bytes home space + 8 bytes so `rsp` is 16-byte aligned
  at each `call` (entry `rsp` was 8 mod 16 after the loader's implicit
  return-address push), + 16 bytes at `[rsp+0x20]`/`[rsp+0x28]` for the 5th
  argument and padding. `[rsp+0x30]` doubles as the `bytes_written` out-slot.

#### `GetStdHandle(STD_OUTPUT_HANDLE)`

`mov ecx, 0xfffffff5` passes `-11` (`STD_OUTPUT_HANDLE`); writing `ecx`
zero-extends into `rcx`, which is fine because the API treats the handle id as
a 32-bit value. Returns the console output handle in `rax`.

#### `WriteFile(handle, &msg, 15, &bytes_written, NULL)`

- `rcx` = handle (copied from `rax`)
- `rdx` = `0x14000103b`, the greeting, via RIP-relative `lea` (again no
  relocation needed)
- `r8d` = 15 = length of `"Hello, win64!\r\n"`
- `r9` = `rsp+0x30`, scratch for the mandatory `lpNumberOfBytesWritten`
- `[rsp+0x20]` = 0 → `lpOverlapped = NULL` (5th arg goes on the stack)

#### `ExitProcess(0)`

`xor ecx, ecx` sets exit status `0`; the process terminates inside the call,
so no `ret` or stack cleanup is ever needed (the `sub rsp, 0x38` is never
undone, deliberately).

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

The import directory begins at file offset `0x24a` / RVA `0x104a`. It is one
20-byte `IMAGE_IMPORT_DESCRIPTOR` followed by an all-zero terminator
descriptor:

```text
0x24a: 80 10 00 00   OriginalFirstThunk = RVA 0x1080  (import lookup table)
0x24e: 00 00 00 00   TimeDateStamp      = 0
0x252: 00 00 00 00   ForwarderChain     = 0
0x256: 72 10 00 00   Name               = RVA 0x1072  ("KERNEL32.dll")
0x25a: a0 10 00 00   FirstThunk         = RVA 0x10a0  (import address table)
0x25e: 00 x20        terminator descriptor (20 zero bytes)
```

### DLL name

The `KERNEL32.dll\0` bytes begin at file offset `0x272` / RVA `0x1072`.

### ILT / IAT and hint/name entries

Both the lookup table (ILT, RVA `0x1080`, file `0x280`) and the address table
(IAT, RVA `0x10a0`, file `0x2a0`) contain the same three 8-byte entries plus a
zero terminator:

```text
c0 10 00 00 00 00 00 00   → hint/name at RVA 0x10c0  (GetStdHandle)
d0 10 00 00 00 00 00 00   → hint/name at RVA 0x10d0  (WriteFile)
dc 10 00 00 00 00 00 00   → hint/name at RVA 0x10dc  (ExitProcess)
00 00 00 00 00 00 00 00   terminator
```

Bit 63 clear in each entry means "import by name"; the low 31 bits are the RVA
of an `IMAGE_IMPORT_BY_NAME` structure — a 2-byte ordinal hint (all `0` here,
so the loader searches the export table by name) followed by the
NUL-terminated function name:

```text
0x2c0: 00 00 "GetStdHandle\0"   (RVA 0x10c0)
0x2d0: 00 00 "WriteFile\0"      (RVA 0x10d0)
0x2dc: 00 00 "ExitProcess\0"    (RVA 0x10dc)
```

At load time the loader walks the ILT to find what to import and writes the
resolved addresses over the IAT copies — which is exactly where the three
`call qword [rip+disp]` instructions point. `objdump` recognises the imported
function names from these entries.

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
