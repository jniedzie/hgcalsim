# coding: utf-8

"""
Helpful utilities.
"""


__all__ = ["cms_run", "parse_cms_run_event", "cms_run_and_publish"]


import os
import re

import six
import law


def cms_run(cfg_file, args, yield_output=False):
    if isinstance(args, dict):
        args = list(args.items())

    def cms_run_arg(key, value):
        return " ".join("{}={}".format(key, v) for v in law.util.make_list(value))

    cfg_file = os.path.expandvars(os.path.expanduser(cfg_file))
    args_str = " ".join(cms_run_arg(*tpl) for tpl in args)
    cmd = "cmsRun {} {}".format(cfg_file, args_str)

    fn = law.util.interruptable_popen if not yield_output else law.util.readable_popen
    return fn(cmd, shell=True, executable="/bin/bash")


def parse_cms_run_event(line):
    if not isinstance(line, str):
        return None

    match = re.match(r"^Begin\sprocessing\sthe\s(\d+)\w{2,2}\srecord\..+$", line.strip())
    if not match:
        return None

    return int(match.group(1))


def cms_run_and_publish(task, cfg_file, args):
    # run the command, parse output as it comes
    for obj in cms_run(cfg_file, args, yield_output=True):
        if isinstance(obj, six.string_types):
            print(obj)

            # try to parse the event number
            n_event = parse_cms_run_event(obj)
            if n_event:
                task.publish_progress(100. * n_event / task.n_events)
                task.publish_message("handle event {}".format(n_event))
        else:
            # obj is the popen object
            if obj.returncode != 0:
                raise Exception("cmsRun failed failed")
