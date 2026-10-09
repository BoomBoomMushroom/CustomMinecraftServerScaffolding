# Custom Minecraft Server Scaffolding
A bare-bones Minecraft server that allows anyone to fork and implement any feature in the exact way they need.


![IMAGE HERE](./image/path/here.png)

Try it! An example server hosted on nest?

# Quick Start
1. Create a venv environment
    - `python -m venv .venv && source .venv/bin/activate`
2. Install dependencies + registries
    - `pip install -r requirements.txt`
    - Download [server.jar (Version 26.2)](https://minecraft.wiki/w/Java_Edition_26.2) and follow the instructions inside of `./registries/WhereFrom.txt`
        - The rundown is that you run `java -DbundlerMainClass=net.minecraft.data.Main -jar minecraft_server.jar --all` and then copy the `generated` folder to `./registries/26.2/generated`
3. Run the server!
    - `python main.py`

# Features
- Clients can connect to the server
- Easily modifiable server settings/information
    - Check `ServerSettings.py` and `gameRules.py`
- Lists implemented and unimplemented packets
- Verbose output while server is running



