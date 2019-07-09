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


class ParallelProdWorkflow(Task, law.LocalWorkflow, HTCondorWorkflow):

    n_events = luigi.IntParameter(default=10, description="number of events to generate per task")
    n_tasks = luigi.IntParameter(default=1, description="number of branch tasks to create")
    gun_type = luigi.ChoiceParameter(default="closeby", choices=["flatpt", "closeby"],
        description="the type of the particle gun")
    gun_min = luigi.FloatParameter(default=1.0, description="minimum value of the gun, either in "
        "pt or E, default: 1.0")
    gun_max = luigi.FloatParameter(default=100.0, description="maximum value of the gun, either in "
        "pt or E, default: 100.0")
    particle_ids = luigi.Parameter(default="mix", description="comma-separated list of particle "
        "ids to shoot, or 'mix', default: mix")
    delta_r = luigi.FloatParameter(default=0.1, description="distance parameter, 'closeby' gun "
        "only, default: 0.1")
    n_particles = luigi.IntParameter(default=10, description="number of particles to shoot, "
        "'closeby' gun only, default: 10")
    random_shoot = luigi.BoolParameter(default=True, description="shoot a random number of "
        "particles between [1, n_particles], 'closeby' gun only")
    seed = luigi.IntParameter(default=1, description="initial random seed, will be increased by "
        "branch number, default: 1")

    previous_task = None

    def create_branch_map(self):
        return {i: i for i in range(self.n_tasks)}

    def workflow_requires(self):
        reqs = super(ParallelProdWorkflow, self).workflow_requires()
        if self.previous_task and not self.pilot:
            key, cls = self.previous_task
            reqs[key] = cls.req(self, _prefer_cli=("version",))
        return reqs

    def requires(self):
        if self.previous_task:
            _, cls = self.previous_task
            return cls.req(self, _prefer_cli=("version",))
        else:
            return None

    def store_parts(self):
        parts = super(ParallelProdWorkflow, self).store_parts()

        # build the gun string
        assert(self.gun_type in ("flatpt", "closeby"))
        gun_str = "{}_{}To{}_ids{}".format(self.gun_type, self.gun_min, self.gun_max,
            self.particle_ids.replace(",", "-"))
        if self.gun_type == "closeby":
            gun_str += "_dR{}_n{}_rnd{:d}".format(self.delta_r, self.n_particles, self.random_shoot)
        gun_str += "_s{}".format(self.seed)

        return parts + (gun_str,)


class GSDTask(ParallelProdWorkflow):

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
                gunType=self.gun_type,
                gunMin=self.gun_min,
                gunMax=self.gun_max,
                particleIds=self.particle_ids,
                deltaR=self.delta_r,
                nParticles=self.n_particles,
                randomShoot=self.random_shoot,
                seed=self.seed + self.branch,
            ))


class RecoTask(ParallelProdWorkflow):

    previous_task = ("gsd", GSDTask)

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


class NtupTask(ParallelProdWorkflow):

    previous_task = ("reco", RecoTask)

    def output(self):
        return self.local_target("ntup_{}_n{}.root".format(self.branch, self.n_events))

    def run(self):
        with self.output().localize("w") as tmp_out:
            with self.input()["reco"].localize("r") as tmp_in:
                cms_run_and_publish(self, "$HGC_BASE/hgc/files/ntup_cfg.py", dict(
                    inputFiles=[tmp_in.path],
                    outputFile=tmp_out.path,
                ))


class CreateTrainingData(ParallelProdWorkflow):

    previous_task = ("ntup", NtupTask)

    def output(self):
        return self.local_target("tuple_{}_n{}.root".format(self.branch, self.n_events))

    @law.decorator.notify
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
