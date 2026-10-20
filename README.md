# RUDRA – TrinityX · website and control station

## Files
- `rudra-trinityx-3d.html` – the complete website (single file, about 10 MB). Open it in Chrome, Edge or Firefox. Includes the 3D model, parts explorer, diagrams, gallery and the Control Station.
- `rudra_bridge.py` – starter program for the vehicle's onboard computer (WebSocket telemetry and commands, MJPEG camera stream, heartbeat failsafe).
- `images/originals` – every unique image you uploaded, unchanged.
- `images/hd-crops` – 31 close-up crops, enlarged 2x with sharpening.
- `images/cad-parts` – the first set of 33 crops from the blueprint and concept sheets.

## Use the Control Station
1. Open `rudra-trinityx-3d.html` from your computer (double-click it).
2. Press "Open control station". A Connections window opens.
3. Try it without hardware: "Run demo simulator" (camera is a live render of the 3D model) or "Test with my webcam".
4. Real vehicle: on the vehicle computer run
   `pip install aiohttp pillow` (add `opencv-python` for a real camera), then
   `python3 rudra_bridge.py --port 8765`
   In the page enter `ws://<vehicle-address>:8765/ws` and `http://<vehicle-address>:8765/video`, then press Connect.
   Pages served over https need `wss://` and `https://` addresses (localhost is the exception).
   Optional token: start the bridge with `RUDRA_TOKEN=secret` and type the same token in the page.

## Maps
Satellite and street maps need an internet connection and use outside tile services:
- Street: OpenStreetMap standard tiles (attribution shown on the map). Their tile policy is meant for light use.
- Satellite: Esri World Imagery tiles (attribution shown on the map). Check Esri's terms for your use.
- Custom: paste any tile URL with {z} {x} {y} under Connections, for example your own provider with an API key. Use this for production or heavy use.
- Offline: a plain grid that needs no internet.

## Message format
Vehicle to page, about 5 per second:
`{"t":"tel","mode":"land","bat":78,"volt":48.6,"temp":32,"speed":2.4,"alt":0,"lat":23.043,"lng":84.542,"hdg":243,"roll":0,"pitch":0,"rssi":97,"sats":12,"gps":"12/16","acc":2.5,"obst":{"f":3.2,"l":4.8,"r":5.1,"b":6.7},"locks":{"rotors":"FOLDED","wheels":"6 LOCKED"},"net":{"wifi":1,"radio":1,"cell":0},"mot":[50,50,50,50]}`
Also `{"t":"pong","ts":...}` and `{"t":"log","msg":"..."}`.

Page to vehicle: `hello`, `hb` every 0.5 s, `ctl` (roll, pitch, yaw, thr from -1 to 1), `mode`, `cmd` (arm, disarm, takeoff, land, rth, hover, estop, goto), `mission` (list of waypoints).

## Safety
- `rudra_bridge.py` is a STUB. It prints commands and sends simulated numbers marked `"stub": true`. Connect its Vehicle class to the real flight controller and motor drivers before any real use.
- The vehicle must fail safe by itself when heartbeats stop. The bridge disarms after 1.5 s without a heartbeat.
- Keep a hardware emergency stop on the vehicle. The on-screen stop is not a substitute.
- Follow local rules for drones, radio and water operation before any field test.
