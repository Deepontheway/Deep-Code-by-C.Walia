//! A dependency-free native entry point. The TypeScript agent remains usable
//! today; this crate is the stable Rust shell for a future Ratatui interface.
use std::{env, fs, path::PathBuf};

const FOLDERS: [&str; 10] = [
    "bin", "runtime", "models", "env", "sandbox",
    "plugins", "data", "training", "cache", "licenses",
];

fn runtime_root() -> PathBuf {
    if let Some(value) = env::var_os("DEEPCODE_HOME") {
        return PathBuf::from(value);
    }
    env::var_os("USERPROFILE")
        .map(PathBuf::from)
        .or_else(|| env::var_os("HOME").map(PathBuf::from))
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".deepcode")
}

fn init_runtime() -> Result<PathBuf, std::io::Error> {
    let root = runtime_root();
    for folder in FOLDERS {
        fs::create_dir_all(root.join(folder))?;
    }
    Ok(root)
}

fn main() {
    let command = env::args().nth(1).unwrap_or_else(|| "help".to_string());
    match command.as_str() {
        "init" => match init_runtime() {
            Ok(root) => println!("DeepCode runtime ready at {}", root.display()),
            Err(error) => {
                eprintln!("Unable to initialise DeepCode runtime: {error}");
                std::process::exit(1);
            }
        },
        "help" | "--help" | "-h" => println!(
            "DeepCode native shell\n\nCommands:\n  deepcode init    Create the self-contained runtime layout\n\nSet DEEPCODE_HOME to place DeepCode data and models on another drive."
        ),
        _ => {
            eprintln!("Unknown command: {command}. Run deepcode help.");
            std::process::exit(2);
        }
    }
}
