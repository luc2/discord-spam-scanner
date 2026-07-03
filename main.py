import os
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()


class SpamScanner(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("Commandes slash synchronisées !")


bot = SpamScanner()


@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")


@bot.tree.command(name="detect", description="Vérifie si le salon est infesté de spam")
async def detect(interaction: discord.Interaction):
    # await interaction.response.send_message("Hello World !", ephemeral=True)
    channels = interaction.guild.text_channels
    channels_string = "\n".join([f"- {c.name} (ID: {c.id})" for c in channels])
    response_text = f"**Liste des canaux textuels :**\n{channels_string}"
    await interaction.response.send_message(response_text, ephemeral=True)


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Erreur : DISCORD_TOKEN introuvable dans l'environnement.")
    else:
        bot.run(token)
