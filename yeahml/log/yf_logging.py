import logging
import os


# this may be a "dumb" way of accomplishing this, but I want to wait until
# the modules are implemented correctly
def config_logger(main_cdict: dict, log_type: str):
    # TODO: should this check if the logger already exists?
    def get_level(level_str: str):
        level = None
        if level_str == "DEBUG":
            level = logging.DEBUG
        elif level_str == "INFO":
            level = logging.INFO
        elif level_str == "WARNING":
            level = logging.WARNING
        elif level_str == "ERROR":
            level = logging.ERROR
        elif level_str == "CRITICAL":
            level = logging.CRITICAL
        else:
            level = None

        return level

    # formatting
    c_fmt = logging.Formatter(main_cdict["log_c_str"])
    f_fmt = logging.Formatter(main_cdict["log_f_str"])
    g_fmt = logging.Formatter(main_cdict["log_g_str"])
    p_fmt = logging.Formatter(main_cdict["log_p_str"])

    if log_type == "build":
        build_logger = logging.getLogger("build_logger")
        build_logger.propagate = False
        build_logger.setLevel(get_level("DEBUG"))  # set base to lowest level
        b_ch = logging.StreamHandler()
        b_fh = logging.FileHandler(
            os.path.join(main_cdict["log_dir"], "yf_logs", "build.log")
        )

        b_ch.setLevel(get_level(main_cdict["log_c_lvl"]))
        b_fh.setLevel(get_level(main_cdict["log_f_lvl"]))

        b_ch.setFormatter(c_fmt)
        b_fh.setFormatter(f_fmt)

        build_logger.addHandler(b_ch)
        build_logger.addHandler(b_fh)

        return build_logger
    elif log_type == "train":
        train_logger = logging.getLogger("train_logger")
        train_logger.propagate = False
        train_logger.setLevel(
            get_level("DEBUG")
        )  # get_level(main_cdict["log_c_lvl"])  # set base to lowest level
        t_ch = logging.StreamHandler()
        t_fh = logging.FileHandler(
            os.path.join(main_cdict["log_dir"], "yf_logs", "train.log")
        )

        t_ch.setLevel(get_level(main_cdict["log_c_lvl"]))
        t_fh.setLevel(get_level(main_cdict["log_f_lvl"]))

        t_ch.setFormatter(c_fmt)
        t_fh.setFormatter(f_fmt)

        train_logger.addHandler(t_ch)
        train_logger.addHandler(t_fh)
        return train_logger
    elif log_type == "eval":
        eval_logger = logging.getLogger("eval_logger")
        eval_logger.propagate = False
        eval_logger.setLevel(get_level("DEBUG"))  # set base to lowest level
        e_ch = logging.StreamHandler()
        e_fh = logging.FileHandler(
            os.path.join(main_cdict["log_dir"], "yf_logs", "eval.log")
        )

        e_ch.setLevel(get_level(main_cdict["log_c_lvl"]))
        e_fh.setLevel(get_level(main_cdict["log_f_lvl"]))

        e_fh.setFormatter(f_fmt)
        e_ch.setFormatter(c_fmt)

        eval_logger.addHandler(e_ch)
        eval_logger.addHandler(e_fh)
        return eval_logger
    elif log_type == "graph":
        graph_logger = logging.getLogger("graph_logger")
        graph_logger.propagate = False
        graph_logger.setLevel(get_level("DEBUG"))  # set base to lowest level

        g_ch = logging.StreamHandler()
        g_fh = logging.FileHandler(
            os.path.join(main_cdict["log_dir"], "yf_logs", "graph.log")
        )

        g_ch.setLevel(get_level(main_cdict["log_g_lvl"]))
        g_fh.setLevel(get_level(main_cdict["log_g_lvl"]))

        g_fh.setFormatter(g_fmt)
        g_ch.setFormatter(g_fmt)

        graph_logger.addHandler(g_ch)
        graph_logger.addHandler(g_fh)
        return graph_logger
    elif log_type == "preds":
        preds_logger = logging.getLogger("preds_logger")
        preds_logger.propagate = False
        preds_logger.setLevel(get_level("DEBUG"))  # set base to lowest level
        p_ch = logging.StreamHandler()
        p_fh = logging.FileHandler(
            os.path.join(main_cdict["log_dir"], "yf_logs", "preds.log")
        )

        # by default, don't log < critical to terminal
        p_ch.setLevel(get_level("CRITICAL"))
        p_fh.setLevel(get_level(main_cdict["log_p_lvl"]))

        p_fh.setFormatter(p_fmt)
        p_ch.setFormatter(p_fmt)

        preds_logger.addHandler(p_ch)
        preds_logger.addHandler(p_fh)
        return preds_logger
    else:
        raise ValueError(f"can't get this logger type: {log_type}")
