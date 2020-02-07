#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import json
import os
from os import path
import argparse
import re

"""
HOW TO SET THIS UP
1) Enabled Emby Webhooks Plguin (You will need Supporter Status)
2) set URL to http://<IPAddress>:8080/webhook
3) Enable all webhook events for the above URL
4) Ensure you have rclone cache mount using RC, add "--rc --rc-addr=127.0.0.1:5572" to its command line
5) Run it! You should see logging for when you unpause a video or play a video that it is caching something

If you see something like:
INFO:root:Caching File: Media/Anime/Darwin's Game/Season 1/Darwin's Game - S01E01 - First Game WEBDL-1080p.mkv

Then it worked!

If you see something like:
INFO:root:{
        "status": {
                "drive/Media/Anime/Darwin's Game/Season 1/Darwin's Game - S01E01 - First Game WEBDL-1080p.mkv": {
                        "Error": "object not found",
                        "FetchedChunks": 0
                }
        }
}

Then you need to fix your pathing replacement using the --map argument.
"""

parser = argparse.ArgumentParser()
parser.add_argument('-m', '--map', required = True, help = 'Map an Emby path to a Rclone path. Separate the pair with colon, and use a comma to separate more than one pair. Example: "/localpath/movies:gdrivepath/Movies,//192.168.1.191/drive:/"')
parser.add_argument('-i', '--ip', default = '127.0.0.1', help = 'IP address to listen for webhooks from Emby. Defaults to localhost (127.0.0.1).')
parser.add_argument('-p', '--port', default = '8080', help = 'TCP port to listen for webhooks from Emby. Defaults to 8080.')
parser.add_argument('-r', '--rc', default = '127.0.0.1:5572', help = 'Rclone cache rc address. Defaults to 127.0.0.1:5572')
parser_args = parser.parse_args()

# Creates a dictionary of Emby->Rclone path mappings.
rclone_mapping = dict(item.split(':') for item in parser_args.map.split(','))


def is_json(myjson):
  try:
    json_object = json.loads(myjson)
  except ValueError as e:
    return False
  return True


class S(BaseHTTPRequestHandler):
  def _set_response(self):
    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.end_headers()

  def do_GET(self):
    logging.info('GET request,\nPath: %s\nHeaders:\n%s\n', str(self.path), str(self.headers))
    self._set_response()
    self.wfile.write('GET request for {}'.format(self.path).encode('utf-8'))

  def do_POST(self):
    content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
    post_data = self.rfile.read(content_length) # <--- Gets the data itself

    self._set_response()
    for line in post_data.splitlines():
      if is_json(line):
        task = json.loads(line)
        logging.info('Event: ' + task['Event'])
        if task['Event'] == 'playback.unpause' or task['Event'] == 'playback.start':
          logging.info('Emby Path: ' + task['Item']['Path'])
          filepath = ''
          for embypath in rclone_mapping:
            if re.match(embypath, task['Item']['Path']):
              filepath = re.sub(embypath, rclone_mapping[embypath], task['Item']['Path'])

          logging.info('Caching Rclone Path: ' + filepath)
          p = os.popen('rclone rc --rc-addr=' + parser_args.rc + '  cache/fetch chunks=: file="' + filepath + '"')
          logging.info(p.read())
    self.wfile.write('POST request for {}'.format(self.path).encode('utf-8'))

def run(server_class=HTTPServer, handler_class=S, port=int(parser_args.port)):
  logging.basicConfig(level=logging.INFO)
  server_address = ('', port)
  httpd = server_class(server_address, handler_class)
  logging.info('Starting httpd...\n')
  try:
    httpd.serve_forever()
  except KeyboardInterrupt:
    pass
  httpd.server_close()
  logging.info('Stopping httpd...\n')

if __name__ == '__main__':
  from sys import argv

  if len(argv) == 2:
    run(port=int(argv[1]))
  else:
    run()

