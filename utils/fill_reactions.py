#!/usr/bin/env python3
"""
Fill a Telegram chat-export JSON with complete reaction lists.
Requirements: pip install Telethon==1.42
"""
import asyncio
import json
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetMessageReactionsListRequest
from telethon.tl.types import InputPeerChat, PeerChannel, PeerUser, ReactionCustomEmoji, ReactionEmoji, MessagePeerReaction
from telethon.tl.types.messages import MessageReactionsList

SESSION_FILE: str = "fill_reactions_session"
FETCH_LIMIT: int = 50
REQUEST_DELAY: float = 2.0

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def build_reactions(reactions: list[MessagePeerReaction]) -> list[dict]:
    grouped: dict[tuple[str, str], list[MessagePeerReaction]] = defaultdict(list)
    for pr in reactions:
        if isinstance(pr.reaction, ReactionEmoji):
            grouped[("emoji", pr.reaction.emoticon)].append(pr)
        elif isinstance(pr.reaction, ReactionCustomEmoji):
            grouped[("custom_emoji", str(pr.reaction.document_id))].append(pr)

    out = []
    for (rtype, value), peers in grouped.items():
        entry: dict = {"type": rtype}
        if rtype == "emoji":
            entry["emoji"] = value
        elif rtype == "custom_emoji":
            entry["document_id"] = value
        entry["count"] = 0
        entry["recent"] = []
        for pr in peers:
            if isinstance(pr.peer_id, PeerUser):
                entry["count"] += 1
                entry["recent"].append({
                    "from": "",
                    "from_id": f"user{pr.peer_id.user_id}",
                    "date": pr.date.astimezone().strftime("%Y-%m-%dT%H:%M:%S")
                })
        out.append(entry)
    return out


async def process(client: TelegramClient, src: Path, dst: Path):
    logger.info("Reading %s", src)
    data = json.loads(src.read_text("utf-8"))

    chat_type, chat_id = data.get("type", ""), data.get("id", 0)
    if chat_type not in ("private_group", "private_supergroup"):
        logger.error("Unsupported chat type %s", chat_type)
        return data

    await client.get_dialogs()  # populate entity cache

    try:
        peer = InputPeerChat(chat_id) if chat_type == "private_group" else await client.get_input_entity(PeerChannel(chat_id))
    except Exception as exc:
        logger.error("Cannot resolve peer: %s", exc)
        return data

    messages = data.get("messages", [])
    targets = [m for m in messages
               if any(r.get("count", 0) > len(r.get("recent", []))
                      or (r.get('type', '') == 'custom_emoji' and not r.get('document_id', '').isdigit())
                      for r in m.get("reactions", []))
               ]
    logger.info("Filling reactions for %d out of %d messages", len(targets), len(messages))

    msgs_filled = msgs_failed = 0
    last_request_at = 0.0
    for msg in reversed(targets):  # fill newer messages first
        await asyncio.sleep(max(0.0, REQUEST_DELAY - (time.monotonic() - last_request_at)))
        last_request_at = time.monotonic()

        msg_id = msg["id"]
        rcts_expected = sum(r.get("count", 0) for r in msg.get("reactions", []))

        try:
            result: MessageReactionsList = await client(GetMessageReactionsListRequest(peer=peer, id=msg_id, limit=FETCH_LIMIT))
        except FloodWaitError as exc:
            logger.warning("Message %d: flood wait %ds", msg_id, exc.seconds)
            await asyncio.sleep(exc.seconds)
            try:
                result = await client(GetMessageReactionsListRequest(peer=peer, id=msg_id, limit=FETCH_LIMIT))
            except Exception as exc2:
                logger.error("Message %d: API error after flood wait: %s", msg_id, exc2)
                msgs_failed += 1
                continue
        except Exception as exc:
            logger.error("Message %d: API error: %s", msg_id, exc)
            msgs_failed += 1
            continue

        if not result.reactions:
            logger.warning("Message %d: got 0 reactions, skipping", msg_id)
            msgs_failed += 1
            continue

        if len(result.reactions) < result.count:
            logger.warning("Message %d: only got %d reactions out of %d in total", msg_id, len(result.reactions), result.count)

        msg["reactions"] = build_reactions(result.reactions)
        rcts_filled = sum(r["count"] for r in msg["reactions"])
        msgs_filled += 1
        logger.info("Message %d (%d/%d): filled %d reactions out of %d",
                    msg_id, msgs_filled, len(targets), rcts_filled, rcts_expected)
        if msgs_filled % 50 == 0 or msgs_filled == len(targets):
            logger.info("Writing %s...", dst)
            dst.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", "utf-8")

    logger.info("%d messages filled, %d failed", msgs_filled, msgs_failed)


async def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input.json> <output.json>")
        sys.exit(1)

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])

    print("Message reaction data can only be accessed via Telegram Application API.")
    print("Follow the instructions at https://core.telegram.org/api/obtaining_api_id to obtain API credentials.")
    api_id = int(input("API_ID: "))
    api_hash = input("API_HASH: ").strip()

    client = TelegramClient(SESSION_FILE, api_id, api_hash)
    await client.start()
    try:
        await process(client, src, dst)
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
