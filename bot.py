import discord
from discord.ext import commands
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from typing import Dict, List, Optional, Tuple

# Load configuration
def load_config() -> dict:
    """Load configuration from environment variables or config file"""
    config = {
        'DISCORD_TOKEN': os.getenv('DISCORD_TOKEN'),
        'SHEET_URL': os.getenv('SHEET_URL')
    }
    
    try:
        with open('config.json') as f:
            file_config = json.load(f)
            config.update({k: v for k, v in file_config.items() if v is not None})
    except FileNotFoundError:
        pass
    
    return config

# Initialize config
config = load_config()

# Initialize Google Sheets
def init_sheets():
    """Initialize Google Sheets client and worksheets"""
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        # Open the spreadsheet by URL
        spreadsheet = client.open_by_url(config['SHEET_URL'])
        
        # Get the worksheets
        try:
            time_logs = spreadsheet.worksheet("Logs")
        except gspread.WorksheetNotFound:
            time_logs = spreadsheet.add_worksheet(title="Logs", rows=1000, cols=4)
            time_logs.append_row(["Nom", "Date", "Heure", "Événement"])
            
        try:
            daily_totals = spreadsheet.worksheet("Totaux")
        except gspread.WorksheetNotFound:
            daily_totals = spreadsheet.add_worksheet(title="Totaux", rows=1000, cols=3)
            daily_totals.append_row(["Nom", "Date", "Heures Travaillées"])
        
        return time_logs, daily_totals
    except Exception as e:
        print(f"Error initializing Google Sheets: {e}")
        raise

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Global variables
time_logs = None
daily_totals = None

def log_event(username: str, event_type: str) -> bool:
    """
    Log an event to Google Sheets
    Returns True if successful, False otherwise
    """
    try:
        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        
        # Log to Time Logs
        time_logs.append_row([username, date_str, time_str, event_type])
        
        # If checking out, calculate total hours
        if event_type == "CHECK OUT":
            calculate_daily_hours(username, date_str)
        
        return True
    except Exception as e:
        print(f"Error logging event: {e}")
        return False

def calculate_daily_hours(username: str, date_str: str) -> Optional[str]:
    """Calculate daily working hours and return formatted as 9h55m00s"""
    if time_logs is None or daily_totals is None:
        return None
        
    try:
        # Get all records for the user on the given date
        records = time_logs.get_all_records()
        user_records = [r for r in records if r['Nom'] == username and r['Date'] == date_str]
        
        if not user_records:
            return None
            
        # Sort records by time
        user_records.sort(key=lambda x: x['Heure'])
        
        total_seconds = 0
        current_session_start = None
        in_break = False
        break_start = None
        
        for record in user_records:
            event_time = datetime.datetime.strptime(record['Heure'], '%H:%M:%S').time()
            
            if record['Événement'] == 'CHECK IN':
                if current_session_start is None:  # New session starts
                    current_session_start = event_time
                    
            elif record['Événement'] == 'BREAK':
                if not in_break and current_session_start:  # Start break
                    # Add time from session start to break start
                    session_seconds = (datetime.datetime.combine(datetime.date.today(), event_time) - 
                                     datetime.datetime.combine(datetime.date.today(), current_session_start)).total_seconds()
                    total_seconds += session_seconds
                    in_break = True
                    break_start = event_time
                elif in_break:  # End break
                    in_break = False
                    current_session_start = event_time  # New session starts after break
                    
            elif record['Événement'] == 'CHECK OUT':
                if current_session_start and not in_break:
                    # Add time from session start to check out
                    session_seconds = (datetime.datetime.combine(datetime.date.today(), event_time) - 
                                     datetime.datetime.combine(datetime.date.today(), current_session_start)).total_seconds()
                    total_seconds += session_seconds
                current_session_start = None  # Reset for possible new session
        
        # Handle case where user is still in a break at the end of records
        if in_break and break_start and current_session_start:
            # Add time from session start to break start
            session_seconds = (datetime.datetime.combine(datetime.date.today(), break_start) - 
                             datetime.datetime.combine(datetime.date.today(), current_session_start)).total_seconds()
            total_seconds += session_seconds
        
        # Convert total seconds to hours, minutes, seconds
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        
        # Format as 9h55m00s
        formatted_time = f"{hours}h{minutes:02d}m{seconds:02d}s"
        
        # Check if entry for this user and date already exists
        existing_entries = daily_totals.get_all_records()
        entry_updated = False
        
        for i, entry in enumerate(existing_entries, start=2):  # Start from row 2 (1-based)
            if entry['Nom'] == username and entry['Date'] == date_str:
                daily_totals.update_cell(i, 3, formatted_time)  # Update existing entry
                entry_updated = True
                break
        
        if not entry_updated:
            daily_totals.append_row([username, date_str, formatted_time])  # Add new entry
        
        return formatted_time
        
    except Exception as e:
        print(f"Error calculating daily hours: {str(e)}")
        return None

@bot.event
async def on_ready():
    """Called when the bot is ready"""
    global time_logs, daily_totals
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')
    
    try:
        time_logs, daily_totals = init_sheets()
        print("Successfully connected to Google Sheets")
    except Exception as e:
        print(f"Failed to initialize Google Sheets: {e}")
        print("Bot will continue with limited functionality")

@bot.command(name='checkin')
async def check_in(ctx):
    """Check in to start tracking work time"""
    if log_event(ctx.author.name, "CHECK IN"):
        await ctx.send(f"✅ {ctx.author.name} a commencé à travailler à {datetime.datetime.now().strftime('%H:%M:%S')}")
    else:
        await ctx.send("❌ Échec de l'enregistrement. Veuillez réessayer.")

@bot.command(name='checkout')
async def check_out(ctx):
    """Check out to stop tracking work time"""
    if log_event(ctx.author.name, "CHECK OUT"):
        await ctx.send(f"✅ {ctx.author.name} a terminé à {datetime.datetime.now().strftime('%H:%M:%S')}")
    else:
        await ctx.send("❌ Échec de l'enregistrement. Veuillez réessayer.")

@bot.command(name='break')
async def take_break(ctx):
    """Start or end a break"""
    user_logs = time_logs.get_all_records()
    user_logs = [log for log in user_logs if log['Nom'] == ctx.author.name]
    
    # Check if user is currently on a break
    last_break = next(
        (log for log in reversed(user_logs) if log['Événement'] in ['BREAK START', 'BREAK END']),
        None
    )
    
    if last_break is None or last_break['Événement'] == 'BREAK END':
        # Start a new break
        if log_event(ctx.author.name, "BREAK START"):
            await ctx.send(f"⏸️ {ctx.author.name} a commencé une pause à {datetime.datetime.now().strftime('%H:%M:%S')}")
        else:
            await ctx.send("❌ Échec de l'enregistrement de la pause. Veuillez réessayer.")
    else:
        # End the current break
        if log_event(ctx.author.name, "BREAK END"):
            await ctx.send(f"▶️ {ctx.author.name} a repris le travail à {datetime.datetime.now().strftime('%H:%M:%S')}")
        else:
            await ctx.send("❌ Échec de l'enregistrement de la fin de pause. Veuillez réessayer.")

@bot.command(name='status')
async def status(ctx):
    """Show your current status"""
    try:
        logs = time_logs.get_all_records()
        user_logs = [log for log in logs if log['Nom'] == ctx.author.name]
        
        if not user_logs:
            await ctx.send("Aucun temps enregistré pour le moment.")
            return
        
        last_event = user_logs[-1]
        status_msg = f"👤 **Statut de {ctx.author.name}**\n"
        status_msg += f"📅 Dernier événement: {last_event['Événement']} à {last_event['Heure']} le {last_event['Date']}\n"
        
        # Calculate today's total hours
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_logs = [log for log in user_logs if log['Date'] == today]
        
        if today_logs:
            # Find the most recent check-in
            check_ins = [log for log in today_logs if log['Événement'] == 'CHECK IN']
            if check_ins:
                last_check_in = check_ins[-1]
                check_in_time = datetime.datetime.strptime(
                    f"{last_check_in['Date']} {last_check_in['Heure']}", 
                    "%Y-%m-%d %H:%M:%S"
                )
                current_time = datetime.datetime.now()
                hours_worked = (current_time - check_in_time).total_seconds() / 3600
                status_msg += f"⏱️ En train de travailler depuis: {hours_worked:.1f} heures\n"
        
        # Get today's total from daily totals
        daily_records = daily_totals.get_all_records()
        today_total = next(
            (entry for entry in daily_records 
             if entry['Nom'] == ctx.author.name and entry['Date'] == today),
            None
        )
        
        if today_total:
            status_msg += f"📊 Total des heures aujourd'hui: {today_total['Heures Travaillées']}h"
        
        await ctx.send(status_msg)
    except Exception as e:
        print(f"Error getting status: {e}")
        await ctx.send("❌ Impossible d'obtenir le statut. Veuillez réessayer.")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Commande non trouvée. Commandes disponibles: !checkin, !checkout, !break, !status")
    else:
        print(f"Error: {error}")
        await ctx.send("❌ Une erreur est survenue. Veuillez réessayer.")

# Run the bot
if __name__ == "__main__":
    if not config.get('DISCORD_TOKEN'):
        print("Error: Aucun token Discord trouvé dans config.json ou les variables d'environnement")
        exit(1)
    
    if not config.get('SHEET_URL'):
        print("Attention: Aucune URL Google Sheet trouvée dans config.json ou les variables d'environnement")
    
    try:
        bot.run(config['DISCORD_TOKEN'])
    except Exception as e:
        print(f"Erreur lors du démarrage du bot: {e}")