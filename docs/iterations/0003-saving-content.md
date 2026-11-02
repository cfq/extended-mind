# 0003 - Saving Content

Saving content, starting with articles, and displaying them. 

## Decisions
  - / is a dashboard
    - shows a list of items
    - on click opens a page for the item
    - before fetch complete, just metadata
    - after fetch complete, displays the article
  - /add new page for adding content
    - Link for Add in header
    - Takes in a URL
    - Adds immediately, there's a status, unfetched yet
    - Worker kicks off, fetches, saves
    - Article body saved to database
    - Raw document fetched can be saved to filesystem
    - Updates status
    - Before completely fetched
      - item description, or preview empty
      - title as fetched from metadata
    - After fetched
      - item description show son dashboard
    

## Out of Scope
  - Inbox
  - Streaming of changes in status to the front-end
    - No polling, events or streaming yet. Changes visible on update