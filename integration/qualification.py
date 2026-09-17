"""Qualify exact provider integration through deterministic Bundle regeneration."""
from pathlib import Path
import tempfile
from integration.producer import produce
from publication_bundle.contract import BundleError, validate


def qualify(**inputs):
    output = Path(inputs['output'])
    if output.exists() or output.is_symlink():
        raise BundleError('refusing to replace existing Bundle')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Keep the first generation private until validation and a second generation
    # have both succeeded. A failed qualification must not leave a destination
    # that looks like a valid candidate Bundle.
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.qualification-') as temporary:
        first_output = Path(temporary) / 'first'
        first = produce(**{**inputs, 'output': first_output})
        # Validation reaches every model, source blob, publication file and provenance.
        validate(first_output, expected_producer={'authority':'integration','revision':inputs['producer_revision']},
                 expected_providers=inputs['provider_revisions'])
        repeated = {**inputs, 'output': Path(temporary) / 'second'}
        second = produce(**repeated)
        if first != second or (first_output/'bundle.json').read_bytes() != (repeated['output']/'bundle.json').read_bytes():
            raise BundleError('Bundle regeneration is not deterministic')
        if output.exists() or output.is_symlink():
            raise BundleError('Bundle destination appeared during qualification')
        first_output.rename(output)
    return first
