# Qingping CGD1 Alarm Clock

Local Bluetooth control of the Qingping CGD1 alarm clock - no cloud, no app.

Reset the clock first if it's paired with another app: hold the button
until the Bluetooth icon flashes, or remove it in the Qingping+ app.

- Temperature, humidity, battery and signal strength, read passively from
  the clock's own advertisements.
- Volume, brightness, backlight, language, time format, temperature unit
  and night mode, read and written over Bluetooth.
- All 16 alarm slots, plus `set_alarm`, `delete_alarm` and `sync_time`
  services.

Home Assistant's built-in `qingping` integration also matches this clock's
advertisement. Add it through **this** integration, not the built-in one -
this one adds full control (alarms, settings, time sync) on top of the sensors.

See the [README](https://github.com/rjocoleman/ha-qingping-cgd1) for the
full entity list and service examples.
