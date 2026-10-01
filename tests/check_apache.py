"""Exercise the real .htaccess on a disposable, loopback-only Apache instance.

macOS default paths; override HTTPD, APACHE_MODULE_DIR, APACHE_MIME_TYPES on Linux.
No production requests, database access, system-service changes or privileged ports.
Hostinger/CDN owns HTTP-to-HTTPS enforcement; Apache must also serve canonical
requests over plain HTTP from the proxy without redirecting them to themselves.
"""
import getpass
import http.client
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://flownova-crm.fr"


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    assert "%{HTTPS}" not in (ROOT / ".htaccess").read_text(), "HTTPS enforcement belongs to Hostinger/CDN"
    httpd = os.environ.get("HTTPD", "/usr/sbin/httpd")
    modules = Path(os.environ.get("APACHE_MODULE_DIR", "/usr/libexec/apache2"))
    mime = os.environ.get("APACHE_MIME_TYPES", "/etc/apache2/mime.types")
    openssl = shutil.which("openssl")
    if not Path(httpd).exists() or not openssl:
        raise SystemExit("Apache and OpenSSL are required for the optional HTTP checks.")
    plain, secure = unused_port(), unused_port()
    while secure == plain:
        secure = unused_port()
    with tempfile.TemporaryDirectory(prefix="flownova-apache-") as directory:
        tmp = Path(directory)
        subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-keyout", str(tmp / "key.pem"), "-out", str(tmp / "cert.pem"),
                        "-days", "1", "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
                       check=True, capture_output=True)
        load = "\n".join(f'LoadModule {name}_module "{modules}/mod_{name}.so"'
                         for name in ("mpm_prefork", "unixd", "authz_core", "authz_host",
                                      "dir", "mime", "rewrite", "ssl", "socache_shmcb"))
        conf = tmp / "httpd.conf"
        conf.write_text(f'''ServerRoot "{tmp}"
PidFile "{tmp}/httpd.pid"
Mutex file:{tmp} default
ErrorLog "{tmp}/error.log"
ServerName localhost
Listen 127.0.0.1:{plain}
Listen 127.0.0.1:{secure}
{load}
User {getpass.getuser()}
Group #{os.getgid()}
TypesConfig "{mime}"
DocumentRoot "{ROOT}"
<Directory "{ROOT}">
    Require all granted
    AllowOverride All
    Options FollowSymLinks
</Directory>
<VirtualHost 127.0.0.1:{secure}>
    ServerName flownova-crm.fr
    SSLEngine on
    SSLCertificateFile "{tmp}/cert.pem"
    SSLCertificateKeyFile "{tmp}/key.pem"
</VirtualHost>
''')
        subprocess.run([httpd, "-t", "-f", str(conf)], check=True)
        context = ssl.create_default_context(cafile=str(tmp / "cert.pem"))

        def request(path, host="flownova-crm.fr", tls=True, forwarded_proto=None):
            # Always connect to loopback, regardless of Host or redirect target.
            conn = (http.client.HTTPSConnection("127.0.0.1", secure, context=context, timeout=5)
                    if tls else http.client.HTTPConnection("127.0.0.1", plain, timeout=5))
            try:
                headers = {"Host": host}
                if forwarded_proto is not None:
                    headers["X-Forwarded-Proto"] = forwarded_proto
                conn.request("GET", path, headers=headers)
                result = conn.getresponse()
                return result.status, result.getheader("Location"), result.read(), result.getheader("Content-Type")
            finally:
                conn.close()

        process = subprocess.Popen([httpd, "-X", "-f", str(conf)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        checks = 0
        try:
            for _ in range(50):
                if process.poll() is not None:
                    log = tmp / "error.log"
                    raise RuntimeError(process.communicate()[1].decode() + (log.read_text() if log.exists() else ""))
                try:
                    with socket.create_connection(("127.0.0.1", plain), timeout=.1):
                        break
                except OSError:
                    time.sleep(.1)
            cases = [
                ("/", "home.html"), ("/index.html", "index.html"),
                ("/terms.html", "terms.html"), ("/delete-account.html", "delete-account.html"),
                ("/sitemap.xml", "sitemap.xml"), ("/robots.txt", "robots.txt"),
                ("/?utm_source=test", "home.html"),
            ]
            for path, file in cases:
                for tls, forwarded_proto in ((True, None), (False, None), (False, "https")):
                    status, location, body, mime_type = request(path, tls=tls, forwarded_proto=forwarded_proto)
                    assert status == 200 and location is None, (path, tls, forwarded_proto, status, location)
                    assert body == (ROOT / file).read_bytes(), (path, "incorrect body")
                    checks += 1
            for path in ("/", "/index.html", "/terms.html?utm_source=test", "/delete-account.html"):
                for tls, forwarded_proto in ((True, None), (False, None), (False, "https")):
                    status, location, _, _ = request(path, "www.flownova-crm.fr", tls, forwarded_proto)
                    assert (status, location) == (301, BASE + path), (path, tls, status, location)
                    final = request(path, tls=tls, forwarded_proto=forwarded_proto)
                    assert final[0] == 200 and final[1] is None, "host redirect loop"
                    checks += 1
            for path in ("/home.html", "/home.html?utm_source=test"):
                for host in ("flownova-crm.fr", "www.flownova-crm.fr"):
                    for tls, forwarded_proto in ((True, None), (False, None), (False, "https")):
                        status, location, _, _ = request(path, host, tls, forwarded_proto)
                        expected = BASE + "/" + ("?utm_source=test" if "?" in path else "")
                        assert (status, location) == (301, expected), (path, host, tls, status, location)
                        # Test the redirect destination locally: no external redirect following.
                        final = request(location[len(BASE):], tls=tls, forwarded_proto=forwarded_proto)
                        assert final[0] == 200 and final[1] is None, "redirect loop"
                        checks += 1
            for path in ("/not-found", "/nested/missing", "/home.html/", "/index.html/", "/terms.html/"):
                for tls, forwarded_proto in ((True, None), (False, None), (False, "https")):
                    status, location, body, _ = request(path, tls=tls, forwarded_proto=forwarded_proto)
                    assert status == 404 and location is None, (path, tls, status, location)
                    assert body == (ROOT / "404.html").read_bytes(), "wrong error document"
                    checks += 1
            for path in (ROOT / "assets/optimized").iterdir():
                status, location, body, mime_type = request("/" + str(path.relative_to(ROOT)))
                assert status == 200 and location is None and body == path.read_bytes(), path
                expected = {".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg"}[path.suffix]
                assert mime_type == expected, (path, mime_type)
                checks += 1
            print(f"PASS: {checks} local Apache HTTP/TLS/proxy-origin checks; no HTTPS enforcement or redirect loop; privacy page preserved; genuine 404s.")
        finally:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    main()
