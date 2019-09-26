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

mongourl = ""
redishost=""
redisport=""
redispwd=""

# App route to get profile information ---------------------------------------------------------------------
# Input Params : ID
@app.route('/userprofile/userprofileget/<ID>',methods=['GET'])
def userProfileGet(ID):
    try:
        redisdb = redis.Redis(host=redishost,port=redisport,password=redispwd)
        redisdb.ping()
        userInfo = redisdb.get(ID)
        if(userInfo!=None):
            print("UserInfo Data : " + userInfo)
            jData = json.loads(userInfo)
            jData = jData["result"]
            redisdb.expire(ID,1800)
            return jsonify({ 'result':{'status':'true','code':'200','data':{'emailAddr':jData["emailAddr"],'lastName':jData["lastName"],'userId':jData["userId"],'id':jData["id"],'firstName':jData["firstName"] } } })
        else:
            return jsonify({ 'result':{ 'status':'false','code':'500','reason':'No Record Found' } })
    except Exception as ex:
        print("Exception occured on fetching profile information : "+ str(ex))
        jresp = jsonify({"result":{"status":"false","reason":str(ex)}})
        resp = Response(jresp, status=200, mimetype='application/json')
        return resp

# App route to update profile information -------------------------------------------------------------------
# Input Params : ID, FirstName, LastName, Email Address
@app.route('/userprofile/userprofileupdate/<Id>/<firstName>/<lastName>/<emailAddr>',methods=['POST'])
def userProfileUpdate(Id,firstName,lastName,emailAddr):
    try:
        client = MongoClient(mongourl)
        mongodb = client.CubusDBTest
        users = mongodb.users
        query = {"_id":ObjectId(Id)}
        values = {"$set":{"firstName":firstName,"lastName":lastName,"emailAddr":emailAddr}}
        users.update_one(query,values)
        redisdb = redis.Redis(host=redishost,port=redisport,password=redispwd)
        redisdb.ping()
        redisData = []
        redisData = json.dumps({"result":{'id':Id,'firstName':firstName, 'lastName':lastName,'emailAddr':emailAddr}})
        redisdb.setex(Id,1800,redisData)
        client.close()
        return jsonify({"result":{"status":"true","code":"200"}})
    except Exception as ex:
        print("Exception occured in updating profile information : " + str(ex))
        jresp = jsonify({"result":{"status":"false","code":"500","reason":str(ex)}})
        resp = Response(jresp, status=200, mimetype='application/json')
        return resp

@app.route('/profile/healthz',methods=['GET'])
def getUsageParams():
    MongoOK = False
    RedisOK = False
    try:
        zk = KazooClient(hosts=config.ZOOKEEPER_HOST,timeout=5,max_retries=3)
        zk.start()
        zk.stop()

        client = MongoClient(mongourl)
        mongodb = client.CubusDBTest
        print("MongoDB Ok")
        MongoOK = True
        client.close()

        redisdb = redis.Redis(host=redishost,port=redisport,password=redispwd)
        print("MongoDB Ok")
        RedisOK = True

        jresp = jsonify({"result":{"status":"true","code":"200","reason":"None"}})
        resp = Response(jresp, status=200, mimetype='application/json')
        return resp

    except:
        Reason=None
        if MongoOK == False:
            print("Failed to connect to MongoDB")
            Reason = "Failed to connect to MongoDB"
        elif RedisOK == False:
            print("Failed to connect to RedisDB")
            Reason = "Failed to connect to RedisDB"
        else:
            print("Failed to connect to zoo keeper")
            Reason = "Failed to connect to zoo keeper"

        jresp = jsonify({"result":{"status":"false","code":"500","reason":Reason}})
        resp = Response(jresp, status=500, mimetype='application/json')
        return resp

if __name__ == '__main__':
    # Initializing Zookeeper Client----------------------------------------------------------------------------
    try:
        zk = KazooClient(hosts=config.ZOOKEEPER_HOST,timeout=5,max_retries=3)
        zk.start()
        try:
            if zk.exists("/databases/mongodb"):
                mongodata = zk.get("/databases/mongodb")
                mongodata = json.loads(mongodata[0])
                mongourl = mongodata["endpoints"]["url"]
                print("Fetched mongodb config from zookeeper")
            else:
                mongourl = config.MONGODB_HOST
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
            else:
                redishost = config.REDIS_HOST
                redisport = config.REDIS_PORT
                redispwd = config.REDIS_PASSWORD
        except:
            print("Failed to fetch redis config from zookeeper. Reverting to default value")
            redishost = config.REDIS_HOST
            redisport = config.REDIS_PORT
            redispwd = config.REDIS_PASSWORD
        
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
            print("Profileservice configuration updated")
        else:
            print("Zookeeper Creating ProfileService")
            zk.create("/microservices/profileservice",data)
            print("Profileservice configuration created")
        zk.stop()

    except:
        print("Failed to fetch redis config from zookeeper. Reverting to default value")
        redishost = config.REDIS_HOST
        redisport = config.REDIS_PORT
        redispwd = config.REDIS_PASSWORD
    
    
    app.run(debug=config.DEBUG_MODE,host='0.0.0.0',port=config.PORT)
