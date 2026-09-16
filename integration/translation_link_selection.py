"""Compatibility import for the public authority-content contract."""
import sys
from publication_bundle.authority_content import translation_link_selection as _implementation
sys.modules[__name__] = _implementation
globals().update({k:v for k,v in vars(_implementation).items() if not k.startswith("__")})
