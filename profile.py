from flask import Flask
from flask import jsonify
from flask import request
from flask import Response
from kazoo.client import KazooClient
import json
import requests
import random
from requests.exceptions import HTTPError
import config
import logging

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
        userInfo = redisdb.get(ID).decode('utf-8')
        redisdb.expire(ID,1800)
        return jsonify(userInfo)
    except Exception as ex:
        print("Error : "+ex)
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

@app.route('/auth/healthz',methods=['GET'])
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
    # Intializing MongoDB Client ------------------------------------------------------------------------------
    try:
        client = MongoClient(config.MONGODB_HOST)
        mongodb = client.CubusDBTest
        mongodb_ok = True
        print("Mongo DB OK")
    except Exception as ex:
        print("Exception occured while connecting to mongo db error : " + str(ex))

# Initializing Redis Client --------------------------------------------------------------------------------
    try:
        redisdb = redis.Redis(host=config.REDIS_HOST,port=config.REDIS_PORT,password=config.REDIS_PASSWORD)
        redis_ok = True
        print("Redis OK")
    except Exception as ex:
        print("Exception occured while connecting to redis db : " + str(ex))
    app.run(debug=config.DEBUG_MODE,host='0.0.0.0',port=config.PORT)
