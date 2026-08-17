"""Build the product wheel, or the optional console wheel from this tree."""

import os
import shutil
from pathlib import Path

from setuptools import find_packages, setup
from setuptools.command.build_py import build_py


include_console = os.environ.get("FINAL_PROJECT_INCLUDE_CONSOLE") == "1"
excluded = [] if include_console else ["app.console", "app.console.*"]


class ProductBuildPy(build_py):
    def run(self):
        super().run()
        if not include_console:
            shutil.rmtree(Path(self.build_lib) / "app" / "console", ignore_errors=True)
            for legacy in ("console.py", "composer.py", "theme.py"):
                (Path(self.build_lib) / "app" / "presentation" / "ui" / legacy).unlink(missing_ok=True)

setup(
    packages=find_packages(exclude=excluded),
    cmdclass={"build_py": ProductBuildPy},
)
