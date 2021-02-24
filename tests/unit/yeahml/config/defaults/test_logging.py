import pytest

from yeahml.config.template.components.logging import LOGGING
from util import parse_default

# TODO: test options
ex_config = {
    # ----- REQUIRED
    # missing
    "minimal_00": (
        {"logging": {}},
        {
            "logging": {
                "console": {
                    "level": "critical",
                    "format_str": "%(name)-12s: %(levelname)-8s %(message)s",
                },
                "file": {
                    "level": "critical",
                    "format_str": "%(filename)s:%(lineno)s - %(funcName)20s()][%(levelname)-8s]: %(message)s",
                },
                "track": {"tracker_steps": 0, "tensorboard": {"param_steps": 0}},
            }
        },
    ),
    "working_00": (
        {
            "logging": {
                "console": {
                    "level": "critical",
                    "format_str": "%(name)-12s: %(levelname)-8s %(message)s",
                },
                "file": {
                    "level": "critical",
                    "format_str": "%(filename)s:%(lineno)s - %(funcName)20s()][%(levelname)-8s]: %(message)s",
                },
                "track": {"tracker_steps": 30, "tensorboard": {"param_steps": 50}},
            }
        },
        {
            "logging": {
                "console": {
                    "level": "critical",
                    "format_str": "%(name)-12s: %(levelname)-8s %(message)s",
                },
                "file": {
                    "level": "critical",
                    "format_str": "%(filename)s:%(lineno)s - %(funcName)20s()][%(levelname)-8s]: %(message)s",
                },
                "track": {"tracker_steps": 30, "tensorboard": {"param_steps": 50}},
            }
        },
    ),
}


@pytest.mark.parametrize(
    "config,expected", ex_config.values(), ids=list(ex_config.keys())
)
def test_default(config, expected):
    """test parsing of logging"""
    if isinstance(expected, dict):
        formatted_config = parse_default(config, LOGGING)
        assert expected == formatted_config
    elif isinstance(expected, ValueError):
        with pytest.raises(ValueError):
            formatted_config = parse_default(config, LOGGING)
    elif isinstance(expected, TypeError):
        with pytest.raises(TypeError):
            formatted_config = parse_default(config, LOGGING)
