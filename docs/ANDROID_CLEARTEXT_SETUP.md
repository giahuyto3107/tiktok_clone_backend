# Android Cleartext Communication Setup

## Problem
Android 9+ (API level 28+) blocks cleartext (non-HTTPS) HTTP traffic by default for security.

**Error message:**
```
CLEARTEXT communication to ... (wifi ip address) not permitted
```

## Solution: Allow Cleartext Traffic (Development Only)

**⚠️ WARNING: Only for development! Never use in production!**

Backend is already configured with `--host 0.0.0.0` to accept connections from WiFi IP addresses. You just need to configure Android app to allow cleartext HTTP traffic.

### Option 1: Network Security Config (Per Domain) - Recommended

Create `res/xml/network_security_config.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">192.168.1.100</domain>
        <domain includeSubdomains="true">10.0.2.2</domain> <!-- Android Emulator -->
    </domain-config>
</network-security-config>
```

Add to `AndroidManifest.xml`:
```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ...>
```

### Option 2: Allow All Cleartext (Not Recommended)

In `AndroidManifest.xml`:
```xml
<application
    android:usesCleartextTraffic="true"
    ...>
```

**Note:** Option 1 (per-domain) is safer as it only allows cleartext for specific IP addresses.

---

## Finding Your WiFi IP Address

**Windows:**
```cmd
ipconfig
```
Look for "IPv4 Address" under your WiFi adapter (e.g., `192.168.1.100`)

**Linux/Mac:**
```bash
ifconfig
# or
ip addr show
```

**Android Emulator:**
- Use `10.0.2.2` to access `localhost` on your development machine

---

## Testing

1. **Backend running:**
   ```bash
   python main.py
   ```

2. **Check from Android device:**
   - HTTP: `http://YOUR_WIFI_IP:8000/health`

3. **Expected response:**
   ```json
   {"status": "healthy"}
   ```

---

## Backend Configuration

Make sure backend is running with `--host 0.0.0.0`:

```bash
# FastAPI CLI
fastapi dev main.py --host 0.0.0.0 --port 8000

# Or Python script
python main.py
```

This allows the server to accept connections from WiFi IP addresses (not just localhost).

## Production Notes

- **Never** use `cleartextTrafficPermitted="true"` in production
- Use proper SSL certificates (Let's Encrypt, etc.) for production
- Configure domain-specific network security config
- Use certificate pinning for sensitive apps
