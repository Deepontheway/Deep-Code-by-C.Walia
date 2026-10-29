# Native components

The deepcode-cli crate is a deliberately dependency-free Rust entry point. It
owns the portable runtime layout and will become the native TUI host. The
TypeScript packages remain the current agent/protocol layer, while Python may
be used only inside DeepCode's isolated env folder for optional LoRA/QLoRA
training workflows.

This split keeps the terminal interface fast and distributable while allowing
model and training integrations to evolve independently.
