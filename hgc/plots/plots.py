# coding: utf-8

"""
Collection of plot functions.
"""

__all__ = ["particle_rechit_eta_phi_plot"]


import plotlib.root as r
import ROOT


def particle_rechit_eta_phi_plot(event, particle_name, plot_path):
    r.setup_style()
    canvas, (pad,) = r.routines.create_canvas()
    pad.cd()

    n_particles = event[particle_name + "_energy"].shape[0]
    n_rechits = event["rechit_z"].shape[0]

    binning = (1, -6.00, 6.00, 1, -3.2, 3.2)
    dummy_hist = ROOT.TH2F("h", ";#eta;#phi;Entries", *binning)
    particle0_graph = ROOT.TGraph(1)
    particle_graph = ROOT.TGraph(n_particles)
    rechit_graph = ROOT.TGraph(n_rechits)

    for j in range(n_particles):
        eta, phi = event[particle_name + "_eta"][j], event[particle_name + "_phi"][j]
        if j == 0:
            particle0_graph.SetPoint(j, eta, phi)
        particle_graph.SetPoint(j, eta, phi)

    for j in range(n_rechits):
        eta, phi = event["rechit_eta"][j], event["rechit_phi"][j]
        rechit_graph.SetPoint(j, eta, phi)

    r.setup_hist(dummy_hist, pad=pad)
    r.setup_graph(particle0_graph, {"MarkerSize": 1.5, "MarkerColor": 3})
    r.setup_graph(particle_graph, {"MarkerSize": 1.5})
    r.setup_graph(rechit_graph, {"MarkerSize": 0.25, "MarkerColor": 2})

    dummy_hist.Draw()
    rechit_graph.Draw("P")
    particle_graph.Draw("P")
    particle0_graph.Draw("P")

    r.update_canvas(canvas)
    canvas.SaveAs(plot_path)
