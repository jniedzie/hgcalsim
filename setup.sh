#!/usr/bin/env bash

action() {
    local origin="$( pwd )"


    #
    # global variables
    #

    # determine the directory of this file
    if [ ! -z "$ZSH_VERSION" ]; then
        local this_file="${(%):-%x}"
    else
        local this_file="${BASH_SOURCE[0]}"
    fi
    export HGC_BASE="$( cd "$( dirname "$this_file" )" && pwd )"

    # check if we're on lxplus
    if [[ "$( hostname )" = lxplus*.cern.ch ]]; then
        export HGC_ON_LXPLUS="1"
    else
        export HGC_ON_LXPLUS="0"
    fi

    # default grid user
    if [ -z "$HGC_GRID_USER" ]; then
        if [ "$HGC_ON_LXPLUS" = "1" ]; then
            export HGC_GRID_USER="$( whoami )"
            echo "NOTE: lxplus detected, setting HGC_GRID_USER to $HGC_GRID_USER"
        else
            2>&1 echo "please set HGC_GRID_USER to your grid user name and try again"
            return "1"
        fi
    fi
    export HGC_GRID_USER_FIRST_CHAR="${HGC_GRID_USER:0:1}"

    # other defaults
    [ -z "$HGC_DATA" ] && export HGC_DATA="$HGC_BASE/.data"
    [ -z "$HGC_SOFTWARE" ] && export HGC_SOFTWARE="$HGC_DATA/software/$( whoami )"
    [ -z "$HGC_STORE" ] && export HGC_STORE="$HGC_DATA/store"
    [ -z "$HGC_STORE_EOS_USER" ] && export HGC_STORE_EOS_USER="/eos/cms/store/cmst3/group/hgcal/CMG_studies/$HGC_GRID_USER/hgcalsim"
    [ -z "$HGC_STORE_EOS" ] && export HGC_STORE_EOS="$HGC_STORE_EOS_USER"
    [ -z "$HGC_CONDA_DIR" ] && export HGC_CONDA_DIR="/afs/cern.ch/work/j/jkiesele/public/conda_env/miniconda3"

    # store the location of the default gfal2 python bindings
    local gfal2_bindings_file="$( python -c "import gfal2; print(gfal2.__file__)" )"


    #
    # helper functions
    #

    hgc_install_pip() {
        pip install --ignore-installed --no-cache-dir --prefix "$HGC_SOFTWARE" "$@"
    }
    export -f hgc_install_pip

    hgc_add_py() {
        [ ! -z "$1" ] && export PYTHONPATH="$1:$PYTHONPATH"
    }
    export -f hgc_add_py

    hgc_add_bin() {
        [ ! -z "$1" ] && export PATH="$1:$PATH"
    }
    export -f hgc_add_bin

    hgc_cmssw_base() {
        if [ -z "$CMSSW_VERSION" ]; then
            2>&1 echo "CMSSW_VERSION must be set for hgc_cmssw_path"
            return "1"
        fi
        echo "$HGC_DATA/cmssw/$( whoami )/$CMSSW_VERSION"
    }
    export -f hgc_cmssw_base


    #
    # CMSSW setup
    # (hardcoded for the moment)
    #

    export SCRAM_ARCH="slc7_amd64_gcc700"
    export CMSSW_VERSION="CMSSW_11_0_0_pre3"
    export CMSSW_BASE="$( hgc_cmssw_base )"

    if [ ! -d "$CMSSW_BASE" ]; then
        echo "setting up $CMSSW_VERSION with $SCRAM_ARCH in $CMSSW_BASE"

        source "/cvmfs/cms.cern.ch/cmsset_default.sh" ""
        mkdir -p "$( dirname "$CMSSW_BASE" )"
        cd "$( dirname "$CMSSW_BASE" )"
        scramv1 project CMSSW "$CMSSW_VERSION" || return "$?"
        cd "$CMSSW_VERSION/src"
        eval `scramv1 runtime -sh` || return "$?"
        scram b || return "$?"

        # custom packages
        git cms-init
        git cms-addpkg IOMC/ParticleGuns
        git cms-merge-topic riga:add_CloseByFlatDeltaRGunProducer_11_0_0_pre3
        git clone https://github.com/CMS-HGCAL/reco-prodtools.git reco_prodtools
        git clone https://github.com/CMS-HGCAL/reco-ntuples.git RecoNtuples

        # compile
        scram b -j
        if [ "$?" != "0" ]; then
            2>&1 echo "cmssw compilation failed"
            return "1"
        fi

        # create the prodtools base templates once
        ( cd reco_prodtools/templates/python; bash produceSkeletons_D41_NoSmear_noPU.sh )
        scram b python

        cd "$origin"
    else
        cd "$CMSSW_BASE/src"
        eval `scramv1 runtime -sh`
        cd "$origin"
    fi


    #
    # minimal software stack
    #

    # variables for external software
    export GLOBUS_THREAD_MODEL="none"
    export PYTHONWARNINGS="ignore"
    export HGC_PYTHONPATH_ORIG="$PYTHONPATH"
    export HGC_GFAL_PLUGIN_DIR_ORIG="$GFAL_PLUGIN_DIR"
    export HGC_GFAL_PLUGIN_DIR="$HGC_SOFTWARE/gfal_plugins"

    # ammend software paths
    hgc_add_bin "$HGC_SOFTWARE/bin"
    hgc_add_py "$HGC_SOFTWARE/lib/python2.7/site-packages"
    hgc_add_py "$HGC_BASE/plotlib"

    # software that is used in this project
    hgc_install_software() {
        local origin="$( pwd )"
        local mode="$1"

        if [ -d "$HGC_SOFTWARE" ]; then
            if [ "$mode" = "force" ]; then
                echo "remove software in $HGC_SOFTWARE"
                rm -rf "$HGC_SOFTWARE"
            else
                if [ "$mode" != "silent" ]; then
                    echo "software already installed in $HGC_SOFTWARE"
                fi
                return "0"
            fi
        fi

        echo "installing software stack in $HGC_SOFTWARE"
        mkdir -p "$HGC_SOFTWARE"

        hgc_install_pip wget
        hgc_install_pip python-telegram-bot
        hgc_install_pip git+https://github.com/riga/scinum.git
        hgc_install_pip git+https://github.com/riga/order.git
        hgc_install_pip git+https://github.com/riga/plotlib.git
        hgc_install_pip luigi
        hgc_install_pip --no-dependencies git+https://github.com/riga/law.git

        # setup gfal, setup patched plugins, remove the http plugin
        ln -s "$gfal2_bindings_file" "$HGC_SOFTWARE/lib/python2.7/site-packages"
        export GFAL_PLUGIN_DIR="$HGC_GFAL_PLUGIN_DIR_ORIG"
        source "$(law location)/contrib/cms/scripts/setup_gfal_plugins.sh" "$HGC_GFAL_PLUGIN_DIR"
        unlink "$HGC_GFAL_PLUGIN_DIR/libgfal_plugin_http.so"
    }
    export -f hgc_install_software
    hgc_install_software silent

    # update the GFAL_PLUGIN_DIR
    export GFAL_PLUGIN_DIR="$HGC_GFAL_PLUGIN_DIR"

    # add _this_ repo to the python path
    hgc_add_py "$HGC_BASE"


    #
    # law setup
    #

    export LAW_HOME="$HGC_BASE/.law"
    export LAW_CONFIG_FILE="$HGC_BASE/law.cfg"

    # configs that depend on the run location
    if [ "$HGC_ON_HTCONDOR" = "1" ] || [ "$HGC_ON_GRID" = "1" ]; then
        export HGC_LOCAL_CACHE="$LAW_JOB_HOME/cache"
        export HGC_LUIGI_WORKER_KEEP_ALIVE="False"
        export HGC_LUIGI_WORKER_FORCE_MULTIPROCESSING="True"
    else
        export HGC_LOCAL_CACHE="$HGC_DATA/cache"
        export HGC_LUIGI_WORKER_KEEP_ALIVE="False"
        export HGC_LUIGI_WORKER_FORCE_MULTIPROCESSING="False"
    fi

    if [ -z "$HGC_SCHEDULER_HOST" ]; then
        2>&1 echo "NOTE: HGC_SCHEDULER_HOST is not set, use '--local-scheduler' in your tasks!"
        export HGC_SCHEDULER_HOST=""
    fi
    export HGC_SCHEDULER_PORT="80"

    # source law's bash completion scipt
    source "$( law completion )" ""

    # rerun the task indexing
    law index --verbose
}
action "$@"
