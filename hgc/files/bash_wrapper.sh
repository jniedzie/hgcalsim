#!/usr/bin/env bash

# wrapper script to ensure that the job script is executed in a bash

# fix for CERN htcondor batch system: although getenv is used,
# ensure that PATH is really what we expect
export PATH="{{env_path}}"

bash "{{job_file}}" $@
