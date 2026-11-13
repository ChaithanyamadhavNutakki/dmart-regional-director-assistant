"""Run weather-tool checks and the full twenty-case agent acceptance suite."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_weather_tests import main as run_weather_tests
from scripts.run_acceptance import main as run_acceptance


def main():
    run_weather_tests()
    run_acceptance()


if __name__ == "__main__":
    main()
