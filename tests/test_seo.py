"""Static SEO checks: standard library only, no network or database access."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import json
import unittest
from urllib.parse import unquote, urlsplit
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://flownova-crm.fr"
PAGES = {"home.html": "/", "index.html": "/index.html",
         "terms.html": "/terms.html", "delete-account.html": "/delete-account.html"}
PRIVACY_LINKS = {
    "home.html": {"index.html": 1, "index.html#s8": 1},
    "index.html": {"index.html": 2},
    "terms.html": {"index.html": 3, "index.html#s7": 2, "index.html#s9": 1,
                   "index.html#s11": 1, "index.html#s8": 1},
    "delete-account.html": {"index.html": 2, "index.html#s8": 1, "index.html#s7": 1},
}


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags, self.headings, self.titles, self.jsonld = [], [], [], []
        self.capture = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag in ("h1", "h2", "h3"):
            self.headings.append(int(tag[1]))
        if tag == "title":
            self.titles.append("")
            self.capture = self.titles
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.jsonld.append("")
            self.capture = self.jsonld

    def handle_data(self, data):
        if self.capture is not None:
            self.capture[-1] += data

    def handle_endtag(self, tag):
        if tag in ("title", "script"):
            self.capture = None

    def meta(self, key):
        return [a.get("content", "") for t, a in self.tags if t == "meta"
                and key in (a.get("name"), a.get("property"))]


class SEOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {name: Page((ROOT / name).read_text()) for name in (*PAGES, "404.html")}

    def test_metadata(self):
        titles, descriptions = [], []
        for name, path in PAGES.items():
            with self.subTest(page=name):
                p = self.pages[name]
                self.assertEqual(len(p.titles), 1)
                self.assertTrue(p.titles[0].strip())
                titles += p.titles
                description = p.meta("description")
                self.assertEqual(len(description), 1)
                self.assertTrue(description[0].strip())
                descriptions += description
                canonical = [a["href"] for t, a in p.tags if t == "link" and a.get("rel") == "canonical"]
                self.assertEqual(canonical, [BASE + path])
                self.assertEqual(p.meta("og:url"), canonical)
                self.assertEqual(p.meta("og:title"), p.titles)
                self.assertEqual(p.meta("og:description"), description)
                self.assertEqual(p.meta("og:type"), ["website"])
                self.assertEqual(p.meta("twitter:title"), p.titles)
                self.assertEqual(p.meta("twitter:description"), description)
                self.assertEqual(p.meta("twitter:card"), ["summary_large_image"])
                self.assertEqual(p.meta("twitter:image"), p.meta("og:image"))
                self.assertEqual(len(p.meta("og:image")), 1)
                self.assertTrue(p.meta("og:image")[0].startswith(BASE + "/"))
                self.assertNotIn("noindex", ",".join(p.meta("robots")))
        self.assertEqual(len(set(titles)), 4)
        self.assertEqual(len(set(descriptions)), 4)
        self.assertEqual(self.pages["home.html"].titles, ["FlowNova — CRM mobile pour indépendants"])

    def test_semantics_and_images(self):
        for name, p in self.pages.items():
            with self.subTest(page=name):
                self.assertEqual(p.headings.count(1), 1)
                for previous, current in zip(p.headings, p.headings[1:]):
                    self.assertLessEqual(current, previous + 1)
                self.assertEqual(sum(t == "main" for t, _ in p.tags), 1)
                self.assertIn(("html", {"lang": "fr"}), p.tags)
                for t, a in p.tags:
                    if t == "img":
                        self.assertIn("alt", a)
                        self.assertGreater(int(a["width"]), 0)
                        self.assertGreater(int(a["height"]), 0)
        home = self.pages["home.html"]
        screenshots = [a for t, a in home.tags if t == "img" and ".webp" in a["src"]]
        self.assertEqual(len(screenshots), 4)
        self.assertTrue(all(a.get("loading") == "lazy" for a in screenshots[2:]))
        self.assertLessEqual(sum(a.get("fetchpriority") == "high" for a in screenshots), 1)

    def test_local_links_and_assets(self):
        for name, p in self.pages.items():
            ids = [a["id"] for _, a in p.tags if "id" in a]
            self.assertEqual(len(ids), len(set(ids)), name)
            for tag, attrs in p.tags:
                refs = [attrs[k] for k in ("href", "src") if k in attrs]
                if "srcset" in attrs:
                    refs += [v.strip().split()[0] for v in attrs["srcset"].split(",")]
                if tag == "meta" and attrs.get("property", attrs.get("name")) in ("og:image", "twitter:image"):
                    refs.append(attrs["content"])
                for ref in refs:
                    u = urlsplit(ref)
                    if u.scheme and u.scheme not in ("https", "http"):
                        continue
                    if u.netloc and u.netloc != "flownova-crm.fr":
                        continue
                    target = unquote(u.path).lstrip("/") if u.path else name
                    target = target or "home.html"
                    self.assertTrue((ROOT / target).is_file(), (name, ref))
                    if u.fragment and target in self.pages:
                        target_ids = [a.get("id") for _, a in self.pages[target].tags]
                        self.assertIn(unquote(u.fragment), target_ids, (name, ref))
                    if tag == "a":
                        self.assertNotEqual(u.path.lstrip("/"), "home.html", (name, ref))

    def test_privacy_links_preserved(self):
        for name, expected in PRIVACY_LINKS.items():
            actual = Counter(a["href"] for t, a in self.pages[name].tags
                             if t == "a" and a.get("href", "").startswith("index.html"))
            self.assertEqual(actual, expected, name)

    def test_sitemap_and_robots(self):
        root = ET.parse(ROOT / "sitemap.xml").getroot()
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        self.assertEqual(root.tag, ns + "urlset")
        urls = [node.text for node in root.findall(f"{ns}url/{ns}loc")]
        self.assertCountEqual(urls, [BASE + path for path in PAGES.values()])
        self.assertFalse(root.findall(f"{ns}url/{ns}lastmod"))
        self.assertTrue(all("home.html" not in u and not urlsplit(u).query for u in urls))
        robots = RobotFileParser()
        robots.parse((ROOT / "robots.txt").read_text().splitlines())
        self.assertEqual(robots.site_maps(), [BASE + "/sitemap.xml"])
        for url in urls:
            self.assertTrue(robots.can_fetch("Googlebot", url))

    def test_schema(self):
        blocks = self.pages["home.html"].jsonld
        self.assertEqual(len(blocks), 1)
        data = json.loads(blocks[0])
        self.assertEqual(data["@context"], "https://schema.org")
        graph = {node["@type"]: node for node in data["@graph"]}
        self.assertEqual(set(graph), {"WebSite", "MobileApplication"})
        app = graph["MobileApplication"]
        self.assertEqual(app["operatingSystem"], ["iOS", "iPadOS"])
        self.assertEqual(app["url"], BASE + "/")
        self.assertEqual(app["offers"]["price"], "0")
        self.assertEqual(app["offers"]["name"], "FlowNova Free")
        links = [a.get("href") for t, a in self.pages["home.html"].tags if t == "a"]
        self.assertIn(app["downloadUrl"], links)
        for forbidden in ("aggregateRating", "review", "FAQPage", "Android", "address"):
            self.assertNotIn(forbidden, blocks[0])

    def test_404(self):
        self.assertEqual(self.pages["404.html"].meta("robots"), ["noindex"])
        self.assertIn("ErrorDocument 404 /404.html", (ROOT / ".htaccess").read_text())
        links = [a.get("href") for t, a in self.pages["404.html"].tags if t == "a"]
        self.assertIn("/", links)


if __name__ == "__main__":
    unittest.main(verbosity=2)
