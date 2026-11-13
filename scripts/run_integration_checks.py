"""Run weather-tool checks and the full twenty-case agent acceptance suite."""

from scripts.run_weather_tests import main as run_weather_tests
from scripts.run_acceptance import main as run_acceptance


def main():
    run_weather_tests()
    run_acceptance()


if __name__ == "__main__":
    main()
