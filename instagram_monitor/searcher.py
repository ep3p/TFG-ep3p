from   threading  import Thread
from   queue      import Queue
import instagram_private_api as api
import json
import logging
import requests
import socket
import time
import urllib


class InstagramSearcher(object):

    def __init__(self, username=None, password=None, rich_comments=False,
                       wait_time=30, n_threads=5):
        """

        Args:
            username (str): An Instagram username to login.
            password (str): The password of the Instagram username.
            wait_time (int): Amount of seconds the client will wait when
                errors from too many requests happen.
            n_threads (int): Amount of threads to speed up downloading.

        """
        if username and password:
            self.priv_client = api.Client(
                username, password, auto_patch=True, drop_incompat_keys=True)
        else:
            self.priv_client = None
        self.wait_time  = wait_time
        self.n_threads  = n_threads
        self.rich_comments = rich_comments

    @staticmethod
    def daytosec(days): return days*24*60*60

    def __wait(self, sec=None):
        """Waits an amount of seconds.

        Args:
            sec (int): The amount of seconds to wait.

        """
        if not sec: sec = self.wait_time
        logging.info('Waiting {} seconds.'.format(sec))
        time.sleep(sec)
        logging.info('Waiting ended.')

    def search(self, query: str, unix_date=None, prev_days=0, len_days=None):
        """Searchs Instagram posts of a query from a range of time.

        Retrieves Instagram posts with their comments, from a query,
        a user or a tag, created in a period of time. The period of time will
        start prev_days before the unix_date, and its duration is len_days.

        Args:
            query (str): A tag or a user in Instagram.
            unix_date (int): A date in unix format. It defaults to
                the present date.
            prev_days (int): The amount of days to advance the period of search
                before the unix_date. It defaults to zero.
            len_days (int): The length in days of the period of search.
                It defaults to the amount of days until the present date.

        """
        if not unix_date:
            unix_date = time.time()
        else:
            unix_date = int(unix_date)
        min_date = int(unix_date - InstagramSearcher.daytosec(prev_days))
        if not len_days:
            max_date = int(time.time())
        else:
            max_date = int(min_date + InstagramSearcher.daytosec(len_days))

        logging.info('Searching posts from {} days ago.'.format(
            int((time.time() - min_date)/InstagramSearcher.daytosec(1)*10)/10))
        posts = self.get_id_list(query, min_date, max_date)
        #posts = self.get_id_list2(query, min_date, max_date)
        logging.info('Posts found: {}'.format(len(posts)))
        return self.download_posts(posts)

    def get_id_list(self, query: str, min_date, max_date):
        """Searchs Instagram posts' ids from a query between two dates.

        Searchs Instagram posts using Instagram's GraphQL. The posts are
        from a user, or contain a tag, returns the posts' ids from between
        min_date and max_date.

        Args:
            query (str): A tag or a user in Instagram.
            min_date (int): The lower limit date in unix format.
            max_date (int): The upper limit date in unix format.

        """
        if query[0] == '#':
            type_query = 'tag'
            query      = query[1:]
            query_id   = '17882293912014529&tag_name='
        else:
            type_query = 'user'
            user_info  = requests.get(''.join(['https://www.instagram.com/',
                query, '/?__a=1'])).json()
            query      = user_info['user']['id']
            query_id   = '17880160963012870&id='
        url = ''.join(['https://www.instagram.com/graphql/query/?query_id=',
            query_id, query, '&first=500'])

        json_media     = None
        end_cursor     = None
        repeated       = None
        has_next_page  = None
        last_date      = None
        list_ids       = []

        while True:
            try:
                if type_query == 'user':
                    while (not json_media
                           or (has_next_page
                               and len(edges)
                               and min_date < last_date)):
                        post_url = '&after=' + end_cursor if end_cursor else ''
                        json_media = requests.get(url + post_url).json()
                        if json_media['status'] != 'ok' :
                            raise api.errors.ClientError(
                                'GraphQL request failed.')
                        has_next_page = (json_media['data']['user']
                            ['edge_owner_to_timeline_media']
                            ['page_info']['has_next_page'])
                        end_cursor = (json_media['data']['user']
                            ['edge_owner_to_timeline_media']
                            ['page_info']['end_cursor'])
                        edges = (json_media['data']['user']
                            ['edge_owner_to_timeline_media']['edges'])
                        for edge in edges:
                            post_date = int(edge['node']['taken_at_timestamp'])
                            if min_date < post_date < max_date:
                                list_ids.append(
                                    {'id': edge['node']['id'],
                                     'code': edge['node']['shortcode']})
                        if len(edges):
                            last_date = int(json_media['data']['user']
                                ['edge_owner_to_timeline_media']
                                ['edges'][-1]['node']['taken_at_timestamp'])
                elif type_query == 'tag':
                    while (not json_media
                           or (has_next_page
                               and len(edges)
                               and min_date <= last_date)):
                        post_url = '&after=' + end_cursor if end_cursor else ''
                        json_media = requests.get(url + post_url).json()
                        if json_media['status'] != 'ok' :
                            raise api.errors.ClientError(
                                'GraphQL request failed.')
                        has_next_page = (json_media['data']['hashtag']
                            ['edge_hashtag_to_media']
                            ['page_info']['has_next_page'])
                        end_cursor = (json_media['data']['hashtag']
                            ['edge_hashtag_to_media']
                            ['page_info']['end_cursor'])
                        edges = (json_media['data']['hashtag']
                            ['edge_hashtag_to_media']['edges'])
                        for edge in edges:
                            post_date = int(edge['node']['taken_at_timestamp'])
                            if min_date <= post_date <= max_date:
                                list_ids.append(
                                    {'id': edge['node']['id'],
                                     'code': edge['node']['shortcode']})
                        if len(edges):
                            last_date = int(json_media['data']['hashtag']
                                ['edge_hashtag_to_media']
                                ['edges'][-1]['node']['taken_at_timestamp'])
            except (socket.timeout,
                    urllib.error.URLError,
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError,
                    json.decoder.JSONDecodeError,
                    api.errors.ClientError) as e:
                logging.error(str(e))
                json_media = None
                self.__wait()
            else:            #: If it finishes without any error, returns list.
                return list_ids

    def get_id_list2( self, query: str, min_date, max_date ):
        """Searchs Instagram posts' ids from a query between two dates.

        This version is slower.

        Args:
            query (str): A tag or a user in Instagram.
            min_date (int): The lower limit date in unix format.
            max_date (int): The upper limit date in unix format.

        """
        if query[0] == '#':
            query      = query[1:]
            type_query = 'tag'
            url = ''.join(
            ['https://www.instagram.com/explore/tags/', query, '/?__a=1'])
        else:
            type_query = 'user'
            url = ''.join(['https://www.instagram.com/', query, '/media/'])

        json_media    = None
        last_id       = None
        has_next_page = None
        last_date     = None
        list_ids      = []

        while True:
            try:
                if type_query == 'user':
                    while (not json_media
                           or (has_next_page and min_date < last_date)):
                        post_url = '?max_id=' + last_id if last_id else ''
                        json_media = requests.get(url + post_url).json()
                        has_next_page = json_media['more_available']
                        last_date = int(
                            json_media['items'][-1]['created_time'])
                        last_id = json_media['items'][-1]['id']
                        for item in json_media['items']:
                            if min_date < int(item['created_time']) < max_date:
                                list_ids.append(
                                    {'id': item['id'].split('_')[0],
                                     'code': item['code']})
                elif type_query == 'tag':
                    while (not json_media
                           or (has_next_page and min_date <= last_date)):
                        post_url = '?max_id=' + last_id if last_id else ''
                        json_media = requests.get(url + post_url).json()
                        has_next_page = (json_media['tag']['media']
                            ['page_info']['has_next_page'])
                        last_date = int(json_media['tag']['media']
                            ['nodes'][-1]['date'])
                        last_id = (json_media['tag']['media']
                            ['page_info']['end_cursor'])
                        for node in json_media['tag']['media']['nodes']:
                            if min_date <= int(node['date']) <= max_date:
                                list_ids.append({'id': node['id'],
                                                 'code': node['code']})
            except(socket.timeout,
                   urllib.error.URLError,
                   requests.exceptions.ChunkedEncodingError,
                   requests.exceptions.SSLError,
                   requests.exceptions.ConnectionError,
                   json.decoder.JSONDecodeError) as e:
                logging.error(str(e))
                self.__wait(5)
            else:            #: If it finishes without any error, returns list.
                return list_ids

    def download_posts(self, list_ids: list):
        """Retrieves Instagram posts with their comments from a id list.

        Args:
            list_ids (list[dict]): A list whose elements are dicts with
                the key 'id' or 'code' from an Instagram's post.

        """
        if len(list_ids):
            logging.info('Downloading: {}'.format(len(list_ids)))

            list_posts   = []
            queue_ids    = Queue()
            list_threads = []
            # Creates threads and a queue to process quicker the pool of posts
            for enum_id in enumerate(list_ids):
                queue_ids.put(enum_id)
            for i in range(self.n_threads):
                thread = Thread(target=self.__post_worker,
                                args=(queue_ids,list_posts))
                thread.start()
                list_threads.append(thread)

            queue_ids.join()
            for i in range(self.n_threads):
                queue_ids.put(None)
            for thread in list_threads:
                thread.join(60)

            return list_posts
        else:
            return []

    def __post_worker(self, queue_ids, list_posts):
        """The downloader function for a thread.

        Args:
            queue_ids (Queue): Queue containing post ids enumerated.
            list_posts (list): The list where to save the downloaded posts.

        """
        while True:
            enum_id = queue_ids.get()
            #If a task is None, the thread finishes
            if enum_id is None:
                break
            try:
                if 'id' in enum_id[1] and self.priv_client:
                    post = self.get_post(enum_id[1]['id'])
                elif 'code' in enum_id[1]:
                    post = self.get_post2(enum_id[1]['code'])

                if post['comments']['count']:
                    if self.rich_comments and self.priv_client:
                        comments = self.get_comments2(post['id'])                        
                    else:
                        comments = self.get_comments(post['code'])
                else:
                    comments = []

                list_posts.append({'post': post, 'comments': comments})
                logging.info('Post {:>5}: {:>5} from {:>5} comments.'.format(
                    enum_id[0]+1, post['comments']['count'], len(comments)))

            except api.ClientError as e:
                logging.error('Post {:>5}: {} {}.'.format(
                    enum_id[0]+1, str(e.code), str(e)))
                # If error code is 0 or 429, our IP has made too much requests
                if int(e.code) in (0, 429):
                    queue_ids.put(enum_id)
                    self.__wait()
                # If error code is 400, 404, maybe the post was deleted
                elif int(e.code) in (400, 404):
                    pass
                else:
                    queue_ids.put(enum_id)

            except (socket.timeout,
                    urllib.error.URLError,
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError,
                    json.decoder.JSONDecodeError) as e:
                logging.error(str(e))
                queue_ids.put(enum_id)
                self.__wait(5)
            queue_ids.task_done()

    def get_post(self, id):
        """Retrieves the Instagram post from an id.

        Comments are not included.

        Args:
            id (int, str): An Instagram post id, it can be called 'pk'.

        """
        post         = self.priv_client.media_info(id)['items'][0]
        post['id']   = post.pop('id').split('_')[0]
        post['code'] = post['link'].split('/')[-2]
        return post

    def get_post2(self, code: str):
        """Retrieves the Instagram post from a code.

        This version is slower.

        Args:
            code (str): An Instagram post shortcode.

        """
        post = requests.get(''.join(
            ['https://www.instagram.com/p/', code, '/?__a=1']))
        if not post.ok:
            raise api.errors.ClientError('Web API request failed',
                                         post.status_code)
        else:
            post = post.json()['graphql']['shortcode_media']

        # Patch dict keys
        post['user'] = post.pop('owner')
        post['user']['profile_picture'] = post['user'].pop('profile_pic_url')
        post['comment_threading_enabled'] = post.pop('comments_disabled')
        caption = post.pop('edge_media_to_caption')['edges']
        text = '' if not len(caption) else caption[0]['node']['text']
        post['caption'] = {'text': text, 'from': post['user']}
        post['link'] = ''.join(['https://www.instagram.com/p/', code, '/'])
        post['created_time'] = post.pop('taken_at_timestamp')
        post['images'] = {'standard_resolution': post.pop('dimensions')}
        post['images']['standard_resolution']['url'] = post.pop('display_url')
        post['likes'] = {'count': post.pop('edge_media_preview_like')['count'],
                         'data': []}
        post['comments'] = {
            'count': post.pop('edge_media_to_comment')['count'], 'data': []}
        post['users_in_photo'] = {}
        post['code'] = post.pop('shortcode')

        post.pop('edge_media_to_tagged_user', None)
        post.pop('edge_media_to_sponsor_user', None)
        post.pop('viewer_has_liked', None)
        post['user'].pop('followed_by_viewer', None)
        post['user'].pop('is_private', None)
        post['user'].pop('requested_by_viewer', None)
        post['user'].pop('is_unpublished', None)
        post['user'].pop('blocked_by_viewer', None)
        post['user'].pop('has_blocked_viewer', None)
        post.pop('edge_web_media_to_related_media', None)

        return post

    def get_comments(self, code: str):
        """Retrieves the comments of an Instagram post from a code.

        Args:
            code (str): An Instagram post shortcode.

        """
        query_id = ('https://www.instagram.com/graphql/'
                    'query/?query_id=17852405266163336&shortcode=')
        url = ''.join([query_id, code,'&first=1000'])
        comments      = None
        end_cursor    = None
        list_comments = []

        while (not comments
               or comments['page_info']['has_next_page']):
            post_url = '&after=' + end_cursor if end_cursor else ''
            comments = requests.get(url + post_url)
            if (not comments.ok
                or comments.json()['status'] != 'ok'):
                raise api.errors.ClientError('GraphQL request failed',
                                             comments.status_code)
            else:
                comments = (comments.json()
                    ['data']['shortcode_media']['edge_media_to_comment'])
            end_cursor = comments['page_info']['end_cursor']
            comm_to_add = [edge['node'] for edge in comments['edges']]
            list_comments = comm_to_add + list_comments

        for comment in list_comments:
            comment['created_time'] = comment.pop('created_at')
            comment['from'] = comment.pop('owner')
            comment['from']['profile_picture'] = (
                comment['from'].pop('profile_pic_url'))

        return list_comments

    def get_comments2(self, id, count=1000000):
        """Retrieves the comments of an Instagram post from an id.

        This version is much slower, but returns more information.

        Args:
            id (int, str): An Instagram post id, it can be called 'pk'.

        """
        list_comments = self.priv_client.media_n_comments(id, n=count)
        for comment in list_comments:
            for key in ('pk',
                        'user_id',
                        'created_at',
                        'created_at_utc',
                        'user'):
                comment.pop(key, None)

        return list_comments

'''

Graphql Query IDs

https://www.instagram.com/graphql/query/?query_id=

&first= &after=

user_feed       = 17880160963012870 &id=
tag_feed        = 17882293912014529 &tag_name=
media_comments  = 17852405266163336 &shortcode=
user_following  = 17874545323001329 &id=
user_followers  = 17851374694183129 &id=



# User information
# https://www.instagram.com/[user]/?__a=1

# 20 posts from a user, can use ?max_id=num
# https://www.instagram.com/[user]/media/?__a=1

# Posts containing a tag
# https://www.instagram.com/explore/tags/[tag]/?__a=1

# Information of a single post, limit 29 comments
# https://www.instagram.com/p/[post]/?__a=1

'https://www.instagram.com/{username}/media/?max_id={max_id}';
'https://www.instagram.com/{username}/?__a=1';
'https://www.instagram.com/p/{code}/?__a=1';
'https://www.instagram.com/explore/locations/{facebookLocationId}/?__a=1&max_id={maxId}';
'https://www.instagram.com/explore/tags/{tag}/?__a=1&max_id={end_cursor}';
'https://www.instagram.com/web/search/topsearch/?query={query}';
'''
