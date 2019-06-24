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
    clean = luigi.BoolParameter(default=False, description="run 'scram b clean' before compiling")

    version = None

    def run(self):
        # create the compilation command
        cmd = "scram b -j {}".format(self.n_cores)

        # prepend the cleanup command when clean is set
        if self.clean:
            cmd = "scram b clean; " + cmd

        # determine the directory in which to run
        cwd = os.path.expandvars("$CMSSW_BASE/src")

        # run the command
        code = law.util.interruptable_popen(cmd, cwd=cwd, shell=True, executable="/bin/bash")[0]
        if code != 0:
            raise Exception("CMSSW compilation failed")
