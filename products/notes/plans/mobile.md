# Mobile Product Plan

This file covers the mobile note product targets:

- Android ARM64
- iOS ARM64

## Goal

Keep the same core note-taking behavior as the desktop reference build while
allowing a mobile-appropriate presentation:

- editable note pane
- note list derived from first words
- tap to load note
- save on the platform's equivalent primary action, with `Enter` behavior where
  physical or software keyboards make that natural
- normal printable ASCII input when a keyboard is present, including uppercase
  letters and shifted symbols
- simple visual separation between editor and list, with readable colours

## Android ARM64

Starting point:

- packaging/runtime proof: [`../../../experiments/poc-10-android-apk/hello.apk.md`](../../../experiments/poc-10-android-apk/hello.apk.md)

Required implementation work:

1. replace the current no-op `ANativeActivity_onCreate`
2. create a real native render/input path
3. provide list selection and note editing
4. store notes in app-private storage using the same record framing
5. preserve the same add/load/edit behavior as the Linux reference build
6. support the shared printable ASCII editing policy for hardware and software
   keyboard input
7. draw or theme editor/list borders and foreground/background colours

## iOS ARM64

Starting point:

- structural Mach-O precedent: [`../../../experiments/poc-11-apple-mach-o/hello-ios.md`](../../../experiments/poc-11-apple-mach-o/hello-ios.md)

Required implementation work:

1. real UIKit-based runtime path
2. touch selection in the note list
3. note editing surface
4. same note storage format
5. Apple-host validation and signing during execution
6. shared printable ASCII input behavior for hardware/software keyboards
7. simple editor/list borders and readable foreground/background colours

## Mobile layout policy

If the device cannot comfortably show two fixed panes side-by-side, the product
should still preserve the same operations using the best native mobile layout
available:

- list visible
- editor visible
- tap-to-load
- edit
- save
- printable text input
- visual borders or native separators between list and editor

The behavior matters more than a strict desktop geometry clone.
