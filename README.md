# FormD T1 Monitor (Educational)

Python Playwright helper that watches FormD T1 product variants, then fires a notification call and opens checkout when stock appears. Built for educational and testing purposes only — please use responsibly and respect site terms.

## Requirements
- Python 3.10+ (Windows-friendly; uses `winsound`)
- `pip install curl_cffi playwright playwright-stealth`
- Playwright browser assets: `python -m playwright install chrome`

## Setup
1) Clone/download the repo and open a terminal in its folder.  
2) Copy `.env.example` to `.env` (or create `.env`) and fill in values:  
   - `CALL_LINK_TITANIUM`  
   - `CALL_LINK_SILVER`  
   - `VARIANT_TITANIUM_ID`, `VARIANT_TITANIUM_NAME`, `VARIANT_TITANIUM_URL`  
   - `VARIANT_SILVER_ID`, `VARIANT_SILVER_NAME`, `VARIANT_SILVER_URL`  
3) Optional: set `ENV_PATH` to point to a different env file.  
4) (Recommended) Use a virtualenv, then install dependencies from the list above.

## Usage
- Warm up and log in once (saves session locally):  
  `python t1bot.py warmup`
- Start monitoring (default mode):  
  `python t1bot.py monitor`
- Test the call hook without monitoring:  
  `python t1bot.py testcall Titanium`

The script reads all sensitive links/IDs from your `.env` (kept out of git). Session data is stored in `ghost_session_data` alongside the script.

## Notes
- For educational/testing use; do not abuse the target site.  
- Run from anywhere — the script resolves `.env` relative to its own directory unless `ENV_PATH` is set.  
- If Playwright launches fail, rerun `python -m playwright install chrome`.
