#!/bin/sh -x

rm -rf /tmp/clickwork-backup
mkdir /tmp/clickwork-backup
pg_dump -U postgres clickwork > /tmp/clickwork-backup/clickwork.db
cp -r /clickwork/ /tmp/clickwork-backup/clickwork
rm /var/backups/clickwork/clickwork.tar.gz
tar -zvcf /var/backups/clickwork/clickwork.tar.gz /tmp/clickwork-backup

