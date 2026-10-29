# DeepCode development platform

DeepCode is language-neutral at its agent boundary: it reads project files,
uses the project's declared commands, and asks before running anything. The app
recognises Python, JavaScript, TypeScript, Rust, C, C++, Java, C#, Go, PHP,
Ruby, Kotlin, Swift, Dart/Flutter, HTML, CSS, SCSS, MDX, Astro, SQL, R, and
Julia projects.

Toolchains are optional. DeepCode may recommend Python plus Spyder, Conda,
Cargo, a JDK, CMake, or an IDE integration, but installation must be a specific
user-approved setup action. It must not silently install a system-wide IDE or
package manager.

GitHub integration is also opt-in. DeepCode works with local Git by default;
connecting a GitHub account should use the user's existing Git credential
manager or GitHub CLI authentication and minimum required permissions.
