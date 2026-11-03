"""Statistics used by the explicit offline developer performance probe."""
import importlib.util
from pathlib import Path


def test_percentiles_are_defined_for_empty_and_small_samples():
    spec = importlib.util.spec_from_file_location('beta_benchmark', Path(__file__).resolve().parents[1] / 'scripts/benchmark-beta.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.summarize([]) == {'count': 0}
    result = module.summarize([1, 2, 3, 100])
    assert result['count'] == 4
    assert result['min'] == 1
    assert result['max'] == 100
    assert result['median'] == 2.5
    assert result['p95'] == 100