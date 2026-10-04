"""
Spotify Downloader
"""
import os
import re
import argparse
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
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
    my_args = parser.parse_args()

    if not (my_args.spotiuri or my_args.spotiplaylistId):
        parser.error('Need URI or ID')
    if not (my_args.client_id and my_args.client_secret):
        parser.error('Need client id and secret (-i/-s or SPOTIPY_CLIENT_ID/SPOTIPY_CLIENT_SECRET)')

    return my_args


def parse_playlist_id(value):
    """
    Accepts a playlist id, spotify:playlist:<id> URI or open.spotify.com URL
    """
    match = re.search(r'playlist[:/]([A-Za-z0-9]+)', value)
    return match.group(1) if match else value


def get_tracks(sp, playlist_id):
    """
    Return every track in the playlist, following pagination
    """
    tracks = list()
    results = sp.playlist_items(playlist_id, additional_types=('track',))
    while results:
        for item in results["items"]:
            track = item.get("track")
            if track and track.get("name"):
                tracks.append(track)
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
    for counter, track in enumerate(tracks, 1):
        song_artist = ", ".join(a["name"] for a in track["artists"])
        song_name = track["name"]
        wholename = f"{song_artist} - {song_name}"
        filename = safe_filename(wholename)
        print(f"{counter})\t{wholename}")
        if os.path.exists(filename + ".mp3"):
            continue
        if not yt_dl(f"{track['artists'][0]['name']} {song_name} audio", filename):
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
    playlist_id = parse_playlist_id(args.spotiuri or args.spotiplaylistId)

    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=args.client_id,
                                                               client_secret=args.client_secret))
    tracks = get_tracks(sp, playlist_id)

    os.makedirs(args.dir_name, exist_ok=True)
    os.chdir(args.dir_name)
    download_songs(tracks)


if __name__ == "__main__":
    main()
