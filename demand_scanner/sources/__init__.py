from .app_stores import AppStore, GooglePlay
from .base import ScanContext, Source
from .bluesky import Bluesky
from .github import GitHubIssues
from .google_suggest import GoogleSuggest
from .google_trends import GoogleTrends
from .hackernews import HackerNews
from .reddit import Reddit
from .stackexchange import StackExchange
from .tiktok import TikTok
from .youtube import YouTube

REGISTRY: dict[str, type[Source]] = {cls.name: cls for cls in (
    Reddit, HackerNews, GoogleTrends, GoogleSuggest, YouTube, TikTok, StackExchange,
    Bluesky, AppStore, GooglePlay, GitHubIssues,
)}

__all__ = ["REGISTRY", "ScanContext", "Source"]
