# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# pelisalacarta
# MCT - Mini Cliente Torrent para pelisalacarta
# http://blog.tvalacarta.info/plugin-xbmc/pelisalacarta/
# ------------------------------------------------------------

import os, re
import shutil, tempfile
import urllib, urllib2
from contextlib import closing
import zlib

from core import config, scrapertools
from platformcode import library
import xbmc, xbmcgui

try:
    from lib.python_libtorrent import get_libtorrent, get_platform
    lt = get_libtorrent()
except:
    import libtorrent as lt

def play(url, xlistitem={}, is_view=None, subtitle=""):

    allocate = True
    try:
        _platform = get_platform()
        if str(_platform['system']) in ["android_armv7", "linux_armv6", "linux_armv7"]:
            allocate = False
    except: pass

    if url.startswith("http://adf.ly/"):
        ddd = xbmcgui.Dialog()
        ddd.ok("pelisalacarta-MCT: Sin soporte adf.ly", "El script no tiene soporte para el acortador de urls adf.ly.", "", "url: " + url)
        return

    if not url.endswith(".torrent") and not url.startswith("magnet"):
        t_file = scrapertools.get_header_from_response(url, header_to_get="location")
        if len(t_file) > 0:
            url = t_file
            t_file = scrapertools.get_header_from_response(url, header_to_get="location")
        if len(t_file) > 0: url = t_file

    save_path_videos = os.path.join(config.get_setting("downloadpath") , "torrent-videos")
    save_path_torrents = os.path.join(config.get_setting("downloadpath") , "torrent-torrents")
    if not os.path.exists( save_path_torrents ): os.mkdir(save_path_torrents)

    if not os.path.isfile(url) and not url.startswith("magnet"):
        data = url_get(url)
        re_name = library.title_to_folder_name(urllib.unquote(scrapertools.get_match(data, ':name\d+:(.*?)\d+:')))
        torrent_file = os.path.join(save_path_torrents, unicode(re_name, "'utf-8'", errors="replace")+'.torrent')

        f = open(torrent_file,'wb')
        f.write(data)
        f.close()
    elif os.path.isfile(url):
        torrent_file = url
    else:
        torrent_file = url

    ses = lt.session()

    ses.add_dht_router("router.bittorrent.com",6881)
    ses.add_dht_router("router.utorrent.com",6881)
    ses.add_dht_router("router.bitcomet.com",554)
    ses.add_dht_router("dht.transmissionbt.com",6881)

    trackers = [
        "http://exodus.desync.com:6969/announce",
        "udp://tracker.publicbt.com:80/announce",
        "udp://tracker.openbittorrent.com:80/announce",
        "http://tracker.torrentbay.to:6969/announce",
        "http://fr33dom.h33t.com:3310/announce",
        "http://tracker.pow7.com/announce",
        "udp://tracker.ccc.de:80/announce",
        "http://tracker.bittorrent.am:80/announce",
        "http://denis.stalker.h3q.com:6969/announce",
        "udp://tracker.prq.to:80/announce",
        "udp://tracker.istole.it:80/announce",
        "udp://open.demonii.com:1337",

        "http://9.rarbg.com:2710/announce",
        "http://announce.torrentsmd.com:6969/announce",
        "http://bt.careland.com.cn:6969/announce",
        "http://explodie.org:6969/announce",
        "http://mgtracker.org:2710/announce",
        "http://tracker.best-torrents.net:6969/announce",
        "http://tracker.tfile.me/announce",
        "http://tracker.torrenty.org:6969/announce",
        "http://tracker1.wasabii.com.tw:6969/announce",
        "udp://9.rarbg.com:2710/announce",
        "udp://9.rarbg.me:2710/announce",
        "udp://coppersurfer.tk:6969/announce",
        "udp://tracker.btzoo.eu:80/announce",

        "http://www.spanishtracker.com:2710/announce",
        "http://www.todotorrents.com:2710/announce",
    ]

    video_file = ""
    if torrent_file.startswith("magnet"):
        tempdir = tempfile.mkdtemp()
        params = {
            'save_path': tempdir,
            'trackers':trackers,
            'storage_mode': lt.storage_mode_t.storage_mode_allocate,
            'paused': False,
            'auto_managed': True,
            'duplicate_is_error': True
        }
        h = lt.add_magnet_uri(ses, torrent_file, params)
        dp = xbmcgui.DialogProgress()
        h.force_reannounce()
        h.force_dht_announce()
        dp.create('pelisalacarta-MCT')
        while not h.has_metadata():
            message, porcent, msg_file, s, download = getProgress(h, "Creando torrent desde magnet")
            dp.update(porcent, message, msg_file)
            if s.state == 1: download = 1
            if dp.iscanceled():
                dp.close()
                remove_files(download, torrent_file, video_file, ses, h)
                return
        dp.close()
        info = h.get_torrent_info()
        data = lt.bencode(lt.create_torrent(info).generate())

        torrent_file = os.path.join(save_path_torrents, unicode(info.name(), "'utf-8'", errors="replace") + ".torrent")
        f = open(torrent_file,'wb')
        f.write(data)
        f.close()
        ses.remove_torrent(h)
        shutil.rmtree(tempdir)

    e = lt.bdecode(open(torrent_file, 'rb').read())
    info = lt.torrent_info(e)

    _index_file, _video_file, _size_file = get_video_file(info)

    _video_file_ext = os.path.splitext( _video_file )[1]
    if (_video_file_ext == ".avi" or _video_file_ext == ".mp4") and allocate:
        h = ses.add_torrent({'ti':info, 'save_path': save_path_videos, 'trackers':trackers, 'storage_mode':lt.storage_mode_t.storage_mode_allocate})
    else:
        h = ses.add_torrent({'ti':info, 'save_path': save_path_videos, 'trackers':trackers, 'storage_mode':lt.storage_mode_t.storage_mode_sparse})

    h.set_sequential_download(True)
    h.force_reannounce()
    h.force_dht_announce()

    _index, video_file, video_size = get_video_files_sizes(info)
    if _index == -1:
        _index = _index_file
        video_file = _video_file
        video_size = _size_file

    is_greater_num_pieces = False
    is_greater_num_pieces_plus = False
    is_greater_num_pieces_pause = False

    porcent4first_pieces = int(video_size * 0.000000005)
    if porcent4first_pieces < 10: porcent4first_pieces = 10
    if porcent4first_pieces > 100: porcent4first_pieces = 100
    porcent4last_pieces = int(porcent4first_pieces/2)

    num_pieces_to_resume = int(video_size * 0.0000000025)
    if num_pieces_to_resume < 5: num_pieces_to_resume = 5
    if num_pieces_to_resume > 25: num_pieces_to_resume = 25

    piece_set = set_priority_pieces(h, _index, video_file, video_size, porcent4first_pieces, porcent4last_pieces, allocate)

    dp = xbmcgui.DialogProgress()
    dp.create('pelisalacarta-MCT')

    _pieces_info = {}

    while not h.is_seed():
        s = h.status()

        xbmc.sleep(100)
        message, porcent, msg_file, s, download = getProgress(h, video_file, _pf=_pieces_info)

        if s.state == 1: download = 1
        first_pieces = True
        _c = 0
        for i in range(piece_set[0], piece_set[porcent4first_pieces]):
            first_pieces&= h.have_piece(i)
            if h.have_piece(i): _c+= 1
        _pieces_info = {'current': 0, 'continuous': "%s/%s" % (_c,porcent4first_pieces), 'continuous2': "", 'have': h.status().num_pieces, 'len': len(piece_set)}

        last_pieces = True
        if not allocate:
            _c = len(piece_set)-1; _cc = 0
            for i in range(len(piece_set)-porcent4last_pieces,len(piece_set)):
                last_pieces &= h.have_piece(i)
                if h.have_piece(i): _c-= 1; _cc+=1
            _pieces_info['continuous2'] = "[%s/%s] " % (_cc,porcent4last_pieces)

        if is_view != "Ok" and first_pieces and last_pieces:
            _pieces_info['continuous2'] = ""
            is_view = "Ok"
            dp.close()

            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            playlist.clear()

            ren_video_file = os.path.join(save_path_videos, video_file)
            playlist.add(ren_video_file, xlistitem)

            player = play_video(xbmc.PLAYER_CORE_AUTO)
            player.play(playlist)

            is_greater_num_pieces_canceled = 0
            continuous_pieces = 0
            porcent_time = 0.00
            current_piece = 0

            not_resume = True
            _sub = False

            while player.isPlaying():
                xbmc.sleep(100)

                if subtitle!="" and not _sub:
                    _sub = True
                    player.setSubtitles(subtitle)

                if not_resume:
                    player.seekTime(0)
                    not_resume = False

                continuous_pieces = count_completed_continuous_pieces(h, piece_set)

                if xbmc.Player().isPlaying():

                    porcent_time = player.getTime() / player.getTotalTime() * 100
                    current_piece = int( porcent_time / 100 * len(piece_set) )

                    is_greater_num_pieces = (current_piece > continuous_pieces - num_pieces_to_resume)
                    is_greater_num_pieces_plus = (current_piece + porcent4first_pieces > continuous_pieces)
                    is_greater_num_pieces_finished = (current_piece + porcent4first_pieces >= len(piece_set))

                    if is_greater_num_pieces and not player.paused and not is_greater_num_pieces_finished:
                        is_greater_num_pieces_pause = True
                        player.pause()

                if player.resumed:
                    dp.close()

                if player.paused:
                    if not player.statusDialogoProgress:
                        dp = xbmcgui.DialogProgress()
                        dp.create('pelisalacarta-MCT')
                        player.setDialogoProgress()

                    if not h.is_seed():
                        message, porcent, msg_file, s, download = getProgress(h, video_file, _pf=_pieces_info)
                        dp.update(porcent, message, msg_file)
                    else:
                        dp.update(100, "Descarga completa: " + video_file)

                    if dp.iscanceled():
                        dp.close()
                        player.pause()

                    if dp.iscanceled() and is_greater_num_pieces_pause:
                        is_greater_num_pieces_canceled+= 1
                        if is_greater_num_pieces_canceled == 3:
                            player.stop()

                    if not dp.iscanceled() and not is_greater_num_pieces_plus and is_greater_num_pieces_pause:
                        dp.close()
                        player.pause()
                        is_greater_num_pieces_pause = False
                        is_greater_num_pieces_canceled = 0

                    if player.ended:
                        remove_files( download, torrent_file, video_file, ses, h )
                        return

        if is_view == "Ok" and not xbmc.Player().isPlaying():

            if info.num_files() == 1:
                d = xbmcgui.Dialog()
                ok = d.yesno('pelisalacarta-MCT', 'XBMC-Kodi Cerró el vídeo.', '¿Continuar con la sesión?')
            else: ok = False

            if ok: is_view = None
            else:
                _index, video_file, video_size = get_video_files_sizes(info)
                if _index == -1 or info.num_files() == 1:
                    remove_files(download, torrent_file, video_file, ses, h)
                    return
                else:
                    piece_set = set_priority_pieces(h, _index, video_file, video_size, porcent4first_pieces, porcent4last_pieces, allocate)
                    is_view = None
                    dp = xbmcgui.DialogProgress()
                    dp.create('pelisalacarta-MCT')

        if is_view != "Ok": dp.update(porcent, message, msg_file)

        if dp.iscanceled():
            dp.close()
            _index, video_file, video_size = get_video_files_sizes(info)
            if _index == -1 or info.num_files() == 1:
                remove_files(download, torrent_file, video_file, ses, h)
                return
            else:
                piece_set = set_priority_pieces(h, _index, video_file, video_size, porcent4first_pieces, porcent4last_pieces, allocate)
                is_view=None
                dp = xbmcgui.DialogProgress()
                dp.create('pelisalacarta-MCT')

    if is_view == "Ok" and not xbmc.Player().isPlaying():
        dp.close()
        remove_files(download, torrent_file, video_file, ses, h)

    return

def getProgress(h, video_file, _pf={}):

    if len(_pf) > 0:
        _pf_msg = "[%s] [%s] %s[%s] [%s]" % (_pf['current'], _pf['continuous'], _pf['continuous2'], _pf['have'], _pf['len'])
    else: _pf_msg = ""

    s = h.status()

    state_str = ['queued', 'checking', 'downloading metadata', \
        'downloading', 'finished', 'seeding', 'allocating', 'checking fastresume']

    message = '%.2f%% d:%.1f kb/s u:%.1f kb/s p:%d s:%d %s' % \
        (s.progress * 100, s.download_rate / 1000, s.upload_rate / 1000, \
        s.num_peers, s.num_seeds, state_str[s.state])
    porcent = int( s.progress * 100 )

    download = ( s.progress * 100 )

    if "/" in video_file: video_file = video_file.split("/")[1]
    msg_file = video_file

    if len(msg_file) > 50:
        msg_file = msg_file.replace( video_file, os.path.splitext(video_file)[0][:40] + "... " + os.path.splitext(video_file)[1] )
    msg_file = msg_file + "[CR]" + "%.2f MB" % (s.total_wanted/1048576.0) + " - " + _pf_msg

    return (message, porcent, msg_file, s, download)

class play_video(xbmc.Player):

    def __init__(self, *args, **kwargs):
        self.paused = False
        self.resumed = True
        self.statusDialogoProgress = False
        self.ended = False

    def onPlayBackPaused(self):
        self.paused = True
        self.resumed = False

    def onPlayBackResumed(self):
        self.paused = False
        self.resumed = True
        self.statusDialogoProgress = False

    def is_paused(self):
        return self.paused

    def setDialogoProgress(self):
        self.statusDialogoProgress = True

    def is_started(self):
        self.ended = False

    def is_ended(self):
        self.ended = True

def get_video_file(info):
    size_file = 0
    for i, f in enumerate(info.files()):
        if f.size > size_file:
            video_file = f.path.replace("\\","/")
            size_file = f.size
            index_file = i
    return index_file, video_file, size_file

def get_video_files_sizes(info):

    opciones = []
    vfile_name = {}
    vfile_size = {}

    for i, f in enumerate(info.files()):
        _index = int(i)
        _title = f.path.replace("\\","/")
        _size = f.size
        _offset = f.offset

        _file_name = os.path.splitext(_title)[0]
        if "/" in _file_name: _file_name = _file_name.split('/')[1]

        _file_ext = os.path.splitext(_title)[1]

        _caption = str(i) + " - " + _file_name + _file_ext + " - %.2f MB" % (_size / 1048576.0)

        vfile_name[i] = _title
        vfile_size[i] = _size

        opciones.append(_caption)

    if len(opciones) > 1:
        d = xbmcgui.Dialog()
        seleccion = d.select("pelisalacarta-MCT: Lista de vídeos", opciones)
    else: seleccion = 0

    if seleccion == -1:
        vfile_name[seleccion] = ""
        vfile_size[seleccion] = 0

    return seleccion, vfile_name[seleccion], vfile_size[seleccion]

def remove_files(download, torrent_file, video_file, ses, h):

    dialog_view = False
    torrent = False

    if os.path.isfile(torrent_file):
        dialog_view = True
        torrent = True

    if download > 0:
        dialog_view = True

    if "/" in video_file: video_file = video_file.split("/")[0]

    if dialog_view:
        d = xbmcgui.Dialog()
        ok = d.yesno('pelisalacarta-MCT', 'Borrar las descargas del video', video_file)

        if ok:
            if torrent: os.remove( torrent_file )
            ses.remove_torrent(h, 1)
        else:
            ses.remove_torrent(h)
    else:
        ses.remove_torrent(h)

    return

def url_get(url, params={}, headers={}):

    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:20.0) Gecko/20100101 Firefox/20.0"

    if params: url = "%s?%s" % (url, urllib.urlencode(params))

    req = urllib2.Request(url)
    req.add_header("User-Agent", user_agent)

    for k, v in headers.items():
        req.add_header(k, v)

    try:
        with closing(urllib2.urlopen(req)) as response:
            data = response.read()
            if response.headers.get("Content-Encoding", "") == "gzip":
                return zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(data)
            return data
    except urllib2.HTTPError:
        return None

def count_completed_continuous_pieces(h, piece_set):
    not_zero = 0
    for i, _set in enumerate(piece_set):
        if not h.have_piece(_set): break
        else: not_zero = 1
    return i + not_zero

def set_priority_pieces(h, _index, video_file, video_size, porcent4first_pieces, porcent4last_pieces, allocate):

    for i, _set in enumerate(h.file_priorities()):
        if i != _index: h.file_priority(i,0)
        else: h.file_priority(i,1)

    piece_set = []
    for i, _set in enumerate(h.piece_priorities()):
        if _set == 1: piece_set.append(i)

    if not allocate:
        for i in range(0,porcent4first_pieces):
            h.set_piece_deadline(piece_set[i],10000)

        for i in range(len(piece_set)-porcent4last_pieces,len(piece_set)):
            h.set_piece_deadline(piece_set[i],10000)

    return piece_set
