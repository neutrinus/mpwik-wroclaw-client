# MPWiK Wrocław - Water Consumption Data Fetcher

Python script to fetch water consumption data from MPWiK Wrocław e-BOK system for Home Assistant integration.

## Features

- 🔐 Authentication with MPWiK Wrocław API
- 📊 Fetch daily water consumption readings
- ⏰ Fetch hourly water consumption readings
- 📁 Export data to JSON format
- 🖥️ Command-line interface
- 🌐 **Browser automation mode** to handle reCAPTCHA and debug issues

## Installation

1. Clone this repository:
```bash
git clone https://github.com/neutrinus/ha-mwpwik-wroclaw.git
cd ha-mwpwik-wroclaw
```

2. Install dependencies using uv:
```bash
uv sync
```

    -   For the **`selenium`** method, install the `selenium` extra:
        ```bash
        uv sync --extra selenium
        ```

    -   For the **`playwright`** method, install the `playwright` extra and then install the necessary browser binaries:
        ```bash
        uv sync --extra playwright
        playwright install
        ```

> **Note**: If you use `uv sync`, you must run the script with `uv run python mpwik_client.py` or activate the virtual environment first with `source .venv/bin/activate` (Linux/Mac) or `.venv\Scripts\activate` (Windows).

## Usage

The script supports three connection methods:
1. **`direct`**: Uses the `requests` library to directly call the backend API. This is the most lightweight method but may be blocked by reCAPTCHA on the login page.
2. **`selenium` (Default)**: Uses Selenium to automate a real web browser (like Chrome or Firefox). This can bypass reCAPTCHA challenges but is resource-intensive.
3. **`playwright`**: A modern alternative to Selenium. It also automates a real browser and is often faster and more reliable.

The browser-based methods (`selenium`, `playwright`) are recommended if you encounter login failures with the `direct` method.

### Basic Usage (API Mode)

Fetch hourly water consumption for yesterday (default):

```bash
uv run python mpwik_client.py \
  --login "123456" \
  --password "YourPassword" \
```

### API Mode with ReCAPTCHA Solving (CapMonster)

To use the API mode with automatic reCAPTCHA solving, you need a CapMonster API key:

```bash
uv run python mpwik_client.py \
  --login "123456" \
  --password "YourPassword" \
  --capmonster-api-key "YOUR_CAPMONSTER_API_KEY"
```

The API mode uses the official [CapMonster Python client library](https://github.com/Zennolab/capmonstercloud-client-python) and properly passes the User-Agent to CapMonster, ensuring the reCAPTCHA token validation succeeds. You can optionally specify the reCAPTCHA version:

```bash
# Use ReCAPTCHA v3 (default)
uv run python mpwik_client.py \
  --login "123456" \
  --password "YourPassword" \
  --capmonster-api-key "YOUR_CAPMONSTER_API_KEY" \
  --recaptcha-version 3

# Or use ReCAPTCHA v2
uv run python mpwik_client.py \
  --login "123456" \
  --password "YourPassword" \
  --capmonster-api-key "YOUR_CAPMONSTER_API_KEY" \
  --recaptcha-version 2
```

**Installation**: The CapMonster client is automatically installed with the project dependencies. If not installed, the code will fall back to direct API calls.


**Note**: Get your CapMonster API key from [https://capmonster.cloud/](https://capmonster.cloud/)

### List Available Meters

Before fetching readings, you can list all available meters for your account:

**With uv:**
```bash
uv run python mpwik_client.py \
  --login "123456" \
  --password "YourPassword" \
  --list-punkty-sieci
```

This will display information about all network points including:
- Network point ID (for use with `--punkt-sieci`)
- Meter number
- Address
- Active status
- Coordinates (latitude/longitude)

### Browser Automation Mode (Recommended for reCAPTCHA)

Use browser automation to bypass reCAPTCHA and log debugging information. The default method is `selenium`:

```bash
uv run python mpwik_client.py \
  --login "123456" \
  --password "YourPassword"
```

**Using Playwright instead:**

```bash
uv run python mpwik_client.py \
  --login "123456" \
  --password "YourPassword" \
  --method playwright
```

**Run with visible browser window** (for manual reCAPTCHA solving):

```bash
uv run python mpwik_client.py \
  --login "123456" \
  --password "YourPassword" \
  --no-headless
```

**Using direct API method** (lightweight but may be blocked by reCAPTCHA):

```bash
uv run python mpwik_client.py \
  --login "123456" \
  --password "YourPassword" \
  --method direct
```

### Fetch Hourly Readings

Fetch hourly readings for a specific day (note: hourly is now the default type):

```bash
uv run python mpwik_client.py \
  --login "123456" \
  --password "YourPassword" \
  --date-from "2025-11-09" \
  --date-to "2025-11-09"
```

### Fetch Daily Readings

Fetch daily readings for the last 7 days:

```bash
uv run python mpwik_client.py \
  --login "123456" \
  --password "YourPassword" \
  --type daily \
  --days 7
```

### Testing Different Connection Methods

The `test_auth.py` script allows you to test different connection methods (direct API, Selenium, or Playwright):

-   **Using Direct API (default):**
    ```bash
    export MPWIK_LOGIN="123456"
    export MPWIK_PASSWORD="YourPassword"
    python test_auth.py --method direct
    ```

-   **Using Selenium (non-headless):**
    ```bash
    export MPWIK_LOGIN="123456"
    export MPWIK_PASSWORD="YourPassword"
    python test_auth.py --method selenium --no-headless
    ```

-   **Using Playwright (headless):**
    ```bash
    export MPWIK_LOGIN="123456"
    export MPWIK_PASSWORD="YourPassword"
    python test_auth.py --method playwright --headless
    ```

### Command-line Options

-   `--method`: `direct`, `selenium`, or `playwright`. Default: `selenium`.
-   `--type`: `dobowe` (daily) or `godzinowe` (hourly). Default: `godzinowe`.
-   `--headless` / `--no-headless`: Enable or disable headless mode for browser methods. Default: `headless`.



## Command-Line Arguments

| Argument | Required | Description | Default |
|----------|----------|-------------|---------|
| `--login` | Yes | Login (podmiot ID) | - |
| `--password` | Yes | Password | - |
| `--podmiot-id` | No | Podmiot ID (defaults to login if not provided) | login value |
| `--punkt-sieci` | Conditional | Network point ID (e.g., "0123-2021"). Required unless `--list-punkty-sieci` is used | - |
| `--list-punkty-sieci` | No | List all available network points (meters) for this account | - |
| `--type` | No | Type of readings: `daily`, `hourly`, or `both` | `daily` |
| `--days` | No | Number of days to fetch (for daily readings only) | `7` |
| `--date-from` | No | Start date (YYYY-MM-DD) | Yesterday (for hourly), N days ago (for daily) |
| `--date-to` | No | End date (YYYY-MM-DD) | Yesterday (for hourly), Today (for daily) |
| `--output` | No | Output JSON file path | - |
| `--use-browser` | No | Use browser automation (Selenium) instead of direct API | `False` |
| `--headless` | No | Run browser in headless mode (when using `--use-browser`) | `True` |
| `--no-headless` | No | Run browser with visible window (for manual reCAPTCHA) | `False` |
| `--capmonster-api-key` | No | CapMonster API key for automatic reCAPTCHA solving (API mode) | - |
| `--recaptcha-version` | No | Preferred ReCAPTCHA version (2 or 3). Tries v3 first, then v2 if not specified | Auto |
| `--log-dir` | No | Directory for logs and screenshots | `./logs` |
| `--debug` | No | Enable debug logging | `False` |

For detailed API endpoint documentation, request/response formats, and technical implementation details, see [API.md](API.md).

## Finding Your Parameters

To use this script, you need to find your specific parameters:

1. **login**: Your MPWiK login (usually your podmiot ID)
2. **password**: Your MPWiK account password
3. **podmiot-id**: Your entity ID (optional - defaults to login if not provided)
4. **punkt-sieci**: Your network point ID (can be found using `--list-punkty-sieci` or from the URL, defaults to first one)

## Testing

The project includes comprehensive test suites for both clients. To run the tests:

### Run all tests:

```bash
# Run all tests at once
python3 -m unittest discover -s tests -p "test_*.py" -v
```

Or run individual test files:

```bash
python3 -m unittest tests.test_auth
python3 -m unittest tests.test_error_handling
python3 -m unittest tests.test_mpwik_client
python3 -m unittest tests.test_mpwik_browser_client
```

### Test Coverage:

- **tests/test_auth.py**: Authentication flow tests
- **tests/test_error_handling.py**: Error handling in browser client
- **tests/test_mpwik_client.py**: Comprehensive tests for API client (25 tests)
  - Initialization and configuration
  - Authentication with/without ReCAPTCHA
  - CSRF token handling
  - Data fetching methods
  - Logging and debugging
  
- **tests/test_mpwik_browser_client.py**: Comprehensive tests for browser client (29 tests)
  - Driver setup and configuration
  - Browser automation
  - API data extraction
  - Context managers
  - Error handling

**Total: 56+ tests covering all major functionality**

### Known Limitations

- **ReCAPTCHA in API Mode**: Without a CapMonster API key, the API mode cannot solve ReCAPTCHA challenges automatically. Use `--method selenium` or `--method playwright` (or just omit the flag since selenium is the default).
- **Browser Mode Performance**: Browser automation is slower than direct API calls but more reliable for bypassing reCAPTCHA.
- **Session Persistence**: Consider implementing session token storage to avoid frequent re-authentication.

## How It Works

The login page at `ebok.mpwik.wroc.pl` is protected by reCAPTCHA, which makes direct API calls difficult.

The `selenium` and `playwright` methods work by automating a real browser. Because these browsers have a "trusted" fingerprint, Google's reCAPTCHA service typically allows them to log in without issue. Once logged in, the script navigates to a specific page to establish a full API session and then uses the browser's internal `fetch` API to retrieve data.

This approach combines the robustness of browser automation with the efficiency of direct API calls post-authentication.

## References

- Forum discussion: https://forum.arturhome.pl/t/bezsprzetowy-licznik-zuzycia-wody-mpwik-wroclaw/10883/11
- MPWiK Wrocław e-BOK: https://ebok.mpwik.wroc.pl/

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Disclaimer

This is an unofficial integration. Use at your own risk. Always verify water consumption data with official MPWiK Wrocław statements.
