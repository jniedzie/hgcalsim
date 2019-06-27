# coding: utf-8

"""
Custom base task classes.
"""


__all__ = ["Task", "HTCondorWorkflow", "ARCWorkflow", "UploadSoftware", "UploadRepo", "UploadCMSSW"]


import os
import math
import re

import luigi
import law

law.contrib.load("arc", "cms", "git", "htcondor", "tasks", "telegram", "root", "wlcg")


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

    def wlcg_path(self, *path):
        parts = [str(p) for p in self.store_parts() + self.store_parts_opt() + path]
        return os.path.join(*parts)

    def wlcg_target(self, *args, **kwargs):
        cls = law.WLCGFileTarget if args else law.WLCGDirectoryTarget
        return cls(self.wlcg_path(*args), **kwargs)


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


class ARCWorkflow(law.ARCWorkflow):

    arc_ce_map = {
        "DESY": "grid-arcce0.desy.de",
        "KIT": ["arc-{}-kit.gridka.de".format(i) for i in range(1, 6 + 1)],
    }

    arc_ce = law.CSVParameter(default=["DESY"], significant=False, description="target computing "
        "element(s)")

    @classmethod
    def modify_param_values(cls, params):
        if params.get("workflow") == "arc":
            ces = []
            for key in params["arc_ce"]:
                ces += law.util.make_list(cls.arc_ce_map.get(key, key))
            params["arc_ce"] = ces

        return params

    def arc_workflow_requires(self):
        reqs = super(ARCWorkflow, self).arc_workflow_requires()

        reqs["repo"] = UploadRepo.req(self, replicas=10)
        reqs["software"] = UploadSoftware.req(self, replicas=10)
        reqs["cmssw"] = UploadCMSSW.req(self, replicas=10)

        return reqs

    def arc_output_directory(self):
        return law.WLCGDirectoryTarget(self.wlcg_path())

    def arc_output_uri(self):
        return self.arc_output_directory().url(cmd="listdir")

    def arc_bootstrap_file(self):
        return os.path.expandvars("$HGC_BASE/hgc/files/arc_bootstrap.sh")

    def arc_stageout_file(self):
        return os.path.expandvars("$HGC_BASE/hgc/files/arc_stageout.sh")

    def arc_job_config(self, config, job_num, branches):
        reqs = self.arc_workflow_requires()

        config.render_variables["hgc_grid_user"] = os.getenv("HGC_GRID_USER")
        config.render_variables["repo_base"] = reqs["repo"].output().dir.url()
        config.render_variables["repo_checksum"] = reqs["repo"].checksum
        config.render_variables["scram_arch"] = os.getenv("SCRAM_ARCH")
        config.render_variables["software_base_url"] = reqs["software"].output().dir.url()
        config.render_variables["cmssw_base_url"] = reqs["cmssw"].output().dir.url()
        config.render_variables["cmssw_version"] = os.getenv("CMSSW_VERSION")

        return config


class UploadSoftware(Task, law.TransferLocalFile):

    version = None

    def single_output(self):
        return self.wlcg_target("software.tgz", fs="wlcg_software_fs")

    def run(self):
        software_path = os.environ["HGC_SOFTWARE"]

        # create the local bundle
        bundle = law.LocalFileTarget(software_path + ".tgz", is_tmp=True)

        def _filter(tarinfo):
            if re.search(r"(\.pyc|\/\.git|\.tgz|__pycache__)$", tarinfo.name):
                return None
            return tarinfo

        # create the archive with a custom filter
        bundle.dump(software_path, filter=_filter)

        # log the size
        self.publish_message("bundled software archive, size is {:.2f} {}".format(
            *law.util.human_bytes(bundle.stat.st_size)
        ))

        # transfer the bundle
        self.transfer(bundle)


class UploadRepo(Task, law.BundleGitRepository, law.TransferLocalFile):

    version = None
    task_namespace = None

    exclude_files = [".data", "tmp"]

    def get_repo_path(self):
        # required by BundleGitRepository
        return os.environ["HGC_BASE"]

    def single_output(self):
        repo_base = os.path.basename(self.get_repo_path())
        return self.wlcg_target("{}.{}.tgz".format(repo_base, self.checksum), fs="wlcg_software_fs")

    def output(self):
        return law.TransferLocalFile.output(self)

    def run(self):
        # create the bundle
        bundle = law.LocalFileTarget(is_tmp="tgz")
        self.bundle(bundle)

        # log the size
        self.publish_message("bundled repository archive, size is {:.2f} {}".format(
            *law.util.human_bytes(bundle.stat.st_size)
        ))

        # transfer the bundle
        self.transfer(bundle)


class UploadCMSSW(Task, law.BundleCMSSW, law.TransferLocalFile, law.RunOnceTask):

    force_upload = luigi.BoolParameter(default=False, description="force uploading")

    version = None
    task_namespace = None

    def get_cmssw_path(self):
        # required by BundleCMSSW
        return os.environ["CMSSW_BASE"]

    def complete(self):
        if self.force_upload and not self.has_run:
            return False
        else:
            return law.TransferLocalFile.complete(self)

    def single_output(self):
        path = "{}.tgz".format(os.path.basename(self.get_cmssw_path()))
        return self.wlcg_target(path, fs="wlcg_software_fs")

    def output(self):
        return law.TransferLocalFile.output(self)

    def run(self):
        # create the bundle
        bundle = law.LocalFileTarget(is_tmp="tgz")
        self.bundle(bundle)

        # log the size
        self.publish_message("bundled CMSSW archive, size is {:.2f} {}".format(
            *law.util.human_bytes(bundle.stat.st_size)
        ))

        # transfer the bundle and mark the task as complete
        self.transfer(bundle)
        self.mark_complete()
