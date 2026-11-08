# Daytime Frontlight Dimmer for KOReader

This plugin lets **AutoWarmth** control the Kindle frontlight at sunrise and sunset, while adding a five-minute idle timeout only during daylight:

- At night, it leaves the frontlight alone.
- During daylight, a touch turns the frontlight on if it is off.
- After five minutes without input in daylight, it turns the frontlight off.
- A later daytime touch turns it on again and restarts the five-minute idle period.

The plugin uses the location saved by AutoWarmth to calculate sunrise and sunset. If solar times cannot be calculated, it will not dim the light.

## Install

Copy the `daylightdimmer.koplugin` folder into KOReader's `plugins` folder on the Kindle, then restart KOReader. For a standard Kindle installation, this is usually:

```text
/mnt/us/koreader/plugins/daylightdimmer.koplugin/
```

## Configure

1. In KOReader, open **Settings → Screen → AutoWarmth**.
2. Set **Activate → According to the sun's position**, set the correct location, and enable **Frontlight off during day**.
3. Disable KOReader's built-in **Automatic dimmer** so it cannot dim the frontlight at night.
4. Open the main menu and enable **Daytime frontlight dimmer**.

The timeout is fixed at five minutes. This plugin responds to touch and other KOReader input while the device is awake; timers do not run while the Kindle is suspended.
