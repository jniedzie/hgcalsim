#!/usr/bin/env bash

load_replica() {
    local remote_base="$1"
    local bundle_re="$2"
    local arc_path="$3"

    local arc="$( gfal-ls "$remote_base" | grep -Po "$bundle_re" | shuf -n 1 )"
    if [ -z "$arc" ]; then
        >&2 echo "could not determine archive to load from $remote_base"
        return "1"
    fi

    gfal-copy "$remote_base/$arc" "$arc_path"
    if [ "$?" != "0" ]; then
        >&2 echo "could not load archive $arc from $remote_base"
        return "1"
    fi
}

action() {
    #
    # set env variables
    #

    export PATH_ORIG="$PATH"
    export PYTHONPATH_ORIG="$PYTHONPATH"
    export LD_LIBRARY_PATH_ORIG="$LD_LIBRARY_PATH"

    export HGC_DATA="$HOME/hgc_data"
    export HGC_SOFTWARE="$HGC_DATA/software"
    export HGC_STORE="$HGC_DATA/store"
    export HGC_LOCAL_CACHE="$HGC_DATA/cache"
    export HGC_GRID_USER="{{hgc_grid_user}}"

    export SCRAM_ARCH="{{scram_arch}}"
    export CMSSW_VERSION="{{cmssw_version}}"
    export CMSSW_BASE="$HGC_DATA/cmssw/$CMSSW_VERSION"

    export HGC_ON_GRID="1"

    mkdir -p "$HGC_DATA"


    #
    # setup CMSSW
    #

    source "/cvmfs/cms.cern.ch/cmsset_default.sh"
    mkdir -p "$( dirname "$CMSSW_BASE" )"
    cd "$( dirname "$CMSSW_BASE" )"
    scramv1 project CMSSW "$CMSSW_VERSION"
    cd "$CMSSW_VERSION"
    load_replica "{{cmssw_base_url}}" "$CMSSW_VERSION\.\d+\.tgz" "cmssw.tgz"
    tar -xzf "cmssw.tgz"
    rm "cmssw.tgz"
    cd src
    eval `scramv1 runtime -sh`
    scram build
    cd "$HOME"


    #
    # load the software bundle
    #

    mkdir -p "$HGC_SOFTWARE"
    cd "$HGC_SOFTWARE"
    load_replica "{{software_base_url}}" "software\.\d+\.tgz" "software.tgz"
    tar -xzf "software.tgz"
    rm "software.tgz"
    cd "$HOME"


    #
    # load the repo bundle
    #

    load_replica "{{repo_base}}" "hgcalsim\.{{repo_checksum}}\.\d+\.tgz" "repo.tgz"
    tar -xzf "repo.tgz"
    rm "repo.tgz"

    # source the repo setup
    source "hgcalsim/setup.sh"
}
action "$@"
