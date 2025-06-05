import os
import sys
from pathlib import Path

# Ensure the project root is on the import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pancake import Pancake


def test_flatten_name(tmp_path):
    out_dir = tmp_path / "out"
    p = Pancake(source_dir=str(tmp_path), output_dir=str(out_dir))
    test_path = os.path.join(str(tmp_path), 'src', 'engine', 'main.py')
    assert p.flatten_name(test_path) == 'src_engine_main.py'

