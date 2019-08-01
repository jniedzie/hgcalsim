# coding: utf-8

"""
Plotting tasks.
"""

__all__ = ["PlotTask"]


import law
import luigi

from hgc.tasks.base import Task
from hgc.tasks.simulation import NtupTask


luigi.namespace("plot", scope=__name__)


class PlotTask(Task):

    n_events = NtupTask.n_events

    def requires(self):
        return NtupTask.req(self, n_tasks=1)

    def output(self):
        return law.SiblingFileCollection([
            self.local_target("eta_phi_{}.png".format(i))
            for i in range(self.n_events)
        ])

    @law.decorator.notify
    def run(self):
        from hgc.plots.plots import particle_rechit_eta_phi_plot

        # ensure that the output directory exists
        output = self.output()
        output.dir.touch()

        # load the data to a structured numpy array
        input_target = self.input()["collection"][0]
        data = input_target.load(formatter="root_numpy", treename="ana/hgc")

        for i, event in enumerate(data):
            with output[i].localize("w") as tmp_out:
                particle_rechit_eta_phi_plot(event, "gunparticle", tmp_out.path)
