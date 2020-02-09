from yeahml.build.components.loss import return_available_losses
from yeahml.build.components.metric import return_available_metrics
from yeahml.build.components.optimizer import return_available_optimizers
from yeahml.config.default.config_types import (
    categorical,
    list_of_categorical,
    numeric,
    optional_config,
    parameter_config,
    data_in_spec,
    dict_of_data_in_spec,
)


def hithere():
    return 42


# numeric(
#     required=None,
#     is_type=None,
#     description=None,
#     fn=None,
#     fn_args=None,
#     # specifc
#     value=None,
#     bounds=None,
# )
# categorical(
#     required=None,
#     is_type=None,
#     description=None,
#     fn=None,
#     fn_args=None,
#     # specific
#     value=None,
#     is_subset=None,
# )
# loop keys
# if type == dict recursive
# else, fill
# return

# meta
# TODO: set accepted options for `trace_level`
# TODO: ensure `default_load_params_path` is a path.. also, does this belong in
# meta?
# TODO: I'm not sure trace_level is used anymore
# TODO: numbers could probably be converted to string (for experiment_name?)
meta = {
    "meta": {
        # directory
        "yeahml_dir": categorical(
            default_value="yeahml", required=False, is_type=str
        ),  # could add a check that the location exists
        "data_name": categorical(default_value=None, required=True, is_type=str),
        "experiment_name": categorical(default_value=None, required=True, is_type=str),
        # random seed
        "rand_seed": numeric(default_value=None, required=False, is_type=int),
        # tracing
        "trace_level": categorical(default_value=None, required=False),
        # default path to load param information
        # TODO: this should likely move to the model config
        "default_load_params_path": categorical(
            default_value=None, required=False, is_type=str
        ),  # TODO: confirm path exists
    }
}

# TODO: eventually, we need to support custom performance/loss metrics
performance = {
    "performance": {
        "metric": {
            "type": list_of_categorical(
                default_value=None,
                is_type=str,
                required=True,
                is_in_list=return_available_metrics(),
            ),
            "options": list_of_categorical(
                default_value=None, is_type=list, required=False
            ),
        },
        # TODO: support multiple losses -- currently only one loss is supported
        "loss": {
            "type": categorical(
                default_value=None,
                required=True,
                is_in_list=return_available_losses(),
                is_type=str,
            ),
            # TODO: error check that options are valid
            "options": categorical(default_value=None, required=False, is_type=str),
        },
    }
}

hyper_parameters = {
    "hyper_parameters": {
        "dataset": {
            "batch": numeric(default_value=None, required=True, is_type=int),
            "shuffle_buffer": numeric(default_value=None, required=False, is_type=int),
        },
        "epochs": numeric(default_value=None, required=True, is_type=int),
        # TODO: need to account for optional outter keys
        "early_stopping": optional_config(
            conf_dict={
                "epochs": numeric(default_value=None, required=False, is_type=int),
                "warm_up": numeric(default_value=None, required=False, is_type=int),
            }
        ),
        # TODO: Right now I'm assuming 1 loss and one optimizer.. this isn't
        # and needs to be reconsidered
        "optimizer": {
            "type": categorical(
                default_value=None,
                required=True,
                is_in_list=return_available_optimizers(),
            ),
            # TODO: this isn't really a list of categorical.... most are numeric
            "options": parameter_config(
                known_dict={
                    "learning_rate": numeric(
                        default_value=None, required=True, is_type=float
                    )
                }
            ),
        },
    }
}


ERR_LEVELS = [x.lower() for x in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]]

logging = {
    "logging": {
        "console": {
            "level": categorical(
                default_value="CRITICAL", required=False, is_in_list=ERR_LEVELS
            ),
            "format_str": categorical(
                default_value="%(name)-12s: %(levelname)-8s %(message)s", required=False
            ),
        },
        "file": {
            "level": categorical(
                default_value="CRITICAL", required=False, is_in_list=ERR_LEVELS
            ),
            "format_str": categorical(
                default_value="%(filename)s:%(lineno)s - %(funcName)20s()][%(levelname)-8s]: %(message)s",
                required=False,
            ),
        },
    }
}


# Data
data = {"data": {"in": dict_of_data_in_spec()}}


preprocess = {"preprocess": {}}

# # copy is used to prevent overwriting underlying data
# formatted_dict["input_layer_dim"] = None
# formatted_dict["in_dim"] = raw_config["in"]["dim"].copy()
# if formatted_dict["in_dim"][0]:  # as oppposed to [None, x, y, z]
#     formatted_dict["in_dim"].insert(0, None)  # add batching
# formatted_dict["in_dtype"] = raw_config["in"]["dtype"]
# try:
#     formatted_dict["reshape_in_to"] = raw_config["in"]["reshape_to"]
#     if formatted_dict["reshape_in_to"][0] != -1:  # as oppposed to [None, x, y, z]
#         formatted_dict["reshape_in_to"].insert(0, -1)  # -1
# except KeyError:
#     # None in this case is representative of not reshaping
#     formatted_dict["reshape_in_to"] = None
# if formatted_dict["reshape_in_to"]:
#     formatted_dict["input_layer_dim"] = raw_config["in"]["reshape_to"]
# else:
#     formatted_dict["input_layer_dim"] = raw_config["in"]["dim"].copy()


# formatted_dict["output_dim"] = raw_config["label"]["dim"].copy()
# if formatted_dict["output_dim"][0]:  # as oppposed to [None, x, y, z]
#     formatted_dict["output_dim"].insert(0, None)  # add batching

# formatted_dict["label_dtype"] = raw_config["label"]["dtype"]

# formatted_dict["label_one_hot"] = raw_config["label"]["one_hot"]

# formatted_dict["TFR_dir"] = raw_config["TFR"]["dir"]
# formatted_dict["TFR_train"] = raw_config["TFR"]["train"]
# formatted_dict["TFR_test"] = raw_config["TFR"]["test"]
# formatted_dict["TFR_val"] = raw_config["TFR"]["validation"]

# # TODO: this is a first draft for this type of organization and will
# # will likely be changed
# formatted_dict["data_in_dict"] = raw_config["in"]
# formatted_dict["data_out_dict"] = raw_config["label"]
# formatted_dict["TFR_parse"] = raw_config["TFR_parse"]

# formatted_dict["augmentation"] = raw_config["image"]["augmentation"]

# formatted_dict["image_standardize"] = raw_config["image"]["standardize"]


model = {"model": {}}

DEFAULT_CONFIG = {}
DEFAULT_CONFIG = {**DEFAULT_CONFIG, **meta}
DEFAULT_CONFIG = {**DEFAULT_CONFIG, **performance}
DEFAULT_CONFIG = {**DEFAULT_CONFIG, **hyper_parameters}
DEFAULT_CONFIG = {**DEFAULT_CONFIG, **logging}