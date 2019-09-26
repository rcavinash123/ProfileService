from flask import Flask
from flask import jsonify
from flask import request
from flask_pymongo import PyMongo
from pymongo import MongoClient
import urllib
import redis
import json
from bson.objectid import ObjectId
import psutil
from kazoo.client import KazooClient
import config
import logging
from flask import Response

logging.basicConfig()

app = Flask(__name__)
mongodb_ok = False
redis_ok = False

# App route to get profile information ---------------------------------------------------------------------
# Input Params : ID
@app.route('/userprofile/userprofileget/<ID>',methods=['GET'])
def userProfileGet(ID):
    try:
        redisdb.ping()
        userInfo = redisdb.get(ID)
        if(userInfo!=None):
            userInfo = userInfo.decode('utf-8')
            redisdb.expire(ID,1800)
            return jsonify(userInfo)
        else:
            return jsonify("{ 'result':{ 'status':'false','reason':'No Record Found' } }")
    except Exception as ex:
        print("Error : "+ str(ex))
        return("Failed to connect to redis")

# App route to update profile information -------------------------------------------------------------------
# Input Params : ID, FirstName, LastName, Email Address
@app.route('/userprofile/userprofileupdate/<Id>/<firstName>/<lastName>/<emailAddr>',methods=['POST'])
def userProfileUpdate(Id,firstName,lastName,emailAddr):
    try:
        users = mongodb.users
        query = {"_id":ObjectId(Id)}
        values = {"$set":{"firstName":firstName,"lastName":lastName,"emailAddr":emailAddr}}
        users.update_one(query,values)
        redisdb.ping()
        redisData = []
        redisData = json.dumps({"result":{'id':Id,'firstName':firstName, 'lastName':lastName,'emailAddr':emailAddr}})
        redisdb.setex(Id,1800,redisData)
        return json.dumps({"result":{"Success":"true"}})
    except Exception as ex:
        print("Error : " + ex)
        return("Failed to update profile information")

@app.route('/profile/healthz',methods=['GET'])
def getUsageParams():
    try:
        zk = KazooClient(hosts=config.ZOOKEEPER_HOST,timeout=5,max_retries=3)
        zk.start()
        data = json.dumps({
                "profileget":{
                    "url":"http://profileservice.default.svc.cluster.local:4003/userprofile/userprofileget/"
                },
                "profileupdate":{
                    "url":"http://profileservice.default.svc.cluster.local:4003/userprofile/userprofileupdate/"
                },
                "healthcheck":{
                    "url":"http://profileservice.default.svc.cluster.local:4003/auth/healthz"
                }
            })

        if zk.exists("/microservices/profileservice"):
            print("Zookeeper Updating Profileservice")
            zk.set("/microservices/profileservice",data)
            zk.stop()
            print("Profileservice configuration updated")
        else:
            print("Zookeeper Creating ProfileService")
            zk.create("/microservices/profileservice",data)
            print("Profileservice configuration created")
            zk.stop()
        if mongodb_ok == True and redis_ok == True:
            print("Connectivity to the zoo keeper succeeded")
            jresp = json.dumps({"status":"success","reason":"none"})
            resp = Response(jresp, status=200, mimetype='application/json')
            zk.stop()
            return resp
        else:
            print("Failed to connect to mongodb or redis")
            jresp = json.dumps({"status":"fail","reason":"Failed to connect to mongo/redis"})
            resp = Response(jresp, status=500, mimetype='application/json')
            zk.stop()
            return resp
    except:
        print("Failed to connect to zoo keeper")
        jresp = json.dumps({"status":"fail","reason":"Failed to connect to zookeeper"})
        resp = Response(jresp, status=500, mimetype='application/json')
        return resp

if __name__ == '__main__':
    # Initializing Zookeeper Client----------------------------------------------------------------------------
    zk = KazooClient(hosts=config.ZOOKEEPER_HOST,timeout=5,max_retries=3)
    mongourl = ""
    redishost=""
    redisport=""
    redispwd=""
    zk.start()
    try:
        if zk.exists("/databases/mongodb"):
            mongodata = zk.get("/databases/mongodb")
            mongodata = json.loads(mongodata[0])
            mongourl = mongodata["endpoints"]["url"]
            print("Fetched mongodb config from zookeeper")
    except:
        print("Failed to fetch mongodb config from zookeeper. Reverting to default value")
        mongourl = config.MONGODB_HOST
    
    try:
        if zk.exists("/databases/redisdb"):
            redisdata = zk.get("/databases/redisdb")
            redisdata = json.loads(redisdata[0])
            redishost = redisdata["endpoints"]["host"]
            redisport = redisdata["endpoints"]["port"]
            redispwd = redisdata["endpoints"]["password"]
            print("Fetched redisdb config from zookeeper")
    except:
        print("Failed to fetch redis config from zookeeper. Reverting to default value")
        redishost = config.REDIS_HOST
        redisport = config.REDIS_PORT
        redispwd = config.REDIS_PASSWORD
    # Intializing MongoDB Client ------------------------------------------------------------------------------
    zk.stop()
    try:
        client = MongoClient(mongourl)
        mongodb = client.CubusDBTest
        mongodb_ok = True
        print("Mongo DB OK")
    except Exception as ex:
        print("Exception occured while connecting to mongo db error : " + str(ex))

# Initializing Redis Client --------------------------------------------------------------------------------
    try:
        redisdb = redis.Redis(host=redishost,port=redisport,password=redispwd)
        redis_ok = True
        print("Redis OK")
    except Exception as ex:
        print("Exception occured while connecting to redis db : " + str(ex))
    
    app.run(debug=config.DEBUG_MODE,host='0.0.0.0',port=config.PORT)
