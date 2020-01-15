#!/bin/sh
dropdb --if-exists bf_metronom
createdb bf_metronom
ssh root@workbench.feinheit.ch "sudo -u postgres pg_dump -Ox bf_metronom" | psql bf_metronom
