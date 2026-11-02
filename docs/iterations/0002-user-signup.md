# Iteration 0002 - User Sign-up

## A User management flow for the application.

- Login page
- Sign up page

- Out of scope
  - Forgot passoword
    - Don't want to worry about emails now
  - Password rules
    - We'll worry about this later. No need for now.
    - Use Django defaults, and indicate in copy as well
  - Profile details
    - We'll embellish the profile later on with names, avatars.
  - Testing and linting
  - Design
    - Come up with a basic design of your own for now


## Decisions:
  - Email and password for logging in
    - lowercase all emails
    - email for logging into /admin as well
  - Signup page asks for a username
    - After signup redirects to login
  - /login, /logout, /signup
    - Everything else behind login
  - /logout redirects back to /login
  - /user/{username} 
    - isomorphic naming for all users 
    - user's profile page as well, no /me
    - shows username for now
  - Brings us to / and says welcome {username}
    - There's a logout button too
  - Dev: `frontend` Compose service runs Vite, proxies `/api` and `/admin` to Django
  - Prod: Node build stage in the Dockerfile; Django serves the built SPA, with a catch-all to `index.html` for SPA routes.
  - Default ports for Vite (5173) and Django (8000)


## Backend:
  - User model and API pages
  - App: `apps/users/`.
  - Custom user model for futureproofing
    - User model: `AbstractUser` subclass, unique `email` as login, unique `username`.
  - /api/v1/auth/session for logged in session
  - SIGNUP_ENABLED env var to enable/disable new signups
  - API under `/api/v1/auth/`: `GET csrf`, `POST signup`, `POST login`, `POST logout`, `GET session`. Session cookie + CSRF.
  - GET /api/v1/users/{username} for user info


## Frontend:
  - /frontend/ directory
  - Typescript
  - React + React Router
  - node 24 LTS
  - npm
  - TanStack Query
  - plain CSS
  - vite
  - node build and dev in dockerfile and makefile

---

## Claude Notes

Small decisions:
- `GET /api/v1/users/{username}` added for the profile page (login required).
- `SIGNUP_ENABLED` defaults to off; `.env.example` turns it on.
- Signup validates via `full_clean` (email/username format + uniqueness) and Django's default password validators; errors joined into one message.
- Login and signup endpoints don't check CSRF (Ninja only checks it on authenticated endpoints). Low risk for now.
- Unknown routes behind login show "Not found"; logged out, everything redirects to `/login`.
- Built SPA lives at `/opt/frontend`; whitenoise serves its assets, a Django catch-all serves `index.html`.
- `frontend` dev container runs as UID 1000 (host user), `node_modules` lives in `frontend/` on the host.
- Vite `allowedHosts: true` in dev, so any hostname works.
- `/api/v1/users/` vs `/user/` pages: API resources plural, page URLs as specced.
