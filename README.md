# Häfele Mesh Local MQTT Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

A Home Assistant custom component for local control of Häfele Mesh devices via MQTT.

## Features

- **Local Control**: Direct MQTT communication with your Häfele Mesh gateway - no cloud required
- **Device Discovery**: Automatic detection of lights, groups, and scenes
- **Full Light Control**: 
  - On/Off control
  - Brightness adjustment
  - Color temperature (for supported devices)
  - HSL color control (for RGB devices)
- **Scene Activation**: Trigger predefined scenes
- **Group Support**: Control multiple lights as groups
- **Real-time Updates**: Instant state synchronization via MQTT

## Requirements

- Home Assistant 2023.1.0 or newer
- Häfele Connect Gateway with local MQTT access
- MQTT broker (Mosquitto add-on recommended) - **The integration will automatically detect when MQTT is available**

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/paulschmid/haefele-mesh-connect-local`
6. Select category "Integration"
7. Click "Add"
8. Find "Häfele Mesh Local" in the integration list
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/haefele_mesh` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

> **Note**: This integration depends on the MQTT integration. When you install the Mosquitto broker add-on or configure MQTT in Home Assistant, the Häfele Mesh integration will become available automatically.

### Setup Methods

The integration offers **two convenient setup methods**:

#### Option 1: Automatic Setup (Recommended)

Perfect for users with the **Mosquitto broker** add-on:

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **Häfele Mesh Local**
4. Select **"Automatic (Mosquitto Add-on)"**
5. Enter your **Gateway MQTT Topic** (default: `Mesh`)
6. **Save the generated credentials** displayed on screen:
   - MQTT Broker URL
   - Username
   - Password
   - Topic
7. Enter these credentials in your **Häfele Mesh Connect app**
8. Click **Submit** to complete setup

The integration will automatically:
- Create a secure MQTT user in Mosquitto
- Generate a strong random password
- Configure the connection
- Display credentials for your Häfele gateway

#### Option 2: Manual Configuration

For advanced users or custom MQTT brokers:

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **Häfele Mesh Local**
4. Select **"Manual MQTT Configuration"**
5. Enter your MQTT broker details:
   - **MQTT Broker Host**: IP address or hostname (default: `localhost`)
   - **MQTT Broker Port**: Port number (default: `1883`)
   - **Username**: MQTT username (optional)
   - **Password**: MQTT password (optional)
   - **Gateway MQTT Topic**: The base topic (default: `Mesh`)

## MQTT Configuration

### Setting up MQTT Broker

If you don't have an MQTT broker yet:

1. Install the **Mosquitto broker** add-on from the Add-on Store
2. Configure it with basic settings
3. Start the broker
4. Proceed with **Automatic Setup** (recommended)

### Häfele Gateway Configuration

After completing the Home Assistant setup, configure your Häfele Connect Gateway:

1. Open the **Häfele Mesh Connect** mobile app
2. Go to gateway settings
3. Configure MQTT connection:
   - Enter the **MQTT Broker URL** (displayed during setup)
   - Enter the **Username** (displayed during setup)
   - Enter the **Password** (displayed during setup)
   - Set the **Topic** to match your configuration (default: `Mesh`)
4. Save and verify the connection

> **Tip**: The default topic is now `Mesh` instead of `haefele/gateway` for cleaner MQTT paths.

## Supported Devices

This integration supports all Häfele Mesh devices that communicate via the gateway:

- **Lights**: Individual dimmable lights, color temperature lights, and RGB lights
- **Groups**: Predefined groups of lights
- **Scenes**: Stored lighting scenes


## Troubleshooting

### Integration not discovering devices

1. Check that your MQTT broker is running and accessible
2. Verify the gateway topic matches your Häfele gateway configuration
3. Check Home Assistant logs for MQTT connection errors
4. Ensure your Häfele gateway is connected to the MQTT broker

### Devices not responding to commands

1. Check MQTT broker logs for incoming/outgoing messages
2. Verify the device names match exactly (case-sensitive)
3. Ensure the gateway is properly communicating with the mesh network

### Enable Debug Logging

Add to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.haefele_mesh: debug
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Credits

- Based on the [Häfele Connect MQTT API](https://help.connect-mesh.io/mqtt/index.html)
- Uses [paho-mqtt](https://pypi.org/project/paho-mqtt/) for MQTT communication

## Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/paulschmid/haefele-mesh-connect-local/issues) page.

## Disclaimer

This is an unofficial integration and is not affiliated with or endorsed by Häfele.
