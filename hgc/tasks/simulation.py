# coding: utf-8

"""
HGCAL simulation tasks.
"""


__all__ = ["GSDTask", "RecoTask", "NtupTask", "ConverterTask", "MergeConvertedFiles"]


import os
import random

import law
import luigi

from hgc.tasks.base import Task, HTCondorWorkflow
from hgc.tasks.software import CompileConverter, CompileDeepJetCore
from hgc.util import cms_run_and_publish, log_runtime, hadd_task


class GeneratorParameters(Task):

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

    def store_parts(self):
        parts = super(GeneratorParameters, self).store_parts()

        # build the gun string
        assert(self.gun_type in ("flatpt", "closeby"))
        gun_str = "{}_{}To{}_ids{}".format(self.gun_type, self.gun_min, self.gun_max,
            self.particle_ids.replace(",", "-"))
        if self.gun_type == "closeby":
            gun_str += "_dR{}_n{}_rnd{:d}".format(self.delta_r, self.n_particles, self.random_shoot)
        gun_str += "_s{}".format(self.seed)

        return parts + (gun_str,)


class ParallelProdWorkflow(GeneratorParameters, law.LocalWorkflow, HTCondorWorkflow):

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

    default_eos_store = "$HGC_STORE_EOS_GERRIT"

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


class MergeConvertedFiles(GeneratorParameters, law.CascadeMerge):

    n_merged_files = luigi.IntParameter(description="number of files after merging")

    merge_factor = 10

    default_eos_store = "$HGC_STORE_EOS_GERRIT"

    def cascade_workflow_requires(self):
        return ConverterTask.req(self, _prefer_cli=["workflow"])

    def trace_cascade_workflow_inputs(self, inputs):
        return self.n_tasks

    def cascade_requires(self, start_leaf, end_leaf):
        return [ConverterTask.req(self, branch=b) for b in range(start_leaf, end_leaf)]

    def cascade_output(self):
        return law.SiblingFileCollection(
            self.local_target("tuple_{}Of{}_n{}.root".format(
                i + 1, self.n_merged_files, self.n_events))
            for i in range(self.n_merged_files)
        )

    def merge(self, *args, **kwargs):
        return hadd_task(self, *args, **kwargs)


class CreateMLDataset(GeneratorParameters, law.LocalWorkflow, HTCondorWorkflow):

    n_merged_files = MergeConvertedFiles.n_merged_files

    def create_branch_map(self):
        return {i: i for i in range(self.n_merged_files)}

    def workflow_requires(self):
        reqs = super(CreateMLDataset, self).workflow_requires()
        if not self.pilot:
            reqs["merged"] = MergeConvertedFiles.req(self, cascade_tree=-1,
                _prefer_cli=("version", "workflow"))
        else:
            reqs["conv"] = ConverterTask.req(self, _prefer_cli=("version", "workflow"))
        reqs["deepjetcore"] = CompileDeepJetCore.req(self)
        return reqs

    def requires(self):
        return {
            "merged": MergeConvertedFiles.req(self, cascade_tree=self.branch, workflow="local",
                _prefer_cli=("version")),
            "deepjetcore": CompileDeepJetCore.req(self),
        }

    def output(self):
        postfix = lambda tmpl: tmpl.format("{}_n{}".format(self.branch, self.n_events))
        return law.SiblingFileCollection({
            "x": self.local_target(postfix("x_{}.dat")),
            "y": self.local_target(postfix("y_{}.dat")),
            "meta": self.local_target(postfix("meta_{}.meta")),
            "dc": self.local_target(postfix("dc_{}.dc")),
            "snapshot": self.local_target(postfix("snapshot_{}.dc")),
        })

    @law.decorator.notify
    def run(self):
        with self.input()["merged"].localize("r") as inp:
            # write the path of the input file to a temporary file
            samples_file = law.LocalFileTarget(is_tmp=True)
            samples_file.touch(content="{}\n".format(inp.path))

            # tmp dir for output files
            tmp_dir = law.LocalDirectoryTarget(is_tmp=True)

            # create the conversion command
            compile_task = self.requires()["deepjetcore"]
            cmd = """
                {} &&
                export HGCALML="$HGC_BASE/modules/HGCalML"
                export DEEPJETCORE_SUBPACKAGE="$HGCALML"
                export PYTHONPATH="$HGCALML/modules:$PYTHONPATH"
                export PYTHONPATH="$HGCALML/modules/datastructures:$PYTHONPATH"
                convertFromRoot.py -n 0 --noRelativePaths -c TrainData_hitlist -o "{}" -i "{}"
            """.format(compile_task.get_setup_cmd(), tmp_dir.path, samples_file.path)

            # run the command
            code = law.util.interruptable_popen(cmd, env=compile_task.get_setup_env(), shell=True,
                executable="/bin/bash")[0]
            if code != 0:
                raise Exception("convertFromRoot.py failed")

        with self.output().localize("w") as outp:
            basename = os.path.splitext(inp.basename)[0]
            outp["x"].path = tmp_dir.child(basename + ".x.0").path
            outp["y"].path = tmp_dir.child(basename + ".y.0").path
            outp["meta"].path = tmp_dir.child(basename + ".meta").path
            outp["dc"].path = tmp_dir.child("dataCollection.dc").path
            outp["snapshot"].path = tmp_dir.child("snapshot.dc").path


class TestTask(Task):

    version = None

    def output(self):
        return self.local_target("hist.png")

    @law.decorator.notify
    def run(self):
        import numpy as np

        # data = self.input().load(formatter="root_numpy", treename="ana/hgc")

        # inp = law.LocalFileTarget("/eos/user/m/mrieger/data/hgc/mergedntup2.root")
        # with log_runtime():
        #     data = inp.load(formatter="root_numpy", treename="ana/hgc",
        #         branches=["simcluster_hits_indices", "rechit_energy"])

        def calculate_missing_rechit_fractions(data):
            fractions_of_missing_rechits = []

            for event in data:
                n_simclusters = event["simcluster_energy"].shape[0]

                for i in range(n_simclusters):
                    idxs_missing = event["simcluster_hits_indices"][i] == -1
                    fractions_of_missing_rechits.append(np.mean(idxs_missing))

            return np.array(fractions_of_missing_rechits)

        # with log_runtime(log_prefix="conversion of {} events: ".format(data.shape[0])):
        #     fractions_of_missing_rechits = calculate_missing_rechit_fractions(data)
        # mean = np.mean(fractions_of_missing_rechits)
        # std = np.var(fractions_of_missing_rechits)**0.5
        # print("{:.1f} ± {:.1f} % of rechits missing per simcluster".format(mean * 100, std * 100))

        def calculate_hit_stats(data):
            flen = lambda l: float(len(l))
            stats = []
            for event in data:
                rec_det_ids = set(event["rechit_detid"])

                sim_det_ids = set()
                matched_sim_det_ids = set()
                for idxs, ids in zip(event["simcluster_hits_indices"], event["simcluster_hits"]):
                    sim_det_ids |= set(ids)
                    matched_sim_det_ids |= set(ids[idxs != -1])

                    # assert(set(event["rechit_detid"][idxs[idxs != -1]]) == set(ids[idxs != -1]))

                # assert(len(matched_sim_det_ids - rec_det_ids) == 0)

                stats.append([
                    # number of reconstructed hits
                    flen(rec_det_ids),
                    # number of hits, connected to at least one sim cluster
                    flen(sim_det_ids),
                    # number of reconstructed hits, connected to at least one sim cluster
                    flen(matched_sim_det_ids),
                ])

            return np.array(stats)

        cache_path = "/tmp/mrieger/testtaskcache.npy"
        if os.path.exists(cache_path):
            stats = np.load(cache_path)
        else:
            inp = law.LocalFileTarget("/eos/user/m/mrieger/data/hgc/mergedntup2.root")
            with log_runtime():
                data = inp.load(formatter="root_numpy", treename="ana/hgc",
                    branches=["simcluster_hits", "simcluster_hits_indices", "rechit_detid"])
            stats = calculate_hit_stats(data)
            np.save(cache_path, stats)

        import plotlib.root as r
        import ROOT

        r.setup_style()
        canvas, (pad,) = r.routines.create_canvas()
        pad.cd()

        binning = (1, 36., 46., 1, 36., 46.)
        title = ";N RecHits / 10^{3};N RecHits - N SimHits / 10^{3};Entries"
        dummy_hist = ROOT.TH2F("h", title, *binning)
        graph = ROOT.TGraph(stats.shape[0])

        noise_hits = stats[:, 0] - stats[:, 2]
        for j in range(stats.shape[0]):
            graph.SetPoint(j, stats[j][0] * 0.001, noise_hits[j] * 0.001)

        r.setup_hist(dummy_hist, pad=pad)
        r.setup_graph(graph, {"MarkerSize": 0.25, "MarkerColor": 2})

        dummy_hist.Draw()
        graph.Draw("P")

        # cms label
        cms_labels = r.routines.create_cms_labels(postfix="Simulation")
        cms_labels[0].Draw()
        cms_labels[1].Draw()

        # phase 2 label
        phase2_label = r.routines.create_top_right_label("HGCal, Phase II (D41)")
        phase2_label.Draw()

        r.update_canvas(canvas)
        with self.output().localize() as outp:
            canvas.SaveAs(outp.path)
