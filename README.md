# Hesperia-bot
Hesperia bot is a Discord Bot that can manage a GCP instance running a dedicated Valheim game server. The bot can start, stop, and check the number of players currently online.

The Valheim game server runs (well) on a single n1-standard-1 machine. The discord bot can run on the GCP free-tier f1-micro instance.

I followed the following guides to build this bot:

* Settting up the Valheim Server using Linux GSM: https://linuxgsm.com/lgsm/vhserver/
* How to make a Discord bot in Python: https://realpython.com/how-to-make-a-discord-bot-python/
* PubSub Quickstart guide: https://cloud.google.com/pubsub/docs/quickstart-client-libraries
* Scheduling compute instances with Cloud Scheduler: https://cloud.google.com/scheduler/docs/start-and-stop-compute-engine-instances-on-a-schedule

## Setup

From a "stock" debian or ubuntu install:

1. Install python

> sudo apt-get install python3

2. Install pip

> sudo apt-get install python3-pip

3. Install the discord libraries

> pip3 install -U discord.py
> pip3 install -U python-dotenv

4. Install and initialize the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)

5. Install the [Google PubSub python client libraries](https://cloud.google.com/pubsub/docs/quickstart-client-libraries)

> pip install --upgrade google-cloud-pubsub
    
Be sure to set up your environment variables properly:

"Set the environment variable GOOGLE_APPLICATION_CREDENTIALS to the path of the JSON file that contains your service account key. This variable only applies to your current shell session, so if you open a new session, set the variable again."

## Usage

    $ python3 bot.py

## Commands

### Start

!start - Will start the sever if it's not already up.

### Stop

!stop - Will stop the server if it's not being used.

### Status

!status - Will return the number of players currently logged into the server

## Architecture

There are a few components to this system: 

* The Discord Bot
* The Valheim server (LinuxGSM)
* Google's Cloud Services
    *  Compute Engine
    *  PubSub
    *  Cloud Scheudler
    *  Cloud Functions

The Discord bot uses Dicord's python library to manage the interaction with the Discord servers. The 'Bot' Client sub-class implements 'commands' that are called when a user types the correct 
