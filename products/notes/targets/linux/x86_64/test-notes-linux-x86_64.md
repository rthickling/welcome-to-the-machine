# `products/notes/test-notes-linux-x86_64`

`test-notes-linux-x86_64` is a **509-byte** statically-linked Linux ELF64
x86_64 binary. It is a headless structural verifier for the Linux product
reference build `./notes-linux-x86_64`.

Terminology for [BSS](../../../glossary.md#bss), syscalls, and similar implementation
phrases: [product notes glossary](../../../glossary.md).

It checks eleven anchored byte ranges:

1. window title `notes-x64` at file offset `0x784`
2. left-pane label `Note:` at file offset `0x824`
3. right-pane header `Words` at file offset `0x870`
4. dark `CreateWindow` background pixel at `0x764`
5. light-on-dark `CreateGC` foreground/background pixels at `0x7b4`
6. expanded printable keymap row at `0x83e`
7. border helper call at `0x549`
8. border helper prefix at `0x92a`
9. session-bootstrap entry redirect `e9 3e 0a 00 00` at `0x78`
10. `find_env` prologue at `0xa48`
11. session-bootstrap `socket`-resume tail at `0xbce`

The last three anchors were added when the product became session-independent:
they lock down the runtime `DISPLAY`/cookie/root-window discovery code so a
regression there is caught by the always-runnable structural check.

Exit status:

- `0` = pass
- `1` = fail

## Why this test is structural

The target is a GUI program tied to the live X11 session cookie and socket, so a
small structural verifier is the safest always-runnable regression check on the
Linux host. It proves that the visible product strings, colour constants,
printable keymap expansion, and border drawing entry point are present in the
expected file layout.

## File layout

`mkelf` wraps a `332`-byte body:

```text
0x000..0x077   120   ELF header + PT_LOAD program header
0x078..0x0fc   133   open + descriptor-driven pread64/compare loop + exits
0x0fd..0x10f    19   path string "notes-linux-x86_64\0"
0x110..0x193   132   eleven 12-byte check descriptors
0x194..0x1fc   105   expected byte ranges
```

Total file size: `509` bytes.

The only code change from the eight-descriptor revision is the descriptor count
immediate at `0x9c` (`0x08` → `0x0b`); the descriptor-base at `0x94` is still
`0x400110`. Everything else in the code walk-through below is unchanged.

## The shared descriptor-driven verifier (canonical reference)

Every product structural verifier in this repo (`test-notes-macos`,
`test-notes-ios`, `test-notes-linux-arm64`, `test-notes-web`,
`test-notes-winarm64`, `test-notes-win64`, `test-notes-android`) is the **same
Linux x86_64 machine-code routine** documented below. They differ only in three
things, all in data:

1. the embedded path string (which sibling file to open),
2. the descriptor-table base address loaded into `r12d`,
3. the descriptor count loaded into `r13d`.

Those sibling docs therefore link here for the opcode walkthrough and only
tabulate their own path, count, and the byte content of each 12-byte
descriptor. The three-word descriptor format is:

```text
u32 file_offset                    ; where in the target file to read
u32 byte_count                     ; how many bytes to read and compare
u32 expected_bytes_virtual_address ; pointer to the embedded expected bytes
```

## Overall logic

Pseudocode:

```text
fd = open(path, O_RDONLY)

for each descriptor:
    pread64(fd, buf, descriptor.length, descriptor.offset)
    memcmp(buf, descriptor.expected, descriptor.length)

exit(0) on success, else exit(1)
```

## Code walk-through

The ELF has no section table, so the listing below is from `objdump` on the raw
load segment. Addresses are the runtime virtual addresses after `mkelf`'s
fixed `0x400078` entry point.

```text
400078: b8 02 00 00 00                mov     eax, 0x2          ; __NR_open
40007d: bf fd 00 40 00                mov     edi, 0x4000fd     ; path
400082: 31 f6                         xor     esi, esi          ; O_RDONLY
400084: 31 d2                         xor     edx, edx
400086: 0f 05                         syscall
400088: 48 85 c0                      test    rax, rax
40008b: 0f 88 60 00 00 00             js      0x4000f1          ; fail
400091: 48 89 c3                      mov     rbx, rax          ; fd
400094: 41 bc 10 01 40 00             mov     r12d, 0x400110    ; descriptors
40009a: 41 bd 0b 00 00 00             mov     r13d, 0xb         ; count (11 descriptors)

4000a0: b8 11 00 00 00                mov     eax, 0x11         ; __NR_pread64
4000a5: 48 89 df                      mov     rdi, rbx
4000a8: be 00 10 40 00                mov     esi, 0x401000     ; scratch buffer
4000ad: 41 8b 54 24 04                mov     edx, [r12+4]      ; length
4000b2: 45 8b 14 24                   mov     r10d, [r12]       ; file offset
4000b6: 0f 05                         syscall
4000b8: 41 3b 44 24 04                cmp     eax, [r12+4]
4000bd: 0f 85 2e 00 00 00             jne     0x4000f1
4000c3: be 00 10 40 00                mov     esi, 0x401000
4000c8: 41 8b 7c 24 08                mov     edi, [r12+8]      ; expected bytes
4000cd: 41 8b 4c 24 04                mov     ecx, [r12+4]
4000d2: fc                            cld
4000d3: f3 a6                         repe    cmpsb
4000d5: 0f 85 16 00 00 00             jne     0x4000f1
4000db: 49 83 c4 0c                   add     r12, 0xc          ; next descriptor
4000df: 41 ff cd                      dec     r13d
4000e2: 0f 85 b8 ff ff ff             jne     0x4000a0

4000e8: b8 3c 00 00 00                mov     eax, 0x3c         ; exit(0)
4000ed: 31 ff                         xor     edi, edi
4000ef: 0f 05                         syscall
4000f1: b8 3c 00 00 00                mov     eax, 0x3c         ; exit(1)
4000f6: bf 01 00 00 00                mov     edi, 0x1
4000fb: 0f 05                         syscall
```

## Checked Descriptors

```text
0x784 len 0x09 -> notes-x64
0x824 len 0x05 -> Note:
0x870 len 0x05 -> Words
0x764 len 0x04 -> 20 20 20 00
0x7b4 len 0x08 -> e0 e0 e0 00 20 20 20 00
0x83e len 0x20 -> 2d 3d 08 00 71 77 65 72 74 79 75 69 6f 70 5b 5d
                  0a 00 61 73 64 66 67 68 6a 6b 6c 3b 27 60 00 5c
0x549 len 0x05 -> e8 dc 03 00 00
0x92a len 0x10 -> 8b 04 25 d8 07 40 00 89 04 25 30 0a 40 00 8b 04
0x078 len 0x05 -> e9 3e 0a 00 00                     (entry -> session bootstrap)
0xa48 len 0x06 -> 48 8b 07 48 85 c0                  (find_env prologue)
0xbce len 0x0a -> b8 29 00 00 00 e9 a5 f4 ff ff      (bootstrap socket-resume)
```

## Embedded path

At `0x4000fd`:

```text
6e 6f 74 65 73 2d 6c 69 6e 75 78 2d 78 38 36 5f 36 34 00
```

ASCII:

```text
notes-linux-x86_64
```

## Syscalls used

Exactly three Linux x86_64 syscalls:

- `2` = `open`
- `17` = `pread64`
- `60` = `exit`

## What this test proves

It proves that the committed Linux product reference binary still contains the
product-specific title, pane labels, colour constants, printable keymap
expansion, and border-helper entry bytes at the expected anchored offsets.

It does **not** prove full GUI runtime behavior. That behavior depends on a live
X11 session whose cookie and socket details match the binary's baked data.
