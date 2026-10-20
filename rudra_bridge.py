#!/usr/bin/env python3
"""
RUDRA - TrinityX ground-station bridge (starter).

Runs on the vehicle's onboard computer (Raspberry Pi, Jetson, laptop).
  * WebSocket  /ws     telemetry out (5 Hz), commands in
  * MJPEG      /video  camera stream (OpenCV camera, or a test pattern if none)
  * Heartbeat watchdog: controls drop to zero and the vehicle disarms if the
    page stops sending heartbeats for 1.5 s.

IMPORTANT: the Vehicle class below is a STUB. It prints commands and reports
simulated numbers (marked "stub": true). Replace its methods with calls to your
real flight controller, ESCs and sensors (for example MAVLink via pymavlink).
Keep a hardware emergency stop on the vehicle. This software is no substitute.

Install:  pip install aiohttp pillow        (optional: opencv-python for a camera)
Run:      python3 rudra_bridge.py --port 8765
Token:    RUDRA_TOKEN=secret python3 rudra_bridge.py   (page sends ?token=secret)
"""
import argparse, asyncio, io, json, math, os, time
from aiohttp import web, WSMsgType
try:
    import cv2
except ImportError:
    cv2 = None
try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None

TOKEN = os.environ.get("RUDRA_TOKEN", "")
WATCHDOG_S = 1.5


class Vehicle:
    """Replace these methods with real hardware control."""
    def __init__(self):
        self.mode, self.armed = "land", False
        self.ctl = dict(roll=0, pitch=0, yaw=0, thr=0)
        self.lat, self.lng, self.hdg, self.alt, self.bat = 23.043, 84.542, 243.0, 0.0, 78.0
        self.last_hb = time.time()

    def set_mode(self, m):
        if m in ("air", "water", "land"):
            self.stop_all(); self.mode = m; print("MODE ->", m)   # run the transition sequence here

    def arm(self, on):
        self.armed = on; print("ARMED" if on else "DISARMED")
        if not on: self.stop_all()

    def control(self, roll, pitch, yaw, thr):
        if self.armed: self.ctl = dict(roll=roll, pitch=pitch, yaw=yaw, thr=thr)   # mix to motors here

    def stop_all(self):
        self.ctl = dict(roll=0, pitch=0, yaw=0, thr=0)

    def estop(self):
        self.armed = False; self.stop_all(); print("EMERGENCY STOP")   # cut propulsion power here

    def command(self, c, m):
        print("CMD", c, {k: v for k, v in m.items() if k not in ("t", "cmd")})   # takeoff / land / rth / hover / goto

    def step(self, dt):
        c = self.ctl
        self.hdg = (self.hdg + c["yaw"] * 30 * dt) % 360
        v = c["pitch"] * (8 if self.mode == "air" else 2.5)
        r = math.radians(self.hdg)
        self.lat += v * math.cos(r) * dt / 110540
        self.lng += v * math.sin(r) * dt / (111320 * math.cos(math.radians(self.lat)))
        if self.mode == "air" and self.armed:
            self.alt = max(0, min(120, self.alt + c["thr"] * 3 * dt))
        if self.armed: self.bat = max(5, self.bat - 0.01 * dt * 5)
        return v

    def telemetry(self, v):
        t = time.time()
        return {"t": "tel", "stub": True, "mode": self.mode, "bat": self.bat, "volt": 42 + self.bat * 0.0846,
                "temp": 32, "speed": abs(v), "alt": self.alt, "lat": self.lat, "lng": self.lng, "hdg": self.hdg,
                "roll": self.ctl["roll"] * 10, "pitch": -self.ctl["pitch"] * 8, "rssi": 95, "sats": 12,
                "obst": {"f": 3.2 + math.sin(t), "l": 4.8, "r": 5.1, "b": 6.7},
                "locks": {"rotors": "LOCKED OPEN" if self.mode == "air" else "FOLDED",
                          "wheels": "6 LOCKED" if self.mode == "land" else "RETRACTED"}}


veh = Vehicle()


@web.middleware
async def cors(req, handler):
    if req.method == "OPTIONS":
        resp = web.Response()
    else:
        resp = await handler(req)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp


async def ws_handler(req):
    if TOKEN and req.query.get("token") != TOKEN:
        return web.Response(status=401, text="bad token")
    ws = web.WebSocketResponse(heartbeat=10)
    await ws.prepare(req)
    print("page connected", req.remote)
    veh.last_hb = time.time()

    async def sender():
        last = time.time()
        while not ws.closed:
            now = time.time(); v = veh.step(now - last); last = now
            await ws.send_json(veh.telemetry(v))
            await asyncio.sleep(0.2)

    task = asyncio.create_task(sender())
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                m = json.loads(msg.data)
            except ValueError:
                continue
            veh.last_hb = time.time()
            t = m.get("t")
            if t == "hb":
                await ws.send_json({"t": "pong", "ts": m.get("ts")})
            elif t == "ctl":
                veh.control(*(max(-1, min(1, float(m.get(k, 0)))) for k in ("roll", "pitch", "yaw", "thr")))
            elif t == "mode":
                veh.set_mode(m.get("mode"))
            elif t == "cmd":
                c = m.get("cmd")
                if c == "estop": veh.estop()
                elif c == "arm": veh.arm(True)
                elif c == "disarm": veh.arm(False)
                else: veh.command(c, m)
            elif t == "mission":
                print("MISSION", len(m.get("wps", [])), "waypoints")
    finally:
        task.cancel()
        veh.stop_all(); veh.arm(False)   # link gone: fail safe
        print("page disconnected")
    return ws


def frame_jpeg(cap, n):
    if cap is not None:
        ok, f = cap.read()
        if ok:
            return cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
    if Image is None:
        return b""
    im = Image.new("RGB", (960, 540), (12, 24, 48)); d = ImageDraw.Draw(im)
    d.text((30, 30), "RUDRA TrinityX  -  NO CAMERA (test pattern)", fill=(159, 195, 255))
    d.text((30, 60), time.strftime("%H:%M:%S") + f"  frame {n}", fill=(127, 232, 160))
    x = 80 + (n * 6) % 800; d.ellipse((x, 250, x + 60, 310), outline=(67, 210, 115), width=4)
    b = io.BytesIO(); im.save(b, "JPEG", quality=80); return b.getvalue()


async def video(req):
    if TOKEN and req.query.get("token") != TOKEN:
        return web.Response(status=401, text="bad token")
    resp = web.StreamResponse(headers={"Content-Type": "multipart/x-mixed-replace; boundary=frame", "Cache-Control": "no-store"})
    await resp.prepare(req)
    cap = cv2.VideoCapture(0) if cv2 else None
    loop, n = asyncio.get_event_loop(), 0
    try:
        while True:
            jpg = await loop.run_in_executor(None, frame_jpeg, cap, n); n += 1
            await resp.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpg) + jpg + b"\r\n")
            await asyncio.sleep(1 / 20)
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        if cap is not None: cap.release()
    return resp


async def watchdog(app):
    async def run():
        while True:
            await asyncio.sleep(0.25)
            if veh.armed and time.time() - veh.last_hb > WATCHDOG_S:
                print("heartbeat lost: failsafe"); veh.estop()
    app["wd"] = asyncio.create_task(run())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--host", default="0.0.0.0"); ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    app = web.Application(middlewares=[cors])
    app.add_routes([web.get("/ws", ws_handler), web.get("/video", video)])
    app.on_startup.append(watchdog)
    print(f"ws://{a.host}:{a.port}/ws   http://{a.host}:{a.port}/video   camera={'opencv' if cv2 else 'test pattern'}")
    web.run_app(app, host=a.host, port=a.port, print=None)
