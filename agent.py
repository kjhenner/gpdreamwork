import os
import time
import threading
import re
import subprocess
from typing import List, Dict
from abc import ABC, abstractmethod

import openai
import yaml
import asyncio
import logging
from httpx import AsyncClient
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def parse_messages(response: str, sender: str) -> Dict[str, List[Dict]]:
    regex = r'@(\w+)'
    to = list(set(re.findall(regex, response)))

    formatted_messages = [
        {
            "from_": sender,
            "to": to,
            "content": response
        }
    ]
    return {"messages": formatted_messages}


async def backoff_helper(func, attempts=3, delay=1, backoff_factor=2):
    for attempt in range(attempts):
        try:
            return await func()
        except Exception as e:
            logger.exception(f"Attempt {attempt + 1} failed: {e}")
            if attempt == attempts - 1:
                raise e
            await asyncio.sleep(delay * (backoff_factor ** attempt))


class BaseAgent(ABC, threading.Thread):
    def __init__(self, id, server_host, server_port):
        super().__init__()
        self.id = id
        self.server_host = server_host
        self.server_port = server_port
        self.last_timestamp = 0

    @abstractmethod
    async def respond(self, body: str, sender: str):
        pass

    @abstractmethod
    async def agent_run(self):
        pass

    def run(self):
        asyncio.run(self.agent_run())


class ChatCompletionAgent(BaseAgent):

    def __init__(self, id, server_host, server_port, system_message_text):
        super().__init__(
            id=id,
            server_host=server_host,
            server_port=server_port,
        )
        self.messages = [{"role": "system", "content": system_message_text}]

    def add_message(self, role, content):
        self.messages.append({"role": role, "content": content})

    async def generate_text(self, max_tokens=1024):
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model='gpt-4',
                messages=self.messages,
                max_tokens=max_tokens
            )
        )
        return response["choices"][0]["message"]["content"]

    async def respond(self, body: str, sender: str):
        message_with_sender = f"{sender}: {body}"  # todo: Is this redundant?
        self.add_message("user", message_with_sender)
        response = await backoff_helper(lambda: self.generate_text())
        self.add_message("assistant", response)
        return response

    async def agent_run(self):
        async with AsyncClient() as client:
            while True:
                logger.debug(f"Agent {self.id} checking for new messages")
                new_timestamp = time.time()
                response = await client.get(
                    f"http://{self.server_host}:{self.server_port}/check_messages?timestamp={self.last_timestamp}"
                )
                self.last_timestamp = new_timestamp

                if not response.text:  # Check if the response body is empty
                    logger.debug(f"Agent {self.id} received no new messages")
                    time.sleep(3)
                    continue

                new_messages = response.json()

                for message in new_messages:
                    if self.id not in message["to"]:
                        continue
                    logger.debug(f"Agent {self.id} received message: {message['content']}")
                    response = await self.respond(message["content"], message["from"])
                    messages_to_send = parse_messages(response, self.id)

                    logger.debug(f"Agent {self.id} messages to send: {messages_to_send}")
                    await client.post(
                        f"http://{self.server_host}:{self.server_port}/send_messages",
                        json=messages_to_send
                    )
                time.sleep(3)


class BashAgent(BaseAgent):

    @staticmethod
    async def generate_text(command: str):
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: subprocess.check_output(command, shell=True).decode("utf-8")
        )
        return response

    async def respond(self, body: str, sender: str):
        command = re.sub(r'@\w+\s+', '', body)
        response = await backoff_helper(lambda: self.generate_text(command))
        return response

    async def agent_run(self):
        async with AsyncClient() as client:
            while True:
                logger.debug(f"Agent {self.id} checking for new messages")
                new_timestamp = time.time()
                response = await client.get(
                    f"http://{self.server_host}:{self.server_port}/check_messages?timestamp={self.last_timestamp}"
                )
                self.last_timestamp = new_timestamp

                if not response.text:  # Check if the response body is empty
                    logger.debug(f"Agent {self.id} received no new messages")
                    time.sleep(3)
                    continue

                new_messages = response.json()

                for message in new_messages:
                    if self.id not in message["to"]:
                        continue
                    logger.debug(f"Agent {self.id} received message: {message['content']}")
                    response = await self.respond(message["content"], message["from"])
                    messages_to_send = parse_messages(response, self.id)

                    logger.debug(f"Agent {self.id} messages to send: {messages_to_send}")
                    await client.post(
                        f"http://{self.server_host}:{self.server_port}/send_messages",
                        json=messages_to_send
                    )
                time.sleep(3)


def main():
    with open("agents_conf.yml", "r") as f:
        config = yaml.safe_load(f)

    agents = {}
    for agent_conf in config["agents"]:
        if agent_conf["type"] == "chat_completion":
            agent = ChatCompletionAgent(
                agent_conf["id"],
                config["server_host"],
                config["server_port"],
                agent_conf["system_message_text"],
            )
        elif agent_conf["type"] == "bash":
            agent = BashAgent(
                agent_conf["id"],
                config["server_host"],
                config["server_port"],
            )
        else:
            continue

        agents[agent_conf["id"]] = agent
        logger.info(f"Starting agent {agent_conf['id']}")
        agent.start()

    for agent in agents.values():
        agent.join()


if __name__ == "__main__":
    main()