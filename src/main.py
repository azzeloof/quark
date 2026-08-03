"""
QUARK -- QUeued Asynchronous Request Keeper
main.py
Adam Zeloof
8/2/2026
"""

import json  #merrin
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlmodel import Field, Session, SQLModel, create_engine, select

###### DB Structure ######

class Topic(SQLModel, table=True):
    name: str = Field(primary_key=True)
    current_sequence_id: int = Field(default=0)
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))

class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    topic_name: str = Field(foreign_key="topic.name")
    topic_sequence_id: int = Field()
    payload: str = Field()
    client_ip: str | None = Field(default=None, index=True)
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))


###### DB Initialization and Helpers ######

sqlite_file_name = "data/quark_data.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


###### API Definition ######

app = FastAPI()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def validate_api_key(api_key: str = Security(api_key_header)):
    expected_key = os.environ.get("QUARK_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Server API Key is not configured."
        )
    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )
    return api_key

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]
APIKeyDep = Annotated[str, Depends(validate_api_key)]

def get_or_create_topic(name: str, session: Session) -> Topic:
    query = select(Topic).where(Topic.name == name)
    result = session.exec(query).first()
    if result is not None:
        return result
    else:
        new_topic = Topic(name=name, current_sequence_id=0)
        session.add(new_topic)
        return new_topic

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

@app.post("/submit")
def queue_message(
    payload: dict[str, Any],
    request: Request,
    session: SessionDep, # type: ignore
    api_key: APIKeyDep,
    topic: str = "default"
):
    db_topic = get_or_create_topic(topic, session)
    session.add(db_topic)
    raw_ip = request.client.host if request.client else None
    client_ip = request.headers.get("X-Forwarded-For", raw_ip)
    payload_string = json.dumps(payload)
    new_message = Message(
        topic_name=topic,
        topic_sequence_id=db_topic.current_sequence_id,
        payload=payload_string,
        client_ip=client_ip
    )
    session.add(new_message)
    db_topic.current_sequence_id += 1
    session.commit()
    return {"status": "queued", "topic": topic, "id": db_topic.current_sequence_id}

@app.get("/messages")
def get_messages(
    session: SessionDep, # type: ignore
    api_key: APIKeyDep, 
    topic: str = "default",
    index: int = 0,
    max_index: int | None = None
):
    query = (
        select(Message)
        .where(Message.topic_name == topic)
        .where(Message.topic_sequence_id >= index)
        .order_by(Message.topic_sequence_id)
    )
    if max_index is not None:
        query = query.where(Message.topic_sequence_id <= max_index)
    messages = session.exec(query).all()
    formatted_response = []
    for msg in messages:
        msg_dict = msg.model_dump(exclude={'id', 'topic_sequence_id'})
        msg_dict['id'] = msg.topic_sequence_id
        try:
            msg_dict['payload'] = json.loads(msg.payload)
        except json.JSONDecodeError as e:
            msg_dict['payload'] = {"JSON Error": e, "raw_text": msg.payload}
        formatted_response.append(msg_dict)
    return formatted_response

@app.get("/topics")
def get_topics(session: SessionDep, api_key: APIKeyDep, ): # type: ignore
    query = select(Topic)
    topics = session.exec(query).all()
    formatted_response = []
    for topic in topics:
        topic_dict = topic.model_dump(exclude={'id'})
        formatted_response.append(topic_dict)
    return formatted_response
