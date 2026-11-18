# Extended Mind

- I constantly come across things I'm potentially interested whilst browsing the web at large and want to find a way to save and categorise them.
- The web slips through our fingers constantly. I want to save some things in the way I saw them. Things get deleted or updated. I want to be able to download and keep things.
- I want to have a workflow where I trawl through lots of links, keep the ones into a sort pile, and then categorise or get rid of them quickly.
- I want to be able to access this from multiple devices. I want the save to be really quick.
- It should have a mechanism for saving my content through my accounts. 
  - For each major source there will be a downloader that can use my login information.
  - Specifically thinking of instagram, x and youtube for now.
  - I should be able to accept image uploads as well, and extract data from images, EXIF, OCR and object detection.
  - Save articles ala Instapaper with images
  - If webpage, screenshot of it at the time of save
- It should make it easy for me to find things after I saved them. Do postprocessing, content extraction etc.
- It should be easy to search both by freetext, but also by tagging, and should have a folder structure for adding to projects.
  - Both rhizomatic with tagging and search, and arborescent with folders.
  - Freeform text field for notes
  - Saving the origin, where I saved it from, metadata
- I should be able to deploy the application wherever I like.

## Parts
- [Architecture](docs/spec/architecture.md)
- [Deployment](docs/spec/deployment.md)
- [Auth](docs/spec/auth.md)
- [ADRs](docs/adr/)

## Current scope
- API backend 
- Web front-end
- Bookmarklet
- Content extractors
- Pipeline for data extraction and processing
- Saving articles, YouTube videos, Instagram posts with photos and videos, X threads
- A way to capture site credentials for instagram, X and YouTube
- Uploading images
- Multi-user, so auth flow, email, API tokens, settings
- Admin panel for user management
- Dashboard in the admin panel for monitoring background processes, information about data, relevant statistics
- Logging, monitoring
- Inbox workflow, everything gets saved into an unsorted pile
- Editing/adding tags, notes for items
- Automatic tagging: tags the page declares, plus a small LLM run locally with Ollama (no external service)
- Editor for tags, projects
- Search, postgres full-text search for now

## Out of scope
- Playlists/channels/profiles, email verification, sharing, offline, external search, S3, backups, quotas, dead-link checks, cloud AI tagging.
