import pathlib
from typing import Any, Dict
from yeahml.build.components.callbacks.objects.base import CallbackContainer as CBC

import tensorflow as tf


from yeahml.log.yf_logging import config_logger
from yeahml.train.gradients.gradients import update_model_params
from yeahml.train.inference import inference_dataset

from yeahml.train.setup.datasets import get_datasets
from yeahml.train.setup.objectives import get_objectives
from yeahml.train.setup.callbacks import get_callbacks
from yeahml.train.setup.paths import (
    create_model_run_path,
    create_model_training_paths,
    get_tb_writers,
)

from yeahml.train.update_progress.tf_objectives import update_metric_objects
from yeahml.train.update_progress.tracker import (
    update_loss_trackers,
    update_metrics_tracking,
)
from yeahml.train.util import convert_to_single_pass_iterator, get_losses_to_update

# TODO: delete out before merging
from yeahml.build.components.callbacks.objects.printer import Printer as printer

from yeahml.train.setup.loop_dynamics import (  # obtain_optimizer_loss_mapping,; create_grouped_metrics,; map_in_config_to_objective,
    create_full_dict,
)

from yeahml.train.setup.optimizers import Optimizers

from yeahml.train.controller.controller import Controller

# from yeahml.build.load_params_onto_layer import init_params_from_file  # load params


"""
this training logic will need to be cleaned up/refactored a few times, but for
now it is "working" as I hoped.

- create a single fn that accepts "train"/"val" and does the logic (the loops
  are ~the same) and accepts a ds that is of the appropriate size .take()
- simplify/standardize the `return_dict` -- also accept any batch_steps for
  logging + determining when to save params.
- the variable naming throughout this is super inconsistent and not always
  accurate, I intend to improve this over time
- I need to validate the metric/loss/joint logic. I've only tried the present
  case and I'm not sure it will generalize well yet
- tensorboard -- I'm waiting until the loop logic is cleaned up before writing
  to tb again
- early stopping
- save best params
- create a variable in the graph to keep track of the number of batch
  steps/epochs run (if run from a notebook) --- also allow for the passing of an
  epoch param so that if we want to only run ~n more epochs from the notebook we
  can
- I'll also need to ensure the tracking dict is persisted.

- could keep note of all extra tricky batches/instances after n epochs.
"""


"""
TODO: check that all metrics are accounted for.  If so. raise a not
implemented error -- presently the training loop is driven by the
optimizers (and as a result all objectives that have matching in_configs).
meaning, if a metric does not have a matching in_config, it will not be
evaluated.

# TODO: random -- check for nans in loss values

TODO: build best loss dict

TODO: ASSUMPTION: using optimizers sequentially. this may be:
- jointly, ordered: sequentially, or unordered: alternate/random

NOTE: I'm not sure looping on epochs makes sense as an outter layer
anymore.
TODO: is there a way to save a variable in the graph to keep track of
epochs (if multiple runs from a notebook?)

TODO: per batch/epoch/adaptive -- all open questions.

NOTE: this isn't perfect in that someone may care about the output of
something they are not directly optimizing.. I'd argue the current
workaround is to specify that metric with a dataset and associate it to a
particular optimizer (it will eval at the same time this optimizer is run)


"""


def update_epoch_dict(
    obj_ds_to_epoch: Dict[str, Any],
    objective_name: str,
    dataset_name: str,
    split_name: str,
):
    """update num of iterations
    """
    try:
        obj_ds_to_epoch[objective_name][dataset_name][split_name] += 1
    except KeyError:
        # begin at 1 since it is initialized after being run
        tmp_dict = {objective_name: {dataset_name: {split_name: 1}}}
        obj_ds_to_epoch = {**obj_ds_to_epoch, **tmp_dict}
    return obj_ds_to_epoch


# TODO: epochs in 'budget'


class Trainer:
    def __init__(self, graph, config_dict, datasets):
        # parameterized graph to train/fit
        self.graph = graph

        # information about how to train
        self.model_cdict: Dict[str, Any] = config_dict["model"]
        self.meta_cdict: Dict[str, Any] = config_dict["meta"]
        self.log_cdict: Dict[str, Any] = config_dict["logging"]
        self.data_cdict: Dict[str, Any] = config_dict["data"]
        self.hp_cdict: Dict[str, Any] = config_dict["hyper_parameters"]
        self.perf_cdict: Dict[str, Any] = config_dict["performance"]
        self.optim_cdict: Dict[str, Any] = config_dict["optimize"]
        self.cb_cdict: Dict[str, Any] = config_dict["callbacks"]

        # data to train on
        self.datasets = datasets

        self.return_dict = {}

        full_exp_path = (
            pathlib.Path(self.meta_cdict["yeahml_dir"])
            .joinpath(self.meta_cdict["data_name"])
            .joinpath(self.meta_cdict["experiment_name"])
            .joinpath(self.model_cdict["name"])
        )
        # build paths and obtain tb writers
        self.model_run_path = create_model_run_path(full_exp_path)
        self.save_model_path, self.save_best_param_path = create_model_training_paths(
            self.model_run_path
        )

        # tensorboard writers
        self.tr_writer, self.v_writer = get_tb_writers(self.model_run_path)

        # profile_path = model_run_path.joinpath("tf_logs").joinpath("profile")

        self.logger = config_logger(self.model_run_path, self.log_cdict, "train")

        # get datasets
        self.dataset_dict = get_datasets(self.datasets, self.data_cdict, self.hp_cdict)

        # {objective_name: "in_config": {...}, "loss": {...}, "metric": {...}}
        # TODO: "train", "val" should be obtained from the config
        self.objectives_dict = get_objectives(
            self.perf_cdict["objectives"],
            self.dataset_dict,
            target_splits=["train", "val"],
        )

        # optimizers
        # {optimizer_name: {"optimizer": tf.obj, "objective": [objective_name]}}
        # self.optimizers_dict = get_optimizers(self.optim_cdict)
        self.optimizers = Optimizers(self.optim_cdict, self.objectives_dict)

        # create callbacks
        custom_callbacks = get_callbacks(self.cb_cdict)
        self.cbs = CBC(
            custom_callbacks,
            optimizer_names=list(self.optimizers.optimizers.keys()),
            dataset_names=list(self.dataset_dict.keys()),
            objective_names=list(self.objectives_dict.keys()),
        )
        # TODO: call all cbc methods at the appropriate time

        self.main_tracker_dict = create_full_dict(
            optimizers_dict=self.optimizers.optimizers,
            objectives_dict=self.objectives_dict,
            datasets_dict=self.dataset_dict,
        )

        self.dataset_iter_dict = convert_to_single_pass_iterator(self.dataset_dict)

        # TODO: create list order of directives to loop through -- I no longer know
        # that this is the best approach -- that is, this should be adaptive  and
        # learned during training and is related to  'how do I determine how "long"'
        # to go here... I think the 'right' answer is dependent on the losses (train
        # and val), but I think there is a short answer as well.
        # TODO: this needs to be driven by the directive, not just a walkthrough

        self.obj_ds_to_epoch = {}

        # initialize to True
        self.is_training = True

        # NOTE: really this should be per param .. not sure if that's relevant
        # not
        self.num_training_ops = 0
        # a core issue here is that we're doing this entire loop for a single batch
        # NOTE: consider changing is_training to `switch_optimizer`

        self.objective_to_output_index = self._create_objective_to_output_index()

        self.controller = Controller(
            self.optimizers.optimizers,
            self.dataset_dict,
            self.objectives_dict,
            ebudget=self.hp_cdict["epochs"],
            obj_policy="random",
            training=True,
        )

    def _create_objective_to_output_index(self):
        # TODO: this is hardcoded for supervised settings
        # tf.keras models output the model outputs in a list, we need to get the
        # of each prediction we care about from that output to use in the loss
        # function
        # NOTE: I'm not sure how I feel about this -- is it better to have multiple
        # "tf.models" that share params (is that even possible) -- or is it better
        # to do this where it is one "tf.model"?
        if isinstance(self.graph.output, list):
            model_output_order = [n.name.split("/")[0] for n in self.graph.output]
            objective_to_output_index = {}
            for obj_name, obj_dict in self.objectives_dict.items():
                try:
                    pred_name = obj_dict["in_config"]["options"]["prediction"]
                    out_index = model_output_order.index(pred_name)
                    objective_to_output_index[obj_name] = out_index
                except KeyError:
                    # TODO: perform check later
                    objective_to_output_index[obj_name] = None
        else:
            # TODO: this is hardcoded to assume supervised
            objective_to_output_index = {}
            for obj_name, obj_dict in self.objectives_dict.items():
                objective_to_output_index[obj_name] = None

        return objective_to_output_index

    def _log_model_params(self, writer, g_train_step):
        with writer.as_default():
            for v in self.graph.variables:
                tf.summary.histogram(v.name.split(":")[0], v.numpy(), step=g_train_step)

    # TODO: how to decide when training is done?
    def fit(self) -> Dict[str, Any]:
        self.logger.info("START - training")
        self._log_model_params(self.tr_writer, 0)

        while self.controller.training:

            # NOTE: if there are multiple objectives, they will be trained *jointly*
            # cur_optimizer_config:
            #   {'optimizer': <tf.opt{}>, 'objectives': ['main_obj']}
            # cur_apply_grad_fn = opt_name_to_gradient_fn[cur_optimizer_name]
            get_grads_fn = self.controller.cur_optimizer.get_grads_fn
            apply_grads_fn = self.controller.cur_optimizer.apply_grads_fn

            # TODO: these should really be grouped by the in config (likely by
            # creating a hash) this allows us to group objectives by what
            # dataset their using so that we can reuse the same batch.
            # NOTE: for now, I'm saving the prediction and gt (if supervised) in
            # the grad_dict

            obj_to_grads = {}
            # TODO: the losses should be grouped by the ds used so that we only
            # obtain+run the batch once+ensuring it's the same batch
            loss_update_dict, update_metrics_dict = {}, {}

            loss_conf = self.controller.cur_objective.performance.loss
            tf_train_loss_descs_to_update = get_losses_to_update(loss_conf, "train")

            # cur_train_iter = self.controller.cur_dataset.dataset.iter_dict["train"]
            cur_batch = self.controller.cur_dataset.dataset.get_next_batch("train")
            if not cur_batch:
                # dataset pass is complete
                self.obj_ds_to_epoch = update_epoch_dict(
                    self.obj_ds_to_epoch,
                    self.controller.cur_objective.name,
                    self.controller.cur_dataset.name,
                    "train",
                )

                self.logger.info(
                    f"epoch {self.controller.cur_objective.name} - {self.controller.cur_dataset.name} {'train'}:"
                    f" {self.obj_ds_to_epoch[self.controller.cur_objective.name][self.controller.cur_dataset.name]['train']}"
                )

                # perform validation after each pass through the training
                # dataset
                # NOTE: the location of this 'validation' may change
                # TODO: there is an error here where the first objective
                # will be validated on the last epoch and then one more
                # time.
                # TODO: ensure the metrics are reset
                #  iterate validation after iterating entire training..
                # this will/should change to update on a set frequency --
                # also, maybe we don't want to run the "full" validation,
                # only a (random) subset?

                # validation pass
                # TODO: here -- 1) adjust dataset access/use
                # print(self.controller.datasets["abalone"].dataset.iter_dict["val"])
                sys.exit()
                cur_val_update = inference_dataset(
                    self.graph,
                    self.controller,
                    self.dataset_iter_dict,
                    self.main_tracker_dict[self.controller.cur_optimizer.name],
                    self.dataset_dict,
                    self.num_training_ops,
                    self.objective_to_output_index,
                    self.objectives_dict,
                    self.v_writer,
                    self.logger,
                    split_name="val",
                )

                # log params used during validation in other location
                self._log_model_params(self.tr_writer, self.num_training_ops)

                # TODO: has run entire ds -- for now, time to break out of
                # this ds eventually, something smarter will need to be done
                # here in the training loop, not just after an epoch
                pass
            else:
                # grad_dict contains {
                #     "gradients": grads,
                #     "predictions": prediction,
                #     "final_loss": final_loss,
                #     "losses": loss,
                # }
                grad_dict = get_grads_fn(
                    self.graph,
                    cur_batch,
                    self.controller.cur_objective.performance.loss["object"],
                    self.objective_to_output_index[self.controller.cur_objective.name],
                    tf_train_loss_descs_to_update,
                )

                # TODO: see note above about ensuring the same batch is used for
                # losses with the same dataset specified
                self.controller.cur_optimizer.num_train_steps += cur_batch[0].shape[0]
                self.num_training_ops += 1

                # TODO: currently this only stores the last grad dict per objective
                obj_to_grads[self.controller.cur_objective.name] = grad_dict

                # NOTE: the steps here aren't accurate (due to note above about)
                # using the same batches for objectives/losses that specify the
                # same datasets
                # update_tf_loss_descriptions(
                #     grad_dict, tf_train_loss_descs_to_update
                # )
                # # TODO: add to tensorboard

                # create histograms of model parameters
                if self.log_cdict["track"]["tensorboard"]["param_steps"] > 0:
                    if (
                        self.num_training_ops
                        % self.log_cdict["track"]["tensorboard"]["param_steps"]
                        == 0
                    ):
                        self._log_model_params(self.tr_writer, self.num_training_ops)

                # update Tracker
                if self.log_cdict["track"]["tracker_steps"] > 0:
                    if (
                        self.num_training_ops % self.log_cdict["track"]["tracker_steps"]
                        == 0
                    ):
                        cur_loss_tracker_dict = self.main_tracker_dict[
                            self.controller.cur_optimizer.name
                        ][self.controller.cur_objective.name]["loss"][
                            self.controller.cur_dataset.name
                        ][
                            "train"
                        ]
                        cur_loss_update = update_loss_trackers(
                            loss_conf["track"]["train"],
                            cur_loss_tracker_dict,
                            self.controller.cur_optimizer.num_train_steps,
                            self.num_training_ops,
                            tb_writer=self.tr_writer,
                            ds_name=self.controller.cur_dataset.name,
                            objective_name=self.controller.cur_objective.name,
                        )

                        loss_update_dict[
                            self.controller.cur_objective.name
                        ] = cur_loss_update

                # TODO: this is a hacky way of seeing if training on a batch was run
                if obj_to_grads:
                    update_model_params(
                        apply_grads_fn,
                        obj_to_grads,
                        self.graph,
                        self.controller.cur_optimizer.object,
                    )

                    update_metric_objects(
                        self.controller.cur_optimizer.metrics,
                        self.objectives_dict,
                        obj_to_grads,
                        "train",
                    )

                    if self.log_cdict["track"]["tracker_steps"] > 0:
                        if (
                            self.num_training_ops
                            % self.log_cdict["track"]["tracker_steps"]
                            == 0
                        ):
                            update_metrics_dict = update_metrics_tracking(
                                self.controller.cur_optimizer.metrics,
                                self.objectives_dict,
                                self.main_tracker_dict[
                                    self.controller.cur_optimizer.name
                                ],
                                obj_to_grads,
                                self.controller.cur_optimizer.num_train_steps,
                                self.num_training_ops,
                                "train",
                                tb_writer=self.tr_writer,
                                ds_name=self.controller.cur_dataset.name,
                                objective_name=self.controller.cur_objective.name,
                            )
                objective_advanced = self.controller.maybe_advance_objective()

            # update_dict = {"loss": loss_update_dict, "metrics": update_metrics_dict}
        return_dict = {"tracker": self.main_tracker_dict}

        return return_dict

    # one pass of training (a batch from each objective) with the
    # current optimizer

    # TODO: I think the 'joint' should likely be the optimizer name, not the
    # combination of losses name, this would also simplify the creation of these

    # # TODO: adjust
    # train_best_joint_update = record_joint_losses(
    #     "train",
    #     "epoch",
    #     e,
    #     joint_dict_tracker,
    #     joint_loss_name,
    #     joint_loss_record_train,
    # )

    # TODO: save best params with update dict and save params
    # accordingly
    # TODO: use early_stopping:epochs and early_stopping:warmup
    # if cur_val_loss_ < best_val_loss:
    #     if e == 0:
    #         # on the first time params are saved, try to save the model
    #         model.save(save_model_path)
    #         logger.debug(f"model saved to: {save_model_path}")
    #     best_val_loss = cur_val_loss_
    #     model.save_weights(save_best_param_path)

    #     logger.debug(f"best params saved: val loss:
    #     {cur_val_loss_:.4f}")