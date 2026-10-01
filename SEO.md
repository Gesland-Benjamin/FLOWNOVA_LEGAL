# Vérification des corrections SEO

Le site reste statique. Aucun build, accès BDD ou service externe n'est nécessaire.
Les originaux PNG sont conservés. Aucun déploiement n'est effectué par ces scripts.

## Contrôles locaux

Depuis la racine du dépôt :

```sh
python3 -B -m unittest discover -s tests -v
python3 -B tests/check_apache.py
git diff --check
```

Le premier contrôle utilise uniquement la bibliothèque standard Python, sans réseau.
Il vérifie les métadonnées, le JSON-LD, les titres, le sitemap, robots.txt,
les ancres, les ressources et la conservation des liens de confidentialité.

Le second lance un Apache temporaire sur deux ports aléatoires de **127.0.0.1**.
Il utilise un certificat TLS de test, explicitement approuvé par le client de test.
Il ne suit jamais les redirections vers Internet. Le processus et ses fichiers
temporaires sont arrêtés/supprimés à la fin ; le service Apache système n'est pas modifié.
Apache, ses modules rewrite/SSL et OpenSSL doivent être installés. Les chemins par
défaut sont ceux de macOS ; sur un autre système, définir `HTTPD`,
`APACHE_MODULE_DIR` et `APACHE_MIME_TYPES` si nécessaire.

## Images

Les variantes sont déjà présentes dans `assets/optimized/` et directement utilisables.
Pour les régénérer volontairement, avec Pillow installé :

```sh
python3 scripts/optimize_images.py
```

- Logo : PNG 84 et 126 px ; favicon PNG 48 px.
- Captures : WebP 480 et 800 px, compression sans perte après redimensionnement Lanczos.
- Image sociale : JPEG 1200 × 630, dérivé de `app-hero.png`, sans recadrage du produit.
- Les captures secondaires conservent `loading="lazy"` et toutes conservent leurs
  dimensions HTML. Aucun preload ni priorité haute n'est imposé en l'absence de mesure LCP.
- AVIF n'est pas ajouté : WebP suffit ici et conserve une chaîne de génération simple.

## URLs et contenu

Les quatre URLs canoniques sont `/`, `/index.html`, `/terms.html` et
`/delete-account.html`, sous `https://flownova-crm.fr`.
**`index.html` reste la confidentialité ; ne jamais le rediriger vers `/`.**

`.htaccess` conserve `DirectoryIndex home.html index.html`. La règle qui redirige
`/home.html` vérifie `THE_REQUEST`, pour ne pas rediriger la résolution interne de `/`.
Les autres règles imposent HTTPS et le domaine sans www, en conservant le chemin
et la query string. Les canonicals omettent les paramètres de suivi.
`ErrorDocument 404 /404.html` sert la page d'erreur en interne, avec le statut 404.
La page d'erreur porte `noindex` et n'est pas dans le sitemap.

Le JSON-LD de l'accueil décrit `WebSite` et `MobileApplication` (iOS/iPadOS).
La seule offre structurée est **FlowNova Free, 0 EUR**, telle qu'affichée.
Aucun avis, note, société, adresse ou disponibilité Android n'est ajouté.
Les descriptions et textes visibles des quatre pages sont conservés.

## Avant un déploiement explicitement autorisé

1. Comparer les règles Hostinger existantes avec `.htaccess` : ne pas écraser
   d'éventuelles règles serveur absentes du dépôt. `mod_rewrite`, `AllowOverride`
   et `ErrorDocument` doivent être pris en charge.
2. Confirmer que le serveur d'origine reconnaît les requêtes HTTPS derrière le CDN.
   Si `%{HTTPS}` reste `off` après terminaison TLS par un proxy, la règle HTTPS
   doit être adaptée dans la configuration de confiance de l'hébergeur pour éviter
   une boucle. Ne pas faire confiance aveuglément à un en-tête client transmis.
3. Publier ensemble les HTML, `.htaccess`, fichiers SEO, 404 et toutes les images
   optimisées ; les chemins absolus supposent un hébergement à la racine du domaine.
   Les scripts/tests/documentation ne sont pas nécessaires au serveur public.
4. Vérifier mobile et clavier à 320, 375, 390 et 430 px : menu, hero, CTA, captures,
   tarifs, FAQ et footer. Mesurer LCP/CLS/INP ; le code seul ne certifie pas ces métriques.
5. Après déploiement validé, vérifier 200/301/404, types MIME, sitemap, accès Googlebot,
   aperçus sociaux et données structurées. Contrôler les réglages anti-robot Hostinger.
6. Confirmer séparément les mentions GitHub Pages dans la confidentialité et les
   langues annoncées sur l'App Store ; elles n'ont pas été modifiées dans ce lot SEO.
7. La validation DNS Search Console et la soumission du sitemap restent manuelles.

Les redirections 301 peuvent être mises en cache : toute vérification en production
doit donc tenir compte du cache navigateur/CDN. Aucun commit, push ou déploiement
n'est déclenché par les commandes ci-dessus.
