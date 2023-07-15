#!/bin/bash

docker exec -it images_management-db-1 pg_dump -U admin -d russian_poetry > backup.sql
