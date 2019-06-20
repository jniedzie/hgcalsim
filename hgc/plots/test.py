# coding: utf-8


import os
import contextlib

import numpy as np
import root_numpy
import psutil
import law

import plotlib.root as r
import ROOT


proc = psutil.Process(os.getpid())


@contextlib.contextmanager
def log_mem(entry="rss"):
    base = getattr(proc.memory_info(), entry)
    try:
        yield
    finally:
        diff = getattr(proc.memory_info(), entry) - base
        print("difference of '{}' memory: {} {}".format(entry, *law.util.human_bytes(diff)))


with log_mem():
    cache_file = os.path.expandvars("$HGC_BASE/tmp/ntup.npy")
    if not os.path.exists(cache_file) or 1:
        data = root_numpy.root2array(
            "/afs/cern.ch/user/m/mrieger/gentest/.data/store/NtupTask/dev/ntup_n10.root",
            treename="ana/hgc",
        )
        np.save(cache_file, data)
    else:
        data = np.load(cache_file)


r.setup_style()
canvas, (pad,) = r.routines.create_canvas()
pad.cd()


with log_mem():
    # print branch names
    names = sorted(data.dtype.names)
    print("\n".join(names))

    # print some event stats
    for i in range(data.shape[0]):
        print(80 * "-")
        print("event {}".format(i))
        event = data[i]

        # number of particles
        n_particles = event["calopart_energy"].shape[0]
        print("calopart: {}".format(n_particles))

        # number of 2d clusters
        n_2dclusters = event["cluster2d_energy"].shape[0]
        print("2dcluster: {}".format(n_2dclusters))

        # number of multi clusters
        n_multiclusters = event["multiclus_energy"].shape[0]
        print("multiclus: {}".format(n_multiclusters))

        # number of rec hits
        n_rechits = event["rechit_z"].shape[0]
        print("rechits: {}".format(n_rechits))

        # calo particle stats
        dummy_hist = ROOT.TH2F("h_{}".format(i), ";#eta;#phi;Entries", 1, 1.3, 3.3, 1, -3.2, 3.2)
        part_graph = ROOT.TGraph(n_particles)
        rechit_graph = ROOT.TGraph(n_rechits)

        rechit_energy_hist = ROOT.TH1F("h_rechit_e_{}".format(i), ";Rec. hit energy / MeV;Entries", 40, 0., 50.)

        for j in range(n_particles):
            print("caloparticle: {}, energy: {:.3f}, eta: {:.3f}, phi: {:.3f}".format(j,
                event["calopart_energy"][j], event["calopart_eta"][j], event["calopart_phi"][j]))

            part_graph.SetPoint(j, event["calopart_eta"][j], event["calopart_phi"][j])

        for j in range(n_rechits):
            rechit_graph.SetPoint(j, event["rechit_eta"][j], event["rechit_phi"][j])
            rechit_energy_hist.Fill(1000. * event["rechit_energy"][j])

        r.setup_hist(dummy_hist, pad=pad)
        r.setup_graph(part_graph, {"MarkerSize": 2})
        r.setup_graph(rechit_graph, {"MarkerSize": 0.25, "MarkerColor": 2})

        r.setup_hist(rechit_energy_hist, pad=pad)

        dummy_hist.Draw()
        rechit_graph.Draw("P")
        part_graph.Draw("P")
        r.update_canvas(canvas)
        canvas.SaveAs(os.path.expandvars("$HGC_BASE/tmp/etaphi_{}.png".format(i)))

        rechit_energy_hist.Draw()
        r.update_canvas(canvas)
        canvas.SaveAs(os.path.expandvars("$HGC_BASE/tmp/rechit_energy_{}.png".format(i)))
