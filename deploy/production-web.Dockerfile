# Build context is a verified copy of the currently running production /srv only.
# Never build this tag from the unapproved modernized web source.
FROM caddy:2-alpine@sha256:003a97808e781aa9f7e75cc2f43d34d461099031faf5e20faefb9f61126836f0
COPY srv /srv
