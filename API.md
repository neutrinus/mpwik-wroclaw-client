# MPWiK Wrocław API Documentation

This document describes the MPWiK Wrocław e-BOK (electronic customer service) API endpoints used by this client.

## Base URL

```
https://ebok.mpwik.wroc.pl/frontend-api/v1
```

## Authentication

### Login

Authenticate with the MPWiK e-BOK system.

**Endpoint:** `POST /login`

**Full URL:** `https://ebok.mpwik.wroc.pl/frontend-api/v1/login`

**Headers:**
```
Content-Type: application/json
Accept: application/json
Origin: https://ebok.mpwik.wroc.pl
Referer: https://ebok.mpwik.wroc.pl/login
```

**Request Body:**
```json
{
  "login": "123456",
  "password": "YourPassword"
}
```

**Response (200 OK):**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "123456",
    "name": "..."
  }
}
```

**Session Management:**
- After successful login, session cookies (`JSESSIONID`) are set
- Additional session headers are required for subsequent API calls:
  - `X-AccountId`: Account identifier
  - `X-Nav-Id`: Navigation/session identifier
  - `X-SessionId`: Session identifier

**Note:** When using browser automation, these session headers are automatically set by visiting the water consumption page (`/trust/zuzycie-wody?p={podmiot_id}`) after login.

---

## Network Points (Meters)

### List Network Points

Retrieve a list of water meters associated with an account.

**Endpoint:** `GET /podmioty/{podmiot_id}/punkty-sieci`

**Full URL:** `https://ebok.mpwik.wroc.pl/frontend-api/v1/podmioty/{podmiot_id}/punkty-sieci?status=AKTYWNE`

**Path Parameters:**
- `podmiot_id` (string, required): Entity ID (account number)

**Query Parameters:**
- `status` (string, optional): Filter by status. Default: `"AKTYWNE"` (active meters)

**Headers:**
```
Accept: application/json
Cookie: JSESSIONID=...
X-AccountId: ...
X-Nav-Id: ...
X-SessionId: ...
```

**Response (200 OK):**
```json
{
  "punkty": [
    {
      "id_punktu": 9876543,
      "numer": "0123/2021",
      "adres": "Plac Solny 1, Wrocław",
      "aktywny": true,
      "wspolrzedne": {
        "szerokosc": 51.1128,
        "dlugosc": 17.0262
      },
      "kod_podmiotu": "123456"
    }
  ]
}
```

**Response Fields:**
- `id_punktu` (integer): Unique identifier for the network point
- `numer` (string): Meter number (format: `"XXXX/YYYY"`)
- `adres` (string): Physical address of the meter
- `aktywny` (boolean): Whether the meter is active
- `wspolrzedne` (object): GPS coordinates
  - `szerokosc` (float): Latitude
  - `dlugosc` (float): Longitude
- `kod_podmiotu` (string): Entity code (podmiot ID)

**Note:** The `numer` field contains a forward slash (`/`) which should be converted to a dash (`-`) when used in API URLs (e.g., `0123/2021` → `0123-2021`).

---

## Water Consumption Readings

### Daily Readings

Retrieve daily water consumption readings for a specific meter.

**Endpoint:** `GET /podmioty/{podmiot_id}/punkty-sieci/{punkt_sieci}/odczyty/dobowe`

**Full URL:** 
```
https://ebok.mpwik.wroc.pl/frontend-api/v1/podmioty/{podmiot_id}/punkty-sieci/{punkt_sieci}/odczyty/dobowe?dataOd={start}&dataDo={end}
```

**Path Parameters:**
- `podmiot_id` (string, required): Entity ID (account number)
- `punkt_sieci` (string, required): Network point ID (meter number with dash, e.g., `"0123-2021"`)

**Query Parameters:**
- `dataOd` (string, required): Start date in ISO 8601 format with URL encoding
  - Format: `YYYY-MM-DDTHH:MM:SS`
  - Example (unencoded): `2025-11-04T00:00:00`
  - Example (encoded): `2025-11-04T00%3A00%3A00`
  - **Important:** Colons (`:`) must be URL-encoded as `%3A`
- `dataDo` (string, required): End date in ISO 8601 format with URL encoding
  - Format: Same as `dataOd`
  - Example (encoded): `2025-11-11T23%3A59%3A59`

**Headers:**
```
Accept: application/json
Content-Type: application/json
Cookie: JSESSIONID=...
X-AccountId: ...
X-Nav-Id: ...
X-SessionId: ...
```

**Example Request:**
```
GET https://ebok.mpwik.wroc.pl/frontend-api/v1/podmioty/123456/punkty-sieci/0123-2021/odczyty/dobowe?dataOd=2025-11-04T00%3A00%3A00&dataDo=2025-11-11T23%3A59%3A59
```

**Response (200 OK):**
```json
{
  "odczyty": [
    {
      "licznik": "C123B004567",
      "data": "2025-11-01T23:00:00",
      "wskazanie": 100.123,
      "zuzycie": 0.456,
      "srednia": 0.019,
      "typ": "Rutynowy"
    },
    {
      "licznik": "C123B004567",
      "data": "2025-11-02T23:00:00",
      "wskazanie": 100.579,
      "zuzycie": 0.456,
      "srednia": 0.019,
      "typ": "Rutynowy"
    }
  ]
}
```

**Response Fields:**
- `licznik` (string): Water meter ID/serial number
- `data` (string): Reading timestamp in ISO 8601 format
- `wskazanie` (float): Meter reading in cubic meters (m³)
- `zuzycie` (float): Water consumption in cubic meters (m³)
- `srednia` (float): Average daily consumption (m³/day)
- `typ` (string): Reading type (usually `"Rutynowy"` - routine)

---

### Hourly Readings

Retrieve hourly water consumption readings for a specific meter.

**Endpoint:** `GET /podmioty/{podmiot_id}/punkty-sieci/{punkt_sieci}/odczyty/godzinowe`

**Full URL:** 
```
https://ebok.mpwik.wroc.pl/frontend-api/v1/podmioty/{podmiot_id}/punkty-sieci/{punkt_sieci}/odczyty/godzinowe?dataOd={start}&dataDo={end}
```

**Path Parameters:**
- `podmiot_id` (string, required): Entity ID (account number)
- `punkt_sieci` (string, required): Network point ID (meter number with dash, e.g., `"0123-2021"`)

**Query Parameters:**
- `dataOd` (string, required): Start date/time in ISO 8601 format with URL encoding
  - Format: `YYYY-MM-DDTHH:MM:SS`
  - Example (unencoded): `2025-11-10T00:00:00`
  - Example (encoded): `2025-11-10T00%3A00%3A00`
  - **Critical:** Colons (`:`) MUST be URL-encoded as `%3A` or the API will return HTTP 400
- `dataDo` (string, required): End date/time in ISO 8601 format with URL encoding
  - Format: Same as `dataOd`
  - Example (encoded): `2025-11-10T23%3A59%3A59`

**Headers:**
```
Accept: application/json
Content-Type: application/json
Cookie: JSESSIONID=...
X-AccountId: ...
X-Nav-Id: ...
X-SessionId: ...
Referer: https://ebok.mpwik.wroc.pl/trust/zuzycie-wody?p={podmiot_id}
```

**Example Request:**
```
GET https://ebok.mpwik.wroc.pl/frontend-api/v1/podmioty/123456/punkty-sieci/0123-2021/odczyty/godzinowe?dataOd=2025-11-10T00%3A00%3A00&dataDo=2025-11-10T23%3A59%3A59
```

**Response (200 OK):**
```json
{
  "odczyty": [
    {
      "licznik": "C123B004567",
      "data": "2025-11-10T00:00:00",
      "wskazanie": 105.234,
      "zuzycie": 0.000,
      "typ": "Rutynowy"
    },
    {
      "licznik": "C123B004567",
      "data": "2025-11-10T01:00:00",
      "wskazanie": 105.234,
      "zuzycie": 0.000,
      "typ": "Rutynowy"
    },
    {
      "licznik": "C123B004567",
      "data": "2025-11-10T06:00:00",
      "wskazanie": 105.248,
      "zuzycie": 0.014,
      "typ": "Rutynowy"
    },
    {
      "licznik": "C123B004567",
      "data": "2025-11-10T07:00:00",
      "wskazanie": 105.421,
      "zuzycie": 0.173,
      "typ": "Rutynowy"
    }
  ]
}
```

**Response Fields:**
- `licznik` (string): Water meter ID/serial number
- `data` (string): Reading timestamp in ISO 8601 format (hourly intervals)
- `wskazanie` (float): Meter reading in cubic meters (m³)
- `zuzycie` (float): Water consumption for that hour in cubic meters (m³)
- `typ` (string): Reading type (usually `"Rutynowy"` - routine)

**Note:** Unlike daily readings, hourly readings do not include the `srednia` (average) field.

---

## Common Error Responses

### 400 Bad Request

**Cause:** Invalid request parameters or malformed URL

Common issues:
- DateTime parameters not URL-encoded (colons must be `%3A`)
- Invalid date format
- Invalid punkt_sieci format

**Example Error (unencoded datetime):**
```
Request: ?dataOd=2025-11-10T00:00:00  ❌
Correct: ?dataOd=2025-11-10T00%3A00%3A00  ✅
```

**Response:**
```json
{
  "error": "Bad Request",
  "message": "Invalid date format"
}
```

### 401 Unauthorized

**Cause:** Missing or invalid authentication

**Response:**
```json
{
  "error": "Unauthorized",
  "message": "Invalid credentials or session expired"
}
```

### 403 Forbidden

**Cause:** Missing session headers or insufficient permissions

**Response:**
```json
{
  "error": "Forbidden",
  "message": "Access denied"
}
```

### 404 Not Found

**Cause:** Invalid podmiot_id, punkt_sieci, or endpoint

**Response:**
```json
{
  "error": "Not Found",
  "message": "Resource not found"
}
```

---

## Implementation Notes

### URL Encoding

**Critical for hourly readings:** DateTime parameters MUST be URL-encoded.

```python
from urllib.parse import quote

date_str = "2025-11-10T00:00:00"
encoded = quote(date_str)  # "2025-11-10T00%3A00%3A00"
```

### Session Context

When using browser automation (Selenium), session headers are automatically set by:
1. Authenticating via the login page
2. Navigating to `/trust/zuzycie-wody?p={podmiot_id}`
3. Making API calls via `fetch()` with `credentials: 'include'`

This ensures `X-AccountId`, `X-Nav-Id`, and `X-SessionId` headers are included.

### Point Network Format

The `numer` field from `/punkty-sieci` uses format `"XXXX/YYYY"` but must be converted to `"XXXX-YYYY"` (dash instead of slash) when used in API URLs:

```python
punkt_sieci = punkt['numer'].replace('/', '-')
# "0123/2021" → "0123-2021"
```

### Date Ranges

- **Daily readings:** Can fetch multiple days (weeks or months)
- **Hourly readings:** **API accepts only single day requests**
  - The API returns HTTP 400 error if requesting more than 1 day
  - Default when using `--type hourly`: today only (00:00:00 to 23:59:59)
  - To fetch a specific day, use: `--date-from 2025-11-10 --date-to 2025-11-10`
  - **Important:** Both dates must be the same day
- **DateTime format:** Always use `YYYY-MM-DDTHH:MM:SS` format
- **Timezone:** Times appear to be in local timezone (Europe/Warsaw)

**Example:** For hourly data, request only one specific day:
```bash
# Good - today only (default)
--type hourly

# Good - specific day
--type hourly --date-from 2025-11-10 --date-to 2025-11-10

# Bad - multiple days will cause 400 error
--type hourly --date-from 2025-11-04 --date-to 2025-11-11  ❌
```

---

## Example Code

### Python (requests library)

```python
import requests
from urllib.parse import quote
from datetime import datetime, timedelta

BASE_URL = "https://ebok.mpwik.wroc.pl/frontend-api/v1"

# Authenticate
session = requests.Session()
login_response = session.post(
    f"{BASE_URL}/login",
    json={"login": "123456", "password": "YourPassword"}
)

# Get hourly readings
date_from = datetime(2025, 11, 10, 0, 0, 0)
date_to = datetime(2025, 11, 10, 23, 59, 59)

params = {
    'dataOd': date_from.strftime('%Y-%m-%dT%H:%M:%S'),
    'dataDo': date_to.strftime('%Y-%m-%dT%H:%M:%S')
}

response = session.get(
    f"{BASE_URL}/podmioty/123456/punkty-sieci/0123-2021/odczyty/godzinowe",
    params=params  # requests automatically URL-encodes
)

readings = response.json()['odczyty']
```

### JavaScript (fetch API in browser)

```javascript
const baseUrl = 'https://ebok.mpwik.wroc.pl/frontend-api/v1';

// Assume already authenticated and on /trust/zuzycie-wody page

const dateFrom = '2025-11-10T00:00:00';
const dateTo = '2025-11-10T23:59:59';

// URL encode the datetime parameters
const encodedFrom = encodeURIComponent(dateFrom);
const encodedTo = encodeURIComponent(dateTo);

const url = `${baseUrl}/podmioty/123456/punkty-sieci/0123-2021/odczyty/godzinowe?dataOd=${encodedFrom}&dataDo=${encodedTo}`;

fetch(url, {
    method: 'GET',
    credentials: 'include',
    headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
})
.then(response => response.json())
.then(data => {
    console.log('Hourly readings:', data.odczyty);
});
```

---

## Testing

You can test the API endpoints using curl:

```bash
# Login (save cookies)
curl -X POST 'https://ebok.mpwik.wroc.pl/frontend-api/v1/login' \
  -H 'Content-Type: application/json' \
  -d '{"login":"123456","password":"YourPassword"}' \
  -c cookies.txt

# Get hourly readings (using saved cookies)
curl -X GET 'https://ebok.mpwik.wroc.pl/frontend-api/v1/podmioty/123456/punkty-sieci/0123-2021/odczyty/godzinowe?dataOd=2025-11-10T00%3A00%3A00&dataDo=2025-11-10T23%3A59%3A59' \
  -H 'Accept: application/json' \
  -b cookies.txt
```

**Note:** Direct API testing may fail due to missing session headers. Browser automation is recommended for testing.

---

## Changes and Bug Fixes

### Issue: Hourly Readings HTTP 400 Error

**Problem:** Hourly readings endpoint was returning HTTP 400 error while daily readings worked fine.

**Root Causes:**
1. DateTime parameters were not URL-encoded (colons as `:` instead of `%3A`)
2. Missing session-specific headers (`X-AccountId`, `X-Nav-Id`, `X-SessionId`)
3. Date range too large - API rejects requests for more than 1 day of hourly data

**Solution:**
1. Use `urllib.parse.quote()` to URL-encode datetime parameters
2. Navigate to `/trust/zuzycie-wody?p={podmiot_id}` before making API calls to establish session context
3. Use browser's `fetch()` API with `credentials: 'include'` to automatically include session cookies and headers
4. Limit hourly readings to single day only (today: 00:00:00 to 23:59:59)

**Fixed in commits:**
- `a1e62d2`: Added URL encoding for datetime parameters
- `5255a48`: Navigate to water consumption page to set session headers
- `7a906e9`: Optimized navigation and improved debugging
- `3c237ec`: Changed default date range for hourly to 1 day, added network logging for failed requests
- `8e11180`: Fixed to fetch only today (single day) for hourly readings - **WORKING** ✅

---

## References

- MPWiK Wrocław e-BOK: https://ebok.mpwik.wroc.pl/
- Forum discussion: https://forum.arturhome.pl/t/bezsprzetowy-licznik-zuzycia-wody-mpwik-wroclaw/10883/11
