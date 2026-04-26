# `poc-08/test-hello` — host-side machine-code test for `hello.exe`

`test-hello` is a **369-byte** statically-linked Linux ELF64 x86_64 binary
that structurally tests the Windows PE target `./hello.exe`.

It does **not** execute the PE. Instead it:

1. opens `hello.exe`
2. reads the first 1024 bytes into memory
3. checks:
   - `MZ` at offset `0x000`
   - `PE\0\0` at offset `0x080`
   - the first imported-call opcode at offset `0x209`
   - the `lea`-to-greeting bytes at offset `0x212`
   - `Hello, win64!\r\n` at offset `0x23b`
   - the import-descriptor `Name` RVA at offset `0x256`
   - `KERNEL32.dll\0` at offset `0x272`

Exit status:

- `0` = pass
- `1` = fail

This gives the Windows target a fast machine-code regression check on Linux
without having to start Wine for every validation pass.

## Usage

```bash
cd experiments/poc-08-windows-pe
./test-hello
echo $?
```

Verified result: `0`.

Also verified by corrupting the `lea` displacement byte at offset `0x215` of
`hello.exe`; the test then exits `1`, and returns to `0` after restoring the
original byte.

## Why this test is Linux ELF

The target is Windows PE, but under the repo rules it is still useful to ship a
machine-code test that runs directly on the Linux host. This verifier checks the
fixed PE bytes directly, while `wine hello.exe` serves as the separate runtime
execution check.

It is therefore:

- still machine code
- still a real executable binary
- runnable on this host right now
- good enough to catch structural regressions in the Windows target

## Body layout

`mkelf` prepends its normal 120-byte ELF wrapper to a `249`-byte body:

```text
0x000..0x077   120   ELF header + PT_LOAD program header
0x078..0x148   209   code
0x149..0x154    12   path string "hello.exe\0\0\0"
0x155..0x163    15   expected greeting
0x164..0x170    13   expected DLL name
```

Total file size: `369` bytes.

## High-level logic

Pseudocode:

```text
fd = open("hello.exe", O_RDONLY)
read(fd, 0x401000, 1024)

if *(u16*)(0x401000 + 0x000) != 0x5a4d: fail
if *(u32*)(0x401000 + 0x080) != 0x00004550: fail
if *(u16*)(0x401209) != 0x15ff: fail
if *(u32*)(0x401212) != 0x22158d48: fail
if memcmp(0x40123b, "Hello, win64!\r\n", 15) != 0: fail
if *(u32*)(0x401256) != 0x00001072: fail
if memcmp(0x401272, "KERNEL32.dll\0", 13) != 0: fail

exit(0)
fail: exit(1)
```

**How the Linux test maps to instructions:** the verifier uses the usual `open(2)` / `read(2)` prologue, then a chain of `cmp` against absolute addresses in the mapped buffer and two `repe cmpsb` memcmp-style checks (greeting, DLL name). Any mismatch jumps to a shared fail epilogue; success falls through to `exit(0)`. Blocks below name each **Intel** mnemonic sequence in file order.

## Code walkthrough

### Block 1 — open sibling PE

```text
b8 02 00 00 00             mov eax, 2
bf 49 01 40 00             mov edi, 0x400149
31 f6                      xor esi, esi
31 d2                      xor edx, edx
0f 05                      syscall
48 85 c0                   test rax, rax
0f 88 ac 00 00 00          js fail
48 89 c3                   mov rbx, rax
```

This is:

```text
open("hello.exe", O_RDONLY, 0)
```

The pathname string lives at virtual address `0x400149`.

### Block 2 — read first 1024 bytes

```text
31 c0                      xor eax, eax
48 89 df                   mov rdi, rbx
be 00 10 40 00             mov esi, 0x401000
ba 00 04 00 00             mov edx, 1024
0f 05                      syscall
48 3d 00 04 00 00          cmp rax, 1024
0f 85 8c 00 00 00          jne fail
```

So:

```text
read(fd, 0x401000, 1024)
```

### Block 3 — verify `MZ`

```text
66 81 3c 25 00 10 40 00 4d 5a    cmp word [0x401000], 0x5a4d
0f 85 7c 00 00 00                jne fail
```

The little-endian constant `0x5a4d` corresponds to:

```text
4d 5a
```

### Block 4 — verify `PE\0\0`

```text
81 3c 25 80 10 40 00 50 45 00 00    cmp dword [0x401080], 0x00004550
0f 85 6b 00 00 00                   jne fail
```

That is the PE signature at file offset `0x80`.

### Block 5 — verify the first imported-call opcode

```text
66 81 3c 25 09 12 40 00 ff 15    cmp word [0x401209], 0x15ff
0f 85 5b 00 00 00                jne fail
```

This checks that the first Windows import really uses:

```text
ff 15
```

which is the `call [rip+disp32]` opcode pair. A previous broken build omitted
the leading `ff`, which made execution fall through into data.

### Block 6 — verify the greeting pointer bytes

```text
81 3c 25 12 12 40 00 48 8d 15 22    cmp dword [0x401212], 0x22158d48
0f 85 4a 00 00 00                   jne fail
```

This checks the four bytes:

```text
48 8d 15 22
```

which cover the start of the `lea rdx, [rip+0x22]` instruction used to point at
the greeting string. This catches the one-byte displacement regression that made
Wine print `ello, win64!` plus one extra byte.

### Block 7 — compare greeting payload

```text
be 3b 12 40 00             mov esi, 0x40123b
bf 55 01 40 00             mov edi, 0x400155
b9 0f 00 00 00             mov ecx, 15
fc                         cld
f3 a6                      repe cmpsb
0f 85 32 00 00 00          jne fail
```

This compares the 15 bytes loaded from `hello.exe` offset `0x23b` against the
embedded expected string:

```text
Hello, win64!\r\n
```

### Block 8 — verify the import-descriptor DLL-name RVA

```text
81 3c 25 56 12 40 00 72 10 00 00    cmp dword [0x401256], 0x00001072
0f 85 21 00 00 00                   jne fail
```

This checks that the import descriptor's `Name` field points at the actual DLL
string. A previous broken build pointed a few bytes too late and caused Wine to
look for a malformed DLL name.

### Block 9 — compare DLL name

```text
be 72 12 40 00             mov esi, 0x401272
bf 64 01 40 00             mov edi, 0x400164
b9 0d 00 00 00             mov ecx, 13
fc                         cld
f3 a6                      repe cmpsb
0f 85 09 00 00 00          jne fail
```

This compares the bytes at file offset `0x272` against:

```text
KERNEL32.dll\0
```

### Block 10 — success / fail exits

Success:

```text
b8 3c 00 00 00       mov eax, 60
31 ff                xor edi, edi
0f 05                syscall
```

Fail:

```text
b8 3c 00 00 00       mov eax, 60
bf 01 00 00 00       mov edi, 1
0f 05                syscall
```

Linux syscall `60` is `exit`.

## Embedded data

The three literals packed after the code are:

### Path at `0x400149`

```text
68 65 6c 6c 6f 2e 65 78 65 00 00 00
```

ASCII:

```text
hello.exe\0\0\0
```

### Expected greeting at `0x400155`

```text
48 65 6c 6c 6f 2c 20 77 69 6e 36 34 21 0d 0a
```

### Expected DLL string at `0x400164`

```text
4b 45 52 4e 45 4c 33 32 2e 64 6c 6c 00
```

## Syscalls used

Exactly three Linux x86_64 syscalls:

| nr | name | purpose |
| -- | ---- | ------- |
| 2  | open | open `hello.exe` |
| 0  | read | read the PE bytes |
| 60 | exit | return pass/fail |

## What this test proves

It proves that the committed Windows target:

- starts with a DOS header
- has a PE signature at the expected offset
- contains the expected `call [rip+disp32]` import opcode bytes
- contains the expected `lea` displacement for the greeting pointer
- contains the expected greeting payload
- contains the expected import-descriptor `Name` RVA
- contains the expected `KERNEL32.dll` import string

It does **not** by itself prove full runtime behaviour, but `wine hello.exe`
has also now been run successfully on the current host as a separate execution
check.
