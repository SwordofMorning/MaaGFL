// agent.js

// 1. 设置地址
var OFFSET_DECODE = 21054368; // AC.AuthCode$$DecodeWithGzip
var OFFSET_ENCODE = 21054608; // AC.AuthCode$$Encode

var gameAssembly = Module.findBaseAddress("GameAssembly.dll");
var funcEncode = null;
var funcDecode = null;

if (gameAssembly) {
    var ptrEncode = gameAssembly.add(OFFSET_ENCODE);
    var ptrDecode = gameAssembly.add(OFFSET_DECODE);
    
    // 初始化函数指针
    funcEncode = new NativeFunction(ptrEncode, 'pointer', ['pointer', 'pointer']);
    funcDecode = new NativeFunction(ptrDecode, 'pointer', ['pointer', 'pointer']);
    send({type: 'log', msg: "[JS] NativeFunctions initialized."});
} else {
    send({type: 'log', msg: "[JS] [!] GameAssembly.dll not found!"});
}

// --- 内存辅助函数 ---
function allocCStr(str) {
    if (!str) str = "";
    var size = 0x14 + (str.length * 2) + 2; 
    var ptr = Memory.alloc(size);
    ptr.writeByteArray([0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0]);
    ptr.add(0x10).writeU32(str.length);
    ptr.add(0x14).writeUtf16String(str);
    return ptr;
}

function readCStr(ptr) {
    if (ptr.isNull()) return null;
    var len = ptr.add(0x10).readU32();
    return ptr.add(0x14).readUtf16String(len);
}

function allocCByteArr(data) {
    var len = data.length;
    var size = 0x20 + len;
    var ptr = Memory.alloc(size);
    ptr.writeByteArray([0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0]);
    ptr.add(0x18).writeU32(len);
    ptr.add(0x20).writeByteArray(data);
    return ptr;
}

function readCByteArr(ptr) {
    if (ptr.isNull()) return [];
    var len = ptr.add(0x18).readU32();
    return ptr.add(0x20).readByteArray(len);
}

// --- 核心：监听 Python 发来的消息 ---
recv(function(message) {
    handleMessage(message);
});

function handleMessage(message) {
    // 重新注册监听，保持长连接
    recv(function(msg) { handleMessage(msg); });

    var op = message.op;
    var reqId = message.reqId; // 用于匹配 Python 端的请求
    
    if (op === 'encrypt') {
        try {
            var jsonStr = message.data;
            var keyStr = message.key;
            
            var ptrJson = allocCStr(jsonStr);
            var ptrKey = allocCStr(keyStr);
            var resultPtr = funcEncode(ptrJson, ptrKey);
            var resultStr = readCStr(resultPtr);
            
            send({type: 'result', reqId: reqId, data: resultStr});
        } catch (e) {
            send({type: 'error', reqId: reqId, msg: "" + e});
        }
    } 
    else if (op === 'decrypt') {
        try {
            var b64Data = message.data;
            var keyStr = message.key;
            
            // Base64 -> Byte Array
            var data = Buffer.from(b64Data, 'base64');
            var byteArray = [];
            for(var i=0; i<data.length; i++) byteArray.push(data[i]);

            var ptrData = allocCByteArr(byteArray);
            var ptrKey = allocCStr(keyStr);
            var resultPtr = funcDecode(ptrData, ptrKey);
            
            var resultBytes = readCByteArr(resultPtr);
            var resultStr = "";
            if (resultBytes.byteLength > 0) {
                var decoder = new TextDecoder('utf-8');
                resultStr = decoder.decode(resultBytes);
            }
            
            send({type: 'result', reqId: reqId, data: resultStr});
        } catch (e) {
            send({type: 'error', reqId: reqId, msg: "" + e});
        }
    }
}