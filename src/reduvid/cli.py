# SPDX-License-Identifier: LicenseRef-WNCL-CU-1.0
# Copyright (C) 2026 Catlinux

import argparse
import sys
from collections.abc import Sequence

from reduvid import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reduvid")
    parser.add_argument("--version", action="version", version=f"reduvid {__version__}")
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if arguments == []:
        parser.print_help()
        return 0
    parser.parse_args(arguments)
    return 0
