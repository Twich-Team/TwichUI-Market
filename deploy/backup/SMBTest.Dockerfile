FROM alpine:3.22
RUN apk add --no-cache samba samba-common-tools && adduser -D -u 1000 nas && mkdir -p /share /samba /run/samba /var/cache/samba /var/log/samba && chown -R nas:nas /share /samba /run/samba /var/cache/samba /var/log/samba
COPY deploy/backup/smb-test.conf /etc/samba/smb.conf
RUN printf 'synthetic-nas-test-only\nsynthetic-nas-test-only\n' | smbpasswd -s -a nas && chown -R nas:nas /samba
USER 1000:1000
ENTRYPOINT ["smbd","--foreground","--no-process-group","--debug-stdout","--configfile=/etc/samba/smb.conf"]
