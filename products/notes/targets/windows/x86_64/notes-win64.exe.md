# `products/notes/notes-win64.exe`

`notes-win64.exe` is a **3072-byte** `PE32+` Windows x86_64 GUI executable.
It uses only Win32 imports and opens a native Notes window under Windows or
Wine.

The current Win64 GUI has the product shape:

- a left multiline editor pane
- a right list pane
- an `Add` button that copies the editor text into the list
- a `Delete` button that removes the selected list item

Typing, cursor movement, selection, copy/paste, and editor scrolling are handled
by the built-in Windows `EDIT` control.

## File layout

```text
0x000..0x03f    64    DOS header
0x040..0x07f    64    DOS stub / padding
0x080..0x187   264    PE signature, COFF header, optional header
0x188..0x1af    40    `.text` section header
0x1b0..0x1ff    80    header padding
0x200..0x5ff  1024    executable code and padding
0x800..0x83f    64    Win32 class names and UI strings
0x900..0x93b    60    import descriptors
0x950..0x96d    30    DLL names
0x980..0xa1f   160    ILT/IAT arrays
0xa30..0xab4   133    imported function hint/name strings
```

The single `.text` section maps file offset `0x200` to RVA `0x1000`.

## Header anchors

At `0x000`:

```text
4d 5a
```

At `0x084`:

```text
64 86
```

This is the AMD64 PE machine type.

At `0x0dc`:

```text
02 00
```

This is `IMAGE_SUBSYSTEM_WINDOWS_GUI`.

The import data directory at `0x110` is:

```text
00 17 00 00 3c 00 00 00
```

meaning import descriptors start at RVA `0x1700` and span `0x3c` bytes.

## Code walkthrough (file `0x200` / VA `0x140001000`)

The `.text` section maps file offset `0x200` to RVA `0x1000`, so the file
offset of any VA below is `VA − 0x140000000 − 0xE00`. The PE container
mechanics — the DOS/COFF/optional headers, the `ff 15 disp32`
RIP-relative-indirect call idiom, and how the loader patches the IAT — are
identical in shape to the poc-08 greeter and are documented byte-by-byte in
[`experiments/poc-08-windows-pe/hello.exe.md`](../../../../../experiments/poc-08-windows-pe/hello.exe.md#how-the-indirect-calls-resolve).
Here every `call qword [rip+disp]` resolves to one of seven IAT slots:

| IAT slot (VA) | Function | Called from |
| ------------- | -------- | ----------- |
| `0x1400017c0` | `CreateWindowExA`  | `0x1065`, `0x10c8`, `0x1127`, `0x118a`, `0x11ed` |
| `0x1400017c8` | `GetMessageA`      | `0x1233` |
| `0x1400017d0` | `TranslateMessage` | `0x12da` |
| `0x1400017d8` | `DispatchMessageA` | `0x12e5` |
| `0x1400017e0` | `IsWindow`         | `0x12ee` |
| `0x1400017e8` | `SendMessageA`     | `0x1208`, `0x1220`, `0x126b`, `0x128e`, `0x12b6`, `0x12cf` |
| `0x140001810` | `ExitProcess`      | `0x12fe` |

("Called from" gives the low 16 bits of the call VA.)

Window handles live in callee-saved registers for the whole run: `rbx` =
parent window, `r12` = EDIT, `r13` = LISTBOX, `r14` = Add button, `r15` =
Delete button. The 12-argument `CreateWindowExA` calls put args 1–4 in
`rcx/rdx/r8/r9` and args 5–12 on the stack at `[rsp+0x20]..[rsp+0x58]`, per
the Windows x64 convention.

### Prologue and parent window (`0x1000..0x106d`)

```text
140001000: 48 81 ec e8 01 00 00   sub  rsp, 0x1e8          ; home space + MSG struct + text buffer
140001007: 31 c9                  xor  ecx, ecx            ; dwExStyle = 0
140001009: 48 8d 15 f0 05 00 00   lea  rdx, [rip+0x5f0]    ; 0x140001600 = "STATIC" (class)
140001010: 4c 8d 05 04 06 00 00   lea  r8,  [rip+0x604]    ; 0x14000161b = "Notes x64" (title)
140001017: 41 b9 00 00 cf 10      mov  r9d, 0x10cf0000     ; WS_VISIBLE | WS_OVERLAPPEDWINDOW
14000101d: 48 c7 44 24 20 32 00 00 00  mov QWORD [rsp+0x20], 0x32   ; x = 50
140001026: 48 c7 44 24 28 32 00 00 00  mov QWORD [rsp+0x28], 0x32   ; y = 50
14000102f: 48 c7 44 24 30 a8 02 00 00  mov QWORD [rsp+0x30], 0x2a8  ; width = 680
140001038: 48 c7 44 24 38 a4 01 00 00  mov QWORD [rsp+0x38], 0x1a4  ; height = 420
140001041: 48 c7 44 24 40 00 00 00 00  mov QWORD [rsp+0x40], 0      ; hWndParent = NULL
14000104a: 48 c7 44 24 48 00 00 00 00  mov QWORD [rsp+0x48], 0      ; hMenu = NULL
140001053: 48 c7 44 24 50 00 00 00 00  mov QWORD [rsp+0x50], 0      ; hInstance = NULL
14000105c: 48 c7 44 24 58 00 00 00 00  mov QWORD [rsp+0x58], 0      ; lpParam = NULL
140001065: ff 15 55 07 00 00      call QWORD [rip+0x755]   ; [0x1400017c0] CreateWindowExA
14000106b: 48 89 c3               mov  rbx, rax            ; rbx = parent hwnd
```

Style `0x10cf0000` = `WS_VISIBLE (0x10000000) | WS_OVERLAPPEDWINDOW
(0x00CF0000)`. The parent uses the built-in `STATIC` class, so it has no
custom window procedure — all product behaviour happens in the message loop
below.

### EDIT child — left editor pane (`0x106e..0x10d0`)

Same 12-arg shape; only the changed values are annotated:

```text
14000106e: 31 c9                  xor  ecx, ecx
140001070: 48 8d 15 90 05 00 00   lea  rdx, [rip+0x590]    ; 0x140001607 = "EDIT"
140001077: 4c 8d 05 a7 05 00 00   lea  r8,  [rip+0x5a7]    ; 0x140001625 = "Type notes here."
14000107e: 41 b9 44 10 a0 50      mov  r9d, 0x50a01044     ; see style decode below
140001084: 48 c7 44 24 20 14 00 00 00  mov QWORD [rsp+0x20], 0x14   ; x = 20
14000108d: 48 c7 44 24 28 14 00 00 00  mov QWORD [rsp+0x28], 0x14   ; y = 20
140001096: 48 c7 44 24 30 a4 01 00 00  mov QWORD [rsp+0x30], 0x1a4  ; width = 420
14000109f: 48 c7 44 24 38 4a 01 00 00  mov QWORD [rsp+0x38], 0x14a  ; height = 330
1400010a8: 48 89 5c 24 40         mov  QWORD [rsp+0x40], rbx       ; parent = main window
1400010ad: 48 c7 44 24 48 00 00 00 00  mov QWORD [rsp+0x48], 0
1400010b6: 48 c7 44 24 50 00 00 00 00  mov QWORD [rsp+0x50], 0
1400010bf: 48 c7 44 24 58 00 00 00 00  mov QWORD [rsp+0x58], 0
1400010c8: ff 15 f2 06 00 00      call QWORD [rip+0x6f2]   ; [0x1400017c0] CreateWindowExA
1400010ce: 49 89 c4               mov  r12, rax            ; r12 = edit hwnd
```

Style `0x50a01044` = `WS_CHILD (0x40000000) | WS_VISIBLE (0x10000000) |
WS_BORDER (0x00800000) | WS_VSCROLL (0x00200000) | ES_WANTRETURN (0x1000) |
ES_AUTOVSCROLL (0x0040) | ES_MULTILINE (0x0004)`. This is what delegates all
typing, cursor, selection, and clipboard behaviour to the built-in `EDIT`
class — the binary contains no text-editing code of its own.

### LISTBOX child — right list pane (`0x10d1..0x112f`)

```text
1400010d1: 31 c9                  xor  ecx, ecx
1400010d3: 48 8d 15 32 05 00 00   lea  rdx, [rip+0x532]    ; 0x14000160c = "LISTBOX"
1400010da: 45 31 c0               xor  r8d, r8d            ; no title
1400010dd: 41 b9 01 00 a0 50      mov  r9d, 0x50a00001     ; WS_CHILD|WS_VISIBLE|WS_BORDER|WS_VSCROLL|LBS_NOTIFY
1400010e3: 48 c7 44 24 20 cc 01 00 00  mov QWORD [rsp+0x20], 0x1cc  ; x = 460
1400010ec: 48 c7 44 24 28 14 00 00 00  mov QWORD [rsp+0x28], 0x14   ; y = 20
1400010f5: 48 c7 44 24 30 b4 00 00 00  mov QWORD [rsp+0x30], 0xb4   ; width = 180
1400010fe: 48 c7 44 24 38 18 01 00 00  mov QWORD [rsp+0x38], 0x118  ; height = 280
140001107: 48 89 5c 24 40         mov  QWORD [rsp+0x40], rbx
14000110c: (three zero stores as above)
140001127: ff 15 93 06 00 00      call QWORD [rip+0x693]   ; [0x1400017c0] CreateWindowExA
14000112d: 49 89 c5               mov  r13, rax            ; r13 = listbox hwnd
```

### Add and Delete buttons (`0x1130..0x11f5`)

Two more `CreateWindowExA` calls with class `"BUTTON"` (`0x140001614`), style
`0x50000000` (`WS_CHILD | WS_VISIBLE`), size 80×30 at y = 310:

```text
140001130: ... rdx = "BUTTON", r8 = 0x140001636 "Add",    x = 0x1cc (460)
14000118a: ff 15 30 06 00 00      call QWORD [rip+0x630]   ; CreateWindowExA
140001190: 49 89 c6               mov  r14, rax            ; r14 = Add hwnd
140001193: ... rdx = "BUTTON", r8 = 0x14000163a "Delete",  x = 0x230 (560)
1400011ed: ff 15 cd 05 00 00      call QWORD [rip+0x5cd]   ; CreateWindowExA
1400011f3: 49 89 c7               mov  r15, rax            ; r15 = Delete hwnd
```

(Bytes between are the same `mov QWORD [rsp+...]` stores as the earlier
blocks, with `y = 0x136` (310), `w = 0x50` (80), `h = 0x1e` (30).)

### Seed the list (`0x11f6..0x1225`)

`LB_ADDSTRING` is message `0x180`; `SendMessageA(hwnd, msg, wParam, lParam)`
takes the string pointer in `lParam` (`r9`):

```text
1400011f6: 4c 89 e9               mov  rcx, r13            ; listbox
1400011f9: ba 80 01 00 00         mov  edx, 0x180          ; LB_ADDSTRING
1400011fe: 45 31 c0               xor  r8d, r8d            ; wParam = 0
140001201: 4c 8d 0d 39 04 00 00   lea  r9, [rip+0x439]     ; 0x140001641 = "First note"
140001208: ff 15 da 05 00 00      call QWORD [rip+0x5da]   ; [0x1400017e8] SendMessageA
14000120e: 4c 89 e9               mov  rcx, r13
140001211: ba 80 01 00 00         mov  edx, 0x180
140001216: 45 31 c0               xor  r8d, r8d
140001219: 4c 8d 0d 2c 04 00 00   lea  r9, [rip+0x42c]     ; 0x14000164c = "Second note"
140001220: ff 15 c2 05 00 00      call QWORD [rip+0x5c2]   ; SendMessageA
```

### Message loop (`0x1226..0x12fb`)

The `MSG` structure lives at `[rsp+0x20]` (hwnd at `+0x20`, message code at
`+0x28`); a 128-byte text buffer lives at `[rsp+0x100]`. The loop peeks at
each message *before* dispatching it and implements Add/Delete inline when the
message is a `WM_LBUTTONUP` (`0x202`) addressed to one of the two button
windows:

```text
; --- fetch the next message ---
140001226: 48 8d 4c 24 20         lea  rcx, [rsp+0x20]     ; &msg
14000122b: 31 d2                  xor  edx, edx            ; hWnd filter = NULL
14000122d: 45 31 c0               xor  r8d, r8d            ; wMsgFilterMin = 0
140001230: 45 31 c9               xor  r9d, r9d            ; wMsgFilterMax = 0
140001233: ff 15 8f 05 00 00      call QWORD [rip+0x58f]   ; [0x1400017c8] GetMessageA
140001239: 85 c0                  test eax, eax
14000123b: 0f 8e bb 00 00 00      jle  0x1400012fc         ; 0 = WM_QUIT, -1 = error → exit
; --- Add button: WM_LBUTTONUP on r14? ---
140001241: 48 8b 44 24 20         mov  rax, [rsp+0x20]     ; msg.hwnd
140001246: 4c 39 f0               cmp  rax, r14
140001249: 75 49                  jne  0x140001294         ; not the Add button → try Delete
14000124b: 81 7c 24 28 02 02 00 00  cmp DWORD [rsp+0x28], 0x202  ; WM_LBUTTONUP?
140001253: 75 3f                  jne  0x140001294
140001255: 4c 89 e1               mov  rcx, r12            ; EDIT control
140001258: ba 0d 00 00 00         mov  edx, 0xd            ; WM_GETTEXT
14000125d: 41 b8 80 00 00 00      mov  r8d, 0x80           ; max 128 chars
140001263: 4c 8d 8c 24 00 01 00 00  lea r9, [rsp+0x100]    ; destination buffer
14000126b: ff 15 77 05 00 00      call QWORD [rip+0x577]   ; SendMessageA
140001271: 80 bc 24 00 01 00 00 00  cmp BYTE [rsp+0x100], 0  ; empty text?
140001279: 74 19                  je   0x140001294         ; yes → don't add
14000127b: 4c 89 e9               mov  rcx, r13            ; listbox
14000127e: ba 80 01 00 00         mov  edx, 0x180          ; LB_ADDSTRING
140001283: 45 31 c0               xor  r8d, r8d
140001286: 4c 8d 8c 24 00 01 00 00  lea r9, [rsp+0x100]    ; the fetched text
14000128e: ff 15 54 05 00 00      call QWORD [rip+0x554]   ; SendMessageA
; --- Delete button: WM_LBUTTONUP on r15? ---
140001294: 48 8b 44 24 20         mov  rax, [rsp+0x20]
140001299: 4c 39 f8               cmp  rax, r15
14000129c: 75 37                  jne  0x1400012d5         ; not the Delete button → dispatch
14000129e: 81 7c 24 28 02 02 00 00  cmp DWORD [rsp+0x28], 0x202
1400012a6: 75 2d                  jne  0x1400012d5
1400012a8: 4c 89 e9               mov  rcx, r13
1400012ab: ba 88 01 00 00         mov  edx, 0x188          ; LB_GETCURSEL
1400012b0: 45 31 c0               xor  r8d, r8d
1400012b3: 45 31 c9               xor  r9d, r9d
1400012b6: ff 15 2c 05 00 00      call QWORD [rip+0x52c]   ; SendMessageA → selected index
1400012bc: 83 f8 ff               cmp  eax, 0xffffffff     ; LB_ERR = no selection
1400012bf: 74 14                  je   0x1400012d5
1400012c1: 4c 63 c0               movsxd r8, eax           ; wParam = selected index
1400012c4: 4c 89 e9               mov  rcx, r13
1400012c7: ba 82 01 00 00         mov  edx, 0x182          ; LB_DELETESTRING
1400012cc: 45 31 c9               xor  r9d, r9d
1400012cf: ff 15 13 05 00 00      call QWORD [rip+0x513]   ; SendMessageA
; --- normal dispatch + liveness check ---
1400012d5: 48 8d 4c 24 20         lea  rcx, [rsp+0x20]
1400012da: ff 15 f0 04 00 00      call QWORD [rip+0x4f0]   ; [0x1400017d0] TranslateMessage
1400012e0: 48 8d 4c 24 20         lea  rcx, [rsp+0x20]
1400012e5: ff 15 ed 04 00 00      call QWORD [rip+0x4ed]   ; [0x1400017d8] DispatchMessageA
1400012eb: 48 89 d9               mov  rcx, rbx            ; parent hwnd
1400012ee: ff 15 ec 04 00 00      call QWORD [rip+0x4ec]   ; [0x1400017e0] IsWindow
1400012f4: 85 c0                  test eax, eax
1400012f6: 0f 85 2a ff ff ff      jne  0x140001226         ; still alive → next message
```

The `IsWindow(parent)` check is the app's close-detection: when the user
closes the window, `DefWindowProc`'s `WM_CLOSE` handling destroys it, the next
`IsWindow` returns 0, and the loop falls through to exit. (A `STATIC`-class
window never posts `WM_QUIT`, so `GetMessageA` alone would not terminate.)

### Exit (`0x12fc..0x1303`)

```text
1400012fc: 31 c9                  xor  ecx, ecx            ; exit code 0
1400012fe: ff 15 0c 05 00 00      call QWORD [rip+0x50c]   ; [0x140001810] ExitProcess
```

The rest of the code region (`0x1304..0x15ff`) is zero padding.

## Strings

The UI strings are NUL-terminated ASCII at these file offsets (VA =
offset + `0x140000E00`), consumed directly by `CreateWindowExA` /
`SendMessageA`:

```text
0x800: "STATIC"            0x81b: "Notes x64"
0x807: "EDIT"              0x825: "Type notes here."
0x80c: "LISTBOX"           0x836: "Add"
0x814: "BUTTON"            0x83a: "Delete"
                           0x841: "First note"
                           0x84c: "Second note"
```

## Imports

The import table starts at file offset `0x900` / RVA `0x1700` — two
`IMAGE_IMPORT_DESCRIPTOR`s plus a zero terminator (the structure is decoded
field-by-field in
[`experiments/poc-08-windows-pe/hello.exe.md`](../../../../../experiments/poc-08-windows-pe/hello.exe.md#import-descriptor)):

```text
0x900: OFT=0x1780  Name=0x1750 ("USER32.dll")    FirstThunk(IAT)=0x17c0
0x914: OFT=0x1800  Name=0x1760 ("KERNEL32.dll")  FirstThunk(IAT)=0x1810
0x928: terminator
```

`USER32.dll` provides `CreateWindowExA`, `GetMessageA`, `TranslateMessage`,
`DispatchMessageA`, `IsWindow`, and `SendMessageA`; `KERNEL32.dll` provides
`ExitProcess`. Hint/name entries (all hint `0`, lookup by name):

```text
0x950: USER32.dll          0xa30: CreateWindowExA   (RVA 0x1830)
0x960: KERNEL32.dll        0xa48: GetMessageA       (RVA 0x1848)
                           0xa58: TranslateMessage  (RVA 0x1858)
                           0xa70: DispatchMessageA  (RVA 0x1870)
                           0xa88: IsWindow          (RVA 0x1888)
                           0xa98: SendMessageA      (RVA 0x1898)
                           0xaa8: ExitProcess       (RVA 0x18a8)
```

The loader overwrites the IAT slots at RVA `0x17c0..0x17f0` (USER32) and
`0x1810` (KERNEL32) with resolved addresses; those slots are exactly what the
`call qword [rip+disp]` instructions in the code reference.

One known quirk: the optional header's IAT data-directory entry (index 12, at
file offset `0x168`) still reads `RVA 0x10a0, size 0x20` — a stale value
inherited from the poc-08 layout. Import resolution does not depend on that
directory (the loader binds via the descriptors' `FirstThunk` fields), so the
binary loads and runs correctly regardless; the entry is only an optimization
hint for the loader's page-protection handling.

## Verification

`test-notes-win64` checks the PE signature, AMD64 machine type, GUI subsystem,
code prefix, control class strings, `Add`/`Delete` labels, the
`LB_DELETESTRING` instruction, and the `SendMessageA` import.

If Wine is installed, run:

```bash
cd products/notes/targets/windows/x86_64
/usr/lib/wine/wine64 ./notes-win64.exe
```

On systems where `wine` launches 64-bit PE files without requiring 32-bit Wine
support:

```bash
wine ./notes-win64.exe
```
