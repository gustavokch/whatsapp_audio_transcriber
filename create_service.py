import os
from dotenv import load_dotenv

currentdir = os.getcwd()

def create_systemd_unit(name: str):

    filename = f"whatsapp_{name}.service"
    content = f"""[Unit]
Description=Run WhatsApp transcriber ({name})
After=network.target

[Service]
Type=simple
Environment="TMPLOGDIR={currentdir}/logs"
ExecStart=/bin/bash -c "{currentdir}/start.sh"
Restart=always
RestartSec=5s
StandardOutput=append:{currentdir}/logs/handler.log
StandardError=append:{currentdir}/logs/handler.log

[Install]
WantedBy=default.target

[Timer]
OnBootSec=0
OnUnitActiveSec=2h
"""
    restarter_content = f"""[Unit]
Description=Restart WhatsApp Mime and Gus services

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl --user restart whatsapp_mime.service whatsapp_gus.service

[Install]
WantedBy=default.target
"""
    timer_content = f"""[Unit]
Description=Restart WhatsApp services every 2 hours

[Timer]
OnCalendar=*-*-* */2:00:00
Persistent=true

[Install]
WantedBy=timers.target
"""
        

    with open(filename, "w") as file:
        file.write(content)
    print(f"Systemd unit file '{filename}' created successfully.")
    with open("restart_whatsapp_services.service", "w") as file:
        file.write(restarter_content)
    print(f"Systemd unit file 'restart_whatsapp_services.service' created successfully.")
    with open("restart_whatsapp_services.timer", "w") as file:
        file.write(timer_content)
    print(f"Systemd unit file 'restart_whatsapp_services.timer' created successfully.")

def fix_start_script():
    currentdir = os.getcwd()
    print(currentdir)
    with open("start.sh", "r") as file:
        start_script = file.read()
        print("Script read successfully.")
        if currentdir == "/home/ubuntu/whatsapp_bots/whatsapp_audio_transcriber":
            print("Dir variable: "+str(os.system("echo $GUSDIR")))
            start_script = start_script.replace("$GUSDIR", str(currentdir))
            

        elif currentdir == "/home/ubuntu/whatsapp_bots/whatsapp_audio_transcriber_mime":
            start_script = start_script.replace("$GUSDIR", str(currentdir))
    file.close()
    with open("start.sh", "w") as file:
        file.write(start_script)
        os.system("chmod +x start.sh")
        print("start.sh script updated successfully.")

def copy_files(name):
    os.system(f"cp -f whatsapp_*.service ~/.config/systemd/user/")
    if name != "mime":
        os.system(f"systemctl --user daemon-reload")
        os.system(f"systemctl --user enable whatsapp_gus.service")
        os.system(f"systemctl --user start whatsapp_gus.service")
        print(f"Service enabled and started.")
    elif name != "gus":
        os.system(f"systemctl --user daemon-reload")
        os.system(f"systemctl --user enable whatsapp_mime.service")
        os.system(f"systemctl --user start whatsapp_mime.service")
        print(f"Service enabled and started.")
    else:
        os.system(f"systemctl --user daemon-reload")
        os.system(f"systemctl --user enable whatsapp_{name}.service")
        os.system(f"systemctl --user start whatsapp_{name}.service")
        print(f"Service enabled and started.")
    os.system(f"cp -f restart_whatsapp_services.* ~/.config/systemd/user/")
    os.system(f"systemctl --user daemon-reload")
    os.system(f"systemctl --user enable restart_whatsapp_services.service")
    os.system(f"systemctl --user enable restart_whatsapp_services.timer")

# Example usage:
name = input("Name prefix: ")  # Replace with the desired name
currentdir = os.getcwd()

if name != "gus" and name != "mime":
    print("Invalid name prefix. Please use 'gus' or 'mime'.")
    exit(1)
fix_start_script()
create_systemd_unit(name)

copy = input("Press '1' to copy the file to ~/.config/systemd/user/ and enable it: ")
if copy == "1":
    copy_files(name)