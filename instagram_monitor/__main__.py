from instagram_monitor.monitor  import InstagramMonitor
from instagram_monitor.searcher import InstagramSearcher
from urllib.error               import URLError
import argparse
import logging
import requests
import sys
import time


def main():

    parser = argparse.ArgumentParser(
        description=('instagram_monitor scrapes Instagram posts'
                     'from users or hashtags, uses a MongoDB service.'),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--queries', default='queries.txt',
                        help='Path to a file containing users and hashtags to scrape')

    parser.add_argument('--login_user', default=None,
                        help='Instagram login user')
    parser.add_argument('--login_pass', default=None,
                        help='Instagram login password')

    parser.add_argument('--host', default='localhost',
                        help='Address of MongoDB service')
    parser.add_argument('--port', default=27017,
                        help='Port of MongoDB service')
    parser.add_argument('--post_db', default='post',
                        help='Post database name of MongoDB service')
    parser.add_argument('--comments_db', default='comment',
                        help='Comment database name of MongoDB service')

    parser.add_argument('--rich',
                        default=False, action='store_true',
                        help=('Comments have more information'))

    parser.add_argument('--update_days', type=int, default=2,
                        help=('Amount of days old a post must be, to not try '
                              'to search for new comments'))


    parser.add_argument('--loop', '-l',
                        default=False, action='store_true',
                        help=('Search and update periodically'))

    parser.add_argument('--wait_time', type=int, default=2,
                        help=('Hours to wait between iterations of the loop'))


    parser.add_argument('--search', '-s',
                        default=False, action='store_true',
                        help=('Search new posts from queries'))
    parser.add_argument('--update', '-u',
                        default=False, action='store_true',
                        help=('Update posts from queries'))


    parser.add_argument('--export_comments', '-c',
                        default=False, action='store_true',
                        help=('Export post texts to a file.'))
    parser.add_argument('--export_graphs', '-g',
                        default=False, action='store_true',
                        help=('Export mentions graph to a file.'))
    parser.add_argument('--export_info', '-i',
                        default=False, action='store_true',
                        help=('Export general information of each query to a file.'))

    parser.add_argument('--quiet', '-q', default=False, action='store_true',
                        help='No logging info')
    parser.add_argument('--verbose', default='INFO',
                        help=('Logging verbosity level. '
                              'Options: DEBUG INFO WARNING ERROR CRITICAL'))

    args = parser.parse_args()

    if ((args.login_user and args.login_pass is None)
        or (args.login_user is None and args.login_pass)):
        parser.print_help()
        raise ValueError('Must provide login user and password')

    if ((args.host and args.port is None)
        or (args.host is None and args.port)):
        parser.print_help()
        raise ValueError('Must provide host and port of MongoDB service')

    logging.basicConfig(level=(100 if args.quiet else args.verbose),
                        format='%(levelname)-8s %(message)s')


    with open(args.queries) as file_queries:
        queries = file_queries.read().splitlines()

    while True:
        try:
            monitor = InstagramMonitor(args.login_user, args.login_pass,
                                       args.host, args.port,
                                       args.post_db, args.comments_db,
                                       args.rich, args.update_days)
            tasks   = []
            if args.search:
                tasks.append(monitor.search_query)
            if args.update:
                tasks.append(monitor.update_query)
            if args.export_comments:
                tasks.append(monitor.export_comments_query)
            if args.export_graphs:
                tasks.append(monitor.export_graph_query)
            if args.export_info:
                tasks.append(monitor.export_info_query)

            if not tasks:
                tasks = [monitor.search_query,
                         monitor.update_query]

            for task in tasks:
                for query in queries:
                    task(query)

            if not args.loop:
                break

            logging.info('Waiting {} hours.'.format(args.wait_time))
            prev = time.time()
            while True:
                now = time.time()
                if now - prev > args.wait_time*60*60:
                    break
            logging.info('Going back to scrape posts.')

        except URLError as e:
            pass

if __name__ == "__main__":
    main()