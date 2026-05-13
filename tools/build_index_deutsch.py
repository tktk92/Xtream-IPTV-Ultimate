# -*- coding: utf-8 -*-

import sys
from xtream_index_builder import main


if __name__ == "__main__":
    sys.exit(main(["--languages", "Deutsch"] + sys.argv[1:]))
