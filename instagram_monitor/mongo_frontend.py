import datetime
import json
import pymongo
import logging

'''
Code inspired by the book " Mining the Social Web, Matthew A. Russell - 2nd Edition."
It is used to save and/or retreive tweets in a MongoDb database.
'''


#date_str = "Sat Nov 07 22:40:58 +0010 2015"
#d = datetime.strptime(date_str,'%a %b %d %H:%M:%S %z %Y')
#print (d.strftime('%Y-%m-%d-%H'))


def datestr_to_date(datestr):
    return datetime.datetime.strptime(datestr,'%a %b %d %H:%M:%S %z %Y')



class MongoFrontEnd:

    _warehouse_DB = "mulan-warehouse"
    _active_DB = "mulan-active"
    _extra_DB = "mulan-extra"
    _catalog_DB = "mulan-catalog"


    def __init__(self, host, port, db=None, coll=None, username=None, password=None):
        if username and password:
            mongo_uri = 'mongodb://%s:%s@%s:%s/admin' % (username, password, host, port)
            c = pymongo.MongoClient(mongo_uri)
        else:
            c = pymongo.MongoClient(host, port)
        self.__client = c

        if db != None:
            self.change_db(db, coll)


    def change_db(self, db, coll=None):
        # Get a reference to a particular database
        self.__db = self.__client[db]
        if coll is not None:
            self.change_collection(coll)

    def change_collection(self, coll):
        # Reference a particular collection in the database
        self.__collection = self.__db[coll]

    def save_json(self, data):
        r = self.__collection.insert(data) #insert is deprecated
        return r

    def save_one_by_one(self, data):
        #logging.info('saving...{}'.format(len(data)))
        for item in data:
            self.save_json(item)

    def find(self, criteria=None, projection=None):
        # Optionally, use criteria and projection to limit the data that is
        # returned as documented in
        # http://docs.mongodb.org/manual/reference/method/db.collection.find/
        # Consider leveraging MongoDB's aggregations framework for more
        # sophisticated queries.
        coll = self.__collection
        if criteria is None:
            criteria={}
        if projection is None:
            cursor=coll.find(criteria)
        else:
            cursor=coll.find(criteria, projection)
        # Returning a cursor
        return cursor

    def updateMany(self, filter=None, update=None):
        coll = self.__collection
        if filter is None:
            filter={}
        if update is not None:
            doc = coll.update_many(filter, update)
        return doc

    def get_limits(self, atr='id'):
        res_min, res_max = self.get_info_limits(atr)
        if res_min is None or atr not in res_min:
            min_atr = None
            max_atr = None
        else:
            min_atr = res_min[atr]
            max_atr = res_max[atr]
        return (min_atr, max_atr)


    def get_info_limits(self, atr='id'):
        return self.__collection.find_one(sort=[(atr, pymongo.ASCENDING)]), self.__collection.find_one(sort=[(atr, pymongo.DESCENDING)])


    def get_databases(self):
        return [db for db in self.__client.database_names() if db not in ['local', 'admin', 'test']]


    def get_collections(self):
        return [c for c in self.__db.collection_names() if c not in ['system.indexes']]


################################################
#
#   MANAGE COLLECTIONS
#
################################################

    def join_collections(self, source_collection, target_collection=None, source_database=None, target_database=None):
        if target_collection is None:
            if target_database is None:
                return None
            else:
                target_collection = source_collection
        if source_database is not None:
            self.change_db(source_database)
        self.change_collection(source_collection)

        scr_coll = self.__collection
        scr = self.find()
        if target_database is not None:
            self.change_db(target_database)
        self.change_collection(target_collection)
        target_coll = self.__collection
        cnt = 0
        for tweet in scr:
            tid = tweet['id']
            dst = self.find({'id':tid})
            if dst.count() == 0:
                #print ('.', end="")
                cnt += 1
                if False:
                    print (type(tweet))
                    print (tid)
                    print (tweet['_id'])
                    print (dst.count())
                    print ()

                #not exists this 'id' in the target collection
                self.save_json(tweet)
            if dst.count() == 1:
                #print ('.', end="")
                cnt += 1

                #updating this 'id' in the target collection
                target_coll.remove({'id':tid})
                self.save_json(tweet)
            scr_coll.remove({'id':tid})
        return cnt
        #self.change_collection()

    def drop_collection(self, collection):
        self.__db.drop_collection(collection)