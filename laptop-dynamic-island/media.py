"""
Now-Playing info, album art + controls via Windows System Media Transport
Controls (SMTC). Drives whatever app owns media -- Spotify, a browser tab, etc.

Optional: needs 'winrt-Windows.Media.Control' (has Python 3.14 wheels). If it's
missing, every function returns a safe default so the island still runs.
"""

import asyncio

_AVAILABLE = False
_Manager = None
_streams = None

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as _Manager,
    )
    import winrt.windows.storage.streams as _streams
    _AVAILABLE = True
except Exception:
    try:
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as _Manager,
        )
        import winsdk.windows.storage.streams as _streams
        _AVAILABLE = True
    except Exception:
        _AVAILABLE = False


def available() -> bool:
    return _AVAILABLE


async def _current_session():
    mgr = await _Manager.request_async()
    return mgr.get_current_session()


async def _info():
    session = await _current_session()
    if session is None:
        return None
    props = await session.try_get_media_properties_async()
    playback = session.get_playback_info()
    try:
        playing = int(playback.playback_status) == 4   # 4 = PLAYING
    except Exception:
        playing = False
    title = (props.title or "").strip()
    artist = (props.artist or "").strip()
    if not title and not artist:
        return None
    return {"title": title, "artist": artist, "playing": playing}


def now_playing():
    """Return {'title','artist','playing'} or None. Never raises."""
    if not _AVAILABLE:
        return None
    try:
        return asyncio.run(_info())
    except Exception:
        return None


async def _thumb():
    session = await _current_session()
    if session is None:
        return None
    props = await session.try_get_media_properties_async()
    ref = props.thumbnail
    if ref is None:
        return None
    stream = await ref.open_read_async()
    size = int(stream.size)
    if size <= 0:
        return None
    buf = _streams.Buffer(size)
    await stream.read_async(buf, buf.capacity, _streams.InputStreamOptions.READ_AHEAD)
    reader = _streams.DataReader.from_buffer(buf)
    data = reader.read_bytes(buf.length)
    return bytes(bytearray(data))


def album_art():
    """Return the current track's cover image as bytes (jpg/png), or None."""
    if not _AVAILABLE:
        return None
    try:
        return asyncio.run(_thumb())
    except Exception:
        return None


async def _do(action: str):
    session = await _current_session()
    if session is None:
        return
    if action == "toggle":
        await session.try_toggle_play_pause_async()
    elif action == "next":
        await session.try_skip_next_async()
    elif action == "prev":
        await session.try_skip_previous_async()


def _run(action: str):
    if not _AVAILABLE:
        return
    try:
        asyncio.run(_do(action))
    except Exception:
        pass


def toggle_play_pause():
    _run("toggle")


def skip_next():
    _run("next")


def skip_previous():
    _run("prev")
