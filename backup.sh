#!/bin/bash

docker exec -it images_management-db-1 pg_dump -U admin -d russian_poetry > backup.sql

docker exec -it images_management-db-1 pg_dump -U admin -d ukranian_poetry > backup_ua.sql

docker exec -it images_management-db-1 pg_dump -U admin -d english_poetry > backup_en.sql