import crummycm as ccm
from crummycm.validation.types.placeholders.placeholder import (
    KeyPlaceholder as KPH,
    ValuePlaceholder as VPH,
)
from crummycm.validation.types.values.element.numeric import Numeric
from crummycm.validation.types.values.element.text import Text
from crummycm.validation.types.values.element.bool import Bool
from crummycm.validation.types.values.compound.multi import Multi

ERR_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
ERR_LEVELS = ERR_LEVELS + [x.lower() for x in ERR_LEVELS]

LOGGING = {
    "logging": {
        KPH("console", exact=True, populate=True, required=False): {
            "level": Text(
                default_value="critical",
                is_in_list=ERR_LEVELS,
                to_lower=True,
                description="level to log information to the console",
            ),
            "format_str": Text(
                default_value="%(name)-12s: %(levelname)-8s %(message)s"
            ),
        },
        KPH("file", exact=True, populate=True, required=False): {
            "level": Text(
                default_value="critical",
                is_in_list=ERR_LEVELS,
                to_lower=True,
                description="level to log information to a file",
            ),
            "format_str": Text(
                default_value="%(filename)s:%(lineno)s - %(funcName)20s()][%(levelname)-8s]: %(message)s"
            ),
        },
        KPH("track", exact=True, populate=True, required=False): {
            "tracker_steps": Numeric(
                default_value=0,
                is_type=int,
                description="the frequency (as a number of training steps) at which to log tracker information",
            ),
            "tensorboard": {"param_steps": Numeric(default_value=0, is_type=int)},
        },
    }
}
