# conf files

| *document* | conf files explanation                                         |
|:----------:|:---------------------------------------------------------------|
| *version*  | 1.0                                                            |
| *date*     | 11 août 2015                                                   |
| *auteur*   | Mollé Benjamin, <benjamin.molle@gmail.com>                     |
| *copyright*| Copyright 2015 Orange                                          |
| *license*  | CC BY CA                                                       |


## Brief

Explanation of the content of the folder **conf**

## Udev rules

*25-node-usb.rules* is a udev rules for Iotlab-M3 node.
You can copy it in `/etc/udev/rules.d/`

```bash
cp 25-node-usb.rules /etc/udev/rules.d/
```
____
## Systemd service

*observer-node.service* is the systemd Unit file for Observer.
You can copy it in `/etc/systemd/system/`

```bash
cp observer-node.service /etc/systemd/system/
```
and enable it :
```bash
systemctl enable observer-node.service
```

For more details, see *observer-setup* file.