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

# Output definition
# process.FEVTDEBUGHLToutput.fileName = cms.untracked.string('file:partGun_PDGid211_x96_Pt1.0To35.0_RECO_1.root')
# process.DQMoutput.fileName = cms.untracked.string('file:partGun_PDGid211_x96_Pt1.0To35.0_DQM_1.root')

# Customisation from command line
# process.hgcalLayerClusters.minClusters = cms.uint32(3)
# those below are all now the default values - just there to illustrate what can be customised
#process.hgcalLayerClusters.dependSensor = cms.bool(True)
#process.hgcalLayerClusters.ecut = cms.double(3.) #multiple of sigma noise if dependSensor is true
#process.hgcalLayerClusters.kappa = cms.double(9.) #multiple of sigma noise if dependSensor is true
#process.hgcalLayerClusters.multiclusterRadii = cms.vdouble(2.,2.,2.) #(EE,FH,BH), in com
#process.hgcalLayerClusters.deltac = cms.vdouble(2.,2.,2.) #(EE,FH,BH), in cm
