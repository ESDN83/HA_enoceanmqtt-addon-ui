# Documentation Screenshots

Capture these screenshots from the running addon for the README and GitHub releases.

## Required Screenshots

### 1. `dashboard.png` — Dashboard overview
- Shows MQTT connected (green), EnOcean connected (green)
- Device count and profile count visible
- Some recent telegrams in the feed

### 2. `dashboard-dark.png` — Dashboard in dark mode
- Same as above but with HA dark theme active

### 3. `devices.png` — Devices list page
- Several device cards visible (sensor + actuator)
- Search bar at top

### 4. `device-detail.png` — Device detail view
- Shows a device with recent telegrams, MQTT topics, test buttons

### 5. `profiles.png` — EEP Profiles tree
- RORG tree expanded to show FUNC/TYPE levels
- Custom profile section at top (yellow highlight)

### 6. `custom-profile.png` — Custom Profile editor
- Modal open with fields filled in
- HA Entity Mapping section visible with rows

### 7. `teach-in.png` — Teach-In page
- Teach-in countdown timer active
- "Waiting for device..." indicator

### 8. `settings.png` — Settings page
- Import/Export buttons
- Local Backups section with backup list
- System restart button

### 9. `settings-backup-confirm.png` — Restore confirmation popup
- Modal asking "Are you sure you want to restore?"

### 10. `actuator-teach-in.png` — Actuator teach-in
- Actuator teach-in form with sender offset, base ID

## How to Capture

1. Start the addon in Home Assistant
2. Open the web UI via sidebar
3. Use browser DevTools > screenshot (Ctrl+Shift+P > "Capture screenshot")
4. For dark mode: enable HA dark theme in Profile > Theme
5. Crop to content area (no browser chrome)
6. Save as PNG, max width 1200px
