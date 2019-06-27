# coding: utf-8

"""
Custom base task classes.
"""


__all__ = ["Task", "HTCondorWorkflow"]


import os
import math

import luigi
import law

law.contrib.load("htcondor", "tasks", "telegram", "root")


class Task(law.Task):
    """
    Custom base task.
    """

    version = luigi.Parameter(description="version of outputs to produce")
    notify = law.NotifyTelegramParameter()
    eos = luigi.BoolParameter(default=False, description="store local targets on EOS instead of in "
        "the local HGC_STORE directory, default: False")

    exclude_params_req = {"notify"}
    outputs_siblings = True
    workflow_run_decorators = [law.decorator.notify]
    message_cache_size = 20

    def store_parts(self):
        parts = (self.__class__.__name__,)
        return parts

    def store_parts_opt(self):
        parts = tuple()
        if self.version is not None:
            parts += (self.version,)
        return parts

    def local_path(self, *path):
        parts = [str(p) for p in self.store_parts() + self.store_parts_opt() + path]
        return os.path.join(os.environ["HGC_STORE_EOS" if self.eos else "HGC_STORE"], *parts)

    def local_target(self, *args, **kwargs):
        cls = law.LocalFileTarget if args else law.LocalDirectoryTarget
        return cls(self.local_path(*args), **kwargs)


class HTCondorWorkflow(law.HTCondorWorkflow):
    """
    Custom htcondor workflow with good default configs for the CERN batch system.
    """

    poll_interval = luigi.FloatParameter(default=0.5, significant=False, description="time between "
        "status polls in minutes, default: 0.5")
    max_runtime = luigi.FloatParameter(default=24.0, significant=False, description="maximum "
        "runtime in hours")
    cmst3 = luigi.BoolParameter(default=False, significant=False, description="use the CMS T3 "
        "HTCondor quota for jobs, default: False")

    def htcondor_output_directory(self):
        return law.LocalDirectoryTarget(self.local_path())

    def htcondor_bootstrap_file(self):
        return os.path.expandvars("$HGC_BASE/hgc/files/htcondor_bootstrap.sh")

    def htcondor_use_local_scheduler(self):
        return False

    def htcondor_job_config(self, config, job_num, branches):
        # render_data is rendered into all files sent with a job
        config.render_variables["hgc_base"] = os.getenv("HGC_BASE")
        # force to run on CC7, http://batchdocs.web.cern.ch/batchdocs/local/submit.html#os-choice
        config.custom_content.append(("requirements", "(OpSysAndVer =?= \"CentOS7\")"))
        # copy the entire environment
        config.custom_content.append(("getenv", "true"))
        # the CERN htcondor setup requires a "log" config, but we can safely set it to /dev/null
        # if you are interested in the logs of the batch system itself, set a meaningful value here
        config.custom_content.append(("log", "/dev/null"))
        # set the maximum runtime
        config.custom_content.append(("+MaxRuntime", int(math.floor(self.max_runtime * 3600)) - 1))
        # CMS T3 group settings
        if self.cmst3:
            config.custom_content.append(("+AccountingGroup", "group_u_CMST3.all"))

        return config
