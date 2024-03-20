from spotipy import CacheHandler


class NoopCacheHandler(CacheHandler):
    def get_cached_token(self):
        return None

    def save_token_to_cache(self, token_info):
        return None
