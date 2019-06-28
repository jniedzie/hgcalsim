# coding: utf-8

"""
HGCAL simulation tasks.
"""


__all__ = ["GSDTask", "RecoTask", "NtupTask", "CreateTrainingData"]


import os
import random

import law
import luigi

from hgc.tasks.base import Task, HTCondorWorkflow
from hgc.util import cms_run_and_publish, log_runtime


class ParallelProdWorkflow(law.LocalWorkflow, HTCondorWorkflow):

    n_events = luigi.IntParameter(default=10, description="number of events to generate per task")
    n_tasks = luigi.IntParameter(default=1, description="number of branch tasks to create")
    seed = luigi.IntParameter(default=0, description="initial random seed, random itself when set "
        "to 0, will increased by branch number + 1, default: 0")

    def __init__(self, *args, **kwargs):
        super(ParallelProdWorkflow, self).__init__(*args, **kwargs)

        if self.seed <= 0:
            self.seed = random.randint(1, 1e8)

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
                seed=self.seed + self.branch + 1,
            ))


class RecoTask(Task, ParallelProdWorkflow):

    def workflow_requires(self):
        reqs = super(RecoTask, self).workflow_requires()
        if not self.pilot:
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
        if not self.pilot:
            reqs["reco"] = RecoTask.req(self, _prefer_cli=("version",))
        return reqs

    def requires(self):
        return RecoTask.req(self, _prefer_cli=("version",))

    def output(self):
        return self.local_target("ntup_{}_n{}.root".format(self.branch, self.n_events))

    def run(self):
        with self.output().localize("w") as tmp_out:
            with self.input()["reco"].localize("r") as tmp_in:
                cms_run_and_publish(self, "$HGC_BASE/hgc/files/ntup_cfg.py", dict(
                    inputFiles=[tmp_in.path],
                    outputFile=tmp_out.path,
                ))


class CreateTrainingData(Task, ParallelProdWorkflow):

    def workflow_requires(self):
        reqs = super(CreateTrainingData, self).workflow_requires()
        if not self.pilot:
            reqs["ntup"] = NtupTask.req(self, _prefer_cli=("version",))
        return reqs

    def requires(self):
        return NtupTask.req(self, _prefer_cli=("version",))

    def output(self):
        return self.local_target("tuple_{}_n{}.root".format(self.branch, self.n_events))

    def run(self):
        import numpy as np

        data = self.input().load(formatter="root_numpy", treename="ana/hgc")

        # inp = self.input()
        # inp.path = "/eos/cms/store/cmst3/group/hgcal/CMG_studies/mrieger/hgcalsim/NtupTask/dev1_testCondor/merged.root"
        # data = inp.load(formatter="root_numpy", treename="ana/hgc")

        def calculate_missing_rechit_fractions(data):
            fractions_of_missing_rechits = []

            for event in data:
                n_simclusters = event["simcluster_energy"].shape[0]

                for i in range(n_simclusters):
                    idxs_missing = event["simcluster_hits_indices"][i] == -1
                    fractions_of_missing_rechits.append(np.mean(idxs_missing))

            return np.array(fractions_of_missing_rechits)

        with log_runtime(log_prefix="conversion of {} events: ".format(data.shape[0])):
            fractions_of_missing_rechits = calculate_missing_rechit_fractions(data)

        mean = np.mean(fractions_of_missing_rechits)
        std = np.var(fractions_of_missing_rechits)**0.5
        print("{:.1f} ± {:.1f} % of rechits missing per simcluster".format(mean * 100, std * 100))

        from IPython import embed; embed()
        pass
