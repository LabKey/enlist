# enlist

This is a tool to help create LabKey enlistments in known/correct configurations.
  
To create a completely new release15.3 enlistment, assuming ~/enlist/bin is on your path.

```
$ mkdir release15.3

$ cd release15.3

$ enlistconfig ~/enlist/release15_3.config

$ checkconfig -v
```

To change to the modules15.3 branch
```
$ enlistconfig ~/enlist/modules15_3.config

$ checkconfig -v
```

To add the cds configuration
```
$ checkconfig ~/enlist/cds.config

$ addconfig ~/enlist/cds.config
```

# mr
Enlist should interoperate with with **mr**. There is a copy in the bin/. see here for documentation: https://github.com/joeyh/myrepos


# todos and ideas
* module/config dependencies
* create config from existing enlistments (see mr register)
* manage active modules in intellij .ipr
* manage database connections
* update ~/.mrtrust
