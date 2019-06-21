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
    caloparticle_graph = ROOT.TGraph(n_caloparticles)
    rechit_graph = ROOT.TGraph(n_rechits)

    for j in range(n_caloparticles):
        print j
        caloparticle_graph.SetPoint(j, event["calopart_eta"][j], event["calopart_phi"][j])

    for j in range(n_rechits):
        rechit_graph.SetPoint(j, event["rechit_eta"][j], event["rechit_phi"][j])

    r.setup_hist(dummy_hist, pad=pad)
    r.setup_graph(caloparticle_graph, {"MarkerSize": 2})
    r.setup_graph(rechit_graph, {"MarkerSize": 0.25, "MarkerColor": 2})

    dummy_hist.Draw()
    rechit_graph.Draw("P")
    caloparticle_graph.Draw("P")

    r.update_canvas(canvas)
    canvas.SaveAs(plot_path)
