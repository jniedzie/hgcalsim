# coding: utf-8

"""
HGCAL simulation tasks.
"""


__all__ = ["GSDTask", "RecoTask", "NtupTask"]


import os

import law
import luigi

from hgc.tasks.base import Task, HTCondorWorkflow
from hgc.util import cms_run_and_publish


class ParallelProdWorkflow(law.LocalWorkflow, HTCondorWorkflow):

    n_events = luigi.IntParameter(default=10, description="number of events to generate per task")
    n_tasks = luigi.IntParameter(default=1, description="number of branch tasks to create")

    def create_branch_map(self):
        return {i: i for i in range(self.n_tasks)}


class GSDTask(Task, ParallelProdWorkflow):

    def output(self):
        return self.local_target("gsd_{}_n{}.root".format(self.branch, self.n_events))

    def run(self):
        # localize the output file
        # (i.e. create a temporary local representation and move it to the destination on success)
        with self.output().localize("w") as tmp_out:
            # run the command using a helper that publishes the current progress to the scheduler
            cms_run_and_publish(self, "$HGC_BASE/hgc/files/gsd_cfg.py", dict(
                outputFile=tmp_out.path,
                maxEvents=self.n_events,
                seed=self.branch + 1,
            ))


class RecoTask(Task, ParallelProdWorkflow):

    def workflow_requires(self):
        reqs = super(RecoTask, self).workflow_requires()
        if not self.cancel_jobs and not self.cleanup_jobs and not self.pilot:
            reqs["gsd"] = GSDTask.req(self)
        return reqs

    def requires(self):
        return GSDTask.req(self)

    def output(self):
        return {
            "reco": self.local_target("reco_{}_n{}.root".format(self.branch, self.n_events)),
            "dqm": self.local_target("dqm_{}_n{}.root".format(self.branch, self.n_events)),
        }

    def run(self):
        outp = self.output()
        with outp["reco"].localize("w") as tmp_reco, outp["dqm"].localize("w") as tmp_dqm:
            with self.input().localize("r") as tmp_in:
                cms_run_and_publish(self, "$HGC_BASE/hgc/files/reco_cfg.py", dict(
                    inputFiles=[tmp_in.path],
                    outputFile=tmp_reco.path,
                    outputFileDQM=tmp_dqm.path,
                ))


class NtupTask(Task, ParallelProdWorkflow):

    def workflow_requires(self):
        reqs = super(NtupTask, self).workflow_requires()
        if not self.cancel_jobs and not self.cleanup_jobs and not self.pilot:
            reqs["reco"] = RecoTask.req(self)
        return reqs

    def requires(self):
        return RecoTask.req(self)

    def output(self):
        return self.local_target("ntup_{}_n{}.root".format(self.branch, self.n_events))

    def run(self):
        with self.output().localize("w") as tmp_out:
            with self.input()["reco"].localize("r") as tmp_in:
                cms_run_and_publish(self, "$HGC_BASE/hgc/files/ntup_cfg.py", dict(
                    inputFiles=[tmp_in.path],
                    outputFile=tmp_out.path,
                ))


class PlotTask(Task):

    n_events = ParallelProdWorkflow.n_events

    def requires(self):
        return NtupTask.req(self, n_tasks=1)

    def output(self):
        return law.SiblingFileCollection([
            self.local_target("eta_phi_{}.png".format(i))
            for i in range(self.n_events)
        ])

    def run(self):
        from hgc.plots.plots import caloparticle_rechit_eta_phi_plot

        # ensure that the output directory exists
        output = self.output()
        output.dir.touch()

        # load the data to a structured numpy array
        input_target = self.input()["collection"][0]
        data = input_target.load(formatter="root_numpy", treename="ana/hgc")

        for i, event in enumerate(data):
            with output[i].localize("w") as tmp_out:
                caloparticle_rechit_eta_phi_plot(event, tmp_out.path)

            break
