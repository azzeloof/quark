# QUARK: QUeued Asynchronous Request Keeper

[![Lint](https://github.com/azzeloof/quark/actions/workflows/lint.yml/badge.svg)](https://github.com/azzeloof/quark/actions/workflows/lint.yml)
[![Test](https://github.com/azzeloof/quark/actions/workflows/test.yml/badge.svg)](https://github.com/azzeloof/quark/actions/workflows/test.yml)
[![Publish](https://github.com/azzeloof/quark/actions/workflows/publish.yml/badge.svg)](https://github.com/azzeloof/quark/actions/workflows/publish.yml)

## Problem
We want to have a web form that posts data to a server, but the server in question is on an arbitrary network that we don't own, and cannot forward ports through. 

## Solution
An intermediate API that accepts POST requests to ingest arbitrary data, which it stores in a database. A client can request all messages it hasn't seen with a GET request, optionally passing in a "cursor" or index of the last message it's seen. This acts as a "chunked queue" where incoming messages are stored in a queue that is retrieved in ordered chunks. This is useful for applications like Unity where the polling logic can be incorporated into a main loop, where threading is a pain, and when web sockets are infeasible due to firewalls. 


## Architecture
Dockerized python script that uses FastAPI, with a SQLite database (or the option to plug in a SQL database such as Postgres running in a different docker container, or a different server).

```mermaid
graph LR
    %% Define Subgraphs for visual grouping
    subgraph External [External Data Sources]
        P1[Publisher 1\n e.g. Web Form]
        P2[Publisher 2\n e.g. Python Script]
        P3[Publisher 3\n e.g. IoT Sensor]
    end

    subgraph QUARK [QUARK Server]
        API(FastAPI Router)

        subgraph DB [SQL Database]
            direction TB
            Topics[(Topic Table)]
            Messages[(Message Table)]
            
            Topics -. "1 : Many" .- Messages
        end
        
        API -- "Tracks Sequence IDs" --> Topics
        API <-- "Stores & Retrieves" --> Messages
    end

    subgraph Protected [Firewalled Network]
        C1[Client 1\n e.g. Unity Application]
        C2[Client 2\n e.g Python Script]
    end

    C3[Client 3\n e.g. Another Server]
    QUARK ~~~ C3
    QUARK ~~~ Protected
    DB ~~~ C3

    %% Define Connections and Annotations
    P1 -- "POST /submit" --> API
    P2 -- "POST /submit" --> API
    P3 -- "POST /submit" --> API

    API -. "GET /messages (Polling)" .-> C1
    API -. "GET /messages (Polling)" .-> C2
    API -. "GET /messages (Polling)" .-> C3

    %% Styling for the Firewall
    style Protected fill:#f4f4f4,stroke:#ff4757,stroke-width:2px,stroke-dasharray: 5 5
    style QUARK fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px
```


## How to use
Everything is packaged into a handy-dandy container (i barely know 'er!). Create a .env file with the following (depending on whether you want to use an external database such as postgres, or a local SQLite db file):
```
QUARK_API_KEY="secret_api_key"
# If you just want to use a local SQLite db, you can exclude the remaining lines. If you're connecting to an existing remote db, keep the URL line below and edit accordingly, but you can get rid of the POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB lines.
QUARK_DB_URL="postgresql://myuser:mysecretpassword@db:5432/quarkdb"
POSTGRES_USER="myuser"
POSTGRES_PASSWORD="mysecretpassword"
POSTGRES_DB="quarkdb"
```
If you're using a SQLite db, make sure the postgres lines in the docker-compose.yml are commented out. Similarly, there's no need to mount a data volume for the Quark service if you're using a separate db. 
Then run `docker-compose up -d` 
Once it's running, documentation can be found at `http://<ip or domain>:8000/docs`, but in summary:

- To write a new message to the 'pizza' topic:
```
  curl -X POST "http://127.0.0.1:8000/submit?topic_name=pizza" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: my_super_secret_key" \
     -d '{"message": "i like pasta", "color", "red", "number_of_meatballs": 6}'
```
You can also optionally include a `max_index` if you only want to grab a specific number of messages in a chunk. If no topic is included, it is assumed to be `default`. If a topic does not yet exist, it is created.

- To read messages in the 'pizza' topic after message '3':
```
  curl -X GET "http://127.0.0.1:8000/messages?topic=pizza&index=3" \
     -H "X-API-Key: my_super_secret_key" 
```
- There is also a `/topics` endpoint that returns a list of available topics and the current index for each.

To actually receive data, just poll your chosen topic periodically. Each time you poll, keep track of the highest index, so the next time you poll you know how to set the index.
Here's a diagram that shows an example workflow with one publisher and one client:

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant Q as QUARK API
    participant DB as SQL Database
    participant P as Publisher (e.g. Web Form)

    Note over C: Client Boots.<br/>next_expected_index = 0

    Note over DB: Already contains three messages
    
    C->>+Q: GET /messages?topic=pizza&index=0
    Q->>DB: Query WHERE id >= 0
    DB-->>Q: [Msg 0, Msg 1, Msg 2]
    Q-->>-C: JSON Array (3 items)
    
    Note over C: Client processes chunk.<br/>Updates next_expected_index = 3
    
    C->>+Q: GET /messages?topic=pizza&index=3
    Q->>DB: Query WHERE id >= 3
    DB-->>Q: No results
    Q-->>-C: Empty JSON Array []
    
    
    P->>+Q: POST /submit?topic=pizza (Msg 3)
    Q->>DB: Insert Message
    DB-->>Q: Success
    Q-->>-P: {"status": "queued", "id": 3}

    P->>+Q: POST /submit?topic=pizza (Msg 4)
    Q->>DB: Insert Message
    DB-->>Q: Success
    Q-->>-P: {"status": "queued", "id": 4}
    
    Note over C: Client polling loop fires (e.g. 5 seconds later)
    
    C->>+Q: GET /messages?topic=pizza&index=3
    Q->>DB: Query WHERE id >= 3
    DB-->>Q: [Msg 3, Msg 4]
    Q-->>-C: JSON Array (2 items)
    
    Note over C: Client processes chunk.<br/>Updates next_expected_index = 5
```
