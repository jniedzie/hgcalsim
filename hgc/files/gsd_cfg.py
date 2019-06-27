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
    return z * math.tan(2 * math.atan(math.exp(-eta)))


def particle_id_list(content):
    # content is expected to be a list of 2-tuples with each of them containing a pdg id of a
    # particle and a relative fraction in percent with a maximum precision of 1% (so, integers!)

    # check if all fractions are integers
    fractions = [tpl[1] for tpl in content]
    if not all(isinstance(f, int) for f in fractions):
        raise TypeError("fractions must be integers, got {}".format(fractions))

    # check if the fractions sum up to 100
    s = sum(fractions)
    if s != 100:
        raise Exception("sum of fractions expected to be 100, got {}".format(s))

    # create the final list of particle ids simply by multiplying with the corresponding fraction
    ids = sum(([i] * f for i, f in content), [])

    return ids


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
process.generator = cms.EDProducer("CloseByParticleGunProducer",
    PGunParameters=cms.PSet(
        # particle ids
        PartID=cms.vint32(particle_id_list([(211, 50), (22, 15), (11, 15), (13, 20)])),
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
        DeltaR=cms.double(0.4),
        Pointing=cms.bool(True),
        Overlapping=cms.bool(True),
        RandomShoot=cms.bool(True),
    ),
    AddAntiParticle=cms.bool(False),
    firstRun=cms.untracked.uint32(1),
    Verbosity=cms.untracked.int32(10),
)
