import os
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


@bot.tree.command(name="detect", description="Scan channels and print the latest messages in the terminal")
async def detect(interaction: discord.Interaction):
    # await interaction.response.send_message("Hello World !", ephemeral=True)

    # channels = interaction.guild.text_channels
    # channels_string = "\n".join([f"- {c.name} (ID: {c.id})" for c in channels])
    # response_text = f"**Liste des canaux textuels :**\n{channels_string}"
    # await interaction.response.send_message(response_text, ephemeral=True)

    # Acknowledge the interaction immediately to prevent 3-second timeouts
    await interaction.response.defer(ephemeral=True)

    channels = interaction.guild.text_channels
    print(f"\n--- STARTING CHANNEL SCAN (Limit per channel: {MSG_LIMIT}) ---")
    
    for channel in channels:
        print(f"\n[Channel: #{channel.name}]")
        try:
            # 3. Stream and print history to the terminal only
            async for message in channel.history(limit=MSG_LIMIT):
                timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                print(f"  - [{timestamp}] [{message.author.name}]: {message.content[:50]}")
        except discord.Forbidden:
            print("  [Error: Missing permissions to read this channel]")
        except discord.HTTPException as e:
            print(f"  [API Error: {e}]")
            
    print("\n--- SCAN COMPLETE ---")
    
    # Send the single allowed response interaction once backend tasks finish
    await interaction.followup.send(
        f"Scan complete! Check the terminal for logs (Limit: {MSG_LIMIT} messages).", 
        ephemeral=True
    )


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Error: DISCORD_TOKEN not found in environment.")
    else:
        bot.run(token)
