from collections                       import Counter
from datetime                          import date
from instagram_monitor.mongo_frontend  import MongoFrontEnd
from instagram_monitor.searcher        import InstagramSearcher as Searcher
from matplotlib                        import pyplot            as plt
from matplotlib                        import dates             as md
from matplotlib.dates                  import MO, TU, WE, TH, FR, SA, SU
from pathlib                           import Path
import logging
import networkx
import re
import time


class InstagramMonitor(object):

    def __init__(self, username=None, password=None,
                 host='localhost', port=27017,
                 post_db='post', comments_db='comment',
                 rich_comments=False, update_days=2):
        """

        Args:
            username (str): An Instagram username to login.
            password (str): The password of the Instagram username.
            host (str): Address where MongoDB is listening.
            port (int): Port where MongoDB is listening.
            post_db (str): Name of database storing Instagram posts.
            comments_db (str): Name of database storing Instagram comments.
            update_days (int): Amount of days old a post must be, to not try
                to search for new comments.

        """
        self.searcher    = Searcher(username, password,
                                    rich_comments=rich_comments)
        self.host        = host
        self.port        = port
        self.post_db     = post_db
        self.comm_db     = comments_db
        self.update_days = update_days
        self.mongo       = MongoFrontEnd(self.host, self.port)

    def __save_query(self, query, posts):
        """Saves Instagram posts from a query.

        Saves in MongoDB in a query collection a list of Instagram posts
        and their comments. If a post is older than self.update_days, it
        is marked as archived.

        Args:
            query (str): The name of the collection where to save posts.
            posts (list[dict]): A list containing posts with their comments.

        """
        if len(posts):
            logging.info('Saving posts: {}'.format(len(posts)))

            ago_sec = time.time() - Searcher.daytosec(self.update_days)
            for post in posts:
                created_time = int(post['post']['created_time'])
                post['post']['archived'] = created_time < ago_sec
                post['post']['not_found'] = False

            post_entry = self.post_db + '-entry'
            comm_entry = self.comm_db + '-entry'

            self.mongo.change_db(post_entry, query)
            self.mongo.save_one_by_one([post['post'] for post in posts])
            self.mongo.join_collections(query, query,
                                        post_entry, self.post_db )
            for post in posts:
                if len(post['comments']):
                    post_id = post['post']['id']
                    self.mongo.change_db(comm_entry, post_id)
                    self.mongo.save_one_by_one(post['comments'])
                    self.mongo.join_collections(post_id, post_id,
                                                comm_entry, self.comm_db)

            logging.info('Saving completed.')

    def search_query(self, query):
        """Searchs new Instagram posts of a query

        Checks in MongoDB previous stored posts of the query, with the oldest
        date searchs new posts. If there aren't previous stored posts,
        defaults to search posts of the last day.

        Args:
            query (str): A tag or a user in Instagram.

        """
        logging.info('Searching \'{}\' new posts.'.format(query))

        self.mongo.change_db(self.post_db, query)
        date_min, date_max = self.mongo.get_limits('created_time')
        if date_max:
            posts = self.searcher.search(query, unix_date=date_max)
        else:
            posts = self.searcher.search(query, prev_days=1)

        self.__save_query(query, posts)

    def update_query(self, query, older_days=None):
        """Updates stored Instagram posts of a query older than n days.

        Checks in MongoDB stored posts of the query marked as not archived and
        their created_time. If older than older_days, updates them. If a post
        can't be found, maybe because the post was deleted, it is marked as
        archived and not found.

        Args:
            query (str): The name of the collection where to update posts.
            older_days (int): Days old the posts must be to be updated.

        """
        if not older_days: older_days = self.update_days

        logging.info(('Updating \'{}\'.').format(query, older_days))

        ago_sec = time.time() - Searcher.daytosec(older_days)
        self.mongo.change_db(self.post_db, query)
        not_archived = self.mongo.find({'archived': False},
                                       {'id': 1, 'code': 1,
                                        'created_time': 1, '_id': 0})

        if not_archived.count():
            posts_to_up = [post for post in not_archived
                                if int(post['created_time']) < ago_sec]
            logging.info('Posts to update: {}.'.format(
                    len(posts_to_up), query))
            if len(posts_to_up):
                uped_posts = self.searcher.download_posts(posts_to_up)
                ids_to_up = [post['id'] for post in posts_to_up]
                uped_ids = [post['post']['id'] for post in uped_posts]
                not_uped_ids = list(set(ids_to_up).difference(uped_ids))
                logging.info(('Posts not found: {}.').format(len(not_uped_ids)))
                self.mongo.updateMany(
                    {'id': {'$in': not_uped_ids}},
                    {'$set': {'archived': True, 'not_found': True}})
                self.__save_query(query, uped_posts)

        logging.info(('Updated  \'{}\'.').format(query, older_days))

    def migrate_query(self, query, migrate_db):
        """Redownloads all posts from a database to the current database.

        Searchs posts from a query in database migrate_db, takes their ids and
        and downloads completely them again from Instagram.

        Args:
            query (str): The name of the collection from where to take ids.
            migrate_db (str): The database from where to take ids.

        """
        logging.info('Migrating posts of {}'.format(query))

        self.mongo.change_db(migrate_db, query)
        posts_cursor = self.mongo.find({},
                                       {'id': 1})
        list_ids = []
        for post in post_cursor:
            list_ids.append({'id' : post['id']})
        list_ids = [list_ids[i:i+500] for i in range(0, len(list_ids), 500)]
        for ids in list_ids:
            posts = self.searcher.download_posts(ids)
            self.__save_query(query, posts)

    def export_comments_query(self, query):
        """Saves in a file all comments from a query collection.

        Saves two files, one for comments, another for captions, each line
        of a file has a comment or caption with the next format:
        post_id \t username \t text_id \t text

        Args:
            query (str): The name of the collection.

        """
        logging.info(('Saving comments from '
                      'query \'{}\' to a file.').format(query) )

        pathcomm = Path(''.join(['exported_comments/', query, '/',
                                 query, '_comments.txt']))
        pathcapt = Path(''.join(['exported_comments/', query, '/',
                                 query, '_captions.txt']))
        pathcomm.parent.mkdir(parents = True, exist_ok = True)
        pathcapt.parent.mkdir(parents = True, exist_ok = True)
        with pathcomm.open( 'w+', encoding = 'utf8' ) as file_comm, \
             pathcapt.open( 'w+', encoding = 'utf8' ) as file_capt:

            list_ids = []
            self.mongo.change_db(self.post_db, query)
            posts = self.mongo.find({},
                                    {'id': 1, 'comments': 1, 'caption': 1})
            for post in posts:
                if (post['caption']
                    and post['caption']['text']
                    and len(post['caption']['text'])):
                    cleaned_text = post['caption']['text'].replace('\n', ' ')
                    file_capt.write(''.join([
                        post['id'], '\t',
                        post['caption']['from']['username'], '\t',
                        post['caption']['id'], '\t',
                        cleaned_text,'\n']))
                if post['comments']['count']:
                    self.mongo.change_db(self.comm_db, post['id'])
                    comments = self.mongo.find({},
                                               {'id': 1, 'text': 1, 'from': 1})
                    for comment in comments:
                        list_ids.append(comment['id'])
                        cleaned_text = comment['text'].replace('\n', ' ')
                        file_comm.write( ''.join([
                            post['id'], '\t',
                            comment['from']['username'], '\t',
                            comment['id'], '\t',
                            cleaned_text, '\n']))
            logging.info('Saved {:>8} comments, {} repeated ids.'.format(
                len(list_ids), len(list_ids) - len(set(list_ids))))

    def export_graph_query(self, query, op_mentioned=False):
        """Saves a graph file representing mentions in comments.

        Creates a graph file using all the comments from a query,
        nodes represent usernames, and edges represent mentions
        from a user to another. If op_mentioned is True,
        any comment will count as a mention to the user who created the post,
        although he is not mentioned in the text.

        Args:
            query (str): The name of the collection.
            op_mentioned (bool): Represents if any comment must count
                as a mention to the user who created the post.
        """
        logging.info('Creating graph of query \'{}\'.'.format(query))

        # The pattern to find Instagram user mentions,
        # example: 'dsdf @ds54d.sds.dd klfg' -> 'ds54d.sds.dd'.
        pattern = re.compile('(?:@)([A-Za-z0-9_]'
                                   '(?:(?:[A-Za-z0-9_]|(?:\.(?!\.))){0,28}'
                                      '(?:[A-Za-z0-9_]))?)')

        self.mongo.change_db(self.post_db, query)
        posts = self.mongo.find({},
                                {'id': 1, 'user': 1, 'caption': 1,
                                 'comments': 1, 'usertags': 1})
        list_texts = []
        for post in posts:
            if (post['caption']
                and post['caption']['text']
                and len(post['caption']['text'])):
                list_texts.append(
                    {'username': post['caption']['from']['username'],
                     'text': post['caption']['text']})
            if post['comments']['count']:
                self.mongo.change_db( self.comm_db, post['id'])
                comments = self.mongo.find({},
                                           {'id': 1, 'text': 1, 'from': 1})
                for comment in comments:
                    list_texts.append(
                        {'username': comment['from']['username'],
                         'text': comment['text'],
                         'op': post['user']['username']})

        graph = networkx.DiGraph()
        for text in list_texts:
            mentioned_users = pattern.findall(text['text'])
            for user in mentioned_users:
                graph.add_edge(text['username'], user)
            if op_mentioned and 'op' in text:
                graph.add_edge(text['username'], text['op'])

        path = Path('graphs/')
        path.mkdir(parents = True, exist_ok = True)
        networkx.drawing.nx_pydot.write_dot(graph,
            ''.join(['graphs/', query, '-', str(int(time.time())), '.dot']))

        logging.info( 'Created \'{}\' graph:'.format(query))
        logging.info( '{:>8} nodes.'.format(graph.order()))
        logging.info( '{:>8} edges.'.format(graph.size()))

    def export_info_query(self, query):
        """Saves in a file general information from a query collection.

        Saves two files, one about post, comments and likes information, 
        and another is a plot of the number of posts per day of the query.

        Args:
            query (str): The name of the collection.

        """
        logging.info(('Saving general information from '
                      'query \'{}\' to a file.').format(query) )

        pathinfo = Path(''.join(['exported_info/', query, '/',
                                 query, '_info.txt']))
        pathinfo.parent.mkdir(parents = True, exist_ok = True)
        with pathinfo.open( 'w+', encoding = 'utf8' ) as file_comm:
            self.mongo.change_db(self.post_db, query)
            posts = self.mongo.find({},
                                    {'id': 1, 'created_time': 1,
                                     'comments': 1, 'likes': 1})
            total_posts = posts.count()
            total_comms = 0
            total_likes = 0
            post_dates = Counter()
            for post in posts:
                post_dates.update(
                    [date.fromtimestamp(int(post['created_time']))])
                total_comms += post['comments']['count']
                total_likes += post['likes']['count']
            result = ('{:<20} {:>10.3f}\n'*3).format(
                'Total posts:', total_posts,
                'Average likes:', total_likes/total_posts,
                'Average comments:', total_comms/total_posts)
            file_comm.write(result)
            x, y = zip(*sorted(post_dates.items()))
            fig, ax = plt.subplots()
            ax.plot_date(x, y, fmt='r-')
            days = md.DayLocator()
            mons = md.WeekdayLocator(byweekday=MO)
            monsFmt = md.DateFormatter('%Y-%m-%d')
            ax.xaxis.set_minor_locator(days)
            ax.xaxis.set_major_locator(mons)
            ax.xaxis.set_major_formatter(monsFmt)
            #ax.set_xlim([date(2017, 6, 7), date(2017, 7, 4)])
            ax.format_xdata = md.DateFormatter('%Y-%m-%d')

            ax.grid(True)
            fig.autofmt_xdate()
            plt.suptitle(query + ' posts per day',
                         size=20, family='serif')
            plt.savefig(
                ''.join(['exported_info/', query, '/',
                         query, '_post_dates.png']),
                bbox_inches='tight')
            plt.close()
            logging.info('Saved general information.')
