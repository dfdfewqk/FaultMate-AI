"""Portable Windows entrypoint.

Keep the existing scripts.start module import (rather than freezing that file
as __main__) so its bundled __file__ points into _internal/scripts/ and
resolves _internal/web and _internal/faultmate/knowledge correctly.

No elevation, installer, model promotion, or external AI call at startup.
"""
from scripts.start import main


if __name__ == "__main__":
    raise SystemExit(main())
