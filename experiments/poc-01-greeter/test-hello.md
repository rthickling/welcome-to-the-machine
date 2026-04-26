# `poc-01/test-hello` - Byte-by-Byte Explanation

## What it does

`test-hello` is a 163-byte statically-linked Linux ELF64 executable for x86_64 that acts as a **test binary** for `poc-01/hello`. It calls the `access(2)` syscall on the relative path `greeting.txt` with mode `F_OK` (file-exists check) and converts the result into a Unix-style exit code:

- Exits `0` (success) if `greeting.txt` exists in the current working directory.
- Exits `1` (failure) otherwise.

This is the minimum viable test for the "stores data" property of `hello`: after running `hello`, running `test-hello` in the same directory must exit 0. This was verified when building the POC:

```
$ echo "Alice" | ./hello > /dev/null  # creates greeting.txt
$ ./test-hello ; echo $?              # -> 0
$ rm greeting.txt
$ ./test-hello ; echo $?              # -> 1
```

A richer future test (planned for `poc-02`) will additionally:

1. `pipe()` + `fork()` + `execve("./hello")` with a known stdin payload.
2. Read back `greeting.txt` and `strncmp` it with the payload.
3. Parse the stdout banner and check the ANSI sequences are correct.

## Target platform and ABI

Identical to `hello`: ELF64, little-endian, `ET_EXEC`, machine `EM_X86_64 (0x3E)`, System V ABI, load address `0x400000`, entry point `0x400078`, single `PT_LOAD` segment. The one difference from `hello`'s program header:

- `p_flags = 0x5` (`PF_R | PF_X`, **no write**) - the test does not need a writable buffer.
- `p_filesz == p_memsz == 0xA3` - no zero-filled tail needed.

### Syscalls used

| Name | # | Description |
|---|---|---|
| `access` | 21 | `int access(const char *pathname, int mode)` - 0 on success, -errno on failure |
| `exit`   | 60 | `_Noreturn void _exit(int status)` |

Modes for `access`: `F_OK = 0` (file exists), `R_OK = 4`, `W_OK = 2`, `X_OK = 1`.

Because this executable is not linked against any library, the only external interface is the kernel syscall ABI.

## File layout (163 bytes = `0xA3`)

```
Offset      Size  Contents
0x000..0x03F  64  ELF64 file header
0x040..0x077  56  Program header (single PT_LOAD, R+X)
0x078..0x095  30  Executable code (entry point = VA 0x400078)
0x096..0x0A2  13  filename string "greeting.txt\0"
```

## 1. ELF64 file header - 64 bytes at offset `0x00`

```
0x00: 7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
0x10: 02 00 3e 00 01 00 00 00 78 00 40 00 00 00 00 00
0x20: 40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
0x30: 00 00 00 00 40 00 38 00 01 00 00 00 00 00 00 00
```

Identical layout/values to `hello`'s header (see `hello.md` section 1 for full decode).

## 2. Program header - 56 bytes at offset `0x40`

```
0x40: 01 00 00 00 05 00 00 00 00 00 00 00 00 00 00 00
0x50: 00 00 40 00 00 00 00 00 00 00 40 00 00 00 00 00
0x60: a3 00 00 00 00 00 00 00 a3 00 00 00 00 00 00 00
0x70: 00 10 00 00 00 00 00 00
```

| Offset | Bytes | Field | Meaning |
|---|---|---|---|
| 0x40 | `01 00 00 00` | `p_type`   | `PT_LOAD` |
| 0x44 | `05 00 00 00` | `p_flags`  | `PF_R \| PF_X` (read + execute only) |
| 0x48 | `00..00`      | `p_offset` | 0 |
| 0x50 | `00 00 40 00 00 00 00 00` | `p_vaddr`  | `0x400000` |
| 0x58 | `00 00 40 00 00 00 00 00` | `p_paddr`  | `0x400000` |
| 0x60 | `a3 00 00 00 00 00 00 00` | `p_filesz` | 163 |
| 0x68 | `a3 00 00 00 00 00 00 00` | `p_memsz`  | 163 (== filesz, no bss) |
| 0x70 | `00 10 00 00 00 00 00 00` | `p_align`  | `0x1000` |

## 3. Executable code - 30 bytes at offset `0x78` (VA `0x400078`)

The complete code, in order of execution:

| VA | Bytes | Mnemonic | Notes |
|---|---|---|---|
| 0x400078 | `b8 15 00 00 00` | `mov eax, 21`         | syscall nr = `access` (21 = 0x15) |
| 0x40007D | `bf 96 00 40 00` | `mov edi, 0x00400096` | arg 1: pathname pointer |
| 0x400082 | `31 f6`          | `xor esi, esi`        | arg 2: mode = 0 (`F_OK`) |
| 0x400084 | `0f 05`          | `syscall`             | `rax` = 0 on success, negative errno on failure |
| 0x400086 | `48 85 c0`       | `test rax, rax`       | sets ZF=1 iff rax==0 (file exists) |
| 0x400089 | `0f 95 c0`       | `setne al`            | al = 1 if ZF=0 (rax != 0, test failed), else 0 |
| 0x40008C | `0f b6 f8`       | `movzx edi, al`       | zero-extend al into edi (exit status, 0 or 1) |
| 0x40008F | `b8 3c 00 00 00` | `mov eax, 60`         | syscall nr = `exit` |
| 0x400094 | `0f 05`          | `syscall`             | does not return |

### Instruction encoding notes

- `48 85 c0` = `REX.W + 85 /r` with ModR/M byte `c0` (= `11 000 000`: reg=rax, r/m=rax). This is the 64-bit form of `test rax, rax`: bitwise AND the register with itself, discarding the result and only updating flags. Semantically equivalent to `cmp rax, 0` but one byte shorter.
- `0f 95 c0` = `SETNE r/m8` with ModR/M `c0` (r/m = `al`). Sets `al` to 1 if ZF is clear, 0 otherwise.
- `0f b6 f8` = `MOVZX r32, r/m8` with ModR/M `f8` (= `11 111 000`: reg=edi, r/m=al). Zero-extends `al` into `edi`. Using the 32-bit form automatically zeroes the top 32 bits of `rdi`, which is what the `exit` syscall sees.

### Control-flow (no jumps!)

The test contains **no conditional or unconditional branches**. The `setne` / `movzx` combination converts the syscall's return-value sign into a 0/1 exit code without any `jcc`. This keeps the code linear, branch-predictor-friendly, and trivially correct.

## 4. Data section - 13 bytes at `0x096..0x0A2`

```
67 72 65 65 74 69 6e 67 2e 74 78 74 00    "greeting.txt\0"
```

This is a **relative** path, so the test must be run from the same working directory where `hello` was run.

## 5. How it was produced

Using `xxd -r -p` fed from a here-doc containing the literal hex bytes. No compiler, assembler, or source file. The binary is reproducible byte-for-byte from the hex shown in sections 1-4 above.

## 6. How to run

```
cd experiments/poc-01-greeter
./hello                # creates greeting.txt
./test-hello           # exits 0 => PASS
echo $?

rm greeting.txt
./test-hello           # exits 1 => FAIL (as expected)
echo $?
```

Return-code convention matches `make check`, `pytest`, `ctest`, etc., so this binary can be plugged into any shell-based test runner with no wrapper.
