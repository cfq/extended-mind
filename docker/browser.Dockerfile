# Headless Chromium as a Playwright server; the worker connects over a
# websocket. The package version must match the image's browsers and
# the app's playwright package.
FROM mcr.microsoft.com/playwright/python:v1.65.2-noble
RUN pip install --no-cache-dir --break-system-packages playwright==1.65.2
USER pwuser
EXPOSE 3000
CMD ["playwright", "run-server", "--port", "3000", "--host", "0.0.0.0"]
