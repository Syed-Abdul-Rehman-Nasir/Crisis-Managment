# CIRO — Offline Android APK

## What this build does

- Bundles all demo scenarios inside the app (no Python server).
- Status shows **LOCAL DEMO**.
- Map tiles still load from the internet when you open the **Map** tab.

## Build APK (on your PC)

1. Install [Android Studio](https://developer.android.com/studio) (SDK + JDK).
2. From `frontend/`:

```bash
npm install
npm run cap:android
```

3. In Android Studio: **Build → Build Bundle(s) / APK(s) → Build APK(s)**.
4. APK path (typical): `android/app/build/outputs/apk/debug/app-debug.apk`

## Install on a phone

1. Copy APK to the device.
2. Allow install from unknown sources.
3. Open **CIRO Crisis** → tap **FLOOD**, then **FALSE POSITIVE**.

## Web dev (still uses backend)

```bash
npm run dev
```

Uses `http://localhost:8000` unless you set `VITE_OFFLINE_DEMO=true` in `.env.local`.

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run build:mobile` | Production build with offline demo |
| `npm run cap:sync` | Build + copy into Android project |
| `npm run cap:android` | Sync and open Android Studio |
