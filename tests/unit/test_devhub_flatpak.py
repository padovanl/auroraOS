"""Flatpak recipes must work with only a system-wide Flathub remote."""

import os
import subprocess

from aurora.devhub.games import RECIPES as GAME_RECIPES
from aurora.devhub.recipes import RECIPES as DEV_RECIPES
from aurora.devhub.app import install_wrapper


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


def test_install_wrapper_reports_failure_and_preserves_exit_code(tmp_path):
    recipe = tmp_path / "recipe with spaces.sh"
    recipe.write_text("exit 17\n")
    result = subprocess.run(["bash", "-c", install_wrapper(str(recipe))], input="\n",
                            capture_output=True, text=True)
    assert result.returncode == 17
    assert "Installation failed" in result.stdout
    assert not recipe.exists()
