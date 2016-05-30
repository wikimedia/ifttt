# Wikipedia channel for IFTTT

An [IFTTT](https://ifttt.com/recipes) channel built for [Wikimedia Tool Labs](http://tools.wmflabs.org/).

It currently supports the following triggers:

 - Picture of the day
 - Article of the day
 - Word of the day
 - New article
 - Hashtag in an article edit summary
 - Updates to article
 - Updates from user
 - Page added to category
 - Page updated in category

# [WIP] Deploying to Wikimedia Labs

We are in the process of moving the IFTTT channel to a standalone service on Wikimedia Labs from tool labs. The new deployment process is explained here, and might evolve.

The staging server for dev(ifttt-dev channel) is setup at ifttt-staging-01.eqiad.wmflabs, the public endpoint is hosted at ifttt-dev.wmflabs.org
The prod server will be at ifttt-01.eqiad.wmflabs(ifttt prod channel), public endpoint is at ifttt.wmflabs.org

To create your own test instance, create an instance in the ifttt labs project, and apply the role::ifttt::staging puppet role to initialize the repo, and have necessary packages installed on the server. Add your host to the STAGES config in the fabfile.

* To list all fabric actions: `fab -list`
```
ifttt [master] fab -list
Available commands:

    deploy             Deploys updated code to the web server
    initialize_server  Setup an initial deployment on a fresh host.
    production
    restart_ifttt      Restarts the ifttt web sersive
    staging
```

* To initialize server (Needs to be done only the first time after setting up server through puppet):
`fab <staging|production> initialize_server`.
```
ifttt [master] fab staging initialize_server --hide everything --show user
Setting up the staging server
Updating ifttt source repo
Uploading config files to remote host(s)
Upgrading requirements

Done.
Disconnecting from madhuvishy@ifttt-staging.ifttt.eqiad.wmflabs... done.
```

* To deploy changes: `fab <staging|production> deploy`.
```
ifttt [master] ⚡ fab staging deploy --hide everything --show user
Deploying to staging
Updating ifttt source repo
Uploading config files to remote host(s)
Upgrading requirements
Restarting ifttt

Done.
Disconnecting from madhuvishy@ifttt-staging.ifttt.eqiad.wmflabs... done.
```

* To restart the service: `fab <staging|production> restart_ifttt`


# License

Copyright 2015 Ori Livneh <ori@wikimedia.org>,
               Stephen LaPorte <stephen.laporte@gmail.com>,
               Alangi Derick <alangiderick@gmail.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.