import discord
import os
from dotenv import load_dotenv
load_dotenv()

# Botのトークンを環境変数から取得
# ローカルでテストする際は、一時的に 'YOUR_DISCORD_TOKEN' を実際のトークンに置き換えても良い
# ただし、このファイルをGitにコミットする前に必ず環境変数を使う方式に戻してください
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
print(DISCORD_TOKEN)

# Intentsの設定
intents = discord.Intents.default()
intents.message_content = True  # メッセージの内容を読み取るために必要

# Botオブジェクトの生成
client = discord.Client(intents=intents)

# Botが起動したときに実行されるイベント
@client.event
async def on_ready():
    print(f'{client.user} としてログインしました')

# メッセージが送信されたときに実行されるイベント
@client.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author == client.user:
        return

    # 'こんにちは' というメッセージに応答
    if message.content == 'こんにちは':
        await message.channel.send('こんにちは！')

# Botの起動
client.run(DISCORD_TOKEN)