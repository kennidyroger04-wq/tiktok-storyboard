"""Download one public TikTok video without loading browser cookies or user config."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--deps', type=Path, help='Directory containing yt_dlp')
    args = parser.parse_args()
    url = urlparse(args.url)
    host = (url.hostname or '').lower()
    if url.scheme != 'https' or not (host == 'tiktok.com' or host.endswith('.tiktok.com')) or url.username or url.password or url.port not in (None, 443):
        parser.error('Use an HTTPS TikTok URL without credentials or a custom port.')
    deps = args.deps or Path(__file__).resolve().parents[1] / '.runtime'
    if deps.is_dir():
        sys.path.insert(0, str(deps.resolve()))
    try:
        import yt_dlp
        from yt_dlp.version import __version__
    except ImportError:
        parser.exit(2, 'Missing yt-dlp. See references/download.md for setup.\n')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    match = re.fullmatch(r'/@[^/]+/video/(\d+)/?', url.path)
    if match:
        cached_manifest = output / (match[1] + '.download.json')
        if cached_manifest.is_file():
            try:
                cached = json.loads(cached_manifest.read_text(encoding='utf-8'))
                cached_media = Path(cached['file']).resolve()
                if cached_media.parent == output and cached_media.stem == match[1] and cached_media.is_file():
                    with cached_media.open('rb') as stream:
                        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                    if digest == cached['sha256'] and cached['id'] == match[1]:
                        cached['reused_verified_local_file'] = True
                        print(json.dumps(cached, ensure_ascii=False, indent=2))
                        return 0
            except (ValueError, KeyError, OSError):
                pass

    class Logger:
        def debug(self, message):
            pass
        def warning(self, message):
            print('Downloader warning: ' + message, file=sys.stderr)
        def error(self, message):
            print('Downloader error: ' + message, file=sys.stderr)

    options = {
        'noplaylist': True, 'playlistend': 1,
        'format': 'best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]',
        'outtmpl': str(output / '%(id)s.%(ext)s'),
        'cachedir': False, 'overwrites': False,
        'socket_timeout': 20, 'retries': 2, 'extractor_retries': 1,
        'quiet': True, 'noprogress': True, 'logger': Logger(),
        'writethumbnail': False, 'writeinfojson': False,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(args.url, download=True)
            if not info or info.get('_type') in ('playlist', 'multi_video'):
                raise RuntimeError('Expected a single video.')
            media = Path(downloader.prepare_filename(info))
            if not media.is_file() or media.stat().st_size < 1024:
                raise RuntimeError('No usable media file was downloaded.')
            with media.open('rb') as stream:
                checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
            result = {
                'status': 'downloaded_not_decoded', 'yt_dlp_version': __version__,
                'source_url': args.url, 'webpage_url': info.get('webpage_url'),
                'id': info.get('id'), 'uploader': info.get('uploader'),
                'description': info.get('description'), 'duration': info.get('duration'),
                'width': info.get('width'), 'height': info.get('height'),
                'fps': info.get('fps'), 'format_id': info.get('format_id'),
                'vcodec': info.get('vcodec'), 'acodec': info.get('acodec'),
                'file': str(media), 'bytes': media.stat().st_size,
                'sha256': checksum,
            }
            manifest = output / (str(info['id']) + '.download.json')
            manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as error:
        print('Download failed: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
