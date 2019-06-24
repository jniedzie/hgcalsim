# coding: utf-8

"""
Collection of plot functions.
"""

__all__ = ["caloparticle_rechit_eta_phi_plot"]


import plotlib.root as r
import ROOT


def caloparticle_rechit_eta_phi_plot(event, plot_path):
    r.setup_style()
    canvas, (pad,) = r.routines.create_canvas()
    pad.cd()

    n_caloparticles = event["calopart_energy"].shape[0]
    n_rechits = event["rechit_z"].shape[0]

    binning = (1, -6.00, 6.00, 1, -3.2, 3.2)
    dummy_hist = ROOT.TH2F("h", ";#eta;#phi;Entries", *binning)
    caloparticle0_graph = ROOT.TGraph(1)
    caloparticle_graph = ROOT.TGraph(n_caloparticles)
    rechit_graph = ROOT.TGraph(n_rechits)

    for j in range(n_caloparticles):
        eta, phi = event["calopart_eta"][j], event["calopart_phi"][j]
        if j == 0:
            caloparticle0_graph.SetPoint(j, eta, phi)
        caloparticle_graph.SetPoint(j, eta, phi)

    for j in range(n_rechits):
        eta, phi = event["rechit_eta"][j], event["rechit_phi"][j]
        rechit_graph.SetPoint(j, eta, phi)

    r.setup_hist(dummy_hist, pad=pad)
    r.setup_graph(caloparticle0_graph, {"MarkerSize": 1.5, "MarkerColor": 3})
    r.setup_graph(caloparticle_graph, {"MarkerSize": 1.5})
    r.setup_graph(rechit_graph, {"MarkerSize": 0.25, "MarkerColor": 2})

    dummy_hist.Draw()
    rechit_graph.Draw("P")
    caloparticle_graph.Draw("P")
    caloparticle0_graph.Draw("P")

    r.update_canvas(canvas)
    canvas.SaveAs(plot_path)
