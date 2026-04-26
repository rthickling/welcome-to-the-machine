# Welcome to the Machine

Machine language only.

## Motivation

In early 2026, Elon Musk [said](https://www.youtube.com/watch?v=HD_SiJDWPcQ&t=683s)
that in future, developers would write code in natural language and AI would
generate machine code directly, without the need for human-readable code.

This repo explores that idea by committing executable machine-code artifacts,
their byte-level explanations, and machine-code test binaries.

## Repository Map

| Area | Purpose |
| --- | --- |
| [`docs/`](docs/) | Binding rules, host prerequisites, and documentation index. |
| [`experiments/`](experiments/) | Proof-of-concept binaries grouped by target or technique. |
| [`products/`](products/) | Product-oriented deliverables, currently the cross-platform Notes product. |
| [`tools/`](tools/) | Self-built binary tools that also obey the repo rules. |
| [`var/`](var/) | Runtime samples and ignored local scratch space. |

## Rules

The binding contribution rules are in [`docs/rules.md`](docs/rules.md). In
short: committed implementations are executable binaries only; every binary has
a sibling Markdown explanation; every target has a binary verifier.

Host setup and runtime notes are in
[`docs/prerequisites.md`](docs/prerequisites.md).

## Products

| Product | Status | Docs |
| --- | --- | --- |
| `notes` | First cross-platform product. Linux x86_64 is the reference build; Windows x86_64 has a runnable two-pane Win32 GUI; other targets have scaffold/container artifacts with structural verifiers. | [`products/notes/README.md`](products/notes/README.md) |

## Experiments

The detailed byte-by-byte explanations live beside each binary in its experiment
directory.

| Experiment | Architecture | Platform | Description |
| --- | --- | --- | --- |
| [`poc-01-greeter`](experiments/poc-01-greeter/) | x86_64 | Linux ELF | Greeter that reads stdin, writes `greeting.txt`, and prints an ANSI greeting. |
| [`poc-02-x11-window`](experiments/poc-02-x11-window/) | x86_64 | Linux ELF / X11 | Minimal raw-X11 window that records simple status to `status.log`. |
| [`poc-03-notes-cli`](experiments/poc-03-notes-cli/) | x86_64 | Linux ELF | Note-taker that appends stdin text to `notes.db` and reprints stored notes. |
| [`poc-04-notes-x11`](experiments/poc-04-notes-x11/) | x86_64 | Linux ELF / X11 | Notes GUI with `note-view` and interactive sorted-entry `note-edit`. |
| [`poc-05-wasm-wasi`](experiments/poc-05-wasm-wasi/) | WebAssembly | WASI | First non-ELF target: `hello.wasm` plus a WASM structural verifier. |
| [`poc-06-linux-arm64`](experiments/poc-06-linux-arm64/) | ARM64 | Linux ELF | Minimal AArch64 ELF hello program with matching native test binary. |
| [`poc-07-riscv64`](experiments/poc-07-riscv64/) | RISC-V 64 | Linux ELF | Minimal RV64 ELF hello program with matching structural verifier. |
| [`poc-08-windows-pe`](experiments/poc-08-windows-pe/) | x86_64 | Windows PE | Minimal `PE32+` console hello program with Linux x86_64 verifier. |
| [`poc-09-android-elf`](experiments/poc-09-android-elf/) | ARM64 | Android-style Linux ELF PIE | Native Android-oriented AArch64 PIE executable, before full APK packaging. |
| [`poc-10-android-apk`](experiments/poc-10-android-apk/) | x86_64, ARM64 | Android APK | NativeActivity APK with `x86_64` and `arm64-v8a` payloads plus Linux verifier. |
| [`poc-11-apple-mach-o`](experiments/poc-11-apple-mach-o/) | ARM64 | macOS Mach-O, iOS Mach-O | Host-verified Apple Mach-O structural POCs for macOS and iOS. |

## Tools

Committed helper tools must also follow the repo rules and ship with their own
binary tests and Markdown explanations.

| Tool | Purpose | Docs |
| --- | --- | --- |
| [`mkelf`](tools/mkelf/) | Small Linux x86_64 ELF wrapper used to turn raw code+data bytes into complete ELF executables. | [`tools/mkelf/mkelf.md`](tools/mkelf/mkelf.md) |

## How to Use

1. Pick the target directory you want to inspect or run.
2. Read the matching `.md` files in that directory for the exact binary layout,
   verification method, and any platform-specific caveats.
3. Run the binary and its test using the runtime noted in that directory's docs.
