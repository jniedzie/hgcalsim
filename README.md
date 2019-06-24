# HGCAL simulation using law


### Resources

- [law](https://law.readthedocs.io/en/latest)
- [luigi](https://luigi.readthedocs.io/en/stable)


### Setup

After cloning the repository, run

```shell
source setup.sh
```

This will install CMSSW and a few python packages once. You should source the setup script everytime you start with a new session.

Also, in order to let the tasks communicate with a central luigi scheduler, you should set

```shell
export HGC_SCHEDULER_HOST="..."
export HGC_SCHEDULER_PORT="..."
```

most probably in your bashrc file. Otherwise, you should add `--local-scheduler` to all `law run` commands.


### Example commands

Re-compile CMSSW with 2 cores after making some updates to the code:

```shell
law run CompileCMSSW --n-cores 2
```

Run GSD, RECO and NTUP steps and create a simple eta-phi histogram of all rechits and calo particles:

```shell
law run PlotTask --version dev --n-events 2
```
