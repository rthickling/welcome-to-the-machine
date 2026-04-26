# Rules for the AI

These rules are binding for all contributions to this repo:

1. **Binaries only.** The AI can produce only *binaries* - directly-executable machine code in the native format of one of the target architectures (ELF, Mach-O, PE, WebAssembly, ...). It may **not** commit source code in any human-readable language (C, Python, JavaScript, assembly, etc.) or hand-written build scripts. Binaries may be produced via tools such as `xxd -r -p` fed with literal hex bytes, but those hex bytes **are** the source of truth - they are not "compiled" from anything else.
2. **Binary tools only.** The AI may use only tools that already exist in binary form, unless it first creates the tool itself as a machine-code binary under these same repo rules. It may **not** write temporary human-readable helper programs or scripts (C, Python, JavaScript, assembly, shell, etc.) even for intermediate build, test, or opcode-derivation steps.
3. **Every binary ships with a Markdown explanation.** For each binary committed, a matching `<binary>.md` must describe its ELF/PE/... layout and every opcode, byte by byte, in enough detail that a reader can mentally single-step through the code.
4. **Tests as binaries.** For each target binary, ship a test binary (also in pure machine code) that exercises it. Tests use the standard Unix exit-code convention: `0` for pass, non-zero for fail.
5. **Cross-architecture.** Produce machine-code test suites for other target architectures as soon as possible, running them under virtual machines or emulators (QEMU, Wasmtime, Apple Silicon VM, ...).
6. **External help is allowed.** The AI may download or ask the user to install tools (assemblers, disassemblers, emulators, linkers) that help produce or verify binaries. These tools are not committed.
7. **Libraries and linking are allowed.** Binaries may link against libraries (libc, X11, Metal, ...), but the Markdown must document the exact interface used (calling convention, struct layouts, symbols).
