import os
from collections import defaultdict

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


@bot.tree.command(name="detect", description="Collect attachments and calculate spam scores")
async def detect(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    channels = interaction.guild.text_channels
    print(f"\n--- STARTING DATA COLLECTION (History limit: {MSG_LIMIT}) ---")
    
    # Structure requested: { "Username": [{"filename": "...", "md5": "...", "channel": "..."}] }
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
                        # Storing MD5 placeholder as "123" for now since discord.py doesn't provide it directly
                        attachments[user].append({
                            "filename": attachment.filename,
                            "md5": "123",  
                            "channel": f"#{channel.name}"
                        })
                        print(f"[Collected] Recorded attachment from {user} in #{channel.name}")
                            
        except discord.Forbidden:
            print(f"  [Error: Missing permissions for #{channel.name}]")
        except discord.HTTPException as e:
            print(f"  [API Error in #{channel.name}: {e}]")
            
    print("\n--- PROCESSING SCORES ---")
    
    guilty_list = []
    
    # Calculate scores at the end based on the collected structure
    for user, file_list in attachments.items():
        # Track unique files seen for this user across channels using filename
        # (Can be switched to MD5 later when hash calculation is added)
        seen_files = set()
        score = 0
        
        for file_data in file_list:
            file_id = file_data["filename"]
            
            if file_id in seen_files:
                score += 2
            else:
                seen_files.add(file_id)
                score += 1
                
        print(f"User: {user} | Total Attachments: {len(file_list)} | Final Score: {score}")
        
        if score >= 1:
            guilty_list.append(f"- **{user}** (Score: {score})")
            
    print("\n--- SCAN COMPLETE ---")
    
    if guilty_list:
        report = "**Suspected Spammers (Cross-channel image duplicates):**\n" + "\n".join(guilty_list)
    else:
        report = "Scan finished. No cross-channel image spammers detected."
        
    await interaction.followup.send(report, ephemeral=True)


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Error: DISCORD_TOKEN not found in environment.")
    else:
        bot.run(token)
