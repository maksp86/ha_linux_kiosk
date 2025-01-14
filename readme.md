# Linux kiosk service for HomeAssistant
written on python 3.12

**Dependencies:**
- NetworkManager
- chromium
- dbus
- python3.13 or newer with venv

**Installation (Arch in my case):**
Create autologin override for getty@tty1 service
```
mkdir "/etc/systemd/system/getty@tty1.service.d/"
nano /etc/systemd/system/getty\@tty1.service.d/autologin.conf
```

Content
```
[Service]
ExecStart=
ExecStart=-/sbin/agetty -o '-p -f -- \\u' --noclear --autologin kiosk_user_name %I $TERM
```
  
  
  
Create user with groups (tty video), give users permission to set brightness in udev rules, su into user
```
useradd -m -G tty,video kiosk_user_name
echo 'SUBSYSTEM=="backlight",RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"' | tee -a /etc/udev/rules.d/backlight-permissions.rules
su kiosk_user_name
```

Clone repository and go to folder
```
git clone https://github.com/maksp86/ha_linux_kiosk.git
cd ha_linux_kiosk
cp .env.example .env
nano .env # fill your credentials
```

Create venv and install requirements
```
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create .xinitrc with following content
```
xrandr --output DSI1 --rotate right --fb 1280x800 # optional, set if you need

unclutter --start-hidden --timeout=1 &
cd ~/ha_linux_kiosk/ &&
source .venv/bin/activate &&
python __init__.py
```

Create .bash_profile with following content
```
[[ -f ~/.bashrc ]] && . ~/.bashrc

if [ -z "$DISPLAY" ] && [ "$XDG_VTNR" = 1 ]; then
  exec startx &>/dev/null
fi
```