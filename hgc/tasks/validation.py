# coding: utf-8

"""
HGCAL simulation tasks.
"""


__all__ = ["GSDTask", "RecoTask", "HarvestingTask", "ValidationPlotsTask"]


import os
import random

import law
import luigi

from hgc.tasks.base import Task
from hgc.util import cms_run_and_publish, log_runtime


luigi.namespace("vali", scope=__name__)


class SimTask(Task):
  
    version = None
    
    distance = luigi.FloatParameter(default=7.5, description="")
    thickness = luigi.IntParameter(default=200, description="")

    def store_parts(self):
        parts = super(SimTask, self).store_parts()
        parts += (self.thickness, '%g'%self.distance)
        return parts


class GSDTask(SimTask, law.ExternalTask):

    def store_parts(self):
        return (self.thickness, '%g'%self.distance)
    
    def output(self):
        return self.local_target("step2.root", store="/data/hgcal-0/store/layerClusteringTuning")


class RecoTask(SimTask):

    n_threads = luigi.IntParameter(default=1, description="", significant=False)
    n_events = luigi.IntParameter(default=5, description="")
  
    def requires(self):
        return GSDTask.req(self)
  
    def output(self):
        return {
            "reco": self.local_target("reco_{}.root".format(self.n_events)),
            "dqm": self.local_target("dqm_{}.root".format(self.n_events)),
        }

    @law.decorator.localize
    def run(self):
        inp = self.input()
        outp = self.output()

        cms_run_and_publish(self, "$HGC_BASE/hgc/files/reco_for_validation_cfg.py", dict(
            inputFiles=[inp.path],
            outputFile=outp["reco"].path,
            outputFileDQM=outp["dqm"].path,
            nThreads=self.n_threads,
            maxEvents=self.n_events,
        ))

class HarvestingTask(SimTask):

    n_threads = luigi.IntParameter(default=1, description="", significant=False)
    n_events = luigi.IntParameter(default=5, description="")

    def requires(self):
      return RecoTask.req(self)

    def output(self):
      return { "harvesting" : self.local_target("DQM_V0001_R000000001__Global__CMSSW_X_Y_Z__RECO.root") }

    @law.decorator.safe_output
    def run(self):
      inp = self.input()
      outp = self.output()
      outp["harvesting"].parent.touch()

      cms_run_and_publish(self, "$HGC_BASE/hgc/files/harvesting_cfg.py", dict(
            inputFiles=inp["dqm"].path,
            outputDir=outp["harvesting"].parent.path,
            nThreads=self.n_threads,
            maxEvents=self.n_events,
      ))

class ValidationPlotsTask(SimTask):
  
    n_threads = luigi.IntParameter(default=1, description="", significant=False)
    n_events = luigi.IntParameter(default=5, description="")
  
    def requires(self):
      return HarvestingTask.req(self)
    
    def output(self):
      return { "validation" : self.local_target("plots/") }
    
    @law.decorator.safe_output
    def run(self):
      inp = self.input()
      outp = self.output()
      outp["validation"].parent.touch()
      
      cmd = "$HGC_BASE/hgc/files/validation_plots.py {} \
      --outputDir {} --no-ratio --png \
      --separate --verbose --collection hgcalLayerClusters".format(inp["harvesting"].path, outp["validation"].parent.path)
      
      os.system(cmd)


class MultiRecoTask(Task, law.WrapperTask):
      version = None


      def requires(self):
          thicknesses=[120, 200, 300]
          distances=[2.5, 5, 7.5, 15]

          reqs=[]

          for t in thicknesses:
              for d in distances:
                  reqs.append(RecoTask.req(self, thickness=t, distance=d))

          return reqs

class MultiHarvestingTask(Task, law.WrapperTask):
  version = None
    
    
  def requires(self):
    thicknesses=[120, 200, 300]
    distances=[2.5, 5, 7.5, 15]
      
    reqs=[]
        
    for t in thicknesses:
      for d in distances:
        reqs.append(HarvestingTask.req(self, thickness=t, distance=d))
          
    return reqs

class MultiValidationPlotsTask(Task, law.WrapperTask):
  version = None

  def requires(self):
    thicknesses=[120, 200, 300]
    distances=[2.5, 5, 7.5, 15]
    
    reqs=[]
    
    for t in thicknesses:
      for d in distances:
        reqs.append(ValidationPlotsTask.req(self, thickness=t, distance=d))
  
    return reqs
