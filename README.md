# Qingping CGD1 Alarm Clock

A Home Assistant integration for the
[Qingping CGD1 Bluetooth alarm clock](https://www.qingping.co/bluetooth-alarm-clock/specifications).
It runs entirely over local Bluetooth Low Energy - no cloud account, no app, no
internet dependency. Sensor readings come from the clock's own advertisements;
settings and alarms are read and written over a direct BLE connection.

Not affiliated with or endorsed by Qingping. "Qingping" is used only to say
which device this works with.

## Before you add the clock

A CGD1 only accepts one paired app at a time. If yours is already set up in
the Qingping+ app (or was previously added to another Home Assistant
instance), Home Assistant's setup will fail with an authentication error.

Reset the clock first:

- Press and hold the clock's button until the Bluetooth icon flashes, or
- Remove the clock in the Qingping+ app.

Once reset, the clock pairs with the first app that connects, so add it here
straight after resetting.

## A note about the built-in `qingping` integration

Home Assistant ships its own `qingping` integration, and its Bluetooth
matching picks up the CGD1's advertisement too. Because of this, Home
Assistant may offer to set up the clock through both integrations.

Add it through **this** integration and ignore the built-in one. The built-in
`qingping` is local Bluetooth like this one, but it only listens to
advertisements passively, so it exposes sensors and nothing else - no alarms,
no display settings, no time sync (and it doesn't list the CGD1 among its
supported devices anyway). This integration also connects to the clock, so you
get the full control surface on top of the sensors.

## What this integration does

- **Sensors**, read passively from the clock's Bluetooth advertisements -
  no connection needed, so they keep working even if the clock is out of
  range of an active BLE link: temperature, humidity, battery and signal
  strength.
- **Settings and alarms**, read and written over an active BLE connection
  that the integration opens on demand: volume, day/night display
  brightness, backlight timeout, language, time format, temperature unit,
  night mode and its time window, and all 16 alarm slots (time and
  enabled state).
- **Time sync**, pushed to the clock automatically on every successful
  connection (an option you can turn off), or manually via a button or
  service call. The clock's crystal drifts and it has no DST logic of its
  own, so the integration also polls periodically (every 24 hours by
  default, configurable, 0 to disable) to correct drift and, if the clock's
  stored timezone offset no longer matches Home Assistant's current one,
  update it. This is what keeps the clock (and the next-alarm sensor)
  correct across a DST change.

## Installing through HACS

This is a custom repository. The quickest way is the button below, which
opens HACS on your Home Assistant with this repo pre-filled:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rjocoleman&repository=ha-qingping-cgd1&category=integration)

Then download it and restart Home Assistant.

Or add it by hand:

1. In Home Assistant, open HACS.
2. Open the three-dot menu, choose **Custom repositories**.
3. Add `https://github.com/rjocoleman/ha-qingping-cgd1` with category
   **Integration**.
4. Search for **Qingping CGD1 Alarm Clock** and download it.
5. Restart Home Assistant.

This integration depends on the
[`qingping-cgd1`](https://github.com/rjocoleman/qingping-cgd1) Python library
for the Bluetooth protocol. Home Assistant installs it from PyPI itself, from
the integration's `manifest.json`, the first time the integration loads (HACS
only copies the files; it doesn't install Python packages).

## Setting it up

1. Reset the clock (see above) if it is paired with anything else.
2. Go to **Settings -> Devices & services**. Home Assistant should discover
   the clock automatically; if not, use **Add integration** and search for
   **Qingping CGD1 Alarm Clock**.
3. Confirm the auth token. Leave the default: once you have reset the clock
   (step 1) it binds to whatever connects first, which is this default. You
   only need to change it if you deliberately manage your own pairing tokens.

If setup fails with an authentication error, the clock is still paired with
something else. Reset it as described above and try again.

### Options

Open the integration and choose **Configure** to turn automatic time sync
on connection off, if you would rather sync manually via the button or
service. The same form lets you turn off timezone matching or change the
periodic sync interval.

## Entities

| Entity | Type | Notes |
| --- | --- | --- |
| Temperature | Sensor | From advertisements |
| Humidity | Sensor | From advertisements |
| Battery | Sensor (diagnostic) | From advertisements |
| Signal strength | Sensor (diagnostic) | From advertisements |
| Firmware | Sensor (diagnostic) | Read over BLE |
| Next alarm | Sensor | Soonest enabled alarm, as a timestamp |
| Volume | Number | 1-5 |
| Day Brightness | Number | 0-100% |
| Night Brightness | Number | 0-100% |
| Backlight Timeout | Number | 0-30 seconds |
| Language | Select | Chinese / English |
| Time Format | Select | 24-hour / 12-hour |
| Temperature Unit | Select | Celsius / Fahrenheit |
| Alarms | Switch | Master alarm enable |
| Night Mode | Switch | |
| Alarm 1-16 enabled | Switch | Only alarms 1 and 2 are enabled by default; enable the rest yourself |
| Night Mode From / To | Time | Night mode window |
| Alarm 1-16 time | Time | Only alarms 1 and 2 are enabled by default |
| Sync time | Button | Pushes the current time to the clock |

Alarm slots 3-16 are disabled by default to keep the entity list manageable.
Enable the ones you need from the entity's settings.

## Services

### `qingping_cgd1.set_alarm`

Write a single alarm slot, including its days and snooze setting.

```yaml
action: qingping_cgd1.set_alarm
target:
  device_id: <your clock's device id>
data:
  slot: 0
  time: "07:30:00"
  days: [monday, wednesday, friday]
  snooze: true
  enabled: true
```

### `qingping_cgd1.delete_alarm`

Clear a single alarm slot.

```yaml
action: qingping_cgd1.delete_alarm
target:
  device_id: <your clock's device id>
data:
  slot: 0
```

### `qingping_cgd1.sync_time`

Push the current time to the clock. Same effect as the **Sync time** button.

```yaml
action: qingping_cgd1.sync_time
target:
  device_id: <your clock's device id>
```

## Limitations

- Custom ringtones aren't supported. The clock can take an uploaded ringtone
  (clOwOck documents the audio-transfer protocol), but it's fiddly and out of
  scope here.
- The clock stores its timezone offset in 6-minute steps, so an unusual offset
  like +5:45 rounds slightly when the integration matches Home Assistant's
  timezone.

## Removing it

Go to **Settings -> Devices & services**, open the integration, and delete
the entry. The device and its entities are removed with it. If the clock
still shows as paired afterwards, reset it as described above before
setting it up with anything else.

## Credits

The BLE protocol was mapped by
[MrBoombastic/clOwOck](https://github.com/MrBoombastic/clOwOck), an Android app
for the CGD1. Its reverse-engineered protocol notes (authentication, GATT
layout, sensor and alarm formats) are what this integration and its library are
built from.

## Other options for this clock

- Home Assistant's built-in
  [`qingping`](https://www.home-assistant.io/integrations/qingping/) integration
  - passive Bluetooth sensors, no control.

This integration does both: the temperature, humidity and battery sensors from
the advertisements, and full control over a connection, plus the reset/reauth
handling and DST-aware time sync described above.

## How this was built

The integration, its `qingping-cgd1` library, and these docs were built largely
with AI assistance (Claude), then reviewed and tested against a real CGD1
(firmware 1.0.1_0130). It works and it's tested, but it's a spare-time project -
no warranty, no support promises.

## Licence

MIT.
