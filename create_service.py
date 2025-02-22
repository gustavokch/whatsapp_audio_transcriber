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
StandardOutput=append:{currentdir}/logs/systemd.log
StandardError=append:{currentdir}/logs/systemd.log

[Install]
WantedBy=default.target

[Timer]
OnBootSec=0
OnUnitActiveSec=2h
"""
    restarter_content = f"""[Unit]
Description=Restart WhatsApp transcription service(s)

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl --user restart whatsapp_{name}.service

[Install]
WantedBy=default.target
"""
    timer_content = f"""[Unit]
Description=Run WhatsApp restart service every two hours

[Timer]
OnBootSec=60s
OnUnitActiveSec=2h
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

    os.system(f"systemctl --user daemon-reload")
    os.system(f"systemctl --user enable whatsapp_{name}.service")
    os.system(f"systemctl --user start whatsapp_gus.service")
    print(f"Service enabled and started.")
    os.system(f"cp -f restart_whatsapp_services.* ~/.config/systemd/user/")
    os.system(f"systemctl --user daemon-reload")
    os.system(f"systemctl --user enable restart_whatsapp_services.service")
    os.system(f"systemctl --user enable restart_whatsapp_services.timer")

# Example usage:
def parse_name(calls_n):
    if calls_n == 0:
        name = input("Name prefix: ")  # Replace with the desired name
        name_list.append(name)
        
    if calls_n > 1:
        name = input("next name prefix: ")  # Replace with the desired name
    add_another = input("Press 1 to add another prefix to the restart service")
    if add_another != "":
        calls_n = calls_n + 1
        return name
    if add_another == "1":
        return 666
    
currentdir = os.getcwd()
name_list = []
calls_n = 0
prefix = parse_name(calls_n)
if prefix == 666:
    name_list.append(parse_name(calls_n))
    calls_n = calls_n + 1
else:
    if prefix not in name_list:
        name_list.append(prefix)
    fix_start_script()
count = 0
for n in name_list:
    count = count + 1
    create_systemd_unit(n)

if count >= len(name_list):
    copy = input("Press '1' to copy the file to ~/.config/systemd/user/ and enable it: ")
    if copy == "1":
        for n in name_list:
            name=name_list[n]
            copy_files(name)