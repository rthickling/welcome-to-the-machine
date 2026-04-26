# macOS Desktop Product Plan

This file isolates the macOS-specific desktop work for the cross-platform notes
product.

## Goal

Ship:

- `notes-macos`

as a real native macOS note editor with the same visible behavior as the Linux
reference build:

- left editor pane
- right first-word list
- click list item to load note
- save current note with the product's shared semantics
- normal printable ASCII input, including uppercase letters and shifted symbols
- simple pane borders with readable foreground/background colours

## Starting point

The current Apple artifact in the repo is only a structural Mach-O precedent:

- [`../../../experiments/poc-11-apple-mach-o/hello-macos.md`](../../../experiments/poc-11-apple-mach-o/hello-macos.md)

That file is useful for container shape only. It does not yet prove a runnable
AppKit product path.

## Required macOS work

1. real Mach-O desktop executable using native macOS GUI APIs
2. file I/O using the shared `notes.db` format
3. list selection and editor rendering
4. click handling and save behavior
5. Apple-host runtime validation
6. code-signing workflow suitable for local testing and eventual distribution
7. keyboard handling that preserves the shared printable ASCII policy
8. native border / colour setup for the editor and list panes

## Validation policy

Unlike the current Apple POCs, the product target is not considered complete on
container shape alone. It needs:

- a runnable binary on Apple-host tooling or hardware
- a matching test artifact
- detailed interface documentation for any linked Apple frameworks
- structural anchors for visible labels, printable input handling, colours, and
  border drawing where host-side verification is practical
