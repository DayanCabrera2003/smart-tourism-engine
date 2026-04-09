"""
Políticas de crawling: respeto a robots.txt, delay configurable y User-Agent identificable.
Incluye función is_allowed(url) y utilidad para delays.
"""
import urllib.robotparser
from urllib.parse import urlparse

import httpx

DEFAULT_USER_AGENT = "SmartTourismBot/1.0 (+https://github.com/your-org/smart-tourism-engine)"
DEFAULT_DELAY = 1.0  # segundos

class RobotsCache:
    """
    Cachea y gestiona robots.txt por dominio.
    """
    def __init__(self, user_agent: str = DEFAULT_USER_AGENT):
        self.parsers = {}
        self.user_agent = user_agent

    def get_parser(self, url: str) -> urllib.robotparser.RobotFileParser:
        domain = urlparse(url).netloc
        if domain not in self.parsers:
            robots_url = f"https://{domain}/robots.txt"
            parser = urllib.robotparser.RobotFileParser()
            try:
                resp = httpx.get(robots_url, headers={"User-Agent": self.user_agent}, timeout=5)
                parser.parse(resp.text.splitlines())
            except Exception:
                parser.parse("")  # Permisivo si no hay robots.txt
            self.parsers[domain] = parser
        return self.parsers[domain]

    def is_allowed(self, url: str) -> bool:
        parser = self.get_parser(url)
        return parser.can_fetch(self.user_agent, url)

robots_cache = RobotsCache()

def is_allowed(url: str) -> bool:
    """
    Devuelve True si el crawling está permitido para la URL según robots.txt.
    """
    return robots_cache.is_allowed(url)

def crawl_delay(domain: str, default: float = DEFAULT_DELAY) -> float:
    """
    Obtiene el crawl-delay de robots.txt para el dominio, o default si no está.
    """
    parser = robots_cache.parsers.get(domain)
    if parser and hasattr(parser, 'crawl_delay'):
        delay = parser.crawl_delay(robots_cache.user_agent)
        if delay is not None:
            return delay
    return default
