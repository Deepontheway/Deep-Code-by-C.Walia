# WaliaCode

WaliaCode is an independent, open-source local coding and personal-agent application designed to launch through Pinokio. It brings project-aware coding chat, model configuration, code generation/explanation/debugging, and reviewed file/terminal actions together with permission-gated browser, PowerShell, Python/C++, HTTP, and email tools.

WaliaCode is a separate application with its own name, implementation, and branding. It is not affiliated with Manus or any other service provider.

## Capabilities

- Maintain, rename, switch, and delete local chat sessions; keep conversation history in SQLite on this computer.
- Connect to a user-chosen OpenAI-compatible model endpoint, including a local model service. WaliaCode does not ship a model or provider account.
- Assist with Java, JavaScript, Python, PHP, HTTP/API workflows, PowerShell, C++, and other software topics supported by the selected model.
- Read files only inside the folder the user selects. Show a proposed file diff and require approval before every write.
- Propose PowerShell/generic shell commands, Python/C++ execution, browser actions, HTTP requests, and email sends. Each action is shown for one-time approval before it runs.
- Open an isolated, WaliaCode-managed Chromium profile using Playwright; it does not silently attach to the user's everyday browser profile.
- Send email through SMTP after the user configures an SMTP account and approves the exact recipient, subject, and body.

## Usage limits and model quality

WaliaCode does not add a per-turn or token quota. This is not a promise of unlimited model service: hosted providers may apply quotas, billing, rate limits, context windows, or account rules. A local model is limited by the user's computer and model configuration. Compiling or executing languages also requires the relevant runtime, SDK, compiler, or build tool to be installed locally.

## Permission and safety behavior

WaliaCode binds its server to `127.0.0.1` and is intended to be used only on the computer running Pinokio. Workspace reads are scoped to the selected directory. Every file write, shell/PowerShell/Python/C++ action, browser action, HTTP request, and email send requires explicit per-action approval. The approval panel shows the exact diff, command/code, URL/selectors, request method/headers/body, or email content.

Approval is not a sandbox: a command you approve runs with the Windows user's privileges. Review every action carefully. Browser login/session state is stored in WaliaCode's separate local Chromium profile. Model prompts and attached file contents are sent to the provider you configure. Do not expose the local port through a tunnel or network proxy.

## Repository discovery policy

WaliaCode can discover coding resources from approved sources such as GitHub, GitHits, and Reddit. Downloads may be automatic from approved sources, but dependency installation, MCP-server startup, code execution, credential use, file overwrites, browser submissions, and outbound messages remain approval-gated. Every downloaded source should record its URL, commit or release, license, install-script summary, and estimated disk usage.

## Pinokio installation

The package includes Pinokio launcher files. The base installation should avoid heavyweight model weights, Docker images, datasets, and optional browser runtimes until explicitly enabled. Browser automation and other optional features should be feature flags with a disk-usage estimate.

For Pinokio's Download from URL flow, use this repository: https://github.com/Deepontheway/walia-code

## Project quality target

WaliaCode follows the detailed-project standard used by mature repositories: clear documentation, security and disclaimer files, a contribution guide, reproducible launcher scripts, tests, source notes, MCP contracts, skill definitions, and third-party notices. REA and OpenManus are integrated as documented, lazy-loaded capabilities rather than silently installed heavyweight dependencies.

## License

WaliaCode is offered under the MIT License. Third-party libraries retain their own licenses.
