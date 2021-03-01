#!/bin/python3
# bot.py

import discord
import json
import os
import socket
import time

from discord.ext import commands
from dotenv import load_dotenv
from google.cloud import pubsub_v1

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

bot = commands.Bot(command_prefix='!')
vhserver = Server(IPADDR, PORT)


## Bot Commands

@bot.command(name='start', help='Starts the Valheim server (Hesperia) if it\'s not already online.')
async def start(ctx):
    if not vhserver.isOnline():
        await write_to_discord("Starting Hesperia.... This can take 15-20 minutes", ctx)

        data = '{"zone":"us-central1-a","label":"world=hesperia"}'
        data = data.encode("utf-8")
        future = publisher.publish(start_topic_path, data)
        print('Starting up: %s'%future.result())

        while not vhserver.isOnline():
            time.sleep(180)
            await write_to_discord("Initializing... Check back in 3 minutes", ctx)

    await write_to_discord("Hesperia is online.", ctx)
    return

@bot.command(name='stop', help='Stops the Valheim Server (Hesperia). Nothing happens if somebody is still logged in.')
async def stop(ctx):
    if not vhserver.isOnline():
        await write_to_discord("The server is already offline.", ctx)
        return

    num_players = vhserver.getPlayers()

    if num_players > 0:
        await write_to_discord("Sorry, there are still %s vikings in Hesperia."%num_players, ctx)
    else:
        await write_to_discord("Shutting down Hesperia...", ctx)
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
        response = 'There is %s viking in Hesperia.'% num_players
    else:
        response = 'There are %s vikings in Hesperia.'% num_players
    await write_to_discord(response, ctx)
    return

# @bot.command(name='udate', help='Updates and restarts the server.')
async def update(ctx):
    # This should only work while the server is online and has 0 players:
    # Server will stop vhserver
    # Server will run the updates
    # Server will start vhserver
    if not vhserver.isOnline():
        await write_to_discord("The server is offline. To update, please start the server and try again with 0 players.",ctx)
        return

    write_to_discord("Updating Hesperia, one moment please.", ctx)


    # Send an update request to the server via pubsub
    data = 'update'
    data = data.encode('utf-8')
    update_future = publisher.publish(update_topic_path, data)
    print('Updating: %s..'%update_future.result())

    def response_callback(message):
        print("Received %s."%message.data)
        message.ack()
        if message.data.decode('utf-8') == "{done}":
            raise Exception('Update Complete')
        return message.data

    response_future = subscriber.subscribe(response_subscription_path, callback=response_callback)
    print ("Listening for messages on %s.."%response_subscription_path)


    with subscriber:
        try:
            response = response_future.result()
            await ctx.send(response)
        except (KeyboardInterrupt, TimeoutError):
            response_future.cancel()
        except e:
            response_future.cancel()
            print(e)

    response = "Server has been updated"
    await ctx.send(response)

    return
        

bot.run(TOKEN)
