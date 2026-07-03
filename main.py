import os
from collections import defaultdict
import hashlib

import discord
from discord import app_commands
from dotenv import load_dotenv

# 1. Default fallback constant
DEFAULT_LIMIT = 100

load_dotenv()

# 2. Extract true limit from environment variable
try:
    MSG_LIMIT = int(os.getenv("SPAM_SCAN_LIMIT", DEFAULT_LIMIT))
except ValueError:
    MSG_LIMIT = DEFAULT_LIMIT


class SpamScanner(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synchronized.")


bot = SpamScanner()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.tree.command(name="detect", description="Collect attachments, calculate MD5 hashes, and score spammers")
async def detect(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    channels = interaction.guild.text_channels
    print(f"\n--- STARTING DATA COLLECTION (History limit: {MSG_LIMIT}) ---")
    
    attachments = defaultdict(list)
    
    for channel in channels:
        processed_users_in_channel = set()
        
        try:
            async for message in channel.history(limit=MSG_LIMIT):
                if message.author.bot:
                    continue
                
                user = message.author.name
                
                if user in processed_users_in_channel:
                    continue
                
                processed_users_in_channel.add(user)
                
                if message.attachments:
                    for attachment in message.attachments:
                        try:
                            # Read the attachment bytes directly from Discord's CDN
                            file_bytes = await attachment.read()
                            
                            # Compute the MD5 hash of the file content
                            file_md5 = hashlib.md5(file_bytes).hexdigest()
                            
                            attachments[user].append({
                                "filename": attachment.filename,
                                "md5": file_md5,  
                                "channel": f"#{channel.name}"
                            })
                            print(f"[Collected] {user} in #{channel.name} -> {attachment.filename} (MD5: {file_md5})")
                        except (discord.HTTPException, discord.NotFound) as download_err:
                            print(f"  [Error: Could not download attachment {attachment.filename}: {download_err}]")
                            
        except discord.Forbidden:
            print(f"  [Error: Missing permissions for #{channel.name}]")
        except discord.HTTPException as e:
            print(f"  [API Error in #{channel.name}: {e}]")
            
    print("\n--- PROCESSING SCORES ---")
    
    suspect_list = []
    
    for user, file_list in attachments.items():
        # Using MD5 to accurately track identical images across channels
        seen_hashes = set()
        score = 0
        
        for file_data in file_list:
            file_hash = file_data["md5"]
            
            if file_hash in seen_hashes:
                score += 2
            else:
                seen_hashes.add(file_hash)
                score += 1
                
        print(f"User: {user} | Total Attachments: {len(file_list)} | Final Score: {score}")
        
        if score >= 1:
            suspect_list.append(dict(user=user, score=score, attachments=file_list))
            
    print("\n--- SCAN COMPLETE ---")
    
    if suspect_list:
        report = "**Suspected Spammers (Cross-channel image duplicates):**\n" + "\n".join([
            f"- **{suspect['user']}** (Score: {suspect['score']}, Attachments: {len(suspect['attachments'])})"
            for suspect in sorted(suspect_list, key=lambda x: x['score'], reverse=True)
        ])
    else:
        report = "Scan finished. No cross-channel image spammers detected."
        
    await interaction.followup.send(report, ephemeral=True)


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Error: DISCORD_TOKEN not found in environment.")
    else:
        bot.run(token)
