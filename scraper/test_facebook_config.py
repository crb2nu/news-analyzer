from scraper.config import Settings


def test_facebook_pages_list_parsing(monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_IDS", "123, 456 , 789 ")
    s = Settings()
    assert s.list_facebook_pages() == ["123", "456", "789"]


def test_facebook_defaults():
    s = Settings()
    assert s.facebook_graph_version.startswith("v")
