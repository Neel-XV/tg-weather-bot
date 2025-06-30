import requests
import logging
import configparser
from datetime import datetime, timedelta
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import asyncio
import threading
import time

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("weather_bot.log"),
                        logging.StreamHandler()
                    ])

# Load configuration
config = configparser.ConfigParser()
try:
    config.read('config.ini')
    WEATHERAPI_KEY = config['WEATHERAPI']['API_KEY']
    BOT_TOKEN = config['TELEGRAM']['BOT_TOKEN']
    ADMIN_CHAT_ID = config['TELEGRAM']['CHAT_ID']
    WHITELISTED_USERS = [user.strip() for user in config['TELEGRAM']['WHITELISTED_USERS'].split(',') if user.strip()]
    ADMINS = [admin.strip() for admin in config['TELEGRAM']['ADMINS'].split(',') if admin.strip()]
    SCHEDULE_TIME = config['SCHEDULE']['TIME']
    TIMEZONE = config['SCHEDULE']['TIMEZONE']
    
    user_locations = {}
    if 'LOCATIONS' in config:
        for user_id, locations in config['LOCATIONS'].items():
            user_locations[user_id] = [loc.strip() for loc in locations.split(',')]

except KeyError as e:
    logging.error(f"Configuration error: Missing key {e}. Please check config.ini.")
    exit(1)

if ADMIN_CHAT_ID not in WHITELISTED_USERS:
    WHITELISTED_USERS.append(ADMIN_CHAT_ID)

bot = Bot(token=BOT_TOKEN)

def get_weather(city, api_key, days=3):
    """Fetches forecast weather data from WeatherAPI.com."""
    url = f"http://api.weatherapi.com/v1/forecast.json?key={api_key}&q={city}&days={days}&aqi=yes&alerts=yes"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching weather for {city}: {e}")
        return None

def get_historical_weather(city, api_key, date):
    """Fetches historical weather data from WeatherAPI.com."""
    url = f"http://api.weatherapi.com/v1/history.json?key={api_key}&q={city}&dt={date}"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching historical weather for {city} on {date}: {e}")
        return None

async def send_telegram_message(chat_id, message):
    """Sends a message to a specified Telegram chat."""
    try:
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except TelegramError as e:
        logging.error(f"Telegram error sending message to {chat_id}: {e}")

# --- Data Formatting and Suggestions ---

def get_rain_forecast(forecast):
    """Parses the forecast to find and format rain periods."""
    rain_periods = []
    is_raining = False
    start_time = None

    for hour in forecast.get('forecastday', [{}])[0].get('hour', []):
        if hour.get('will_it_rain') and not is_raining:
            is_raining = True
            start_time = datetime.fromtimestamp(hour['time_epoch']).strftime('%I:%M %p')
        elif not hour.get('will_it_rain') and is_raining:
            is_raining = False
            end_time = datetime.fromtimestamp(hour['time_epoch']).strftime('%I:%M %p')
            rain_periods.append(f"from {start_time} to {end_time}")

    if is_raining:
        rain_periods.append(f"from {start_time} onwards")

    if not rain_periods:
        return "No rain expected today."
    else:
        return "Rain expected " + ", ".join(rain_periods) + "."

def get_suggestions(current, forecast):
    """Generates dynamic suggestions based on weather data."""
    suggestions = []
    day_forecast = forecast.get('forecastday', [{}])[0].get('day', {})

    if day_forecast.get('daily_will_it_rain') or day_forecast.get('daily_chance_of_rain', 0) > 40:
        suggestions.append("Light drizzle or rain is possible—consider carrying an umbrella.")
    
    aqi = current.get('air_quality', {}).get('us-epa-index', 0)
    if aqi <= 2:
        suggestions.append("Air quality is good—a great day for outdoor activities.")
    else:
        suggestions.append("Air quality is poor—it may be wise to limit strenuous outdoor activities.")

    uv_index = current.get('uv', 0)
    if uv_index > 5:
        suggestions.append("UV index is high—use sunscreen and wear protective clothing if outdoors.")
    elif uv_index > 2:
        suggestions.append("UV index is moderate—use sunscreen if staying outdoors for extended periods.")

    return "\n".join(f"- {s}" for s in suggestions) or "- Enjoy your day!"

def format_weather_report(city, weather_data):
    """Formats the full weather report for a city."""
    current = weather_data.get('current', {})
    forecast = weather_data.get('forecast', {})
    astro = forecast.get('forecastday', [{}])[0].get('astro', {})
    
    aqi_data = current.get('air_quality', {})
    aqi_levels = {1: "Good", 2: "Moderate", 3: "Unhealthy for Sensitive Groups", 4: "Unhealthy", 5: "Very Unhealthy", 6: "Hazardous"}
    aqi_index = aqi_data.get('us-epa-index', 0)
    aqi_desc = aqi_levels.get(aqi_index, 'Unknown')

    return (
        f"**Weather Update for {city}**\n"
        f"_{current.get('condition', {}).get('text')}_\n\n"
        f"*Temperature*: {current.get('temp_c')}°C (Feels like: {current.get('feelslike_c')}°C)\n"
        f"*Humidity*: {current.get('humidity')}% | *Wind*: {current.get('wind_kph')} km/h {current.get('wind_dir')}\n"
        f"*UV Index*: {current.get('uv')} | *Visibility*: {current.get('vis_km')} km\n\n"
        f"**Rain Forecast**\n{get_rain_forecast(forecast)}\n\n"
        f"**Air & Light**\n"
        f"*Air Quality*: {aqi_index} - {aqi_desc}\n\n"
        f"**Suggestions for the Day**\n{get_suggestions(current, forecast)}"
    )

# --- Alert and Command Functions ---

async def send_weather_report(chat_id, city):
    """Fetches and sends a formatted weather report."""
    weather_data = get_weather(city, WEATHERAPI_KEY)
    if weather_data:
        report = format_weather_report(city, weather_data)
        await send_telegram_message(chat_id, report)
    else:
        await send_telegram_message(chat_id, f"Could not retrieve weather for {city}.")

async def scheduled_weather_update():
    """Scheduled job to send daily alerts."""
    logging.info("Running scheduled daily weather alerts...")
    for user_id, locations in user_locations.items():
        if str(user_id) in WHITELISTED_USERS:
            for city in locations:
                await send_weather_report(user_id, city)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start and /help commands."""
    commands = (
        "**/weather [city]**: Get current weather. Shows all your locations if no city is specified.\n"
        "**/add <city>**: Add a city to your daily alert list.\n"
        "**/remove <city>**: Remove a city from your list.\n"
        "**/list**: View your list of registered locations.\n"
        "**/help**: Show this help message."
    )
    message = f"**Welcome to the Advanced Weather Bot!**\n\n{commands}"
    await update.message.reply_text(message, parse_mode='Markdown')

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /weather command."""
    user_id = str(update.message.from_user.id)
    if user_id not in WHITELISTED_USERS: return

    cities = [' '.join(context.args)] if context.args else user_locations.get(user_id, [])
    if not cities:
        await update.message.reply_text("Please specify a city or add one with /add <city>.")
        return

    for city in cities:
        await send_weather_report(update.message.chat_id, city)



async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /history command."""
    user_id = str(update.message.from_user.id)
    if user_id not in WHITELISTED_USERS: return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /history <YYYY-MM-DD> <city>")
        return

    date_str = context.args[0]
    city = ' '.join(context.args[1:])

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if date > datetime.now().date():
            await update.message.reply_text("Cannot get history for a future date.")
            return
    except ValueError:
        await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD.")
        return

    hist_data = get_historical_weather(city, WEATHERAPI_KEY, date_str)
    if not hist_data:
        await update.message.reply_text(f"Could not get history for {city} on {date_str}.")
        return

    day_data = hist_data.get('forecast', {}).get('forecastday', [{}])[0].get('day', {})
    message = (
        f"**Historical Weather for {city} on {date_str}**\n"
        f"- *Condition*: {day_data.get('condition', {}).get('text')}\n"
        f"- *Max Temp*: {day_data.get('maxtemp_c')}°C\n"
        f"- *Min Temp*: {day_data.get('mintemp_c')}°C\n"
        f"- *Avg Temp*: {day_data.get('avgtemp_c')}°C\n"
        f"- *Total Precip*: {day_data.get('totalprecip_mm')} mm"
    )
    await update.message.reply_text(message, parse_mode='Markdown')

# --- Location and User Management ---

def update_config_file():
    """Writes the current state of user_locations and WHITELISTED_USERS to config.ini."""
    config.set('TELEGRAM', 'WHITELISTED_USERS', ','.join(WHITELISTED_USERS))
    for user_id, locations in user_locations.items():
        if locations:
            config.set('LOCATIONS', user_id, ','.join(locations))
        elif config.has_option('LOCATIONS', user_id):
            config.remove_option('LOCATIONS', user_id)
            
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if user_id not in WHITELISTED_USERS: return
    if not context.args: 
        await update.message.reply_text("Usage: /add <city>")
        return

    city = ' '.join(context.args)
    if not get_weather(city, WEATHERAPI_KEY, days=1):
        await update.message.reply_text(f"Invalid city: '{city}'. Please check the name.")
        return

    user_locations.setdefault(user_id, [])
    if city.lower() not in [loc.lower() for loc in user_locations[user_id]]:
        user_locations[user_id].append(city)
        update_config_file()
        await update.message.reply_text(f"Added '{city}' to your locations.")
    else:
        await update.message.reply_text(f"'{city}' is already in your list.")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if user_id not in WHITELISTED_USERS: return
    if not context.args: 
        await update.message.reply_text("Usage: /remove <city>")
        return

    city_to_remove = ' '.join(context.args)
    if user_id in user_locations and city_to_remove.lower() in [loc.lower() for loc in user_locations[user_id]]:
        user_locations[user_id] = [loc for loc in user_locations[user_id] if loc.lower() != city_to_remove.lower()]
        update_config_file()
        await update.message.reply_text(f"Removed '{city_to_remove}'.")
    else:
        await update.message.reply_text(f"'{city_to_remove}' not found in your list.")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if user_id not in WHITELISTED_USERS: return
    locations = user_locations.get(user_id, [])
    message = "**Your locations:**\n- " + "\n- ".join(locations) if locations else "You have no locations."
    await update.message.reply_text(message, parse_mode='Markdown')

async def buymeacoffee_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if user_id in WHITELISTED_USERS:
        await update.message.reply_text("You are already whitelisted.")
        return
    WHITELISTED_USERS.append(user_id)
    update_config_file()
    await update.message.reply_text("You are now whitelisted! Use /start to see commands.")

async def mock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if user_id not in ADMINS:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /mock <command> [args...]")
        return

    command_to_mock = context.args[0]
    mock_args = context.args[1:]
    
    # Create a new mock update and context object
    mock_update = update
    mock_update.message.text = f"/{command_to_mock} {' '.join(mock_args)}"
    
    mock_context = ContextTypes.DEFAULT_TYPE(application=context.application, chat_id=update.effective_chat.id, user_id=user_id)
    mock_context.args = mock_args


    if command_to_mock == 'weather':
        await weather_command(mock_update, mock_context)
    elif command_to_mock == 'add':
        await add_command(mock_update, mock_context)
    elif command_to_mock == 'remove':
        await remove_command(mock_update, mock_context)
    elif command_to_mock == 'list':
        await list_command(mock_update, mock_context)
    elif command_to_mock == 'history':
        await history_command(mock_update, mock_context)
    elif command_to_mock == 'buymeacoffee':
        await buymeacoffee_command(mock_update, mock_context)
    elif command_to_mock == 'start' or command_to_mock == 'help':
        await start_command(mock_update, mock_context)
    elif command_to_mock == 'scheduledalert':
        await scheduled_weather_update()
    else:
        await update.message.reply_text(f"Command '/{command_to_mock}' cannot be mocked or does not exist.")

# --- Main Application Setup ---

def run_scheduler():
    scheduler = BackgroundScheduler(timezone=pytz.timezone(TIMEZONE))
    hour, minute = map(int, SCHEDULE_TIME.split(':'))
    scheduler.add_job(scheduled_weather_update, CronTrigger(hour=hour, minute=minute))
    scheduler.start()
    logging.info(f"Scheduler started for {TIMEZONE} at {SCHEDULE_TIME}.")

def main():
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()

    application = Application.builder().token(BOT_TOKEN).build()
    handlers = [
        CommandHandler("start", start_command),
        CommandHandler("help", start_command),
        CommandHandler("weather", weather_command),
        CommandHandler("add", add_command),
        CommandHandler("remove", remove_command),
        CommandHandler("list", list_command),
        
        CommandHandler("history", history_command),
        CommandHandler("buymeacoffee", buymeacoffee_command),
        CommandHandler("mock", mock_command)
    ]
    application.add_handlers(handlers)
    
    logging.info("Weather bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
