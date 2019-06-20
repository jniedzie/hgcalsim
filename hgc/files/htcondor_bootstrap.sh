#!/usr/bin/env bash

# Bootstrap file for batch jobs that is sent with all jobs and
# automatically called by the law remote job wrapper script to find the
# setup.sh file of this example which sets up software and some environment
# variables.

action() {
    export HGC_ON_HTCONDOR="1"

    source "{{hgc_base}}/setup.sh"
}
action
