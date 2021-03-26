from flask import Flask, jsonify, request, render_template, redirect
from tinydb import TinyDB, Query
import json
import requests
from score_checker import ScoreChecker
import threading
import time
import redis
from rq import Queue, Worker
from rq.command import send_stop_job_command
from rq.job import Job
import rq_dashboard
from worker_functions import start_check
import subprocess
import serial

r = redis.Redis()
q = Queue(connection=r, default_timeout=144000)

app = Flask(__name__)
app.config.from_object(rq_dashboard.default_settings)
app.register_blueprint(rq_dashboard.blueprint, url_prefix="/rq")


db = TinyDB('db.json')
# lock to control access to variable

th = threading.Thread(target=ScoreChecker, args=(db.all()[0]['id'],))

def start_checking_thread():
  th.start()

def stop_checking_thread():
  pass


@app.route('/')
def hello_world():

  records = db.all()
  #checking_score = db.table("game").all()[0]["checking_score"]
  team_id = records[0]['id']
  url = 'https://statsapi.web.nhl.com/api/v1/teams/' + str(team_id) + '?expand=team.schedule.next'
  r = requests.get(url)
  json_response = r.json()
  team_name = json_response['teams'][0]['name']
  next_game = json_response['teams'][0]['nextGameSchedule']['dates'][0]['date']
  
  checking_score = False
  job = None

  conn = redis.Redis()
  try:
    job = Job.fetch('checking_score', connection=conn)
  except:
    pass

  if job is not None and job.get_status() == "started":
    checking_score = True

  return render_template('index.html', team_name=team_name, next_game=next_game, checking_score=checking_score)

@app.route("/start_checking_score", methods=["POST"])
def start_checking_score():
  records = db.all()
  team_id = records[0]['id']

  job = q.enqueue(start_check, team_id, job_id="checking_score", job_timeout=14400)
  return redirect("/")

@app.route("/stop_checking_score", methods=["POST"])
def stop_checking_score():

  conn = redis.Redis()
  curr_job = Job.fetch('checking_score', connection=conn)
  if curr_job is not None:
    print(curr_job.get_status())
  # qlen = len(q)
  # if qlen > 0:
  #   curr_job = q.jobs[0]
  #   curr_job_id = curr_job.id
  #   print(curr_job.get_status())
    # if curr_job_id == "checking_score" and curr_job.get_status() == "started":
    send_stop_job_command(conn, curr_job.id)
  return redirect("/")

    

@app.route("/my_team", methods=['POST'])
def select_team():
  print(request.form)
  horn = False
  if 'horn' in request.form.keys():
    horn = True
  db.update({"id":request.form['teams'], "horn":horn})
  return redirect("/")


@app.route("/settings")
def settings():
    url = 'https://statsapi.web.nhl.com/api/v1/teams'
    r = requests.get(url)
    json_response = r.json()

    teams = json_response['teams']
    team_names = []
    horn = False
    for team in teams:
      team_names.append({"id":team["id"],"name":team['name']})

    record = db.all()[0]
    print(record)
    horn = record['horn']

    return render_template("settings.html", teams=team_names, horn=horn)

@app.route("/lights_horn")
def lights_horn():
    serial_port = '/dev/ttyACM0'
    ser = serial.Serial(serial_port)
    ser.baudrate = 9600
    ser.write(b'0;0;255;')
    ser.close()
     # playsound('blues-horn.mp3')
    subprocess.run(["omxplayer", "-o", "local", "./horn.mp3"])
    return redirect("/") 


if __name__ == "__main__":
  app.run(host="0.0.0.0")
