import requests
import schedule
import time
import datetime
import pytz, dateutil.parser
from playsound import playsound
import os
from tinydb import TinyDB, Query
import serial
import subprocess
import threading

###REQUIREMENTS##

#check once a day for new games
#if there is a game today, break into a check once every minute
#check every minute until the gametime is current time
#once 
###


class ScoreChecker():

  score = 0
  base_url = 'https://statsapi.web.nhl.com/'
  is_game_day = False
  game_started = False
  database = TinyDB('db.json')
  table = database.table("game")

  def __init__(self, team_id):
    print("STARTING THE SCORE CHECKER")
    checking_score = self.table.all()[0]['checking_score']
    print(checking_score)
    #self.play_horn()
    # if checking_score:
    #   print("already running")
    #   return
    # else:
    self.team_id = int(team_id)
    self.endpoint = self.base_url + 'api/v1/' + 'teams/'+ str(team_id)+'?expand=team.schedule.next'
    self.start()

  def start(self):
    self.wait_for_next_game_date()
  
  def get_live_feed_link(self):
    r = requests.get(self.endpoint)
    json = r.json()
    next_game_link = json['teams'][0]['nextGameSchedule']['dates'][0]['games'][0]['link']

    feed = self.base_url + next_game_link

    self.live_feed_link = feed

  def check_game_day(self):
    print("checking game day")
    r = requests.get(self.endpoint)
    json = r.json()

    if str(datetime.date.today()) == json['teams'][0]['nextGameSchedule']['dates'][0]['date']:
      print("today is game day")
      self.is_game_day = True
      self.get_live_feed_link()



  def wait_for_next_game_date(self):
    self.check_game_day()
    # schedule.every(2).hours.do(self.check_game_day).tag('game-day-check')

    # while not self.is_game_day:
    #   schedule.run_pending()
    #   time.sleep(1)
    

    # schedule.clear('game-day-check')
    if self.is_game_day:
      self.wait_for_game_time()
    else:
      return
  
  def check_game_time(self):
    print("checking game time")

    feed = requests.get(self.live_feed_link)
    feed_json = feed.json()

    game_status = feed_json['gameData']['status']['abstractGameState']

    if game_status == "Live":
      self.game_started = True
      print('game is running')



  def wait_for_game_time(self):
    self.check_game_time()
    schedule.every(5).minutes.do(self.check_game_time).tag("game-time-check")

    while not self.game_started:
      schedule.run_pending()
      time.sleep(1)

    schedule.clear('game-time-check')
    self.check_score_loop()


  def check_score(self):

    r = requests.get(self.live_feed_link)
    json = r.json()

    away_score = json['liveData']['linescore']['teams']['away']['goals']
    away_team_id = json['liveData']['linescore']['teams']['away']['team']['id']

    home_score = json['liveData']['linescore']['teams']['home']['goals']
    home_team_id = json['liveData']['linescore']['teams']['home']['team']['id']

    game_status = json['gameData']['status']['abstractGameState']

    print(away_score, home_score)

    if home_team_id == self.team_id:
      if home_score > self.score:
        print(f"Looking for {self.team_id}, home_id = {home_team_id}")
        self.score = home_score
        self.celebrate()
        print("GOAL!")
        #start the lights!

    if away_team_id == self.team_id:
      if away_score > self.score:
        print(f"Looking for {self.team_id}, home_id = {away_team_id}")
        self.score = away_score
        self.celebrate()
        print("GOAL!")
        #start the lights

    if game_status != "Live":
      print(game_status)
      print("Game Ended")
      self.game_started = False
      self.table.update({"checking_score":False})
      
  def celebrate(self):
    horn_th = threading.Thread(target=self.play_horn)
    horn_th.start()
    lights_th = threading.Thread(target=self.goal)
    lights_th.start()

  def play_horn(self):
    horn = self.database.all()[0]['horn']
    print(horn)
    if horn:
     # playsound('blues-horn.mp3')
     subprocess.run(["omxplayer", "-o", "local", "./horn.mp3"])

  def goal(self):
    serial_port = '/dev/ttyACM0'
    ser = serial.Serial(serial_port)
    ser.baudrate = 9600
    ser.write(b'0;0;255;')
    ser.close() 

  def check_score_loop(self):
    self.table.update({"checking_score":True})
    print("checking score")
    try:
      self.check_score()
      schedule.every(10).seconds.do(self.check_score).tag("score-check")
      while self.game_started:
        schedule.run_pending()
      schedule.clear("score-check")
    except:
      self.table.update({"checking_score":False})
      return
