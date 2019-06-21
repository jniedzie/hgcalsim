# coding: utf-8

"""
Tasks related to software compilation.
"""


__all__ = ["CompileCMSSW"]


import os

import law
import luigi

from hgc.tasks.base import Task


class CompileCMSSW(Task, law.RunOnceTask):

    n_cores = luigi.IntParameter(default=1, significant=False, description="the number of cores to "
        "use for compiling cmssw")

    version = None

    def run(self):
        # create the compilation command
        cmd = "scram b -j {}".format(self.n_cores)

        # determine the directory in which to run
        cwd = os.path.expandvars("$CMSSW_BASE/src")

        # run the command
        code = law.util.interruptable_popen(cmd, cwd=cwd, shell=True, executable="/bin/bash")[0]
        if code != 0:
            raise Exception("CMSSW compilation failed")
