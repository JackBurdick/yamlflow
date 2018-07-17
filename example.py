import os
import logging

import yamlflow as yf

# TODO: this needs to be handled differently
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
# os.environ["TF_USE_CUDNN"] = "1" # necessary for Conv2d

## Core Logic

## Config files for currently supported modes
sigmoid_example = "./examples/cats_v_dogs_01/model_config.yaml"
# softmax_example = "./examples/mnist/model_config.yaml"
model_config, hidden_config = yf.create_model_and_hidden_config(sigmoid_example)


## build graph
g = yf.build_graph(model_config, hidden_config)

## train graph
_ = yf.train_graph(g, model_config, hidden_config)

## evaluate graph
# _ = eval_graph(g, model_config)

## same as above, but does not require manual graph creation
# > will load a graph from the saver path (if present)
_ = yf.eval_graph_from_saver(model_config)


## Serving
## TODO: implementation