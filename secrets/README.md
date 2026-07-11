# Optional local API secret

The desktop application does not need an API key. Developers who enable API
authentication can generate a local key with:

``` powershell
New-Item -ItemType Directory -Force secrets | Out-Null
python scripts/generate_api_key.py | Set-Content -NoNewline secrets/freshsense_api_key.txt
```

`freshsense_api_key.txt` is ignored by Git. Configure its absolute path with
`FRESHSENSE_API_KEY_FILE`, set `FRESHSENSE_REQUIRE_API_KEY=true`, and start the
local API. Never paste the key into source code, issues, pull requests, chat
messages, or logs.
