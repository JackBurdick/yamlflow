import os
import pathlib
from typing import Any, Dict
from pathlib import Path

import tensorflow as tf

from yeahml.build.components.loss import configure_loss
from yeahml.build.components.metric import configure_metric
from yeahml.dataset.handle_data import return_batched_iter  # datasets from tfrecords
from yeahml.dataset.util import get_configured_dataset
from yeahml.log.yf_logging import config_logger  # custom logging
from yeahml.train.inference import inference_dataset

#####
from yeahml.train.util import (
    convert_to_single_pass_iterator,
    get_losses_to_update,
    get_next_batch,
    re_init_iter,
)
from yeahml.train.gradients.gradients import get_validation_step_fn

################
from yeahml.config.model.util import make_hash
from yeahml.train.setup.datasets import get_datasets
from yeahml.train.setup.paths import create_model_run_path
from yeahml.train.setup.objectives import get_objectives


@tf.function
def eval_step(model, x_batch, y_batch, loss_fn, loss_avg, metric_fns):
    prediction = model(x_batch)
    loss = loss_fn(y_batch, prediction)

    # NOTE: only allow one loss
    loss_avg(loss)

    # TODO: log outputs

    # TODO: ensure pred, gt order
    for eval_metric_fn in metric_fns:
        eval_metric_fn(y_batch, prediction)


def create_ds_to_lm_mapping(perf_cdict):
    """

    For evaluation, we would like to be efficient with looping over the
    datasets.
    
    ds_to_chash is used to iterate on the dataset on the outer loop then group
    metrics/losses by the same in_config (which may be the same prediction node
    and label), which is indexed by a hash.

    the chash_to_in_config, is then used to map the hash to which nodes to pull
    from on the graph


    e.g.
    `ds_to_chash`
        {
            "abalone": {
                -2976269282734729230: {"metrics": set(), "loss": {"second_obj", "main_obj"}}
            }
        }


    `chash_to_in_config`
        {
            -2976269282734729230: {
                "type": "supervised",
                "options": {"prediction": "dense_out", "target": "target_v"},
                "dataset": "abalone",
            }
        }
    
    """

    # map datasets to objectives
    ds_to_obj = {}
    for key, val in perf_cdict["objectives"].items():
        ds = val["in_config"]["dataset"]
        try:
            ds_to_obj[ds].append(key)
        except KeyError:
            ds_to_obj[ds] = [key]

    # map objectives to losses and metrics
    ds_to_chash = {}
    chash_to_in_config = {}
    for ds_name, ds_objs in ds_to_obj.items():
        ds_to_chash[ds_name] = {}
        loss_objective_names = set()
        metrics_objective_names = set()
        for objective in ds_objs:
            cur_obj_dict = perf_cdict["objectives"][objective]
            conf_hash = make_hash(cur_obj_dict["in_config"])
            try:
                assert (
                    chash_to_in_config[conf_hash] == cur_obj_dict["in_config"]
                ), f"hash not equal"
            except KeyError:
                chash_to_in_config[conf_hash] = cur_obj_dict["in_config"]
            if "loss" in cur_obj_dict.keys():
                if cur_obj_dict["loss"]:
                    loss_objective_names.add(objective)
            if "metrics" in cur_obj_dict.keys():
                if cur_obj_dict["metrics"]:
                    metrics_objective_names.add(objective)

            # make the outter dict if not yet made
            try:
                _ = ds_to_chash[ds_name][conf_hash]
            except KeyError:
                ds_to_chash[ds_name][conf_hash] = {
                    "inference_fn": get_validation_step_fn()
                }

            try:
                s = ds_to_chash[ds_name][conf_hash]["metrics"]
                if metrics_objective_names:
                    s.update(metrics_objective_names)
            except KeyError:
                ds_to_chash[ds_name][conf_hash]["metrics"] = metrics_objective_names

            try:
                s = ds_to_chash[ds_name][conf_hash]["loss"]
                if loss_objective_names:
                    s.update(loss_objective_names)
            except KeyError:
                ds_to_chash[ds_name][conf_hash]["loss"] = loss_objective_names

    return ds_to_chash, chash_to_in_config


def eval_model(
    model: Any,
    config_dict: Dict[str, Dict[str, Any]],
    datasets: Any = None,
    weights_path: str = "",
) -> Dict[str, Any]:

    # TODO: option to reinitialize model?

    # unpack configurations
    model_cdict: Dict[str, Any] = config_dict["model"]

    # set up loop for performing inference more efficiently
    perf_cdict: Dict[str, Any] = config_dict["performance"]
    ds_to_chash, chash_to_in_config = create_ds_to_lm_mapping(perf_cdict)

    # obtain datasets
    # TODO: hyperparams (depending on implementation) may not be relevant here
    data_cdict: Dict[str, Any] = config_dict["data"]
    hp_cdict: Dict[str, Any] = config_dict["hyper_parameters"]
    dataset_dict = get_datasets(datasets, data_cdict, hp_cdict)
    dataset_iter_dict = convert_to_single_pass_iterator(dataset_dict)

    # obtain logger
    log_cdict: Dict[str, Any] = config_dict["logging"]
    meta_cdict: Dict[str, Any] = config_dict["meta"]
    full_exp_path = (
        pathlib.Path(meta_cdict["yeahml_dir"])
        .joinpath(meta_cdict["data_name"])
        .joinpath(meta_cdict["experiment_name"])
        .joinpath(model_cdict["name"])
    )
    # build paths and obtain tb writers
    model_run_path = create_model_run_path(full_exp_path)
    logger = config_logger(model_run_path, log_cdict, "eval")

    # TODO: this block should be abstracted away to be used by both
    # train/inference loops
    # TODO: this is hardcoded for supervised settings
    # tf.keras models output the model outputs in a list, we need to get the index
    # of each prediction we care about from that output to use in the loss
    # function
    # TODO: Additionally, this assumes the targeted variable is a model `output`
    # NOTE: rather than `None` when a model only outputs a single value, maybe
    # there should be a magic keyword/way to denote this.
    if isinstance(model.output, list):
        MODEL_OUTPUT_ORDER = [n.name.split("/")[0] for n in model.output]
        chash_to_output_index = {}
        for chash, cur_in_config in chash_to_in_config.items():
            try:
                assert (
                    cur_in_config["type"] == "supervised"
                ), f"only supervised is currently allowed, not {cur_in_config['type']} :("
                pred_name = cur_in_config["options"]["prediction"]
                out_index = MODEL_OUTPUT_ORDER.index(pred_name)
                chash_to_output_index[chash] = out_index
            except KeyError:
                # TODO: perform check later
                chash_to_output_index[chash] = None
    else:
        chash_to_output_index = {}
        for chash, cur_in_config in chash_to_in_config.items():
            assert (
                cur_in_config["type"] == "supervised"
            ), f"only supervised is currently allowed, not {cur_in_config['type']} :("
            assert (
                model.output.name.split("/")[0]
                == cur_in_config["options"]["prediction"]
            ), f"model output {model.output.name.split('/')[0]} does not match prediction of cur_in_config: {cur_in_config}"
            chash_to_output_index[chash] = None

    # print("====" * 8)
    # print(ds_to_chash)
    # print("----")
    # print(chash_to_in_config)
    # print("-----")
    # print(dataset_iter_dict)
    # print("--" * 8)
    # print(chash_to_output_index)

    print("........" * 8)
    logger.info("START - evaluating")
    for cur_ds_name, chash_conf_d in ds_to_chash.items():
        logger.info(f"current dataset: {cur_ds_name}")
        for in_hash, cur_hash_conf in chash_conf_d.items():
            cur_objective_config = chash_to_in_config[in_hash]
            assert (
                cur_objective_config["type"] == "supervised"
            ), f"only supervised is currently allowed, not {cur_objective_config['type']} :("
            logger.info(f"current config: {cur_objective_config}")

            cur_inference_fn = cur_hash_conf["inference_fn"]
            cur_metrics = cur_hash_conf["metrics"]
            cur_losses = cur_hash_conf["loss"]
            cur_ds_iter = dataset_iter_dict[cur_ds_name]
            cur_pred_index = chash_to_output_index[in_hash]
            cur_target_name = cur_objective_config["options"]["target"]
            print(cur_target_name)

        print(chash_conf_d)
        print("====")

    objectives_dict = get_objectives(perf_cdict["objectives"], dataset_dict)
    print("XXXXX" * 8)
    print(objectives_dict)

    raise NotImplementedError(f"not implemented yet")

    # logger.info(f"objective: {cur_objective}")

    # # TODO: next step -- continue_objective = True
    # # each loss may be being optimized by data from different datasets
    # cur_ds_name = objectives_dict[cur_objective]["in_config"]["dataset"]
    # loss_conf = objectives_dict[cur_objective]["loss"]
    # tf_train_loss_descs_to_update = get_losses_to_update(loss_conf, "train")

    # cur_train_iter = get_train_iter(dataset_iter_dict, cur_ds_name, "train")

    # while continue_objective:
    #     cur_batch = get_next_batch(cur_train_iter)
    #     if not cur_batch:

    #         # validation pass
    #         cur_val_update = inference_dataset(
    #             model,
    #             loss_objective_names,
    #             metrics_objective_names,
    #             dataset_iter_dict,
    #             opt_to_validation_fn[cur_optimizer_name],
    #             opt_tracker_dict,
    #             cur_objective,
    #             cur_ds_name,
    #             dataset_dict,
    #             opt_to_steps[cur_optimizer_name],
    #             num_training_ops,
    #             objective_to_output_index,
    #             objectives_dict,
    #             v_writer,
    #             logger,
    #             split_name="val",
    #         )

    # # TODO: it also be possible to use this without passing the model?

    # # load best weights
    # # TODO: load specific weights according to a param

    # model_path = full_exp_path.joinpath("model")
    # if model_path.is_dir():
    #     sub_dirs = [x for x in model_path.iterdir() if x.is_dir()]
    #     most_recent_subdir = sub_dirs[0]
    #     # TODO: this assumes .h5 is the filetype and that model.h5 is present
    #     most_recent_save_path = Path(most_recent_subdir).joinpath("save")

    # # TODO: THis logic/specification needs to be validated. Is this what we
    # # want? what if we want to specify a specific run? Where should we get that information?
    # if weights_path:
    #     specified_path = weights_path
    # else:
    #     # TODO: this needs to allow an easier specification for which params to load
    #     # The issue here is that if someone alters the model (perhaps in a notebook), then
    #     # retrains the model (but doesn't update the config), the "old" model, not new model
    #     # will be evaluated.  This will need to change
    #     specified_path = most_recent_save_path.joinpath("params").joinpath(
    #         "best_params.h5"
    #     )

    # if not specified_path.is_file():
    #     raise ValueError(
    #         f"specified path is neither an h5 path, nor a directory containing directories of h5: {specified_path}"
    #     )

    # model.load_weights(str(specified_path))
    # logger.info(f"params loaded from {specified_path}")

    # # Right now, we're only going to add the first loss to the existing train
    # # loop
    # objective_list = list(perf_cdict["objectives"].keys())
    # if len(objective_list) > 1:
    #     raise ValueError(
    #         "Currently, only one objective is supported by the training loop logic. There are {len(objective_list)} specified ({objective_list})"
    #     )
    # first_and_only_obj = objective_list[0]

    # # loss
    # # get loss function
    # loss_object = configure_loss(perf_cdict["objectives"][first_and_only_obj]["loss"])

    # # mean loss
    # avg_eval_loss = tf.keras.metrics.Mean(name="validation_loss", dtype=tf.float32)

    # # metrics
    # eval_metric_fns, metric_order = [], []
    # # TODO: this is hardcoded to only the first objective
    # met_opts = perf_cdict["objectives"][first_and_only_obj]["metric"]["options"]
    # # TODO: this is hardcoded to only the first objective
    # for i, metric in enumerate(
    #     perf_cdict["objectives"][first_and_only_obj]["metric"]["type"]
    # ):
    #     try:
    #         met_opt_dict = met_opts[i]
    #     except TypeError:
    #         # no options
    #         met_opt_dict = None
    #     except IndexError:
    #         # No options for particular metric
    #         met_opt_dict = None
    #     eval_metric_fn = configure_metric(metric, met_opt_dict)
    #     eval_metric_fns.append(eval_metric_fn)
    #     metric_order.append(metric)

    # # reset metrics (should already be reset)
    # for eval_metric_fn in eval_metric_fns:
    #     eval_metric_fn.reset_states()

    # # TODO: log each instance

    # return eval_dict
