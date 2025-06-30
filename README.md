# Telegram Weather Bot

This is a feature-rich Telegram bot that provides weather information, forecasts, and scheduled alerts. It uses the WeatherAPI.com service to fetch weather data.

## Features

- **Current Weather:** Get the current weather for any city.
- **3-Day Forecast:** Provides a 3-day weather forecast.
- **Rain Forecast:** Details on when to expect rain.
- **Air Quality Index (AQI):** Get the AQI for a location.
- **UV Index:** Information on the UV index.
- **Historical Weather:** Retrieve historical weather data for a specific date and city.
- **Scheduled Alerts:** Set up daily weather alerts for multiple locations.
- **Personalized Locations:** Each user can manage their own list of locations.
- **Whitelist System:** Control who can use the bot.

## Commands

The bot supports the following commands:

- `/start`: Displays the welcome message and command list.
- `/help`: Shows the help message with all available commands.
- `/weather [city]`: Get the current weather. If no city is specified, it will show the weather for all of your saved locations.
- `/add <city>`: Add a city to your daily alert list.
- `/remove <city>`: Remove a city from your list of saved locations.
- `/list`: View your list of registered locations.
- `/history <YYYY-MM-DD> <city>`: Get historical weather data for a specific date and city.

### Admin Commands

- `/mock <command> [args...]`: Allows an admin to execute a command as if it were a regular user.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Neel-XV/tg-weather-bot.git
    cd tg-weather-bot
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

Before running the bot, you need to set up the `config.ini` file.

1.  **Create `config.ini`:**
    Create a file named `config.ini` in the root directory of the project.

2.  **Add API Keys and Settings:**
    You will need to add your API keys and other settings to the `config.ini` file.

    ```ini
    [WEATHERAPI]
    API_KEY = YOUR_WEATHERAPI_KEY

    [TELEGRAM]
    BOT_TOKEN = YOUR_TELEGRAM_BOT_TOKEN
    CHAT_ID = YOUR_ADMIN_CHAT_ID
    WHITELISTED_USERS = USER_ID_1,USER_ID_2
    ADMINS = ADMIN_USER_ID_1

    [SCHEDULE]
    TIME = 08:00
    TIMEZONE = UTC

    [LOCATIONS]
    ```

    - `API_KEY`: Your API key from [WeatherAPI.com](https://www.weatherapi.com/).
    - `BOT_TOKEN`: The token for your Telegram bot from BotFather.
    - `CHAT_ID`: The main admin's Telegram chat ID.
    - `WHITELISTED_USERS`: A comma-separated list of Telegram user IDs that are allowed to use the bot.
    - `ADMINS`: A comma-separated list of Telegram user IDs for admin commands.
    - `TIME`: The time for scheduled daily alerts (in HH:MM format).
    - `TIMEZONE`: The timezone for the scheduler (e.g., `America/New_York`).
    - `LOCATIONS`: This section is managed by the bot to store user locations.

## Usage

To run the bot, execute the following command:

```bash
python weather_bot.py
```

The bot will start polling for messages and will send scheduled alerts at the time you configured.
