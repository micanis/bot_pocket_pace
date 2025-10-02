import os
import discord
import requests
import json
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime, timezone
import calendar

# .envファイルから環境変数を読み込む
load_dotenv()

# --- 定数 ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_NAMESPACE_ID = os.getenv('CF_NAMESPACE_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')

DEFAULT_ACCOUNT_DATA = {
    "base_income": 0,
    "extra_incomes": [],
    "spending": {
        "fixed_costs": [],
        "daily_spends": []
    },
    "savings_goal": 0,
    "settings": {
        "calculation_period": "7day"
    }
}

# --- Cloudflare KV Manager ---
# (省略: 前回と同じ)
class KVManager:
    def __init__(self, account_id, namespace_id, api_token):
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values"
        self.headers = { "Authorization": f"Bearer {api_token}" }

    def get_account_data(self, user_id):
        try:
            url = f"{self.base_url}/{user_id}"
            response = requests.get(url, headers=self.headers)
            if response.status_code == 404:
                print(f"ユーザー(ID: {user_id})のデータが見つかりません。新規データを作成します。")
                return DEFAULT_ACCOUNT_DATA.copy()
            response.raise_for_status()
            return json.loads(response.text)
        except requests.exceptions.RequestException as e:
            print(f"エラー: データの取得に失敗しました - {e}")
            return None

    def set_account_data(self, user_id, data):
        try:
            url = f"{self.base_url}/{user_id}"
            response = requests.put(url, headers=self.headers, data=json.dumps(data, indent=2, ensure_ascii=False))
            response.raise_for_status()
            print(f"ユーザー(ID: {user_id})のデータを保存しました。")
            return True
        except requests.exceptions.RequestException as e:
            print(f"エラー: データの保存に失敗しました - {e}")
            return False
    
    def list_all_user_ids(self):
        """KVに入っているすべてのユーザーIDのリストを取得する"""
        try:
            url = f"{self.base_url}/keys"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            if result.get("success"):
                return [key["name"] for key in result.get("result", [])]
            return []
        except requests.exceptions.RequestException as e:
            print(f"エラー : キーリストの取得に失敗 - {e}")
            return []

# --- Budget Calculator ---
# (省略: 前回と同じ)
class BudgetCalculator:
    def __init__(self, account_data):
        self.data = account_data
        self.today = datetime.now(timezone.utc).date()

    def get_total_income(self):
        total = self.data.get("base_income", 0)
        for extra in self.data.get("extra_incomes", []):
            total += extra.get("amount", 0)
        return total

    def get_total_fixed_costs(self):
        return sum(item.get("amount", 0) for item in self.data["spending"].get("fixed_costs", []))

    def get_total_daily_spends(self):
        return sum(item.get("amount", 0) for item in self.data["spending"].get("daily_spends", []))

    def calculate_remaining_budget(self):
        monthly_spendable = (self.get_total_income() - 
                             self.get_total_fixed_costs() - 
                             self.data.get("savings_goal", 0))
        remaining_for_month = monthly_spendable - self.get_total_daily_spends()
        days_in_month = calendar.monthrange(self.today.year, self.today.month)[1]
        remaining_days = days_in_month - self.today.day + 1
        daily_average = remaining_for_month / remaining_days if remaining_days > 0 else 0
        return remaining_for_month, daily_average

    def get_formatted_budget_text(self):
        total_remaining, daily_average = self.calculate_remaining_budget()
        period_setting = self.data["settings"].get("calculation_period", "7day")
        
        header = f"💰 **今月使える残額**: {total_remaining:,.0f}円\n"
        
        if period_setting == "daily":
            return header + f"🗓️ **今日使える金額の目安**: {daily_average:,.0f}円"
        elif period_setting == "7day":
            day_of_week = self.today.weekday()
            remaining_days_in_week = 7 - day_of_week
            week_budget = daily_average * remaining_days_in_week
            return header + f"📅 **今週あと使える金額の目安**: {week_budget:,.0f}円 ({remaining_days_in_week}日間)"
        else:
            return header + f"🗓️ **1日あたりの平均**: {daily_average:,.0f}円"

# --- Discord Bot 本体 ---
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
kv_manager = KVManager(CF_ACCOUNT_ID, CF_NAMESPACE_ID, CF_API_TOKEN)

# --- ★★★ ヘルパー関数: 応答メッセージ生成 ★★★ ---
def create_response_embed(title, description, budget_text):
    """コマンド実行後の応答用Embedを生成する"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green()
    )
    embed.add_field(name="現在の予算状況", value=budget_text, inline=False)
    embed.set_footer(text=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    return embed

# --- Botイベント ---
@client.event
async def on_ready():
    await tree.sync()
    print(f'{client.user} としてログインし、コマンドを同期しました。')

from discord.ext import tasks
@tasks.loop(seconds=60)
async def daily_report():
    await client.wait_until_ready()

    now = datetime.now()
    if now.hour == 8 and now.minute == 0:
        print("提示通知の送信を開始します")

        user_ids = kv_manager.list_all_user_ids()
        if not user_ids:
            print("通知対象のユーザーがいません")
            return
        
        for user_id in user_ids:
            account_data = kv_manager.get_account_data(user_id)
            if not account_data: continue

            channel_id_str = account_data.get("settings", {}).get("notification_channel")
            if channel_id_str:
                try:
                    channel_id = int(channel_id_str)
                    channel = client.get_channel(channel_id)

                    if channel:
                        calculator = BudgetCalculator(account_data)
                        budget_text = calculator.get_formatted_budget_text()

                        embed = discord.Embed(
                            title=f"{now.strftime("%m月%d日")}の家計簿です",
                            color=discord.Color.orange()
                        )
                        embed.add_field(name="現在の予算状況", value=budget_text, inline=False)

                        await channel.send(embed=embed)
                        print("送信")
                    else:
                        print("エラー")
                except (ValueError, discord.Forbidden, discord.HTTPException) as e:
                    print(e)
    print("完了")

# --- スラッシュコマンド ---

@tree.command(name="spend", description="支出を記録します。")
@app_commands.describe(amount="金額", item="品目や内容")
async def spend(interaction: discord.Interaction, amount: int, item: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    
    account_data = kv_manager.get_account_data(user_id)
    if account_data is None:
        await interaction.followup.send("エラー: データ取得失敗")
        return

    account_data["spending"]["daily_spends"].append({
        "amount": amount, "item": item, "date": datetime.now(timezone.utc).isoformat()
    })
    
    if not kv_manager.set_account_data(user_id, account_data):
        await interaction.followup.send("エラー: データ保存失敗")
        return
        
    calculator = BudgetCalculator(account_data)
    budget_text = calculator.get_formatted_budget_text()
    
    embed = create_response_embed(
        title="支出を記録しました📝",
        description=f"**金額**: {amount:,}円\n**内容**: {item}",
        budget_text=budget_text
    )
    await interaction.followup.send(embed=embed)


# --- ★★★ ここから新しいコマンド ★★★ ---

@tree.command(name="income", description="基本収入（給与など）を設定します。")
@app_commands.describe(amount="収入額")
async def income(interaction: discord.Interaction, amount: int):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    
    account_data = kv_manager.get_account_data(user_id)
    if account_data is None:
        await interaction.followup.send("エラー: データ取得失敗")
        return

    account_data["base_income"] = amount
    
    if not kv_manager.set_account_data(user_id, account_data):
        await interaction.followup.send("エラー: データ保存失敗")
        return
        
    calculator = BudgetCalculator(account_data)
    budget_text = calculator.get_formatted_budget_text()
    
    embed = create_response_embed(
        title="基本収入を設定しました💼",
        description=f"新しい基本収入: **{amount:,}円**",
        budget_text=budget_text
    )
    await interaction.followup.send(embed=embed)

@tree.command(name="extra_income", description="臨時収入を記録します。")
@app_commands.describe(amount="金額", description="収入の内容（ボーナスなど）")
async def extra_income(interaction: discord.Interaction, amount: int, description: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    
    account_data = kv_manager.get_account_data(user_id)
    if account_data is None:
        await interaction.followup.send("エラー: データ取得失敗")
        return

    account_data["extra_incomes"].append({
        "amount": amount, "description": description, "date": datetime.now(timezone.utc).isoformat()
    })
    
    if not kv_manager.set_account_data(user_id, account_data):
        await interaction.followup.send("エラー: データ保存失敗")
        return
        
    calculator = BudgetCalculator(account_data)
    budget_text = calculator.get_formatted_budget_text()
    
    embed = create_response_embed(
        title="臨時収入を記録しました🎉",
        description=f"**金額**: {amount:,}円\n**内容**: {description}",
        budget_text=budget_text
    )
    await interaction.followup.send(embed=embed)

@tree.command(name="fixed_cost", description="固定費（家賃、サブスクなど）を記録します。")
@app_commands.describe(amount="金額", description="固定費の内容")
async def fixed_cost(interaction: discord.Interaction, amount: int, description: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    
    account_data = kv_manager.get_account_data(user_id)
    if account_data is None:
        await interaction.followup.send("エラー: データ取得失敗")
        return

    account_data["spending"]["fixed_costs"].append({
        "amount": amount, "description": description
    })
    
    if not kv_manager.set_account_data(user_id, account_data):
        await interaction.followup.send("エラー: データ保存失敗")
        return
        
    calculator = BudgetCalculator(account_data)
    budget_text = calculator.get_formatted_budget_text()
    
    embed = create_response_embed(
        title="固定費を記録しました💳",
        description=f"**金額**: {amount:,}円\n**内容**: {description}",
        budget_text=budget_text
    )
    await interaction.followup.send(embed=embed)

@tree.command(name="set_savings", description="毎月の目標貯金額を設定します。")
@app_commands.describe(amount="貯金額")
async def set_savings(interaction: discord.Interaction, amount: int):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    
    account_data = kv_manager.get_account_data(user_id)
    if account_data is None:
        await interaction.followup.send("エラー: データ取得失敗")
        return

    account_data["savings_goal"] = amount
    
    if not kv_manager.set_account_data(user_id, account_data):
        await interaction.followup.send("エラー: データ保存失敗")
        return
        
    calculator = BudgetCalculator(account_data)
    budget_text = calculator.get_formatted_budget_text()
    
    embed = create_response_embed(
        title="目標貯金額を設定しました🐖",
        description=f"新しい目標貯金額: **{amount:,}円**",
        budget_text=budget_text
    )
    await interaction.followup.send(embed=embed)

@tree.command(name="setting", description="予算の計算期間を設定します。")
@app_commands.describe(period="計算する期間を選択してください")
@app_commands.choices(period=[
    app_commands.Choice(name="1日ごと", value="daily"),
    app_commands.Choice(name="7日ごと (週)", value="7day"),
    app_commands.Choice(name="10日ごと (上旬/中旬/下旬)", value="10day"),
    app_commands.Choice(name="14日ごと (半月)", value="14day"),
    app_commands.Choice(name="月全体", value="monthly"),
])
async def setting(interaction: discord.Interaction, period: app_commands.Choice[str]):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    
    account_data = kv_manager.get_account_data(user_id)
    if account_data is None:
        await interaction.followup.send("エラー: データ取得に失敗しました。")
        return

    # 設定を更新
    account_data["settings"]["calculation_period"] = period.value
    
    if not kv_manager.set_account_data(user_id, account_data):
        await interaction.followup.send("エラー: データ保存に失敗しました。")
        return
        
    calculator = BudgetCalculator(account_data)
    budget_text = calculator.get_formatted_budget_text()
    
    embed = create_response_embed(
        title="設定を変更しました⚙️",
        description=f"予算の計算期間を **{period.name}** に変更しました。",
        budget_text=budget_text
    )
    await interaction.followup.send(embed=embed)

@tree.command(name="set_notifications", description="このチャンネルに毎朝8時の定時通知を設定します。")
async def set_notifications(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    channel_id = str(interaction.channel_id)

    account_data = kv_manager.get_account_data(user_id)
    if account_data is None:
        await interaction.followup.send("エラー: データ取得に失敗しました。")
        return

    # 設定を更新
    account_data["settings"]["notification_channel"] = channel_id
    
    if not kv_manager.set_account_data(user_id, account_data):
        await interaction.followup.send("エラー: データ保存に失敗しました。")
        return
        
    embed = discord.Embed(
        title="通知設定が完了しました！",
        description=f"✅ このチャンネル <#{channel_id}> に、毎朝8時のサマリーが通知されるよう設定しました。",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed)
    
# Botの実行
if DISCORD_TOKEN:
    client.run(DISCORD_TOKEN)