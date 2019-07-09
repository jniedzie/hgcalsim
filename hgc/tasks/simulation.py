# coding: utf-8

"""
HGCAL simulation tasks.
"""


__all__ = ["GSDTask", "RecoTask", "NtupTask", "ConverterTask"]


import os
import random

import law
import luigi

from hgc.tasks.base import Task, HTCondorWorkflow
from hgc.tasks.software import CompileConverter
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
        reqs = {}
        if self.previous_task:
            key, cls = self.previous_task
            reqs[key] = cls.req(self, _prefer_cli=("version",))
        return reqs

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
        with self.output().localize("w") as outp:
            # run the command using a helper that publishes the current progress to the scheduler
            cms_run_and_publish(self, "$HGC_BASE/hgc/files/gsd_cfg.py", dict(
                outputFile=outp.path,
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
        with self.localize_output("w") as outp:
            with self.localize_input("r") as inp:
                cms_run_and_publish(self, "$HGC_BASE/hgc/files/reco_cfg.py", dict(
                    inputFiles=[inp["gsd"].path],
                    outputFile=outp["reco"].path,
                    outputFileDQM=outp["dqm"].path,
                ))


class NtupTask(ParallelProdWorkflow):

    previous_task = ("reco", RecoTask)

    def output(self):
        return self.local_target("ntup_{}_n{}.root".format(self.branch, self.n_events))

    def run(self):
        with self.localize_output("w") as outp:
            with self.localize_input("r") as inp:
                cms_run_and_publish(self, "$HGC_BASE/hgc/files/ntup_cfg.py", dict(
                    inputFiles=[inp["reco"]["reco"].path],
                    outputFile=outp.path,
                ))


class ConverterTask(ParallelProdWorkflow):

    previous_task = ("ntup", NtupTask)

    def workflow_requires(self):
        reqs = super(ConverterTask, self).workflow_requires()
        reqs["converter"] = CompileConverter.req(self)
        return reqs

    def requires(self):
        reqs = super(ConverterTask, self).requires()
        reqs["converter"] = CompileConverter.req(self)
        return reqs

    def output(self):
        return self.local_target("tuple_{}_n{}.root".format(self.branch, self.n_events))

    @law.decorator.notify
    def run(self):
        # determine the converter executable
        inp = self.input()
        converter = inp["converter"].path
        converter_dir = inp["converter"].parent

        # read the config template
        with converter_dir.child("config/config_template.txt").open("r") as f:
            template = f.read()

        # temporary output directory
        output_dir = law.LocalDirectoryTarget(is_tmp=True)
        output_dir.touch()

        # fill template variables
        with inp["ntup"].localize("r") as ntup_file:
            config = template.format(
                input_dir=ntup_file.parent.path,
                input_file=ntup_file.basename,
                output_dir=output_dir.path,
                hist_output_file="no_used.root",
                skim_output_prefix="output_file_",
            )

            # create a config file required by the converter
            config_file = law.LocalFileTarget(is_tmp=True)
            with config_file.open("w") as f:
                f.write(config)

            # run the converter
            env_script = converter_dir.child("env.sh").path
            cmd = "source {} '' && {} {}".format(env_script, converter, config_file.path)
            code = law.util.interruptable_popen(cmd, shell=True, executable="/bin/bash")[0]
            if code != 0:
                raise Exception("conversion failed")

        # determine the skim output file and
        output_basename = output_dir.glob("output_file_*")[0]
        self.output().copy_from_local(output_dir.child(output_basename))
