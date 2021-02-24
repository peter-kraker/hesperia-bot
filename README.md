# hesperia-bot
Hesperia bot is a Discord Bot that can manage a GCP instance running a dedicated Valheim game server. The bot can start, stop, and check the number of players currently online.

The Valheim game server runs (well) on a single n1-standard-1 machine. The discord bot can run on the GCP free-tier f1-micro instance.

I followed the following guides to build this bot:

* Settting up the Valheim Server using Linux GSM: https://linuxgsm.com/lgsm/vhserver/
* How to make a Discord bot in Python: https://realpython.com/how-to-make-a-discord-bot-python/
* PubSub Quickstart guide: https://cloud.google.com/pubsub/docs/quickstart-client-libraries
* Scheduling compute instances with Cloud Scheduler: https://cloud.google.com/scheduler/docs/start-and-stop-compute-engine-instances-on-a-schedule

## Commands

### Start

!start - Will start the sever if it's not already up.

### Stop

!stop - Will stop the server if it's not being used.

### Status

!status - Will return the number of players currently logged into the server
