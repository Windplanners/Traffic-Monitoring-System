#!/usr/bin/python

import serial, threading, socket, MySQLdb, bottle, datetime
from bottle import route, run, template, request, static_file
from datetime import datetime as dt

s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
s.connect(('google.com',0))
host = s.getsockname()[0]

epoch = dt.utcfromtimestamp(0)
db = MySQLdb.connect('localhost',db='Traffic')

fmt = "%Y-%m-%d %H:%M:%S"

cursor = db.cursor()
endobj = dt.now()
end = endobj.strftime(fmt)

global offline
offline = None

try:
	f = open('/home/pi/Traffic/heartbeat.txt')
	start = f.read()
	f.close()
	startobj = dt.strptime(start, fmt)
	delta = datetime.timedelta(minutes=2)
	downtime = endobj-startobj

	if downtime > delta:
		dbrequest = ("INSERT INTO downtimes (start, end) VALUES ('%s', '%s')" % (start,end))
		cursor.execute(dbrequest)
		db.commit()
		cursor.close()
except:
	pass

def read_from_serial():
	global offline
	output = " "
	ser = serial.Serial('/dev/ttyACM0', 9600, 8, 'N', 1, timeout=1)
	while True:
		try:
	  		while output != "":
  				output = ser.readline()
				num = output.count("C")
				off = "O" in output
				on = "P" in output
				for i in range(0,num):
					cursor = db.cursor()
					v = dt.now()
					cursor.execute(v.strftime("INSERT INTO stamps (stamp) VALUES ('%Y-%m-%d %H:%M:%S')"))
					cursor.execute(v.strftime("INSERT INTO hourCounts (time, count) VALUES ('%Y-%m-%d %H:0:0', 1) ON DUPLICATE KEY UPDATE count = count + 1"))
					cursor.execute(v.strftime("INSERT INTO dayCounts (time, count) VALUES ('%Y-%m-%d', 1) ON DUPLICATE KEY UPDATE count = count + 1"))
					db.commit()
					cursor.close()
				if off:
					offline = dt.now()
				if on and offline != None:
					cursor = db.cursor()
					s = offline.strftime(fmt)
					e = dt.now().strftime(fmt)
					cursor.execute("INSERT INTO downtimes (start, end) VALUES ('%s', '%s')" % (s, e))
					db.commit()
					cursor.close()
					offline = None
		except:
			db = MySQLdb.connect('localhost', db="Traffic")
	  	output = " "

readthread = threading.Thread(target=read_from_serial)
readthread.start()

def heartbeat():
	out = '/home/pi/Traffic/heartbeat.txt'
	out_file = open(out, 'w')
	out_file.write(dt.now().strftime("%Y-%m-%d %H:%M:%S"))
	out_file.close()
	heartTime = threading.Timer(60.0, heartbeat)
	heartTime.start()

heartTime = threading.Timer(60.0, heartbeat)
heartTime.start()

@route('/static/<filename>')
def server_static(filename):
	return static_file(filename, root="/home/pi/Traffic")

@route('/request')
def login():
    return '''
        <form action="/request" method="post">
            From: <input name="start" type="date" min="2018-01-01" />
            To: <input name="end" type="date" min="2018-01-01" />
            <input value="Request Data" type="submit" />
        </form>
    '''

@route('/request', method='POST')
def do_login():
    start = request.forms.get('start')
    end = request.forms.get('end')
    response = '''
	<!DOCTYPE html>
	<html>
	<head>
	<style>
	table, th, td {
	    border: 1px solid black;
	}
	</style>
	</head>
	<body>
	<table>
    '''
    rdb = MySQLdb.connect('localhost', db='Traffic')
    cursor = rdb.cursor()
    cursor.execute("SELECT stamp FROM stamps WHERE stamp > '" + str(start) + "' and stamp < '" + str(end) + "'")
    r = cursor.fetchall()
    for i in r:
	response += "<tr><td>" + str(i[0]) + "</td></tr>"
    response += '''
	</table>
	</body>
	</html>
    '''
    cursor.close()
    rdb.close()
    return response
@route('/output.js')
def output():
	global offline
	rdb = MySQLdb.connect('localhost', db = 'Traffic')
	cursor = rdb.cursor()
	cursor.execute("SELECT time, count FROM hourCounts")
	r = cursor.fetchall()
	hourCounts = []
	for i in r:
		hourCounts.append([i[0].strftime(fmt),int(i[1])])
	cursor.execute("SELECT time,count FROM dayCounts")
	r = cursor.fetchall()
	dayCounts = []
	for i in r:
		dayCounts.append([i[0].strftime(fmt),int(i[1])])
	downtimes = []
	cursor.execute("SELECT start, end FROM downtimes")
	r = cursor.fetchall()
	for i in r:
		downtimes.append([i[0].strftime(fmt), i[1].strftime(fmt)])
	if offline != None:
		downtimes.append([offline.strftime(fmt), dt.now().strftime(fmt)])
	response = "function getData()	{return %s}" % ([hourCounts, dayCounts, downtimes])
	cursor.close()
	rdb.close()
	return response

@route('/')
def home():
	f = open('graph.txt')
	response = f.read()
	return response % (host)

application = bottle.default_app()
from paste import httpserver
httpserver.serve(application, host='0.0.0.0', port=80)
