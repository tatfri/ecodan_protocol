### Mitsubishi CN105 protocol Python implementation

This is generated with Copilot from reverse-engineered protocol specifications from
the [ESPHome Ecodan heatpump](https://github.com/gekkekoe/esphome-ecodan-hp/blob/main/protocol.md)
project.

The most important change to the code generated from the specification is that the CN105 protocol
is __big-endian__. Also, the heat pump controller will only answer if you send a connect request
before other messages.

> [!CAUTION]
> __Use at your own risk.__
>
> This is an unofficial, unsupported implementation based on reverse-engineered Mitsubishi Electric protocol. [Melcloud](https://www.melcloud.com/en) is Mitsubishi Electric's officially supported commercial solution for remote control of compatible heat pumps.
>
> I have only tested that received values are reasonable and that setters work to the extent that was needed
> for [my heat pump control project](https://github.com/tatfri/ecodan_control). As for the setters, that only includes setting
> zone1 temperature setpoint and starting forced DHW heating.
>
> Some of the setter commands could have side effects that are not completely understood. Their use could potentially damage your heat pump or building. __Only use the setter commands if you understand their function
> and accept the risk.__

# Example

```python
from ecodan_protocol import EcodanClient

with EcodanClient("/dev/ttyUSB0") as client:
     client.connect()
     reponse = client.get_water_flow_temperatures()
     print(response)
     client.set_options(z1_setpoint=21.0)
```
