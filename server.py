import logging
import time
from typing import List, Dict, Optional

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add the following code to enable CORS
origins = [
    "*",  # Update this with your frontend's origin
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    from_: str
    to: List[str]
    content: str


class MessageStore:
    def __init__(self):
        self.messages = []

    async def put(self, message: Message):
        timestamp = time.time()  # todo: Race condition?
        self.messages.append(
            {
                "from": message.from_,
                "to": message.to,
                "content": message.content,
                "timestamp": timestamp,
            }
        )

    async def get(self, timestamp: Optional[float] = None):
        if timestamp:
            response = [msg for msg in self.messages if msg["timestamp"] > timestamp]
        else:
            response = self.messages
        return response


message_store = MessageStore()


@app.post("/send_messages")
async def send_messages(data: Dict[str, List[Message]]):
    messages = data.get('messages', [])
    for message in messages:
        logger.debug(f"Received message from {message.from_}: {message}")
        await message_store.put(message)
    return {"detail": "Messages received"}


@app.get("/check_messages")
async def check_messages(timestamp: Optional[float] = None):
    messages = [message for message in await message_store.get(timestamp)]
    logger.debug(f"Returning messages: {messages}")
    return messages


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=12345, log_level="debug")