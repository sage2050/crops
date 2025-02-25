from colorama import Fore

from api import RED, OPS
from args import get_args
from config import Config
from downloader import get_torrent_id, get_torrent_url, get_torrent_filepath, download_torrent
from filesystem import create_folder, get_files, get_filename
from parser import get_torrent_data, get_infohash, get_new_hash, get_source, save_torrent_data
from progress import Progress
from urllib.parse import urlparse

def gen_infohash_set(files):
    infohash_set = set()
    for file in files:
        torrent_data = get_torrent_data(file)
        infohash = get_infohash(torrent_data)
        infohash_set.add(infohash)
    return infohash_set

ops_sources = (b"OPS", b"APL", b"")
red_sources = (b"RED", b"PTH", b"")

ops_announce = "home.opsfet.ch"
red_announce = "flacsfor.me"

def main():
    create_folder(args.folder_out)
    local_torrents = get_files(args.folder_in)
    dest_torrents = get_files(args.folder_out)
    p = Progress(len(local_torrents))
    if args.download:
        p.generated.name = "Downloaded for cross-seeding"

    in_infohash_set = gen_infohash_set(local_torrents)
    out_infohash_set = gen_infohash_set(dest_torrents)

    for i, torrent_path in enumerate(local_torrents, 1):
        filename = get_filename(torrent_path)
        print(f"{i}/{p.total}) {filename}")

        try:
            torrent_data = get_torrent_data(torrent_path)
        except AssertionError:
            p.error.print("Decoding error.")
            continue

        source = get_source(torrent_data)
        if source is None:
            try:
                announce_data = torrent_data[b'announce']
                announce_url = urlparse(announce_data)
                announce_loc = announce_url.netloc.decode('utf-8')
            except:
                p.error.print("No source flag or valid announce url found.")
                continue
            
            if announce_loc == ops_announce:
                api = red
                new_sources = red_sources
            elif announce_loc == red_announce:
                api = ops
                new_sources = ops_sources
            else:
                p.skipped.print(f"Skipped: Torrent announces to {announce_loc} and source flag is absent.")
                continue
        else:
            if source in ops_sources:
                api = red
                new_sources = red_sources
            elif source in red_sources:
                api = ops
                new_sources = ops_sources
            else:
                p.skipped.print(f"Skipped: Source flag is {source.decode('utf8')}.")
                continue

        found_infohash_match = False
        for new_source in new_sources:
            new_hash = get_new_hash(torrent_data, new_source)
            if new_hash in in_infohash_set:
                p.already_exists.print(
                    f"A match was found in the input directory with source {new_source.decode('utf-8')}."
                )
                found_infohash_match = True
                break
            if new_hash in out_infohash_set:
                p.already_exists.print(
                    f"A match was found in the output directory with source {new_source.decode('utf-8')}."
                )
                found_infohash_match = True
                break

        if found_infohash_match:
            continue

        for i, new_source in enumerate(new_sources, 0):
            new_hash = get_new_hash(torrent_data, new_source)
            torrent_details = api.find_torrent(new_hash)
            status = torrent_details["status"]

            try:
                new_source = new_source.decode("utf-8")
            except:
                new_source = "empty"

            known_errors = ("bad hash parameter", "bad parameters")

            torrent_successful = False
            if status == "success":
                torrent_filepath = get_torrent_filepath(
                    torrent_details, api.sitename, args.folder_out
                )
                torrent_id = get_torrent_id(torrent_details)

                if args.download:
                    download_torrent(api, torrent_filepath, torrent_id)

                    p.generated.print(
                        f"Found with source {new_source} "
                        f"and downloaded as '{get_filename(torrent_filepath)}'."
                    )
                else:
                    torrent_data[b"announce"] = api.announce_url
                    torrent_data[b"comment"] = get_torrent_url(api.site_url, torrent_id)

                    save_torrent_data(torrent_filepath, torrent_data)

                    p.generated.print(
                        f"Found with source {new_source} "
                        f"and generated as '{get_filename(torrent_filepath)}'."
                    )
                torrent_successful = True
                break  # Skip the other source hash checks if successful
            elif torrent_details["error"] in known_errors:
                if i == 1:
                    p.not_found.print(
                        f"Not found with sources "
                        f"{', '.join(x.decode('utf-8') or 'empty' for x in new_sources)}.",
                        add=False,
                    )
            else:
                p.error.print(
                    f"Unexpected error while using source {new_source}"
                    f"{Fore.LIGHTBLACK_EX}:\n{str(torrent_details)}"
                )

        if not torrent_successful:
            p.not_found.increment()

    print(p.report())


if __name__ == "__main__":
    args = get_args()
    config = Config()

    red = RED(config.red_key)
    ops = OPS(config.ops_key)

    main()
