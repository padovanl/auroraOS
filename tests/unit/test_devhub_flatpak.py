"""Flatpak recipes must work with only a system-wide Flathub remote."""

import os
import subprocess

from aurora.devhub.games import RECIPES as GAME_RECIPES
from aurora.devhub.recipes import APT_REPO, RECIPES as DEV_RECIPES, docker_service
from aurora.devhub.app import INSTALL_SCRIPT_HEADER, install_wrapper


def test_flatpak_recipes_configure_matching_user_remote(tmp_path):
    fake = tmp_path / "flatpak"
    log = tmp_path / "calls"
    fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FLATPAK_TEST_LOG\"\n"
                    "case \"$*\" in\n"
                    "  'remote-add --user --if-not-exists flathub '* ) touch \"$FLATPAK_TEST_REMOTE\" ;;\n"
                    "  'install -y --noninteractive --user flathub '* ) test -f \"$FLATPAK_TEST_REMOTE\" ;;\n"
                    "  * ) exit 1 ;;\n"
                    "esac\n")
    fake.chmod(0o755)
    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}",
               FLATPAK_TEST_LOG=str(log), FLATPAK_TEST_REMOTE=str(tmp_path / "user-remote"))
    recipes = [r for r in DEV_RECIPES + GAME_RECIPES if "flatpak install" in r["script"]]
    assert len(recipes) >= 10
    for recipe in recipes:
        log.write_text("")
        # Arduino adds a separate sudo group change after the Flatpak commands.
        flatpak_steps = "\n".join(recipe["script"].splitlines()[:2])
        result = subprocess.run(["bash", "-e", "-c", flatpak_steps], env=env,
                                capture_output=True, text=True)
        assert result.returncode == 0, (recipe["id"], result.stderr)
        calls = log.read_text().splitlines()
        assert calls[0].startswith("remote-add --user --if-not-exists flathub ")
        assert calls[1].startswith("install -y --noninteractive --user flathub ")


def test_flatpak_recipes_detect_user_or_system_installations(tmp_path):
    fake = tmp_path / "flatpak"
    fake.write_text("#!/bin/sh\n"
                    "test \"$1\" = info || exit 2\n"
                    "test \"$2\" = \"$FLATPAK_TEST_SCOPE\"\n")
    fake.chmod(0o755)
    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}")
    recipes = [r for r in DEV_RECIPES + GAME_RECIPES if "flatpak install" in r["script"]]
    for scope in ("--user", "--system"):
        for recipe in recipes:
            result = subprocess.run(["bash", "-c", recipe["check"]],
                                    env=dict(env, FLATPAK_TEST_SCOPE=scope),
                                    capture_output=True, text=True)
            assert result.returncode == 0, (recipe["id"], scope, result.stderr)


def test_install_wrapper_reports_failure_and_preserves_exit_code(tmp_path):
    recipe = tmp_path / "recipe with spaces.sh"
    recipe.write_text("exit 17\n")
    result = subprocess.run(["bash", "-c", install_wrapper(str(recipe))],
                            capture_output=True, text=True)
    assert result.returncode == 17
    assert "Installation failed" in result.stdout
    assert not recipe.exists()


def test_recipe_header_does_not_hide_pipeline_failures():
    result = subprocess.run(["bash"], input=INSTALL_SCRIPT_HEADER + "false | true\n",
                            capture_output=True, text=True)
    assert result.returncode != 0


def test_docker_service_restarts_an_existing_container():
    script = docker_service("postgres", "postgres:17", "5432:5432")
    assert "docker container inspect postgres" in script
    assert "docker start postgres" in script
    assert "docker run -d --name postgres" in script
    assert script.index("docker start postgres") < script.index("docker run -d --name postgres")


def test_docker_service_checks_require_a_running_container():
    services = {"postgres", "mariadb", "redis", "mongodb"}
    recipes = [recipe for recipe in DEV_RECIPES if recipe["id"] in services]
    assert {recipe["id"] for recipe in recipes} == services
    for recipe in recipes:
        assert ".State.Running" in recipe["check"]


def test_archive_recipes_use_private_temporary_directories():
    ids = {"go", "kubectl", "terraform", "awscli"}
    recipes = [recipe for recipe in DEV_RECIPES if recipe["id"] in ids]
    assert {recipe["id"] for recipe in recipes} == ids
    for recipe in recipes:
        assert "tmp=$(mktemp -d)" in recipe["script"]
        assert "trap 'rm -rf \"$tmp\"' EXIT" in recipe["script"]
        assert "cd /tmp" not in recipe["script"]


def test_external_repositories_remove_conflicting_legacy_definition_first():
    remove = 'sudo rm -f "/etc/apt/sources.list.d/$1.list"'
    write = 'sudo tee "/etc/apt/sources.list.d/$1.sources"'
    assert remove in APT_REPO
    assert APT_REPO.index(remove) < APT_REPO.index(write) < APT_REPO.index("apt-get update")
