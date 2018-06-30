#!/usr/bin/env python
import yaml
import shutil
import os


def parse_yaml_from_path(path: str) -> dict:
    # return python dict from yaml path
    with open(path, "r") as stream:
        try:
            y = yaml.load(stream)
            return y
        except yaml.YAMLError as exc:
            print(exc)
            return None


def create_model_and_arch_config(path: str) -> (dict, dict):
    # return the model and archtitecture configuration dicts
    m_config = parse_yaml_from_path(path)
    # create architecture config
    if m_config["architecture"]["yaml"]:
        a_config = parse_yaml_from_path(m_config["architecture"]["yaml"])
    else:
        a_config = m_config["architecture"]

    return (m_config, a_config)


# helper to create dirs if they don't already exist
def maybe_create_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print("{} created".format(dir_path))
    else:
        print("{} already exists".format(dir_path))


def create_standard_dirs(root_dir, wipe):
    # this logic is messy
    if wipe:
        if os.path.exists(root_dir):
            shutil.rmtree(root_dir)
        maybe_create_dir(root_dir)
    else:
        maybe_create_dir(root_dir)

    # maybe_create_dir(root_dir + "/saver")
    # `best_params/` will hold a serialized version of the best params
    # I like to keep this as a backup in case I run into issues with
    # the saver files
    maybe_create_dir(root_dir + "/best_params")
    # `tf_logs/` will hold the logs that will be visable in tensorboard
    maybe_create_dir(root_dir + "/tf_logs")


def extract_from_dict(MC: dict, AC: dict) -> (dict, dict):
    # this is necessary since the YAML structure is likely to change
    # eventually, this can be deleted
    MCd = {}
    # ACd = {}
    ## inputs
    MCd["in_dim"] = MC["data"]["in_dim"]
    if MCd["in_dim"][0]:
        MCd["in_dim"].insert(0, None)  # add batching

    MCd["output_dim"] = MC["data"]["output_dim"]
    if MCd["output_dim"][0]:
        MCd["output_dim"].insert(0, None)  # add batching

    MCd["TFR_dir"] = MC["data"]["TFR_dir"]

    ## hyperparams
    MCd["lr"] = MC["hyper_parameters"]["lr"]
    MCd["epochs"] = MC["hyper_parameters"]["epochs"]
    MCd["batch_size"] = MC["hyper_parameters"]["batch_size"]
    ## implementation
    MCd["optimizer"] = MC["implementation"]["optimizer"]
    MCd["def_act"] = MC["implementation"]["default_activation"]
    MCd["shuffle_buffer"] = MC["implementation"]["shuffle_buffer"]

    ### architecture
    # TODO: implement after graph can be created...l
    MCd["save_pparams"] = MC["saver"]["save_pparams"]
    MCd["final_type"] = MC["overall"]["options"]
    MCd["seed"] = MC["overall"]["rand_seed"]
    MCd["trace_level"] = MC["overall"]["trace"]
    MCd["print_g_spec"] = MC["overall"]["print_graph_spec"]
    MCd["name"] = MC["overall"]["name"]

    try:
        MCd["augmentation"] = MC["train"]["augmentation"]
    except KeyError:
        pass

    MCd["log_dir"] = os.path.join(
        ".", "example", "cats_v_dogs_01", MC["tensorboard"]["log_dir"]
    )
    # wipe is set to true for now
    create_standard_dirs(MCd["log_dir"], True)

    return (MCd, AC)


# TODO: will need to implement preprocessing logic
