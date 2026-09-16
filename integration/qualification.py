"""Qualify exact provider integration through deterministic Bundle regeneration."""
from pathlib import Path
import tempfile
from integration.producer import produce
from publication_bundle.contract import BundleError, validate


def qualify(**inputs):
    output = Path(inputs['output'])
    first = produce(**inputs)
    # Validation reaches every model, source blob, publication file and provenance.
    validate(output, expected_producer={'authority':'site-internal-integration','revision':inputs['producer_revision']},
             expected_providers=inputs['provider_revisions'])
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        repeated = {**inputs, 'output': Path(temporary) / 'bundle'}
        second = produce(**repeated)
        if first != second or (output/'bundle.json').read_bytes() != (repeated['output']/'bundle.json').read_bytes():
            raise BundleError('Bundle regeneration is not deterministic')
    return first
