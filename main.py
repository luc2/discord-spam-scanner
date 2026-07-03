import hashlib
import os
from collections import defaultdict
from typing import Dict, List, Set

import discord
from discord import app_commands
from dotenv import load_dotenv

DEFAULT_LIMIT = 100

load_dotenv()


def get_message_history_limit() -> int:
    raw_value = os.getenv("SPAM_SCAN_LIMIT", str(DEFAULT_LIMIT))
    try:
        return int(raw_value)
    except ValueError:
        return DEFAULT_LIMIT


MSG_LIMIT = get_message_history_limit()


def calculate_md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


async def get_attachment_md5(attachment: discord.Attachment) -> str:
    return calculate_md5(await attachment.read())


def compute_attachment_score(files: List[Dict[str, str]]) -> int:
    seen_hashes: Set[str] = set()
    score = 0

    for file_record in files:
        hash_value = file_record["md5"]
        if hash_value in seen_hashes:
            score += 2
        else:
            seen_hashes.add(hash_value)
            score += 1

    return score


def build_report(suspects: List[Dict[str, object]]) -> str:
    if not suspects:
        return "Scan finished. No cross-channel image spammers detected."

    lines = ["**Suspected Spammers (Cross-channel image duplicates):**"]
    sorted_suspects = sorted(suspects, key=lambda item: item["score"], reverse=True)

    for suspect in sorted_suspects:
        lines.append(
            f"- **{suspect['user']}** (Score: {suspect['score']}, Attachments: {len(suspect['attachments'])})"
        )

    return "\n".join(lines)


async def collect_attachments(channel: discord.TextChannel) -> Dict[str, List[Dict[str, str]]]:
    result: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    processed_users: Set[str] = set()

    async for message in channel.history(limit=MSG_LIMIT):
        if message.author.bot:
            continue

        username = message.author.name
        if username in processed_users:
            continue

        processed_users.add(username)

        for attachment in message.attachments:
            try:
                attachment_md5 = await get_attachment_md5(attachment)
                result[username].append({
                    "username": username,
                    "channel": f"#{channel.name}",
                    "filename": attachment.filename,
                    "md5": attachment_md5,
                })
                print(
                    f"[Collected] {username} in #{channel.name} -> {attachment.filename} "
                    f"(MD5: {attachment_md5})"
                )
            except (discord.HTTPException, discord.NotFound) as error:
                print(f"  [Error: Could not download attachment {attachment.filename}: {error}]")

    return result


async def collect_all_attachments(channels: List[discord.TextChannel]) -> Dict[str, List[Dict[str, str]]]:
    print(f"--- STARTING DATA COLLECTION (History limit: {MSG_LIMIT}) ---")

    all_attachments: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    for channel in channels:
        try:
            channel_attachments = await collect_attachments(channel)
            for username, attachment_list in channel_attachments.items():
                all_attachments[username].extend(attachment_list)
        except discord.Forbidden:
            print(f"  [Error: Missing permissions for #{channel.name}]")
        except discord.HTTPException as error:
            print(f"  [API Error in #{channel.name}: {error}]")

    return all_attachments


def build_suspect_list(all_attachments: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, object]]:
    print("\n--- PROCESSING SCORES ---")

    suspects: List[Dict[str, object]] = []

    for username, attachment_list in all_attachments.items():
        score = compute_attachment_score(attachment_list)
        print(
            f"User: {username} | Total Attachments: {len(attachment_list)} | Final Score: {score}"
        )

        if score >= 1:
            suspects.append(
                {
                    "user": username,
                    "score": score,
                    "attachments": attachment_list,
                }
            )

    return suspects


async def send_scan_report(interaction: discord.Interaction, suspects: List[Dict[str, object]]) -> None:
    print("\n--- SENDING REPORT ---")
    report = build_report(suspects)
    await interaction.followup.send(report, ephemeral=True)


class SpamScanner(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()
        print("Slash commands synchronized.")


bot = SpamScanner()


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user}")


@bot.tree.command(
    name="detect",
    description="Collect attachments, calculate MD5 hashes, and score spammers",
)
async def detect(interaction: discord.Interaction) -> None:
    print(f"\n--- /detect requested by {interaction.user.name} ---")
 
    await interaction.response.defer(ephemeral=True)
 
    all_attachments = await collect_all_attachments(interaction.guild.text_channels)
    suspects = build_suspect_list(all_attachments)
    await send_scan_report(interaction, suspects)


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Error: DISCORD_TOKEN not found in environment.")
    else:
        bot.run(token)
