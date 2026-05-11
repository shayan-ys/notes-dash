FROM python:3.12-alpine

RUN apk add --no-cache git busybox-suid

WORKDIR /app
COPY build_manifest.py index.html favicon.svg entrypoint.sh /app/
COPY crontab /etc/crontabs/root

RUN chmod +x /app/entrypoint.sh /app/build_manifest.py

ENV NOTES_REPO_DIR=/var/lib/notes-dash/repo \
    NOTES_OUT_DIR=/var/lib/notes-dash/public

EXPOSE 8181

CMD ["/app/entrypoint.sh"]
