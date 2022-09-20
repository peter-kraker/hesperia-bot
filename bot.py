#!/bin/python3
# bot.py

import discord
import json
import os
import socket
import time
import datetime
import asyncio


# from google.api_core import retry
from discord.ext import commands
from dotenv import load_dotenv
from google.cloud import pubsub_v1

# User-defined exception class used for message routing

class VhserverException(Exception):
    def __init__(self, message):
        self.message = message

class DoneException(Exception):
    def __init__(self, message):
        self.message = message

# Helper Class representing the vhserver instance.

class Server:

    def __init__(self, ip, port):
        self.ipaddr = ip
        self.port = port

    # Send a Source Engine Query to Steam, and parse the results.
    # Returns the number of players on the server.

    def __query(self, ip, port):
        self.addr = (ip, port)
        message = '\xff\xff\x54\x53\x6f\x75\x72\x63\x65\x20\x45\x6e\x67\x69\x6e\x65\x20\x51\x75\x65\x72\x79\x00'
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.settimeout(2.0)

        client_socket.sendto(message.encode(), self.addr)

        # Steam implemented a challenge to the INFO Request packet in Dec 2020
        #   After sending the info request, the server will respond with a
        #   4-byte challenge packet that you need to re-send, appended 
        #   to the request.

        # Read the challenge off the wire
        challenge = client_socket.recvfrom(2048)[0]

        # The challenge looks like 4 bytes of header (FFFFFFFF), followed by 1
        #   byte of "A" i.e. \x41:
        #
        #   FF FF FF FF 41 DE AD BE EF
        #
        response = challenge[5:]

        # Send the request again with the challenge appended.
        client_socket.sendto((message.encode())+response, self.addr)
        data = client_socket.recvfrom(2048)[0]

        return data

    def getPlayers(self):
        raw = self.__query(self.ipaddr, self.port)

        # Decode and parse the query response
        # Protocol Reference: https://developer.valvesoftware.com/wiki/Server_queries 
        response = raw.decode('utf-8', errors='ignore')[2:].split(chr(0x0))
        players_response = response[6] # Player count is item 7 in the response
        if len(players_response) == 0: 
            return 0
        else:
            num_players = ord(players_response[0])

        return num_players

    # Send a Source engine Query to Steam -- if it times out, the server is off 
    def isOnline(self):
        try:
            self.__query(self.ipaddr, self.port)
        except socket.timeout:
            return False

        return True

async def write_to_discord(message, ctx):
    await ctx.send(message)


## Load Environment

load_dotenv('./.env')
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
IPADDR = os.getenv('IPADDR')
PORT = int(os.getenv('PORT'))
GOOGLE = os.getenv('GOOGLE_JSON')


## Google Environment

# If pubsub fails because of "auth scopes" be sure to:
# export GOOGLE_APPLICATION_CREDENTIALS="/home/$username/$credentials.json"

f = open(GOOGLE)
google_creds = json.loads(f.read())


## PubSub Setup

project_id = google_creds['project_id']

start_topic_id = "start-hesperia-event"
status_topic_id = "status-hesperia-event"
stop_topic_id = "stop-hesperia-event"
update_topic_id = "update-hesperia-event"

response_subscription_id = "status-response-hesperia-event-sub"

publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

start_topic_path = publisher.topic_path(project_id, start_topic_id)
status_topic_path = publisher.topic_path(project_id, status_topic_id)
stop_topic_path = publisher.topic_path(project_id, stop_topic_id)
update_topic_path = publisher.topic_path(project_id, update_topic_id)

response_subscription_path = subscriber.subscription_path(project_id, response_subscription_id)


## Discord Setup

intents = discord.Intents.default()
intents.messages = True
bot = commands.Bot(command_prefix='!', intents=intents)
vhserver = Server(IPADDR, PORT)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!\nConnecting to:')
    for guild in bot.guilds:
        print(f'.. {guild.name}')


## Bot Commands

@bot.command(name='start', help='Starts the Valheim server (Vault616) if it\'s not already online.')
async def start(ctx):
    if not vhserver.isOnline():
        await write_to_discord("Starting Vault616.... This can take 15-20 minutes", ctx)

        data = '{"zone":"us-central1-a","label":"world=hesperia"}'
        data = data.encode("utf-8")
        future = publisher.publish(start_topic_path, data)
        print('Starting up: %s'%future.result())

        while not vhserver.isOnline():
            time.sleep(180)
            await write_to_discord("Initializing... Check back in 3 minutes", ctx)

    await write_to_discord("Hesperia is online.", ctx)
    return

@bot.command(name='stop', help='Stops the Valheim Server (Vault616). Nothing happens if somebody is still logged in.')
async def stop(ctx):
    if not vhserver.isOnline():
        await write_to_discord("The server is already offline.", ctx)
        return

    num_players = vhserver.getPlayers()

    if num_players > 0:
        await write_to_discord("Sorry, there are still %s vikings in Vault616."%num_players, ctx)
    else:
        await write_to_discord("Shutting down Vault616...", ctx)
        data = '{"zone":"us-central1-a","label":"world=hesperia"}'
        data = data.encode('utf-8')
        future = publisher.publish(stop_topic_path, data)
        print('Shutting Down: %s'%future.result())
    return

@bot.command(name='status', help='Responds with the number of players currently logged in.')
async def status(ctx):
    if not vhserver.isOnline():
        await write_to_discord("The server is offline.", ctx)
        return

    num_players = vhserver.getPlayers()

    if num_players == 1:
        response = 'There is %s viking in Vault616.'% num_players
    else:
        response = 'There are %s vikings in Vault616.'% num_players
    await write_to_discord(response, ctx)
    return

@bot.command(name='info', help='Server Info.')
async def status(ctx):
    response = 'Vault616 Server Info:\n```  Server Name: Vault616\n  IP address: 35.208.212.176:2456\n  Server Password: StayAtHomeDads```To Join, use Steam\'s server window to add by IP:\nSteam > View > Servers > Favorites > [Right Click] "Add by IP Address > "35.208.212.176:2456"' 

    await write_to_discord(response, ctx)
    return

#@bot.command(name='update', help='Updates and restarts the server.')
async def update(ctx):
    # This should only work while the server is online and has 0 players:
    # Server will stop vhserver
    # Server will run the updates
    # Server will start vhserver
#    if not vhserver.isOnline():
#        await write_to_discord("The server is offline. To update, please start the server and try again with 0 players.",ctx)
#        return

    await write_to_discord("Updating Hesperia, one moment please.", ctx)


    # Send an update request to the server via pubsub
    data = 'update'
    data = data.encode('utf-8')
    update_future = publisher.publish(update_topic_path, data)
    print('Updating: %s..'%update_future.result())

    def response_callback(message):
        print(ctx)
        print(" Inside: %s."%message.data.decode('utf-8'))
        asyncio.run(asyncio.wait_for(ctx.send(message.data), 15))
        # write_to_discord(message.data.decode('utf-8'), ctx)
        message.ack()


    # We want to ignore all messages that were delievered before we started listening.
    seekreq = pubsub_v1.types.SeekRequest(subscription=response_subscription_path, time=datetime.datetime.now())
    subscriber.seek(seekreq)

    # Start listening to what vhserver is telling us
    response_future = subscriber.subscribe(response_subscription_path, callback=response_callback)
    print ("Listening for messages on %s.."%response_subscription_path)

#    update_is_done = False
#    while subscriber:
#        response = subscriber.pull(
#                request={"subscription": response_subscription_path, "max_messages": 10},
#                retry=retry.Retry(deadline=10),
#                )
#
#        ack_ids = []
#        for received_message in response.received_messages:
#            vhserver_response = received_message.message.data.decode('utf-8')
#            if vhserver_response == "{done}":
#                update_is_done = True
#
#            await write_to_discord(received_message.message.data.decode('utf-8'), ctx)
#            ack_ids.append(received_message.ack_id)
#
#        subscriber.acknowledge(
#            request={"subscription": response_subscription_path, "ack_ids": ack_ids}
#        )
#
#        if update_is_done == True:
#            break
    with subscriber:
        try:
            print(response_future.result())

        except (KeyboardInterrupt, TimeoutError) as e:
            response_future.cancel()
        except Exception as e:
            response_future.cancel()

    await write_to_discord("Server has been updated", ctx)
    return
        

bot.run(TOKEN)
