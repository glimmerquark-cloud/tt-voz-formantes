"""Corre las pruebas cocotb con Icarus sin make (util en Windows).

Uso (con oss-cad-suite/bin en PATH):  python sim/run_tests.py [nombre_de_prueba]
"""
from pathlib import Path
import sys

from cocotb_tools.runner import get_runner

root = Path(__file__).resolve().parent.parent
test_dir = root / "test"
sys.path.insert(0, str(test_dir))

runner = get_runner("icarus")
runner.build(
    sources=[root / "src" / "project.v", test_dir / "tb.v"],
    hdl_toplevel="tb",
    build_dir=root / "sim" / "build",
    always=True,
)
runner.test(
    hdl_toplevel="tb",
    test_module="test",
    test_dir=test_dir,
    build_dir=root / "sim" / "build",
    test_filter=sys.argv[1] if len(sys.argv) > 1 else None,
    extra_env={"PYTHONPATH": str(test_dir)},
)
