# `products/notes/notes-win64.exe`

`notes-win64.exe` is a **4608-byte** `PE32+` Windows x86_64 GUI executable.
It uses only Win32 imports and opens a native Notes window under Windows or
Wine.

The current Win64 GUI is a genuinely persistent notes app:

- a left multiline editor pane
- a right list pane populated from `notes.db` at startup (no more seeded
  placeholder notes)
- an `Add` button that copies the editor text into the list **and rewrites
  `notes.db`**
- a `Delete` button that removes the selected list item **and rewrites
  `notes.db`**
- clicking a list row loads that note's text back into the editor

Persistence uses the same shared `[u32 length][length bytes of text]` record
format as the other Notes targets (see the [product contract](../../../contract.md)).
Typing, cursor movement, selection, copy/paste, and editor scrolling are handled
by the built-in Windows `EDIT` control. Because that editor is multiline
(`ES_WANTRETURN`), `Enter` inserts a newline; the `Add` button is the explicit
save action, matching the "Enter/save" role on the other targets.

## File layout

```text
0x000..0x03f    64    DOS header
0x040..0x07f    64    DOS stub / padding
0x080..0x187   264    PE signature, COFF header, optional header
0x188..0x1af    40    `.text` section header
0x1b0..0x1ff    80    header padding
0x200..0x5ff  1024    original executable code (message loop etc.) + repointed calls
0x600..0x69d   158    new KERNEL32 IAT/ILT arrays, hint/names, "notes.db"
0x800..0x85b    92    Win32 class names and UI strings
0x900..0x93b    60    import descriptors (KERNEL32 OFT/FirstThunk repointed)
0x950..0x96d    30    DLL names
0x980..0xa1f   160    USER32 ILT/IAT arrays
0xa30..0xab4   133    imported function hint/name strings
0xb00..0xd6d   622    new persistence + click-to-load code
0xd6e..0x11ff        zero padding to the grown raw size
```

The single `.text` section maps file offset `0x200` to RVA `0x1000`. To hold
the new code and import arrays, its `VirtualSize` and `SizeOfRawData` were both
grown from `0x900`/`0xa00` to `0x1000` (the section still ends at RVA `0x2000`,
matching `SizeOfImage`), and the file was extended to `0x1200`.

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
Here every `call qword [rip+disp]` resolves to one of these IAT slots. The
USER32 slots are unchanged from the original layout; the KERNEL32 slots were
moved into a new array at RVA `0x1400` (file `0x600`) so that `CreateFileA`,
`ReadFile`, `WriteFile`, and `CloseHandle` could be added alongside
`ExitProcess`:

| IAT slot (VA) | Function | Called from |
| ------------- | -------- | ----------- |
| `0x1400017c0` | `CreateWindowExA`  | `0x1065`, `0x10c8`, `0x1127`, `0x118a`, `0x11ed` |
| `0x1400017c8` | `GetMessageA`      | `0x1233` |
| `0x1400017d0` | `TranslateMessage` | `0x12da` (via `disp_hook`) |
| `0x1400017d8` | `DispatchMessageA` | `0x12e5` |
| `0x1400017e0` | `IsWindow`         | `0x12ee` |
| `0x1400017e8` | `SendMessageA`     | `0x126b`, `0x128e` (via `save_trampoline`), `0x12b6`, `0x12cf` (via `save_trampoline`), and the new persistence/hook code |
| `0x140001400` | `ExitProcess`      | `0x12fe` |
| `0x140001408` | `CreateFileA`      | `load_notes` `0x1b08`, `save_notes` `0x1c08` |
| `0x140001410` | `ReadFile`         | `load_notes` |
| `0x140001418` | `WriteFile`        | `save_notes` |
| `0x140001420` | `CloseHandle`      | `load_notes`, `save_notes` |

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

### Load from `notes.db` (`0x11f6..0x1225`)

The original build seeded two fake list entries here with two `LB_ADDSTRING`
`SendMessageA` calls. That block is now replaced by a single call to the new
`load_notes` routine (documented below), followed by `nop` padding out to the
message loop entry at `0x1226`:

```text
1400011f6: e8 05 07 00 00         call 0x140001b00         ; load_notes (file 0x3f6 → 0xb00)
1400011fb: 90 … 90                nop  × 0x2b              ; pad to 0x1226
```

`load_notes` opens `notes.db`, walks its `[u32 length][bytes]` records, and
issues one `LB_ADDSTRING` per record, so the list pane reflects whatever was
last saved. The two seed strings ("First note", "Second note") remain in the
string area at `0x841`/`0x84c` but are no longer referenced.

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
14000128e: e8 c6 08 00 00         call 0x140001d59         ; save_trampoline (was direct SendMessageA)
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
1400012cf: e8 85 08 00 00         call 0x140001d59         ; save_trampoline (was direct SendMessageA)
; --- click-to-load hook, then dispatch + liveness check ---
1400012d4: 90                     nop                      ; padding from the shortened lea
1400012d5: e9 16 08 00 00         jmp  0x140001cf0         ; disp_hook (returns to 0x12da)
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
1400012fe: ff 15 fc 00 00 00      call QWORD [rip+0xfc]    ; [0x140001400] ExitProcess
```

The displacement changed from `0x50c` to `0xfc` because the `ExitProcess` IAT
slot moved from `0x140001810` to the relocated KERNEL32 array at
`0x140001400`. No save runs here: every `Add` and `Delete` already rewrites
`notes.db` through `save_trampoline`, so the file is always current when the
window closes.

The rest of the original code region (`0x1304..0x15ff`) is zero padding.

## Persistence and click-to-load code (file `0xb00` / VA `0x140001b00`)

Four new routines occupy the grown `.text` tail. All addresses below are VAs;
subtract `0x140000e00` for the file offset. RIP-relative string/IAT references
resolve to the new data block at `0x600` and the relocated KERNEL32 IAT at
`0x1400`.

### `load_notes` (`0x1b00..0x1bfe`)

Called once at startup in place of the seed block. Opens `notes.db`
`GENERIC_READ` / `OPEN_EXISTING`; on success it repeatedly reads a 4-byte
length then that many text bytes, NUL-terminates each record in a stack buffer,
and sends `LB_ADDSTRING` (`0x180`) to the listbox (`r13`). A zero-length read
or `ReadFile` failure ends the loop; the handle is closed before return.

```text
140001b00: 56                       push rsi
140001b01: 48 81 ec 40 01 00 00     sub  rsp, 0x140
140001b08: 48 8d 0d 85 fb ff ff     lea  rcx, [rip-0x47b]   ; 0x140001694 = "notes.db"
140001b0f: ba 00 00 00 80           mov  edx, 0x80000000    ; GENERIC_READ
140001b14: 41 b8 01 00 00 00        mov  r8d, 1             ; FILE_SHARE_READ
140001b1a: 45 31 c9                 xor  r9d, r9d           ; no security attrs
140001b1d: 48 c7 44 24 20 03 00 00 00  mov QWORD [rsp+0x20], 3   ; OPEN_EXISTING
140001b26: 48 c7 44 24 28 00 00 00 00  mov QWORD [rsp+0x28], 0
140001b2f: 48 c7 44 24 30 00 00 00 00  mov QWORD [rsp+0x30], 0
140001b38: ff 15 ca fa ff ff        call QWORD [rip-0x536]  ; [0x140001408] CreateFileA
140001b3e: 48 83 f8 ff              cmp  rax, -1            ; INVALID_HANDLE_VALUE
140001b42: 0f 84 ae 00 00 00        je   0x140001bf6        ; no file → return
140001b48: 48 89 c6                 mov  rsi, rax           ; rsi = hFile
; --- per-record loop ---
140001b4b: 48 89 f1                 mov  rcx, rsi
140001b4e: 48 8d 54 24 38           lea  rdx, [rsp+0x38]    ; &len
140001b53: 41 b8 04 00 00 00        mov  r8d, 4             ; read 4 length bytes
140001b59: 4c 8d 4c 24 34           lea  r9, [rsp+0x34]     ; &bytesRead
140001b5e: 48 c7 44 24 20 00 00 00 00  mov QWORD [rsp+0x20], 0  ; lpOverlapped
140001b67: ff 15 a3 fa ff ff        call QWORD [rip-0x55d]  ; [0x140001410] ReadFile
140001b6d: 85 c0                    test eax, eax
140001b6f: 0f 84 78 00 00 00        je   0x140001bed        ; ReadFile failed → close
140001b75: 83 7c 24 34 04           cmp  DWORD [rsp+0x34], 4 ; got 4 bytes?
140001b7a: 0f 85 6d 00 00 00        jne  0x140001bed        ; short/EOF → close
140001b80: 8b 4c 24 38              mov  ecx, [rsp+0x38]     ; len
140001b84: 85 c9                    test ecx, ecx
140001b86: 0f 8e 61 00 00 00        jle  0x140001bed         ; len<=0 → close
140001b8c: 83 f9 7f                 cmp  ecx, 0x7f           ; clamp to buffer
140001b8f: 0f 8f 58 00 00 00        jg   0x140001bed
140001b95: 41 89 c8                 mov  r8d, ecx            ; nbytes = len
140001b98: 48 89 f1                 mov  rcx, rsi
140001b9b: 48 8d 54 24 50           lea  rdx, [rsp+0x50]     ; text buffer
140001ba0: 4c 8d 4c 24 34           lea  r9, [rsp+0x34]      ; &bytesRead
140001ba5: 48 c7 44 24 20 00 00 00 00  mov QWORD [rsp+0x20], 0
140001bae: ff 15 5c fa ff ff        call QWORD [rip-0x5a4]  ; [0x140001410] ReadFile
140001bb4: 85 c0                    test eax, eax
140001bb6: 0f 84 31 00 00 00        je   0x140001bed
140001bbc: 8b 44 24 34              mov  eax, [rsp+0x34]     ; bytes actually read
140001bc0: 85 c0                    test eax, eax
140001bc2: 74 09                    je   0x140001bcd
140001bc4: 80 7c 04 4f 0a           cmp  BYTE [rsp+rax+0x4f], 0x0a  ; trailing '\n'?
140001bc9: 75 02                    jne  0x140001bcd
140001bcb: ff c8                    dec  eax                 ; drop it
140001bcd: c6 44 04 50 00           mov  BYTE [rsp+rax+0x50], 0     ; NUL-terminate
140001bd2: 4c 89 e9                 mov  rcx, r13            ; listbox
140001bd5: ba 80 01 00 00           mov  edx, 0x180          ; LB_ADDSTRING
140001bda: 45 31 c0                 xor  r8d, r8d
140001bdd: 4c 8d 4c 24 50           lea  r9, [rsp+0x50]      ; the record text
140001be2: ff 15 00 fe ff ff        call QWORD [rip-0x200]  ; [0x1400017e8] SendMessageA
140001be8: e9 5e ff ff ff           jmp  0x140001b4b         ; next record
; --- close and return ---
140001bed: 48 89 f1                 mov  rcx, rsi
140001bf0: ff 15 2a fa ff ff        call QWORD [rip-0x5d6]  ; [0x140001420] CloseHandle
140001bf6: 48 81 c4 40 01 00 00     add  rsp, 0x140
140001bfd: 5e                       pop  rsi
140001bfe: c3                       ret
```

### `save_notes` (`0x1c00..0x1cef`)

Rewrites `notes.db` from scratch (`CREATE_ALWAYS`) whenever a note is added or
deleted. It queries the listbox item count (`LB_GETCOUNT` `0x18b`), then for
each row fetches the text (`LB_GETTEXT` `0x189`) and writes a `[u32
length][bytes]` record — the shared cross-target format.

```text
140001c00: 56                       push rsi
140001c01: 48 81 ec 60 01 00 00     sub  rsp, 0x160
140001c08: 48 8d 0d 85 fa ff ff     lea  rcx, [rip-0x57b]   ; "notes.db"
140001c0f: ba 00 00 00 40           mov  edx, 0x40000000    ; GENERIC_WRITE
140001c14: 45 31 c0                 xor  r8d, r8d
140001c17: 45 31 c9                 xor  r9d, r9d
140001c1a: 48 c7 44 24 20 02 00 00 00  mov QWORD [rsp+0x20], 2   ; CREATE_ALWAYS
140001c23: 48 c7 44 24 28 00 00 00 00  mov QWORD [rsp+0x28], 0
140001c2c: 48 c7 44 24 30 00 00 00 00  mov QWORD [rsp+0x30], 0
140001c35: ff 15 cd f9 ff ff        call QWORD [rip-0x633]  ; [0x140001408] CreateFileA
140001c3b: 48 83 f8 ff              cmp  rax, -1
140001c3f: 0f 84 a2 00 00 00        je   0x140001ce7        ; open failed → return
140001c45: 48 89 c6                 mov  rsi, rax            ; hFile
140001c48: 4c 89 e9                 mov  rcx, r13
140001c4b: ba 8b 01 00 00           mov  edx, 0x18b          ; LB_GETCOUNT
140001c50: 45 31 c0                 xor  r8d, r8d
140001c53: 45 31 c9                 xor  r9d, r9d
140001c56: ff 15 8c fd ff ff        call QWORD [rip-0x274]  ; [0x1400017e8] SendMessageA
140001c5c: 89 44 24 3c              mov  [rsp+0x3c], eax     ; count
140001c60: c7 44 24 38 00 00 00 00  mov  DWORD [rsp+0x38], 0 ; i = 0
; --- per-row loop ---
140001c68: 8b 44 24 38              mov  eax, [rsp+0x38]
140001c6c: 3b 44 24 3c              cmp  eax, [rsp+0x3c]
140001c70: 0f 8d 68 00 00 00        jge  0x140001cde        ; done
140001c76: 4c 63 44 24 38           movsxd r8, DWORD [rsp+0x38]  ; wParam = i
140001c7b: 4c 89 e9                 mov  rcx, r13
140001c7e: ba 89 01 00 00           mov  edx, 0x189          ; LB_GETTEXT
140001c83: 4c 8d 4c 24 50           lea  r9, [rsp+0x50]      ; text buffer
140001c88: ff 15 5a fd ff ff        call QWORD [rip-0x2a6]  ; SendMessageA → length
140001c8e: 89 44 24 40              mov  [rsp+0x40], eax     ; len (also the u32 prefix)
140001c92: 48 89 f1                 mov  rcx, rsi
140001c95: 48 8d 54 24 40           lea  rdx, [rsp+0x40]     ; &len
140001c9a: 41 b8 04 00 00 00        mov  r8d, 4              ; write 4-byte prefix
140001ca0: 4c 8d 4c 24 34           lea  r9, [rsp+0x34]
140001ca5: 48 c7 44 24 20 00 00 00 00  mov QWORD [rsp+0x20], 0
140001cae: ff 15 64 f9 ff ff        call QWORD [rip-0x69c]  ; [0x140001418] WriteFile
140001cb4: 44 8b 44 24 40           mov  r8d, [rsp+0x40]     ; nbytes = len
140001cb9: 48 89 f1                 mov  rcx, rsi
140001cbc: 48 8d 54 24 50           lea  rdx, [rsp+0x50]     ; text bytes
140001cc1: 4c 8d 4c 24 34           lea  r9, [rsp+0x34]
140001cc6: 48 c7 44 24 20 00 00 00 00  mov QWORD [rsp+0x20], 0
140001ccf: ff 15 43 f9 ff ff        call QWORD [rip-0x6bd]  ; [0x140001418] WriteFile
140001cd5: ff 44 24 38              inc  DWORD [rsp+0x38]    ; i++
140001cd9: e9 8a ff ff ff           jmp  0x140001c68
; --- close and return ---
140001cde: 48 89 f1                 mov  rcx, rsi
140001ce1: ff 15 39 f9 ff ff        call QWORD [rip-0x6c7]  ; [0x140001420] CloseHandle
140001ce7: 48 81 c4 60 01 00 00     add  rsp, 0x160
140001cee: 5e                       pop  rsi
140001cef: c3                       ret
```

### `disp_hook` (`0x1cf0..0x1d58`)

Reached by the `jmp` that replaced the pre-`TranslateMessage` `lea`. It runs on
every message but only acts on a `WM_LBUTTONUP` (`0x202`) whose `hwnd` is the
listbox (`r13`). Because the preceding `WM_LBUTTONDOWN` was already dispatched
(updating the selection) in an earlier loop iteration, `LB_GETCURSEL` (`0x188`)
now returns the clicked row; its text is fetched with `LB_GETTEXT` and pushed
into the editor with `WM_SETTEXT` (`0x0c`). It then performs the original
`lea rcx,[rsp+0x20]` and jumps back to the `TranslateMessage` call.

```text
140001cf0: 48 8b 44 24 20           mov  rax, [rsp+0x20]     ; msg.hwnd
140001cf5: 4c 39 e8                 cmp  rax, r13            ; listbox?
140001cf8: 75 55                    jne  0x140001d4f         ; no → dispatch as usual
140001cfa: 81 7c 24 28 02 02 00 00  cmp  DWORD [rsp+0x28], 0x202  ; WM_LBUTTONUP?
140001d02: 75 4b                    jne  0x140001d4f
140001d04: 4c 89 e9                 mov  rcx, r13
140001d07: ba 88 01 00 00           mov  edx, 0x188          ; LB_GETCURSEL
140001d0c: 45 31 c0                 xor  r8d, r8d
140001d0f: 45 31 c9                 xor  r9d, r9d
140001d12: ff 15 d0 fc ff ff        call QWORD [rip-0x330]  ; SendMessageA → index
140001d18: 83 f8 ff                 cmp  eax, -1             ; LB_ERR = nothing selected
140001d1b: 74 32                    je   0x140001d4f
140001d1d: 4c 63 c0                 movsxd r8, eax           ; wParam = index
140001d20: 4c 89 e9                 mov  rcx, r13
140001d23: ba 89 01 00 00           mov  edx, 0x189          ; LB_GETTEXT
140001d28: 4c 8d 8c 24 00 01 00 00  lea  r9, [rsp+0x100]     ; text buffer
140001d30: ff 15 b2 fc ff ff        call QWORD [rip-0x34e]  ; SendMessageA
140001d36: 4c 89 e1                 mov  rcx, r12            ; EDIT control
140001d39: ba 0c 00 00 00           mov  edx, 0xc            ; WM_SETTEXT
140001d3e: 45 31 c0                 xor  r8d, r8d
140001d41: 4c 8d 8c 24 00 01 00 00  lea  r9, [rsp+0x100]     ; loaded note text
140001d49: ff 15 99 fc ff ff        call QWORD [rip-0x367]  ; SendMessageA
140001d4f: 48 8d 4c 24 20           lea  rcx, [rsp+0x20]     ; original &msg
140001d54: e9 81 f7 ff ff           jmp  0x140001cda         ; back to TranslateMessage
```

### `save_trampoline` (`0x1d59..0x1d6c`)

The `Add` and `Delete` handlers `call` this thin wrapper instead of
`SendMessageA` directly. It forwards the already-loaded `rcx/rdx/r8/r9`
arguments to `SendMessageA` (performing the `LB_ADDSTRING` / `LB_DELETESTRING`),
then calls `save_notes` so the file always mirrors the list. Its `sub rsp,0x28`
plus the two `call` pushes keep 16-byte stack alignment consistent with the
direct calls it replaced.

```text
140001d59: 48 83 ec 28              sub  rsp, 0x28           ; shadow space + align
140001d5d: ff 15 85 fc ff ff        call QWORD [rip-0x37b]  ; [0x1400017e8] SendMessageA
140001d63: e8 98 fe ff ff           call 0x140001c00         ; save_notes
140001d68: 48 83 c4 28              add  rsp, 0x28
140001d6c: c3                       ret
```

## Strings

The UI strings are NUL-terminated ASCII at these file offsets (VA =
offset + `0x140000E00`), consumed directly by `CreateWindowExA` /
`SendMessageA`:

```text
0x800: "STATIC"            0x81b: "Notes x64"
0x807: "EDIT"              0x825: "Type notes here."
0x80c: "LISTBOX"           0x836: "Add"
0x814: "BUTTON"            0x83a: "Delete"
                           0x841: "First note"    (vestigial, unreferenced)
                           0x84c: "Second note"   (vestigial, unreferenced)
```

The persistence filename lives in the new data block:

```text
0x694: "notes.db"
```

## Imports

The import table starts at file offset `0x900` / RVA `0x1700` — two
`IMAGE_IMPORT_DESCRIPTOR`s plus a zero terminator (the structure is decoded
field-by-field in
[`experiments/poc-08-windows-pe/hello.exe.md`](../../../../../experiments/poc-08-windows-pe/hello.exe.md#import-descriptor)).
The USER32 descriptor is unchanged; the KERNEL32 descriptor's `OriginalFirstThunk`
and `FirstThunk` were repointed to the new arrays in the data block so the
loader binds five functions instead of one:

```text
0x900: OFT=0x1780  Name=0x1750 ("USER32.dll")    FirstThunk(IAT)=0x17c0
0x914: OFT=0x1430  Name=0x1760 ("KERNEL32.dll")  FirstThunk(IAT)=0x1400
0x928: terminator
```

`USER32.dll` provides `CreateWindowExA`, `GetMessageA`, `TranslateMessage`,
`DispatchMessageA`, `IsWindow`, and `SendMessageA`. `KERNEL32.dll` now provides
`ExitProcess`, `CreateFileA`, `ReadFile`, `WriteFile`, and `CloseHandle`.

The KERNEL32 IAT (RVA `0x1400`, file `0x600`) and its matching ILT
(RVA `0x1430`, file `0x630`) are five 8-byte entries plus a terminator, each
pointing at a hint/name entry (hint `0`, lookup by name):

```text
0x600 IAT / 0x630 ILT entries → name RVA:
  0x1460  →  0x662: "CreateFileA"
  0x146e  →  0x66e: "ReadFile"
  0x147a  →  0x67a: "WriteFile"
  0x1486  →  0x686: "CloseHandle"
  0x18a8  →  0xaa8: "ExitProcess"   (reuses the original name string)
```

The USER32 hint/name entries stay where they were:

```text
0x950: USER32.dll          0xa30: CreateWindowExA   (RVA 0x1830)
0x960: KERNEL32.dll        0xa48: GetMessageA       (RVA 0x1848)
                           0xa58: TranslateMessage  (RVA 0x1858)
                           0xa70: DispatchMessageA  (RVA 0x1870)
                           0xa88: IsWindow          (RVA 0x1888)
                           0xa98: SendMessageA      (RVA 0x1898)
                           0xaa8: ExitProcess       (RVA 0x18a8)
```

The loader overwrites the IAT slots at RVA `0x17c0..0x17e8` (USER32) and
`0x1400..0x1420` (KERNEL32) with resolved addresses; those slots are exactly
what the `call qword [rip+disp]` instructions in the code reference.

One known quirk: the optional header's IAT data-directory entry (index 12, at
file offset `0x168`) still reads `RVA 0x10a0, size 0x20` — a stale value
inherited from the poc-08 layout. Import resolution does not depend on that
directory (the loader binds via the descriptors' `FirstThunk` fields), so the
binary loads and runs correctly regardless; the entry is only an optimization
hint for the loader's page-protection handling.

## Verification

`test-notes-win64` checks the PE signature, AMD64 machine type, GUI subsystem,
code prefix, control class strings, `Add`/`Delete` labels, the
`LB_DELETESTRING` instruction, the `SendMessageA` import, the `load_notes`
call that replaced the seed block, the `load_notes` prologue, and the
`CreateFileA` import name — the anchors that move or appear with the
persistence code.

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
