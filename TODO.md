Harden the server:
	- Turn DEBUG off: DEBUG=False in .env @cfq
	- Random SECRET_KEY and Postgres password for the fresh install @cfq
	- Publish port 8000 on 127.0.0.1 only
	- Vite only from localhost
		- Behind a Compose profile, not started by make up
		- Drop allowedHosts: true
		- Reach it with ssh -L 5173:localhost:5173 when needed
	- nginx: em.cfqs.com server block with Let's Encrypt, proxying to 127.0.0.1:8000 @cfq
	- nginx: catch-all default_server that drops unknown hosts (return 444) @cfq
	- Django behind the proxy: ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS for https://em.cfqs.com, secure cookies
	- Refuse to start with DEBUG on unless only reachable locally
	- Log out all sessions and replace the iOS Shortcut API token
	- Deployment note in the spec: dev ports never public, everything through the proxy
	- Check ~/.ssh/authorized_keys (ssh-keygen -lf), confirm the 31.94.32.64 login with key mMyG… @cfq
	- Track down the hourly ssh-rsa login attempts @cfq

Fresh install:
	- make install: npm ci, build, up
	- make nuke @cfq
	- make install, make createsuperuser @cfq
	- Re-save articles from tmp/export-2026-11-20.txt, re-apply tags

Reading view:
	- Metadata section rework

Open Graph:
	- og:image and related tags, saved with the item

Extraction:
	- Art Nouveau special round: dropped figures, footnote references without links @cfq
	- Readability fallback for images when trafilatura keeps none (strip heading classes first)
	- Per-site rules (ftr-site-config style)
	- Patchright for bot walls (Cloudflare on hyperspekulation.org, Vercel on nabeelqu.co); check it works with the remote browser first
	- Keep the page (HTML, screenshots) even when extraction fails

Image uploads:
	- Upload images
	- type: image items

Inbox and sorting:

Search:
	- Postgres full-text search

Tags and projects:
	- Tag editor: rename, merge, delete
	- Folders / projects

Social:
	- Downloaders for Instagram, X, YouTube with your logins

Housekeeping:
	- Delete tmp/bakeoff @cfq
