# QUARK
#### QUeued Asynchronous Request Keeper

# QUARK API

[![Lint](https://github.com/azzeloof/quark/actions/workflows/lint.yml/badge.svg)](https://github.com/azzeloof/quark/actions/workflows/lint.yml)
[![Test](https://github.com/azzeloof/quark/actions/workflows/test.yml/badge.svg)](https://github.com/azzeloof/quark/actions/workflows/test.yml)
[![Publish](https://github.com/azzeloof/quark/actions/workflows/publish.yml/badge.svg)](https://github.com/azzeloof/quark/actions/workflows/publish.yml)

## Problem
We want to have a web form that posts data to a server, but the server in question is on an arbitrary network that we don't own, and cannot forward ports through.

## Goal
An intermediate API that accepts POST requests to ingest arbitrary data, which it stores in a database. A client can request all messages it hasn't seen with a GET request, optionally passing in a "cursor" or index of the last message it's seen.

## Architecture
Dockerized python script that uses FastAPI, with a SQLite database (or the option to plug in a SQL database such as Postgres running in a different docker container, but I haven't added that yet).

## How to use
Everything is packaged into a handy-dandy container (i barely know 'er!). Create a .env file with `QUARK_API_KEY = BUNCHOFCHARACTERS`, then run `docker-compose up -d`
(You can also change the port mapping in the compose file)
Once it's running, documentation can be found at `http://<ip or domain>:8000/docs`, but in summary:

- To write a new message to the 'pizza' topic:
```
  curl -X POST "http://127.0.0.1:8000/submit?topic_name=pizza" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: my_super_secret_key" \
     -d '{"message": "i like pasta", "color", "red", "number_of_meatballs": 6}'
```

- To read messages in the 'pizza' topic after message '3':
```
  curl -X GET "http://127.0.0.1:8000/messages?topic=pizza&index=3" \
     -H "X-API-Key: my_super_secret_key" 
```

To actually receive data, just poll your chosen topic periodically. Each time you poll, keep track of the highest index, so the next time you poll you know how to set the index.
