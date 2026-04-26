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

## Code at `0x200`

The checked prefix begins:

```text
48 81 ec e8 01 00 00             sub rsp, 0x1e8
31 c9                            xor ecx, ecx
48 8d 15 f0 05 00 00             lea rdx, [rip+0x5f0]
4c 8d 05 04 06 00 00             lea r8,  [rip+0x604]
41 b9 00 00 cf 10                mov r9d, 0x10cf0000
```

Execution summary:

1. Create a top-level `STATIC` parent window.
2. Create a child multiline `EDIT` control on the left.
3. Create a child `LISTBOX` control on the right.
4. Create child `BUTTON` controls labelled `Add` and `Delete`.
5. Seed the list with `First note` and `Second note`.
6. Run a `GetMessageA` / `TranslateMessage` / `DispatchMessageA` loop.
7. Before dispatching a button-up message, handle `Add` or `Delete` directly
   with `SendMessageA`.

The delete path contains:

```text
ba 82 01 00 00                   mov edx, 0x182
```

`0x182` is `LB_DELETESTRING`, sent to the right-hand list box with the selected
index.

## Strings

At file offset `0x800`:

```text
STATIC
EDIT
LISTBOX
BUTTON
Notes x64
Type notes here.
Add
Delete
First note
Second note
```

The UI labels are plain ASCII and are consumed directly by `CreateWindowExA`.

## Imports

The import table starts at file offset `0x900` / RVA `0x1700`.

`USER32.dll` imports:

- `CreateWindowExA`
- `GetMessageA`
- `TranslateMessage`
- `DispatchMessageA`
- `IsWindow`
- `SendMessageA`

`KERNEL32.dll` imports:

- `ExitProcess`

Important anchored names:

```text
0x950: USER32.dll
0x960: KERNEL32.dll
0xa30: CreateWindowExA
0xa48: GetMessageA
0xa58: TranslateMessage
0xa70: DispatchMessageA
0xa88: IsWindow
0xa98: SendMessageA
0xaa8: ExitProcess
```

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
