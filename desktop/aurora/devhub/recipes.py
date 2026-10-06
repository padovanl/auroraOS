"""Dev Hub catalog: what can be installed, how, and how to tell it is installed.

Every recipe installs from the vendor's official source, so users always
get the current release. Scripts run in a visible terminal with `set -e`;
anything that needs root uses sudo and asks for the password there.
"""

import shlex

from aurora.i18n import N_

APT_REPO = r'''
add_repo() {  # add_repo NAME KEY_URL "deb822 lines..."
    sudo install -d -m 0755 /etc/apt/keyrings
    curl -fsSL "$2" | gpg --dearmor | sudo tee "/etc/apt/keyrings/$1.gpg" >/dev/null
    # Vendor packages and older recipes may have left the same repository in
    # one-line format with a different Signed-By path. APT rejects both before
    # it can install or repair anything, so replace that stale definition.
    sudo rm -f "/etc/apt/sources.list.d/$1.list"
    printf '%s\nSigned-By: /etc/apt/keyrings/%s.gpg\n' "$3" "$1" | sudo tee "/etc/apt/sources.list.d/$1.sources" >/dev/null
    sudo apt-get update
}
'''

CATEGORIES = [
    ("editors", N_("Editors & IDEs")),
    ("languages", N_("Languages & Runtimes")),
    ("cloud", N_("Cloud & DevOps")),
    ("data", N_("Databases & API Tools")),
    ("ai", N_("AI Assistants")),
    ("shells", N_("Shells & Terminals")),
    ("cli", N_("Command-Line Tools")),
    ("vcs", N_("Version Control")),
    ("containers", N_("Containers & Virtual Machines")),
    ("web", N_("Web Development")),
    ("mobile", N_("Mobile")),
    ("debug", N_("Debugging & Performance")),
    ("science", N_("Data Science")),
    ("gamedev", N_("Game Development")),
    ("embedded", N_("Embedded & Hardware")),
    ("design", N_("Design & Documentation")),
    ("security", N_("Security & Networking")),
]


def default_shell(path):
    """Make an installed shell the login shell of the current user."""
    return (f'grep -qx "{path}" /etc/shells || echo "{path}" | sudo tee -a /etc/shells >/dev/null\n'
            f'sudo chsh -s "{path}" "$USER"\n'
            "echo; echo 'Done: new terminals use it after you log out and back in.'")


def flatpak(app_id):
    # The image ships a system Flathub remote, but these recipes install into
    # the user's Flatpak installation. Remotes are scoped to the installation.
    return ("flatpak remote-add --user --if-not-exists flathub "
            "https://dl.flathub.org/repo/flathub.flatpakrepo\n"
            f"flatpak install -y --noninteractive --user flathub {shlex.quote(app_id)}")


def flatpak_check(app_id):
    """Find an app in either Flatpak installation.

    Recipes install for the current user, while the image also ships a system
    Flathub remote.  An unqualified ``flatpak info`` can therefore inspect the
    wrong installation and make a successful install look like a failure.
    """
    app = shlex.quote(app_id)
    return (f"flatpak info --user {app} >/dev/null 2>&1 || "
            f"flatpak info --system {app} >/dev/null 2>&1")


def docker_service(name, image, port, env=""):
    return (f"docker volume create {name}-data >/dev/null\n"
            f"docker run -d --name {name} --restart unless-stopped -p {port} {env} "
            f"-v {name}-data:/var/lib/{name} {image}\n"
            f"echo; echo '{name} is running on localhost:{port.split(':')[0]}'")


RECIPES = [
    # --- editors ---
    {"id": "vscode", "cat": "editors", "name": "Visual Studio Code", "icon": "com.visualstudio.code",
     "fallback_icon": "text-editor", "desc": N_("Microsoft's popular code editor, from the official apt repository."),
     "check": "command -v code",
     "script": APT_REPO + r'''
add_repo vscode https://packages.microsoft.com/keys/microsoft.asc "Types: deb
URIs: https://packages.microsoft.com/repos/code
Suites: stable
Components: main
Architectures: amd64"
# The package would add its own copy of the repository, signed with another
# key path: apt then refuses both ("Conflicting values set for option Signed-By").
echo "code code/add-microsoft-repo boolean false" | sudo debconf-set-selections
sudo apt-get install -y code
'''},
    {"id": "vscodium", "cat": "editors", "name": "VSCodium", "icon": "vscodium",
     "fallback_icon": "text-editor", "desc": N_("VS Code built from source without telemetry."),
     "check": "command -v codium",
     "script": APT_REPO + r'''
add_repo vscodium https://gitlab.com/paulcarroty/vscodium-deb-rpm-repo/raw/master/pub.gpg "Types: deb
URIs: https://download.vscodium.com/debs
Suites: vscodium
Components: main
Architectures: amd64"
sudo apt-get install -y codium
'''},
    {"id": "zed", "cat": "editors", "name": "Zed", "icon": "dev.zed.Zed",
     "fallback_icon": "text-editor", "desc": N_("A very fast, collaborative editor written in Rust."),
     "check": "test -x ~/.local/bin/zed",
     "script": "curl -f https://zed.dev/install.sh | sh"},
    {"id": "intellij", "cat": "editors", "name": "IntelliJ IDEA Community", "icon": "com.jetbrains.IntelliJ-IDEA-Community",
     "fallback_icon": "applications-development", "desc": N_("The JetBrains IDE for Java and Kotlin (Flathub)."),
     "check": flatpak_check("com.jetbrains.IntelliJ-IDEA-Community"),
     "script": flatpak("com.jetbrains.IntelliJ-IDEA-Community")},
    {"id": "pycharm", "cat": "editors", "name": "PyCharm Community", "icon": "com.jetbrains.PyCharm-Community",
     "fallback_icon": "applications-development", "desc": N_("The JetBrains IDE for Python (Flathub)."),
     "check": flatpak_check("com.jetbrains.PyCharm-Community"),
     "script": flatpak("com.jetbrains.PyCharm-Community")},
    {"id": "android-studio", "cat": "editors", "name": "Android Studio", "icon": "com.google.AndroidStudio",
     "fallback_icon": "applications-development", "desc": N_("Google's IDE for Android apps (Flathub)."),
     "check": flatpak_check("com.google.AndroidStudio"),
     "script": flatpak("com.google.AndroidStudio")},

    # --- languages ---
    {"id": "rust", "cat": "languages", "name": "Rust", "icon": "rust",
     "fallback_icon": "applications-engineering", "desc": N_("rustup, cargo and the stable toolchain."),
     "check": "test -x ~/.cargo/bin/rustc",
     "script": "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"},
    {"id": "go", "cat": "languages", "name": "Go", "icon": "golang",
     "fallback_icon": "applications-engineering", "desc": N_("The latest Go release from go.dev, in /usr/local/go."),
     "check": "test -x /usr/local/go/bin/go",
     "script": r'''
v=$(curl -fsSL 'https://go.dev/VERSION?m=text' | head -1)
echo "Installing $v"
curl -fL "https://go.dev/dl/$v.linux-amd64.tar.gz" -o /tmp/go.tgz
sudo rm -rf /usr/local/go && sudo tar -C /usr/local -xzf /tmp/go.tgz && rm /tmp/go.tgz
/usr/local/go/bin/go version
'''},
    {"id": "java", "cat": "languages", "name": "Java (OpenJDK 21)", "icon": "openjdk",
     "fallback_icon": "applications-engineering", "desc": N_("OpenJDK 21 LTS with Maven and Gradle."),
     "check": "command -v javac",
     "script": "sudo apt-get update && sudo apt-get install -y openjdk-21-jdk maven gradle"},
    {"id": "fnm", "cat": "languages", "name": N_("Node.js versions (fnm)"), "icon": "nodejs",
     "fallback_icon": "applications-engineering", "desc": N_("Install and switch any Node.js version, including the latest LTS."),
     "check": "test -x ~/.local/share/fnm/fnm",
     "script": "curl -fsSL https://fnm.vercel.app/install | bash && ~/.local/share/fnm/fnm install --lts"},
    {"id": "uv", "cat": "languages", "name": "uv", "icon": "python",
     "fallback_icon": "applications-engineering", "desc": N_("Astral's extremely fast Python package and project manager."),
     "check": "test -x ~/.local/bin/uv",
     "script": "curl -LsSf https://astral.sh/uv/install.sh | sh"},
    {"id": "bun", "cat": "languages", "name": "Bun", "icon": "bun",
     "fallback_icon": "applications-engineering", "desc": N_("All-in-one JavaScript runtime, bundler and test runner."),
     "check": "test -x ~/.bun/bin/bun",
     "script": "curl -fsSL https://bun.sh/install | bash"},
    {"id": "deno", "cat": "languages", "name": "Deno", "icon": "deno",
     "fallback_icon": "applications-engineering", "desc": N_("Secure JavaScript and TypeScript runtime."),
     "check": "test -x ~/.deno/bin/deno",
     "script": "curl -fsSL https://deno.land/install.sh | sh -s -- -y"},

    # --- cloud ---
    {"id": "gh", "cat": "cloud", "name": "GitHub CLI", "icon": "github",
     "fallback_icon": "utilities-terminal", "desc": N_("Work with GitHub issues, pull requests and Actions from the terminal."),
     "check": "command -v gh",
     "script": APT_REPO + r'''
sudo install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli.gpg >/dev/null
printf 'Types: deb\nURIs: https://cli.github.com/packages\nSuites: stable\nComponents: main\nSigned-By: /etc/apt/keyrings/githubcli.gpg\n' | sudo tee /etc/apt/sources.list.d/github-cli.sources >/dev/null
sudo apt-get update && sudo apt-get install -y gh
'''},
    {"id": "kubectl", "cat": "cloud", "name": "kubectl", "icon": "kubernetes",
     "fallback_icon": "utilities-terminal", "desc": N_("The Kubernetes command-line tool, latest stable."),
     "check": "command -v kubectl",
     "script": r'''
v=$(curl -fsSL https://dl.k8s.io/release/stable.txt)
curl -fLo /tmp/kubectl "https://dl.k8s.io/release/$v/bin/linux/amd64/kubectl"
sudo install -m 0755 /tmp/kubectl /usr/local/bin/kubectl && rm /tmp/kubectl
kubectl version --client
'''},
    {"id": "terraform", "cat": "cloud", "name": "Terraform", "icon": "terraform",
     "fallback_icon": "utilities-terminal", "desc": N_("Infrastructure as code by HashiCorp, latest release."),
     "check": "command -v terraform",
     "script": r'''
v=$(curl -fsSL https://checkpoint-api.hashicorp.com/v1/check/terraform | sed -E 's/.*"current_version":"([^"]+)".*/\1/')
curl -fLo /tmp/tf.zip "https://releases.hashicorp.com/terraform/$v/terraform_${v}_linux_amd64.zip"
unzip -o /tmp/tf.zip terraform -d /tmp && sudo install -m 0755 /tmp/terraform /usr/local/bin/terraform
rm -f /tmp/tf.zip /tmp/terraform
terraform version
'''},
    {"id": "awscli", "cat": "cloud", "name": "AWS CLI", "icon": "aws",
     "fallback_icon": "utilities-terminal", "desc": N_("Amazon Web Services command-line interface v2."),
     "check": "command -v aws",
     "script": r'''
cd /tmp && curl -fL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip
unzip -oq awscliv2.zip && sudo ./aws/install --update && rm -rf aws awscliv2.zip
aws --version
'''},

    # --- data ---
    {"id": "postgres", "cat": "data", "name": N_("PostgreSQL (Docker)"), "icon": "postgresql",
     "fallback_icon": "network-server", "desc": N_("PostgreSQL 17 in a container. User and password: postgres."),
     "check": "docker container inspect postgres",
     "script": docker_service("postgres", "postgres:17", "5432:5432", "-e POSTGRES_PASSWORD=postgres")},
    {"id": "mariadb", "cat": "data", "name": N_("MariaDB (Docker)"), "icon": "mariadb",
     "fallback_icon": "network-server", "desc": N_("MariaDB in a container. Root password: mariadb."),
     "check": "docker container inspect mariadb",
     "script": docker_service("mariadb", "mariadb:lts", "3306:3306", "-e MARIADB_ROOT_PASSWORD=mariadb")},
    {"id": "redis", "cat": "data", "name": N_("Redis (Docker)"), "icon": "redis",
     "fallback_icon": "network-server", "desc": N_("Redis key-value store in a container."),
     "check": "docker container inspect redis",
     "script": docker_service("redis", "redis:7", "6379:6379")},
    {"id": "mongodb", "cat": "data", "name": N_("MongoDB (Docker)"), "icon": "mongodb",
     "fallback_icon": "network-server", "desc": N_("MongoDB document database in a container."),
     "check": "docker container inspect mongodb",
     "script": docker_service("mongodb", "mongo:8", "27017:27017")},
    {"id": "dbeaver", "cat": "data", "name": "DBeaver", "icon": "io.dbeaver.DBeaverCommunity",
     "fallback_icon": "network-server", "desc": N_("Universal database client (Flathub)."),
     "check": flatpak_check("io.dbeaver.DBeaverCommunity"),
     "script": flatpak("io.dbeaver.DBeaverCommunity")},
    {"id": "postman", "cat": "data", "name": "Postman", "icon": "com.getpostman.Postman",
     "fallback_icon": "network-server", "desc": N_("API development and testing (Flathub)."),
     "check": flatpak_check("com.getpostman.Postman"),
     "script": flatpak("com.getpostman.Postman")},
    # --- AI ---
    {"id": "claude-code", "cat": "ai", "name": "Claude Code", "icon": "claude",
     "fallback_icon": "utilities-terminal",
     "desc": N_("Anthropic's coding agent in the terminal. Sign in with your Claude "
                "subscription or an API key."),
     "check": "command -v claude || test -x ~/.local/bin/claude",
     "script": "curl -fsSL https://claude.ai/install.sh | bash"},
    {"id": "codex", "cat": "ai", "name": "OpenAI Codex CLI", "icon": "openai",
     "fallback_icon": "utilities-terminal",
     "desc": N_("OpenAI's coding agent in the terminal. Sign in with your ChatGPT plan or "
                "an API key."),
     "check": "command -v codex",
     "script": "mkdir -p ~/.local && npm install -g --prefix ~/.local @openai/codex"},
    {"id": "ollama", "cat": "ai", "name": "Ollama", "icon": "ollama",
     "fallback_icon": "application-x-executable",
     "desc": N_("Run many more open models locally; Aurora AI can use it as its provider."),
     "check": "command -v ollama",
     "script": "curl -fsSL https://ollama.com/install.sh | sh"},
    # Shells & terminals. Bash is the default shell; Ptyxis the default terminal.
    {"id": "zsh", "cat": "shells", "name": "Zsh", "icon": "utilities-terminal",
     "fallback_icon": "utilities-terminal",
     "desc": N_("The Z shell, with autosuggestions and syntax highlighting."),
     "check": "command -v zsh",
     "script": "sudo apt-get install -y zsh zsh-autosuggestions zsh-syntax-highlighting\n"
               "test -f ~/.zshrc || printf '%s\\n' "
               "'source /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh' "
               "'source /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh' > ~/.zshrc"},
    {"id": "ohmyzsh", "cat": "shells", "name": "Oh My Zsh", "icon": "utilities-terminal",
     "fallback_icon": "utilities-terminal",
     "desc": N_("Themes and hundreds of plugins for Zsh (installs Zsh too)."),
     "check": "test -d ~/.oh-my-zsh",
     "script": "sudo apt-get install -y zsh git\n"
               'RUNZSH=no CHSH=no sh -c "$(curl -fsSL '
               'https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"'},
    {"id": "fish", "cat": "shells", "name": "fish", "icon": "utilities-terminal",
     "fallback_icon": "utilities-terminal",
     "desc": N_("A friendly shell with suggestions and colors out of the box."),
     "check": "command -v fish",
     "script": "sudo apt-get install -y fish"},
    {"id": "shell-zsh", "cat": "shells", "name": N_("Zsh as default shell"),
     "icon": "utilities-terminal", "fallback_icon": "utilities-terminal",
     "desc": N_("Open new terminals in Zsh (installs it if needed)."),
     "check": 'getent passwd "$USER" | grep -q ":/usr/bin/zsh$"',
     "script": "command -v zsh >/dev/null || sudo apt-get install -y zsh\n" + default_shell("/usr/bin/zsh")},
    {"id": "shell-fish", "cat": "shells", "name": N_("fish as default shell"),
     "icon": "utilities-terminal", "fallback_icon": "utilities-terminal",
     "desc": N_("Open new terminals in fish (installs it if needed)."),
     "check": 'getent passwd "$USER" | grep -q ":/usr/bin/fish$"',
     "script": "command -v fish >/dev/null || sudo apt-get install -y fish\n" + default_shell("/usr/bin/fish")},
    {"id": "shell-bash", "cat": "shells", "name": N_("Bash as default shell"),
     "icon": "utilities-terminal", "fallback_icon": "utilities-terminal",
     "desc": N_("Go back to Bash, Aurora's standard shell."),
     "check": 'getent passwd "$USER" | grep -q ":/bin/bash$"',
     "script": default_shell("/bin/bash")},
    {"id": "starship", "cat": "shells", "name": "Starship", "icon": "starship",
     "fallback_icon": "utilities-terminal",
     "desc": N_("A fast, informative prompt for Bash, Zsh and fish."),
     "check": "command -v starship",
     "script": "mkdir -p ~/.local/bin\n"
               "curl -sS https://starship.rs/install.sh | sh -s -- -y -b ~/.local/bin\n"
               "grep -q 'starship init bash' ~/.bashrc || "
               "echo 'eval \"$(starship init bash)\"' >> ~/.bashrc\n"
               "test -f ~/.zshrc && ! grep -q 'starship init zsh' ~/.zshrc && "
               "echo 'eval \"$(starship init zsh)\"' >> ~/.zshrc\n"
               "mkdir -p ~/.config/fish && ! grep -qs 'starship init fish' ~/.config/fish/config.fish && "
               "echo 'starship init fish | source' >> ~/.config/fish/config.fish\ntrue"},
    {"id": "zellij", "cat": "shells", "name": "Zellij", "icon": "utilities-terminal",
     "fallback_icon": "utilities-terminal",
     "desc": N_("A terminal workspace with panes, tabs and plugins, an alternative to tmux."),
     "check": "test -x ~/.local/bin/zellij",
     "script": "mkdir -p ~/.local/bin\n"
               "curl -fsSL https://github.com/zellij-org/zellij/releases/latest/download/"
               "zellij-x86_64-unknown-linux-musl.tar.gz | tar -xz -C ~/.local/bin zellij"},
    {"id": "kitty", "cat": "shells", "name": "kitty", "icon": "kitty",
     "fallback_icon": "utilities-terminal",
     "desc": N_("A fast, GPU-accelerated terminal with tabs, splits and images."),
     "check": "command -v kitty",
     "script": "sudo apt-get install -y kitty"},
    {"id": "alacritty", "cat": "shells", "name": "Alacritty", "icon": "Alacritty",
     "fallback_icon": "utilities-terminal",
     "desc": N_("A minimal, very fast GPU-accelerated terminal."),
     "check": "command -v alacritty",
     "script": "sudo apt-get install -y alacritty"},
    {"id": "wezterm", "cat": "shells", "name": "WezTerm", "icon": "org.wezfurlong.wezterm",
     "fallback_icon": "utilities-terminal",
     "desc": N_("A GPU-accelerated terminal and multiplexer, configured in Lua (Flathub)."),
     "check": flatpak_check("org.wezfurlong.wezterm"),
     "script": flatpak("org.wezfurlong.wezterm")},
    {"id": "tilix", "cat": "shells", "name": "Tilix", "icon": "com.gexperts.Tilix",
     "fallback_icon": "utilities-terminal",
     "desc": N_("A tiling terminal: split one window into many terminals."),
     "check": "command -v tilix",
     "script": "sudo apt-get install -y tilix"},
    {"id": "terminator", "cat": "shells", "name": "Terminator", "icon": "terminator",
     "fallback_icon": "utilities-terminal",
     "desc": N_("Several terminals in a grid, with broadcast typing."),
     "check": "command -v terminator",
     "script": "sudo apt-get install -y terminator"},
    {"id": "gnome-console", "cat": "shells", "name": N_("GNOME Console"),
     "icon": "org.gnome.Console", "fallback_icon": "utilities-terminal",
     "desc": N_("A simple terminal, GNOME's default."),
     "check": "command -v kgx",
     "script": "sudo apt-get install -y gnome-console"},
]


def apt(*pkgs):
    return "sudo apt-get install -y " + " ".join(pkgs)


def uv_tool(spec):
    return ("command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh\n"
            f"~/.local/bin/uv tool install {spec}")


def recipe(id, cat, name, icon, desc, check, script, fallback="applications-development"):
    return {"id": id, "cat": cat, "name": name, "icon": icon, "fallback_icon": fallback,
            "desc": desc, "check": check, "script": script}


RECIPES += [
    # Command-line tools
    # ripgrep, fd, bat, fzf, jq, btop, tmux, lazygit, git-lfs, direnv and httpie
    # come with Aurora.
    recipe("cli-kit", "cli", N_("More CLI tools"), "utilities-terminal",
           N_("eza (a modern ls), yq (jq for YAML), just (a command runner), tldr pages, "
              "ncdu and duf for disk usage."),
           "command -v eza && command -v just",
           apt("eza", "yq", "just", "tealdeer", "ncdu", "duf"), "utilities-terminal"),
    recipe("zoxide", "cli", "zoxide", "utilities-terminal",
           N_("A smarter cd that remembers the folders you use."), "command -v zoxide",
           apt("zoxide") + "\ngrep -q 'zoxide init bash' ~/.bashrc || "
           "echo 'eval \"$(zoxide init bash)\"' >> ~/.bashrc", "utilities-terminal"),
    recipe("atuin", "cli", "Atuin", "utilities-terminal",
           N_("Searchable shell history, synced across your machines if you want."),
           "command -v atuin", apt("atuin") + "\ngrep -q 'atuin init bash' ~/.bashrc || "
           "echo 'eval \"$(atuin init bash)\"' >> ~/.bashrc", "utilities-terminal"),
    recipe("git-delta", "cli", "delta", "git",
           N_("Readable, syntax-highlighted git diffs."), "command -v delta",
           apt("git-delta") + "\ngit config --global core.pager delta\n"
           "git config --global interactive.diffFilter 'delta --color-only'",
           "utilities-terminal"),
    recipe("glow", "cli", "Glow", "utilities-terminal",
           N_("Read Markdown beautifully in the terminal."), "command -v glow", apt("glow"),
           "utilities-terminal"),

    # Version control
    recipe("meld", "vcs", "Meld", "org.gnome.Meld",
           N_("Compare and merge files and folders visually."), "command -v meld", apt("meld")),
    recipe("glab", "vcs", "GitLab CLI", "gitlab",
           N_("Merge requests, issues and pipelines from the terminal."),
           "command -v glab", apt("glab")),
    recipe("github-desktop", "vcs", "GitHub Desktop", "io.github.shiftey.Desktop",
           N_("GitHub's Git client (community build, Flathub)."),
           flatpak_check("io.github.shiftey.Desktop"), flatpak("io.github.shiftey.Desktop")),
    recipe("gitkraken", "vcs", "GitKraken", "com.axosoft.GitKraken",
           N_("A visual Git client with a commit graph (Flathub)."),
           flatpak_check("com.axosoft.GitKraken"), flatpak("com.axosoft.GitKraken")),
    recipe("sublime-merge", "vcs", "Sublime Merge", "com.sublimemerge.App",
           N_("A fast Git client from the makers of Sublime Text (Flathub)."),
           flatpak_check("com.sublimemerge.App"), flatpak("com.sublimemerge.App")),

    # Containers & virtual machines (Docker and Podman are already installed)
    recipe("podman-desktop", "containers", "Podman Desktop", "io.podman_desktop.PodmanDesktop",
           N_("Manage containers, images and Kubernetes from a window (Flathub)."),
           flatpak_check("io.podman_desktop.PodmanDesktop"),
           flatpak("io.podman_desktop.PodmanDesktop")),
    recipe("virt-manager", "containers", "Virtual Machine Manager", "virt-manager",
           N_("Full KVM virtual machines with QEMU and libvirt."), "command -v virt-manager",
           apt("virt-manager", "qemu-system-x86", "libvirt-daemon-system")
           + '\nsudo usermod -aG libvirt "$USER"'
           + '\necho; echo "Log out and back in to manage virtual machines."'),
    recipe("boxes", "containers", "GNOME Boxes", "org.gnome.Boxes",
           N_("Simple virtual machines: pick an OS and go."),
           "command -v gnome-boxes", apt("gnome-boxes")),
    recipe("kind", "containers", "kind", "kubernetes",
           N_("Local Kubernetes clusters running in Docker."), "command -v kind", apt("kind")),
    recipe("k9s", "containers", "k9s", "kubernetes",
           N_("A terminal UI for Kubernetes clusters."), "command -v k9s",
           'tmp=$(mktemp -d)\n'
           'curl -fsSL -o "$tmp/k9s.deb" '
           'https://github.com/derailed/k9s/releases/latest/download/k9s_linux_amd64.deb\n'
           'sudo apt-get install -y "$tmp/k9s.deb"\n'
           'rm -rf "$tmp"'),
    recipe("helm", "containers", "Helm", "kubernetes", N_("The package manager for Kubernetes."),
           "command -v helm",
           "curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"),
    recipe("lazydocker", "containers", "lazydocker", "docker", N_("A terminal UI for Docker."),
           "test -x ~/.local/bin/lazydocker",
           "mkdir -p ~/.local/bin\n"
           "curl -fsSL https://raw.githubusercontent.com/jesseduffield/lazydocker/master/"
           "scripts/install_update_linux.sh | DIR=~/.local/bin bash"),

    # Web development
    recipe("chrome", "web", "Google Chrome", "com.google.Chrome",
           N_("Chrome and its developer tools, for testing sites (Flathub)."),
           flatpak_check("com.google.Chrome"), flatpak("com.google.Chrome"), "web-browser"),
    recipe("chromium", "web", "Chromium", "chromium",
           N_("The open-source browser behind Chrome."),
           "command -v chromium", apt("chromium"), "web-browser"),
    recipe("mkcert", "web", "mkcert", "security-high",
           N_("Trusted HTTPS certificates for localhost."), "command -v mkcert",
           apt("mkcert", "libnss3-tools") + "\nmkcert -install"),
    recipe("caddy", "web", "Caddy", "network-server",
           N_("A web server with automatic HTTPS."), "command -v caddy", apt("caddy")),
    recipe("nginx", "web", "nginx", "network-server",
           N_("The popular web server and reverse proxy."), "command -v nginx", apt("nginx")),

    # Mobile
    recipe("adb", "mobile", N_("Android platform tools"), "android-studio",
           N_("adb and fastboot to talk to Android phones."), "command -v adb",
           apt("adb", "fastboot")),
    recipe("flutter", "mobile", "Flutter", "flutter",
           N_("Google's SDK for mobile, web and desktop apps."),
           "test -x ~/.local/share/flutter/bin/flutter",
           apt("git", "curl", "unzip", "xz-utils", "clang", "cmake", "ninja-build",
               "libgtk-3-dev")
           + "\ngit clone --depth 1 -b stable https://github.com/flutter/flutter.git "
           "~/.local/share/flutter\nmkdir -p ~/.local/bin\n"
           "ln -sf ~/.local/share/flutter/bin/flutter ~/.local/share/flutter/bin/dart "
           "~/.local/bin/\n~/.local/bin/flutter --version"),

    # Debugging & performance
    recipe("debug-kit", "debug", N_("Debugging toolkit"), "applications-engineering",
           N_("gdb, valgrind, strace and perf."), "command -v valgrind && command -v perf",
           apt("gdb", "valgrind", "strace", "linux-perf")),
    recipe("hyperfine", "debug", "hyperfine", "utilities-terminal",
           N_("Benchmark commands with statistics."), "command -v hyperfine", apt("hyperfine")),
    recipe("wireshark", "debug", "Wireshark", "org.wireshark.Wireshark",
           N_("Capture and inspect network traffic."), "command -v wireshark",
           "echo 'wireshark-common wireshark-common/install-setuid boolean true' "
           "| sudo debconf-set-selections\n" + apt("wireshark")
           + '\nsudo usermod -aG wireshark "$USER"'),
    recipe("bruno", "debug", "Bruno", "com.usebruno.Bruno",
           N_("An offline API client that keeps collections as files (Flathub)."),
           flatpak_check("com.usebruno.Bruno"), flatpak("com.usebruno.Bruno")),
    recipe("insomnia", "debug", "Insomnia", "rest.insomnia.Insomnia",
           N_("Design and test REST, GraphQL and gRPC APIs (Flathub)."),
           flatpak_check("rest.insomnia.Insomnia"), flatpak("rest.insomnia.Insomnia")),
    recipe("devtoolbox", "debug", "Dev Toolbox", "me.iepure.devtoolbox",
           N_("JSON, Base64, JWT, regex, hashes and other converters (Flathub)."),
           flatpak_check("me.iepure.devtoolbox"), flatpak("me.iepure.devtoolbox")),

    # Data science
    recipe("jupyterlab", "science", "JupyterLab", "jupyter",
           N_("Notebooks for Python, with pandas and matplotlib."),
           "test -x ~/.local/bin/jupyter-lab",
           uv_tool("--with pandas --with matplotlib jupyterlab")),
    recipe("miniforge", "science", "Miniforge", "python",
           N_("conda and mamba with the conda-forge packages."), "test -d ~/miniforge3",
           'tmp=$(mktemp -d)\n'
           'curl -fsSL -o "$tmp/m.sh" https://github.com/conda-forge/miniforge/releases/'
           'latest/download/Miniforge3-Linux-x86_64.sh\n'
           'bash "$tmp/m.sh" -b -p ~/miniforge3\n'
           'rm -rf "$tmp"'),
    recipe("r", "science", "R", "r-base", N_("The R language for statistics."),
           "command -v R", apt("r-base")),
    recipe("octave", "science", "GNU Octave", "org.octave.Octave",
           N_("A MATLAB-compatible numerical environment."), "command -v octave",
           apt("octave")),

    # Game development
    recipe("godot", "gamedev", "Godot", "org.godotengine.Godot",
           N_("The open-source 2D and 3D game engine (Flathub)."),
           flatpak_check("org.godotengine.Godot"), flatpak("org.godotengine.Godot")),
    recipe("blender", "gamedev", "Blender", "org.blender.Blender",
           N_("3D modeling, animation and rendering (Flathub)."),
           flatpak_check("org.blender.Blender"), flatpak("org.blender.Blender")),
    recipe("love", "gamedev", "LÖVE", "love", N_("Make 2D games in Lua."),
           "command -v love", apt("love")),

    # Embedded & hardware
    recipe("arduino", "embedded", "Arduino IDE", "cc.arduino.IDE2",
           N_("Program Arduino and compatible boards (Flathub)."),
           flatpak_check("cc.arduino.IDE2"),
           flatpak("cc.arduino.IDE2") + '\nsudo usermod -aG dialout "$USER"'),
    recipe("platformio", "embedded", "PlatformIO", "applications-electronics",
           N_("Build and flash firmware for many boards."),
           "test -x ~/.local/bin/pio", uv_tool("platformio")),
    recipe("kicad", "embedded", "KiCad", "kicad", N_("Design schematics and circuit boards."),
           "command -v kicad", apt("kicad")),
    recipe("serial", "embedded", N_("Serial consoles"), "utilities-terminal",
           N_("picocom and minicom for serial ports."), "command -v picocom",
           apt("picocom", "minicom") + '\nsudo usermod -aG dialout "$USER"'),

    # Design & documentation
    recipe("inkscape", "design", "Inkscape", "org.inkscape.Inkscape",
           N_("Vector graphics: icons, diagrams, illustrations."),
           "command -v inkscape", apt("inkscape")),
    recipe("gimp", "design", "GIMP", "gimp", N_("Edit photos and images."),
           "command -v gimp", apt("gimp")),
    recipe("drawio", "design", "draw.io", "com.jgraph.drawio.desktop",
           N_("Diagrams: flowcharts, architecture, UML (Flathub)."),
           flatpak_check("com.jgraph.drawio.desktop"), flatpak("com.jgraph.drawio.desktop")),
    recipe("obsidian", "design", "Obsidian", "md.obsidian.Obsidian",
           N_("Notes in Markdown files, linked together (Flathub)."),
           flatpak_check("md.obsidian.Obsidian"), flatpak("md.obsidian.Obsidian")),
    recipe("zeal", "design", "Zeal", "zeal",
           N_("Offline documentation for hundreds of languages and libraries."),
           "command -v zeal", apt("zeal")),

    # Security & networking
    recipe("nmap", "security", "Nmap", "nmap", N_("Scan networks and ports."),
           "command -v nmap", apt("nmap"), "network-workgroup"),
    recipe("zap", "security", "ZAP", "org.zaproxy.ZAP",
           N_("Find vulnerabilities in web apps (Flathub)."),
           flatpak_check("org.zaproxy.ZAP"), flatpak("org.zaproxy.ZAP"), "security-high"),
    recipe("tailscale", "security", "Tailscale", "tailscale",
           N_("A private network between your devices, built on WireGuard."),
           "command -v tailscale", "curl -fsSL https://tailscale.com/install.sh | sh",
           "network-vpn"),
    recipe("mosh", "security", "Mosh", "utilities-terminal",
           N_("SSH that survives sleep and changing networks."), "command -v mosh", apt("mosh")),
]
