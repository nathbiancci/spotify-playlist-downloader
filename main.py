"""
Spotify Downloader
"""
import os
import re
import csv
import argparse
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


def get_args():
    """
    Parse Arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--spotiuri', action='store', help='Playlist\'s Spotify URI or URL')
    parser.add_argument('-p', '--spotiplaylistId', action='store', help='Playlist\'s Spotify id')
    parser.add_argument('-i', '--client_id', action='store',
                        default=os.environ.get('SPOTIPY_CLIENT_ID'), help='Client\'s id')
    parser.add_argument('-s', '--client_secret', action='store',
                        default=os.environ.get('SPOTIPY_CLIENT_SECRET'), help='Client\'s secret')
    parser.add_argument('-d', '--dir_name', required=False, action='store', default="spotify_playlist", help='Directory name')
    parser.add_argument('-l', '--login', action='store_true',
                        help='Log in with your Spotify account (needed for apps created after Nov 2024)')
    parser.add_argument('-f', '--file', action='store',
                        help='Read tracks from a file instead of Spotify: Exportify CSV or one "Artist - Title" per line')
    my_args = parser.parse_args()

    if my_args.file:
        return my_args
    if not (my_args.spotiuri or my_args.spotiplaylistId):
        parser.error('Need URI, ID or --file')
    if not (my_args.client_id and my_args.client_secret):
        parser.error('Need client id and secret (-i/-s or SPOTIPY_CLIENT_ID/SPOTIPY_CLIENT_SECRET)')

    return my_args


def parse_playlist_id(value):
    """
    Accepts a playlist id, spotify:playlist:<id> URI or open.spotify.com URL
    """
    match = re.search(r'playlist[:/]([A-Za-z0-9]+)', value)
    return match.group(1) if match else value


def read_tracks_file(path):
    """
    Return (artist, title) pairs from an Exportify CSV or an "Artist - Title" text file
    """
    with open(path, newline='', encoding='utf-8-sig') as f:
        first = f.readline()
        f.seek(0)
        if 'Track Name' in first:
            rows = list(csv.DictReader(f))
            artist_col = next(c for c in rows[0] if c.startswith('Artist Name'))
            return [(r[artist_col].replace(';', ', '), r['Track Name']) for r in rows if r['Track Name']]
        pairs = list()
        for line in f:
            line = line.strip()
            if not line:
                continue
            artist, _, title = line.partition(' - ')
            pairs.append((artist, title) if title else ('', artist))
        return pairs


def get_tracks(sp, playlist_id):
    """
    Return every track in the playlist, following pagination
    """
    tracks = list()
    results = sp.playlist_items(playlist_id, additional_types=('track',))
    while results:
        for item in results["items"]:
            track = item.get("track") or item.get("item")
            if track and track.get("name"):
                tracks.append((", ".join(a["name"] for a in track["artists"]), track["name"]))
        results = sp.next(results) if results["next"] else None
    return tracks


def yt_dl(query, filename):
    """
    Search YouTube for the query and download the first result as mp3
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'outtmpl': filename + '.%(ext)s',
        'writethumbnail': True,
        'postprocessors': [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'},
            {'key': 'FFmpegMetadata'},
            {'key': 'EmbedThumbnail'},
        ]}

    with YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download(["ytsearch1:" + query])
        except DownloadError as dl_e:
            print(f"Couldn't download: {dl_e}")
            return False
        return True


def safe_filename(name):
    """
    Strip characters that are invalid in filenames
    """
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()


def download_songs(tracks):
    """
    Download songs
    """
    failed = list()
    print("\nDownloading songs...\n")
    for counter, (song_artist, song_name) in enumerate(tracks, 1):
        wholename = f"{song_artist} - {song_name}" if song_artist else song_name
        filename = safe_filename(wholename)
        print(f"{counter})\t{wholename}")
        if os.path.exists(filename + ".mp3"):
            continue
        if not yt_dl(f"{song_artist.split(', ')[0]} {song_name} audio", filename):
            print(f"This track failed: {wholename}")
            failed.append(wholename)

    if failed:
        print("\nFailed tracks:")
        for name in failed:
            print(f"  {name}")


def main():
    """
    main function
    """
    args = get_args()

    if args.file:
        tracks = read_tracks_file(args.file)
    else:
        playlist_id = parse_playlist_id(args.spotiuri or args.spotiplaylistId)
        if args.login:
            auth = SpotifyOAuth(client_id=args.client_id, client_secret=args.client_secret,
                                redirect_uri="http://127.0.0.1:8888/callback",
                                scope="playlist-read-private playlist-read-collaborative")
        else:
            auth = SpotifyClientCredentials(client_id=args.client_id, client_secret=args.client_secret)
        sp = spotipy.Spotify(auth_manager=auth)
        try:
            tracks = get_tracks(sp, playlist_id)
        except spotipy.SpotifyException as e:
            print(f"\nSpotify refused to list this playlist ({e.http_status}).")
            if not args.login:
                print("Try again with --login to sign in with your Spotify account.")
            print("Or export the playlist to CSV (e.g. https://exportify.net) and run with --file playlist.csv")
            return

    print(f"Found {len(tracks)} tracks")

    os.makedirs(args.dir_name, exist_ok=True)
    os.chdir(args.dir_name)
    download_songs(tracks)


if __name__ == "__main__":
    main()
