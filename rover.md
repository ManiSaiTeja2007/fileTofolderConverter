# Generated Folder Structure
*Generated from: `D:\ES_Project\AutonomousRoverSwarm\rover`*
*Timestamp: 2025-11-20T21:16:43.063992*

## File Structure
```text
rover/
├── rover_esp8266/
│   ├── rover_esp8266.ino
│   ├── sha256.c
│   └── sha256.h
└── rover_uno/
    └── rover_uno.ino
```

## rover_esp8266/rover_esp8266.ino
```text
/**
 * ESP8266 UART Master - Production Ready Rover Controller
 * UART-based with optimized performance and stability
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <WiFiUdp.h>
#include <FS.h>
#include <ArduinoJson.h>
#include <espnow.h>
#if OTA_ENABLED
  #include <ArduinoOTA.h>
#endif

// ==================== HARDWARE PINOUT ====================
#define UART_TX D1  // → Arduino RX (D0)
#define UART_RX D2  // → Arduino TX (D1) with voltage divider
#define STATUS_LED 2

// ==================== SYSTEM CONSTANTS ====================
#define BACKEND_PORT_DEFAULT 9999
#define CONFIG_FILE "/config.json"
#define HEARTBEAT_INTERVAL 5000
#define CYCLE_LENGTH 900000
#define MAX_SAVED_NETWORKS 5
#define AP_FALLBACK_MS 120000UL
#define PROTO_VERSION 2

// ==================== UART PROTOCOL ====================
#define UART_BAUD_RATE 57600
#define CMD_START_BYTE 0xAA
#define CMD_END_BYTE 0x55
#define UART_BUFFER_SIZE 64
#define UART_TIMEOUT_MS 100

// Command Types
enum CommandType {
  CMD_MOVEMENT = 0x01,
  CMD_NAVIGATION = 0x02,
  CMD_CALIBRATION = 0x03,
  CMD_TELEMETRY_REQUEST = 0x04,
  CMD_PID_PARAMS = 0x05,
  CMD_EMERGENCY_STOP = 0x06,
  CMD_SWEEP_CONTROL = 0x07,
  CMD_SYSTEM_RESET = 0x08
};

// Movement Commands
enum MovementCommand {
  MOVE_STOP = 0x00,
  MOVE_FORWARD = 0x01,
  MOVE_BACKWARD = 0x02,
  MOVE_LEFT = 0x03,
  MOVE_RIGHT = 0x04,
  MOVE_CALIBRATE = 0x05,
  MOVE_RETURN_HOME = 0x06
};

// Response Types
enum ResponseType {
  RESP_TELEMETRY = 0x81,
  RESP_ACK = 0x82,
  RESP_ERROR = 0x83
};

// ==================== TELEMETRY STRUCTURE ====================
#pragma pack(push, 1)
struct TelemetryData {
  uint8_t start_byte;
  uint8_t response_type;
  uint32_t timestamp;
  uint8_t system_status;
  uint16_t battery_mv;
  int16_t heading_centi;
  int16_t posX_cm;
  int16_t posY_cm;
  uint8_t motor_pwm_left;
  uint8_t motor_pwm_right;
  uint8_t left_trim;
  uint8_t right_trim;
  uint8_t navigation_state;
  int16_t velocity_mms;
  int16_t temperature_c;
  uint8_t obstacle_distance;
  uint8_t servo_angle;
  uint16_t checksum;
  uint8_t end_byte;
};
#pragma pack(pop)

// ==================== MESH NETWORKING ====================
#define ESPNOW_MAX_DATA_LEN 250
#define MESH_TTL_MAX 5
#define MESH_CACHE_SIZE 20
#define MESH_CHANNEL 1

enum MeshMessageType {
  MESH_TELEMETRY = 1,
  MESH_DISCOVERY,
  MESH_COMMAND,
  MESH_EMERGENCY
};

#define MESH_FLAG_BROADCAST   0x01

struct MeshMessage {
  uint32_t msg_id;
  uint8_t origin_mac[6];
  uint8_t dest_mac[6];
  uint32_t seq;
  uint8_t msg_type;
  uint8_t hop_count;
  uint8_t ttl;
  uint8_t flags;
  uint16_t payload_len;
  uint8_t payload[ESPNOW_MAX_DATA_LEN];
};

struct MeshCacheEntry {
  uint32_t msg_id;
  uint32_t timestamp;
  uint8_t origin_mac[6];
};

struct NeighborInfo {
  uint8_t mac[6];
  int rssi;
  uint8_t hop_count;
  uint32_t last_seen;
};

struct SavedNetwork {
  String ssid;
  String pass;
};

struct RoverConfig {
  char ssid[32];
  char pass[32];
  char backend_ip[16];
  uint16_t backend_port;
  char rover_name[16];
  char role[12];
  char web_password[32];
  bool enable_mesh;
  uint8_t mesh_channel;
  uint8_t telemetry_rate;
};

struct SystemMetrics {
  uint32_t start_time;
  uint32_t uart_success;
  uint32_t uart_errors;
  uint32_t mesh_tx_success;
  uint32_t mesh_tx_failed;
  uint32_t mesh_rx_packets;
  uint32_t telemetry_sent;
  uint32_t commands_executed;
  uint16_t free_heap_min;
  uint16_t free_heap_current;
};

// ==================== FORWARD DECLARATIONS ====================
class UARTManager;
class MeshManager;
class RoverController;
class ConfigManager;
class TelemetryManager;
class WebInterface;
class NetworkManager;
class SystemMonitor;

// ==================== GLOBAL VARIABLES ====================
ESP8266WebServer server(80);
WiFiUDP udp;

// Core system state
String deviceMac;
uint8_t deviceMacBytes[6];
RoverConfig config;
SystemMetrics metrics;
TelemetryData currentTelemetry;

// Network state
IPAddress backendIP;
bool backendConnected = false;
bool apModeActive = false;
uint32_t apStartTime = 0;

// Mesh networking
NeighborInfo neighbors[15];
uint8_t neighborCount = 0;
MeshCacheEntry meshCache[MESH_CACHE_SIZE];
uint8_t meshCacheCount = 0;
uint32_t meshSequence = 0;
uint32_t lastMeshBroadcast = 0;

// Timing control
uint32_t lastHeartbeat = 0;
uint32_t lastTelemetry = 0;
uint32_t lastMetricsUpdate = 0;
uint32_t lastLedToggle = 0;
uint32_t cycleStart = 0;

// System state
String roverRole = "scout";
bool isSwarmLeader = false;
uint8_t operationMode = 0;

SavedNetwork savedNetworks[MAX_SAVED_NETWORKS];
uint8_t savedNetworkCount = 0;

const uint8_t broadcastMac[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ==================== GLOBAL MANAGER INSTANCES ====================
UARTManager* uartManager = nullptr;
MeshManager* meshManager = nullptr;
RoverController* roverController = nullptr;
ConfigManager* configManager = nullptr;
TelemetryManager* telemetryManager = nullptr;
WebInterface* webInterface = nullptr;
NetworkManager* networkManager = nullptr;
SystemMonitor* systemMonitor = nullptr;

// ==================== UTILITY FUNCTIONS ====================
String macToString(const uint8_t *mac) {
  char buf[18];
  snprintf(buf, sizeof(buf), "%02X:%02X:%02X:%02X:%02X:%02X", 
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  return String(buf);
}

void forwardToBackend(const uint8_t* payload, uint16_t len) {
  if (backendConnected && udp.beginPacket(backendIP, config.backend_port)) {
    udp.write(payload, len);
    udp.endPacket();
  }
}

uint16_t calculateChecksum(uint8_t* data, size_t len) {
  uint16_t sum = 0;
  for (size_t i = 0; i < len; i++) {
    sum += data[i];
  }
  return sum;
}

// ==================== UART MANAGER ====================
class UARTManager {
private:
  uint8_t txPin;
  uint8_t rxPin;
  uint32_t successCount;
  uint32_t errorCount;
  
public:
  UARTManager(uint8_t tx, uint8_t rx) : txPin(tx), rxPin(rx), successCount(0), errorCount(0) {}
  
  void begin() {
    Serial.begin(UART_BAUD_RATE);
    Serial.setTimeout(UART_TIMEOUT_MS);
  }
  
  bool sendCommand(uint8_t commandType, uint8_t* data = nullptr, uint8_t dataLength = 0) {
    uint8_t packet[32];
    uint8_t packetLength = 4 + dataLength; // start + type + length + data + checksum + end
    
    if (packetLength > sizeof(packet) - 2) {
      return false;
    }
    
    packet[0] = CMD_START_BYTE;
    packet[1] = commandType;
    packet[2] = dataLength;
    
    if (dataLength > 0 && data != nullptr) {
      memcpy(&packet[3], data, dataLength);
    }
    
    packet[3 + dataLength] = calculateChecksum(packet + 1, 1 + dataLength) & 0xFF;
    packet[4 + dataLength] = CMD_END_BYTE;
    
    Serial.write(packet, 5 + dataLength);
    
    // Wait for acknowledgment
    unsigned long startTime = millis();
    while (millis() - startTime < UART_TIMEOUT_MS) {
      if (Serial.available() >= 5) {
        uint8_t response[5];
        Serial.readBytes(response, 5);
        
        if (response[0] == CMD_START_BYTE && 
            response[1] == RESP_ACK && 
            response[2] == commandType &&
            response[4] == CMD_END_BYTE) {
          
          uint8_t checksum = calculateChecksum(response + 1, 2) & 0xFF;
          if (response[3] == checksum) {
            successCount++;
            return true;
          }
        }
      }
      delay(1);
    }
    
    errorCount++;
    return false;
  }
  
  bool requestTelemetry(TelemetryData& telemetry) {
    if (!sendCommand(CMD_TELEMETRY_REQUEST)) {
      return false;
    }
    
    unsigned long startTime = millis();
    while (millis() - startTime < UART_TIMEOUT_MS) {
      if (Serial.available() >= sizeof(TelemetryData)) {
        uint8_t buffer[sizeof(TelemetryData)];
        Serial.readBytes(buffer, sizeof(TelemetryData));
        
        if (buffer[0] == CMD_START_BYTE && 
            buffer[1] == RESP_TELEMETRY && 
            buffer[sizeof(TelemetryData) - 1] == CMD_END_BYTE) {
          
          memcpy(&telemetry, buffer, sizeof(TelemetryData));
          
          // Verify checksum
          uint16_t calculated = calculateChecksum(buffer + 2, sizeof(TelemetryData) - 5);
          if (telemetry.checksum == calculated) {
            successCount++;
            return true;
          }
        }
      }
      delay(1);
    }
    
    errorCount++;
    return false;
  }
  
  bool sendMovementCommand(uint8_t movementCommand) {
    return sendCommand(CMD_MOVEMENT, &movementCommand, 1);
  }
  
  bool sendNavigationTarget(float x, float y) {
    uint8_t data[8];
    memcpy(data, &x, 4);
    memcpy(data + 4, &y, 4);
    return sendCommand(CMD_NAVIGATION, data, 8);
  }
  
  bool sendPIDParameters(float kp, float ki, float kd) {
    uint16_t kp_int = kp * 1000;
    uint16_t ki_int = ki * 1000;
    uint16_t kd_int = kd * 1000;
    
    uint8_t data[6];
    data[0] = (kp_int >> 8) & 0xFF;
    data[1] = kp_int & 0xFF;
    data[2] = (ki_int >> 8) & 0xFF;
    data[3] = ki_int & 0xFF;
    data[4] = (kd_int >> 8) & 0xFF;
    data[5] = kd_int & 0xFF;
    
    return sendCommand(CMD_PID_PARAMS, data, 6);
  }
  
  uint32_t getSuccessCount() { return successCount; }
  uint32_t getErrorCount() { return errorCount; }
};

// ==================== MESH MANAGER ====================
class MeshManager {
private:
  bool initialized;
  uint32_t lastDiscovery;
  uint32_t lastCleanup;
  
  bool isMessageCached(uint32_t msg_id) {
    for (int i = 0; i < meshCacheCount; i++) {
      if (meshCache[i].msg_id == msg_id) {
        return (millis() - meshCache[i].timestamp) < 2000;
      }
    }
    return false;
  }
  
  void cacheMessage(uint32_t msg_id, const uint8_t *origin_mac) {
    if (meshCacheCount >= MESH_CACHE_SIZE) {
      memmove(meshCache, meshCache + 1, sizeof(MeshCacheEntry) * (MESH_CACHE_SIZE - 1));
      meshCacheCount--;
    }
    
    meshCache[meshCacheCount].msg_id = msg_id;
    meshCache[meshCacheCount].timestamp = millis();
    memcpy(meshCache[meshCacheCount].origin_mac, origin_mac, 6);
    meshCacheCount++;
  }
  
  bool isMessageForMe(const uint8_t *dest_mac) {
    return memcmp(dest_mac, deviceMacBytes, 6) == 0 || 
           memcmp(dest_mac, broadcastMac, 6) == 0;
  }
  
  void updateNeighbor(const uint8_t *mac, int rssi, uint8_t hop_count) {
    for (int i = 0; i < neighborCount; i++) {
      if (memcmp(neighbors[i].mac, mac, 6) == 0) {
        neighbors[i].rssi = rssi;
        neighbors[i].last_seen = millis();
        neighbors[i].hop_count = (neighbors[i].hop_count < hop_count) ? neighbors[i].hop_count : hop_count;
        return;
      }
    }
    
    if (neighborCount < 15) {
      memcpy(neighbors[neighborCount].mac, mac, 6);
      neighbors[neighborCount].rssi = rssi;
      neighbors[neighborCount].last_seen = millis();
      neighbors[neighborCount].hop_count = hop_count;
      neighborCount++;
    }
  }
  
  void cleanupNeighbors() {
    uint32_t currentTime = millis();
    for (int i = 0; i < neighborCount; i++) {
      if (currentTime - neighbors[i].last_seen > 15000) {
        memmove(&neighbors[i], &neighbors[i + 1], sizeof(NeighborInfo) * (neighborCount - i - 1));
        neighborCount--;
        i--;
      }
    }
  }
  
  void handleMeshMessage(MeshMessage *msg) {
    metrics.mesh_rx_packets++;
    
    switch(msg->msg_type) {
      case MESH_TELEMETRY:
        if (isSwarmLeader && backendConnected) {
          forwardToBackend(msg->payload, msg->payload_len);
        }
        break;
        
      case MESH_DISCOVERY:
        break;
        
      case MESH_EMERGENCY:
        break;
    }
  }
  
  void relayMessage(MeshMessage *msg) {
    msg->hop_count++;
    msg->ttl--;
    
    uint8_t packet[sizeof(MeshMessage)];
    memcpy(packet, msg, sizeof(MeshMessage));
    
    int relays = 0;
    for (int i = 0; i < neighborCount && relays < 2; i++) {
      if (neighbors[i].rssi > -75) {
        if (esp_now_send(neighbors[i].mac, packet, sizeof(MeshMessage)) == 0) {
          relays++;
        }
      }
    }
  }
  
  uint32_t generateMessageId() {
    static uint32_t counter = 0;
    return counter++;
  }

public:
  static void processReceivedMessage(uint8_t *mac, uint8_t *data, uint8_t len) {
    if (meshManager && len >= sizeof(MeshMessage)) {
      meshManager->processMessage(mac, data, len);
    }
  }
  
  static void processSendStatus(uint8_t *mac, uint8_t status) {
    if (meshManager) {
      meshManager->handleSendStatus(mac, status);
    }
  }
  
  MeshManager() : initialized(false), lastDiscovery(0), lastCleanup(0) {}
  
  bool begin() {
    if (esp_now_init() != 0) {
      return false;
    }
    
    esp_now_set_self_role(ESP_NOW_ROLE_COMBO);
    esp_now_add_peer(const_cast<uint8_t*>(broadcastMac), ESP_NOW_ROLE_COMBO, MESH_CHANNEL, NULL, 0);
    
    esp_now_register_recv_cb(processReceivedMessage);
    esp_now_register_send_cb(processSendStatus);
    
    initialized = true;
    return true;
  }
  
  void processMessage(uint8_t *mac, uint8_t *data, uint8_t len) {
    MeshMessage* msg = (MeshMessage*)data;
    
    if (isMessageCached(msg->msg_id)) return;
    cacheMessage(msg->msg_id, msg->origin_mac);
    
    updateNeighbor(mac, WiFi.RSSI(), msg->hop_count);
    
    if (isMessageForMe(msg->dest_mac)) {
      handleMeshMessage(msg);
    }
    
    if (msg->ttl > 0 && (msg->flags & MESH_FLAG_BROADCAST)) {
      relayMessage(msg);
    }
  }
  
  void handleSendStatus(uint8_t *mac, uint8_t status) {
    if (status == 0) {
      metrics.mesh_tx_success++;
    } else {
      metrics.mesh_tx_failed++;
    }
  }
  
  bool sendMessage(const uint8_t *dest_mac, uint8_t msg_type, const uint8_t *payload, uint16_t payload_len, uint8_t flags = 0) {
    if (!initialized) return false;
    
    MeshMessage msg;
    msg.msg_id = generateMessageId();
    memcpy(msg.origin_mac, deviceMacBytes, 6);
    memcpy(msg.dest_mac, dest_mac, 6);
    msg.seq = meshSequence++;
    msg.msg_type = msg_type;
    msg.hop_count = 0;
    msg.ttl = MESH_TTL_MAX;
    msg.flags = flags;
    msg.payload_len = (payload_len < ESPNOW_MAX_DATA_LEN) ? payload_len : ESPNOW_MAX_DATA_LEN;
    
    if (payload_len > 0 && payload != nullptr) {
      memcpy(msg.payload, payload, msg.payload_len);
    }
    
    uint8_t packet[sizeof(MeshMessage)];
    memcpy(packet, &msg, sizeof(MeshMessage));
    
    int result = esp_now_send(const_cast<uint8_t*>(dest_mac), packet, sizeof(MeshMessage));
    return result == 0;
  }
  
  void broadcastDiscovery() {
    String discovery = "DISCOVERY:" + String(config.rover_name) + ":" + roverRole;
    sendMessage(broadcastMac, MESH_DISCOVERY, (uint8_t*)discovery.c_str(), discovery.length(), MESH_FLAG_BROADCAST);
    lastDiscovery = millis();
  }
  
  void update() {
    uint32_t currentTime = millis();
    
    if (currentTime - lastDiscovery > 10000) {
      broadcastDiscovery();
    }
    
    if (currentTime - lastCleanup > 30000) {
      cleanupNeighbors();
      lastCleanup = currentTime;
    }
  }
};

// ==================== ROVER CONTROLLER ====================
class RoverController {
public:
  void driveForward() { executeCommand(MOVE_FORWARD, "Forward"); }
  void driveBackward() { executeCommand(MOVE_BACKWARD, "Backward"); }
  void turnLeft() { executeCommand(MOVE_LEFT, "Left turn"); }
  void turnRight() { executeCommand(MOVE_RIGHT, "Right turn"); }
  void stop() { executeCommand(MOVE_STOP, "Stop"); }
  void calibrate() { executeCommand(MOVE_CALIBRATE, "Calibrate"); }
  void returnHome() { executeCommand(MOVE_RETURN_HOME, "Return home"); }
  void emergencyStop() { 
    if (uartManager->sendCommand(CMD_EMERGENCY_STOP)) {
      metrics.commands_executed++;
    }
  }
  
  bool setNavigationTarget(float x, float y) {
    return uartManager->sendNavigationTarget(x, y);
  }
  
  bool setPIDParameters(float kp, float ki, float kd) {
    return uartManager->sendPIDParameters(kp, ki, kd);
  }
  
private:
  void executeCommand(uint8_t command, const char* description) {
    if (uartManager->sendMovementCommand(command)) {
      metrics.commands_executed++;
    }
  }
};

// ==================== CONFIGURATION MANAGER ====================
class ConfigManager {
public:
  bool loadConfiguration() {
    if (!SPIFFS.begin()) {
      return false;
    }
    
    if (!SPIFFS.exists(CONFIG_FILE)) {
      setDefaultConfiguration();
      return saveConfiguration();
    }
    
    File file = SPIFFS.open(CONFIG_FILE, "r");
    if (!file) {
      return false;
    }
    
    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, file);
    file.close();
    
    if (error) {
      return false;
    }
    
    strlcpy(config.ssid, doc["ssid"] | "RoverNetwork", sizeof(config.ssid));
    strlcpy(config.pass, doc["pass"] | "rover123", sizeof(config.pass));
    strlcpy(config.backend_ip, doc["backend_ip"] | "192.168.1.100", sizeof(config.backend_ip));
    config.backend_port = doc["backend_port"] | BACKEND_PORT_DEFAULT;
    strlcpy(config.rover_name, doc["rover_name"] | "Rover01", sizeof(config.rover_name));
    strlcpy(config.role, doc["role"] | "scout", sizeof(config.role));
    strlcpy(config.web_password, doc["web_password"] | "admin123", sizeof(config.web_password));
    config.enable_mesh = doc["enable_mesh"] | true;
    config.mesh_channel = doc["mesh_channel"] | 1;
    config.telemetry_rate = doc["telemetry_rate"] | 2;
    
    return true;
  }
  
  bool saveConfiguration() {
    DynamicJsonDocument doc(1024);
    
    doc["ssid"] = config.ssid;
    doc["pass"] = config.pass;
    doc["backend_ip"] = config.backend_ip;
    doc["backend_port"] = config.backend_port;
    doc["rover_name"] = config.rover_name;
    doc["role"] = config.role;
    doc["web_password"] = config.web_password;
    doc["enable_mesh"] = config.enable_mesh;
    doc["mesh_channel"] = config.mesh_channel;
    doc["telemetry_rate"] = config.telemetry_rate;
    
    File file = SPIFFS.open(CONFIG_FILE, "w");
    if (!file) {
      return false;
    }
    
    serializeJson(doc, file);
    file.close();
    
    return true;
  }
  
  void setDefaultConfiguration() {
    memset(&config, 0, sizeof(config));
    strcpy(config.ssid, "RoverNetwork");
    strcpy(config.pass, "rover123");
    strcpy(config.backend_ip, "192.168.1.100");
    config.backend_port = BACKEND_PORT_DEFAULT;
    strcpy(config.rover_name, "Rover01");
    strcpy(config.role, "scout");
    strcpy(config.web_password, "admin123");
    config.enable_mesh = true;
    config.mesh_channel = 1;
    config.telemetry_rate = 2;
  }
};

// ==================== TELEMETRY MANAGER ====================
class TelemetryManager {
private:
  uint32_t lastTransmission;
  uint32_t sequenceNumber;
  
public:
  TelemetryManager() : lastTransmission(0), sequenceNumber(0) {}
  
  void update() {
    uint32_t currentTime = millis();
    uint32_t interval = 1000 / config.telemetry_rate;
    
    if (currentTime - lastTransmission >= interval) {
      if (collectAndSendTelemetry()) {
        lastTransmission = currentTime;
      }
    }
  }
  
  bool collectAndSendTelemetry() {
    TelemetryData telemetry;
    
    if (!uartManager->requestTelemetry(telemetry)) {
      return false;
    }
    
    currentTelemetry = telemetry;
    
    DynamicJsonDocument doc(512);
    doc["type"] = "telemetry";
    doc["rover_id"] = config.rover_name;
    doc["timestamp"] = telemetry.timestamp;
    doc["sequence"] = sequenceNumber++;
    doc["battery"] = telemetry.battery_mv / 1000.0;
    doc["position"] = String(telemetry.posX_cm / 100.0, 2) + "," + String(telemetry.posY_cm / 100.0, 2);
    doc["heading"] = telemetry.heading_centi / 100.0;
    doc["velocity"] = telemetry.velocity_mms / 1000.0;
    
    String payload;
    serializeJson(doc, payload);
    
    if (isSwarmLeader && backendConnected) {
      sendToBackend(payload);
    } else if (config.enable_mesh) {
      meshManager->sendMessage(broadcastMac, MESH_TELEMETRY, 
                              (uint8_t*)payload.c_str(), payload.length(), 
                              MESH_FLAG_BROADCAST);
    }
    
    metrics.telemetry_sent++;
    return true;
  }
  
private:
  void sendToBackend(const String &payload) {
    if (udp.beginPacket(backendIP, config.backend_port)) {
      udp.print(payload);
      udp.endPacket();
    }
  }
};

// ==================== WEB INTERFACE ====================
class WebInterface {
private:
  bool authenticate() {
    if (!server.authenticate("admin", config.web_password)) {
      server.requestAuthentication();
      return false;
    }
    return true;
  }
  
public:
  void begin() {
    server.on("/", HTTP_GET, [this]() { handleRoot(); });
    server.on("/api/telemetry", HTTP_GET, [this]() { handleApiTelemetry(); });
    server.on("/api/control", HTTP_POST, [this]() { handleApiControl(); });
    server.on("/api/status", HTTP_GET, [this]() { handleApiStatus(); });
    server.on("/api/mesh", HTTP_GET, [this]() { handleApiMesh(); });
    server.on("/api/config", HTTP_GET, [this]() { handleApiConfig(); });
    server.on("/api/config", HTTP_POST, [this]() { handleApiConfigSave(); });
    
    server.begin();
  }
  
  void handleRoot() {
    if (!authenticate()) return;
    
    String html = R"rawliteral(
<!DOCTYPE html><html><head>
<title>Rover Control</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial,sans-serif;margin:20px;background:#f5f5f5;}
.container{max-width:1200px;margin:0 auto;background:white;padding:20px;border-radius:10px;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0;}
.card{background:#f8f9fa;padding:15px;border-radius:8px;}
.btn{background:#007bff;color:white;border:none;padding:10px 15px;margin:5px;border-radius:5px;cursor:pointer;}
.btn:hover{background:#0056b3;}
.telemetry-value{font-weight:bold;color:#007bff;}
</style>
</head>
<body>
<div class="container">
<h1>🚀 Rover Control - )rawliteral" + String(config.rover_name) + R"rawliteral(</h1>
<div class="grid">
<div class="card"><h3>🎮 Control</h3>
<button class="btn" onclick="sendCommand('forward')">⬆️ Forward</button>
<button class="btn" onclick="sendCommand('backward')">⬇️ Backward</button>
<button class="btn" onclick="sendCommand('left')">⬅️ Left</button>
<button class="btn" onclick="sendCommand('right')">➡️ Right</button>
<button class="btn" onclick="sendCommand('stop')">🛑 Stop</button>
</div>
<div class="card"><h3>📊 Status</h3><div id="status">Loading...</div></div>
<div class="card"><h3>📡 Telemetry</h3><div id="telemetry">Loading...</div></div>
<div class="card"><h3>🕸️ Mesh</h3><div id="mesh">Loading...</div></div>
</div>
</div>
<script>
function sendCommand(cmd) {
fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({command:cmd})}).then(r=>r.json()).then(console.log);
}
function updateData() {
fetch('/api/telemetry').then(r=>r.json()).then(data=>{
document.getElementById('telemetry').innerHTML=`
Battery: <span class="telemetry-value">${data.battery}V</span><br>
Position: <span class="telemetry-value">${data.position}</span><br>
Heading: <span class="telemetry-value">${data.heading}°</span>`;
});
fetch('/api/status').then(r=>r.json()).then(data=>{
document.getElementById('status').innerHTML=`
Uptime: <span class="telemetry-value">${data.uptime}s</span><br>
Memory: <span class="telemetry-value">${data.free_heap} bytes</span>`;
});
fetch('/api/mesh').then(r=>r.json()).then(data=>{
document.getElementById('mesh').innerHTML=`
Neighbors: <span class="telemetry-value">${data.neighbor_count}</span><br>
Packets: <span class="telemetry-value">${data.rx_packets}</span>`;
});
}
setInterval(updateData,2000);
updateData();
</script>
</body></html>
)rawliteral";
    
    server.send(200, "text/html", html);
  }
  
  void handleApiTelemetry() {
    if (!authenticate()) return;
    
    DynamicJsonDocument doc(512);
    doc["battery"] = currentTelemetry.battery_mv / 1000.0;
    doc["position"] = String(currentTelemetry.posX_cm / 100.0, 2) + "," + String(currentTelemetry.posY_cm / 100.0, 2);
    doc["heading"] = currentTelemetry.heading_centi / 100.0;
    doc["velocity"] = currentTelemetry.velocity_mms / 1000.0;
    
    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
  }
  
  void handleApiControl() {
    if (!authenticate()) return;
    
    String body = server.arg("plain");
    DynamicJsonDocument doc(256);
    deserializeJson(doc, body);
    
    String command = doc["command"];
    bool success = false;
    
    if (command == "forward") { roverController->driveForward(); success = true; }
    else if (command == "backward") { roverController->driveBackward(); success = true; }
    else if (command == "left") { roverController->turnLeft(); success = true; }
    else if (command == "right") { roverController->turnRight(); success = true; }
    else if (command == "stop") { roverController->stop(); success = true; }
    else if (command == "calibrate") { roverController->calibrate(); success = true; }
    else if (command == "home") { roverController->returnHome(); success = true; }
    else if (command == "emergency") { roverController->emergencyStop(); success = true; }
    
    DynamicJsonDocument response(128);
    response["success"] = success;
    response["message"] = "Command " + String(success ? "executed" : "failed");
    
    String jsonResponse;
    serializeJson(response, jsonResponse);
    server.send(200, "application/json", jsonResponse);
  }
  
  void handleApiStatus() {
    if (!authenticate()) return;
    
    DynamicJsonDocument doc(512);
    doc["rover_name"] = config.rover_name;
    doc["uptime"] = millis() / 1000;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["uart_success"] = metrics.uart_success;
    doc["uart_errors"] = metrics.uart_errors;
    
    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
  }
  
  void handleApiMesh() {
    if (!authenticate()) return;
    
    DynamicJsonDocument doc(512);
    doc["neighbor_count"] = neighborCount;
    doc["rx_packets"] = metrics.mesh_rx_packets;
    doc["tx_success"] = metrics.mesh_tx_success;
    
    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
  }
  
  void handleApiConfig() {
    if (!authenticate()) return;
    
    DynamicJsonDocument doc(1024);
    doc["ssid"] = config.ssid;
    doc["backend_ip"] = config.backend_ip;
    doc["rover_name"] = config.rover_name;
    doc["role"] = config.role;
    
    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
  }
  
  void handleApiConfigSave() {
    if (!authenticate()) return;
    
    String body = server.arg("plain");
    DynamicJsonDocument doc(1024);
    deserializeJson(doc, body);
    
    if (doc.containsKey("ssid")) strlcpy(config.ssid, doc["ssid"], sizeof(config.ssid));
    if (doc.containsKey("backend_ip")) strlcpy(config.backend_ip, doc["backend_ip"], sizeof(config.backend_ip));
    if (doc.containsKey("rover_name")) strlcpy(config.rover_name, doc["rover_name"], sizeof(config.rover_name));
    
    configManager->saveConfiguration();
    
    server.send(200, "application/json", "{\"message\":\"Configuration saved\"}");
  }
};

// ==================== NETWORK MANAGER ====================
class NetworkManager {
public:
  bool connectToWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(config.ssid, config.pass);
    
    for (int i = 0; i < 20; i++) {
      if (WiFi.status() == WL_CONNECTED) {
        backendIP.fromString(config.backend_ip);
        backendConnected = true;
        return true;
      }
      delay(500);
    }
    
    return false;
  }
  
  void startAPMode() {
    WiFi.mode(WIFI_AP);
    WiFi.softAP("Rover-Config", "config123");
    apModeActive = true;
    apStartTime = millis();
  }
  
  void setupOTA() {
    #if OTA_ENABLED
    ArduinoOTA.setHostname(config.rover_name);
    ArduinoOTA.setPassword(config.web_password);
    ArduinoOTA.begin();
    #endif
  }
};

// ==================== SYSTEM MONITOR ====================
class SystemMonitor {
private:
  uint32_t lastUpdate;
  uint16_t minHeap;
  
public:
  SystemMonitor() : lastUpdate(0), minHeap(UINT16_MAX) {}
  
  void update() {
    uint32_t currentTime = millis();
    
    if (currentTime - lastUpdate >= 1000) {
      uint16_t freeHeap = ESP.getFreeHeap();
      metrics.free_heap_current = freeHeap;
      if (freeHeap < minHeap) minHeap = freeHeap;
      metrics.free_heap_min = minHeap;
      
      metrics.uart_success = uartManager->getSuccessCount();
      metrics.uart_errors = uartManager->getErrorCount();
      
      if (currentTime - lastLedToggle >= 1000) {
        digitalWrite(STATUS_LED, !digitalRead(STATUS_LED));
        lastLedToggle = currentTime;
      }
      
      lastUpdate = currentTime;
    }
    
    #if OTA_ENABLED
    ArduinoOTA.handle();
    #endif
  }
  
  void checkSystemHealth() {
    if (ESP.getFreeHeap() < 10000) {
      // Low memory condition
    }
    
    if (!apModeActive && WiFi.status() != WL_CONNECTED) {
      backendConnected = false;
    }
  }
};

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, LOW);
  
  deviceMac = WiFi.macAddress();
  sscanf(deviceMac.c_str(), "%2hhx:%2hhx:%2hhx:%2hhx:%2hhx:%2hhx",
         &deviceMacBytes[0], &deviceMacBytes[1], &deviceMacBytes[2],
         &deviceMacBytes[3], &deviceMacBytes[4], &deviceMacBytes[5]);
  
  // Create manager instances
  uartManager = new UARTManager(UART_TX, UART_RX);
  configManager = new ConfigManager();
  roverController = new RoverController();
  networkManager = new NetworkManager();
  telemetryManager = new TelemetryManager();
  webInterface = new WebInterface();
  systemMonitor = new SystemMonitor();
  
  configManager->loadConfiguration();
  uartManager->begin();

  if (!networkManager->connectToWiFi()) {
    networkManager->startAPMode();
  }
  
  if (config.enable_mesh) {
    meshManager = new MeshManager();
    meshManager->begin();
  }
  
  webInterface->begin();
  networkManager->setupOTA();
  
  metrics.start_time = millis();
  cycleStart = millis();
}

// ==================== MAIN LOOP ====================
void loop() {
  server.handleClient();
  systemMonitor->update();
  systemMonitor->checkSystemHealth();
  
  if (!apModeActive) {
    telemetryManager->update();
    
    if (config.enable_mesh && meshManager) {
      meshManager->update();
    }
    
    if (millis() - lastHeartbeat >= HEARTBEAT_INTERVAL) {
      lastHeartbeat = millis();
    }
    
    processBackendMessages();
    
  } else {
    if (millis() - apStartTime > AP_FALLBACK_MS) {
      if (networkManager->connectToWiFi()) {
        apModeActive = false;
      }
    }
  }
  
  delay(1);
}

void processBackendMessages() {
  int packetSize = udp.parsePacket();
  if (packetSize) {
    char packet[1024];
    int len = udp.read(packet, sizeof(packet) - 1);
    if (len > 0) {
      packet[len] = 0;
    }
  }
}
```

## rover_esp8266/sha256.c
```c
#include "sha256.h"
#include <string.h>

#define SHA256_SHFR(x, n)    (x >> n)
#define SHA256_ROTR(x, n)   ((x >> n) | (x << ((sizeof(x) << 3) - n)))
#define SHA256_ROTL(x, n)   ((x << n) | (x >> ((sizeof(x) << 3) - n)))
#define SHA256_CH(x, y, z)  ((x & y) ^ (~x & z))
#define SHA256_MAJ(x, y, z) ((x & y) ^ (x & z) ^ (y & z))
#define SHA256_F1(x)        (SHA256_ROTR(x, 2) ^ SHA256_ROTR(x, 13) ^ SHA256_ROTR(x, 22))
#define SHA256_F2(x)        (SHA256_ROTR(x, 6) ^ SHA256_ROTR(x, 11) ^ SHA256_ROTR(x, 25))
#define SHA256_F3(x)        (SHA256_ROTR(x, 7) ^ SHA256_ROTR(x, 18) ^ SHA256_SHFR(x, 3))
#define SHA256_F4(x)        (SHA256_ROTR(x, 17) ^ SHA256_ROTR(x, 19) ^ SHA256_SHFR(x, 10))
#define SHA256_UNPACK32(x, str)                      \
{                                                    \
    *((str) + 3) = (uint8_t) ((x)      );            \
    *((str) + 2) = (uint8_t) ((x) >>  8);            \
    *((str) + 1) = (uint8_t) ((x) >> 16);            \
    *((str) + 0) = (uint8_t) ((x) >> 24);            \
}
#define SHA256_PACK32(str, x)                        \
{                                                    \
    *(x) =   ((uint32_t) *((str) + 3)      )         \
           | ((uint32_t) *((str) + 2) <<  8)         \
           | ((uint32_t) *((str) + 1) << 16)         \
           | ((uint32_t) *((str) + 0) << 24);        \
}

static const uint32_t sha256_k[64] =
{ /* 64 constant values */
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

static const uint32_t sha256_h0[8] =
{
  0x6a09e667,
  0xbb67ae85,
  0x3c6ef372,
  0xa54ff53a,
  0x510e527f,
  0x9b05688c,
  0x1f83d9ab,
  0x5be0cd19
};

static void sha256_transf(sha256_ctx *ctx, const uint8_t *message, size_t block_nb)
{
  uint32_t w[64];
  uint32_t wv[8];
  uint32_t t1, t2;
  const uint8_t *sub_block;
  int i;

  for (i = 0; i < (int) block_nb; i++) {
    sub_block = message + (i << 6);

    for (int j = 0; j < 16; j++)
      SHA256_PACK32(&sub_block[j << 2], &w[j]);

    for (int j = 16; j < 64; j++)
      w[j] = SHA256_F4(w[j - 2]) + w[j - 7] + SHA256_F3(w[j - 15]) + w[j - 16];

    for (int j = 0; j < 8; j++)
      wv[j] = ctx->h[j];

    for (int j = 0; j < 64; j++) {
      t1 = wv[7] + SHA256_F2(wv[4]) + SHA256_CH(wv[4], wv[5], wv[6])
           + sha256_k[j] + w[j];
      t2 = SHA256_F1(wv[0]) + SHA256_MAJ(wv[0], wv[1], wv[2]);
      wv[7] = wv[6];
      wv[6] = wv[5];
      wv[5] = wv[4];
      wv[4] = wv[3] + t1;
      wv[3] = wv[2];
      wv[2] = wv[1];
      wv[1] = wv[0];
      wv[0] = t1 + t2;
    }

    for (int j = 0; j < 8; j++)
      ctx->h[j] += wv[j];
  }
}

void sha256_init(sha256_ctx *ctx)
{
  for (int i = 0; i < 8; i++)
    ctx->h[i] = sha256_h0[i];
  ctx->len = 0;
  ctx->tot_len = 0;
}

void sha256_update(sha256_ctx *ctx, const uint8_t *message, size_t len)
{
  size_t block_nb;
  size_t new_len, rem_len, tmp_len;
  const uint8_t *shifted_message;

  tmp_len = 64 - ctx->len;
  rem_len = len < tmp_len ? len : tmp_len;

  memcpy(&ctx->block[ctx->len], message, rem_len);

  if (ctx->len + len < 64) {
    ctx->len += len;
    return;
  }

  new_len = len - rem_len;
  block_nb = 1 + (new_len >> 6);

  shifted_message = message + rem_len;

  sha256_transf(ctx, ctx->block, 1);
  sha256_transf(ctx, shifted_message, block_nb);

  rem_len = new_len % 64;
  memcpy(ctx->block, &shifted_message[block_nb << 6], rem_len);

  ctx->len = rem_len;
  ctx->tot_len += (block_nb + 1) << 6;
}

void sha256_final(sha256_ctx *ctx, uint8_t *digest)
{
  size_t block_nb;
  size_t pm_len;
  uint32_t len_b;

  block_nb = 1 + ((64 - 9) < (ctx->len % 64));
  len_b = (ctx->tot_len + ctx->len) << 3;
  pm_len = block_nb << 6;

  memset(ctx->block + ctx->len, 0, pm_len - ctx->len);
  ctx->block[ctx->len] = 0x80;
  SHA256_UNPACK32(len_b, ctx->block + pm_len - 4);

  sha256_transf(ctx, ctx->block, block_nb);

  for (int i = 0; i < 8; i++)
    SHA256_UNPACK32(ctx->h[i], digest + (i << 2));
}

void sha256(const uint8_t *message, size_t len, uint8_t *digest)
{
  sha256_ctx ctx;

  sha256_init(&ctx);
  sha256_update(&ctx, message, len);
  sha256_final(&ctx, digest);
}
```

## rover_esp8266/sha256.h
```c
#ifndef SHA256_H
#define SHA256_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint64_t tot_len;
    uint32_t len;
    uint8_t block[64];
    uint32_t h[8];
} sha256_ctx;

void sha256_init(sha256_ctx *ctx);
void sha256_update(sha256_ctx *ctx, const uint8_t *message, size_t len);
void sha256_final(sha256_ctx *ctx, uint8_t *digest);

void sha256(const uint8_t *message, size_t len, uint8_t *digest);

#ifdef __cplusplus
}
#endif

#endif
```

## rover_uno/rover_uno.ino
```text
/**
 * UNO UART Controller - Enhanced Rover Control with Correct Pin Mapping
 * UART Communication with NodeMCU - Optimized for Stability & Performance
 */
#define ENABLE_UART_DEBUG   true   // Set to false to disable all debug prints

#include <Wire.h>
#include <Servo.h>
#include "I2Cdev.h"
#include "MPU6050.h"
#include <NewPing.h>
#include <EEPROM.h>

// ----------------------- CORRECTED HARDWARE PINS -----------------------
// Motor Control (L298N)
#define IN1 4
#define IN2 5
#define IN3 6
#define IN4 7
#define ENA 10  // Left motor PWM
#define ENB 11  // Right motor PWM

// Sensors
#define SERVO_PIN 9      // Ultrasonic sweep servo
#define TRIG_PIN 8       // Ultrasonic trigger
#define ECHO_PIN 3       // Ultrasonic echo

// UART to NodeMCU
// RX → D0 (from NodeMCU D2/GPIO4)
// TX → D1 (to NodeMCU D1/GPIO5 with voltage divider)

// I2C for MPU6050
// SDA → A4
// SCL → A5

// ----------------------- UART PROTOCOL CONSTANTS -----------------------
#define UART_BAUD_RATE 57600
#define CMD_START_BYTE 0xAA
#define CMD_END_BYTE 0x55
#define UART_BUFFER_SIZE 32
#define TELEMETRY_INTERVAL 100  // ms

// Command Types
enum CommandType {
  CMD_MOVEMENT = 0x01,
  CMD_NAVIGATION = 0x02,
  CMD_CALIBRATION = 0x03,
  CMD_TELEMETRY_REQUEST = 0x04,
  CMD_PID_PARAMS = 0x05,
  CMD_EMERGENCY_STOP = 0x06,
  CMD_SWEEP_CONTROL = 0x07,
  CMD_SYSTEM_RESET = 0x08
};

// Movement Commands
enum MovementCommand {
  MOVE_STOP = 0x00,
  MOVE_FORWARD = 0x01,
  MOVE_BACKWARD = 0x02,
  MOVE_LEFT = 0x03,
  MOVE_RIGHT = 0x04,
  MOVE_CALIBRATE = 0x05,
  MOVE_RETURN_HOME = 0x06
};

// Response Types
enum ResponseType {
  RESP_TELEMETRY = 0x81,
  RESP_ACK = 0x82,
  RESP_ERROR = 0x83,
  RESP_SYSTEM_STATUS = 0x84
};

// ----------------------- TELEMETRY STRUCTURE -----------------------
#pragma pack(push, 1)
struct TelemetryData {
  uint8_t start_byte = CMD_START_BYTE;
  uint8_t response_type = RESP_TELEMETRY;
  uint32_t timestamp;
  uint8_t system_status;
  uint16_t battery_mv;
  int16_t heading_centi;
  int16_t posX_cm;
  int16_t posY_cm;
  uint8_t motor_pwm_left;
  uint8_t motor_pwm_right;
  uint8_t left_trim;
  uint8_t right_trim;
  uint8_t navigation_state;
  int16_t velocity_mms;
  int16_t temperature_c;
  uint8_t obstacle_distance;
  uint8_t servo_angle;
  uint16_t checksum;
  uint8_t end_byte = CMD_END_BYTE;
};
#pragma pack(pop)

// ----------------------- SYSTEM CONSTANTS -----------------------
#define SWEEP_MIN           8
#define SWEEP_MAX           32
#define MAX_DISTANCE_CM     400
#define BATTERY_FULL_MV     4200
#define BATTERY_EMPTY_MV    3200

// EEPROM layout
#define EE_SIG_ADDR         0
#define EE_SIG_VALUE        0xA5
#define EE_LEFT_TRIM        1
#define EE_RIGHT_TRIM       2
#define EE_PID_KP           3
#define EE_PID_KI           7
#define EE_PID_KD           11
#define EE_FLAG_CAL         15
#define EE_HOME_X           16
#define EE_HOME_Y           20

// Timing constants
const unsigned long CONTROL_LOOP_MS = 10;
const unsigned long TELEMETRY_INTERVAL_MS = 100;
const unsigned long SAFETY_CHECK_MS = 50;
const unsigned long SWEEP_INTERVAL_MS = 25;

// Calibration constants
const int CALIBRATION_ITERATIONS = 3;
const unsigned long CALIBRATION_DRIVE_MS = 800;

// ----------------------- DEVICE INSTANCES -----------------------
NewPing sonar(TRIG_PIN, ECHO_PIN, MAX_DISTANCE_CM);
Servo sweepServo;
MPU6050 mpu;

// ----------------------- UART COMMUNICATION -----------------------
uint8_t uartBuffer[UART_BUFFER_SIZE];
uint8_t uartBufferIndex = 0;
bool commandInProgress = false;
unsigned long lastUartActivity = 0;

// ----------------------- SYSTEM STATE VARIABLES -----------------------
// Navigation & Positioning
float currentX = 0.0, currentY = 0.0;
float currentHeading = 0.0;
float targetX = 0.0, targetY = 0.0;
float homeX = 0.0, homeY = 0.0;
float currentVelocity = 0.0;
float desiredVelocity = 0.0;

// Motor Control
int motorTargetPWM = 0;
int motorCurrentPWM = 0;
int motorLeftPWM = 0;
int motorRightPWM = 0;
bool motorDirectionForward = true;
uint8_t leftTrimValue = 128;
uint8_t rightTrimValue = 128;

// Sensor & Servo
int sweepSamples = 16;
int currentServoAngle = 90;
int servoDirection = 1;
const int SERVO_MIN_ANGLE = 45;
const int SERVO_MAX_ANGLE = 135;
uint16_t sweepDistances[16];

// IMU & Calibration
float gyroBiasX = 0.0, gyroBiasY = 0.0, gyroBiasZ = 0.0;
float accelBiasX = 0.0, accelBiasY = 0.0, accelBiasZ = 0.0;
bool imuCalibrated = false;
unsigned long lastOdometryUpdate = 0;

// System State
bool isMoving = false;
bool hasActiveDestination = false;
bool returningToHome = false;
bool obstacleDetected = false;
uint8_t systemNavigationState = 0;

// Calibration State
enum CalibrationState { CAL_IDLE, CAL_RUNNING, CAL_COMPLETE };
CalibrationState calibrationState = CAL_IDLE;
int calibrationStep = 0;
unsigned long calibrationStartTime = 0;
float calibrationStartHeading = 0.0;

// Timing Control
unsigned long lastControlUpdate = 0;
unsigned long lastTelemetrySend = 0;
unsigned long lastSafetyCheck = 0;
unsigned long lastServoSweep = 0;
unsigned long lastCommandReceived = 0;

// ----------------------- ENHANCED PID CONTROLLERS -----------------------
class StablePIDController {
private:
  float kp, ki, kd;
  float integral;
  float previousError;
  float previousDerivative;
  unsigned long previousTime;
  float integralWindupLimit;
  float outputLimit;
  float setpointValue;
  bool controllerActive;
  float derivativeFilterAlpha;
  
public:
  StablePIDController() : 
    kp(2.5), ki(0.02), kd(0.8), 
    integral(0), previousError(0), previousDerivative(0),
    previousTime(0), integralWindupLimit(150), outputLimit(80),
    setpointValue(0), controllerActive(false), derivativeFilterAlpha(0.3) {}
  
  float compute(float currentValue, unsigned long currentTime) {
    if (!controllerActive) return 0.0;
    
    float deltaTime = (currentTime - previousTime) / 1000.0;
    if (deltaTime <= 0 || deltaTime > 0.2) {
      previousTime = currentTime;
      return 0.0;
    }
    
    float error = setpointValue - currentValue;
    
    // Handle angular wrapping for heading control
    if (fabs(error) > 180.0) {
      error = error > 0 ? error - 360.0 : error + 360.0;
    }
    
    // Proportional term
    float proportional = kp * error;
    
    // Integral term with anti-windup
    integral += error * deltaTime;
    if (integral > integralWindupLimit) integral = integralWindupLimit;
    if (integral < -integralWindupLimit) integral = -integralWindupLimit;
    float integralTerm = ki * integral;
    
    // Filtered derivative term
    float rawDerivative = (error - previousError) / deltaTime;
    float derivative = previousDerivative + derivativeFilterAlpha * (rawDerivative - previousDerivative);
    float derivativeTerm = kd * derivative;
    
    // Compute final output
    float output = proportional + integralTerm + derivativeTerm;
    
    // Apply output constraints
    if (output > outputLimit) output = outputLimit;
    if (output < -outputLimit) output = -outputLimit;
    
    // Update state variables
    previousError = error;
    previousDerivative = derivative;
    previousTime = currentTime;
    
    return output;
  }
  
  void reset() {
    integral = 0;
    previousError = 0;
    previousDerivative = 0;
    previousTime = millis();
  }
  
  void activate(float target) {
    setpointValue = target;
    controllerActive = true;
    reset();
  }
  
  void deactivate() {
    controllerActive = false;
    reset();
  }
  
  void configureParameters(float proportional, float integralGain, float derivative, 
                          float windupLimit, float outputMax) {
    kp = proportional;
    ki = integralGain;
    kd = derivative;
    integralWindupLimit = windupLimit;
    outputLimit = outputMax;
    reset();
  }
  
  bool isActive() { return controllerActive; }
  float getSetpoint() { return setpointValue; }
};

StablePIDController headingController;
StablePIDController velocityController;

// ----------------------- UTILITY FUNCTIONS -----------------------
void writeFloatToEEPROM(int address, float value) {
  byte *data = (byte*)(void*)&value;
  for (int i = 0; i < 4; i++) {
    EEPROM.update(address + i, data[i]);
  }
}

float readFloatFromEEPROM(int address) {
  float value;
  byte *data = (byte*)(void*)&value;
  for (int i = 0; i < 4; i++) {
    data[i] = EEPROM.read(address + i);
  }
  return value;
}

float applyExponentialFilter(float previous, float current, float alpha) {
  return previous * (1.0 - alpha) + current * alpha;
}

float normalizeAngle(float angle) {
  while (angle >= 360.0) angle -= 360.0;
  while (angle < 0.0) angle += 360.0;
  return angle;
}

float calculateAngleDifference(float from, float to) {
  float difference = to - from;
  if (difference > 180.0) difference -= 360.0;
  if (difference < -180.0) difference += 360.0;
  return difference;
}

uint16_t computeChecksum(uint8_t* data, size_t length) {
  uint16_t sum = 0;
  for (size_t i = 0; i < length; i++) {
    sum += data[i];
  }
  return sum;
}

// ----------------------- UART COMMUNICATION FUNCTIONS -----------------------
void sendTelemetryData() {
  TelemetryData telemetry;
  
  // Populate telemetry structure
  telemetry.timestamp = millis();
  telemetry.system_status = (imuCalibrated ? 0x01 : 0x00) | 
                           (isMoving ? 0x02 : 0x00) |
                           (obstacleDetected ? 0x04 : 0x00) |
                           (hasActiveDestination ? 0x08 : 0x00);
  
  // Simulated battery voltage (would be from ADC in real implementation)
  telemetry.battery_mv = map(analogRead(A0), 0, 1023, BATTERY_EMPTY_MV, BATTERY_FULL_MV);
  
  telemetry.heading_centi = (int16_t)(currentHeading * 100.0);
  telemetry.posX_cm = (int16_t)(currentX * 100.0);
  telemetry.posY_cm = (int16_t)(currentY * 100.0);
  
  telemetry.motor_pwm_left = motorLeftPWM;
  telemetry.motor_pwm_right = motorRightPWM;
  telemetry.left_trim = leftTrimValue;
  telemetry.right_trim = rightTrimValue;
  telemetry.navigation_state = systemNavigationState;
  telemetry.velocity_mms = (int16_t)(currentVelocity * 1000.0);
  telemetry.temperature_c = (int16_t)25; // Placeholder
  telemetry.obstacle_distance = readFilteredSonar();
  telemetry.servo_angle = currentServoAngle;
  
  // Calculate checksum (excluding start/end bytes and checksum field)
  telemetry.checksum = computeChecksum((uint8_t*)&telemetry + 2, sizeof(TelemetryData) - 5);
  
  // Transmit telemetry
  Serial.write((uint8_t*)&telemetry, sizeof(TelemetryData));
}

void sendAcknowledgment(uint8_t commandType) {
  uint8_t ackPacket[5] = {
    CMD_START_BYTE,
    RESP_ACK,
    commandType,
    0x00, // Checksum placeholder
    CMD_END_BYTE
  };
  ackPacket[3] = computeChecksum(ackPacket + 1, 2) & 0xFF;
  Serial.write(ackPacket, sizeof(ackPacket));
}

void sendErrorResponse(uint8_t errorCode) {
  uint8_t errorPacket[5] = {
    CMD_START_BYTE,
    RESP_ERROR,
    errorCode,
    0x00, // Checksum placeholder
    CMD_END_BYTE
  };
  errorPacket[3] = computeChecksum(errorPacket + 1, 2) & 0xFF;
  Serial.write(errorPacket, sizeof(errorPacket));
}
// ====================== UART DEBUG OUTPUT ======================

void debugHex(const uint8_t* data, uint8_t len, const char* prefix = "") {
#if ENABLE_UART_DEBUG
  Serial.print(prefix);
  for (uint8_t i = 0; i < len; i++) {
    if (data[i] < 0x10) Serial.print("0");
    Serial.print(data[i], HEX);
    Serial.print(" ");
  }
  Serial.println();
#endif
}

void debugPrint(const char* msg) {
#if ENABLE_UART_DEBUG
  Serial.println(msg);
#endif
}

void processIncomingCommand() {
  if (uartBufferIndex < 4) return; // Minimum valid packet size
  
  uint8_t startByte = uartBuffer[0];
  uint8_t commandType = uartBuffer[1];
  uint8_t dataLength = uartBuffer[2];
  
  if (startByte != CMD_START_BYTE) {
    uartBufferIndex = 0;
    return;
  }
  
  // Check if we have complete packet
  uint8_t expectedLength = 4 + dataLength; // start + type + length + data + checksum + end
  if (uartBufferIndex < expectedLength) {
    return;
  }
  
  // Verify end byte
  if (uartBuffer[3 + dataLength] != CMD_END_BYTE) {
    uartBufferIndex = 0;
    sendErrorResponse(0x01); // Invalid packet structure
    return;
  }
  
  // Verify checksum
  uint8_t receivedChecksum = uartBuffer[3 + dataLength - 1];
  uint8_t calculatedChecksum = computeChecksum(uartBuffer + 1, 1 + dataLength) & 0xFF;
  
  if (receivedChecksum != calculatedChecksum) {
    uartBufferIndex = 0;
    sendErrorResponse(0x02); // Checksum mismatch
    return;
  }
  #if ENABLE_UART_DEBUG
    Serial.print(F("VALID COMMAND: 0x"));
    Serial.println(commandType, HEX);
    if (dataLength > 0) {
      Serial.print(F("Payload ("));
      Serial.print(dataLength);
      Serial.print(F(" bytes): "));
      debugHex(uartBuffer + 3, dataLength, "");
    }
  #endif
  // Process valid command
  lastCommandReceived = millis();
  
  switch (commandType) {
    case CMD_MOVEMENT:
      executeMovementCommand(uartBuffer[3]);
      break;
      
    case CMD_NAVIGATION:
      if (dataLength >= 8) {
        float targetX, targetY;
        memcpy(&targetX, &uartBuffer[3], 4);
        memcpy(&targetY, &uartBuffer[7], 4);
        setNavigationTarget(targetX, targetY);
      }
      break;
      
    case CMD_CALIBRATION:
      if (calibrationState == CAL_IDLE) {
        calibrationState = CAL_RUNNING;
        calibrationStep = 0;
        calibrationStartTime = 0;
      }
      break;
      
    case CMD_TELEMETRY_REQUEST:
      sendTelemetryData();
      break;
      
    case CMD_PID_PARAMS:
      if (dataLength >= 6) {
        uint16_t kp = (uartBuffer[3] << 8) | uartBuffer[4];
        uint16_t ki = (uartBuffer[5] << 8) | uartBuffer[6];
        uint16_t kd = (uartBuffer[7] << 8) | uartBuffer[8];
        configurePIDParameters(kp/1000.0, ki/1000.0, kd/1000.0);
      }
      break;
      
    case CMD_EMERGENCY_STOP:
      executeEmergencyStop();
      break;
      
    case CMD_SWEEP_CONTROL:
      if (dataLength >= 1) {
        sweepSamples = constrain(uartBuffer[3], SWEEP_MIN, SWEEP_MAX);
      }
      break;
      
    case CMD_SYSTEM_RESET:
      resetSystemState();
      break;
  }
  
  sendAcknowledgment(commandType);
  uartBufferIndex = 0;
}

void handleUARTCommunication() {
  while (Serial.available()) {
    uint8_t b = Serial.read();                          // read one byte
    lastUartActivity = millis();

#if ENABLE_UART_DEBUG
    Serial.print(F("RAW: 0x"));
    if (b < 0x10) Serial.print("0");
    Serial.print(b, HEX);
    Serial.print(F(" (")); Serial.print(b); Serial.println(F(")"));
#endif

    // Only start a new packet on 0xAA
    if (b == CMD_START_BYTE) {
      uartBufferIndex = 0;
      commandInProgress = true;
    }

    if (commandInProgress && uartBufferIndex < UART_BUFFER_SIZE) {
      uartBuffer[uartBufferIndex++] = b;

      // We need at least: start + type + len + checksum + end = 5 bytes (for len=0)
      if (uartBufferIndex >= 5 && uartBuffer[0] == CMD_START_BYTE) {
        uint8_t dataLen = uartBuffer[2];
        uint8_t totalLen = 4 + dataLen + 1;    // start + cmd + len + data + checksum + END

        if (uartBufferIndex >= totalLen && uartBuffer[totalLen-1] == CMD_END_BYTE) {
          // ONLY NOW we have a complete valid packet including 0x55
#if ENABLE_UART_DEBUG
          Serial.print(F("*** COMPLETE PACKET (")); 
          Serial.print(totalLen); 
          Serial.print(F(" bytes): "));
          debugHex(uartBuffer, totalLen, "");
#endif
          processIncomingCommand();
          commandInProgress = false;
          uartBufferIndex = 0;
          return;        // important: start fresh for next packet
        }
      }
    }

    if (uartBufferIndex >= UART_BUFFER_SIZE) {
      Serial.println(F("!!! BUFFER OVERFLOW !!!"));
      uartBufferIndex = 0;
      commandInProgress = false;
    }
  }
}

// ----------------------- MOTOR CONTROL FUNCTIONS -----------------------
void controlMotors(int leftPWM, int rightPWM, bool forwardDirection) {
  // Apply constraints and deadzone
  leftPWM = constrain(leftPWM, 0, 255);
  rightPWM = constrain(rightPWM, 0, 255);
  
  // Motor deadzone compensation
  if (leftPWM < 25) leftPWM = 0;
  if (rightPWM < 25) rightPWM = 0;
  
  motorLeftPWM = leftPWM;
  motorRightPWM = rightPWM;
  
  if (forwardDirection) {
    analogWrite(ENA, leftPWM);
    analogWrite(ENB, rightPWM);
    digitalWrite(IN1, HIGH); 
    digitalWrite(IN2, LOW);
    digitalWrite(IN3, HIGH); 
    digitalWrite(IN4, LOW);
  } else {
    analogWrite(ENA, leftPWM);
    analogWrite(ENB, rightPWM);
    digitalWrite(IN1, LOW); 
    digitalWrite(IN2, HIGH);
    digitalWrite(IN3, LOW); 
    digitalWrite(IN4, HIGH);
  }
  
  isMoving = (leftPWM > 0 || rightPWM > 0);
}

void stopAllMotors() {
  controlMotors(0, 0, true);
  isMoving = false;
  headingController.deactivate();
  velocityController.deactivate();
  desiredVelocity = 0.0;
  motorTargetPWM = 0;
  motorCurrentPWM = 0;
}

void setVelocityTarget(float velocity) {
  desiredVelocity = constrain(velocity, -0.4, 0.6);
  if (fabs(desiredVelocity) < 0.05) {
    velocityController.deactivate();
    motorTargetPWM = 0;
  } else {
    velocityController.activate(desiredVelocity);
  }
}

void executeEmergencyStop() {
  stopAllMotors();
  systemNavigationState = 0;
  hasActiveDestination = false;
  returningToHome = false;
}

// ----------------------- MOVEMENT COMMAND EXECUTION -----------------------
void executeMovementCommand(uint8_t command) {
  switch(command) {
    case MOVE_STOP: 
      stopAllMotors();
      break;
      
    case MOVE_FORWARD: 
      motorDirectionForward = true; 
      setVelocityTarget(0.3);
      headingController.deactivate();
      hasActiveDestination = false;
      break;
      
    case MOVE_BACKWARD: 
      motorDirectionForward = false; 
      setVelocityTarget(-0.2);
      headingController.deactivate();
      hasActiveDestination = false;
      break;
      
    case MOVE_LEFT: 
      motorTargetPWM = 120; 
      applyCorrectedDrive(motorCurrentPWM, -40.0, true); 
      headingController.deactivate();
      hasActiveDestination = false;
      break;
      
    case MOVE_RIGHT: 
      motorTargetPWM = 120; 
      applyCorrectedDrive(motorCurrentPWM, 40.0, true); 
      headingController.deactivate();
      hasActiveDestination = false;
      break;
      
    case MOVE_CALIBRATE: 
      if (calibrationState == CAL_IDLE) { 
        calibrationState = CAL_RUNNING; 
        calibrationStep = 0; 
        calibrationStartTime = 0; 
      }
      break;
      
    case MOVE_RETURN_HOME:
      setNavigationTarget(homeX, homeY);
      returningToHome = true;
      break;
  }
}

// ----------------------- NAVIGATION FUNCTIONS -----------------------
void setNavigationTarget(float x, float y) {
  targetX = x;
  targetY = y;
  hasActiveDestination = true;
  returningToHome = false;
  
  // Calculate initial heading to target
  float deltaX = targetX - currentX;
  float deltaY = targetY - currentY;
  float targetHeading = atan2(deltaY, deltaX) * 180.0 / PI;
  targetHeading = normalizeAngle(targetHeading);
  
  headingController.activate(targetHeading);
  setVelocityTarget(0.25);
  
  systemNavigationState = 1;
}

void updateNavigationSystem() {
  if (!hasActiveDestination || !isMoving) return;
  
  // Calculate target direction and distance
  float deltaX = targetX - currentX;
  float deltaY = targetY - currentY;
  float distanceToTarget = sqrt(deltaX * deltaX + deltaY * deltaY);
  
  // Calculate target heading
  float targetHeading = atan2(deltaY, deltaX) * 180.0 / PI;
  targetHeading = normalizeAngle(targetHeading);
  
  // Update heading controller
  headingController.activate(targetHeading);
  
  // Adaptive velocity control
  float headingError = fabs(calculateAngleDifference(currentHeading, targetHeading));
  float adaptiveSpeed = desiredVelocity;
  
  // Speed reduction near target or with large heading errors
  if (distanceToTarget < 0.5) {
    adaptiveSpeed = desiredVelocity * (distanceToTarget / 0.5);
  }
  if (headingError > 25.0) {
    adaptiveSpeed *= (25.0 / headingError);
  }
  
  setVelocityTarget(adaptiveSpeed);
  
  // Check for destination arrival
  if (distanceToTarget < 0.08) {
    hasActiveDestination = false;
    returningToHome = false;
    stopAllMotors();
  }
}

// ----------------------- SENSOR FUNCTIONS -----------------------
uint8_t readFilteredSonar() {
  unsigned int distance = sonar.ping_cm();
  if (distance == 0) return MAX_DISTANCE_CM;
  
  // Median filtering
  static uint16_t distanceHistory[3] = {MAX_DISTANCE_CM, MAX_DISTANCE_CM, MAX_DISTANCE_CM};
  static uint8_t historyIndex = 0;
  
  distanceHistory[historyIndex] = distance;
  historyIndex = (historyIndex + 1) % 3;
  
  // Simple median calculation
  uint16_t a = distanceHistory[0], b = distanceHistory[1], c = distanceHistory[2];
  if ((a <= b && b <= c) || (c <= b && b <= a)) return b;
  if ((b <= a && a <= c) || (c <= a && a <= b)) return a;
  return c;
}

void calibrateIMUSensors() {
  long gyroXSum = 0, gyroYSum = 0, gyroZSum = 0;
  long accelXSum = 0, accelYSum = 0, accelZSum = 0;
  int16_t accelX, accelY, accelZ, gyroX, gyroY, gyroZ;
  
  for (int i = 0; i < 400; i++) {
    mpu.getMotion6(&accelX, &accelY, &accelZ, &gyroX, &gyroY, &gyroZ);
    gyroXSum += gyroX; gyroYSum += gyroY; gyroZSum += gyroZ;
    accelXSum += accelX; accelYSum += accelY; accelZSum += accelZ;
    delay(2);
  }
  
  gyroBiasX = (float)gyroXSum / 400;
  gyroBiasY = (float)gyroYSum / 400;
  gyroBiasZ = (float)gyroZSum / 400;
  accelBiasX = (float)accelXSum / 400;
  accelBiasY = (float)accelYSum / 400;
  accelBiasZ = (float)accelZSum / 400 - 16384;
  
  imuCalibrated = true;
  lastOdometryUpdate = millis();
  headingController.reset();
  velocityController.reset();
}

void updateOdometry() {
  if (!imuCalibrated) return;
  
  unsigned long currentTime = millis();
  float deltaTime = (currentTime - lastOdometryUpdate) / 1000.0;
  if (deltaTime <= 0 || deltaTime > 0.1) {
    lastOdometryUpdate = currentTime;
    return;
  }
  
  // Read IMU data
  int16_t accelX, accelY, accelZ, gyroX, gyroY, gyroZ;
  mpu.getMotion6(&accelX, &accelY, &accelZ, &gyroX, &gyroY, &gyroZ);
  
  // Apply calibration offsets
  float gyroRate = ((float)gyroX - gyroBiasX) / 131.0;
  float accelXG = ((float)accelX - accelBiasX) / 16384.0;
  float accelYG = ((float)accelY - accelBiasY) / 16384.0;
  
  // Gyro filtering
  static float filteredGyro = 0.0;
  gyroRate = applyExponentialFilter(filteredGyro, gyroRate, 0.2);
  filteredGyro = gyroRate;
  
  // Complementary filter for heading
  float accelHeading = atan2(-accelXG, accelYG) * 180.0 / PI;
  accelHeading = normalizeAngle(accelHeading);
  
  currentHeading = 0.98 * (currentHeading + gyroRate * deltaTime) + 0.02 * accelHeading;
  currentHeading = normalizeAngle(currentHeading);
  
  // Velocity estimation from motor PWM
  currentVelocity = (motorCurrentPWM / 255.0) * 0.5;
  
  // Position update when moving
  if (isMoving && motorCurrentPWM > 20) {
    float distance = currentVelocity * deltaTime;
    float headingRadians = currentHeading * PI / 180.0;
    currentX += distance * cos(headingRadians);
    currentY += distance * sin(headingRadians);
  }
  
  lastOdometryUpdate = currentTime;
}

// ----------------------- CALIBRATION FUNCTIONS -----------------------
void performAutoCalibration() {
  if (calibrationState != CAL_RUNNING) return;
  
  if (calibrationStep >= CALIBRATION_ITERATIONS) {
    calibrationState = CAL_COMPLETE;
    EEPROM.update(EE_SIG_ADDR, EE_SIG_VALUE);
    EEPROM.update(EE_LEFT_TRIM, leftTrimValue);
    EEPROM.update(EE_RIGHT_TRIM, rightTrimValue);
    EEPROM.update(EE_FLAG_CAL, 1);
    
    // Store home position
    homeX = currentX;
    homeY = currentY;
    writeFloatToEEPROM(EE_HOME_X, homeX);
    writeFloatToEEPROM(EE_HOME_Y, homeY);
    
    sendAcknowledgment(CMD_CALIBRATION);
    return;
  }
  
  if (calibrationStartTime == 0) {
    calibrationStartHeading = currentHeading;
    controlMotors(
      (int)(150 * (leftTrimValue / 128.0)), 
      (int)(150 * (rightTrimValue / 128.0)), 
      true
    );
    calibrationStartTime = millis();
  } 
  else {
    if (millis() - calibrationStartTime >= CALIBRATION_DRIVE_MS) {
      stopAllMotors();
      float headingDrift = calculateAngleDifference(calibrationStartHeading, currentHeading);
      
      float trimAdjustment = -headingDrift * 0.3;
      int leftAdjusted = (int)leftTrimValue + (int)round(trimAdjustment);
      int rightAdjusted = (int)rightTrimValue - (int)round(trimAdjustment);
      leftAdjusted = constrain(leftAdjusted, 100, 156);
      rightAdjusted = constrain(rightAdjusted, 100, 156);
      leftTrimValue = (uint8_t)leftAdjusted; 
      rightTrimValue = (uint8_t)rightAdjusted;
      
      calibrationStep++;
      calibrationStartTime = 0;
      delay(150);
    }
  }
}

// ----------------------- CONTROL SYSTEM FUNCTIONS -----------------------
void updateControlSystem() {
  unsigned long currentTime = millis();
  
  // Velocity controller update
  if (velocityController.isActive()) {
    float velocityAdjustment = velocityController.compute(currentVelocity, currentTime);
    motorTargetPWM = constrain((int)(velocityAdjustment * 255.0), 0, 255);
  }
  
  // Motor PWM smoothing
  if (motorCurrentPWM != motorTargetPWM) {
    int pwmStep = (motorTargetPWM > motorCurrentPWM) ? 8 : -8;
    motorCurrentPWM = constrain(motorCurrentPWM + pwmStep, 0, motorTargetPWM);
  }
  
  // Heading correction during movement
  if (headingController.isActive() && isMoving && motorCurrentPWM > 20) {
    float headingCorrection = headingController.compute(currentHeading, currentTime);
    headingCorrection = constrain(headingCorrection, -50, 50);
    
    // Apply motor control with heading correction
    float leftFactor = leftTrimValue / 128.0;
    float rightFactor = rightTrimValue / 128.0;
    int leftPWM = (int)(motorCurrentPWM * leftFactor - headingCorrection);
    int rightPWM = (int)(motorCurrentPWM * rightFactor + headingCorrection);
    controlMotors(leftPWM, rightPWM, motorDirectionForward);
  }
  else if (isMoving) {
    // Direct motor control without heading correction
    controlMotors(motorCurrentPWM, motorCurrentPWM, motorDirectionForward);
  }
  
  // Navigation system update
  if (hasActiveDestination && isMoving) {
    updateNavigationSystem();
  }
}

void applyCorrectedDrive(int basePWM, float correction, bool forward) {
  float leftFactor = leftTrimValue / 128.0;
  float rightFactor = rightTrimValue / 128.0;
  int leftPWM = (int)(basePWM * leftFactor - correction * 0.7);
  int rightPWM = (int)(basePWM * rightFactor + correction * 0.7);
  controlMotors(leftPWM, rightPWM, forward);
}

void configurePIDParameters(float kp, float ki, float kd) {
  headingController.configureParameters(kp, ki, kd, 180.0, 75.0);
  velocityController.configureParameters(kp * 1.8, ki * 0.4, kd * 0.08, 120.0, 90.0);
  
  // Save to EEPROM
  writeFloatToEEPROM(EE_PID_KP, kp);
  writeFloatToEEPROM(EE_PID_KI, ki);
  writeFloatToEEPROM(EE_PID_KD, kd);
  EEPROM.update(EE_SIG_ADDR, EE_SIG_VALUE);
}

// ----------------------- SAFETY & MONITORING FUNCTIONS -----------------------
void performSafetyChecks() {
  unsigned long currentTime = millis();
  
  // Command timeout safety
  if (currentTime - lastCommandReceived > 20000 && isMoving) {
    stopAllMotors();
    systemNavigationState = 0;
  }
  
  // Obstacle detection and avoidance
  uint8_t frontObstacleDistance = readFilteredSonar();
  if (frontObstacleDistance < 30 && isMoving) {
    obstacleDetected = true;
    if (systemNavigationState == 1) {
      stopAllMotors();
      systemNavigationState = 2;
      // Simple obstacle avoidance: turn right
      motorTargetPWM = 100;
      applyCorrectedDrive(motorCurrentPWM, 50.0, true);
      delay(350);
      stopAllMotors();
      systemNavigationState = 1;
      obstacleDetected = false;
    }
  } else {
    obstacleDetected = false;
  }
}

void updateServoSweep() {
  currentServoAngle += servoDirection;
  if (currentServoAngle > SERVO_MAX_ANGLE) { 
    currentServoAngle = SERVO_MAX_ANGLE; 
    servoDirection = -1; 
  }
  if (currentServoAngle < SERVO_MIN_ANGLE) { 
    currentServoAngle = SERVO_MIN_ANGLE; 
    servoDirection = 1; 
  }
  sweepServo.write(currentServoAngle);
}

void loadSystemSettings() {
  if (EEPROM.read(EE_SIG_ADDR) == EE_SIG_VALUE) {
    leftTrimValue = EEPROM.read(EE_LEFT_TRIM);
    rightTrimValue = EEPROM.read(EE_RIGHT_TRIM);
    
    float kp = readFloatFromEEPROM(EE_PID_KP);
    float ki = readFloatFromEEPROM(EE_PID_KI);
    float kd = readFloatFromEEPROM(EE_PID_KD);
    
    if (kp > 0) headingController.configureParameters(kp, ki, kd, 180.0, 75.0);
    if (ki > 0) velocityController.configureParameters(kp * 1.8, ki * 0.4, kd * 0.08, 120.0, 90.0);
    
    homeX = readFloatFromEEPROM(EE_HOME_X);
    homeY = readFloatFromEEPROM(EE_HOME_Y);
  } else {
    leftTrimValue = 128; 
    rightTrimValue = 128;
  }
}

void resetSystemState() {
  stopAllMotors();
  currentX = 0.0;
  currentY = 0.0;
  currentHeading = 0.0;
  systemNavigationState = 0;
  hasActiveDestination = false;
  returningToHome = false;
  calibrationState = CAL_IDLE;
}

// ----------------------- ARDUINO SETUP -----------------------
void setup() {
  // Initialize UART communication
  Serial.begin(UART_BAUD_RATE);
  
  // Configure motor control pins
  pinMode(ENA, OUTPUT); 
  pinMode(IN1, OUTPUT); 
  pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT); 
  pinMode(IN3, OUTPUT); 
  pinMode(IN4, OUTPUT);
  stopAllMotors();

  // Initialize servo
  sweepServo.attach(SERVO_PIN);
  sweepServo.write(currentServoAngle);

  // Initialize IMU
  Wire.begin();
  mpu.initialize();
  loadSystemSettings();
  
  if (mpu.testConnection()) {
    calibrateIMUSensors();
  }

  // Initialize timing variables
  lastControlUpdate = millis(); 
  lastTelemetrySend = millis();
  lastSafetyCheck = millis();
  lastServoSweep = millis();
  lastCommandReceived = millis();
  
  // Initialize PID controllers
  headingController.reset();
  velocityController.reset();
}

// ----------------------- ARDUINO MAIN LOOP -----------------------
void loop() {
  unsigned long currentTime = millis();

  // Process incoming UART commands
  handleUARTCommunication();

  // High-priority control loop (10ms)
  if (currentTime - lastControlUpdate >= CONTROL_LOOP_MS) {
    updateControlSystem();
    lastControlUpdate = currentTime;
  }

  // Automatic telemetry transmission
  if (currentTime - lastTelemetrySend >= TELEMETRY_INTERVAL_MS) {
    sendTelemetryData();
    lastTelemetrySend = currentTime;
  }

  // Calibration process
  performAutoCalibration();

  // Safety monitoring (50ms)
  if (currentTime - lastSafetyCheck >= SAFETY_CHECK_MS) {
    performSafetyChecks();
    lastSafetyCheck = currentTime;
  }

  // Servo sweeping (25ms)
  if (currentTime - lastServoSweep >= SWEEP_INTERVAL_MS) {
    updateServoSweep();
    lastServoSweep = currentTime;
  }

  // Update sensor data and odometry
  updateOdometry();
}
```

## Summary
- Total files: 4
- Total directories: 2
- Warnings: 0