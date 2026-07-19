"""Dev Hub catalog: what can be installed, how, and how to tell it is installed.

Every recipe installs from the vendor's official source, so users always
get the current release. Scripts run in a visible terminal with `set -e`;
anything that needs root uses sudo and asks for the password there.
"""

from aurora.i18n import N_

APT_REPO = r'''
add_repo() {  # add_repo NAME KEY_URL "deb822 lines..."
    sudo install -d -m 0755 /etc/apt/keyrings
    curl -fsSL "$2" | gpg --dearmor | sudo tee "/etc/apt/keyrings/$1.gpg" >/dev/null
    printf '%s\nSigned-By: /etc/apt/keyrings/%s.gpg\n' "$3" "$1" | sudo tee "/etc/apt/sources.list.d/$1.sources" >/dev/null
    sudo apt-get update
}
'''

CATEGORIES = [
    ("editors", N_("Editors & IDEs")),
    ("languages", N_("Languages & Runtimes")),
    ("cloud", N_("Cloud & DevOps")),
    ("data", N_("Databases & API Tools")),
]


def flatpak(app_id):
    return f"flatpak install -y --user flathub {app_id}"


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
     "check": "flatpak info com.jetbrains.IntelliJ-IDEA-Community",
     "script": flatpak("com.jetbrains.IntelliJ-IDEA-Community")},
    {"id": "pycharm", "cat": "editors", "name": "PyCharm Community", "icon": "com.jetbrains.PyCharm-Community",
     "fallback_icon": "applications-development", "desc": N_("The JetBrains IDE for Python (Flathub)."),
     "check": "flatpak info com.jetbrains.PyCharm-Community",
     "script": flatpak("com.jetbrains.PyCharm-Community")},
    {"id": "android-studio", "cat": "editors", "name": "Android Studio", "icon": "com.google.AndroidStudio",
     "fallback_icon": "applications-development", "desc": N_("Google's IDE for Android apps (Flathub)."),
     "check": "flatpak info com.google.AndroidStudio",
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
     "check": "flatpak info io.dbeaver.DBeaverCommunity",
     "script": flatpak("io.dbeaver.DBeaverCommunity")},
    {"id": "postman", "cat": "data", "name": "Postman", "icon": "com.getpostman.Postman",
     "fallback_icon": "network-server", "desc": N_("API development and testing (Flathub)."),
     "check": "flatpak info com.getpostman.Postman",
     "script": flatpak("com.getpostman.Postman")},
]
