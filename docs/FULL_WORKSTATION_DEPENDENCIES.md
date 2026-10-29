# Full workstation dependencies

The Windows full installer provisions Git, Windows Terminal, Python, Miniconda
or Anaconda, Spyder, Visual Studio Code, Docker Desktop, SQLite, and Visual
Studio Build Tools. Ollama is installed when local models are selected.

These packages are system applications; their installers determine their
installation locations and may require Windows privileges, reboots, WSL, or
virtualisation support. They cannot be truthfully contained in DeepCode's own
folder. DeepCode-owned state remains under the DEEPCODE_HOME folder.

Docker Desktop is installed as a tool and is not treated as a security sandbox
until the user configures and explicitly enables a per-project container policy.
