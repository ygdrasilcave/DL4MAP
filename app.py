from flask import Flask, jsonify, g, request, render_template
from flask_cors import CORS
from sqlite3 import dbapi2 as sqlite3
#import sqlite3
from datetime import datetime
import json
from apscheduler.schedulers.background import BackgroundScheduler
#import logging
import random
import paho.mqtt.client as mqtt
import OSC
import threading
import atexit

DATABASE = 'testDB'
TABLE_NAME_PREFIX = 'TB_project_'  #'TB_project_200707' ymmdd
TABLE_SCHEMA = '(logTime text, schedOrEvt text, modID integer, modName text, modValue text);'
###Scheduler
#log = logging.getLogger('apscheduler.executors.default')
sched = BackgroundScheduler(daemon=True)
sched_day_of_week = 'mon-sun'   # 0-6 mon,tue,wed,thu,fri,sat,sun
sched_hour='9-17'               # 0-23
sched_minute='*/5'              # 0-59
###OSC Server
oscServer_port = 12000
oscServer = OSC.OSCServer(('0.0.0.0', oscServer_port))
oscServerThread = threading.Thread(target = oscServer.serve_forever)
oscServerThread.daemon = True
###OSC Clients
oscClientAddr = [('192.168.1.32', 12001), ('192.168.1.32', 12002)]
#oscClientAddr = [('192.168.0.14', 12001), ('192.168.1.14', 12002)]
oscClient = []
###OSC message
###oscMsg_schedRequest_moduleID = ['time tag', 1, 2]
#oscMsg_schedRequest_moduleID = ['', 1, 2, 3, 100, 101]
oscMsg_schedRequest_moduleID = ['', 1, 2]

info_sched = '(day of week) ' + sched_day_of_week + ', (hour) ' +  sched_hour + ', (minute) ' + sched_minute
info_shced_id = '(scheduled module-ID) '
info_osc = '(OSC server port) ' + str(oscServer_port) + ', (OSC clients) '
for o in oscClientAddr:
    _ip = o[0]
    _port = str(o[1])
    info_osc = info_osc + _ip + ':' + _port + ', '
for i in oscMsg_schedRequest_moduleID:
    if(i != ''):
        _id = str(i)
        info_shced_id = info_shced_id + _id + ', '
info = [info_sched, info_shced_id, info_osc]

app = Flask(__name__)
CORS(app)

# DATABASE ##############################################################################################

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def getDB(f=0):
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        if f is 0:
            db.row_factory = sqlite3.Row
        elif f is 1:
            db.row_factory = dict_factory
    return db

def createTable():
    db = getDB(0)
    #with app.open_resource('schema.sql', mode='r') as f:
    #   db.cursor().executescript(f.read().replace('\n', ''))
    today = datetime.now().strftime("%Y%m%d")[2:]
    sql = 'create table if not exists ' + TABLE_NAME_PREFIX + today + TABLE_SCHEMA
    db.cursor().executescript(sql)
    res = db.commit()
    print('****** create table ******')
    print(TABLE_NAME_PREFIX + today)
    print(res)
    print('**************************')

def writeData(lt='', se='', si=0, sn='', sv=''):
    today = datetime.now().strftime("%Y%m%d")[2:]
    #('11:45:20', 'evt', 1, 'light_room_1', '60.50')
    sql = "insert into " + TABLE_NAME_PREFIX + today + " (logTime, schedOrEvt, modID, modName, modValue) VALUES('%s', '%s', %d, '%s', '%s')" %(lt, se, int(si), sn, sv)
    db = getDB(0)
    db.execute(sql)
    res = db.commit()
    #print(res)

"""
@app.before_first_request
def test():
    now = datetime.now().strftime("%H:%M:%S")
    writeData(now, 'sched', 5, 'module-5', format(random.uniform(5,30),'.2f'))
    print('<===== write new data at ' + now)
"""
def getTableName():
    today = datetime.now().strftime("%Y%m%d")[2:]
    table = request.args.get('tableName', today)
    return table

def getTableList():
    sql = 'select name from sqlite_master where type="table"'
    db = getDB(1)
    ex = db.execute(sql)
    allTable = ex.fetchall()
    ex.close()

    tb = []
    for t in allTable:
        tb.append(int(t['name'].split('_')[2]))
        tb.sort()
    #print(tb)
    tables = ''
    for i in range(len(tb)):
        if (i%5 == 4):
            tables = tables + TABLE_NAME_PREFIX + str(tb[i]) + ',\n'
        else:
            tables = tables + TABLE_NAME_PREFIX + str(tb[i]) + ', '
    
    return tables

def fetchTable():    
    sql = 'select * from ' + TABLE_NAME_PREFIX + str(getTableName()) + ' ORDER BY logTime'
    db = getDB(1)
    ex = db.execute(sql)
    readings = ex.fetchall()
    ex.close()
    return readings

# OSC ##############################################################################################

def closeOSC():
    print('===== Waiting for server-thread to finish =====')
    for i in range(len(oscClient)):
        oscClient[i].close()
    oscServer.close()
    #oscServerThread.join()
    print('===== Done =====')

def oscParse(addr, tags, stuff, source):
    #print("received new osc msg from %s" % OSC.getUrlStr(source))
    _start = int(sched_hour.split('-')[0])
    _end = int(sched_hour.split('-')[1])
    now = datetime.now().strftime("%H:%M:%S")
    _currH = int(now.split(':')[0])
    if( _currH >= _start and _currH <= _end):
        if(addr == '/schedReport'):
            if(tags == 'iss'):
                with app.app_context():
                    #('11:45:20', 'sched', int(modID), 'modName', 'modValue')
                    writeData(now, 'sched', stuff[0], stuff[1], stuff[2])
                print('===== Scheduled report: table update ' + now)
        elif(addr == '/evtReport'):
            if(tags == 'iss'):
                with app.app_context():
                    #('11:45:20', 'evt', int(modID), 'modName', 'modValue')
                    writeData(now, 'evt', stuff[0], stuff[1], stuff[2])
                print('===== Event report: table update ' + now)
    else:
        print('===== time over =====')

def oscSendMsg(client, msg):
    bundle = OSC.OSCBundle()
    bundle.append( {'addr':'/schedRequest', 'args':msg} )
    client.send(bundle)

def oscInit():
    i = 0
    for c in oscClientAddr:
        oscClient.append(OSC.OSCClient())
        oscClient[i].connect(c)
        i = i+1
    print('===== OSC Clients connected =====')
    print(oscClient)
    print('=================================')
    #oscServer.addDefaultHandlers()
    oscServer.addMsgHandler('/schedReport', oscParse)
    oscServer.addMsgHandler('/evtReport', oscParse)
    for addr in oscServer.getOSCAddressSpace():
        print('===== OSC handlers: ' + addr)
    oscServerThread.start()

# Scheduler ##############################################################################################

#start_date='2010-10-10 09:30:00', end_date='2014-06-15 11:00:00'
#@sched.scheduled_job('interval', minutes=5, start_date=)
@sched.scheduled_job('cron', day_of_week=sched_day_of_week, hour=sched_hour, minute=sched_minute)
def schedUpdateDB():
    now = datetime.now().strftime("%H:%M:%S")
    oscMsg_schedRequest_moduleID[0] = now
    for i in range(len(oscClient)):
        oscSendMsg(oscClient[i], oscMsg_schedRequest_moduleID)
        print('------ request ------')
        print(oscClientAddr[i])
        print(oscMsg_schedRequest_moduleID)
        print('---------------------')
    """
    with app.app_context():
        now = datetime.now().strftime("%H:%M:%S")
        writeData(now, 'sched', 5, 'distSensor', format(random.uniform(5,30),'.2f'))
        writeData(now, 'sched', 6, 'motorSpeed', format(random.uniform(5,30),'.2f'))
        writeData(now, 'evt', 100, 'videoScene', str(random.randint(1,5)))
        writeData(now, 'evt', 101, 'userInput', str(random.randint(1,8)))
        print('New data updated: ' + now)
    """    
_hour = int(sched_hour.split('-')[0])-1
@sched.scheduled_job('cron', day_of_week=sched_day_of_week, hour=_hour, minute=45)
def schedCreateTable():
    with app.app_context():
        now = datetime.now().strftime("%H:%M:%S")
        createTable()
        print('------ New Table created: ' + now)

def schedStart():
    """
    log.setLevel(logging.INFO)  # DEBUG
    fmt = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    h = logging.StreamHandler()
    h.setFormatter(fmt)
    log.addHandler(h)    
    """
    sched.start()
    print('------ Start Scheduler ------')
    print(sched_day_of_week+' : '+sched_hour+' : '+sched_minute)
    print('-----------------------------')

# APP ##############################################################################################

@app.teardown_appcontext
def closeDB(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
        print('$$$ DB closed $$$')

with app.app_context():
    today = datetime.now().strftime("%Y%m%d %H:%M:%S")
    print('$$$ Server started at ' + today + ' $$$')
    createTable()
    oscInit()
    schedStart()
    atexit.register(closeOSC)

#http://192.168.1.185:8181/line?serverIP=192.168.1.185&dbTableName=200709
@app.route("/line", methods=['GET'])
def line():
    return render_template('line.html')

#http://192.168.1.185:8181/radar?serverIP=192.168.1.185&dbTableName=200709&id=100
@app.route("/radar", methods=['GET'])
def radar():
    return render_template('radar.html')

#http://192.168.1.185:8181/json?tableName=200531
@app.route("/json", methods=['GET'])
def table():
    return jsonify(fetchTable())

#http://192.168.1.185:8181/?tableName=200531
@app.route("/")
def main():
    tableName = TABLE_NAME_PREFIX + getTableName()
    serverIPport = request.host
    serverIP = serverIPport.split(':')[0]
    tableList = getTableList()
    #print(tableList)
    ips = []
    ips.append('http://' + serverIPport + '/?tableName=' + getTableName())
    ips.append('http://' + serverIPport + '/json?tableName=' + getTableName())
    ips.append('http://' + serverIPport + '/line?serverIP=' + serverIPport + '&dbTableName=' + getTableName())
    ips.append(request.remote_addr)
    return render_template('main.html', readings=fetchTable(), tableName=tableName, ips=ips, info=info, tableList=tableList)

###############################################################################################

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8181, debug=True, use_reloader=False)
