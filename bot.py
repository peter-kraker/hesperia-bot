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


## Load Environment

load_dotenv('./.env')
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
IPADDR = os.getenv('IPADDR')
PORT = int(os.getenv('PORT'))
GOOGLE = os.getenv('GOOGLE_JSON')


## Google Environment

# If pubsub fails because of "auth scopes" be sure to:
# export GOOGLE_APPLICATION_CREDENTIALS="/home/petes256/discord/valheim-a13e89a6204a.json"

f = open(GOOGLE)
google_creds = json.loads(f.read())


## PubSub Setup

project_id = google_creds['project_id']

response_topic_id = "status-response-hesperia-event"
start_topic_id = "start-hesperia-event"
status_topic_id = "status-hesperia-event"
stop_topic_id = "stop-hesperia-event"

publisher = pubsub_v1.PublisherClient()
response_topic_path = publisher.topic_path(project_id, response_topic_id)
start_topic_path = publisher.topic_path(project_id, start_topic_id)
status_topic_path = publisher.topic_path(project_id, status_topic_id)
stop_topic_path = publisher.topic_path(project_id, stop_topic_id)


## Discord Setup

bot = commands.Bot(command_prefix='!')
vhserver = Server(IPADDR, PORT)


## Bot Commands

@bot.command(name='start', help='Starts the Valheim server (Hesperia) if it\'s not already online.')
async def start(ctx):
    if not vhserver.isOnline():
        response = "Starting Hesperia.... This can take 15-20 minutes"
        await ctx.send(response)

        data = '{"zone":"us-central1-a","label":"world=hesperia"}'
        data = data.encode("utf-8")
        future = publisher.publish(start_topic_path, data)
        print('Starting up: %s'%future.result())

        response = "Initializing... Check back in 3 minutes"
        while not vhserver.isOnline():
            time.sleep(180)
            await ctx.send(response)

    response = "Hesperia is online."
    await ctx.send(response)
    return

@bot.command(name='stop', help='Stops the Valheim Server (Hesperia). Nothing happens if somebody is still logged in.')
async def stop(ctx):
    if not vhserver.isOnline():
        response = "The server is already offline."
        await ctx.send(response)
        return

    num_players = vhserver.getPlayers()

    if num_players > 0:
        response = "Sorry, there are still %s vikings in Hesperia."%num_players
        await ctx.send(response)
    else:
        response = "Shutting down Hesperia..."
        await ctx.send(response)
        data = '{"zone":"us-central1-a","label":"world=hesperia"}'
        data = data.encode('utf-8')
        future = publisher.publish(stop_topic_path, data)
        print('Shutting Down: %s'%future.result())
    return

@bot.command(name='status', help='Responds with the number of players currently logged in.')
async def status(ctx):
    if not vhserver.isOnline():
        response = "The server is offline."
        await ctx.send(response)
        return

    num_players = vhserver.getPlayers()

    if num_players == 1:
        response = 'There is %s viking in Hesperia.'% num_players
    else:
        response = 'There are %s vikings in Hesperia.'% num_players
    await ctx.send(response)

@bot.command(name='update', help='Updates and restarts the server.')
async def update(ctx):
    if not vhserver.isOnline():
        

bot.run(TOKEN)
