"""Decode opaque repository-path data from the Bundle."""
import base64
from publication_bundle.contract import BundleError

def raw_path(value):
    if not isinstance(value,dict) or set(value)!={'base64'} or not isinstance(value['base64'],str):
        raise BundleError('invalid encoded repository path')
    try:raw=base64.b64decode(value['base64'],validate=True)
    except ValueError as exc:raise BundleError('invalid path base64') from exc
    if base64.b64encode(raw).decode()!=value['base64'] or not raw or b'\0' in raw:
        raise BundleError('invalid repository path identity')
    return raw


