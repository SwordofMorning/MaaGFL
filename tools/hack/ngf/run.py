import frida
import time
import json
import requests
import sys
import base64
import urllib.parse
import threading
import queue

# ================= 配置 =================
PROCESS_NAME = "GrilsFrontLine.exe"
UID = "4370354"
SIGN_KEY = "3f6129b617388aaff7a768496e923b5c"
HOST = "gfcn-game.gw.merge.sunborngame.com"
# ========================================

class GFLAutoPilot:
    def __init__(self):
        print(f"[*] Attaching to {PROCESS_NAME}...")
        try:
            self.session = frida.attach(PROCESS_NAME)
        except Exception as e:
            print(f"[!] Failed to attach: {e}")
            sys.exit(1)

        with open("agent.js", "r", encoding="utf-8") as f:
            script_code = f.read()

        self.script = self.session.create_script(script_code)
        self.script.on('message', self.on_message) # 注册回调
        self.script.load()
        
        # 消息队列，用于同步等待 JS 返回
        # key: reqId, value: queue
        self.response_queues = {}
        self.lock = threading.Lock()
        
        print("[*] Frida Script Loaded. Engine Ready.")
        
        self.http = requests.Session()
        self.http.headers.update({
            "User-Agent": "UnityPlayer/2018.4.36f1 (UnityWebRequest/1.0, libcurl/7.52.0-DEV)",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Unity-Version": "2018.4.36f1",
            "Host": HOST,
            "Connection": "keep-alive"
        })

    def on_message(self, message, data):
        if message['type'] == 'send':
            payload = message['payload']
            msg_type = payload.get('type')
            
            if msg_type == 'log':
                print(payload.get('msg'))
            elif msg_type == 'result' or msg_type == 'error':
                req_id = payload.get('reqId')
                if req_id in self.response_queues:
                    self.response_queues[req_id].put(payload)

    def call_game_func(self, op, data):
        """ 同步调用 JS 中的函数 """
        req_id = str(time.time())
        q = queue.Queue()
        
        with self.lock:
            self.response_queues[req_id] = q
        
        # 发送消息给 JS
        self.script.post({
            'op': op,
            'data': data,
            'key': SIGN_KEY,
            'reqId': req_id
        })
        
        try:
            # 等待 JS 返回，超时 5 秒
            result = q.get(timeout=5)
            with self.lock:
                del self.response_queues[req_id]
            
            if result['type'] == 'error':
                print(f"[!] JS Error: {result.get('msg')}")
                return None
            return result.get('data')
            
        except queue.Empty:
            print("[!] Timeout waiting for game function")
            return None

    def send_request(self, endpoint, payload_dict, param_name="outdatacode"):
        # 1. 准备 JSON
        json_str = json.dumps(payload_dict, separators=(',', ':'))
        
        # 2. 调用游戏加密
        encrypted_str = self.call_game_func('encrypt', json_str)
        if not encrypted_str:
            print("[!] Encryption failed")
            return None

        # 3. URL Encode
        encrypted_encoded = urllib.parse.quote(encrypted_str)
        
        # 4. 发送 HTTP
        req_id = int(time.time() * 100000)
        body_str = f"uid={UID}&{param_name}={encrypted_encoded}&req_id={req_id}"
        url = f"http://{HOST}/index.php/1000/{endpoint}"
        
        print(f"[*] Sending {endpoint}...")
        
        try:
            resp = self.http.post(url, data=body_str)
            if not resp.content:
                return None

            # 5. 调用游戏解密
            resp_b64 = base64.b64encode(resp.content).decode('utf-8')
            decrypted_json = self.call_game_func('decrypt', resp_b64)
            
            if decrypted_json:
                try:
                    return json.loads(decrypted_json)
                except:
                    return {"raw_text": decrypted_json}
            return None
                
        except Exception as e:
            print(f"[!] Network Error: {e}")
            return None

    def run_mission_loop(self):
        current_ally_id = int(time.time())

        # Step 0: Abort
        self.send_request("Mission/abortMission", {"mission_id": 11869}, param_name="signcode")
        time.sleep(0.5)

        # Step 1: Start Mission
        print("\n[Step 1] Starting Mission...")
        payload_start = {
            "mission_id": 11869,
            "spots": [],
            "squad_spots": [{"spot_id": 901897, "squad_with_user_id": 106361, "battleskill_switch": 1}],
            "sangvis_spots": [], "vehicle_spots": [], "ally_spots": [], "mission_ally_spots": [],
            "ally_id": current_ally_id
        }
        res = self.send_request("Mission/startMission", payload_start, param_name="outdatacode")
        
        if res and "squad_spots" in res:
            print("[+] Mission Started.")
        else:
            print(f"[-] Start Failed: {res}")
            return

        time.sleep(1)

        # Step 2: Guide
        guide_str = '{"course":[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,1,0,1,0,0,0,0,0,0,1,1,1,1,1,1,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,1,0,0,0,0,0,0,1,1,1,0,0,1,0,1,1,1,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1,1,1,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]}'
        self.send_request("Index/guide", {"guide": guide_str}, param_name="outdatacode")
        time.sleep(1)

        # Step 3: End Turn
        print("\n[Step 3] Ending Turn...")
        payload_turn = {"mission_id": 11869} 
        self.send_request("Mission/endTurn", payload_turn, param_name="signcode")
        time.sleep(1)

        # Step 4: Enemy Turn
        self.send_request("Mission/startEnemyTurn", payload_turn, param_name="signcode")
        time.sleep(0.2)
        self.send_request("Mission/endEnemyTurn", payload_turn, param_name="signcode")
        time.sleep(1)

        # Step 5: Start Turn 2
        print("\n[Step 5] Starting Turn 2...")
        self.send_request("Mission/startTurn", payload_turn, param_name="signcode")
        time.sleep(1)

        # Step 6: Settle
        print("\n[Step 6] Settlement...")
        res_final = self.send_request("Mission/startMission", payload_start, param_name="outdatacode")
        
        if res_final and "mission_win_result" in res_final:
            win = res_final["mission_win_result"]
            print("\n" + "="*40)
            print(f" $$ MISSION COMPLETE! Rank: {win.get('rank')} $$")
            if "reward_gun" in win and win["reward_gun"]:
                for g in win["reward_gun"]:
                    print(f" [DROP] Gun ID: {g.get('gun_id')} (UUID: {g.get('gun_with_user_id')})")
            else:
                print(" [DROP] No Gun this time.")
            print("="*40 + "\n")
        else:
            print(f"[-] Settlement result: {res_final}")

if __name__ == "__main__":
    pilot = GFLAutoPilot()
    try:
        print("[*] Starting Automation Loop...")
        while True:
            pilot.run_mission_loop()
            print("Wait 3s...")
            time.sleep(3)
    except KeyboardInterrupt:
        print("\nStopped.")