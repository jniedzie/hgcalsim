# coding: utf-8
# flake8: noqa

"""
HGCAL GEN, SIM and DIGI config.
"""


import math

import FWCore.ParameterSet.Config as cms
from reco_prodtools.templates.GSD_fragment import process
from FWCore.ParameterSet.VarParsing import VarParsing


# helpers
def calculate_rho(z, eta):
    x = math.exp(-eta)
    return - z * 2 * x / (x**2 - 1)


# options
options = VarParsing("python")

# set defaults of common options
options.setDefault("outputFile", "gsd.root")
options.setDefault("maxEvents", 1)

# register custom options
options.register("seed", 1, VarParsing.multiplicity.singleton, VarParsing.varType.int,
    "random seed")

options.parseArguments()


# input / output
process.maxEvents.input = cms.untracked.int32(options.maxEvents)
process.FEVTDEBUGHLToutput.fileName = cms.untracked.string(
    "file:{}".format(options.__getattr__("outputFile", noTags=True)))
process.source.firstLuminosityBlock = cms.untracked.uint32(1)

# random seeds
process.RandomNumberGeneratorService.generator.initialSeed = cms.untracked.uint32(options.seed)
process.RandomNumberGeneratorService.VtxSmeared.initialSeed = cms.untracked.uint32(options.seed)
process.RandomNumberGeneratorService.mix.initialSeed = cms.untracked.uint32(options.seed)

# particle gun setup
# process.generator = cms.EDProducer("FlatRandomPtGunProducer",
#     PGunParameters=cms.PSet(
#         # particle ids
#         PartID=cms.vint32(211),
#         # pt range
#         MinPt=cms.double(5.0),
#         MaxPt=cms.double(100.0),
#         # phi range
#         MinPhi=cms.double(-math.pi / 6.),
#         MaxPhi=cms.double(math.pi / 6.),
#         # abs eta range
#         MinEta=cms.double(1.594),
#         MaxEta=cms.double(2.931),
#     ),
#     AddAntiParticle=cms.bool(False),
#     firstRun=cms.untracked.uint32(1),
#     Verbosity=cms.untracked.int32(1),
# )

# our custom CloseByParticleGunProducer
process.generator = cms.EDProducer("CloseByParticleGunProducer",
    PGunParameters=cms.PSet(
        # particle ids
        PartID=cms.vint32(211),
        # max number of particles to shoot at a time
        NParticles=cms.int32(10),
        # energy range
        EnMin=cms.double(5.0),
        EnMax=cms.double(100.0),
        # phi range
        MinPhi=cms.double(-math.pi / 6.),
        MaxPhi=cms.double(math.pi / 6.),
        # abs eta range, not used but must be present
        MinEta=cms.double(0.),
        MaxEta=cms.double(0.),
        # longitudinal distance in cm
        ZMin=cms.double(319.0),
        ZMax=cms.double(319.0),
        # radial distance in cm
        RhoMin=cms.double(calculate_rho(319.0, 1.594)),
        RhoMax=cms.double(calculate_rho(319.0, 2.931)),
        # direction and overlapp settings
        DeltaR=cms.double(1.0),
        Pointing=cms.bool(True),
        Overlapping=cms.bool(True),
        RandomShoot=cms.bool(False),
    ),
    AddAntiParticle=cms.bool(False),
    firstRun=cms.untracked.uint32(1),
    Verbosity=cms.untracked.int32(10),
)

# # CloseByParticleGunProducer as used in CMSSW release
# process.generator = cms.EDProducer("CloseByParticleGunProducer",
#     PGunParameters=cms.PSet(
#         # particle ids
#         PartID=cms.vint32(211),
#         # max number of particles to shoot at a time
#         NParticles=cms.int32(10),
#         # energy range
#         EnMin=cms.double(5.0),
#         EnMax=cms.double(100.0),
#         # phi range
#         MinPhi=cms.double(-math.pi / 6.),
#         MaxPhi=cms.double(math.pi / 6.),
#         # abs eta range, not used but must be present
#         MinEta=cms.double(0.),
#         MaxEta=cms.double(0.),

#         # gun position and overlap settings
#         RMin=cms.double(calculate_rho(319.0, 1.594)),
#         RMax=cms.double(calculate_rho(319.0, 2.931)),
#         ZMin=cms.double(319.0),
#         ZMax=cms.double(319.0),
#         Delta=cms.double(1.0),
#         Pointing=cms.bool(True),
#         Overlapping=cms.bool(True),
#         RandomShoot=cms.bool(False),

#     ),
#     AddAntiParticle=cms.bool(False),
#     firstRun=cms.untracked.uint32(1),
#     Verbosity=cms.untracked.int32(10),
# )
