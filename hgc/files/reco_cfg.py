# coding: utf-8
# flake8: noqa

"""
HGCAL RECO config.
"""


import FWCore.ParameterSet.Config as cms
from reco_prodtools.templates.RECO_fragment import process
from FWCore.ParameterSet.VarParsing import VarParsing


# options
options = VarParsing("python")

# set defaults of common options
options.setDefault("outputFile", "reco.root")
options.setDefault("maxEvents", -1)

# register custom options
options.register("outputFileDQM", "dqm.root", VarParsing.multiplicity.singleton,
    VarParsing.varType.string, "path to the DQM output file")

options.parseArguments()


# input / output
process.maxEvents.input = cms.untracked.int32(-1)
process.source.fileNames = cms.untracked.vstring(
    *["file:{}".format(f) for f in options.inputFiles])
process.FEVTDEBUGHLToutput.fileName = cms.untracked.string(
    "file:{}".format(options.__getattr__("outputFile", noTags=True)))
process.DQMoutput.fileName = cms.untracked.string(
    "file:{}".format(options.outputFileDQM))
