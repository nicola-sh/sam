"""RegCon встроен в SAM. Для совместимости: python -m regcon → python -m sam."""

from __future__ import annotations

import sys

if __name__ == "__main__":
    print("RegCon — вкладка в SAM. Запуск: python -m sam", file=sys.stderr)
    from sam.__main__ import main

    sys.exit(main())
