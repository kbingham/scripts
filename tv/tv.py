#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tv

Usage:
  tv download
  tv archive [--keep] [--recent] [<filename>...]
  tv list

"""
import requests
from bs4 import BeautifulSoup
import json
import youtube_dl
import pickle
import os
from string import ascii_letters, digits
from shutil import move
from docopt import docopt
import yaml
from utils import bprint
import arrow


def mkdir(d):
    if not os.path.isdir(d):
        os.mkdir(d)


class Show(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.ydl = youtube_dl.YoutubeDL({'outtmpl': u'/tmp/%(id)s', "quiet": True, "progress_hooks": [self._progress]})
        self.session = requests.Session()

    def playlist(self):
        return []

    def _getURL(self, url, headers={}):
        html = self.session.get(url, headers=headers).text
        parsed = BeautifulSoup(html, "lxml")
        # self.session.headers.update({"Referer": url})
        return (html, parsed)

    def _getFilename(self, s):
        s = s.replace("/", "-")
        valid_chars = "-_.() %s%s" % (ascii_letters, digits)
        return ''.join(c for c in s if c in valid_chars)

    def _progress(self, d):
        if d["status"] == "downloading":
            s = ' '.join([d["_" + i + "_str"] for i in ["percent", "speed", "total_bytes", "total_bytes_estimate", "eta"] if "_" + i + "_str" in d])
            s = s.ljust(60)
            print(s, end="\r")

    def _getInfo(self, url, db):
        if url not in db["urls"]:
            ydl_info = self.ydl.extract_info(url, download=False)
            info = {
                "ydl_id": ydl_info["id"],
                "ext": ydl_info["ext"],
                "status": None,
                "filename": self.name + "/" + self._getFilename("{}-{}.{}".format(ydl_info["upload_date"],
                                                                                  ydl_info["title"],
                                                                                  ydl_info["ext"]))

            }
            # Save in DB
            db["urls"][url] = info
            return info
        else:
            return db["urls"][url]

    # Fetch one
    def fetch_one(self, p, db, path):
        url = p["url"]
        info = self._getInfo(url, db)
        if info["status"] != "seen" and not os.path.isfile(path + info["filename"]):
            # Download
            print(p["title"])
            print(url)
            print("Download...")
            self.ydl.extract_info(url, download=True)
            for s in ["", "." + info["ext"], ".mkv"]:  # Bug in youtube-dl
                filename = "/tmp/" + info["ydl_id"] + s
                if os.path.isfile(filename):
                    move(filename, path + info["filename"])
                    break
            print("")
        db["urls"][url] = info

    # Fetch all
    def fetch(self, db, path, limit=3):
        bprint("Fetching {}".format(self.name))
        mkdir(path + self.name + "/")
        for p in self.playlist()[:limit]:
            self.fetch_one(p, db, path)


# Espace 2
class Espace2(Show):
    def __init__(self, name, **kwargs):
        # id, name
        super().__init__(name)
        self.url = "http://www.rts.ch/play/radio/emission/{}?id={id}".format(**kwargs)

    def playlist(self):
        html, parsed = self._getURL(self.url)
        teasers = parsed.select(".teaserSegmentList")
        return teasers


# YouTube
class YouTube(Show):
    def __init__(self, name, **kwargs):
        super().__init__(name)
        self.url = "https://www.youtube.com/feeds/videos.xml"
        if "user" in kwargs.keys():
            self.url = self.url + "?user={user}".format(**kwargs)
        else:
            self.url = self.url + "?channel_id={channel}".format(**kwargs)
        self.keyword = None
        if "keyword" in kwargs.keys():
            self.keyword = kwargs["keyword"]

    def playlist(self):
        html, parsed = self._getURL(self.url)
        results = []
        for e in parsed.findAll("entry"):
            title = e.find("title").contents[0]
            if self.keyword is None or self.keyword in title:
                results.append({"url": e.find("link")["href"], "title": title})
        return results


class RSS(Show):
    def __init__(self, name, **kwargs):
        super().__init__(name)
        self.url = kwargs["url"]

    def playlist(self):
        html, parsed = self._getURL(self.url)
        l = []
        for e in parsed.findAll("item"):
            try:
                l.append({"url": e.find("enclosure")["url"], "title": e.find("title").text})
            except:
                continue
        return l


class TheAtlantic(Show):
    def __init__(self, name, **kwargs):
        super().__init__(name)
        self.base = "https://www.theatlantic.com/"
        self.url = "{}video/series/{}/".format(self.base, kwargs["series"])

    def playlist(self):
        l = []
        page = 1
        while True:
            if page == 1:
                html, parsed = self._getURL(self.url)
            else:
                url = self.url + "?page={}".format(page)
                html, _ = self._getURL(url, {"X-Requested-With": "XMLHttpRequest"})
                if "html>" in html:  # End of pages
                    break
                html = json.loads(html)["content"]
                parsed = BeautifulSoup(html, "lxml")
            for e in parsed.select(".grid-video"):
                l.append({"url": self.base + e.find("a")["href"].strip(), "title": e.find("h2").text.strip()})
            page = page + 1
        return l


# RTSPlay
class RTSPlay(Show):
    def __init__(self, name, **kwargs):
        super().__init__(name)
        self.showid = kwargs["showid"]
        self.type = kwargs["type"]

    def playlist(self):
        url = "http://www.rts.ch/play/{}/episodesfromshow?id={}&pageNumber=1&layout=json".format(self.type, self.showid)
        html, parsed = self._getURL(url)
        emissions = json.loads(html)["episodes"]
        emissions.sort(key=lambda x: x["id"], reverse=True)
        emissions = emissions[:3]
        return [
            {
                "url": "http://www.rts.ch" + e["assets"][0]["url"],
                "title": e["title"]
            }
            for e in emissions
        ]


def archive(filenames, keep, recent, db, path):
    bprint("Archive")
    # Add recently accessed files
    if recent:
        for d in os.walk(path):
            for f in d[2]:
                filename = "/".join([d[0], f])
                delta = arrow.now() - arrow.get(os.stat(filename).st_atime)
                delta = delta.total_seconds() / 60
                if delta < 180:
                    filenames.append(filename)
    for filename in filenames:
        filename = filename.replace(path, "")
        if filename is not None:
            # Look for file in database
            v = [(k, v) for k, v in db["urls"].items() if v["filename"] == filename]
            if len(v) == 0:
                exit("Not found")
            k, v = v[0]
            if v["status"] == "seen":
                print("Already archived")
            db["urls"][k]["status"] = "seen"
        # Clean files
        for _, u in db["urls"].items():
            fullpath = path + u["filename"]
            if u["status"] == "seen" and os.path.isfile(fullpath):
                if keep:
                    keepPath = path + "keep/"
                    showPath = keepPath + u["filename"].split("/")[0] + "/"
                    mkdir(keepPath)
                    mkdir(showPath)
                    move(fullpath, keepPath + u["filename"])
                    print("Moved to keep/")
                else:
                    os.remove(fullpath)
                    print("Removed", u["filename"])
    print("Done")


def listShow(s, db):
    bprint(s.name)
    l = list(filter(lambda x: x["filename"].split("/")[0] == s.name, db["urls"].values()))
    for cat in [[None, "New"], ["seen", "Archived"]]:
        print(cat[1])
        for ll in filter(lambda x: x["status"] == cat[0], l):
            print("\t", ll["filename"])
    return


def main():
    arguments = docopt(__doc__)
    with open(os.getenv("HOME") + "/.config/tv.yaml", "r") as f:
        config = yaml.load(f)
    shows = []
    for s in config["shows"]:
        c = globals()[s["type"]]
        shows.append(c(s["name"], **s["parameters"]))
    # Paths
    path = config["path"]
    dbFile = config["dbPath"] + "tv.db"
    if os.path.isfile(dbFile):
        db = pickle.load(open(dbFile, "rb"))
    else:
        db = {"urls": {}}
    if arguments["download"]:
        for s in shows:
            try:
                s.fetch(db, path, 10)
            except Exception as e:
                print("Error:", e)
    # List
    elif arguments["list"]:
        for s in shows:
            listShow(s, db)
    # Archive
    elif arguments["archive"]:
        archive(arguments["<filename>"], arguments["--keep"], arguments["--recent"], db, path)
    pickle.dump(db, open(dbFile, "wb"))


if __name__ == '__main__':
    main()
